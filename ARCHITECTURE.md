---
type: "Reference"
title: "How WhyGloria is built"
description: "Provenance of the corpus, why the documents are markdown, how to work with the repository and what is still pending."
tags: []
---

# How WhyGloria is built

WhyGloria mirrors the [Servicio de Impuestos Internos](https://www.sii.cl) (SII)
circulares and resoluciones from 2013 onward in two parallel trees: the PDFs
exactly as SII publishes them, and the same documents converted to markdown.
This page explains where the content comes from, why it is shaped this way, how
to work with it, and what is still open.

The ordered procedure lives in [`CHECKLIST.md`](./CHECKLIST.md). This page is
the *why*; the checklist is the *how*.

## Where the content comes from

SII publishes one index page per year and document type:

- `https://www.sii.cl/normativa_legislacion/circulares/<year>/indcir<year>.htm`
- `https://www.sii.cl/normativa_legislacion/resoluciones/<year>/res_ind<year>.htm`

`scripts/sii_pdfs.py` reads those pages, follows every `.pdf` and `.zip` link
and downloads only what is missing. The SII front end answers `403` without a
browser user agent, so the scraper sends one. Resumable by design: re-running
never re-downloads what is already there.

Quirks that are normal, not bugs:

- A few documents ship as `.zip` instead of `.pdf` (mostly 2013 circulares);
  `--unpack` extracts the circular itself and leaves the *Suplemento
  Tributario* in the archive.
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
  derived content never mix.
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

## How to work with it

### Reading

- Start at [`index.md`](./index.md), then open the `<year>-<TYPE>/index.md` you
  need.
- Read `MD_*` for content. Open `PDF_*` only to check against the original.
- Match a source to its concept by document number, never by filename. The
  mapping table lives in [`CHECKLIST.md`](./CHECKLIST.md).

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
2. Decide the *Suplemento Tributario* convention before converting them. They
   have no circular number, so they do not fit the `circu<N>` naming yet.
3. Fix the two legacy title collisions (`reso37` / `reso37_afecta` in 2013,
   `reso06` / `reso6` in 2014) if a strict one-file-per-document rule matters.
4. Add CI that runs the three validators on push. They are offline checks, so
   a free runner is enough.
5. SII publishes through the year. Re-run the checklist quarterly so the mirror
   does not drift.

## References

| What | Link |
| --- | --- |
| SII circulares index | https://www.sii.cl/normativa_legislacion/circulares/ |
| SII resoluciones index | https://www.sii.cl/normativa_legislacion/resoluciones/ |
| Open Knowledge Format spec | https://github.com/GoogleCloudPlatform/knowledge-catalog/tree/main/okf |
| Docling | https://github.com/docling-project/docling |
| docling-serve | https://github.com/docling-project/docling-serve |

## Pending work

- 9 *Suplementos Tributarios* remain unconverted inside their `.zip`: they are a
  publication without a circular number, and the bundle has no convention for
  them yet.
- The two title collisions above predate the pipeline.
- No CI yet: the validators only run by hand.
