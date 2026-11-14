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
| `MD_OFICIOS/<year>-OFICIO/` | markdown concepts | yes |
| `PDF_OFICIOS/<year>-OFICIO/` | source PDFs, oficios 2019 onward | yes |
| `SRC_OFICIOS/<year>-OFICIO/` | source HTML, oficios up to 2018 | yes |
| `MD_FORMULARIOS/<AT>-FORMULARIO/` | markdown concepts, declaraciones juradas | yes |
| `PDF_FORMULARIOS/<AT>-FORMULARIO/` | source PDFs, declaraciones juradas | yes |
| `SIN_PROCESAR/<year>-<TYPE>/` | download inbox | no |

Data moves one way: a document lands in `SIN_PROCESAR/`, becomes a concept in
`MD_<TYPE>/`, and finally is published to `PDF_<TYPE>/` — or to `SRC_OFICIOS/` when
the source is an HTML page. Nothing is deleted.

Oficios are the third family, and the one that does not fit the yearly-index
shape. From 2019 their index is a JSON API (`getPublicacionesCTByMateria`) and the
download is a blob GET (`gabineteAdmInternet/descargaArchivo`), not a link to a
`.pdf`. A number is not unique there — it repeats inside a materia and overlaps
across materias — so an oficio is identified by materia, number and publication
date, and the filename carries all three.

Up to 2018 the oficios are a different publication: one HTML page per document
(`.../jurisprudencia_administrativa/<slug>/<year>/ja<N>.htm`), listed on three
static pages per year, plus a `.doc` twin of the same text and no PDF anywhere.
The page is the only publication of the text, so the page is the source and it is
published into `SRC_OFICIOS/<year>-OFICIO/`, never into a `PDF_` folder. The twin
is recorded in the frontmatter as `doc_url` and is not downloaded. There the
filename carries materia and number only: the date is read from the document's own
signature, so it cannot be in the name before the page is fetched. Each source
keeps its provenance in `<stem>.source.txt` next to it, written at download time.

*Suplementos Tributarios* share a circular's folders: nine circulares shipped one
inside their `.zip`. The archive was unpacked, verified and removed, so its member
is staged as `SIN_PROCESAR/SUPLEMENTOS/<year>-CIRCULAR/circu<N>_suplemento.<ext>`,
converted into `MD_CIRCULARES/<year>-CIRCULAR/<year>_CIRCULAR_circu<N>_suplemento.md`
and published to `PDF_CIRCULARES/<year>-CIRCULAR/`. A *Suplemento* is its own
OKF type (`Suplemento Tributario`) and its own identity (`circu<N>_suplemento`),
never the circular's, even though it borrows the folder and the number.

*Declaraciones juradas* (formularios) are the fourth family and the only one
indexed by *año tributario* instead of calendar year. One page per AT lists every
DJ of that year, and its `<AT>-FORMULARIO` folder is named after the AT because
that is what the document declares. One DJ is two documents under one number: the
layout and its instructions, staged as
`SIN_PROCESAR/<AT>-FORMULARIO/formulario-dj<N>.pdf` and `...-instrucciones.pdf`,
converted into `MD_FORMULARIOS/<AT>-FORMULARIO/` and published to
`PDF_FORMULARIOS/<AT>-FORMULARIO/`. Their identity is `dj<N>` and
`dj<N>_instrucciones`, so the two never collapse into each other.

## Checklist

- [ ] **1. Check the mirror** — `python scripts/sii_pdfs.py --check`
  Expect `missing = 0` on every row. Exit code 1 means a source is absent.
  `--list` prints what each index actually yields, one `name<TAB>url` line per
  document, which is the evidence a row count alone does not give.
- [ ] **2. Download what is missing** — `python scripts/sii_pdfs.py --download`
  Fetches only the absent files, into `SIN_PROCESAR/`. Resumable: re-running is safe.
  `--years` and `--kind` narrow a run to one year or one family, so landing a new
  family never downloads the backlog of the others.
- [ ] **3. Unpack the zip circulares** — `python scripts/sii_pdfs.py --unpack`
  Extracts the circular itself into the inbox; the *Suplemento Tributario* stays in the archive.
  The nine archives that shipped one are gone: their *Suplementos* wait in
  `SIN_PROCESAR/SUPLEMENTOS/<year>-CIRCULAR/` under the canonical
  `circu<N>_suplemento.<ext>` name, which is what step 5 reads.
- [ ] **4. Read the backlog** — `python scripts/sii_pdfs.py --pending`
  Lists document numbers that have a source but no concept. Exit code 1 means there is work.
