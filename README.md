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

Source files are `.docx` exports of the SII public documents.

## Purpose

- Provide a structured, version-controlled mirror of SII public tax guidance.
- Enable search, RAG and analysis over Chilean tax regulation.
- Share openly so anyone can build on top of it.

## License

Released under the [MIT License](./LICENSE). The SII documents themselves are
public information published by the Chilean tax authority; this repository only
repackages them for accessibility.

## OKF index

See [OKF_INDEX.md](./OKF_INDEX.md) for the list of Google Open Knowledge Format
(OKF) repositories and tools used to work with this knowledge base.