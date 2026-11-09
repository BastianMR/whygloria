---
type: "Reference"
title: "Agent notes"
description: "Commands and rules for working on this repository with an AI agent."
tags: []
---

# Agent notes

## Commands

```bash
python scripts/sii_pdfs.py --check      # mirror integrity, expect missing = 0
python scripts/sii_pdfs.py --download   # fetch only what is missing
python scripts/sii_pdfs.py --unpack     # extract the zip-only circulares
python scripts/sii_pdfs.py --pending    # sources without a concept, expect 0
python scripts/pdf_to_md.py             # convert pending; needs docling-serve on 127.0.0.1:5001
python scripts/sii_pdfs.py --publish    # move converted sources into PDF_<TYPE>/
python scripts/check_okf.py             # expect 0 problems
python scripts/check_duplicates.py      # expect 0 exact duplicate groups
```

## Rules

- `MD_*` is generated. Fix the script or the conversion, never the markdown.
- Match a source to its concept by document number, never by filename.
- Write UTF-8 without BOM and quote YAML frontmatter values.
- The corpus is append-only: never delete a source or a concept.
- Counts in prose are stale by design; ask the scripts for the real state.
