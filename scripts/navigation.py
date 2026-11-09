#!/usr/bin/env python3
"""Generate navigation indexes over the whole corpus.

A pure projection of the concept frontmatter: every entry is a link plus the
`status_vigencia` already stored in the file. Nothing here restates a fact, and
a document that lacks a dimension is listed under `unclassified` instead of
being dropped.

The per-folder `index.md` files are untouched; this is a second layer above the
tree, rebuilt from scratch on every run.

Usage:
    python scripts/navigation.py
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import check_okf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "navigation"
MD = {"MD_CIRCULARES": "circular", "MD_RESOLUCIONES": "resolucion"}
DIMENSIONS = (
    ("by-tax.md", "By tax", "impuestos", "taxes the document names"),
    ("by-form.md", "By form", "formularios", "SII forms and sworn statements the document names"),
    ("by-regime.md", "By regime", "regimen", "income tax regime the document names"),
    ("by-materia.md", "By materia", "materia", "keywords taken from the MATERIA line"),
)
STOPWORDS = set(
    """para desde sobre entre cuando donde porque segun según conforme respecto
    materia circular circulares resolucion resoluciones resolución señala indica
    establece fijan fija modifica complementa instrucciones imparte deja efecto
    del las los una unos unas que con por sus este esta estos estas""".split()
)
MAX_KEYWORDS = 3
MAX_SECTIONS = 40


def concepts() -> list[dict]:
    found = []
    for folder in MD:
        for path in sorted((ROOT / folder).rglob("*.md")):
            if path.name == "index.md":
                continue
            text = check_okf.read_md(path)
            data, _body, error = check_okf.split_frontmatter(text)
            if error or not isinstance(data, dict):
                continue
            number = re.search(r"(?:circu|reso)(\d+)", path.stem, re.I)
            found.append(
                {
                    "path": path.relative_to(ROOT).as_posix(),
                    "label": path.stem,
                    "number": int(number.group(1)) if number else 0,
                    "status": data.get("status_vigencia") or "desconocido",
                    "data": data,
                }
            )
    return found


def keywords(text: str) -> list[str]:
    words = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{4,}", text or "")
    picked = []
    for word in words:
        key = word.lower()
        if key in STOPWORDS or key in picked:
            continue
        picked.append(key)
        if len(picked) == MAX_KEYWORDS:
            break
    return picked


def entry(concept: dict) -> str:
    return f"* [{concept['label']}](../{concept['path']}) - {concept['status']}"


def frontmatter(title: str, description: str) -> str:
    return (
        "---\n"
        f'type: "Reference"\n'
        f'title: "{title}"\n'
        f'description: "{description}"\n'
        "tags: []\n"
        "---\n\n"
    )


def write_dimension(filename: str, title: str, field: str, description: str, items: list[dict]) -> dict:
    groups: dict[str, list[dict]] = {}
    unclassified = []
    for concept in items:
        value = concept["data"].get(field)
        values = value if isinstance(value, list) else ([value] if value else [])
        labels = [str(item) for item in values if str(item).strip()]
        if not labels:
            unclassified.append(concept)
            continue
        for label in labels:
            groups.setdefault(label, []).append(concept)

    lines = [
        frontmatter(title, f"Generated index of concepts grouped by the {description}.").rstrip("\n"),
        "",
        f"# {title}",
        "",
        "Generated from concept frontmatter by `python scripts/navigation.py`. Do not edit.",
        "",
    ]
    for label, members in sorted(groups.items(), key=lambda item: (-len(item[1]), item[0])):
        lines.append(f"## {label} ({len(members)})")
        lines.extend(entry(concept) for concept in members)
        lines.append("")
    lines.append(f"## unclassified ({len(unclassified)})")
    if unclassified:
        lines.append("No value for this dimension in the frontmatter. Kept visible on purpose.")
    lines.extend(entry(concept) for concept in unclassified)
    (OUT / filename).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return {"groups": len(groups), "unclassified": len(unclassified)}


def write_materia(items: list[dict]) -> dict:
    classified: dict[str, list[dict]] = {}
    unclassified = []
    for concept in items:
        picked = keywords(str(concept["data"].get("materia") or ""))
        if not picked:
            unclassified.append(concept)
            continue
        for word in picked:
            classified.setdefault(word, []).append(concept)

    ranked = sorted(classified.items(), key=lambda item: (-len(item[1]), item[0]))
    heads = [item for item in ranked if len(item[1]) >= 3][:MAX_SECTIONS]
    covered = {concept["path"] for _word, members in heads for concept in members}
    tail = [concept for concept in items if concept["path"] not in covered and keywords(str(concept["data"].get("materia") or ""))]

    lines = [
        frontmatter("By materia", "Generated index of concepts by keyword taken from the MATERIA line.").rstrip("\n"),
        "",
        "# By materia",
        "",
        "Generated from concept frontmatter by `python scripts/navigation.py`. Do not edit.",
        f"At most {MAX_KEYWORDS} keywords per document; the {MAX_SECTIONS} largest keywords get a section.",
        "",
    ]
    for word, members in heads:
        lines.append(f"## {word} ({len(members)})")
        lines.extend(entry(concept) for concept in members)
        lines.append("")
    lines.append(f"## other keywords ({len(tail)})")
    if tail:
        lines.append("Documents whose keywords did not make the section cut. Each line keeps its keywords.")
    for concept in tail:
        picked = ", ".join(keywords(str(concept["data"].get("materia") or "")))
        lines.append(f"{entry(concept)} — {picked}")
    lines.append("")
    lines.append(f"## unclassified ({len(unclassified)})")
    lines.extend(entry(concept) for concept in unclassified)
    (OUT / "by-materia.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return {"groups": len(heads) + 1, "unclassified": len(unclassified), "tail": len(tail)}


def write_hub(items: list[dict], sizes: dict) -> None:
    lines = [
        "# Navigation",
        "",
        "Generated from concept frontmatter by `python scripts/navigation.py`. Do not edit.",
        "The per-folder `index.md` files stay as they are; this is a second layer over the tree.",
        "",
        f"Corpus: {len(items)} concepts.",
        "",
        "| Dimension | Groups | Unclassified |",
        "| --- | --- | --- |",
    ]
    for filename, title, _field, _description in DIMENSIONS:
        size = sizes[filename]
        lines.append(f"| [{title}]({filename}) | {size['groups']} | {size['unclassified']} |")
    lines += [
        "",
        "`GLOSSARY.md`, one level up, is the only hand-maintained file in this layer.",
        "",
    ]
    (OUT / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--report", action="store_true", help="print the index sizes")
    args = parser.parse_args()

    OUT.mkdir(exist_ok=True)
    items = concepts()
    sizes = {}
    for filename, title, field, description in DIMENSIONS:
        if field == "materia":
            sizes[filename] = write_materia(items)
        else:
            sizes[filename] = write_dimension(filename, title, field, description, items)
    write_hub(items, sizes)
    print(f"navigation/: {len(items)} concepts")
    for filename, size in sizes.items():
        print(f"  {filename:15} {size}")
    if args.report:
        print(json.dumps(sizes, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
