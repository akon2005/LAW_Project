"""API tests (Step 45): status, validation, errors, honest prediction."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.main import app

# No ``with`` block: constructing the client without entering the lifespan
# context keeps the tests independent of the embedding model / warm-up.
client = TestClient(app, raise_server_exceptions=False)


class StatusEndpointTests(unittest.TestCase):
    def test_health(self):
        response = client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "healthy")
        self.assertIn("components", body)

    def test_model_status(self):
        response = client.get("/api/model/status")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        # The trained outcome model is committed at backend/data/models/outcome,
        # so the API must report it — with its classes and recorded metrics.
        outcome = body["outcome_model"]
        self.assertTrue(outcome["available"])
        self.assertEqual(sorted(outcome["classes"]), ["acquitted", "convicted"])
        self.assertIn("accuracy", outcome["metrics"])
        self.assertIn("versions", body)
        self.assertIn("embedding_model", body)

    def test_ingestion_status(self):
        response = client.get("/api/ingestion/status")
        self.assertEqual(response.status_code, 200)
        self.assertIn("status", response.json())


class ValidationTests(unittest.TestCase):
    def test_research_rejects_short_query(self):
        response = client.post("/api/research", json={"query": "x"})
        self.assertEqual(response.status_code, 422)

    def test_research_requires_query(self):
        self.assertEqual(client.post("/api/research", json={}).status_code, 422)

    def test_retrieve_rejects_bad_top_k(self):
        response = client.post("/api/retrieve", json={"query": "valid query", "top_k": 999})
        self.assertEqual(response.status_code, 422)

    def test_rag_requires_query(self):
        self.assertEqual(client.post("/api/rag", json={}).status_code, 422)


class PredictionTests(unittest.TestCase):
    def test_predict_reports_the_trained_model_without_claiming_certainty(self):
        response = client.post(
            "/api/predict",
            json={"query": "A person is charged under Section 302 IPC and claims self-defence."},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        # A prediction is returned, but always as a calibrated probability plus a
        # low-confidence flag — never as a bare verdict.
        self.assertTrue(body["available"])
        self.assertIn(body["label"], ("convicted", "acquitted"))
        self.assertGreaterEqual(body["confidence"], 0.0)
        self.assertLessEqual(body["confidence"], 1.0)
        self.assertIsInstance(body["low_confidence"], bool)
        self.assertAlmostEqual(sum(body["probabilities"].values()), 1.0, places=3)
        self.assertIsNone(body["reason"])
        self.assertEqual(body["features_used"], "query_facts_and_sections")


class CaseLookupTests(unittest.TestCase):
    def test_missing_document_returns_404_or_503(self):
        response = client.get("/api/cases/does-not-exist")
        self.assertIn(response.status_code, (404, 503))


class ResearchBehaviourTests(unittest.TestCase):
    def test_research_is_empty_corpus_safe(self):
        response = client.post("/api/research", json={"query": "breach of contract damages"})
        # Either a real result (corpus populated) or a clear 503 (empty corpus).
        self.assertIn(response.status_code, (200, 503))
        if response.status_code == 503:
            self.assertIn("empty", response.json()["detail"].lower())
        else:
            body = response.json()
            for key in ("answer", "sources", "citations", "prediction", "limitations", "disclaimer"):
                self.assertIn(key, body)


if __name__ == "__main__":
    unittest.main()
