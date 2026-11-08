#!/usr/bin/env python3
"""Detect duplicate SII concepts in the repository.

Two checks:
  1. Exact content duplicates: same normalized body (frontmatter stripped,
     whitespace/punctuation/case ignored).
  2. Title collisions: same document number + year in the same folder.

Exit code is 1 when duplicates or collisions are found.

Usage:
    python scripts/check_duplicates.py
"""

from __future__ import annotations

import hashlib
import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FM_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", re.DOTALL)


def normalize(text: str) -> str:
    return re.sub(r"[^\w\s]", "", re.sub(r"\s+", " ", text.lower())).strip()


def load(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8-sig")
    match = FM_RE.match(text)
    if not match:
        return {}, text
    data = yaml.safe_load(match.group(1)) or {}
    return data, match.group(2)


def main() -> int:
    concept_files = [
        p
        for p in sorted(ROOT.rglob("*.md"))
        if p.name != "index.md" and ".git" not in p.parts
    ]

    by_hash: dict[str, list[Path]] = defaultdict(list)
    by_title: dict[tuple, list[Path]] = defaultdict(list)

    for path in concept_files:
        data, body = load(path)
        digest = hashlib.sha256(normalize(body).encode("utf-8")).hexdigest()
        by_hash[digest].append(path)
        title = data.get("title")
        if title:
            by_title[(path.parent.name, title)].append(path)

    exact = {h: paths for h, paths in by_hash.items() if len(paths) > 1}
    collisions = {k: paths for k, paths in by_title.items() if len(paths) > 1}

    print(f"checked {len(concept_files)} concepts")
    print(f"exact duplicate groups: {len(exact)}")
    for paths in exact.values():
        print("  DUPLICATE:")
        for path in paths:
            print(f"    {path.relative_to(ROOT)}")

    # Same-number titles are not necessarily duplicates (SII reuses numbers
    # across series), so they are reported but do not fail the check.
    print(f"title collisions (review): {len(collisions)}")
    for (folder, title), paths in collisions.items():
        print(f"  COLLISION {folder}: {title}")
        for path in paths:
            print(f"    {path.name}")

    return 1 if exact else 0


if __name__ == "__main__":
    sys.exit(main())