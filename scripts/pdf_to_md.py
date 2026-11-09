#!/usr/bin/env python3
"""Convert the source PDFs in sin-procesar/ into OKF markdown concepts.

Uploads one PDF at a time to the local docling-serve container (the same backend
the docling MCP wraps), writes the markdown into the matching circulares/ or
resoluciones/ folder with frontmatter rendered by check_okf.py, and rebuilds that
folder's index. Documents whose number is already converted are skipped, so
re-running resumes where it stopped.

Archives (`.zip`) are reported, not converted: they bundle several documents.

Usage:
    python scripts/pdf_to_md.py --limit 3     # smoke test
    python scripts/pdf_to_md.py               # everything pending
    python scripts/pdf_to_md.py --years 2016 2019
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_okf
from sii_pdfs import NUMBER_RE, PREFIX, PROCESSED, RAW, ROOT

SERVE = "http://127.0.0.1:5001"
# The SII letterhead arrives as an empty image placeholder; the corpus has none.
NOISE = re.compile(r"^\s*<!-- image -->\s*$", re.MULTILINE)


def to_markdown(pdf: Path) -> str:
    """Async endpoint: the sync one answers 504 on documents over ~3 minutes."""
    with pdf.open("rb") as handle:
        response = requests.post(
            f"{SERVE}/v1/convert/file/async",
            files={"files": (pdf.name, handle, "application/pdf")},
            data={"to_formats": "md", "image_export_mode": "placeholder"},
            timeout=120,
        )
    response.raise_for_status()
    task = response.json()["task_id"]

    deadline = time.monotonic() + 1800
    while True:
        status = requests.get(f"{SERVE}/v1/status/poll/{task}", timeout=60).json()
        if status.get("task_status") == "success":
            break
        if status.get("task_status") == "failure":
            raise RuntimeError(status.get("error_message") or "docling task failed")
        if time.monotonic() > deadline:
            raise RuntimeError("docling task exceeded 30 minutes")
        time.sleep(2)

    payload = requests.get(f"{SERVE}/v1/result/{task}", timeout=120).json()
    if payload.get("status") != "success":
        raise RuntimeError(payload.get("errors") or payload.get("status"))
    return NOISE.sub("", payload["document"]["md_content"]).strip() + "\n"


def converted_numbers(folder: Path) -> set[int]:
    found = set()
    for path in folder.glob("*.md"):
        if path.name != "index.md":
            match = NUMBER_RE.search(path.name)
            if match:
                found.add(int(match.group(1)))
    return found


def write_if_changed(path: Path, text: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return
    path.write_text(text, encoding="utf-8", newline="\n")


def sort_key(path: Path) -> tuple[int, str]:
    match = NUMBER_RE.search(path.name)
    return (int(match.group(1)) if match else 10**6, path.name)


def reindex(folder: Path) -> None:
    entries = sorted(
        (p for p in folder.glob("*.md") if p.name != "index.md"), key=sort_key
    )
    lines = [f"# {folder.name}", ""]
    lines += [f"* [{p.stem}](./{p.name})" for p in entries]
    write_if_changed(folder / "index.md", "\n".join(lines) + "\n")


def reindex_parent(folder: Path, label: str) -> None:
    lines = [f"# {label}", ""]
    for child in sorted(d for d in folder.iterdir() if d.is_dir()):
        year, kind = child.name.split("-", 1)
        noun = "Circulares" if kind == "CIRCULAR" else "Resoluciones"
        lines.append(f"* [{child.name}]({child.name}/) - {noun} SII {year}")
    write_if_changed(folder / "index.md", "\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--years", type=int, nargs="+", help="only these years")
    parser.add_argument("--limit", type=int, help="stop after N conversions")
    parser.add_argument("--no-reindex", action="store_true")
    args = parser.parse_args()

    try:
        requests.get(f"{SERVE}/health", timeout=5).raise_for_status()
    except requests.RequestException as exc:
        print(f"docling-serve not reachable at {SERVE}: {exc}", file=sys.stderr)
        return 2

    raw_dirs = sorted(p for p in RAW.iterdir() if p.is_dir() and "-" in p.name)
    if args.years:
        raw_dirs = [p for p in raw_dirs if int(p.name.split("-")[0]) in args.years]

    converted = skipped = failed = 0
    touched: set[Path] = set()
    archives: set[str] = set()

    for raw_dir in raw_dirs:
        year, kind = raw_dir.name.split("-", 1)
        if kind not in PROCESSED:
            continue
        target_dir = ROOT / PROCESSED[kind] / raw_dir.name
        have = converted_numbers(target_dir)

        for pdf in sorted(raw_dir.glob("*.pdf")):
            if args.limit and converted >= args.limit:
                break
            match = NUMBER_RE.search(pdf.name)
            if not match:
                print(f"no document number in {raw_dir.name}/{pdf.name}", file=sys.stderr)
                failed += 1
                continue
            number = int(match.group(1))
            if number in have:
                skipped += 1
                continue

            destination = target_dir / f"{year}_{kind}_{PREFIX[kind]}{number}.md"
            started = time.time()
            try:
                body = to_markdown(pdf)
            except Exception as exc:
                print(f"FAILED {raw_dir.name}/{pdf.name}: {exc}", file=sys.stderr)
                failed += 1
                continue

            meta = check_okf.concept_meta(destination, body)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(
                check_okf.render_frontmatter(meta) + body, encoding="utf-8", newline="\n"
            )
            have.add(number)
            touched.add(target_dir)
            converted += 1
            print(
                f"{destination.relative_to(ROOT)}  {time.time() - started:.1f}s  {len(body)} chars",
                flush=True,
            )

        for archive in sorted(raw_dir.glob("*.zip")):
            match = NUMBER_RE.search(archive.stem)
            if match and int(match.group(1)) not in have:
                archives.add(archive.name)

    if not args.no_reindex and touched:
        for folder in sorted(touched):
            reindex(folder)
        reindex_parent(ROOT / "circulares", "Circulares SII")
        reindex_parent(ROOT / "resoluciones", "Resoluciones SII")

    print(f"\nconverted={converted} skipped={skipped} failed={failed}")
    if archives:
        print(f"archives need unpacking ({len(archives)}): {' '.join(sorted(archives))}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
