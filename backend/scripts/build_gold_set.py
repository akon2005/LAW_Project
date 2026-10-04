#!/usr/bin/env python
"""
Derived gold-set builder (Step 40).

    python scripts/build_gold_set.py --documents 10 --chunks 10
    python scripts/build_gold_set.py --out evaluation/gold_queries.jsonl

Builds a reproducible retrieval evaluation set from the corpus's OWN stored
metadata. This is **machine-derived, not human-validated** legal relevance:

* ``family = source_document``      — the query names a real judgment (case name
  + year) and the relevant ids are *every* stored chunk of that source PDF.
* ``family = chunk_self_retrieval`` — the query is a real snippet of a chunk and
  the relevant id is that exact chunk.

Both definitions are objective and reproducible (relevance comes from
provenance, not opinion). Each entry's ``notes`` field records the derivation.
Legal relevance still requires human review before it can be called ground
truth.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.vector_store import legal_cases_store  # noqa: E402

_READ_BATCH = 2000
_JUDIS = re.compile(r"https?://JUDIS\.NIC\.IN", re.IGNORECASE)
_PAGE = re.compile(r"page\s+\d+\s+of\s+\d+", re.IGNORECASE)
_WORD = re.compile(r"[A-Za-z][A-Za-z'\-]+")


def read_rows() -> List[Dict[str, Any]]:
    """Read ids, metadata and text for every stored chunk (batched)."""
    total = legal_cases_store.get_count()
    rows: List[Dict[str, Any]] = []
    for offset in range(0, total, _READ_BATCH):
        page = legal_cases_store.collection.get(
            include=["metadatas", "documents"], limit=_READ_BATCH, offset=offset
        )
        ids = page.get("ids") or []
        metadatas = page.get("metadatas") or []
        documents = page.get("documents") or []
        for index, chunk_id in enumerate(ids):
            rows.append(
                {
                    "chunk_id": chunk_id,
                    "metadata": metadatas[index] if index < len(metadatas) else {},
                    "text": documents[index] if index < len(documents) else "",
                }
            )
    return rows


def make_query(text: str, words: int = 22, start: int = 25) -> Optional[str]:
    """Extract a distinctive real snippet from a chunk, or None if too short."""
    clean = _PAGE.sub(" ", _JUDIS.sub(" ", text or ""))
    tokens = _WORD.findall(clean)
    if len(tokens) < 12:
        return None
    window = tokens[start : start + words]
    if len(window) < 10:
        window = tokens[:words]
    return " ".join(window)


def build(documents: int, chunks: int, seed: int) -> List[Dict[str, Any]]:
    rows = read_rows()
    if not rows:
        return []

    rng = random.Random(seed)
    entries: List[Dict[str, Any]] = []

    # ── Family A: source-document retrieval ────────────────────────────
    by_source: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        source = (row["metadata"] or {}).get("source") or (row["metadata"] or {}).get("document_key")
        if source:
            by_source[str(source)].append(row)

    sources = sorted(by_source)
    picked_sources = rng.sample(sources, min(documents, len(sources))) if sources else []
    for source in picked_sources:
        group = by_source[source]
        names = Counter(m["metadata"].get("case_name") for m in group if m["metadata"].get("case_name"))
        if not names:
            continue
        case_name = names.most_common(1)[0][0]
        years = Counter(m["metadata"].get("year") for m in group if m["metadata"].get("year"))
        year = years.most_common(1)[0][0] if years else ""
        query = f"{case_name} {year}".strip()
        expected = sorted({m["chunk_id"] for m in group})
        entries.append(
            {
                "query": query,
                "expected_documents": expected,
                "expected_sections": [],
                "family": "source_document",
                "notes": (
                    f"MACHINE-DERIVED (not human-validated). Relevant = all {len(expected)} chunks "
                    f"of source PDF {source}; query is that judgment's case name and year."
                ),
            }
        )

    # ── Family B: chunk self-retrieval ─────────────────────────────────
    candidates = []
    for row in rows:
        snippet = make_query(row["text"])
        if snippet:
            candidates.append((row, snippet))
    picked_chunks = rng.sample(candidates, min(chunks, len(candidates))) if candidates else []
    for row, snippet in picked_chunks:
        metadata = row["metadata"] or {}
        sections = [s.strip() for s in str(metadata.get("sections", "")).split(",") if s.strip()]
        entries.append(
            {
                "query": snippet,
                "expected_documents": [row["chunk_id"]],
                "expected_sections": sections[:3],
                "family": "chunk_self_retrieval",
                "notes": (
                    "MACHINE-DERIVED (not human-validated). Relevant = the single chunk the query "
                    f"text was drawn from (chunk {row['chunk_id']})."
                ),
            }
        )

    return entries


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a derived gold evaluation set.")
    parser.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "evaluation" / "gold_queries.jsonl"))
    parser.add_argument("--documents", type=int, default=10, help="source-document queries")
    parser.add_argument("--chunks", type=int, default=10, help="chunk self-retrieval queries")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    entries = build(args.documents, args.chunks, args.seed)
    if not entries:
        print("Corpus is empty or unreadable; nothing written.")
        return 1

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    families = Counter(entry["family"] for entry in entries)
    print(f"Wrote {len(entries)} entries to {out}")
    for family, count in families.items():
        print(f"  - {family}: {count}")
    print("NOTE: these labels are machine-derived from corpus provenance, not human-validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
