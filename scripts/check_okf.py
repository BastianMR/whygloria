#!/usr/bin/env python3
"""Validate (and repair) OKF frontmatter in this repository.

Checks every markdown file for a valid YAML frontmatter block, a non-empty
`type`, no UTF-8 BOM, and no leftover broken `resource` links. Pass `--fix` to
rewrite concept frontmatter safely (quoted YAML, no BOM) from the document body.

Usage:
    python scripts/check_okf.py          # report problems
    python scripts/check_okf.py --fix    # repair in place
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FOLDER_RE = re.compile(r"^(\d{4})-(CIRCULAR|RESOLUCION)$")
FM_RE = re.compile(r"^(\ufeff)?---\r?\n(.*?)\r?\n---\r?\n?(.*)$", re.DOTALL)
TITLE_RE = re.compile(
    r"(?:CIRCULAR|RESOLUCI[OÓ]N)[^\d\n]{0,20}?N[°º]\s*(\d+)", re.IGNORECASE
)


def clean_description(text: str) -> str:
    for raw in text.splitlines():
        line = raw.strip().lstrip("#|*-> ").strip().replace("**", "").strip()
        if len(line) >= 20:
            return (line[:157] + "...") if len(line) > 160 else line
    return "SII public tax document."


def extract_title(body: str, doc_type: str, year: str, fallback: str) -> str:
    label = "Circular" if "Circular" in doc_type else "Resolución"
    # The filename suffix carries the document number; prefer it over body text,
    # which often cites other resolutions before its own number.
    from_name = re.search(r"(?:circu|reso)(\d+)", fallback, re.IGNORECASE)
    if from_name:
        return f"{label} N° {int(from_name.group(1))} ({year})"
    match = TITLE_RE.search(body)
    if match:
        return f"{label} N° {int(match.group(1))} ({year})"
    return fallback


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


def concept_meta(path: Path, body: str) -> dict:
    folder = path.parent.name
    match = FOLDER_RE.match(folder)
    if not match:
        return {}
    year, kind = match.groups()
    doc_type = "SII Circular" if kind == "CIRCULAR" else "SII Resolución"
    tag = "circular" if kind == "CIRCULAR" else "resolucion"
    fallback = path.name[:-3]
    return {
        "type": doc_type,
        "title": extract_title(body, doc_type, year, fallback),
        "description": clean_description(body),
        "tags": ["SII", year, tag],
    }


def render_frontmatter(meta: dict) -> str:
    def quote(value: str) -> str:
        return json.dumps(value, ensure_ascii=False)

    tags = ", ".join(meta["tags"])
    return (
        "---\n"
        f"type: {quote(meta['type'])}\n"
        f"title: {quote(meta['title'])}\n"
        f"description: {quote(meta['description'])}\n"
        f"tags: [{tags}]\n"
        "---\n\n"
    )


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


def validate(files: list[Path]) -> int:
    problems: list[str] = []
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
    for item in problems[:25]:
        print(item)
    if len(problems) > 25:
        print(f"... and {len(problems) - 25} more")
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