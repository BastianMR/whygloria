---
type: "Reference"
title: "sin-procesar — raw SII PDFs"
description: "Staging area for the original SII PDFs, and how a source PDF maps to a converted markdown concept."
tags: []
---

# sin-procesar

Staging area for the original SII PDFs. Everything here is gitignored except this
note: the repository ships the converted `.md` concepts, this folder keeps the
raw source they were derived from.

It mirrors the yearly SII indexes, one folder per year and document type:

```
sin-procesar/2014-RESOLUCION/reso18.pdf
sin-procesar/2025-CIRCULAR/circu68.pdf
```

Refresh it with:

```bash
python scripts/sii_pdfs.py --check      # mirror integrity: which PDFs are missing
python scripts/sii_pdfs.py --download   # fetch only the missing ones
```

## How to tell processed from pending

Source and concept filenames are **not** identical, so never match by filename.
Match by document number, inside the folder with the same `<year>-<TYPE>` name:

| source | concept |
| --- | --- |
| `sin-procesar/2014-RESOLUCION/reso18.pdf` | `resoluciones/2014-RESOLUCION/2014_RESOLUCION_reso18.md` |
| `sin-procesar/2025-CIRCULAR/circu68.pdf` | `circulares/2025-CIRCULAR/2025_CIRCULAR_circu68.md` |

- `circu<N>.*` maps to `*CIRCULAR*circu<N>*.md`
- `reso<N>.*` and `resosii<N>.*` map to `*RESOLUCION*reso<N>*.md`
- Suffixes such as `_afecta` are the same document, not a second one.

A document is **processed** when that `.md` exists. Anything else is **pending**.

```bash
python scripts/sii_pdfs.py --pending
```

That is the whole check: it lists, per folder, the document numbers that have a
source file but no concept. It exits 1 while the backlog is non-empty, so it also
works as a gate.

## Converting

```bash
python scripts/pdf_to_md.py            # everything pending
python scripts/pdf_to_md.py --limit 3  # smoke test
```

The script uploads each PDF, one at a time, to the local `docling-serve` container
(the same backend the docling MCP wraps). It writes the concept into
`circulares/<year>-CIRCULAR/<year>_CIRCULAR_circu<N>.md` or
`resoluciones/<year>-RESOLUCION/<year>_RESOLUCION_reso<N>.md`, renders the OKF
frontmatter with `check_okf.concept_meta`, and rebuilds that folder's `index.md`.
A document whose number is already converted is skipped, so a stop and restart
resumes.

Nine circulares are published as `.zip` instead of a plain PDF. `--unpack`
extracts the circular itself into the staging folder so the normal pipeline
picks it up; the *Suplemento Tributario* bundled with it stays inside the
archive (see the snapshot below).

## Naming quirks to expect

| Quirk | Example | Meaning |
| --- | --- | --- |
| `resosii<N>.pdf` | `2016-RESOLUCION/resosii38.pdf` | resolution published under an older filename prefix |
| `circu<N>.zip` | `2013-CIRCULAR/circu15.zip` | document shipped as a zip; `--unpack` extracts the circular |
| `_afecta` suffix in `.md` | `2013_RESOLUCION_reso37_afecta.md` | amendment of the same resolution, same number |

## Snapshot 2026-11-08: 0 pending

Every document SII published between 2013 and 2026 is mirrored and converted.
Nine circulares arrive as `.zip` instead of a plain PDF; `--unpack` extracted the
circular itself and the pipeline converted it:

```
circu  8/2020 · 13/2021 · 14/2016 · 15/2013 · 18/2014 · 21 and 60/2017 · 22/2015 · 58/2018
```

Each of those archives also carries a *Suplemento Tributario*: 3 to 35 MB of the
annual tax supplement, which is the real content — the circular is a two-page
cover letter announcing it. Two of them are `.doc`/`.docx`. They are **not**
converted: the bundle has no convention for a publication that has no circular
number, and inventing one was left out.

`--pending` is the source of truth; this snapshot rots.

## After converting

Write the `.md` into `circulares/<year>-CIRCULAR/` or
`resoluciones/<year>-RESOLUCION/`, add it to that folder's `index.md`, and keep
the PDF here. The PDF is the source of truth if a concept needs to be rebuilt.
