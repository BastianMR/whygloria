#!/usr/bin/env python3
"""Convert the source files in SIN_PROCESAR/ into OKF markdown concepts.

PDFs: uploads one at a time to the local docling-serve container (the same backend
the docling MCP wraps), writes the markdown into the matching circulares/ or
resoluciones/ folder with frontmatter rendered by check_okf.py, and rebuilds that
folder's index. Documents whose number is already converted are skipped, so
re-running resumes where it stopped.

HTML: the oficios up to 2018 exist only as an HTML page plus a Word twin, and
docling cannot read them, so their body is stripped from the page by
`html_to_markdown` below. It is the same pipeline, not a second one: the same
loop, the same frontmatter, the same index. No converter service is needed, so a
run made only of HTML years does not ask for one.

Archives (`.zip`) are reported, not converted: they bundle several documents.

*Suplementos Tributarios* are PDFs and Word files that shipped inside a circular
`.zip`; they convert through the same docling upload, with the content type their
suffix declares. The legacy Word 97 `.doc` one is outside the toolchain and is
recorded as a blocker next to its circular instead of being converted.

*Formularios* are PDFs too, one declaración jurada per layout and one per set of
instructions. Their concept keeps the source stem, because one DJ number is two
documents and the number alone cannot say which of the two a file is.

Usage:
    python scripts/pdf_to_md.py --limit 3     # smoke test
    python scripts/pdf_to_md.py               # everything pending
    python scripts/pdf_to_md.py --years 2016 2019
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_okf
import sii_pdfs
from sii_pdfs import MD, MIRROR, NOUN, PREFIX, RAW, ROOT, keys, number_key

SERVE = "http://127.0.0.1:5001"
# docling picks its backend from the declared type, so the upload names the type
# the suffix carries. A `.docx` announced as `application/pdf` is rejected.
CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
# The SII letterhead arrives as an empty image placeholder; the corpus has none.
NOISE = re.compile(r"^\s*<!-- image -->\s*$", re.MULTILINE)
# The pre-2019 oficio pages are plain paragraphs: blocks become paragraph breaks,
# `<br>` a line break, and what is left of the tags is dropped.
HTML_DROP_RE = re.compile(r"(?is)<(script|style|head)\b.*?</\1\s*>")
HTML_COMMENT_RE = re.compile(r"(?is)<!--.*?-->")
HTML_BREAK_RE = re.compile(r"(?i)<br\b[^>]*>")
HTML_BLOCK_RE = re.compile(
    r"(?i)</?(?:p|div|h[1-6]|li|ul|ol|dl|dt|dd|table|thead|tbody|tr|td|th"
    r"|blockquote|pre|hr|section|article)\b[^>]*>"
)
HTML_TAG_RE = re.compile(r"(?s)<[^>]+>")


def html_to_markdown(page: Path) -> str:
    """The body of an HTML source as markdown text.

    Deterministic, and the reason the pre-2019 oficios need no converter service.
    SII serves those pages as UTF-8 **with a BOM** and the repository rejects a
    BOM, so it is decoded away here. Entities are unescaped and the blank-line runs
    the block tags leave behind are collapsed to one.
    """
    text = page.read_bytes().decode("utf-8-sig", "replace")
    text = HTML_DROP_RE.sub("", text)
    text = HTML_COMMENT_RE.sub("", text)
    text = HTML_BREAK_RE.sub("\n", text)
    text = HTML_BLOCK_RE.sub("\n\n", text)
    text = HTML_TAG_RE.sub("", text)
    text = html.unescape(text).replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    kept: list[str] = []
    for line in lines:
        if line:
            kept.append(line)
        elif kept and kept[-1]:
            kept.append("")
    return "\n".join(kept).strip() + "\n"


def source_patterns(kind: str) -> tuple[str, ...]:
    """The source suffixes a folder can hold.

    A circular year also holds its *Suplemento Tributario*, which SII published as a
    Word file whenever it did not publish a PDF.
    """
    return ("*.pdf", "*.docx") if kind == "CIRCULAR" else ("*.pdf",)


def is_html_folder(name: str) -> bool:
    """Only the pre-2019 oficios publish HTML instead of a PDF."""
    year, kind = name.split("-", 1)
    return kind == "OFICIO" and sii_pdfs.oficio_branch(int(year)) == "html"


def needs_docling(sources: dict[str, list[Path]]) -> bool:
    """Whether the selection still has a PDF to convert.

    The HTML branch reads the page itself, so a run made only of those years must
    not require the converter service. A run that does need it still fails loudly
    and before converting anything.
    """
    for name, folders in sources.items():
        if is_html_folder(name):
            continue
        kind = name.split("-", 1)[1]
        if kind not in MD:
            continue
        have = converted_keys(MD[kind] / name)
        for source in (
            p
            for folder in folders
            for pattern in source_patterns(kind)
            for p in folder.glob(pattern)
        ):
            found = keys([source.name])
            if found and not found <= have:
                return True
    return False


def to_markdown(source: Path) -> str:
    """Async endpoint: the sync one answers 504 on documents over ~3 minutes."""
    content_type = CONTENT_TYPES.get(source.suffix.lower(), "application/octet-stream")
    with source.open("rb") as handle:
        response = requests.post(
            f"{SERVE}/v1/convert/file/async",
            files={"files": (source.name, handle, content_type)},
            data={"to_formats": "md", "image_export_mode": "placeholder"},
            timeout=120,
        )
    response.raise_for_status()
    task = response.json()["task_id"]

    deadline = time.monotonic() + 90 * 60
    while True:
        try:
            poll = requests.get(f"{SERVE}/v1/status/poll/{task}", timeout=60)
            if poll.status_code == 404:
                # The service forgets every task when it restarts, and these
                # documents are long enough that a restart mid-conversion happens.
                # A missing task is a failure, not a reason to wait forever.
                raise RuntimeError("docling lost the task (did the service restart?)")
            poll.raise_for_status()
            status = poll.json()
        except requests.RequestException:
            # The service is single-flight: while it converts, it answers no request
            # at all, and these documents run to ~900 pages. Failing to ask is not
            # the task failing, so keep waiting until the deadline.
            if time.monotonic() > deadline:
                raise RuntimeError("docling task exceeded 90 minutes")
            time.sleep(10)
            continue
        if status.get("task_status") == "success":
            break
        if status.get("task_status") == "failure":
            raise RuntimeError(status.get("error_message") or "docling task failed")
        if time.monotonic() > deadline:
            raise RuntimeError("docling task exceeded 90 minutes")
        time.sleep(2)

    payload = requests.get(f"{SERVE}/v1/result/{task}", timeout=120).json()
    if payload.get("status") != "success":
        raise RuntimeError(payload.get("errors") or payload.get("status"))
    return NOISE.sub("", payload["document"]["md_content"]).strip() + "\n"


def converted_keys(folder: Path) -> set:
    return keys(p.name for p in folder.glob("*.md") if p.name != "index.md")


def write_if_changed(path: Path, text: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return
    path.write_text(text, encoding="utf-8", newline="\n")


def sort_key(path: Path) -> tuple[int, str]:
    return number_key(path)


def reindex(folder: Path) -> None:
    entries = sorted(
        (p for p in folder.glob("*.md") if p.name != "index.md"), key=sort_key
    )
    lines = [f"# {folder.name}", ""]
    lines += [f"* [{p.stem}](./{p.name})" for p in entries]
    write_if_changed(folder / "index.md", "\n".join(lines) + "\n")


def reindex_parent(folder: Path, label: str) -> None:
    if not folder.exists():
        return
    lines = [f"# {label}", ""]
    for child in sorted(d for d in folder.iterdir() if d.is_dir()):
        year, kind = child.name.split("-", 1)
        lines.append(f"* [{child.name}]({child.name}/) - {NOUN.get(kind, kind)} SII {year}")
    write_if_changed(folder / "index.md", "\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--years", type=int, nargs="+", help="only these years")
    parser.add_argument(
        "--kind",
        nargs="+",
        choices=tuple(MD),
        help="only these families (default: all of them)",
    )
    parser.add_argument("--limit", type=int, help="stop after N conversions")
    parser.add_argument("--no-reindex", action="store_true")
    args = parser.parse_args()

    sources: dict[str, list[Path]] = {}
    folders: list[Path] = []
    for root in (RAW, *MIRROR.values(), sii_pdfs.SRC_OFICIOS):
        if not root.exists():
            continue
        folders += [f for f in root.iterdir() if f.is_dir() and "-" in f.name]
    # The *Suplementos* were unpacked one level down, beside the archive members SII
    # named them with, so that folder joins the scan.
    folders += [f for f in sii_pdfs.SUPLEMENTOS.glob("*-*") if f.is_dir()]
    for folder in folders:
        sources.setdefault(folder.name, []).append(folder)
    if args.years:
        sources = {k: v for k, v in sources.items() if int(k.split("-")[0]) in args.years}
    if args.kind:
        # One family at a time: a run for a new family must not convert the backlog
        # of the others by accident.
        sources = {k: v for k, v in sources.items() if k.split("-", 1)[1] in args.kind}

    # Only ask for a converter when the selection contains something to convert
    # through docling: the HTML branch strips its own pages and needs none.
    if needs_docling(sources):
        try:
            requests.get(f"{SERVE}/health", timeout=5).raise_for_status()
        except requests.RequestException as exc:
            print(f"docling-serve not reachable at {SERVE}: {exc}", file=sys.stderr)
            return 2

    converted = skipped = failed = 0
    touched: set[Path] = set()
    archives: set[str] = set()
    oficio_records: dict[str, dict] = {}
    oficio_year: str | None = None
    oficio_session = requests.Session()
    oficio_session.headers.update(sii_pdfs.HEADERS)

    for name in sorted(sources, key=lambda n: (int(n.split("-")[0]), n)):
        year, kind = name.split("-", 1)
        if kind not in MD:
            continue
        is_html = is_html_folder(name)
        target_dir = MD[kind] / name
        have = converted_keys(target_dir)
        folders = sources[name]
        if kind == "OFICIO" and not is_html and oficio_year != year:
            # SII's own subject for each oficio: `materia` cannot come from the
            # body because the conversion drops the header line. The register is
            # per year, so it has to be refetched when the year changes.
            oficio_records = sii_pdfs.oficio_records(oficio_session, int(year))
            oficio_year = year

        patterns = ("*.html",) if is_html else source_patterns(kind)
        candidates: list[Path] = []
        for folder in folders:
            if folder.parent == sii_pdfs.SUPLEMENTOS:
                candidates += sii_pdfs.suplemento_sources(folder)
            else:
                candidates += [p for pattern in patterns for p in folder.glob(pattern)]
        for pdf in sorted(candidates):
            if args.limit and converted >= args.limit:
                break
            found = keys([pdf.name])
            if not found:
                print(f"no document identity in {name}/{pdf.name}", file=sys.stderr)
                failed += 1
                continue
            key = next(iter(found))
            if key in have:
                skipped += 1
                continue

            # Circulares and resoluciones keep their number-derived concept name;
            # an oficio reuses its source stem, which already carries materia and,
            # from 2019 on, publication date because the number alone is not unique.
            # A *Suplemento Tributario* is named after its circular, so its key
            # already is the whole stem. A declaración jurada needs the stem for the
            # same reason as an oficio: `dj<N>` names two documents.
            if kind in ("OFICIO", "FORMULARIO"):
                stem = pdf.stem
            else:
                stem = key if isinstance(key, str) else f"{PREFIX[kind]}{key}"
            destination = target_dir / f"{year}_{kind}_{stem}.md"
            started = time.time()
            try:
                body = html_to_markdown(pdf) if is_html else to_markdown(pdf)
            except Exception as exc:
                print(f"FAILED {name}/{pdf.name}: {exc}", file=sys.stderr)
                failed += 1
                continue

            # Oficios lose their header line in conversion, so their `materia` and
            # `fecha` are read from the source record and page 1 of the PDF.
            record = oficio_records.get(pdf.name, {}) if kind == "OFICIO" else {}
            meta = check_okf.concept_meta(
                destination,
                body,
                from_pdf=kind == "OFICIO" and not is_html,
                oficio_legal=str(record.get("pubLegal") or "").strip(),
            )
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(
                check_okf.render_frontmatter(meta) + body, encoding="utf-8", newline="\n"
            )
            have.add(key)
            touched.add(target_dir)
            converted += 1
            print(
                f"{destination.relative_to(ROOT)}  {time.time() - started:.1f}s  {len(body)} chars",
                flush=True,
            )

        for archive in sorted(p for folder in folders for p in folder.glob("*.zip")):
            found = keys([archive.name])
            if found and not found <= have:
                archives.add(archive.name)

    if not args.no_reindex and touched:
        for folder in sorted(touched):
            reindex(folder)
        reindex_parent(MD["CIRCULAR"], "Circulares SII")
        reindex_parent(MD["RESOLUCION"], "Resoluciones SII")
        reindex_parent(MD["OFICIO"], "Oficios SII")
        reindex_parent(MD["FORMULARIO"], "Formularios SII")

    print(f"\nconverted={converted} skipped={skipped} failed={failed}")
    if archives:
        print(f"archives need unpacking ({len(archives)}): {' '.join(sorted(archives))}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
