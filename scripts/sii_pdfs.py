#!/usr/bin/env python3
"""Mirror the PDFs linked from the SII yearly circulares / resoluciones indexes.

Check mode (default) prints, per year and document type, how many documents SII
publishes, how many are already downloaded, how many are already converted to
`.md`, and which files are missing. Exits 1 when anything is missing, so it
doubles as the verification gate before and after a download.

Download mode fetches only the missing files. Each one is written to a `.part`
file and renamed only after the bytes look complete, so an interrupted run never
leaves a truncated file that later looks done.

Oficios (2019 onward) ride the same flow with a different index: their yearly page
is a shell that posts to an API, and the file arrives from a blob endpoint, so the
listing is built from JSON instead of anchors. They are identified by materia,
number and publication date, because the number alone repeats.

Oficios before 2019 are the other half of the same family: SII published no PDF,
only an HTML page plus a Word copy of the same text. Their listing is three static
pages per year, each document is a `.htm`, and the HTML is the only publication of
the text, so it is published into `SRC_OFICIOS/` instead of `PDF_OFICIOS/`.

*Suplementos Tributarios* are the odd member: SII shipped them inside the
circulares `.zip`, next to the circular, and they have no number of their own.
Those archives were unpacked, verified byte for byte and removed, so their
members now live in `SIN_PROCESAR/SUPLEMENTOS/<year>-CIRCULAR/`. Their identity is
`circu<N>_suplemento`, naming the circular they belong to without colliding with
it.

*Formularios* are the fourth family and are indexed by *año tributario*, not by
calendar year: one page per AT lists every declaración jurada with its layout and
its instructions, and SII re-roots the document paths between ATs, so the URL is
read from the page and never built from the number. A DJ is therefore two
documents under one number, `dj<N>` (the layout) and `dj<N>_instrucciones`, and
both carry their own `source_url` plus the `source_at` they belong to.

Downloads land in the gitignored `SIN_PROCESAR/` inbox. `--publish` moves the
already converted ones into the versioned `PDF_<TYPE>/` mirror, or into
`SRC_OFICIOS/` for the HTML branch.

Usage:
    python scripts/sii_pdfs.py --check
    python scripts/sii_pdfs.py --check --list-missing
    python scripts/sii_pdfs.py --list
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
from urllib.parse import unquote, urlencode, urljoin, urlsplit

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "SIN_PROCESAR"
SUPLEMENTOS = RAW / "SUPLEMENTOS"
MD = {
    "CIRCULAR": ROOT / "MD_CIRCULARES",
    "RESOLUCION": ROOT / "MD_RESOLUCIONES",
    "OFICIO": ROOT / "MD_OFICIOS",
    "FORMULARIO": ROOT / "MD_FORMULARIOS",
}
MIRROR = {
    "CIRCULAR": ROOT / "PDF_CIRCULARES",
    "RESOLUCION": ROOT / "PDF_RESOLUCIONES",
    "OFICIO": ROOT / "PDF_OFICIOS",
    "FORMULARIO": ROOT / "PDF_FORMULARIOS",
}
# The pre-2019 oficios publish no PDF, so their provenance cannot live in a `PDF_`
# folder: SII served an HTML page plus a Word twin of the same text. The page is
# the only publication of the text, so it is the source and is kept here.
SRC_OFICIOS = ROOT / "SRC_OFICIOS"
# Manifest written next to a published source: what it was fetched from and when.
SOURCE_RECORD_SUFFIX = ".source.txt"
BASE = "https://www.sii.cl/normativa_legislacion"
INDEX = {
    "CIRCULAR": BASE + "/circulares/{year}/indcir{year}.htm",
    "RESOLUCION": BASE + "/resoluciones/{year}/res_ind{year}.htm",
}
PREFIX = {
    "CIRCULAR": "circu",
    "RESOLUCION": "reso",
    "OFICIO": "oficio",
}
NOUN = {
    "CIRCULAR": "Circulares",
    "RESOLUCION": "Resoluciones",
    "OFICIO": "Oficios",
    "FORMULARIO": "Formularios",
}
KINDS = tuple(MD)
CIRCULAR_MEMBER_RE = re.compile(r"^(?:circu|cir_|circular|reso)", re.IGNORECASE)
FIRST_YEAR = 2013
LINK_RE = re.compile(r"""href=["']([^"']+\.(?:pdf|zip))["']""", re.IGNORECASE)
NUMBER_RE = re.compile(r"(?:circu|reso)\w*?(\d+)", re.IGNORECASE)
# A *Suplemento Tributario* travels inside the circular `.zip` and has no number of
# its own, so it is named after the circular that carried it. The `_suplemento`
# suffix is what keeps it apart from `circu<N>`: the key every command compares
# must name one document, never two.
SUPLEMENTO_KEY_RE = re.compile(r"(?:^|_)circu(\d+)_suplemento$", re.IGNORECASE)

# Formularios are a fourth family with a fifth index shape: one page per *año
# tributario* that lists every declaración jurada of that year, its layout and its
# instructions. The page id carries the AT in its slug, but the document paths do
# not survive a year change (AT2025 served `/declaraciones_juradas/suplemento/2025/`,
# AT2026 serves `/ayudas/ayudas_por_servicios/renta/2026/`), so the page is parsed
# and the URL is never built from the number.
DJ_INDEX = (
    "https://www.sii.cl/ayudas/ayudas_por_servicios/"
    "2120-formularios_y_plazos_{at}-2171.html"
)
DJ_LINK_RE = re.compile(
    r"""href=["']([^"']*?(layout_f|instrucciones_dj)(\d+)\.pdf)["']""", re.IGNORECASE
)
# The DJ slice starts at AT2026: earlier ATs published a different tree, and asking
# for one would be inventing a page this corpus has never seen.
FORMULARIO_FIRST_AT = 2026
# One DJ is two documents under one number: the layout and its instructions. The
# suffix is what keeps them apart, exactly like `circu<N>_suplemento`.
DJ_KEY_RE = re.compile(r"(?:^|_)formulario-dj(\d+)(-instrucciones)?$", re.IGNORECASE)

# Oficios do not follow the yearly-index shape. The page is a shell that posts to
# an API, the "download" is a GET to a blob rather than a link to a `.pdf`, and a
# number is not unique: it repeats inside a materia (a second publication of the
# same oficio) and across materias. Identity is (materia, number, published date).
OFICIO_API = "https://www3.sii.cl/getPublicacionesCTByMateria"
OFICIO_BLOB = "https://www4.sii.cl/gabineteAdmInternet/descargaArchivo"
OFICIO_MATERIAS = {"renta": "RENTA", "iva": "IVA", "otros": "OTROS"}
OFICIO_FIRST_YEAR = 2019
# One identity for both branches. The date is optional because it is derived from
# the document header, not from the listing, so the HTML branch cannot carry it in
# the filename before the document is fetched: there, (materia, number) is enough.
OFICIO_KEY_RE = re.compile(
    r"(?:^|_)oficio-(renta|iva|otros)-(\d+)(?:-(\d{4}-\d{2}-\d{2}))?$", re.IGNORECASE
)
HEADERS = {
    # Without a normal browser UA the SII front end answers 403 to requests.
    "User-Agent": "Mozilla/5.0 (compatible; WhyGloria/1.0)",
}

# The indexes mix absolute and relative hrefs, and a few documents are shipped
# as .zip instead of .pdf (e.g. circulares 2013).
def index_links(session: requests.Session, kind: str, year: int) -> dict[str, str]:
    if kind == "FORMULARIO":
        return formulario_links(session, year)
    if kind == "OFICIO" and oficio_branch(year) == "html":
        return oficio_html_links(oficio_html_records(session, year))
    if kind == "OFICIO":
        return oficio_links(session, year)
    url = INDEX[kind].format(year=year)
    response = session.get(url, timeout=30)
    response.raise_for_status()
    links: dict[str, str] = {}
    for href in LINK_RE.findall(response.text):
        full = urljoin(url, href)
        links[unquote(Path(urlsplit(full).path).name)] = full
    return dict(sorted(links.items()))


def publishes(kind: str, year: int) -> bool:
    """Whether a family publishes anything in that year at all.

    A formulario is indexed by *año tributario*, not by calendar year, and the DJ
    slice starts at AT2026, so asking SII for an earlier formulario year would be a
    fabricated URL instead of a listing.
    """
    return kind != "FORMULARIO" or year >= FORMULARIO_FIRST_AT


def formulario_source_name(number: str | int, instructions: bool = False) -> str:
    """`formulario-dj<N>.pdf`, plus `-instrucciones` for the instructions."""
    return f"formulario-dj{int(number)}" + ("-instrucciones" if instructions else "") + ".pdf"


def formulario_links(session: requests.Session, at: int) -> dict[str, str]:
    """The declaraciones juradas of one *año tributario*, layout and instructions.

    The page lists each DJ twice: `layout_f<N>.pdf` under LAYOUT FORM. N° and
    `instrucciones_dj<N>.pdf` under INSTRUCCIONES, with the certificate layouts and
    the exempt resolutions in their own columns. Only the two DJ documents are
    mirrored here; a certificate layout belongs to the certificate, not to the
    declaración jurada.
    """
    url = DJ_INDEX.format(at=at)
    response = session.get(url, timeout=60)
    response.raise_for_status()
    # The page is UTF-8 with a BOM, and the BOM would end up inside the first href.
    page = response.content.decode("utf-8-sig", "replace")
    links: dict[str, str] = {}
    for href, kind, number in DJ_LINK_RE.findall(page):
        name = formulario_source_name(number, kind.lower() == "instrucciones_dj")
        links[name] = urljoin(url, href)
    return dict(sorted(links.items()))


def formulario_key(name: str) -> str:
    """`dj<N>` for a layout, `dj<N>_instrucciones` for its instructions."""
    match = DJ_KEY_RE.search(Path(name).stem)
    if not match:
        return ""
    number, instructions = match.groups()
    return f"dj{number}" + ("_instrucciones" if instructions else "")



def oficio_records(session: requests.Session, year: int) -> dict[str, dict]:
    """The oficio register for one year, keyed by published file name.

    The yearly page carries no links: it posts to an API. SII cross-lists one
    oficio under several materias with the same published name and identical
    bytes, so the first materia keeps it. A repeat inside one materia is a
    different blob and is kept, with the `pubKey` suffix in the name.
    """
    records: dict[str, dict] = {}
    seen_blobs: set[str] = set()
    for materia, key in OFICIO_MATERIAS.items():
        response = session.post(
            OFICIO_API, json={"key": key, "year": str(year)}, timeout=60
        )
        response.raise_for_status()
        for record in response.json():
            name = oficio_name(materia, record)
            # One document per materia, number and published date. The register
            # re-lists the same oficio under a second `pubKey`, sometimes with the
            # same blob and sometimes re-uploaded, so the name is the identity.
            if name in records:
                continue
            # SII also cross-lists one oficio under several materias, pointing at
            # the same blob: the first materia keeps it.
            blob = str(record.get("idBlobArchPublica") or "")
            if blob and blob in seen_blobs:
                continue
            if blob:
                seen_blobs.add(blob)
            records[name] = record
    return records


def oficio_links(session: requests.Session, year: int) -> dict[str, str]:
    return dict(
        sorted(
            (name, oficio_url(record))
            for name, record in oficio_records(session, year).items()
        )
    )


def oficio_name(materia: str, record: dict) -> str:
    """`oficio-<materia>-<number>-<published date>`, the identity the corpus needs."""
    raw = str(record.get("pubNumOficio") or "").strip()
    number = str(int(raw)) if raw.isdigit() else raw
    match = re.match(r"(\d{2})/(\d{2})/(\d{4})", str(record.get("pubFechaPubli") or ""))
    if match:
        day, month, year = match.groups()
    else:
        day, month, year = "00", "00", str(record.get("pubYear") or "")
    return f"oficio-{materia}-{number}-{year}-{month}-{day}.pdf"


def oficio_url(record: dict) -> str:
    params = {
        "nombreDocumento": record["nombreArchPublica"],
        "extension": record["extensionArchPublica"],
        "acc": "download",
        "id": record["idBlobArchPublica"],
        "mediaType": record["mTypeArchPublica"],
    }
    return OFICIO_BLOB + "?" + urlencode(params)


MATERIA_SLUGS = {
    "renta": "ley_impuesto_renta",
    "iva": "ley_impuesto_ventas",
    "otros": "otras_normas",
}

# The pre-2019 half of the family: one static index page per materia and year, one
# `ja<N>.htm` per document, and a `ja<N>.doc` twin holding the same text.
OFICIO_HTML_INDEX = (
    BASE + "/jurisprudencia_administrativa/{slug}/{year}/{slug}_jadm{year}.htm"
)
OFICIO_HTML_LINK_RE = re.compile(
    r"""href=["']([^"']*?ja(\d+)\.(htm|doc))["']""", re.IGNORECASE
)


def oficio_branch(year: int) -> str:
    """`html` up to 2018, `pdf` from 2019: the two halves of one family."""
    return "html" if year < OFICIO_FIRST_YEAR else "pdf"


def oficio_source_name(materia: str, number: str | int) -> str:
    """`oficio-<materia>-<N>.html`, the source name the HTML branch uses."""
    return f"oficio-{materia}-{int(number)}.html"


def oficio_html_pairs(page: str) -> dict[str, dict[str, str]]:
    """`{number: {"htm": href, "doc": href}}` out of one materia index page."""
    pairs: dict[str, dict[str, str]] = {}
    for href, number, extension in OFICIO_HTML_LINK_RE.findall(page):
        pairs.setdefault(number, {})[extension.lower()] = href
    return pairs


def oficio_html_records(session: requests.Session, year: int) -> dict[str, dict]:
    """The three materia index pages of one year, keyed by source name.

    Every `.htm` has a `.doc` twin carrying the same text. The twin is recorded in
    the manifest and never downloaded: the concept is generated from the HTML.
    """
    records: dict[str, dict] = {}
    for materia, slug in MATERIA_SLUGS.items():
        url = OFICIO_HTML_INDEX.format(slug=slug, year=year)
        response = session.get(url, timeout=30)
        response.raise_for_status()
        # These pages exist with and without a BOM, and are UTF-8 either way.
        page = response.content.decode("utf-8-sig", "replace")
        for number, links in oficio_html_pairs(page).items():
            if "htm" not in links:
                continue
            name = oficio_source_name(materia, number)
            # A name repeats when the page lists the same oficio twice: one file.
            if name in records:
                continue
            records[name] = {
                "materia": materia,
                "number": int(number),
                "url": urljoin(url, links["htm"]),
                "doc_url": urljoin(url, links["doc"]) if links.get("doc") else "",
            }
    return dict(sorted(records.items()))


def oficio_html_links(records: dict[str, dict]) -> dict[str, str]:
    """The `.html` downloads out of the listing records."""
    return {name: record["url"] for name, record in records.items()}


def source_record_path(source: Path) -> Path:
    """Where the manifest of a source lives: next to it, `<stem>.source.txt`.

    Same convention as the unpacked `.zip` archives, so a reader that finds a
    source also finds what it was fetched from and when.
    """
    return source.with_name(source.stem + SOURCE_RECORD_SUFFIX)


def write_source_record(source: Path, record: dict) -> Path:
    """Record where a downloaded source came from, so the concept can say why.

    A formulario records the *año tributario* it belongs to instead of a materia:
    the same DJ number is a different document every AT, and the number alone does
    not say which year the layout serves.
    """
    path = source_record_path(source)
    lines = [f"source: {source.name}", f"url: {record['url']}"]
    if record.get("at"):
        lines.append(f"at: {record['at']}")
    else:
        lines += [
            f"doc_url: {record.get('doc_url', '')}",
            f"materia: {record.get('materia', '')}",
        ]
    lines.append(f"retrieved: {date.today().isoformat()}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return path


def read_source_record(source: Path) -> dict[str, str]:
    """The manifest of a source, or an empty mapping when it has none."""
    path = source_record_path(source)
    if not path.exists():
        return {}
    record: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition(":")
        if key.strip() and value.strip():
            record[key.strip()] = value.strip()
    return record


def suplemento_number(name: str) -> int | None:
    """The circular number a *Suplemento Tributario* belongs to, or None."""
    match = SUPLEMENTO_KEY_RE.search(Path(name).stem)
    return int(match.group(1)) if match else None


def suplemento_key(name: str) -> str:
    """`circu<N>_suplemento`, or the empty string when the name is not one."""
    number = suplemento_number(name)
    return f"circu{number}_suplemento" if number is not None else ""


def suplemento_sources(folder: Path) -> list[Path]:
    """The staged *Suplemento* sources inside a `SIN_PROCESAR/SUPLEMENTOS/` folder.

    An unpacked archive keeps the member names SII wrote, and those carry no
    identity; only the canonical `circu<N>_suplemento.<ext>` name does, so only that
    name is a document of the corpus.
    """
    return sorted(p for p in folder.iterdir() if p.is_file() and suplemento_key(p.name))


def document_url(kind: str, year: int, name: str) -> str:
    """The SII page a source file came from, for the attribution every concept carries.

    Circulares and resoluciones have a stable per-document URL. An oficio is served
    from a blob endpoint that is not citable, so the materia index that lists it is
    what the corpus records.
    """
    number = suplemento_number(name)
    if kind == "CIRCULAR" and number is not None:
        # A *Suplemento* has no page of its own: it is one member of the circular's
        # `.zip`, so that archive is the page it came from.
        return f"{BASE}/circulares/{year}/circu{number}.zip"
    if kind == "FORMULARIO":
        # The declaración jurada index moves every AT, so the URL cannot be derived
        # from (year, name): it is the one the manifest recorded at download time.
        for folder in source_dirs(kind, year):
            url = read_source_record(folder / name).get("url")
            if url:
                return url
        return ""
    if kind == "OFICIO":
        match = OFICIO_KEY_RE.search(Path(name).stem)
        if not match:
            return ""
        slug = MATERIA_SLUGS[match.group(1).lower()]
        if oficio_branch(year) == "html":
            # Pre-2019 the document itself is the page, so it is citable.
            number = int(match.group(2))
            return f"{BASE}/jurisprudencia_administrativa/{slug}/{year}/ja{number}.htm"
        return (
            f"{BASE}/jurisprudencia_administrativa/{slug}/{year}/{slug}_jadm{year}.htm"
        )
    folder = "circulares" if kind == "CIRCULAR" else "resoluciones"
    return f"{BASE}/{folder}/{year}/{name}"


def already_processed(kind: str, year: int) -> int:
    folder = MD[kind] / f"{year}-{kind}"
    return len([p for p in folder.glob("*.md") if p.name != "index.md"])


def inbox_dirs(kind: str, year: int) -> list[Path]:
    """Where an unpublished source can sit.

    The download inbox, plus `SIN_PROCESAR/SUPLEMENTOS/` for a circulares year: the
    *Suplemento Tributario* was published inside the circular `.zip`, so it never
    arrives through the yearly index and its archive is no longer there.
    """
    folders = [RAW / f"{year}-{kind}"]
    if kind == "CIRCULAR":
        folders.append(SUPLEMENTOS / f"{year}-{kind}")
    return folders


def source_dirs(kind: str, year: int) -> list[Path]:
    """A source can sit in the local inbox or in the published mirror.

    The pre-2019 oficios publish HTML, so their published source is `SRC_OFICIOS/`
    and not `PDF_OFICIOS/`.
    """
    if kind == "OFICIO" and oficio_branch(year) == "html":
        return inbox_dirs(kind, year) + [SRC_OFICIOS / f"{year}-{kind}"]
    return inbox_dirs(kind, year) + [MIRROR[kind] / f"{year}-{kind}"]


def mirror_dir(kind: str, year: int) -> Path:
    """Where a published source belongs: `PDF_` for a PDF, `SRC_` for HTML."""
    if kind == "OFICIO" and oficio_branch(year) == "html":
        return SRC_OFICIOS / f"{year}-{kind}"
    return MIRROR[kind] / f"{year}-{kind}"


def source_keys(kind: str, year: int) -> set:
    found: set = set()
    for folder in source_dirs(kind, year):
        if folder.exists():
            found |= keys(p.name for p in folder.iterdir())
    return found


def has_source(kind: str, year: int, name: str) -> bool:
    if any((folder / name).exists() for folder in source_dirs(kind, year)):
        return True
    # A `.zip` that was unpacked, verified byte for byte and removed keeps its
    # manifest, because its contents are still in the corpus.
    if name.lower().endswith(".zip") and extracted_archive(kind, year, name).exists():
        return True
    # A link SII itself publishes but does not serve is not a gap in this mirror.
    # The `.broken.txt` records the URL, the status and the date it was observed.
    return broken_link(kind, year, name).exists()


def broken_link(kind: str, year: int, name: str) -> Path:
    return mirror_dir(kind, year) / (Path(name).stem + ".broken.txt")


def extracted_archive(kind: str, year: int, name: str) -> Path:
    """Manifest of an archive that was unpacked, verified and removed.

    It sits next to the mirror because it is provenance: the inbox is not
    versioned, and losing the manifest would make `--check` report a missing
    source that is actually in the corpus.
    """
    return MIRROR[kind] / f"{year}-{kind}" / (Path(name).stem + ".source.txt")


def keys(names) -> set:
    """Document identity, because source and concept filenames differ.

    A circular or a resolucion is unique by number, so the number is the key. An
    oficio is not: the same number can name two documents in one year, so the key
    carries materia and, from 2019 on, publication date too. The pre-2019 branch has
    no date in the listing, so its key leaves that part empty. A *Suplemento
    Tributario* shares the circular's number and is a different document, so its key
    is the circular's plus the suffix that says which of the two it is. A
    declaración jurada also ships two documents under one number, so `dj<N>` is the
    layout and `dj<N>_instrucciones` the instructions.
    """
    found: set = set()
    for name in names:
        suplemento = suplemento_key(name)
        if suplemento:
            found.add(suplemento)
            continue
        formulario = formulario_key(name)
        if formulario:
            found.add(formulario)
            continue
        # A concept is prefixed with `<year>_OFICIO_`, a source is not.
        match = OFICIO_KEY_RE.search(Path(name).stem)
        if match:
            materia, number, published = match.groups()
            found.add((materia.lower(), int(number), published or ""))
            continue
        match = NUMBER_RE.search(name)
        if match:
            found.add(int(match.group(1)))
    return found


def format_keys(items: set, limit: int = 15) -> str:
    if not items:
        return ""
    if all(isinstance(item, int) for item in items):
        return summarize(sorted(items), limit)
    if all(isinstance(item, tuple) for item in items):
        oficios = sorted(items, key=lambda key: (key[2], key[0], key[1]))
        shown = [
            "-".join(str(part) for part in key if str(part)) for key in oficios[:limit]
        ]
        return " ".join(shown) + (" ..." if len(oficios) > limit else "")
    names = sorted(str(item) for item in items)
    return " ".join(names[:limit]) + (" ..." if len(names) > limit else "")


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
    """Member name from an archive written before the UTF-8 flag existed.

    `zipfile` already decodes an unflagged name as cp437, which is correct for
    archives written on Windows. A few SII archives instead stored UTF-8 bytes in
    that field, so the cp437 reading is mojibake and only then is the name worth
    re-decoding. Falling back to latin-1 used to corrupt correct names
    (`AÑO` became `A¥O`, `N°18` became `Nø18`).
    """
    try:
        return info.filename.encode("cp437").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return info.filename


def unpack(years: list[int]) -> int:
    """Extract the circular out of the .zip archives SII ships instead of a PDF.

    Each archive bundles the circular with a *Suplemento Tributario*. Only the
    circular is extracted here, under the plain `<circu|reso><N>.pdf` name the rest
    of the mirror uses; the *Suplemento* was unpacked separately into
    `SIN_PROCESAR/SUPLEMENTOS/<year>-CIRCULAR/`, because it is its own document
    with its own concept. The nine archives that shipped one are gone, so this
    stays for whatever SII publishes as a `.zip` next.
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


