---
type: "Reference"
title: "WhyGloria — SII Public Tax Information"
description: "Open-source collection of Chilean SII circulares, resoluciones and public tax information."
tags: []
---



# WhyGloria — SII Public Tax Information

Open-source collection of Chilean **Servicio de Impuestos Internos (SII)** public
documents: circulares, resoluciones and related tax information, organized by year
and document type for easy lookup and reuse.

## What's inside

Two parallel trees, one for the converted markdown and one for the original
sources, both split by document type and year:

```
WhyGloria/
├── MD_CIRCULARES/           markdown concepts
│   ├── index.md
│   ├── 2013-CIRCULAR/
│   └── ...
├── MD_RESOLUCIONES/
│   ├── index.md
│   ├── 2013-RESOLUCION/
│   └── ...
├── MD_OFICIOS/              markdown concepts, 2019 onward
│   └── 2019-OFICIO/
├── PDF_CIRCULARES/          source PDFs, as SII publishes them
│   ├── index.md
│   ├── 2013-CIRCULAR/
│   └── ...
├── PDF_RESOLUCIONES/
│   └── 2013-RESOLUCION/
├── PDF_OFICIOS/             source PDFs, 2019 onward
└── SIN_PROCESAR/            local download inbox (not tracked)
```

Each document is an OKF markdown concept (`.md`) with frontmatter (`type`,
`title`, `description`, `tags`) plus structured tax metadata (`materia`,
`fecha`, `exenta`, `impuestos`, `formularios`, `regimen`, `ref_legal`),
converted from the SII PDF of the same document number.

<!-- Decision: markdown exists so AI agents and RAG pipelines can read the corpus
     without PDF parsing or OCR. The PDFs stay as provenance, never as the
     working copy. Rationale: ARCHITECTURE.md, "Why markdown". -->

## Validate

```bash
python scripts/check_okf.py         # report frontmatter problems
python scripts/check_okf.py --fix   # repair in place
python scripts/check_duplicates.py  # detect duplicate content
```

## Pipeline

`scripts/sii_pdfs.py` reads the yearly SII indexes, downloads into the local
`SIN_PROCESAR/` inbox, and publishes the converted files into the tracked
`PDF_<TYPE>/` tree. `scripts/pdf_to_md.py` turns each PDF into a concept.

```bash
python scripts/sii_pdfs.py --check     # mirror integrity
python scripts/sii_pdfs.py --download  # fetch only what is missing
python scripts/sii_pdfs.py --pending   # sources with no concept
python scripts/sii_pdfs.py --publish   # move converted sources into PDF_<TYPE>/
python scripts/pdf_to_md.py            # convert pending sources
```

The ordered procedure, the source-to-concept matching rule and the known naming
quirks live in [`CHECKLIST.md`](./CHECKLIST.md). Where the content comes from,
why it is markdown and what is still pending live in
[`ARCHITECTURE.md`](./ARCHITECTURE.md).

## Purpose

- Provide a structured, version-controlled mirror of SII public tax guidance.
- Enable search, RAG and analysis over Chilean tax regulation.
- Share openly so anyone can build on top of it.

## License

The [MIT License](./LICENSE) covers the code, the derived artifacts
(`navigation/`, `series/`, `relaciones.json`) and the documentation — in other
words, the work this project adds.

It does **not** cover the documents. Circulares, resoluciones, oficios and any
other SII publication in `MD_*`, `PDF_*` and `SRC_OFICIOS/` are works of the
[Servicio de Impuestos Internos](https://www.sii.cl), reproduced with the source
cited, for personal, non-commercial reference. All rights remain with the SII,
whose terms are at
[terminos_generales.htm](https://www.sii.cl/pagina/copyright/terminos_generales.htm).
[NOTICE.md](./NOTICE.md) spells out the exact split.

**Takedown.** This is a personal project of compilation and organisation, not an
official source and not a commercial service. If the SII or any rights holder
asks for a document to be removed, it is removed on request: open an issue and
the affected files come out of the tree, with the rest of the corpus left intact.

## OKF navigation

This repository is an [Open Knowledge Format (OKF)](https://github.com/GoogleCloudPlatform/knowledge-catalog/tree/main/okf)
bundle. Start at [index.md](./index.md) for progressive disclosure; every
`<year>-<TYPE>/` folder carries its own `index.md`.