"""
Evaluation metrics (Step 39).

Pure functions with no third-party dependencies, so they can be unit-tested
directly. Nothing here manufactures results: metrics are only computed when
ground-truth relevance labels are supplied.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Sequence, Set


def recall_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """Fraction of relevant documents found in the top-``k`` retrieved."""
    relevant_set: Set[str] = {str(item) for item in relevant}
    if not relevant_set:
        return 0.0
    top = {str(item) for item in list(retrieved)[:k]}
    return len(top & relevant_set) / len(relevant_set)


def reciprocal_rank(retrieved: Sequence[str], relevant: Iterable[str]) -> float:
    """MRR contribution: 1 / rank of the first relevant result (0 if none)."""
    relevant_set = {str(item) for item in relevant}
    for index, item in enumerate(retrieved, start=1):
        if str(item) in relevant_set:
            return 1.0 / index
    return 0.0


def _dcg(gains: Sequence[float]) -> float:
    return sum(gain / math.log2(index + 2) for index, gain in enumerate(gains))


def ndcg_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """Normalized DCG@k with binary relevance."""
    relevant_set = {str(item) for item in relevant}
    if not relevant_set:
        return 0.0
    gains = [1.0 if str(item) in relevant_set else 0.0 for item in list(retrieved)[:k]]
    ideal = [1.0] * min(len(relevant_set), k)
    ideal_dcg = _dcg(ideal)
    return _dcg(gains) / ideal_dcg if ideal_dcg > 0 else 0.0


def evaluate_retrieval(
    cases: List[Dict[str, Any]], k_values: Sequence[int] = (5, 10, 20)
) -> Dict[str, Any]:
    """
    Aggregate retrieval metrics over gold cases.

    Each case must provide ``retrieved`` (ordered ids/chunk ids) and
    ``relevant`` (gold ids). Cases without ``relevant`` labels are counted as
    unlabeled and excluded from the metric averages.
    """
    labeled = [case for case in cases if case.get("relevant")]
    if not labeled:
        return {
            "available": False,
            "reason": "no ground-truth relevance labels were supplied",
            "labeled_cases": 0,
            "unlabeled_cases": len(cases),
        }

    aggregates: Dict[str, float] = {}
    for k in k_values:
        aggregates[f"recall@{k}"] = round(
            sum(recall_at_k(c["retrieved"], c["relevant"], k) for c in labeled) / len(labeled), 4
        )
    aggregates["mrr"] = round(
        sum(reciprocal_rank(c["retrieved"], c["relevant"]) for c in labeled) / len(labeled), 4
    )
    aggregates["ndcg@10"] = round(
        sum(ndcg_at_k(c["retrieved"], c["relevant"], 10) for c in labeled) / len(labeled), 4
    )
    return {
        "available": True,
        "labeled_cases": len(labeled),
        "unlabeled_cases": len(cases) - len(labeled),
        "metrics": aggregates,
    }


def evaluate_citations(answers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generation metrics from citation verification output (Step 39):
    citation coverage, citation validity and unsupported-citation rate.
    """
    total_citations = 0
    verified = 0
    unsupported = 0
    answers_with_citations = 0

    for answer in answers:
        citations = answer.get("citations", []) or []
        unverified = answer.get("unverified_references", []) or []
        if citations:
            answers_with_citations += 1
        total_citations += len(citations)
        verified += sum(1 for citation in citations if citation.get("verified"))
        unsupported += len(unverified)

    denominator = total_citations + unsupported
    return {
        "answers": len(answers),
        "answers_with_citations": answers_with_citations,
        "citation_coverage": round(answers_with_citations / len(answers), 4) if answers else 0.0,
        "total_citations": total_citations,
        "verified_citations": verified,
        "citation_validity": round(verified / total_citations, 4) if total_citations else 0.0,
        "unsupported_citations": unsupported,
        "unsupported_citation_rate": round(unsupported / denominator, 4) if denominator else 0.0,
    }