def pending(years: list[int], kinds: tuple = KINDS) -> int:
    total = 0
    for year in years:
        for kind in kinds:
            if not publishes(kind, year):
                continue
            doc_dir = MD[kind] / f"{year}-{kind}"
            done = keys(p.name for p in doc_dir.glob("*.md") if p.name != "index.md")
            expected = source_keys(kind, year)
            if not expected and not done:
                continue
            absent = expected - done
            extra = done - expected
            total += len(absent)
            label = "html" if kind == "OFICIO" and oficio_branch(year) == "html" else "pdf"
            print(
                f"{year}-{kind:<12} {label}={len(expected):>4} "
                f"md={len(done):>4} todo={len(absent):>4}"
            )
            if absent:
                print(f"  {format_keys(absent)}")
            if extra:
                print(f"  md without pdf: {format_keys(extra)}")
    print(f"\npending conversion: {total}")
    return 1 if total else 0


def number_key(path: Path) -> tuple[int, str]:
    formulario = formulario_key(path.name)
    if formulario:
        number = re.search(r"\d+", formulario)
        return (
            int(number.group()) if number else 10**6,
            "1" if formulario.endswith("_instrucciones") else "0",
        )
    match = OFICIO_KEY_RE.search(path.stem)
    if match:
        return (int(match.group(2)), f"{match.group(3)}-{match.group(1)}")
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
        lines.append(f"* [{child.name}]({child.name}/) - {NOUN.get(label, label)} SII {year}")
    write_if_changed(root / "index.md", "\n".join(lines) + "\n")


