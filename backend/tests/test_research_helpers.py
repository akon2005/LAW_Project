"""Unit tests for the research route helpers (Steps 21, 25, 29)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.routes.research import (
    ResearchRequest,
    SourceResponse,
    _build_filters,
    _build_limitations,
    _build_prediction,
    _legal_provisions,
    _to_source,
)
from app.rag.query_analyzer import legal_query_analyzer


class RequestSchemaTests(unittest.TestCase):
    def test_short_query_rejected(self):
        with self.assertRaises(Exception):
            ResearchRequest(query="x")

    def test_defaults(self):
        request = ResearchRequest(query="a legal question")
        self.assertEqual(request.sections, [])
        self.assertGreaterEqual(request.top_k, 1)


class FilterTests(unittest.TestCase):
    def test_year_range_and_court(self):
        request = ResearchRequest(query="a legal query", court="Supreme Court of India", year_from=2010, year_to=2020)
        filters = _build_filters(request)
        self.assertEqual(filters["court"], "Supreme Court of India")
        self.assertEqual(filters["year_from"], 2010)
        self.assertEqual(filters["year_to"], 2020)

    def test_no_filters(self):
        self.assertIsNone(_build_filters(ResearchRequest(query="a legal query")))


class SourceMappingTests(unittest.TestCase):
    def test_missing_fields_are_empty_not_invented(self):
        source = _to_source({"chunk_id": "5_1", "similarity_score": 0.42})
        self.assertEqual(source.chunk_id, "5_1")
        self.assertEqual(source.case_name, "")
        self.assertEqual(source.court, "")
        self.assertEqual(source.similarity_score, 0.42)
        self.assertTrue(source.verified)


class ProvisionTests(unittest.TestCase):
    def test_query_and_evidence_provisions(self):
        analysis = legal_query_analyzer.analyze("charged under IPC 302")
        sources = [
            SourceResponse(chunk_id="1_0", sections=["Section 302", "Section 34"], articles=["Article 21"])
        ]
        provisions = _legal_provisions(analysis, sources)
        labels = [p["label"] for p in provisions]
        self.assertIn("IPC Section 302", labels)
        self.assertIn("Section 34", labels)
        self.assertIn("Article 21", labels)
        # Query provision is attributed to the query, not to evidence.
        query_provision = next(p for p in provisions if p["label"] == "IPC Section 302")
        self.assertEqual(query_provision["origin"], "query")

    def test_no_provisions_means_no_invention(self):
        analysis = legal_query_analyzer.analyze("tell me about contract law")
        self.assertEqual(_legal_provisions(analysis, []), [])


class PredictionTests(unittest.TestCase):
    def test_prediction_unavailable_without_evidence(self):
        analysis = legal_query_analyzer.analyze("Will the accused be convicted?")
        prediction = _build_prediction(analysis, evidence_sufficient=False)
        self.assertFalse(prediction["available"])
        self.assertIsNone(prediction["label"])
        self.assertIn("Insufficient", prediction["reason"])

    def test_prediction_unavailable_without_model(self):
        analysis = legal_query_analyzer.analyze("Will the accused be convicted?")
        prediction = _build_prediction(analysis, evidence_sufficient=True)
        # No trained model exists in this repository, so it must say so.
        self.assertFalse(prediction["available"])
        self.assertIsNotNone(prediction["reason"])


class LimitationTests(unittest.TestCase):
    def test_law_area_and_no_evidence(self):
        request = ResearchRequest(query="a legal query", law_area="contract")
        analysis = legal_query_analyzer.analyze("IPC 302")
        limitations = _build_limitations(
            request,
            analysis,
            {"is_low_confidence": True},
            {"answer_origin": "none"},
            [],
            False,
            {"available": False, "reason": "model unavailable"},
        )
        joined = " ".join(limitations)
        self.assertIn("law_area", joined)
        self.assertIn("No sufficiently relevant", joined)
        self.assertIn("model unavailable", joined)


if __name__ == "__main__":
    unittest.main()
