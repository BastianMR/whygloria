#!/usr/bin/env python3
"""Convert SII .docx documents to OKF concept markdown.

For every `<year>-<TYPE>/` folder, each `.docx` becomes a sibling `.md` with
OKF frontmatter (type, title, description, resource, tags). The original
`.docx` is kept as the `resource`. Folder `index.md` files are regenerated to
list the markdown concepts.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from markitdown import MarkItDown

ROOT = Path(__file__).resolve().parents[1]
FOLDER_RE = re.compile(r"^\d{4}-(CIRCULAR|RESOLUCION)$")


def extract_title(body: str, doc_type: str, year: str, fallback: str) -> str:
    match = re.search(r"(?:CIRCULAR|RESOLUCI[OÓ]N)[^\d\n]{0,20}?N[°º]\s*(\d+)", body, re.IGNORECASE)
    if match:
        label = "Circular" if "Circular" in doc_type else "Resolución"
        return f"{label} N° {int(match.group(1))} ({year})"
    return fallback


def clean_description(text: str) -> str:
    for raw in text.splitlines():
        line = raw.strip().lstrip("#|*-> ").strip()
        line = line.replace("**", "").strip()
        if len(line) >= 20:
            return (line[:157] + "...") if len(line) > 160 else line
    return "SII public tax document."


def convert_folder(folder: Path, converter: MarkItDown) -> int:
    doc_type = "SII Circular" if folder.name.endswith("CIRCULAR") else "SII Resolución"
    year = folder.name.split("-")[0]
    tag = "circular" if folder.name.endswith("CIRCULAR") else "resolucion"
    md_files = []
    for docx in sorted(folder.glob("*.docx")):
        name = docx.name[:-5] if docx.name.lower().endswith(".docx") else docx.name
        md = folder / (name if name.lower().endswith(".md") else f"{name}.md")
        try:
            text = converter.convert(str(docx)).text_content
        except Exception as exc:  # keep going, report at the end
            print(f"FAIL {docx}: {exc}", file=sys.stderr)
            continue
        body = text.strip()
        frontmatter = (
            "---\n"
            f"type: {doc_type}\n"
            f"title: {extract_title(body, doc_type, year, name)}\n"
            f"description: {clean_description(body)}\n"
            f"resource: ./{docx.name}\n"
            f"tags: [SII, {year}, {tag}]\n"
            "---\n\n"
        )
        md.write_text(frontmatter + body + "\n", encoding="utf-8")
        md_files.append(md)

    lines = [f"# {folder.name}", ""]
    for md in md_files:
        stem = md.name[:-3]
        lines.append(f"* [{stem}](./{md.name})")
    (folder / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(md_files)


def main() -> int:
    converter = MarkItDown()
    total = 0
    for folder in sorted(ROOT.iterdir()):
        if folder.is_dir() and FOLDER_RE.match(folder.name):
            count = convert_folder(folder, converter)
            total += count
            print(f"{folder.name}: {count}")
    print(f"total: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())