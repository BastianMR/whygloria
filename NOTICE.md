---
type: "Reference"
title: "Content notice: what this licence covers and what it does not"
description: "The MIT licence covers the code, the derived artifacts and the documentation. The SII documents are third-party publications and are not covered."
tags: []
---

# Content notice

This repository has two layers, and only one of them is his to license.

## Covered by the MIT licence (`LICENSE`)

- The code in `scripts/`.
- The derived artifacts: `navigation/`, `series/`, `relaciones.json`,
  `METADATA_GAPS.md`, `RELACIONES_UNRESOLVED.md`.
- The documentation: `README.md`, `ARCHITECTURE.md`, `CHECKLIST.md`, `GLOSSARY.md`,
  `index.md` and the folder indexes.
- The structured metadata this project adds to every concept: `type`, `title`,
  `description`, `tags`, `materia`, `fecha`, `exenta`, `impuestos`, `formularios`,
  `regimen`, `ref_legal`, `status_vigencia`, `replaced_by`, `relaciones`, `source_url`.

## Not covered, and not the author's to license

The documents themselves, in `MD_*`, `PDF_*` and `SRC_OFICIOS/`: circulares,
resoluciones, oficios, and any other document published by the
[Servicio de Impuestos Internos](https://www.sii.cl). They are works of the SII, all rights
belong to the SII, and they are reproduced here under the publisher's own terms.

## What those terms say

`https://www.sii.cl/pagina/copyright/terminos_generales.htm`, section 3: reproduction is
authorised **only when the source is cited**, for **personal, non-commercial use**, with
**no redistribution or retransmission**. Section 5 states that the printed Diario Oficial
version is the authoritative one and disclaims accuracy.

## How this project stays inside that reading

- **Every concept cites its source.** `source_url` is mandatory and points at the SII
  page the text came from; `source_retrieved` records when it was fetched.
- **No commercial use.** This is a personal project of compilation and organisation. It
  is not sold, it carries no advertising, and it is not offered as a service.
- **No claim of authority.** The repository repeats that it is not the official source and
  that the SII document always wins over anything derived here.
- **Removal on request.** If the SII, or a rights holder, asks for a document to be
  removed, it is removed. See the takedown note in `README.md`.

## If the terms and this repository ever conflict

The publisher's terms win. The code and the derived layer can stay; the documents can go.
