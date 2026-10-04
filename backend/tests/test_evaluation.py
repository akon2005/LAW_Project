"""Unit tests for the evaluation harness (Steps 39, 40)."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation.gold_set import GoldQuery, load_gold_set, summarize_gold_set
from evaluation.metrics import (
    evaluate_citations,
    evaluate_retrieval,
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank,
)


class RetrievalMetricTests(unittest.TestCase):
    def test_recall_at_k(self):
        retrieved = ["a", "b", "c", "d"]
        relevant = {"b", "d", "z"}
        self.assertAlmostEqual(recall_at_k(retrieved, relevant, 2), 1 / 3)
        self.assertAlmostEqual(recall_at_k(retrieved, relevant, 4), 2 / 3)

    def test_recall_without_labels(self):
        self.assertEqual(recall_at_k(["a"], set(), 5), 0.0)

    def test_reciprocal_rank(self):
        self.assertEqual(reciprocal_rank(["x", "y", "z"], {"y"}), 0.5)
        self.assertEqual(reciprocal_rank(["x", "y"], {"q"}), 0.0)

    def test_ndcg_perfect_ranking(self):
        self.assertAlmostEqual(ndcg_at_k(["a", "b"], {"a", "b"}, 2), 1.0)

    def test_ndcg_bad_ranking(self):
        self.assertLess(ndcg_at_k(["x", "a"], {"a"}, 2), 1.0)

    def test_evaluate_retrieval_without_labels_is_unavailable(self):
        report = evaluate_retrieval([{"retrieved": ["a"], "relevant": []}])
        self.assertFalse(report["available"])
        self.assertEqual(report["unlabeled_cases"], 1)

    def test_evaluate_retrieval_with_labels(self):
        cases = [
            {"retrieved": ["a", "b", "c"], "relevant": ["a"]},
            {"retrieved": ["d", "e", "f"], "relevant": ["e"]},
        ]
        report = evaluate_retrieval(cases, k_values=(1, 3))
        self.assertTrue(report["available"])
        self.assertEqual(report["labeled_cases"], 2)
        self.assertAlmostEqual(report["metrics"]["recall@1"], 0.5)
        # First relevant result is at rank 1 then rank 2 → mean 0.75.
        self.assertAlmostEqual(report["metrics"]["mrr"], 0.75)


class CitationMetricTests(unittest.TestCase):
    def test_citation_metrics(self):
        answers = [
            {"citations": [{"verified": True}, {"verified": True}], "unverified_references": []},
            {"citations": [{"verified": True}], "unverified_references": [{"reference": "[9]"}]},
        ]
        report = evaluate_citations(answers)
        self.assertEqual(report["total_citations"], 3)
        self.assertEqual(report["verified_citations"], 3)
        self.assertEqual(report["unsupported_citations"], 1)
        self.assertAlmostEqual(report["citation_coverage"], 1.0)
        self.assertGreater(report["unsupported_citation_rate"], 0.0)


class GoldSetTests(unittest.TestCase):
    def test_loader_and_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gold.jsonl"
            path.write_text(
                '{"query": "q1", "expected_documents": ["1_0"], "expected_sections": [], '
                '"family": "chunk_self_retrieval", "notes": ""}\n'
                '{"query": "q2", "expected_documents": [], "expected_sections": [], "notes": "placeholder"}\n'
                'not json\n',
                encoding="utf-8",
            )
            entries = load_gold_set(path)
            self.assertEqual(len(entries), 2)
            self.assertTrue(entries[0].validated)
            self.assertEqual(entries[0].family, "chunk_self_retrieval")
            self.assertFalse(entries[1].validated)
            self.assertEqual(entries[1].family, "")
            summary = summarize_gold_set(entries)
            self.assertEqual(summary, {"total": 2, "validated": 1, "placeholders": 1})

    def test_missing_file_returns_empty(self):
        self.assertEqual(load_gold_set(Path("does/not/exist.jsonl")), [])

    def test_gold_query_defaults(self):
        entry = GoldQuery(query="q")
        self.assertEqual(entry.expected_documents, [])
        self.assertFalse(entry.validated)


if __name__ == "__main__":
    unittest.main()
