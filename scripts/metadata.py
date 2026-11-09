#!/usr/bin/env python3
"""Extract structured tax metadata from a concept body.

One function serves both paths: the conversion in `pdf_to_md.py` and the
backfill in `backfill_metadata.py`, so frontmatter and body cannot drift.

Every extractor is a pure function of the markdown body. Nothing here calls an
LLM and nothing reads the PDF: the body is already the docling conversion.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

VOCAB = json.loads((Path(__file__).with_name("tax_vocab.json")).read_text(encoding="utf-8"))

MONTHS = {
    name: index
    for index, name in enumerate(
        "enero febrero marzo abril mayo junio julio agosto septiembre octubre "
        "noviembre diciembre".split(),
        1,
    )
}
MONTHS["setiembre"] = 9
MONTH_ALT = "|".join(sorted(MONTHS, key=len, reverse=True))

MATERIA_RE = re.compile(r"MATERIA\.?\s*:\s*(.+?)(?:\s*\|\s*|\s*$)", re.I | re.M)
MAT_SHORT_RE = re.compile(r"^[#*\s]*MAT\.?\s*:\s*(.+?)\s*$", re.I | re.M)
BARE_MATERIA_RE = re.compile(r"^[#*\s]*MATERIA\.?\s*:?\s*$", re.I)
REF_LABEL_RE = re.compile(r"REF\.?\s*LEGAL|REFERENCIA", re.I)
FECHA_RE = re.compile(
    rf"(?:^|\|)\s*FECHA\s*[:,_]?\s*((?:\d{{1,2}}|{MONTH_ALT})[^\n]*)", re.I | re.M
)
SANTIAGO_RE = re.compile(rf"SANTIAGO,?\s*((?:\d{{1,2}}|{MONTH_ALT})[^\n]{{0,60}})", re.I)
SANTIAGO_NEXT_RE = re.compile(rf"SANTIAGO,?\s*\n[ \t]*((?:\d{{1,2}}|{MONTH_ALT})[^\n]{{0,60}})", re.I)
DATE_WORDS_RE = re.compile(
    rf"(\d{{1,2}})[°º]?\s*(?:(?:de|e)\s+)?({MONTH_ALT})\s*(?:de|del|,|\.|/|-)?\s*(\d{{4}})",
    re.I,
)
DATE_MONTH_FIRST_RE = re.compile(rf"({MONTH_ALT})\s+(\d{{1,2}})\s+de\s+(\d{{4}})", re.I)
DATE_HEADER_RE = re.compile(
    rf"\b(\d{{1,2}})\s+de\s+({MONTH_ALT})\s+de\s+(\d{{4}})\b", re.I
)
LOWERCASE_WORD_RE = re.compile(r"\s+[A-ZÁÉÍÓÚ][a-záéíóúñ]{3,}")
SENTENCE_END_RE = re.compile(r"\.\s+(?=[A-ZÁÉÍÓÚ])")
MEDIANTE_RE = re.compile(r",\s+(?:mediante|en virtud|por la cual|por las cuales)\b", re.I)
DATE_NUMERIC_RE = re.compile(r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})")
EXENTA_RE = re.compile(r"RESOLUCI[OÓ]N\s+(?:EXENTA|EX\.)", re.I)
F_RE = re.compile(r"\bF\s?[-]?\s?(\d{2,3})\b")
DJ_RE = re.compile(r"\bD\.?\s?J\.?\s?[-]?\s?(\d{3,4})\b", re.I)
REF_LEGAL_RE = re.compile(r"REF\.?\s*LEGAL\s*:\s*(.+?)(?:\s*\|\s*|\s*$)", re.I | re.M)
VISTOS_RE = re.compile(
    r"VISTOS\s*:?\s*(.+?)(?:\n\s*\n|\bCONSIDERANDO\b|\bRESUELVO\b)", re.I | re.S
)
CITATION_RE = re.compile(VOCAB["ref_legal"]["pattern"], re.I)

IMPUESTOS = [
    (name, [re.compile(pattern, re.I) for pattern in patterns])
    for name, patterns in VOCAB["impuestos"]["keywords"].items()
]
REGIMEN = [
    (name, [re.compile(pattern, re.I) for pattern in patterns])
    for name, patterns in VOCAB["regimen"]["patterns"].items()
]
FORM_PATTERN = re.compile(VOCAB["formularios"]["pattern"])
OBSERVED_F = set(VOCAB["formularios"]["observed_f"])


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("**", " ")).strip(" |*-\t")


def _normalize_date_text(text: str) -> str:
    """Undo docling's glued spacing: 'DEJULIO', '26DEDICIEMBREDE2022'."""
    text = re.sub(r"(?<=\d)(?=[a-záéíóúñ])", " ", text, flags=re.I)
    for month in MONTHS:
        text = re.sub(rf"(?i)\bde({month})", rf"de \1", text)
        text = re.sub(rf"(?i)({month})(?=\d{{4}})", r"\1 ", text)
    text = re.sub(r"(?i)(?<=[a-záéíóúñ])de(?=\d{4})", " de ", text)
    text = re.sub(r"(?<=[a-záéíóúñ])(?=\d)", " ", text, flags=re.I)
    return text


