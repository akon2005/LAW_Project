#!/usr/bin/env python
"""
VIDHIVEDA evaluation (Step 39).

    python scripts/evaluate.py
    python scripts/evaluate.py --rerank
    python scripts/evaluate.py --gold evaluation/gold_queries.jsonl --top-k 20
    python scripts/evaluate.py --json evaluation/last_run.json

Retrieval metrics (Recall@K, MRR, nDCG) are computed only when the gold set
contains relevance ids. Ground-truth ids are used exactly as supplied — the
evaluator never "helpfully" widens the relevant set to whatever was retrieved.
Metrics are reported overall and per gold-set family.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from evaluation.gold_set import DEFAULT_GOLD_PATH, load_gold_set, summarize_gold_set  # noqa: E402
from evaluation.metrics import evaluate_retrieval  # noqa: E402
from app.ml.outcome_model import outcome_model_service  # noqa: E402
from app.rag.query_analyzer import legal_query_analyzer  # noqa: E402
from app.rag.retrieval_service import RetrievalError, retrieval_service  # noqa: E402


def _run_retrieval_for_gold(entries, top_k: int, use_reranker):
    cases = []
    for entry in entries:
        if not entry.expected_documents:
            continue
        try:
            result = retrieval_service.retrieve(
                query=legal_query_analyzer.analyze(entry.query)["embedding_text"],
                top_k=top_k,
                use_reranker=use_reranker,
            )
        except RetrievalError as exc:
            print(f"  ! retrieval failed for {entry.query!r}: {exc}")
            continue
        cases.append(
            {
                "retrieved": [record.get("chunk_id", "") for record in result.get("results", [])],
                "relevant": list(entry.expected_documents),
                "family": entry.family or "unspecified",
            }
        )
    return cases


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the VIDHIVEDA pipeline.")
    parser.add_argument("--gold", default=str(DEFAULT_GOLD_PATH))
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--k", action="append", type=int, dest="k_values")
    parser.add_argument("--rerank", dest="rerank", action="store_true", default=None,
                        help="force reranking on")
    parser.add_argument("--no-rerank", dest="rerank", action="store_false",
                        help="force reranking off")
    parser.add_argument("--json", default=None)
    args = parser.parse_args()

    k_values = tuple(args.k_values) if args.k_values else (5, 10, 20)
    report = {"reranking": args.rerank}

    print("VIDHIVEDA — Evaluation")
    print("-" * 40)

    entries = load_gold_set(Path(args.gold))
    summary = summarize_gold_set(entries)
    print(f"Gold set: {summary['total']} entries "
          f"({summary['validated']} labeled, {summary['placeholders']} unlabeled)")
    print(f"Reranking override: {args.rerank if args.rerank is not None else 'config default (USE_RERANKER)'}")
    report["gold_set"] = summary

    if summary["validated"] == 0:
        print("\nRetrieval metrics: UNAVAILABLE")
        print("  No relevance ids were found. Build a derived set with "
              "`python scripts/build_gold_set.py`, or add human-validated ids by hand.")
        report["retrieval"] = {"available": False, "reason": "no relevance labels"}
    else:
        cases = _run_retrieval_for_gold(entries, top_k=args.top_k, use_reranker=args.rerank)
        overall = evaluate_retrieval(cases, k_values=k_values)
        by_family = defaultdict(list)
        for case in cases:
            by_family[case["family"]].append(case)
        per_family = {
            family: evaluate_retrieval(group, k_values=k_values)
            for family, group in sorted(by_family.items())
        }
        report["retrieval"] = {"overall": overall, "by_family": per_family}

        print("\nRetrieval metrics (overall):")
        print(json.dumps(overall, indent=2))
        print("\nRetrieval metrics by family:")
        for family, value in per_family.items():
            print(f"  {family}: {json.dumps(value.get('metrics') or value)}")

    status = outcome_model_service.status()
    if status.get("available"):
        report["outcome"] = status.get("metrics") or {}
        print("\nOutcome model metrics:")
        print(json.dumps(report["outcome"], indent=2))
    else:
        report["outcome"] = {"available": False, "reason": status.get("reason")}
        print("\nOutcome model metrics: UNAVAILABLE")
        print(f"  {status.get('reason')}")

    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nReport written to {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
