---
type: "Reference"
title: "How WhyGloria is built"
description: "Provenance of the corpus, why the documents are markdown, how to work with the repository and what is still pending."
tags: []
---

# How WhyGloria is built

WhyGloria mirrors the [Servicio de Impuestos Internos](https://www.sii.cl) (SII)
circulares and resoluciones from 2013 onward, the oficios from 2013 onward, and the
declaraciones juradas of the 2026 *año tributario*, in two parallel trees: the
sources exactly as SII publishes them, and the same documents converted to
markdown.
This page explains where the content comes from, why it is shaped this way, how
to work with it, and what is still open.

The ordered procedure lives in [`CHECKLIST.md`](./CHECKLIST.md). This page is
the *why*; the checklist is the *how*.

## Where the content comes from

SII publishes one index page per year and document type:

- `https://www.sii.cl/normativa_legislacion/circulares/<year>/indcir<year>.htm`
- `https://www.sii.cl/normativa_legislacion/resoluciones/<year>/res_ind<year>.htm`

The third family, oficios, publishes no such page from 2019 on. From 2019 the index
is a JSON API (`www3.sii.cl/getPublicacionesCTByMateria`, one post per materia:
renta, IVA, otros) and each document is fetched with a blob GET
(`www4.sii.cl/gabineteAdmInternet/descargaArchivo`). A number is not unique there —
it repeats inside a materia and overlaps across materias — so an oficio is
identified by materia, number and publication date, and its filename carries the
three.

Before 2019 the same family is a different publication: there is no PDF at all.
SII served one HTML page per oficio
(`normativa_legislacion/jurisprudencia_administrativa/<slug>/<year>/ja<N>.htm`),
listed on three static pages per year (`<slug>_jadm<year>.htm`), plus a Word twin
(`ja<N>.doc`) holding the same text. The `<slug>` is `ley_impuesto_renta`,
`ley_impuesto_ventas` or `otras_normas`, which this corpus records as `renta`,
`iva` and `otros`. The page is the only publication of the text, so the page is
the provenance: it is mirrored into `SRC_OFICIOS/<year>-OFICIO/` and the concept
is generated from it. 2013 is mirrored; 2014-2018 wait for the same run.

The pre-2019 branch cannot carry the date in the filename: that date is read from
the document's own signature, not from the listing, so it is not known before the
page is fetched. There the identity is (materia, number), and it is the same
identity function as the 2019+ branch — the date part of the key is optional, not
a second rule.

`SRC_OFICIOS/` is the one tree named after what it holds instead of mirroring
`MD_`/`PDF_` in pairs, because calling a folder `PDF_OFICIOS` and putting HTML in
it is a lie that the next reader pays for.

### The *Suplemento Tributario*

Nine circulares shipped a *Suplemento Tributario* inside the same `.zip`: the
annual instructions for the renta return, hundreds of pages each. It belongs to
the circular that carried it and has no number of its own, but it is not a
circular, so it is its own document type (`"Suplemento Tributario"`) instead of
borrowing `SII Circular` or `SII Resolución`:

| Piece | Value |
| --- | --- |
| concept | `MD_CIRCULARES/<year>-CIRCULAR/<year>_CIRCULAR_circu<N>_suplemento.md` |
| source | `PDF_CIRCULARES/<year>-CIRCULAR/circu<N>_suplemento.<ext>`, `.pdf` or `.docx` |
| identity | `circu<N>_suplemento`, in the same `keys()` every command uses |
| title | `Suplemento Tributario N° <N> (<año tributario>)` |
| `source_url` | the `.zip` it came out of: it has no page of its own |

The concept shares the circular's folder because it belongs to that circular. The
identity carries the `_suplemento` suffix so it never collapses into `circu<N>`:
one key names one document. Nothing else about that identity moved — a circular or
a resolución without the suffix keys exactly as before.

The title is dated with the *año tributario* the document serves, read from its own
cover, because that is the year a reader looks for: the 2017 `circu60` archive
carries the AT2018 supplement and the 2018 `circu58` archive the AT2019 one, so
the folder year would be wrong.

The 2016 one is a Word 97 `.doc`. docling-serve accepts it, reports the task as
successful, and then returns a failed result with `md_content: null` and the error
`An unexpected error occurred while opening the document SUPLEMENTO_AT2016.doc`;
its own log names the cause — `LibreOffice is required to convert a .doc file to
.docx` — and there is no LibreOffice on this machine to rewrite it. So it is a
documented blocker: the binary is kept and
`PDF_CIRCULARES/2016-CIRCULAR/circu14_suplemento.blocked.txt` records the sha256,
the observed behaviour and where the file is.

The other eight are staged and waiting, not converted: docling-serve cannot get
through them on this machine (see [Pending work](#pending-work)). The pipeline is
ready — a run only has to reach a converter that survives the document.

### Declaraciones juradas

The fourth family is the *declaraciones juradas* (sworn statements) of one *año
tributario*. They do not share the yearly-index shape of the first two families:
`https://www.sii.cl/ayudas/ayudas_por_servicios/2120-formularios_y_plazos_<AT>-2171.html`
lists every DJ of that AT in one table, with the layout, its instructions, the
associated certificate layout and the exempt resolution that orders it. AT2026
lists 73 of them.

The page is parsed and its paths are never templated: SII re-rooted the DJ
folders between AT2025 (`/declaraciones_juradas/suplemento/2025/DJ1811.pdf`) and
AT2026 (`/ayudas/ayudas_por_servicios/renta/2026/layout_f1811.pdf`), so last year's
URL is not next year's URL and the number does not contain it either.

One DJ is **two documents under one number**, so the identity carries which half a
file is, exactly like `circu<N>_suplemento`:

| Piece | Value |
| --- | --- |
| concept | `MD_FORMULARIOS/<AT>-FORMULARIO/<AT>_FORMULARIO_formulario-dj<N>.md` and `...-instrucciones.md` |
| source | `PDF_FORMULARIOS/<AT>-FORMULARIO/formulario-dj<N>.pdf` and `...-instrucciones.pdf` |
| identity | `dj<N>` for the layout, `dj<N>_instrucciones` for its instructions |
| OKF `type` | `SII Formulario`, for both halves |
| title | `Declaración Jurada N° <N> (AT<AT>)` / `Instrucciones Declaración Jurada N° <N> (AT<AT>)` |
| `source_url` | the exact PDF URL the index linked |
| `source_at` | the *año tributario* the document serves |

The folder year is the *año tributario*, not the publication year, because that is
what the document declares and what a reader looks for. Neither `source_url` nor
`source_at` can be read back out of a filename, so both are written to
`<stem>.source.txt` at download time and carried into the concept from there.

`fecha` is read from the document when it states one; a layout is a form and its
instructions are not signed, so today all 146 are a reported gap instead of an
invented date. `materia` on a layout is a gap too: the form carries no MATERIA
cell, and the oath it prints in capitals is boilerplate, not a subject.

The certificate layouts in the same table are a different document and are not
mirrored here. The plain forms of the same site (F22, F29, F50) are not started
either: their index has no natural year, so it needs a year decision first.

`robots.txt` is `404` on `www.sii.cl` and `www2.sii.cl`, and the site terms
(`/pagina/copyright/terminos_generales.htm` §3) authorise reproduction only when
the source is cited. That is the licence every family here is mirrored under, and
it is why every concept carries `source_url`.

`scripts/sii_pdfs.py` reads those pages, follows every `.pdf` and `.zip` link
and downloads only what is missing. The SII front end answers `403` without a
browser user agent, so the scraper sends one. Resumable by design: re-running
never re-downloads what is already there.

Quirks that are normal, not bugs:

- A few documents ship as `.zip` instead of `.pdf` (mostly 2013 circulares).
  Nine archives were unpacked, every member verified byte for byte against the
  published PDF or the extracted file, and then removed: the circular already had
  its concept and its PDF, and each *Suplemento Tributario* now lives in
  `SIN_PROCESAR/SUPLEMENTOS/<year>-CIRCULAR/` next to a `<archive>.source.txt`
  manifest naming every member and its sha256. `--check` reads that manifest, so
  a removed archive still counts as present instead of showing up as missing. The
  *Suplementos* themselves are first-class documents now: see
  [the *Suplemento Tributario*](#the-suplemento-tributario).
- Some resolutions use an older `resosii<N>.pdf` filename prefix.
- `_afecta` in a concept name marks an amendment of the same document number,
  not a second document.

Downloads land in `SIN_PROCESAR/`, a local inbox that git ignores. Nothing is
ever deleted: the corpus only grows.

## Why markdown

The PDFs are the provenance. The markdown is the working copy.

- **Agent and RAG friendly.** Plain UTF-8 text with YAML frontmatter (`type`,
  `title`, `description`, `tags`) is greppable, chunkable and cheap to load. An
  AI agent can read a document without a PDF parser, an OCR step or a vision
  model.
- **Diffable.** A conversion fix reappears as a readable git diff per document
  instead of an opaque binary blob.
- **One direction only.** `MD_*` holds derived content, `PDF_*` holds sources.
  The pipeline always flows `SIN_PROCESAR -> MD_* -> PDF_*`, so source and
  derived content never mix. The one source that is not a PDF, the pre-2019
  oficios, publishes into `SRC_OFICIOS/` for the same reason.
- **OKF bundle.** The repository follows
  [Open Knowledge Format 0.2](https://github.com/GoogleCloudPlatform/knowledge-catalog/tree/main/okf):
  a root `index.md` for progressive disclosure and one `index.md` per folder.

## How the conversion works

`scripts/pdf_to_md.py` posts one PDF at a time to a local
[docling-serve](https://github.com/docling-project/docling-serve) instance on
`127.0.0.1:5001`, using the async endpoint because the sync one times out on
long documents. It asks for markdown with image placeholders, drops the empty
SII letterhead image, and writes the concept with frontmatter rendered by
`scripts/check_okf.py`. Documents whose number is already converted are
skipped, so a run resumes instead of duplicating.

Titles are derived from the filename number, not from the body: a circular
usually cites several other documents before reaching its own number.

The pre-2019 oficios never reach docling: their pages are plain paragraphs, so the
same script strips them itself. `html_to_markdown` drops script and style blocks,
turns block tags into paragraph breaks and `<br>` into a line break, unescapes
entities and collapses the blank-line runs it leaves behind, and it decodes the
UTF-8 **BOM** those pages carry away, because the validator rejects a BOM. It is a
second writer, not a second pipeline: same loop, same frontmatter, same index. A
run made only of HTML years needs no converter service, and a run that does need
docling still fails before converting anything when the service is down.

## Structured tax metadata

Frontmatter carries the tax signal, so a query does not have to read the prose:

| Field | Shape | Meaning |
| --- | --- | --- |
| `materia` | string | the MATERIA line, wording as published |
| `fecha` | ISO 8601 | signature date from the header |
| `exenta` | boolean | the document is a *resolución exenta* |
| `impuestos` | list of enum | `renta`, `iva`, `timbres`, `herencias`, `territorial`, `iec`, `segunda-categoria`, `contribuciones`, `patente-municipal`, `otro` |
| `formularios` | list | SII forms and sworn statements named in the body (`F22`, `DJ1887`, …), validated by shape |
| `regimen` | list of enum | `14A`, `14B`, `14D1`…`14D8`, `renta-presunta`, `pre-2020`, `no-aplica` |
| `ref_legal` | list of strings | legal citations as the document writes them |
| `source_at` | 4-digit year | the *año tributario* a formulario serves |

The vocabularies and their keyword patterns live in
[`scripts/tax_vocab.json`](./scripts/tax_vocab.json); the extraction lives in
`scripts/metadata.py` and is shared by the conversion and the backfill, so the
two paths cannot drift. Extraction is deterministic and keyword-based: it never
calls a model. Where the source has no MATERIA line or lost its date,
`check_okf.py` reports a *metadata gap* instead of an error, because inventing a
value would be worse than leaving it empty.

Concepts generated from HTML carry the provenance of that branch as well:

| Field | Shape | Meaning |
| --- | --- | --- |
| `source_url` | URL | the exact `.htm` page the text came from |
| `source_format` | `html` | the source is a page, not a PDF |
| `retrieved` | ISO 8601 | date the page was downloaded |
| `doc_url` | URL | the `.doc` twin, recorded and never stored |

Those four are not guessed: they are read from `<stem>.source.txt`, the manifest
written next to a source when it is downloaded and moved with it by `--publish`.
`materia` for that branch is the materia index that listed the oficio, because the
page prints the legal subject as prose instead of a MATERIA cell; `fecha` still
comes from the signature `(ORD. N° <num>, DE dd.mm.yyyy)` anchored on the
document's own number, so citing another oficio never counts.

`exenta`, `fecha` and `materia` are read from the body first. When the
conversion lost the header, `backfill_metadata.py` falls back to page 1 of the
tracked source PDF (pymupdf) and accepts a signature only if it carries the
document's own number, so citing another exenta resolution never counts. That
recovered 71 resolutions; the rest lack the line in the PDF too. `--no-pdf`
restores the body-only behaviour.

## Supersession map

Circulares and resoluciones repeal, modify and replace each other in their own
text. `scripts/vigencia.py` turns that into `relaciones` (one entry per stated
edge), and derives `status_vigencia` plus `replaced_by` across the whole corpus.
The graph is written to [`relaciones.json`](./relaciones.json).

Only a phrase followed by an explicit document number in the same sentence
creates an edge. That rule is measured, not assumed: `MODIFICA` appears 9207
times in this corpus and most of those are prose, not relationships.

```bash
python scripts/sii_pdfs.py --vigencia   # rebuild frontmatter status + relaciones.json
python scripts/vigencia.py              # report only, from current frontmatter
```

`status_vigencia` says what this corpus knows: `vigente` means no document here
repeals or amends it, which is not proof — an oficio or a law can repeal a
circular silently. `desconocido` is reserved for a genuine ambiguity (the same
number twice in the same year), so today it is zero; the 215 unresolved targets
are listed in the report and in `relaciones.json`, and they are the honest
"repealed from outside the corpus" set.

## Derived series

The annual circulares also publish the numeric tables a tax corpus is actually
asked about: UTM, UTA, IPC, the segunda categoría brackets and the daily UF.
`scripts/series.py` extracts them into `series/*.csv`, one row per (series,
period) with the document each value came from. UTM is complete for 2013-2026
and matches the SII table value by value; IPC covers 2012-2025 and only its
monthly variation is comparable across base changes. The segunda categoría
brackets were attempted and discarded: the two legal tables share a header shape
and fragments invent law changes.

The artifact lives in this repository because it is generated from it, never
hand-edited, and CI fails if it drifts: `python scripts/series.py` then
`git diff --exit-code`. It is explicitly not authoritative — the circular is —
and `series/README.md` carries the extraction rules and the remaining gaps.

`navigation/` is the second generated layer: one index per dimension (tax, form,
regime, materia keyword) over the whole corpus, with the status of every entry.
Documents without a value for a dimension are listed as `unclassified`, never
dropped. `GLOSSARY.md` is the only hand-maintained file in that layer.

## How to work with it

### Reading

- Start at [`index.md`](./index.md), then open the `<year>-<TYPE>/index.md` you
  need.
- Read `MD_*` for content. Open `PDF_*` only to check against the original.
- Match a source to its concept by document number, never by filename. The
  mapping table lives in [`CHECKLIST.md`](./CHECKLIST.md). For an oficio the
  number is not enough: match on materia, number and publication date.

### Changing

- Do not hand-edit `MD_*` files. They are generated; fix the script or the
  conversion and re-run, so the change survives the next pass.
- Validate before committing: `check_okf.py`, `check_duplicates.py` and
  `sii_pdfs.py --pending` must report zero problems.
- Numbers printed in prose (snapshot counts, totals) are a courtesy. The
  scripts are the source of truth; when they disagree, the scripts win.
- Save markdown as UTF-8 without BOM. The validator rejects a BOM, and it
  needs quoted YAML strings.

### Driving it with an AI agent

- Give the agent [`AGENTS.md`](./AGENTS.md), [`CHECKLIST.md`](./CHECKLIST.md)
  and this page first; the rest it can grep.
- Never bulk-load `PDF_*`: they are hundreds of megabytes of binaries.
- Ask for state from the scripts (`--pending`, `--check`), not from the counts
  written in the README.
- One phase per run, in order: download, unpack, convert, publish, validate.
  Mixing phases in a single pass is what produced the duplicate names this
  pipeline now checks for.

## Recommendations for maintainers

1. Keep the corpus append-only. Re-downloading is cheap; a source lost to a
   careless cleanup is not.
2. A *Suplemento Tributario* is keyed `circu<N>_suplemento`, never `circu<N>`. The
   suffix is load-bearing: without it the concept, the source and the circular
   collapse into one key and `--pending` reports a mirror that is fine as broken.
   The same rule makes a declaración jurada two keys, `dj<N>` and
   `dj<N>_instrucciones`, never one.
3. Fix the two legacy title collisions (`reso37` / `reso37_afecta` in 2013,
   `reso06` / `reso6` in 2014) if a strict one-file-per-document rule matters.
4. SII publishes through the year. Re-run the checklist quarterly so the mirror
   does not drift.

## References

| What | Link |
| --- | --- |
| SII circulares index | https://www.sii.cl/normativa_legislacion/circulares/ |
| SII resoluciones index | https://www.sii.cl/normativa_legislacion/resoluciones/ |
| SII jurisprudencia administrativa (oficios) | https://www.sii.cl/normativa_legislacion/jurisprudencia_administrativa/indice_jadm.htm |
| SII declaraciones juradas index (one page per *año tributario*) | https://www.sii.cl/ayudas/ayudas_por_servicios/2120-formularios_y_plazos_2026-2171.html |
| Open Knowledge Format spec | https://github.com/GoogleCloudPlatform/knowledge-catalog/tree/main/okf |
| Docling | https://github.com/docling-project/docling |
| docling-serve | https://github.com/docling-project/docling-serve |

## Pending work

- Formularios: the AT2026 declaraciones juradas are mirrored and converted end to
  end — 73 layouts and 73 instructions in `PDF_FORMULARIOS/2026-FORMULARIO/` and the
  same 146 concepts in `MD_FORMULARIOS/2026-FORMULARIO/`. The plain forms (F22, F29,
  F50) are not started: their index is ten category pages with no natural year, so
  the year a row belongs to is a decision, not a parsing problem. Earlier ATs are
  not started either; `FORMULARIO_FIRST_AT` is what says where this family begins.

- *Suplementos Tributarios*: the type, the identity, the title and the publish
  path are landed, but none of the eight convertible ones is converted yet, because
  docling-serve cannot get through them on this 8 GB host. Measured: the seven PDFs
  kill the service process a few seconds after it starts the page pipeline (the
  container restarts and the task is lost; reproduced with `circu13`/2021 at 395
  pages and `circu15`/2013 at 657), while a 209-page circular converts on the same
  instance in 12.6 minutes, so the ceiling is document size, not the request; the
  `.docx` (`circu21`/2017) ends in docling's own `ExportableDocument` validation,
  "Document hierarchy is inconsistent"; the `.doc` (`circu14`/2016) needs
  LibreOffice and is recorded as blocked. Their sources wait in
  `SIN_PROCESAR/SUPLEMENTOS/<year>-CIRCULAR/` under the canonical
  `circu<N>_suplemento.<ext>` name, and `--pending` reports the eight until a
  converter gets through them. Each archive keeps its `.source.txt` manifest with
  every member and its sha256.
- Oficios: 2019-2026 is mirrored (3.019 documents in `PDF_OFICIOS/` and the same
  in `MD_OFICIOS/`); 2013 is mirrored as HTML in `SRC_OFICIOS/2013-OFICIO/` plus
  its concepts, and 2014-2018 wait for the same run. The branch is not converted
  to PDF, and that stays a separate decision: SII never published one. Legal
  texts and regime manuals have not started, so the corpus covers four families
  of five.
- 58 documents have no date and 7 no subject in the converted header or on page
  one of their PDF; that residue needs a human, not another rule.
