#!/usr/bin/env python
"""
Manual RAG check (Step 38).

    python scripts/test_rag.py
    python scripts/test_rag.py "A person is charged under Section 302 IPC and claims self-defence."

Runs the full research pipeline and prints the grounded answer, verified
citations, structured prediction and limitations.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.api.routes.research import ResearchRequest, _execute_research  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a RAG smoke test.")
    parser.add_argument(
        "query",
        nargs="?",
        default="What are the precedents related to breach of contract?",
    )
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    try:
        response = _execute_research(ResearchRequest(query=args.query, top_k=args.top_k))
    except Exception as exc:
        print(f"Pipeline unavailable: {exc}")
        return 3

    print(f"Query:  {response.query}")
    print(f"Status: {response.status} | answer_origin: {response.answer_origin}")
    print(f"Evidence sufficient: {response.evidence_sufficient}")
    print(f"Retrieval confidence (NOT prediction): {response.confidence}")
    print("-" * 60)
    print("ANSWER")
    print(response.answer or "(no generated answer)")
    print("-" * 60)
    print(f"Verified citations: {len(response.citations)}")
    for citation in response.citations:
        print(f"  - {citation.case_name} (chunk {citation.chunk_id})")
    print(f"Unverified references: {len(response.unverified_references)}")
    print("-" * 60)
    print("PREDICTION")
    print(f"  available: {response.prediction.get('available')}")
    if response.prediction.get("available"):
        print(f"  label: {response.prediction.get('label')} "
              f"({response.prediction.get('confidence')})")
    else:
        print(f"  reason: {response.prediction.get('reason')}")
    print("-" * 60)
    print("LIMITATIONS")
    for limitation in response.limitations:
        print(f"  - {limitation}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