- [ ] **5. Convert** — `python scripts/pdf_to_md.py`
  Requires `docling-serve` on `127.0.0.1:5001` for the PDFs. Skips numbers already
  converted. A *Suplemento* is a PDF or a `.docx` and rides the same upload, with
  the content type its suffix declares. A declaración jurada converts like any
  other PDF, and its concept keeps the source stem because one DJ number is two
  documents. The HTML years need no service: the body is stripped from the page,
  BOM and tags included.
- [ ] **6. Publish the sources** — `python scripts/sii_pdfs.py --publish`
  Moves the converted files from `SIN_PROCESAR/` into `PDF_<TYPE>/` — or into
  `SRC_OFICIOS/` for the HTML years — and rebuilds those indexes.
- [ ] **7. Validate** — `python scripts/check_okf.py` and `python scripts/check_duplicates.py`
  Expect `0 problems` and `0 exact duplicate groups`. Title collisions are informational.
- [ ] **8. Re-check the backlog** — `python scripts/sii_pdfs.py --pending`
  Expect `pending conversion: 0`. Anything left is a decision, not a bug.
- [ ] **9. Rebuild the supersession map** — `python scripts/sii_pdfs.py --vigencia`
  Rewrites `status_vigencia` and `relaciones.json` from the corpus. Deterministic:
  two runs on the same commit produce the same file.
- [ ] **10. Rebuild the derived series** — `python scripts/series.py --report`
  Regenerates `series/*.csv` from the corpus. Deterministic; CI fails if it drifts.
- [ ] **11. Rebuild the navigation indexes** — `python scripts/navigation.py`
  Regenerates `navigation/` from frontmatter. Deterministic; CI fails if it drifts.
- [ ] **12. Commit** — review `git status`, then commit.

## Matching a source to its concept

Source and concept filenames are not identical, so never match by filename. Match
by document number, inside the folder with the same `<year>-<TYPE>` name:

| source | concept |
| --- | --- |
| `PDF_RESOLUCIONES/2014-RESOLUCION/reso18.pdf` | `MD_RESOLUCIONES/2014-RESOLUCION/2014_RESOLUCION_reso18.md` |
| `PDF_CIRCULARES/2025-CIRCULAR/circu68.pdf` | `MD_CIRCULARES/2025-CIRCULAR/2025_CIRCULAR_circu68.md` |
| `PDF_CIRCULARES/2013-CIRCULAR/circu15_suplemento.pdf` | `MD_CIRCULARES/2013-CIRCULAR/2013_CIRCULAR_circu15_suplemento.md` |
| `PDF_FORMULARIOS/2026-FORMULARIO/formulario-dj1811.pdf` | `MD_FORMULARIOS/2026-FORMULARIO/2026_FORMULARIO_formulario-dj1811.md` |
| `PDF_FORMULARIOS/2026-FORMULARIO/formulario-dj1811-instrucciones.pdf` | `MD_FORMULARIOS/2026-FORMULARIO/2026_FORMULARIO_formulario-dj1811-instrucciones.md` |
| `PDF_OFICIOS/2019-OFICIO/oficio-renta-2722-2019-12-30.pdf` | `MD_OFICIOS/2019-OFICIO/2019_OFICIO_oficio-renta-2722-2019-12-30.md` |
| `SRC_OFICIOS/2013-OFICIO/oficio-renta-2722.html` | `MD_OFICIOS/2013-OFICIO/2013_OFICIO_oficio-renta-2722.md` |

- `circu<N>.*` maps to `*CIRCULAR*circu<N>*.md`
- `circu<N>_suplemento.*` maps to `*CIRCULAR*circu<N>_suplemento.md`. The suffix is
  part of the identity: a *Suplemento Tributario* is not the circular of the same
  number and has no number of its own.
- `reso<N>.*` and `resosii<N>.*` map to `*RESOLUCION*reso<N>*.md`
- `oficio-<materia>-<N>-<date>.*` maps to `*OFICIO*oficio-<materia>-<N>-<date>.md`.
  An oficio number alone is **not** an identity: the same number can name a renta
  oficio and an IVA oficio in the same year.
- `oficio-<materia>-<N>.*` is the form up to 2018, with no date: that date comes
  from the document's signature, so it does not exist yet when the page is named.
  There `(materia, N)` is the whole identity, and the same key function reads both
  forms.