def publish(years: list[int], kinds: tuple = KINDS) -> int:
    """Move converted sources from the local inbox into the versioned PDF mirror."""
    moved = 0
    for year in years:
        for kind in kinds:
            if not publishes(kind, year):
                continue
            inboxes = [folder for folder in inbox_dirs(kind, year) if folder.exists()]
            if not inboxes:
                continue
            doc_dir = MD[kind] / f"{year}-{kind}"
            done = keys(p.name for p in doc_dir.glob("*.md") if p.name != "index.md")
            target = mirror_dir(kind, year)
            for inbox in inboxes:
                for source in sorted(inbox.iterdir()):
                    if not source.is_file() or source.suffix == ".part":
                        continue
                    # A manifest travels with the document it describes, not alone.
                    if source.name.endswith(SOURCE_RECORD_SUFFIX):
                        continue
                    found = keys([source.name])
                    if not found or not found <= done:
                        continue
                    target.mkdir(parents=True, exist_ok=True)
                    for path in (source, source_record_path(source)):
                        if not path.exists():
                            continue
                        destination = target / path.name
                        destination.unlink(missing_ok=True)
                        shutil.move(str(path), str(destination))
                    moved += 1
            if target.exists():
                reindex_files(target)
    for kind in kinds:
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


def listing(years: list[int], kinds: tuple = KINDS) -> int:
    """Print what each index yields, one `name<TAB>url` line per document.

    The provenance of a listing is the page it came from, so this prints the URL
    that will be fetched rather than reconstructing it. For a declaración jurada the
    count is reported as layout plus instructions, because one number is two
    documents there and summing them would hide which half is missing.
    """
    session = requests.Session()
    session.headers.update(HEADERS)
    total = 0
    for year in years:
        for kind in kinds:
            if not publishes(kind, year):
                continue
            try:
                links = index_links(session, kind, year)
            except requests.HTTPError as exc:
                print(f"{year} {kind}: no index ({exc.response.status_code})", file=sys.stderr)
                continue
            except requests.RequestException as exc:
                print(f"{year} {kind}: {exc}", file=sys.stderr)
                continue
            total += len(links)
            summary = f"{year}-{kind}: total={len(links)}"
            if kind == "FORMULARIO":
                instructions = [n for n in links if formulario_key(n).endswith("_instrucciones")]
                summary = (
                    f"{year}-{kind}: layouts={len(links) - len(instructions)}"
                    f" instrucciones={len(instructions)} total={len(links)}"
                )
            print(summary)
            for name, url in links.items():
                print(f"  {name}\t{url}")
    print(f"\nlisted {total}")
    return 0


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
    parser.add_argument("--list", action="store_true", help="print every document of every index with its URL")
    parser.add_argument("--pending", action="store_true", help="list documents with a source but no .md")
    parser.add_argument("--unpack", action="store_true", help="extract the circular from .zip archives")
    parser.add_argument(
        "--publish",
        action="store_true",
        help="move converted sources to the PDF mirror (SRC_OFICIOS for the HTML oficios)",
    )
    parser.add_argument("--vigencia", action="store_true", help="rebuild the supersession map")
    parser.add_argument("--list-missing", action="store_true", help="name every missing file")
    parser.add_argument("--years", type=int, nargs="+", help=f"default {FIRST_YEAR}..current")
    parser.add_argument(
        "--kind",
        nargs="+",
        choices=KINDS,
        help="only these families (default: all of them)",
    )
    args = parser.parse_args()

    years = args.years or list(range(FIRST_YEAR, date.today().year + 1))
    kinds = tuple(args.kind) if args.kind else KINDS
    if args.vigencia:
        import backfill_metadata

        return backfill_metadata.rebuild()
    if args.pending:
        return pending(years, kinds)
    if args.list:
        return listing(years, kinds)
    if args.unpack:
        return unpack(years)
    if args.publish:
        return publish(years, kinds)

    session = requests.Session()
    session.headers.update(HEADERS)

    rows: list[tuple] = []
    missing: dict[str, dict[str, str]] = {}
    failures = 0

    for year in years:
        for kind in kinds:
            if not publishes(kind, year):
                continue
            records: dict[str, dict] = {}
            try:
                if kind == "OFICIO" and oficio_branch(year) == "html":
                    # The same listing, kept whole: the `.doc` twin is recorded in
                    # the manifest but never downloaded.
                    records = oficio_html_records(session, year)
                    links = oficio_html_links(records)
                else:
                    links = index_links(session, kind, year)
                    if kind == "FORMULARIO":
                        # A formulario has to remember both the exact URL and the AT
                        # it belongs to: neither can be derived from the name later.
                        records = {
                            name: {"url": url, "at": str(year)}
                            for name, url in links.items()
                        }
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
                        if records:
                            write_source_record(folder / name, records[name])
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
