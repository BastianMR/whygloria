#!/usr/bin/env python3
"""Mirror the PDFs linked from the SII yearly circulares / resoluciones indexes.

Check mode (default) prints, per year and document type, how many documents SII
publishes, how many are already downloaded, how many are already converted to
`.md`, and which files are missing. Exits 1 when anything is missing, so it
doubles as the verification gate before and after a download.

Download mode fetches only the missing files. Each one is written to a `.part`
file and renamed only after the bytes look complete, so an interrupted run never
leaves a truncated file that later looks done.

Downloads land in the gitignored `SIN_PROCESAR/` inbox. `--publish` moves the
already converted ones into the versioned `PDF_<TYPE>/` mirror.

Usage:
    python scripts/sii_pdfs.py --check
    python scripts/sii_pdfs.py --check --list-missing
    python scripts/sii_pdfs.py --download
    python scripts/sii_pdfs.py --download --years 2024 2025
    python scripts/sii_pdfs.py --pending
    python scripts/sii_pdfs.py --unpack
    python scripts/sii_pdfs.py --publish
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import time
import zipfile
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "SIN_PROCESAR"
MD = {"CIRCULAR": ROOT / "MD_CIRCULARES", "RESOLUCION": ROOT / "MD_RESOLUCIONES"}
MIRROR = {"CIRCULAR": ROOT / "PDF_CIRCULARES", "RESOLUCION": ROOT / "PDF_RESOLUCIONES"}
BASE = "https://www.sii.cl/normativa_legislacion"
INDEX = {
    "CIRCULAR": BASE + "/circulares/{year}/indcir{year}.htm",
    "RESOLUCION": BASE + "/resoluciones/{year}/res_ind{year}.htm",
}
PREFIX = {"CIRCULAR": "circu", "RESOLUCION": "reso"}
CIRCULAR_MEMBER_RE = re.compile(r"^(?:circu|cir_|circular|reso)", re.IGNORECASE)
FIRST_YEAR = 2013
LINK_RE = re.compile(r"""href=["']([^"']+\.(?:pdf|zip))["']""", re.IGNORECASE)
NUMBER_RE = re.compile(r"(?:circu|reso)\w*?(\d+)", re.IGNORECASE)
HEADERS = {
    # Without a normal browser UA the SII front end answers 403 to requests.
    "User-Agent": "Mozilla/5.0 (compatible; WhyGloria/1.0)",
}

# The indexes mix absolute and relative hrefs, and a few documents are shipped
# as .zip instead of .pdf (e.g. circulares 2013).
def index_links(session: requests.Session, kind: str, year: int) -> dict[str, str]:
    url = INDEX[kind].format(year=year)
    response = session.get(url, timeout=30)
    response.raise_for_status()
    links: dict[str, str] = {}
    for href in LINK_RE.findall(response.text):
        full = urljoin(url, href)
        links[unquote(Path(urlsplit(full).path).name)] = full
    return dict(sorted(links.items()))


def already_processed(kind: str, year: int) -> int:
    folder = MD[kind] / f"{year}-{kind}"
    return len([p for p in folder.glob("*.md") if p.name != "index.md"])


def source_dirs(kind: str, year: int) -> list[Path]:
    """A source can sit in the local inbox or in the published PDF mirror."""
    return [root / f"{year}-{kind}" for root in (RAW, MIRROR[kind])]


def source_numbers(kind: str, year: int) -> set[int]:
    found: set[int] = set()
    for folder in source_dirs(kind, year):
        if folder.exists():
            found |= numbers(p.name for p in folder.iterdir())
    return found


def has_source(kind: str, year: int, name: str) -> bool:
    return any((folder / name).exists() for folder in source_dirs(kind, year))


def numbers(names) -> set[int]:
    """Document numbers, because source and concept filenames differ."""
    found = set()
    for name in names:
        match = NUMBER_RE.search(name)
        if match:
            found.add(int(match.group(1)))
    return found


def summarize(values: list[int], limit: int = 15) -> str:
    """`1-3 7 9-11` instead of a 209-number line."""
    if len(values) <= limit:
        return " ".join(map(str, values))
    spans: list[str] = []
    start = prev = values[0]
    for value in values[1:]:
        if value == prev + 1:
            prev = value
            continue
        spans.append(str(start) if start == prev else f"{start}-{prev}")
        start = prev = value
    spans.append(str(start) if start == prev else f"{start}-{prev}")
    return " ".join(spans)


def zip_name(info: zipfile.ZipInfo) -> str:
    """SII archives predate the UTF-8 flag, so zipfile hands back cp437 mojibake."""
    try:
        return info.filename.encode("cp437").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return info.filename.encode("cp437").decode("latin-1")


def unpack(years: list[int]) -> int:
    """Extract the circular out of the .zip archives SII ships instead of a PDF.

    Each archive bundles the circular with a *Suplemento Tributario*. Only the
    circular belongs in the bundle, so only it is extracted, under the plain
    `<circu|reso><N>.pdf` name the rest of the mirror uses.
    """
    extracted = 0
    for year in years:
        for kind in INDEX:
            raw_dir = RAW / f"{year}-{kind}"
            for archive in sorted(raw_dir.glob("*.zip")):
                match = NUMBER_RE.search(archive.stem)
                if not match:
                    print(f"{archive.relative_to(ROOT)}: no document number", file=sys.stderr)
                    continue
                with zipfile.ZipFile(archive) as bundle:
                    members = [
                        (info, zip_name(info)) for info in bundle.infolist() if not info.is_dir()
                    ]
                    primary = next(
                        (m for m in members if CIRCULAR_MEMBER_RE.match(Path(m[1]).name)), None
                    )
                    if primary is None:
                        print(f"{archive.relative_to(ROOT)}: no circular inside", file=sys.stderr)
                        continue
                    destination = raw_dir / f"{PREFIX[kind]}{int(match.group(1))}.pdf"
                    if destination.exists():
                        continue
                    with bundle.open(primary[0]) as source, destination.open("wb") as target:
                        shutil.copyfileobj(source, target)
                extracted += 1
                print(f"{destination.relative_to(ROOT)}  <- {archive.name}")
    print(f"\nextracted {extracted}")
    return 0


def pending(years: list[int]) -> int:
    total = 0
    for year in years:
        for kind in INDEX:
            doc_dir = MD[kind] / f"{year}-{kind}"
            done = numbers(p.name for p in doc_dir.glob("*.md") if p.name != "index.md")
            expected = source_numbers(kind, year)
            if not expected and not done:
                continue
            absent = sorted(expected - done)
            extra = sorted(done - expected)
            total += len(absent)
            print(f"{year}-{kind:<12} pdf={len(expected):>4} md={len(done):>4} todo={len(absent):>4}")
            if absent:
                print(f"  {summarize(absent)}")
            if extra:
                print(f"  md without pdf: {summarize(extra)}")
    print(f"\npending conversion: {total}")
    return 1 if total else 0


def number_key(path: Path) -> tuple[int, str]:
    match = NUMBER_RE.search(path.name)
    return (int(match.group(1)) if match else 10**6, path.name)


def write_if_changed(path: Path, text: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return
    path.write_text(text, encoding="utf-8", newline="\n")


def reindex_files(folder: Path) -> None:
    entries = sorted(
        (p for p in folder.iterdir() if p.is_file() and p.name != "index.md"), key=number_key
    )
    lines = [f"# {folder.name}", ""] + [f"* [{p.name}](./{p.name})" for p in entries]
    write_if_changed(folder / "index.md", "\n".join(lines) + "\n")


def reindex_mirror(kind: str) -> None:
    root = MIRROR[kind]
    if not root.exists():
        return
    lines = [f"# {root.name}", ""]
    for child in sorted(d for d in root.iterdir() if d.is_dir()):
        year, label = child.name.split("-", 1)
        noun = "Circulares" if label == "CIRCULAR" else "Resoluciones"
        lines.append(f"* [{child.name}]({child.name}/) - {noun} SII {year}")
    write_if_changed(root / "index.md", "\n".join(lines) + "\n")


def publish(years: list[int]) -> int:
    """Move converted sources from the local inbox into the versioned PDF mirror."""
    moved = 0
    for year in years:
        for kind in INDEX:
            inbox = RAW / f"{year}-{kind}"
            if not inbox.exists():
                continue
            doc_dir = MD[kind] / f"{year}-{kind}"
            done = numbers(p.name for p in doc_dir.glob("*.md") if p.name != "index.md")
            target = MIRROR[kind] / f"{year}-{kind}"
            for source in sorted(inbox.iterdir()):
                if not source.is_file() or source.suffix == ".part":
                    continue
                match = NUMBER_RE.search(source.name)
                if not match or int(match.group(1)) not in done:
                    continue
                target.mkdir(parents=True, exist_ok=True)
                destination = target / source.name
                destination.unlink(missing_ok=True)
                shutil.move(str(source), str(destination))
                moved += 1
            if target.exists():
                reindex_files(target)
    for kind in INDEX:
        reindex_mirror(kind)
    print(f"\npublished {moved}")
    return 0


def download(session: requests.Session, url: str, dest: Path, attempts: int = 3) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    for attempt in range(1, attempts + 1):
        try:
            with session.get(url, stream=True, timeout=60) as response:
                response.raise_for_status()
                with part.open("wb") as handle:
                    for chunk in response.iter_content(1 << 16):
                        handle.write(chunk)
            size = part.stat().st_size
            if size < 1024:
                raise ValueError(f"only {size} bytes")
            if dest.suffix.lower() == ".pdf":
                with part.open("rb") as handle:
                    if handle.read(5) != b"%PDF-":
                        raise ValueError("response is not a PDF")
            part.replace(dest)
            return
        except Exception as exc:
            part.unlink(missing_ok=True)
            if attempt == attempts:
                raise RuntimeError(f"{dest.name}: {exc}") from exc
            time.sleep(2 * attempt)


def report(rows: list[tuple], missing: dict[str, dict[str, str]], list_missing: bool) -> int:
    print(f"{'year':<6}{'type':<13}{'sii':>5}{'raw':>5}{'md':>5}{'missing':>9}")
    total = 0
    for year, kind, expected, raw, md, absent in rows:
        print(f"{year:<6}{kind:<13}{expected:>5}{raw:>5}{md:>5}{absent:>9}")
        total += absent
    print(f"{'total':<19}{'':>5}{'':>5}{'':>5}{total:>9}")
    if list_missing:
        for year, kind, expected, raw, md, absent in rows:
            if absent:
                print(f"\n{year}-{kind}")
                for name in missing[kind + str(year)]:
                    print(f"  {name}")
    return 1 if total else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--download", action="store_true", help="fetch missing files")
    parser.add_argument("--check", action="store_true", help="report only (default)")
    parser.add_argument("--pending", action="store_true", help="list documents with a PDF but no .md")
    parser.add_argument("--unpack", action="store_true", help="extract the circular from .zip archives")
    parser.add_argument("--publish", action="store_true", help="move converted sources to the PDF mirror")
    parser.add_argument("--vigencia", action="store_true", help="rebuild the supersession map")
    parser.add_argument("--list-missing", action="store_true", help="name every missing file")
    parser.add_argument("--years", type=int, nargs="+", help=f"default {FIRST_YEAR}..current")
    args = parser.parse_args()

    years = args.years or list(range(FIRST_YEAR, date.today().year + 1))
    if args.vigencia:
        import backfill_metadata

        return backfill_metadata.rebuild()
    if args.pending:
        return pending(years)
    if args.unpack:
        return unpack(years)
    if args.publish:
        return publish(years)

    session = requests.Session()
    session.headers.update(HEADERS)

    rows: list[tuple] = []
    missing: dict[str, dict[str, str]] = {}
    failures = 0

    for year in years:
        for kind in INDEX:
            try:
                links = index_links(session, kind, year)
            except requests.HTTPError as exc:
                print(f"{year} {kind}: no index ({exc.response.status_code})", file=sys.stderr)
                continue
            except requests.RequestException as exc:
                print(f"{year} {kind}: {exc}", file=sys.stderr)
                continue

            folder = RAW / f"{year}-{kind}"
            absent = {
                name: url for name, url in links.items() if not has_source(kind, year, name)
            }
            missing[kind + str(year)] = absent

            if args.download and absent:
                label = f"{year}-{kind}"
                for done, (name, url) in enumerate(absent.items(), 1):
                    print(f"[{label}] {done}/{len(absent)} {name}", flush=True)
                    try:
                        download(session, url, folder / name)
                    except RuntimeError as exc:
                        failures += 1
                        print(f"  FAILED {exc}", file=sys.stderr)
                    time.sleep(0.5)

            still = [name for name in absent if not has_source(kind, year, name)]
            rows.append(
                (
                    year,
                    kind,
                    len(links),
                    len(links) - len(still),
                    already_processed(kind, year),
                    len(still),
                )
            )

    print()
    code = report(rows, missing, args.list_missing and not args.download)
    return 1 if failures or code else 0


if __name__ == "__main__":
    sys.exit(main())
