#!/usr/bin/env python3
"""Rebuild concept frontmatter from the body, in place.

One-shot backfill: conversion already writes the metadata, so this exists only
for concepts produced before the fields existed. It reuses
`check_okf.concept_meta`, which reuses `metadata.extract_metadata`, so the
backfilled frontmatter is exactly what a re-conversion would write.

Two passes: first every concept is extracted, then the supersession graph is
built across all of them, then `status_vigencia` and `replaced_by` are written
back. Those two fields are corpus-wide facts, so they cannot be computed one
document at a time.

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
import vigencia

FOLDERS = {"CIRCULAR": "MD_CIRCULARES", "RESOLUCION": "MD_RESOLUCIONES"}


def rebuild(dry_run: bool = False, from_pdf: bool = True) -> int:
    extracted: dict[Path, tuple[str, dict]] = {}
    coverage = Counter()
    impuestos = Counter()
    unresolved = {"materia": [], "fecha": [], "ref_legal": []}

    for kind, folder in FOLDERS.items():
        for path in sorted((check_okf.ROOT / folder).rglob("*.md")):
            if path.name == "index.md":
                continue
            text = check_okf.read_md(path)
            _data, body, error = check_okf.split_frontmatter(text)
            if error:
                print(f"SKIP {path.relative_to(check_okf.ROOT)}: {error}")
                continue
            meta = check_okf.concept_meta(path, body, from_pdf=from_pdf)
            extracted[path] = (body, meta)
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
            if meta["relaciones"]:
                coverage["relaciones"] += 1

    graph = vigencia.build({path: meta for path, (_body, meta) in extracted.items()})
    changed = 0
    for path, (body, meta) in extracted.items():
        meta["status_vigencia"] = graph["status"][path]
        meta["replaced_by"] = graph["replaced_by"][path]
        text = check_okf.read_md(path)
        new = check_okf.render_frontmatter(meta) + body.lstrip("\n")
        if new != text:
            changed += 1
            if not dry_run:
                check_okf.write_md(path, new)

    total = len(extracted)
    print(f"concepts: {total}   rewritten: {changed}" + ("   (dry run)" if dry_run else ""))
    print("\ncoverage (documents with a value)")
    for key in ("materia", "fecha", "ref_legal", "impuestos", "formularios", "regimen", "exenta", "relaciones"):
        print(f"  {key:12} {coverage[key]:5}  missing {total - coverage[key]:5}")
    print("\nimpuestos (documents per value, one document can have several)")
    for value, count in impuestos.most_common():
        print(f"  {value:18} {count:5}")
    for key, paths in unresolved.items():
        print(f"\nunresolved {key}: {len(paths)}")
        for item in paths:
            print(f"  {item}")
    print("\n" + vigencia.report(graph))
    if not dry_run:
        vigencia.write_graph(graph)
        print(f"wrote {vigencia.GRAPH.name}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="report, do not write")
    parser.add_argument(
        "--no-pdf",
        action="store_true",
        help="body only, without the source-PDF fallback for lost header fields",
    )
    args = parser.parse_args()
    return rebuild(args.dry_run, from_pdf=not args.no_pdf)


if __name__ == "__main__":
    raise SystemExit(main())
