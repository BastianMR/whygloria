#!/usr/bin/env python3
"""Validate (and repair) OKF frontmatter in this repository.

Checks every markdown file for a valid YAML frontmatter block, a non-empty
`type`, no UTF-8 BOM, and no leftover broken `resource` links. Concept files
are also checked for the structured tax fields (materia, fecha, exenta,
impuestos, formularios, regimen, ref_legal). Pass `--fix` to rewrite concept
frontmatter safely (quoted YAML, no BOM) from the document body.

Usage:
    python scripts/check_okf.py          # report problems
    python scripts/check_okf.py --fix    # repair in place
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from datetime import date
from pathlib import Path

import yaml

import metadata
import sii_pdfs
import vigencia

ROOT = Path(__file__).resolve().parents[1]
FOLDER_RE = re.compile(r"^(\d{4})-(CIRCULAR|RESOLUCION|OFICIO|FORMULARIO)$")
DOC_TYPES = {
    "CIRCULAR": ("SII Circular", "circular"),
    "RESOLUCION": ("SII Resolución", "resolucion"),
    "OFICIO": ("SII Oficio", "oficio"),
    "FORMULARIO": ("SII Formulario", "formulario"),
}
# A declaración jurada and its instructions are the same OKF type because they are
# the same publication pair; the title is what says which of the two a file is.
FORMULARIO_TITLE_RE = re.compile(
    r"^(?:Instrucciones )?Declaraci[oó]n Jurada N[°º] \d+ \(AT\d{4}\)$"
)
# A *Suplemento Tributario* is not a circular, even though it is published inside a
# circular's `.zip` and shares its number: it is its own document type, so it reuses
# neither `SII Circular` nor `SII Resolución`.
SUPLEMENTO_TYPE = "Suplemento Tributario"
SUPLEMENTO_TITLE_RE = re.compile(r"^Suplemento Tributario N[°º] \d+ \(\d{4}\)$")
MATERIA_LABELS = {"renta": "Renta", "iva": "IVA", "otros": "Otros"}
FM_RE = re.compile(r"^(\ufeff)?---\r?\n(.*?)\r?\n---\r?\n?(.*)$", re.DOTALL)
TITLE_RE = re.compile(
    r"(?:CIRCULAR|RESOLUCI[OÓ]N)[^\d\n]{0,20}?N[°º]\s*(\d+)", re.IGNORECASE
)
IMPUESTOS = set(metadata.VOCAB["impuestos"]["values"])
REGIMEN = set(metadata.VOCAB["regimen"]["values"])
FORM_PATTERN = re.compile(metadata.VOCAB["formularios"]["pattern"])
CITATION_RE = re.compile(metadata.VOCAB["ref_legal"]["pattern"], re.IGNORECASE)
RELATION_TYPES = set(vigencia.VARIANTS.values())


def clean_description(text: str) -> str:
    for raw in text.splitlines():
        line = raw.strip().lstrip("#|*-> ").strip().replace("**", "").strip()
        if len(line) >= 20:
            return (line[:157] + "...") if len(line) > 160 else line
    return "SII public tax document."


def extract_title(body: str, doc_type: str, year: str, path: Path) -> str:
    # A *Suplemento Tributario* has no number of its own: it is named after the
    # circular that carried it, and dated with the *año tributario* it serves, which
    # is the year a reader looks for and is read from the document itself.
    suplemento = sii_pdfs.suplemento_number(path.name)
    if suplemento is not None:
        anio = metadata.extract_anio_tributario(body) or year
        return f"{doc_type} N° {suplemento} ({anio})"
    # A formulario is dated with the *año tributario* of its folder, because that is
    # the year the document serves and the year its identity belongs to. The layout
    # and its instructions share the DJ number, so the title says which one it is.
    formulario = sii_pdfs.formulario_key(path.name)
    if formulario:
        number = re.search(r"\d+", formulario)
        instructions = formulario.endswith("_instrucciones")
        label = "Instrucciones Declaración Jurada" if instructions else "Declaración Jurada"
        return f"{label} N° {int(number.group()) if number else ''} (AT{year})"
    label = "Circular" if "Circular" in doc_type else "Resolución"
    stem = path.stem
    # Oficios are not unique by number, so the title carries the materia: the
    # same number can name one oficio in renta and another in IVA. The pre-2019
    # branch has no publication date in the filename, so the year stands in.
    oficio = re.search(
        r"oficio-(renta|iva|otros)-(\d+)(?:-(\d{4}-\d{2}-\d{2}))?", stem, re.IGNORECASE
    )
    if oficio:
        materia, number, published = oficio.groups()
        return (
            f"Oficio {MATERIA_LABELS[materia.lower()]} N° {int(number)}"
            f" ({published or year})"
        )
    # The filename suffix carries the document number; prefer it over body text,
    # which often cites other resolutions before its own number.
    from_name = re.search(r"(?:circu|reso)(\d+)", stem, re.IGNORECASE)
    if from_name:
        raw = from_name.group(1)
        number = str(int(raw))
        # Two files can carry the same number: one canonical stem, one padded or
        # amended. Keep the title unique instead of renaming a concept.
        prefix = "circu" if "Circular" in doc_type else "reso"
        canonical = path.parent / f"{year}_{path.parent.name.split('-')[1]}_{prefix}{number}.md"
        if raw != number and canonical.exists():
            number = raw
        suffix = " (afecta)" if "_afecta" in stem.lower() else ""
        return f"{label} N° {number} ({year}){suffix}"
    match = TITLE_RE.search(body)
    if match:
        return f"{label} N° {int(match.group(1))} ({year})"
    return stem


def read_md(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def split_frontmatter(text: str) -> tuple[dict | None, str, str | None]:
    """Return (data, body, error)."""
    match = FM_RE.match(text)
    if not match:
        return None, text, "no YAML frontmatter block"
    raw = match.group(2)
    body = match.group(3)
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        return None, body, f"invalid YAML: {exc}"
    if not isinstance(data, dict):
        return None, body, "frontmatter is not a mapping"
    return data, body, None


def missing_metadata(meta: dict, kind: str) -> bool:
    """Fields worth re-reading from the source PDF. `exenta` is resolution-only."""
    missing = not meta["materia"] or not meta["fecha"]
    if kind != "OFICIO":
        missing = missing or not meta["exenta"]
    return missing


def expected_type(path: Path, kind: str) -> str:
    """The OKF type the folder's family gives a concept.

    The folder alone is not enough: a *Suplemento Tributario* shares the circular's
    folder because it belongs to that circular, and the name is what says which of
    the two documents a file is.
    """
    if sii_pdfs.suplemento_number(path.name) is not None:
        return SUPLEMENTO_TYPE
    return DOC_TYPES[kind][0]


def concept_meta(
    path: Path, body: str, from_pdf: bool = False, oficio_legal: str = ""
) -> dict:
    folder = path.parent.name
    match = FOLDER_RE.match(folder)
    if not match:
        return {}
    year, kind = match.groups()
    doc_type, tag = DOC_TYPES[kind]
    if sii_pdfs.suplemento_number(path.name) is not None:
        # A *Suplemento Tributario* is neither typed nor tagged as the circular it
        # belongs to, so the folder can be shared while the document is not.
        doc_type, tag = SUPLEMENTO_TYPE, "suplemento-tributario"
    meta = {
        "type": doc_type,
        "title": extract_title(body, doc_type, year, path),
        "description": clean_description(body),
        "tags": ["SII", year, tag],
    }
    number = None
    if kind == "OFICIO":
        # The pre-2019 branch has no date in the name, so the trailing separator is
        # optional: the number is what the signature is matched against.
        parsed = re.search(r"oficio-(?:renta|iva|otros)-(\d+)", path.stem, re.IGNORECASE)
        number = int(parsed.group(1)) if parsed else None
    meta.update(metadata.extract_metadata(body, kind, year, number))
    source = metadata.mirror_pdf(path, ROOT)
    if source is not None:
        # Attribution the SII terms require: every concept names the page it came from.
        meta["source_url"] = sii_pdfs.document_url(kind, int(year), source.name)
    if kind == "FORMULARIO":
        # A formulario is indexed by *año tributario*, and the same DJ number means a
        # different layout every AT. Neither fact can be read back out of the name, so
        # both come from the manifest written when the source was downloaded.
        from_manifest = sii_pdfs.read_source_record(source) if source is not None else {}
        meta["source_url"] = from_manifest.get("url") or meta.get("source_url", "")
        meta["source_at"] = from_manifest.get("at") or year
    if source is not None and source.suffix.lower() == ".html":
        # The pre-2019 oficios publish HTML plus a Word twin of the same text and
        # no PDF at all, so the concept records the exact page, its format, the
        # download date and the twin. The manifest written at download time is
        # what knows them; nothing here is guessed from the body.
        from_manifest = sii_pdfs.read_source_record(source)
        meta["source_url"] = from_manifest.get("url") or meta["source_url"]
        meta["source_format"] = "html"
        meta["retrieved"] = from_manifest.get("retrieved", "")
        meta["doc_url"] = from_manifest.get("doc_url", "")
        listed = re.search(r"oficio-(renta|iva|otros)-", path.stem, re.IGNORECASE)
        meta["materia"] = from_manifest.get("materia") or (
            listed.group(1).lower() if listed else ""
        )
    if kind == "OFICIO" and oficio_legal:
        # An oficio has no MATERIA cell. SII already publishes the equivalent as
        # `pubLegal` in the listing API, so the subject comes from the source
        # record instead of being scraped out of a wrapped header.
        meta["materia"] = oficio_legal
    if from_pdf and missing_metadata(meta, kind):
        pdf = metadata.mirror_pdf(path, ROOT)
        if pdf:
            number = re.search(r"(\d+)", path.stem.split("_")[-1])
            fallback = metadata.extract_from_pdf(
                pdf, year, int(number.group(1)) if number else None, kind
            )
            for key, value in fallback.items():
                if value and not meta[key]:
                    meta[key] = value
    meta.setdefault("status_vigencia", "desconocido")
    meta.setdefault("replaced_by", [])
    return meta


def yaml_list(values: list) -> str:
    def item(value):
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return json.dumps(str(value), ensure_ascii=False)

    return "[" + ", ".join(item(value) for value in values) + "]"


def render_frontmatter(meta: dict) -> str:
    def quote(value: str) -> str:
        return json.dumps(value, ensure_ascii=False)

    tags = ", ".join(meta["tags"])
    lines = [
        "---",
        f"type: {quote(meta['type'])}",
        f"title: {quote(meta['title'])}",
        f"description: {quote(meta['description'])}",
        f"tags: [{tags}]",
    ]
    if meta.get("source_url"):
        lines.append(f"source_url: {quote(meta['source_url'])}")
    if meta.get("source_at"):
        # The *año tributario* the document serves, when it is not the folder year.
        lines.append(f"source_at: {quote(meta['source_at'])}")
    if meta.get("source_format"):
        lines.append(f"source_format: {quote(meta['source_format'])}")
    if meta.get("retrieved"):
        lines.append(f"retrieved: {quote(meta['retrieved'])}")
    if meta.get("doc_url"):
        lines.append(f"doc_url: {quote(meta['doc_url'])}")
    if "materia" in meta:
        lines += [
            f"materia: {quote(meta['materia'])}",
            f"fecha: {quote(meta['fecha'])}",
            f"exenta: {'true' if meta['exenta'] else 'false'}",
            f"impuestos: {yaml_list(meta['impuestos'])}",
            f"formularios: {yaml_list(meta['formularios'])}",
            f"regimen: {yaml_list(meta['regimen'])}",
            f"ref_legal: {yaml_list(meta['ref_legal'])}",
            f"status_vigencia: {quote(meta.get('status_vigencia', 'desconocido'))}",
            f"replaced_by: {yaml_list(meta.get('replaced_by') or [])}",
            "relaciones: " + yaml_list(meta.get("relaciones") or []),
        ]
    return "\n".join(lines) + "\n---\n\n"


def write_md(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")


def fix_file(path: Path) -> None:
    text = read_md(path)
    data, body, error = split_frontmatter(text)
    if path.name == "index.md":
        # Reserved file: no frontmatter, just drop the BOM.
        write_md(path, text.lstrip("\ufeff"))
        return
    meta = concept_meta(path, body)
    # Status is derived from the whole corpus; --fix must never reset it.
    for key in ("status_vigencia", "replaced_by"):
        if key in data:
            meta[key] = data[key]
    # Values recovered from the source PDF must survive a body-only repair.
    for key in ("materia", "fecha"):
        if not meta[key] and data.get(key):
            meta[key] = data[key]
    if not meta["exenta"] and data.get("exenta") is True and not metadata.extract_exenta(body):
        meta["exenta"] = True
    if not meta:
        # Root-level concept (e.g. README.md): preserve existing keys.
        if data is None:
            print(f"SKIP (cannot parse) {path}")
            return
        meta = {
            "type": data.get("type", "Reference"),
            "title": data.get("title", path.stem),
            "description": data.get("description", "Reference document."),
            "tags": data.get("tags", []),
        }
    write_md(path, render_frontmatter(meta) + body.lstrip("\ufeff"))


def metadata_gaps(relative, data: dict) -> list[str]:
    """Fields the source itself does not carry (an unlabelled subject, a lost date)."""
    gaps = []
    if not str(data.get("materia") or "").strip():
        gaps.append(f"{relative}: no 'materia' in the source header")
    if not str(data.get("fecha") or "").strip():
        gaps.append(f"{relative}: no 'fecha' in the source header")
    return gaps


def metadata_problems(relative, data: dict, path: Path | None = None) -> list[str]:
    problems = []
    if path is not None and FOLDER_RE.match(path.parent.name):
        expected = expected_type(path, FOLDER_RE.match(path.parent.name).group(2))
        if data.get("type") != expected:
            problems.append(
                f"{relative}: type {data.get('type')!r} is not {expected!r} for this file"
            )
        if expected == SUPLEMENTO_TYPE and not SUPLEMENTO_TITLE_RE.match(
            str(data.get("title") or "")
        ):
            problems.append(
                f"{relative}: title is not 'Suplemento Tributario N° <N> (<año>)': "
                f"{data.get('title')!r}"
            )
        if expected == DOC_TYPES["FORMULARIO"][0] and not FORMULARIO_TITLE_RE.match(
            str(data.get("title") or "")
        ):
            problems.append(
                f"{relative}: title is not 'Declaración Jurada N° <N> (AT<año>)' or "
                f"'Instrucciones Declaración Jurada N° <N> (AT<año>)': "
                f"{data.get('title')!r}"
            )
    source_at = data.get("source_at")
    if source_at is not None:
        if not isinstance(source_at, str) or not re.fullmatch(r"\d{4}", source_at):
            problems.append(f"{relative}: 'source_at' is not a 4-digit año tributario: {source_at!r}")
        elif path is not None and FOLDER_RE.match(path.parent.name):
            # A declaración jurada is filed by the año tributario, so the concept's
            # AT must be the one the folder is named after.
            folder_at = FOLDER_RE.match(path.parent.name).group(1)
            if source_at != folder_at:
                problems.append(
                    f"{relative}: 'source_at' {source_at!r} is not the folder year "
                    f"{folder_at!r}"
                )
    materia = data.get("materia")
    if materia is not None and not isinstance(materia, str):
        problems.append(f"{relative}: 'materia' is not a string")
    source_format = data.get("source_format")
    if source_format is not None and source_format != "html":
        problems.append(f"{relative}: unknown source_format {source_format!r}")
    retrieved = data.get("retrieved")
    if retrieved:
        if not isinstance(retrieved, str):
            problems.append(f"{relative}: 'retrieved' is not a string")
        else:
            try:
                date.fromisoformat(retrieved)
            except ValueError:
                problems.append(f"{relative}: 'retrieved' is not ISO 8601: {retrieved!r}")
    doc_url = data.get("doc_url")
    if doc_url is not None and not isinstance(doc_url, str):
        problems.append(f"{relative}: 'doc_url' is not a string")
    fecha = data.get("fecha")
    if fecha:
        if not isinstance(fecha, str):
            problems.append(f"{relative}: 'fecha' is not a string")
        else:
            try:
                date.fromisoformat(fecha)
            except ValueError:
                problems.append(f"{relative}: 'fecha' is not ISO 8601: {fecha!r}")
    if not isinstance(data.get("exenta"), bool):
        problems.append(f"{relative}: 'exenta' is not a boolean")
    for key in ("impuestos", "formularios", "regimen", "ref_legal"):
        if not isinstance(data.get(key), list):
            problems.append(f"{relative}: '{key}' is not a list")
    for value in data.get("impuestos") or []:
        if value not in IMPUESTOS:
            problems.append(f"{relative}: unknown impuesto {value!r}")
    for value in data.get("regimen") or []:
        if value not in REGIMEN:
            problems.append(f"{relative}: unknown regimen {value!r}")
    if not data.get("regimen"):
        problems.append(f"{relative}: empty 'regimen', expected at least no-aplica")
    for value in data.get("formularios") or []:
        if not FORM_PATTERN.match(str(value)):
            problems.append(f"{relative}: malformed formulario {value!r}")
    for value in data.get("ref_legal") or []:
        if not isinstance(value, str) or not CITATION_RE.search(value):
            problems.append(f"{relative}: ref_legal item is not a citation: {value!r}")
    if data.get("status_vigencia") not in vigencia.STATUSES:
        problems.append(f"{relative}: unknown status_vigencia {data.get('status_vigencia')!r}")
    if not isinstance(data.get("replaced_by"), list):
        problems.append(f"{relative}: 'replaced_by' is not a list")
    relaciones = data.get("relaciones")
    if not isinstance(relaciones, list):
        problems.append(f"{relative}: 'relaciones' is not a list")
    for relation in relaciones or []:
        if not isinstance(relation, dict):
            problems.append(f"{relative}: relacion is not a mapping")
            continue
        if relation.get("type") not in RELATION_TYPES:
            problems.append(f"{relative}: unknown relation type {relation.get('type')!r}")
        if relation.get("target_type") not in ("circular", "resolucion"):
            problems.append(f"{relative}: bad target_type {relation.get('target_type')!r}")
        if not isinstance(relation.get("target_number"), int):
            problems.append(f"{relative}: bad target_number {relation.get('target_number')!r}")
        year = relation.get("target_year")
        if year is not None and not isinstance(year, int):
            problems.append(f"{relative}: bad target_year {year!r}")
    return problems


def gap_report(files: list[Path]) -> int:
    """Every metadata gap, with the reason the source does not carry the value.

    The corpus rule is that a missing `materia` or `fecha` is a source gap, never
    an invented value. This writes the list a human needs in order to close them:
    one line per document, the field, the reason, and what page 1 actually says.
    """
    try:
        import pymupdf
    except ImportError:
        pymupdf = None

    rows: list[tuple[str, str, str, str]] = []
    for path in files:
        if path.name == "index.md" or not FOLDER_RE.match(path.parent.name):
            continue
        data, _body, error = split_frontmatter(read_md(path))
        if error:
            continue
        missing = [field for field in ("materia", "fecha") if not str(data.get(field) or "").strip()]
        if not missing:
            continue
        pdf = metadata.mirror_pdf(path, ROOT)
        if pdf is None:
            reason, sample = "no source PDF in the mirror", ""
        elif pymupdf is None:
            reason, sample = "pymupdf unavailable, not verifiable", ""
        else:
            try:
                with pymupdf.open(pdf) as document:
                    text = re.sub(r"\s+", " ", document[0].get_text()).strip()
            except Exception:
                text = ""
            if len(text) < 40:
                reason, sample = "the page has no text layer (image only)", text
            elif re.search(r"FECHA\s*:?\s*(MATERIA|REFERENCIA|SISTEMA|TABLA|$)", text[:700], re.I):
                reason = "the original prints the FECHA label with no value"
                sample = text[:160]
            elif "OFICIO" in path.parent.name or "_OFICIO_" in path.name:
                reason = "the oficio signature is not readable on page 1"
                sample = text[:160]
            else:
                reason = "page 1 carries neither the label nor the signature"
                sample = text[:160]
        for field in missing:
            rows.append((str(path.relative_to(ROOT)), field, reason, sample))

    rows.sort()
    lines = [
        "---",
        'type: "Reference"',
        'title: "Metadata gaps and why they exist"',
        'description: "Every concept whose source carries no materia or fecha, with the reason per document."',
        "tags: []",
        "---",
        "",
        "# Metadata gaps",
        "",
        "Generated by `python scripts/check_okf.py --gaps-report`. A gap is never a bug:",
        "the source does not carry the value. This is the list a human works through.",
        "",
        f"{len(rows)} gaps.",
        "",
        "| Concept | Field | Reason | Page 1 says |",
        "| --- | --- | --- | --- |",
    ]
    for path, field, reason, sample in rows:
        cell = sample.replace("|", "\\|")[:140]
        lines.append(f"| `{path}` | `{field}` | {reason} | {cell} |")
    (ROOT / "METADATA_GAPS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for reason, count in sorted(
        collections.Counter(row[2] for row in rows).items(), key=lambda item: -item[1]
    ):
        print(f"  {count:>4}  {reason}")
    print(f"wrote METADATA_GAPS.md with {len(rows)} gaps")
    return 0


def validate(files: list[Path]) -> int:
    problems: list[str] = []
    gaps: list[str] = []
    for path in files:
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            problems.append(f"{path.relative_to(ROOT)}: UTF-8 BOM at start")
        if path.name == "index.md":
            continue
        text = read_md(path)
        data, _body, error = split_frontmatter(text)
        if error:
            problems.append(f"{path.relative_to(ROOT)}: {error}")
            continue
        if not data.get("type"):
            problems.append(f"{path.relative_to(ROOT)}: missing or empty 'type'")
        for key in ("title", "description"):
            if not isinstance(data.get(key), str):
                problems.append(f"{path.relative_to(ROOT)}: '{key}' is not a string")
        if raw.find(b"resource:") != -1 and b".docx" in raw:
            problems.append(f"{path.relative_to(ROOT)}: broken .docx resource link")
        if FOLDER_RE.match(path.parent.name):
            relative = path.relative_to(ROOT)
            problems.extend(metadata_problems(relative, data, path))
            for gap in metadata_gaps(relative, data):
                gaps.append(gap)
    for item in problems[:25]:
        print(item)
    if len(problems) > 25:
        print(f"... and {len(problems) - 25} more")
    if gaps:
        materia = sum(1 for gap in gaps if "'materia'" in gap)
        fecha = len(gaps) - materia
        print(f"metadata gaps (not errors): materia {materia}, fecha {fecha}")
        for item in gaps:
            print(f"  {item}")
    print(f"checked {len(files)} files, {len(problems)} problems")
    return 1 if problems else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fix", action="store_true", help="repair in place")
    parser.add_argument(
        "--gaps-report", action="store_true", help="write METADATA_GAPS.md"
    )
    args = parser.parse_args()

    files = sorted(ROOT.rglob("*.md"))
    # Dot directories are tool state (`.git`, `.atl`), never corpus content.
    files = [
        p
        for p in files
        if not any(part.startswith(".") for part in p.relative_to(ROOT).parts)
    ]

    if args.gaps_report:
        return gap_report(files)
    if not args.fix:
        return validate(files)

    for path in files:
        fix_file(path)
    print(f"fixed {len(files)} files")
    return validate(files)


if __name__ == "__main__":
    sys.exit(main())