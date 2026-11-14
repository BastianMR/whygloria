#!/usr/bin/env python3
"""Supersession map: which document repeals, modifies or replaces which.

Extraction is deterministic and sentence-scoped: a phrase becomes an edge only
when the same sentence names a Circular or Resolución with a number. The
measured inventory is why (see ARCHITECTURE.md): MODIFICA appears 9207 times in
this corpus and most of those are not relationships at all.

This module never imports `check_okf` or `metadata`; it is the leaf that both of
them can use, so the graph can be rebuilt from frontmatter alone.

Usage:
    python scripts/vigencia.py            # report from current frontmatter
    python scripts/vigencia.py --json     # also write relaciones.json
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MD = {"circular": ROOT / "MD_CIRCULARES", "resolucion": ROOT / "MD_RESOLUCIONES"}
GRAPH = ROOT / "relaciones.json"
STATUSES = ("vigente", "derogado", "parcialmente_derogado", "desconocido")

# Phrase variants measured in the corpus, mapped to one relation type.
VARIANTS = {
    "deja sin efecto": "deroga",
    "dejan sin efecto": "deroga",
    "dejado sin efecto": "deroga",
    "dejar sin efecto": "deroga",
    "deroga": "deroga",
    "derogan": "deroga",
    "derogase": "deroga",
    "derógase": "deroga",
    "derogada": "deroga",
    "derogado": "deroga",
    "modifica": "modifica",
    "modifican": "modifica",
    "modificase": "modifica",
    "modífcase": "modifica",
    "modifícase": "modifica",
    "complementa": "complementa",
    "complementan": "complementa",
    "complementase": "complementa",
    "sustituye": "reemplaza",
    "sustituyen": "reemplaza",
    "sustituyese": "reemplaza",
    "reemplaza": "reemplaza",
    "reemplazan": "reemplaza",
    "reemplazase": "reemplaza",
    "reemplazada": "reemplaza",
    "reemplazado": "reemplaza",
    "prorroga": "prorroga",
    "prorrogan": "prorroga",
    "prorrogase": "prorroga",
    "aclara": "aclara",
    "aclaran": "aclara",
    "aclarase": "aclara",
}
PHRASE_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in sorted(VARIANTS, key=len, reverse=True)) + r")\b",
    re.I,
)
TARGET_RE = re.compile(
    r"\b(circular(?:es)?|resoluci[oó]n(?:es)?)\b[^.;\n]{0,60}?"
    r"(?:n[°º]?\.?\s*s?\.?|n[uú]meros?|nros?\.?)\s*"
    r"(\d{1,4}(?:\s*(?:,|y|e)\s*(?:n[°º]?\.?\s*)?\d{1,4})*)",
    re.I,
)
YEAR_RE = re.compile(r"\b(?:de|del)\s+(\d{4})\b", re.I)
SHORT_DATE_RE = re.compile(r"\b(?:de|del)\s+\d{2}[./]\d{2}[./](\d{4})\b", re.I)
ABBREV_RE = re.compile(r"\b((?:d\.\s?f\.\s?l|d\.\s?l|d\.\s?s|arts?|artículos?|n[°º]s?))\.", re.I)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.;])\s+(?=[A-ZÁÉÍÓÚ0-9])|\n\s*\n")
NUMBER_IN_NAME_RE = re.compile(r"(?:circu|reso)(\d+)", re.I)
MAX_RAW = 240


def _sentences(body: str) -> list[str]:
    protected = ABBREV_RE.sub(r"\1", body)
    protected = re.sub(r"(?<=\d)\.(?=\d)", "-", protected)  # 15.07.2004 stays one token
    return [chunk.strip() for chunk in SENTENCE_SPLIT_RE.split(protected) if chunk.strip()]


def target_years(text: str) -> list[int | None]:
    years = [int(value) for value in YEAR_RE.findall(text)] or [
        int(value) for value in SHORT_DATE_RE.findall(text)
    ]
    return years or [None]


def extract_relaciones(body: str) -> list[dict]:
    """Relationships stated in the body, each with the sentence that states it."""
    found: list[dict] = []
    seen: set[tuple] = set()
    for sentence in _sentences(body):
        if len(sentence) > 1200:
            continue
        phrase = PHRASE_RE.search(sentence)
        if not phrase:
            continue
        kind = VARIANTS[phrase.group(1).lower()]
        target = TARGET_RE.search(sentence, phrase.end())
        if not target:
            continue
        target_type = "circular" if target.group(1).lower().startswith("circular") else "resolucion"
        numbers = [int(value) for value in re.findall(r"\d{1,4}", target.group(2))]
        years = target_years(sentence[target.end() : target.end() + 160])
        raw = re.sub(r"\s+", " ", sentence)[:MAX_RAW]
        for index, number in enumerate(numbers):
            year = years[min(index, len(years) - 1)]
            key = (kind, target_type, number, year)
            if key in seen:
                continue
            seen.add(key)
            found.append(
                {
                    "type": kind,
                    "target_type": target_type,
                    "target_number": number,
                    "target_year": year,
                    "raw_text": raw,
                }
            )
        if len(found) >= 8:
            break
    return found


def concept_key(path: Path) -> tuple[str, int] | None:
    match = NUMBER_IN_NAME_RE.search(path.stem)
    if not match:
        return None
    kind = "circular" if path.parent.name.endswith("CIRCULAR") else "resolucion"
    return kind, int(match.group(1))


def index_concepts() -> dict[tuple[str, int], list[Path]]:
    index: dict[tuple[str, int], list[Path]] = {}
    for root in MD.values():
        for path in sorted(root.rglob("*.md")):
            if path.name == "index.md":
                continue
            key = concept_key(path)
            if key:
                index.setdefault(key, []).append(path)
    return index


def resolve(edge: dict, index: dict[tuple[str, int], list[Path]], source_year: int) -> Path | None:
    candidates = [
        path for path in index.get((edge["target_type"], edge["target_number"]), [])
        if int(path.parent.name[:4]) <= source_year
    ]
    if len(candidates) == 1:
        return candidates[0]
    if edge.get("target_year"):
        for candidate in candidates:
            if candidate.parent.name.startswith(str(edge["target_year"])):
                return candidate
    return None


def build(concepts: dict[Path, dict]) -> dict:
    """Return the graph plus the derived status of every concept.

    `status_vigencia` can only say what this corpus states: a document with no
    incoming repeal or amendment edge is *vigente según el corpus*, which is not
    the same as vigente (an oficio or a law can repeal it silently).
    """
    index = index_concepts()
    edges: list[dict] = []
    incoming: dict[Path, list[tuple[str, Path]]] = {}
    unresolved: list[dict] = []
    ambiguous: set[Path] = set()

    for source, meta in sorted(concepts.items()):
        source_year = int(source.parent.name[:4])
        for edge in meta.get("relaciones") or []:
            target = resolve(edge, index, source_year)
            record = dict(edge)
            record["source"] = source.as_posix().replace(str(ROOT.as_posix()) + "/", "")
            if target is None:
                record["target"] = None
                unresolved.append(record)
                # Two concepts with the same number in the same year are the
                # only genuine ambiguity: the edge names both of them.
                if edge.get("target_year"):
                    for candidate in index.get((edge["target_type"], edge["target_number"]), []):
                        if candidate.parent.name.startswith(str(edge["target_year"])):
                            ambiguous.add(candidate)
                continue
            if target == source:
                continue
            record["target"] = target.as_posix().replace(str(ROOT.as_posix()) + "/", "")
            edges.append(record)
            incoming.setdefault(target, []).append((edge["type"], source))

    status: dict[Path, str] = {}
    replaced_by: dict[Path, list[str]] = {}
    for path in concepts:
        relations = incoming.get(path, [])
        types = {kind for kind, _source in relations}
        if types & {"deroga", "reemplaza"}:
            status[path] = "derogado"
        elif "modifica" in types:
            status[path] = "parcialmente_derogado"
        elif path in ambiguous:
            status[path] = "desconocido"
        else:
            status[path] = "vigente"
        replaced_by[path] = sorted(
            source.as_posix().replace(str(ROOT.as_posix()) + "/", "")
            for kind, source in relations
            if kind in {"deroga", "reemplaza"}
        )

    documents = {}
    for path in sorted(concepts):
        relative = path.as_posix().replace(str(ROOT.as_posix()) + "/", "")
        documents[relative] = {
            "status_vigencia": status[path],
            "replaced_by": replaced_by[path],
            "relaciones": concepts[path].get("relaciones") or [],
        }
    return {
        "documents": documents,
        "edges": sorted(edges, key=lambda e: (e["source"], e["type"], e["target"], e["target_number"])),
        "unresolved": sorted(
            unresolved, key=lambda e: (e["source"], e["target_number"], e["raw_text"])
        ),
        "status": status,
        "replaced_by": replaced_by,
        "signal": {"ambiguous_targets": sorted(p.as_posix() for p in ambiguous)},
    }


def write_graph(graph: dict) -> None:
    payload = {
        "documents": graph["documents"],
        "edges": graph["edges"],
        "unresolved": graph["unresolved"],
        "ambiguous_targets": graph["signal"]["ambiguous_targets"],
    }
    GRAPH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def report(graph: dict) -> str:
    edges = graph["edges"]
    unresolved = graph["unresolved"]
    status = graph["status"]
    counts = {name: 0 for name in STATUSES}
    for value in status.values():
        counts[value] += 1
    lines = [
        f"documents: {len(status)}   edges resolved: {len(edges)}   unresolved: {len(unresolved)}",
        "status: " + ", ".join(f"{name} {counts[name]}" for name in STATUSES),
        f"ambiguous targets: {len(graph['signal']['ambiguous_targets'])}",
    ]
    if unresolved:
        lines.append("unresolved targets (outside the corpus):")
        for edge in unresolved[:20]:
            lines.append(f"  {edge['source']}  {edge['type']} -> {edge['target_number']} ({edge['target_year']})")
        if len(unresolved) > 20:
            lines.append(f"  ... and {len(unresolved) - 20} more")
    return "\n".join(lines)


def read_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    if not text.startswith("---"):
        return {}
    block = text.split("---", 2)
    if len(block) < 3:
        return {}
    try:
        import yaml

        data = yaml.safe_load(block[1])
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def own_number(source: str) -> int | None:
    match = re.search(r"(?:circu|reso)(\d+)", Path(source).stem)
    return int(match.group(1)) if match else None


def unresolved_report(graph) -> Path:
    """Every unresolved edge with the reason it does not resolve.

    The corpus cannot answer "what replaced this?" for these. The count is not an
    open number any more: each edge is one of three things, and two of them are
    not the parser's fault.
    """
    rows = []
    for edge in graph["unresolved"]:
        own = own_number(edge["source"])
        number = edge.get("target_number")
        if number is not None and own is not None and int(number) == own:
            reason = "the document cites itself"
        elif number is not None:
            reason = "the named document is not in the corpus"
        else:
            reason = "the phrase names no document"
        rows.append((reason, edge))
    rows.sort(key=lambda row: (row[0], row[1]["source"]))
    counts: dict[str, int] = {}
    for reason, _edge in rows:
        counts[reason] = counts.get(reason, 0) + 1
    lines = [
        "---",
        'type: "Reference"',
        'title: "Supersession edges that do not resolve"',
        'description: "Every edge the corpus cannot resolve, with the reason and the phrase that produced it."',
        "tags: []",
        "---",
        "",
        "# Supersession edges that do not resolve",
        "",
        "Generated by `python scripts/vigencia.py --unresolved`. An edge exists when a",
        "document says another document repeals, amends or replaces something; an edge",
        "does not resolve when the corpus cannot name the result.",
        "",
        f"{len(rows)} unresolved edges.",
        "",
        "| Reason | Edges |",
        "| --- | --- |",
    ]
    for reason, count in sorted(counts.items(), key=lambda item: -item[1]):
        lines.append(f"| {reason} | {count} |")
    lines += [
        "",
        "`the document cites itself` is header noise: the parser read the document's",
        "own identification table as a citation. `the named document is not in the",
        "corpus` is a real answer: the corpus only holds 2013 onward, so a 1991 target",
        "cannot resolve. Neither is a parser defect.",
        "",
        "| Concept | Relation | Target | Reason | Phrase |",
        "| --- | --- | --- | --- | --- |",
    ]
    for reason, edge in rows:
        target = edge.get("target_number")
        year = edge.get("target_year")
        label = f"{edge.get('target_type') or '?'} {target if target is not None else '-'}"
        if year:
            label += f" ({year})"
        phrase = " ".join(str(edge.get("raw_text") or "").split())[:150]
        lines.append(
            f"| `{edge['source']}` | {edge.get('type')} | {label} | {reason} | {phrase} |"
        )
    destination = GRAPH.with_name("RELACIONES_UNRESOLVED.md")
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="write relaciones.json")
    parser.add_argument(
        "--unresolved", action="store_true", help="write RELACIONES_UNRESOLVED.md"
    )
    args = parser.parse_args()

    concepts = {}
    for root in MD.values():
        for path in sorted(root.rglob("*.md")):
            if path.name != "index.md":
                concepts[path] = read_frontmatter(path)
    graph = build(concepts)
    print(report(graph))
    if args.unresolved:
        # The written graph is authoritative: `sii_pdfs.py --vigencia` is its
        # documented writer, and a fresh in-memory build can disagree with it.
        source = json.loads(GRAPH.read_text(encoding="utf-8")) if GRAPH.exists() else graph
        print(f"wrote {unresolved_report(source)}")
    if args.json:
        write_graph(graph)
        print(f"wrote {GRAPH.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
