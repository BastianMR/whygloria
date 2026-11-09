#!/usr/bin/env python3
"""Rebuild concept frontmatter from the body, in place.

One-shot backfill: conversion already writes the metadata, so this exists only
for concepts produced before the fields existed. It reuses
`check_okf.concept_meta`, which reuses `metadata.extract_metadata`, so the
backfilled frontmatter is exactly what a re-conversion would write.

The PDFs are never touched and nothing is downloaded: the body is the input.

Usage:
    python scripts/backfill_metadata.py            # rewrite and report
    python scripts/backfill_metadata.py --dry-run  # report only
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import check_okf

FOLDERS = {"CIRCULAR": "MD_CIRCULARES", "RESOLUCION": "MD_RESOLUCIONES"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="report, do not write")
    args = parser.parse_args()

    total = changed = 0
    coverage = Counter()
    impuestos = Counter()
    unresolved = {"materia": [], "fecha": [], "ref_legal": []}

    for kind, folder in FOLDERS.items():
        for path in sorted((check_okf.ROOT / folder).rglob("*.md")):
            if path.name == "index.md":
                continue
            total += 1
            text = check_okf.read_md(path)
            _data, body, error = check_okf.split_frontmatter(text)
            if error:
                print(f"SKIP {path.relative_to(check_okf.ROOT)}: {error}")
                continue
            meta = check_okf.concept_meta(path, body)
            # Canonical join, same as the conversion path: one blank line after
            # the frontmatter, so a second run is a no-op.
            new = check_okf.render_frontmatter(meta) + body.lstrip("\n")
            if new != text:
                changed += 1
                if not args.dry_run:
                    check_okf.write_md(path, new)
            for key in ("materia", "fecha", "ref_legal"):
                if meta[key]:
                    coverage[key] += 1
                else:
                    unresolved[key].append(str(path.relative_to(check_okf.ROOT)))
            if meta["impuestos"]:
                coverage["impuestos"] += 1
            for value in meta["impuestos"]:
                impuestos[value] += 1
            if meta["formularios"]:
                coverage["formularios"] += 1
            if meta["regimen"] != ["no-aplica"]:
                coverage["regimen"] += 1
            if meta["exenta"]:
                coverage["exenta"] += 1

    print(f"concepts: {total}   rewritten: {changed}" + ("   (dry run)" if args.dry_run else ""))
    print("\ncoverage (documents with a value)")
    for key in ("materia", "fecha", "ref_legal", "impuestos", "formularios", "regimen", "exenta"):
        print(f"  {key:12} {coverage[key]:5}  missing {total - coverage[key]:5}")
    print("\nimpuestos (documents per value, one document can have several)")
    for value, count in impuestos.most_common():
        print(f"  {value:18} {count:5}")
    for key, paths in unresolved.items():
        print(f"\nunresolved {key}: {len(paths)}")
        for item in paths:
            print(f"  {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
