#!/usr/bin/env python
"""
Manual retrieval check (Step 38).

    python scripts/test_retrieval.py
    python scripts/test_retrieval.py "breach of contract damages" --top-k 5

Runs hybrid retrieval and prints each result with its stored chunk id, so the
result can be re-read straight out of ChromaDB (see /api/research/chunk/{id}).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.vector_store import legal_cases_store  # noqa: E402
from app.rag.query_analyzer import legal_query_analyzer  # noqa: E402
from app.rag.retrieval_service import retrieval_service  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a retrieval smoke test.")
    parser.add_argument("query", nargs="?", default="breach of contract damages")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    try:
        count = legal_cases_store.get_count()
    except Exception as exc:
        print(f"Vector store unavailable: {exc}")
        return 3
    if count == 0:
        print("Corpus is empty. Run `python scripts/ingest.py --sample 1000` first.")
        return 2

    analysis = legal_query_analyzer.analyze(args.query)
    print(f"Query: {args.query!r}")
    print(f"Detected sections: {[r['normalized_text'] for r in analysis['legal_sections']] or '(none)'}")
    print(f"Detected issue:    {analysis['legal_issue'] or '(none)'}")
    print(f"Corpus chunks:     {count}")
    print("-" * 60)

    result = retrieval_service.retrieve(query=analysis["embedding_text"], top_k=args.top_k)
    for index, record in enumerate(result["results"], 1):
        print(f"[{index}] {record.get('case_name') or record.get('source') or '(unnamed)'}")
        print(f"    chunk_id: {record.get('chunk_id')} | similarity: {record.get('similarity_score')}")
        print(f"    court: {record.get('court') or '(unknown)'} | year: {record.get('year') or '(unknown)'}")
        snippet = " ".join((record.get("text") or "").split())[:160]
        print(f"    {snippet}...")
    print("-" * 60)
    print(f"Best similarity: {result.get('best_similarity')} | low_confidence={result.get('is_low_confidence')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
