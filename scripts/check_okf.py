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
import json
import re
import sys
from datetime import date
from pathlib import Path

import yaml

import metadata
import vigencia

ROOT = Path(__file__).resolve().parents[1]
FOLDER_RE = re.compile(r"^(\d{4})-(CIRCULAR|RESOLUCION)$")
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
    label = "Circular" if "Circular" in doc_type else "Resolución"
    stem = path.stem
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


def concept_meta(path: Path, body: str, from_pdf: bool = False) -> dict:
    folder = path.parent.name
    match = FOLDER_RE.match(folder)
    if not match:
        return {}
    year, kind = match.groups()
    doc_type = "SII Circular" if kind == "CIRCULAR" else "SII Resolución"
    tag = "circular" if kind == "CIRCULAR" else "resolucion"
    meta = {
        "type": doc_type,
        "title": extract_title(body, doc_type, year, path),
        "description": clean_description(body),
        "tags": ["SII", year, tag],
    }
    meta.update(metadata.extract_metadata(body, kind, year))
    if from_pdf and (not meta["materia"] or not meta["fecha"] or not meta["exenta"]):
        pdf = metadata.mirror_pdf(path, ROOT)
        if pdf:
            number = re.search(r"(\d+)", path.stem.split("_")[-1])
            fallback = metadata.extract_from_pdf(
                pdf, year, int(number.group(1)) if number else None
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


def metadata_problems(relative, data: dict) -> list[str]:
    problems = []
    materia = data.get("materia")
    if materia is not None and not isinstance(materia, str):
        problems.append(f"{relative}: 'materia' is not a string")
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
            problems.extend(metadata_problems(relative, data))
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
    args = parser.parse_args()

    files = sorted(ROOT.rglob("*.md"))
    files = [p for p in files if ".git" not in p.parts]

    if not args.fix:
        return validate(files)

    for path in files:
        fix_file(path)
    print(f"fixed {len(files)} files")
    return validate(files)


if __name__ == "__main__":
    sys.exit(main())