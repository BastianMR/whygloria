---
type: "Reference"
title: "Derived value series"
description: "Regenerable numeric series extracted from the corpus, starting with the monthly UTM table 2013-2026."
tags: []
---

# Derived value series

Two series built from the circulares that publish them:

- `utm.csv` — monthly *Unidad Tributaria Mensual*, 2013-2026.
- `ipc.csv` — monthly CPI index and variation, 2012-12 to 2025-11.

Every row carries the document it came from, so a value can always be traced
back to the circular that states it.

This directory is **derived and regenerable**. It is not a source of truth: the
circular is. If a row disagrees with its cited document, the document wins.

## Rebuild

```bash
python scripts/series.py --report
```

The build reads `MD_*` only, is deterministic (two runs produce byte-identical
files) and is checked in CI with `git diff --exit-code`. There is no timestamp
or commit hash inside the artifacts on purpose: the commit that built them is
the last commit touching `series/`.

## Rules

- One row per (series, period). When several circulares reprint the same month,
  the most recent document wins; a conflicting reprint is counted, not merged.
- A value outside 10.000-200.000 CLP is treated as a broken table cell and the
  row is dropped. 33 rows were dropped for this reason.
- The UTA column is cross-checked against 12 x UTM. 85 cells fail that check
  because the conversion lost a digit; the UTM value is still used and the
  mismatch is counted in `build.json`.
- Nothing is interpolated. A month with no publishable value stays missing.
- For IPC, the comparable column is `var_monthly_pct`. `index_points` keeps the
  base of the circular it came from, and those bases change over time, so the
  points are not comparable across decades even though the variation is.

## Coverage

UTM: 167 of 168 month slots. The only gap is 2026-12, which no document in the
corpus publishes yet; the SII already publishes it as 72.802.

IPC: 156 of 168 slots between 2012-12 and 2025-11. Every circular closes the
previous year's series, so the current year is never complete by construction.

## Verification

- All 167 UTM rows appear verbatim next to their month in the document cited by
  the row, not just a sample.
- Ten UTM rows were also checked against their source PDF with an independent
  extractor (pymupdf), so the values do not rest on the docling conversion.
- **Against the issuing institution**: 166 of 166 UTM values match the monthly
  table published at `www.sii.cl/valores_y_fechas/utm/utm<year>.htm`, and 155 of
  155 IPC monthly variations match the same pages. Checked once, by hand, on
  2026-11-09; the check is not part of the build because it needs the network.
- Two builds produce the same bytes.
- Three UTM rows cite a circular from the following year: the January circular
  reprints the closing table of the previous year, so `source_year` can be
  `period year + 1`.
- IPC index points carry the base of their source document; one probe against
  the SII disagreed for that reason, which is why only the variation is claimed
  as comparable.

## Not built: segunda categoría brackets

The bracket tables are present (197 documents with a matching header) and a
parser was written and discarded. Two problems made the output unsafe: the
Art. 43 N° 1 table and the Art. 52 bis table share the same header shape, and
several circulars print only a fragment of the table. The result was a series
that invented a law change every few months. Distinguishing the two tables needs
the section context around the table, not the table itself. A wrong bracket
table is worse than a missing one, so nothing was published.

## What the corpus already carries

## What the corpus already carries

Measured with the same scan, counting documents and documents with a matching
table header:

| Series | Circulares | Resoluciones | With a table | Cadence |
| --- | --- | --- | --- | --- |
| UTM | 382 | 39 | 350 | monthly, in the annual table |
| UTA | 211 | 24 | 182 | monthly, next to UTM |
| IPC | 382 | 21 | 318 | monthly, in the annual table |
| segunda categoría | 241 | 95 | 197 | monthly brackets |
| UF | 68 | 46 | 41 | daily table, published on demand |
| límites en UF/UTM | 15 | 5 | 9 | per reform, not periodic |
| dólar observado | 1 | 0 | 1 | effectively absent |
| interés por mora | 0 | 0 | 0 | absent |

The next series after this review are IPC and the segunda categoría brackets,
both of which share the annual table shape.