def _parse_date(text: str) -> str:
    text = _normalize_date_text(text)
    match = DATE_WORDS_RE.search(text)
    if match:
        day, month, year = match.groups()
        month_name = MONTHS.get(month.lower().rstrip("."))
        if month_name:
            return _iso(int(day), month_name, int(year))
    match = DATE_MONTH_FIRST_RE.search(text)
    if match:
        month, day, year = match.groups()
        month_name = MONTHS.get(month.lower())
        if month_name:
            return _iso(int(day), month_name, int(year))
    match = DATE_NUMERIC_RE.search(text)
    if match:
        day, month, year = (int(part) for part in match.groups())
        return _iso(day, month, year)
    return ""


def _iso(day: int, month: int, year: int) -> str:
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return ""


def _subject_line(body: str) -> str:
    """Older documents carry the subject as an unlabelled uppercase line."""
    for raw in body.splitlines()[:40]:
        value = _clean(raw)
        if len(value) < 25 or value.startswith("|"):
            continue
        upper = value.upper()
        if upper.startswith(
            (
                "SANTIAGO",
                "MATERIA",
                "MAT:",
                "VISTOS",
                "SISTEMA DE PUBLICACIONES",
                "DEPARTAMENTO",
                "SUBDIRECCIÓN",
                "SUBDIRECCION",
                "GABINETE",
                "SERVICIO DE IMPUESTOS",
                "OFICINA",
            )
        ):
            continue
        if raw.lstrip().startswith("#") and "IMPUESTOS INTERNOS" in upper:
            continue
        if ":" in value[:20]:
            continue
        letters = [char for char in value if char.isalpha()]
        if not letters:
            continue
        if sum(char.isupper() for char in letters) / len(letters) > 0.85 and (
            value.endswith(".") or len(value) >= 40
        ):
            return value
    return ""


def _trim_subject(value: str) -> str:
    """Drop prose that docling glued after an uppercase subject line.

    Some documents read 'Dejada sin efecto MATERIA: MODIFICA ... PECUNIARIAS
    Esta Dirección, en virtud ...'. The subject is the uppercase part.
    """
    letters = [char for char in value[:120] if char.isalpha()]
    if not letters or sum(char.isupper() for char in letters) / len(letters) < 0.85:
        return value[:300]
    match = LOWERCASE_WORD_RE.search(value, 20)
    if not match:
        return value[:300]
    return value[: match.start()].rstrip(" ,;-") + "."


