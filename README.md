---
type: Reference
title: WhyGloria — SII Public Tax Information
description: Open-source collection of Chilean SII circulares, resoluciones and public tax information.
---

# WhyGloria — SII Public Tax Information

Open-source collection of Chilean **Servicio de Impuestos Internos (SII)** public
documents: circulares, resoluciones and related tax information, organized by year
and document type for easy lookup and reuse.

## What's inside

Each document lives in a folder named `<year>-<TYPE>` (e.g. `2013-CIRCULAR`,
`2013-RESOLUCION`) and keeps its original filename:

```
WhyGloria/
├── 2013-CIRCULAR/
├── 2013-RESOLUCION/
├── 2014-CIRCULAR/
├── ...
└── 2025-CIRCULAR/
```

Each `.docx` is converted to a sibling OKF markdown concept (`.md`) with
frontmatter (`type`, `title`, `description`, `resource`, `tags`); the original
`.docx` is kept as the `resource`. Conversion script:
[`scripts/convert_docx_to_md.py`](./scripts/convert_docx_to_md.py).

## Purpose

- Provide a structured, version-controlled mirror of SII public tax guidance.
- Enable search, RAG and analysis over Chilean tax regulation.
- Share openly so anyone can build on top of it.

## License

Released under the [MIT License](./LICENSE). The SII documents themselves are
public information published by the Chilean tax authority; this repository only
repackages them for accessibility.

## OKF navigation

This repository is an [Open Knowledge Format (OKF)](https://github.com/GoogleCloudPlatform/knowledge-catalog/tree/main/okf)
bundle. Start at [index.md](./index.md) for progressive disclosure; every
`<year>-<TYPE>/` folder carries its own `index.md`.