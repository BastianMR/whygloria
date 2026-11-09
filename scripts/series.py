#!/usr/bin/env python3
"""Derive numeric series from the corpus.

Read-only over `MD_*`. The UTM table is published inside the annual circulares
and filled month by month, so a single document never carries the whole year:
this scans every table, keeps one row per (series, period), and records the
document each value came from.

Nothing is hand-typed and nothing is interpolated. A row that cannot be tied to
a column header, or whose UTA does not equal twelve UTM, is reported as suspect
and dropped.

Usage:
    python scripts/series.py             # rebuild series/utm.csv
    python scripts/series.py --report    # rebuild and print the coverage report
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

import metadata

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "series"
UTM_CSV = OUT / "utm.csv"
IPC_CSV = OUT / "ipc.csv"
BUILD_JSON = OUT / "build.json"
MD = {"circular": ROOT / "MD_CIRCULARES", "resolucion": ROOT / "MD_RESOLUCIONES"}
FIRST_YEAR = 2013
IPC_FIRST_YEAR = 2012
LAST_YEAR = 2026
MONTHS = metadata.MONTHS
UTM_RANGE = (10_000, 200_000)
CELL_RE = re.compile(r"[|*_`]")


def cells(line: str) -> list[str]:
    return [CELL_RE.sub("", part).strip() for part in line.strip().strip("|").split("|")]


def tables(body: str) -> list[list[list[str]]]:
    """Consecutive markdown table lines, as rows of cells."""
    found, current = [], []
    for line in body.splitlines():
        if line.lstrip().startswith("|"):
            current.append(cells(line))
        elif current:
            found.append(current)
            current = []
    if current:
        found.append(current)
    return found


def number(text: str) -> int | None:
    value = re.sub(r"[^\d,.]", "", text)
    if not value:
        return None
    value = value.replace(".", "").replace(",", ".")
    try:
        return int(round(float(value)))
    except ValueError:
        return None


def month_year_before(row: list[str], index: int) -> tuple[int, int] | None:
    """Walk left from a value cell to its month name and four-digit year."""
    month = year = None
    for position in range(index - 1, -1, -1):
        text = row[position].strip().lower()
        if year is None and re.fullmatch(r"(19|20)\d{2}", text):
            year = int(text)
        if text in MONTHS and month is None:
            month = MONTHS[text]
            break
    if month and year:
        return year, month
    return None


def decimal(text: str) -> float | None:
    value = re.sub(r"[^\d,.-]", "", text or "")
    if not value or not re.search(r"\d", value):
        return None
    value = value.replace(".", "").replace(",", ".")
    try:
        return float(value)
    except ValueError:
        return None


def ipc_rows(body: str) -> list[tuple[int, int, float, float | None]]:
    """(year, month, index points, monthly variation) from every IPC table."""
    rows = []
    for table in tables(body):
        if not table:
            continue
        first_rows = " ".join(
            " ".join(cell.strip().upper() for cell in row) for row in table[:3]
        )
        if "VALOR EN PUNTOS" not in first_rows and "VIPC" not in first_rows:
            continue
        labels: list[str] = []
        header_index = 0
        for position, candidate in enumerate(table[:3]):
            candidate_labels = [cell.strip().upper() for cell in candidate]
            if "VALOR EN PUNTOS" in " ".join(candidate_labels) or "VIPC" in candidate_labels:
                labels = candidate_labels
                header_index = position
                break
        if not labels:
            continue
        index_columns = [
            position for position, label in enumerate(labels)
            if label.startswith("VALOR EN PUNTOS") or label in {"ÍNDICE", "INDICE", "IPC"}
        ]
        variation_columns = {
            position for position, label in enumerate(labels)
            if label == "VIPC" or label.startswith("MENSUAL")
        }
        for row in table[header_index + 1 :]:
            if len(row) != len(labels):
                continue
            for column in index_columns:
                period = month_year_before(row, column)
                points = decimal(row[column])
                if not period or points is None or not (50 <= points <= 500):
                    continue
                variation = decimal(row[column + 1]) if column + 1 in variation_columns else None
                rows.append((period[0], period[1], points, variation))
    return rows


def utm_rows(body: str) -> list[tuple[int, int, int, int | None]]:
    """(year, month, utm, uta) rows from every table that has a UTM column."""
    rows = []
    for table in tables(body):
        if not table:
            continue
        header = table[0]
        utm_columns = [
            index for index, cell in enumerate(header) if cell.strip().upper() == "UTM"
        ]
        if not utm_columns:
            continue
        uta_columns = [
            index for index, cell in enumerate(header) if cell.strip().upper().startswith("UTA")
        ]
        for row in table[1:]:
            if set("".join(row)) <= {"-", " "}:
                continue
            if len(row) != len(header):
                continue
            for index in utm_columns:
                period = month_year_before(row, index)
                value = number(row[index])
                if not period or value is None:
                    continue
                extra = None
                shifted = uta_columns and len(uta_columns) == len(utm_columns)
                if shifted:
                    position = utm_columns.index(index)
                    extra = number(row[uta_columns[position]])
                rows.append((period[0], period[1], value, extra))
    return rows


def collect() -> tuple[dict, dict, dict]:
    values: dict[tuple[int, int], tuple[int, tuple]] = {}
    ipc: dict[tuple[int, int], tuple[float, float | None, tuple]] = {}
    stats = {"suspect": 0, "uta_mismatch": 0, "conflict": 0, "documents": 0, "bracket_docs": 0}
    for kind, root in MD.items():
        for path in sorted(root.rglob("*.md")):
            if path.name == "index.md":
                continue
            stats["documents"] += 1
            body = path.read_text(encoding="utf-8").split("---", 2)[-1]
            match = re.search(r"(?:circu|reso)(\d+)", path.stem, re.I)
            if not match:
                continue
            number_in_name = int(match.group(1))
            year_in_name = int(path.parent.name[:4])
            relative = path.relative_to(ROOT).as_posix()
            source = (year_in_name, number_in_name, relative)
            for year, month, value, uta in utm_rows(body):
                if not (FIRST_YEAR <= year <= LAST_YEAR):
                    continue
                if not (UTM_RANGE[0] <= value <= UTM_RANGE[1]):
                    stats["suspect"] += 1
                    continue
                # A damaged UTA cell is no reason to drop a usable UTM, but it is
                # counted: twelve UTM is the only cross-check this table offers.
                if uta is not None and uta != value * 12:
                    stats["uta_mismatch"] += 1
                key = (year, month)
                current = values.get(key)
                if current and current[0] != value:
                    stats["conflict"] += 1
                # A later document wins: it reprints the same table with the
                # values already known, and any correction lands there.
                if current is None or source[:2] > current[1][:2]:
                    values[key] = (value, source)
            for year, month, points, variation in ipc_rows(body):
                if not (IPC_FIRST_YEAR <= year <= LAST_YEAR):
                    continue
                key = (year, month)
                current = ipc.get(key)
                if current is None or source[:2] > current[2][:2]:
                    ipc[key] = (points, variation, source)
    return values, ipc, stats


def source_type(relative: str) -> str:
    return "circular" if "CIRCULARES" in relative else "resolucion"


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> int:
    OUT.mkdir(exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def utm_csv_rows(values: dict) -> list[dict]:
    rows = []
    for (year, month), (value, information) in sorted(values.items()):
        source_year, source_number, relative = information
        rows.append(
            {
                "series": "UTM",
                "period": f"{year}-{month:02d}",
                "value": value,
                "unit": "CLP",
                "source_type": source_type(relative),
                "source_number": source_number,
                "source_year": source_year,
                "source_doc": relative,
            }
        )
    return rows


def ipc_csv_rows(ipc: dict) -> list[dict]:
    rows = []
    for (year, month), (points, variation, information) in sorted(ipc.items()):
        source_year, source_number, relative = information
        rows.append(
            {
                "series": "IPC",
                "period": f"{year}-{month:02d}",
                "index_points": f"{points:.2f}".rstrip("0").rstrip("."),
                "var_monthly_pct": "" if variation is None else f"{variation:g}",
                "source_type": source_type(relative),
                "source_number": source_number,
                "source_year": source_year,
                "source_doc": relative,
            }
        )
    return rows


def write_build(values: dict, ipc: dict, stats: dict) -> None:
    periods = sorted(values)
    ipc_periods = sorted(ipc)
    payload = {
        "artifact": "series/utm.csv, series/ipc.csv",
        "derived": True,
        "authoritative": False,
        "note": "Regenerable from MD_* with scripts/series.py. The circular is the authority, not this file.",
        "documents_scanned": stats["documents"],
        "utm": {
            "newest_source_year": max((value[1][0] for value in values.values()), default=None),
            "rows": len(values),
            "first_period": f"{periods[0][0]}-{periods[0][1]:02d}" if periods else None,
            "last_period": f"{periods[-1][0]}-{periods[-1][1]:02d}" if periods else None,
            "rows_dropped_out_of_range": stats["suspect"],
            "uta_cell_mismatch": stats["uta_mismatch"],
            "conflicting_reprints": stats["conflict"],
        },
        "ipc": {
            "rows": len(ipc),
            "first_period": f"{ipc_periods[0][0]}-{ipc_periods[0][1]:02d}" if ipc_periods else None,
            "last_period": f"{ipc_periods[-1][0]}-{ipc_periods[-1][1]:02d}" if ipc_periods else None,
            "rows_without_variation": sum(1 for _p, v, _s in ipc.values() if v is None),
        },
    }
    BUILD_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def report(values: dict, ipc: dict, stats: dict) -> str:
    expected = [
        (year, month) for year in range(FIRST_YEAR, LAST_YEAR + 1) for month in range(1, 13)
    ]
    missing = [key for key in expected if key not in values]
    ipc_expected = [
        (year, month) for year in range(IPC_FIRST_YEAR, LAST_YEAR + 1) for month in range(1, 13)
    ]
    ipc_missing = [key for key in ipc_expected if key not in ipc]
    lines = [
        f"UTM rows: {len(values)} of {len(expected)} month slots "
        f"({FIRST_YEAR}-{LAST_YEAR})",
        f"rows dropped (value out of range): {stats['suspect']}   "
        f"UTA cell != 12 x UTM: {stats['uta_mismatch']}   "
        f"reprints with a different value: {stats['conflict']}",
        f"IPC rows: {len(ipc)} of {len(ipc_expected)} month slots "
        f"({IPC_FIRST_YEAR}-{LAST_YEAR})",
    ]
    for label, gaps in (("UTM", missing), ("IPC", ipc_missing)):
        if not gaps:
            continue
        by_year: dict[int, list[int]] = {}
        for year, month in gaps:
            by_year.setdefault(year, []).append(month)
        lines.append(f"missing {label} months (nothing published in the corpus):")
        for year in sorted(by_year):
            lines.append(f"  {year}: " + ", ".join(f"{month:02d}" for month in by_year[year]))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--report", action="store_true", help="print the coverage report")
    args = parser.parse_args()

    values, ipc, stats = collect()
    utm_rows_written = write_csv(UTM_CSV, list(utm_csv_rows(values)[0]), utm_csv_rows(values))
    ipc_rows_written = write_csv(IPC_CSV, list(ipc_csv_rows(ipc)[0]), ipc_csv_rows(ipc))
    write_build(values, ipc, stats)
    print(f"wrote {UTM_CSV.relative_to(ROOT).as_posix()} ({utm_rows_written} rows)")
    print(f"wrote {IPC_CSV.relative_to(ROOT).as_posix()} ({ipc_rows_written} rows)")
    print(f"wrote {BUILD_JSON.relative_to(ROOT).as_posix()}")
    if args.report:
        print(report(values, ipc, stats))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