def extract_materia(body: str) -> str:
    match = MATERIA_RE.search(body)
    if match:
        value = _clean(match.group(1))
        if len(value) >= 15:
            return _trim_subject(value)
        # Labelled but empty cell: the subject is the first cell of the next row.
        for line in body[match.end() :].splitlines():
            if not line.strip():
                continue
            if "|" in line:
                cell = _clean(line.split("|")[1])
                if len(cell) >= 15:
                    return _trim_subject(cell)
            break
    match = MAT_SHORT_RE.search(body)
    if match and len(_clean(match.group(1))) >= 15:
        return _trim_subject(_clean(match.group(1)))
    lines = body.splitlines()
    for index, line in enumerate(lines[:40]):
        if BARE_MATERIA_RE.match(line):
            for following in lines[index + 1 : index + 4]:
                value = _clean(following)
                if value and not value.startswith("|"):
                    return _trim_subject(value)
    for line in lines[:40]:
        if "|" in line and REF_LABEL_RE.search(line):
            for cell in line.split("|"):
                value = _clean(cell)
                if len(value) >= 15 and not REF_LABEL_RE.search(value):
                    return _trim_subject(value)
    return _subject_line(body)


def extract_fecha(body: str, year: str = "") -> str:
    head = "\n".join(body.splitlines()[:40])
    for pattern in (FECHA_RE, SANTIAGO_RE, SANTIAGO_NEXT_RE):
        for match in pattern.finditer(head):
            found = _parse_date(match.group(1))
            if not found:
                continue
            # A document lives in its publication year; anything further out is
            # a citation date that leaked in, not this document's signature.
            if year and not (int(year) - 1 <= int(found[:4]) <= int(year)):
                continue
            return found
    # Header cells often lose the FECHA label; the date is still there.
    for line in body.splitlines()[:12]:
        match = DATE_HEADER_RE.search(line)
        if match:
            day, month, year_name = match.groups()
            month_name = MONTHS.get(month.lower())
            if month_name and (not year or int(year) - 1 <= int(year_name) <= int(year)):
                return _iso(int(day), month_name, int(year_name))
    return ""


def extract_ref_legal(body: str) -> list[str]:
    match = REF_LEGAL_RE.search(body)
    if match:
        items = re.split(r";", match.group(1))
    else:
        match = VISTOS_RE.search(body)
        if not match:
            return []
        items = re.split(r";", match.group(1))
    citations = []
    for item in items:
        value = _clean(re.sub(r"^(?:y|e)\s+", "", item, flags=re.I)).strip(" ;,")
        value = re.sub(r"\s+(?:y|e)$", "", value, flags=re.I)
        value = SENTENCE_END_RE.split(value)[0]
        value = MEDIANTE_RE.split(value)[0].strip(" ;,")
        if len(value) < 6 or not CITATION_RE.search(value):
            continue
        value = value[:300]
        if value not in citations:
            citations.append(value)
    return citations[:10]


def extract_impuestos(body: str) -> list[str]:
    return [name for name, patterns in IMPUESTOS if patterns and any(p.search(body) for p in patterns)]


def extract_regimen(body: str) -> list[str]:
    found = [name for name, patterns in REGIMEN if any(p.search(body) for p in patterns)]
    return found or ["no-aplica"]


def extract_formularios(body: str) -> list[str]:
    forms = {f"F{number}" for number in F_RE.findall(body) if f"F{number}" in OBSERVED_F}
    forms |= {f"DJ{number}" for number in DJ_RE.findall(body)}
    return sorted(forms)


def extract_metadata(body: str, kind: str, year: str = "") -> dict:
    return {
        "materia": extract_materia(body),
        "ref_legal": extract_ref_legal(body),
        "impuestos": extract_impuestos(body),
        "formularios": extract_formularios(body),
        "regimen": extract_regimen(body),
        "exenta": kind == "RESOLUCION" and bool(EXENTA_RE.search(body)),
        "fecha": extract_fecha(body, year),
    }
