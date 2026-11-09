---
type: "Reference"
title: "SII pipeline checklist"
description: "Ordered steps for mirroring SII documents, converting them to markdown and publishing the sources."
tags: []
---

# Pipeline checklist

Ordered steps for mirroring SII documents and converting them to markdown. Every
command runs from the repository root.

## Layout

| Folder | Contents | Tracked in git |
| --- | --- | --- |
| `MD_CIRCULARES/<year>-CIRCULAR/` | markdown concepts | yes |
| `MD_RESOLUCIONES/<year>-RESOLUCION/` | markdown concepts | yes |
| `PDF_CIRCULARES/<year>-CIRCULAR/` | source PDFs, plus the `.zip` ones | yes |
| `PDF_RESOLUCIONES/<year>-RESOLUCION/` | source PDFs | yes |
| `SIN_PROCESAR/<year>-<TYPE>/` | download inbox | no |

Data moves one way: a document lands in `SIN_PROCESAR/`, becomes a concept in
`MD_<TYPE>/`, and finally is published to `PDF_<TYPE>/`. Nothing is deleted.

## Checklist

- [ ] **1. Check the mirror** — `python scripts/sii_pdfs.py --check`
  Expect `missing = 0` on every row. Exit code 1 means a source is absent.
- [ ] **2. Download what is missing** — `python scripts/sii_pdfs.py --download`
  Fetches only the absent files, into `SIN_PROCESAR/`. Resumable: re-running is safe.
- [ ] **3. Unpack the zip circulares** — `python scripts/sii_pdfs.py --unpack`
  Extracts the circular itself into the inbox; the *Suplemento Tributario* stays in the archive.
- [ ] **4. Read the backlog** — `python scripts/sii_pdfs.py --pending`
  Lists document numbers that have a source but no concept. Exit code 1 means there is work.
- [ ] **5. Convert** — `python scripts/pdf_to_md.py`
  Requires `docling-serve` on `127.0.0.1:5001`. Skips numbers already converted.
- [ ] **6. Publish the sources** — `python scripts/sii_pdfs.py --publish`
  Moves the converted files from `SIN_PROCESAR/` into `PDF_<TYPE>/` and rebuilds those indexes.
- [ ] **7. Validate** — `python scripts/check_okf.py` and `python scripts/check_duplicates.py`
  Expect `0 problems` and `0 exact duplicate groups`. Title collisions are informational.
- [ ] **8. Re-check the backlog** — `python scripts/sii_pdfs.py --pending`
  Expect `pending conversion: 0`. Anything left is a decision, not a bug.
- [ ] **9. Rebuild the supersession map** — `python scripts/sii_pdfs.py --vigencia`
  Rewrites `status_vigencia` and `relaciones.json` from the corpus. Deterministic:
  two runs on the same commit produce the same file.
- [ ] **10. Rebuild the derived series** — `python scripts/series.py --report`
  Regenerates `series/*.csv` from the corpus. Deterministic; CI fails if it drifts.
- [ ] **11. Commit** — review `git status`, then commit.

## Matching a source to its concept

Source and concept filenames are not identical, so never match by filename. Match
by document number, inside the folder with the same `<year>-<TYPE>` name:

| source | concept |
| --- | --- |
| `PDF_RESOLUCIONES/2014-RESOLUCION/reso18.pdf` | `MD_RESOLUCIONES/2014-RESOLUCION/2014_RESOLUCION_reso18.md` |
| `PDF_CIRCULARES/2025-CIRCULAR/circu68.pdf` | `MD_CIRCULARES/2025-CIRCULAR/2025_CIRCULAR_circu68.md` |

- `circu<N>.*` maps to `*CIRCULAR*circu<N>*.md`
- `reso<N>.*` and `resosii<N>.*` map to `*RESOLUCION*reso<N>*.md`
- Suffixes such as `_afecta` are the same document, not a second one.

## Naming quirks to expect

| Quirk | Example | Meaning |
| --- | --- | --- |
| `resosii<N>.pdf` | `2016-RESOLUCION/resosii38.pdf` | resolution published under an older filename prefix |
| `circu<N>.zip` | `2013-CIRCULAR/circu15.zip` | document shipped as a zip instead of a PDF |
| `_afecta` suffix in `.md` | `2013_RESOLUCION_reso37_afecta.md` | amendment of the same resolution, same number |

## Snapshot 2026-11-09

- 2914 source files mirrored in `PDF_*` (664 MB), 2904 concepts in `MD_*`.
- 2013 to 2026, both document types, complete.
- 9 *Suplementos Tributarios* remain unconverted inside their `.zip`: they are a
  publication without a circular number, and the bundle has no convention for
  them yet. `circu 8/2020 · 13/2021 · 14/2016 · 15/2013 · 18/2014 · 21 and 60/2017 · 22/2015 · 58/2018`.
- Two known title collisions predate this pipeline: `reso37`/`reso37_afecta`
  (2013) and `reso06`/`reso6` (2014).

`--pending` and `--check` are the source of truth; the numbers above rot.
