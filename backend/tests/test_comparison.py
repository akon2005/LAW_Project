"""Two-scenario comparison tests (Phase 6 / Phase 11).

Retrieval is stubbed so the comparison *logic* is tested deterministically and
without loading the embedding model:

* chunks of one judgment are grouped into a single precedent;
* supporting/contrary evidence is split per account;
* the outcome estimate is honestly unavailable (no trained model);
* every citation carries a real stored chunk id;
* request validation rejects malformed input.

The API-level tests only assert validation/error handling and never require an
external service.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

import app.services.comparison_service as comparison_module
from app.main import app
from app.services.comparison_service import comparison_service

client = TestClient(app, raise_server_exceptions=False)


def _record(document_id, chunk_id, text, similarity, **meta):
    return {
        "document_id": document_id,
        "chunk_id": chunk_id,
        "text": text,
        "similarity_score": similarity,
        "case_name": meta.get("case_name", f"Case {document_id}"),
        "court": meta.get("court", "Supreme Court of India"),
        "year": meta.get("year", 1970),
        "sections": meta.get("sections", []),
        "articles": meta.get("articles", []),
        "source": "doc.pdf",
        "judgment_date": "1970-01-01",
        "citation": "",
        "source_url": "",
        "rerank_method": "dense",
    }


# Two chunks from doc "d1" (one judgment), plus d2 and d3.
_A_TEXT = "accused attacked deceased with weapon property dispute intent to kill murder"
_B_TEXT = "deceased attacked accused first minimum force private defence self defence"
_D2_TEXT = "evidence witness testimony trial procedure record findings"


def _stub_retrieve(query, top_k=5, filters=None, sections=None, use_reranker=None):
    if _B_TEXT in query:
        results = [
            _record("d3", "d3_1", _B_TEXT, 0.62, case_name="B Case"),
            _record("d2", "d2_1", _D2_TEXT, 0.40, case_name="Neutral Case"),
        ]
    else:
        results = [
            _record("d1", "d1_1", _A_TEXT, 0.66, case_name="A Case"),
            _record("d1", "d1_2", _A_TEXT + " more reasoning", 0.55, case_name="A Case"),
            _record("d2", "d2_1", _D2_TEXT, 0.38, case_name="Neutral Case"),
        ]
    return {
        "results": results,
        "best_similarity": max(r["similarity_score"] for r in results),
        "is_low_confidence": False,
        "low_confidence_reason": None,
        "candidate_count": len(results),
        "reranked": False,
    }


REQUEST = {
    "legal_issue": "Whether the accused acted in private defence in a murder charge",
    "case_facts": "A property quarrel led to a fight in which one person died.",
    "provisions": ["IPC Section 302"],
    "scenario_a": {"label": "Party A", "position": _A_TEXT},
    "scenario_b": {"label": "Party B", "position": _B_TEXT},
    "top_k": 5,
}


class ComparisonLogicTests(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(
            comparison_module.retrieval_service, "retrieve", side_effect=_stub_retrieve
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_chunks_of_one_judgment_are_one_precedent(self):
        result = comparison_service.compare(REQUEST)
        ids = [p["document_id"] for p in result["precedents"]]
        # d1 has two chunks but must appear once.
        self.assertEqual(ids.count("d1"), 1)
        d1 = next(p for p in result["precedents"] if p["document_id"] == "d1")
        self.assertEqual(d1["matched_chunks"], 2)

    def test_both_scenarios_get_supporting_evidence(self):
        result = comparison_service.compare(REQUEST)
        self.assertGreaterEqual(result["scenario_a"]["supporting_count"], 1)
        self.assertGreaterEqual(result["scenario_b"]["supporting_count"], 1)

    def test_outcome_prediction_when_trained(self):
        result = comparison_service.compare(REQUEST)
        outcome = result["outcome_prediction"]
        self.assertTrue(outcome["available"])
        self.assertEqual(outcome["status"], "EXPERIMENTAL_PREDICTION")
        self.assertIn("scenario_a", outcome["per_scenario"])
        self.assertIn("scenario_b", outcome["per_scenario"])
        for sc in ("scenario_a", "scenario_b"):
            pred = outcome["per_scenario"][sc]
            self.assertIn(pred["label"], ["convicted", "acquitted"])
            self.assertGreaterEqual(pred["confidence"], 0.0)
            self.assertLessEqual(pred["confidence"], 1.0)

    def test_outcome_prediction_honestly_unavailable_when_untrained(self):
        with patch.object(comparison_module.outcome_model_service, "status", return_value={"available": False, "reason": "No model trained"}):
            result = comparison_service.compare(REQUEST)
            outcome = result["outcome_prediction"]
            self.assertFalse(outcome["available"])
            self.assertIsNone(outcome["predicted_class"])
            self.assertIsNone(outcome["calibrated_probability"])
            self.assertIsNotNone(outcome["reason"])
            self.assertEqual(outcome["status"], "PREDICTION_NOT_AVAILABLE")

    def test_citations_are_verified_and_carry_real_chunk_ids(self):
        result = comparison_service.compare(REQUEST)
        self.assertTrue(result["citations"])
        for citation in result["citations"]:
            self.assertTrue(citation["verified"])
            self.assertTrue(citation["chunk_id"])

    def test_evidence_quality_and_limitations_present(self):
        result = comparison_service.compare(REQUEST)
        self.assertIn(
            result["evidence_quality"]["status"],
            {"SUFFICIENT_EVIDENCE_FOR_ANALYSIS", "LIMITED_EVIDENCE", "INSUFFICIENT_EVIDENCE"},
        )
        self.assertTrue(result["limitations"])
        self.assertIn("disclaimer", result)

    def test_insufficient_evidence_when_nothing_retrieved(self):
        with patch(
            "app.services.comparison_service.retrieval_service.retrieve",
            return_value={
                "results": [],
                "best_similarity": 0.05,
                "is_low_confidence": True,
                "low_confidence_reason": "below threshold",
                "candidate_count": 0,
            },
        ):
            result = comparison_service.compare(REQUEST)
        self.assertEqual(result["evidence_quality"]["status"], "INSUFFICIENT_EVIDENCE")
        self.assertEqual(result["scenario_a"]["supporting_count"], 0)

    def test_single_scenario_mode(self):
        single_req = {
            "legal_issue": "Whether the accused acted in private defence",
            "scenario_a": {"label": "Party A", "position": _A_TEXT},
        }
        result = comparison_service.compare(single_req)
        self.assertEqual(result["mode"], "single_scenario")
        self.assertIsNotNone(result["scenario_a"])
        self.assertIsNone(result["scenario_b"])
        self.assertIn("comparative_analysis", result)
        self.assertTrue(result["comparative_analysis"]["executive_summary"])


class ComparisonApiValidationTests(unittest.TestCase):
    def test_missing_scenarios_rejected(self):
        response = client.post("/api/comparison", json={"legal_issue": "valid issue text"})
        self.assertEqual(response.status_code, 422)

    def test_short_issue_rejected(self):
        payload = {**REQUEST, "legal_issue": "x"}
        self.assertEqual(client.post("/api/comparison", json=payload).status_code, 422)

    def test_bad_top_k_rejected(self):
        payload = {**REQUEST, "top_k": 999}
        self.assertEqual(client.post("/api/comparison", json=payload).status_code, 422)

    def test_oversized_position_rejected(self):
        payload = {**REQUEST, "scenario_a": {"label": "A", "position": "a" * 7000}}
        self.assertEqual(client.post("/api/comparison", json=payload).status_code, 422)


if __name__ == "__main__":
    unittest.main()