- `formulario-dj<N>.pdf` maps to `*FORMULARIO*formulario-dj<N>.md` and
  `formulario-dj<N>-instrucciones.pdf` to `*FORMULARIO*formulario-dj<N>-instrucciones.md`.
  A DJ number names two documents (the layout and its instructions), so the
  `-instrucciones` suffix is part of the identity, `dj<N>_instrucciones`.
- Suffixes such as `_afecta` are the same document, not a second one.

## Naming quirks to expect

| Quirk | Example | Meaning |
| --- | --- | --- |
| `resosii<N>.pdf` | `2016-RESOLUCION/resosii38.pdf` | resolution published under an older filename prefix |
| `circu<N>.zip` | `2013-CIRCULAR/circu15.zip` | **historical**: the nine archives were unpacked, verified and removed; their *Suplementos* live in `SIN_PROCESAR/SUPLEMENTOS/<year>-CIRCULAR/` with a `.source.txt` manifest |
| `_afecta` suffix in `.md` | `2013_RESOLUCION_reso37_afecta.md` | amendment of the same resolution, same number |
| `oficio-<materia>-<N>.html` | `SRC_OFICIOS/2013-OFICIO/oficio-renta-2722.html` | oficio up to 2018: the HTML is the source and `ja<N>.doc` is its twin, recorded as `doc_url` and not stored |
| `<stem>.source.txt` | `SRC_OFICIOS/2013-OFICIO/oficio-renta-2722.source.txt` | where the source came from and when: `url`, `doc_url`, `materia`, `retrieved` |
| `circu<N>_suplemento.<ext>` | `2013-CIRCULAR/circu15_suplemento.pdf` | the *Suplemento Tributario* that shipped inside `circu15.zip`: same folder, same number, own identity |
| `formulario-dj<N>(-instrucciones).pdf` | `2026-FORMULARIO/formulario-dj1811-instrucciones.pdf` | a declaración jurada and its separate instructions: one DJ number, two documents, own identity each |
| `<stem>.source.txt` | `2026-FORMULARIO/formulario-dj1811.source.txt` | where the source came from and when: `url`, `at` (*año tributario*), `retrieved` |
| `<stem>.blocked.txt` | `2016-CIRCULAR/circu14_suplemento.blocked.txt` | a source this toolchain cannot convert, with the sha256, what was observed and where the binary is kept |

## Snapshot 2026-11-09

- 2914 source files mirrored in `PDF_*` (664 MB), 2904 concepts in `MD_*`.
- 2013 to 2026, both document types, complete.
- Declaraciones juradas: AT2026 is mirrored end to end — 73 layouts and 73 sets of
  instructions in `PDF_FORMULARIOS/2026-FORMULARIO/` and the same 146 concepts in
  `MD_FORMULARIOS/2026-FORMULARIO/`, each with its `source_url` and `source_at`.
  The plain forms (F22, F29, F50) and the other ATs are not started. See
  `odd/tasks/formularios-family.md`.
- Oficios: 2019-2026 is mirrored end to end — 3.019 documents in
  `PDF_OFICIOS/<year>-OFICIO/` and the same in `MD_OFICIOS/`. 2013 is mirrored as
  HTML in `SRC_OFICIOS/2013-OFICIO/` plus its 175 concepts in
  `MD_OFICIOS/2013-OFICIO/`; 2014-2018 wait for the same run. SII published no
  PDF for that branch, so there is none to mirror. See
  `odd/tasks/oficios-html-family.md`.
- The nine *Suplementos Tributarios* are a first-class document type
  (`Suplemento Tributario`, identity `circu<N>_suplemento`) and their sources are
  staged, but **none is converted yet**: docling-serve dies on the PDFs on this
  8 GB host (395 pages and up; a 209-page circular converts fine), fails the
  `.docx` with `Document hierarchy is inconsistent`, and answers the `.doc` with
  `md_content: null` because it needs LibreOffice — that last one is recorded in
  `circu14_suplemento.blocked.txt`. `--pending` reports the eight until a converter
  gets through them: `circu 15/2013 · 18/2014 · 22/2015 · 21 and 60/2017 · 58/2018 ·
  8/2020 · 13/2021`, staged as
  `SIN_PROCESAR/SUPLEMENTOS/<year>-CIRCULAR/circu<N>_suplemento.<ext>`. Every
  archive keeps a `.source.txt` manifest naming each member and its sha256.
- Two known title collisions predate this pipeline: `reso37`/`reso37_afecta`
  (2013) and `reso06`/`reso6` (2014).

`--pending` and `--check` are the source of truth; the numbers above rot.
