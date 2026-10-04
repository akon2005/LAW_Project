"""Unit tests for data-layer services (Steps 4, 7, 8, 36)."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.chunking import chunk_text
from app.services.ids import resolve_document_id, stable_chunk_id, stable_document_id
from app.services.ingestion_status import IngestionStatus
from app.services.schema_service import detect_field_mapping, detect_schema, dot_get


class IdTests(unittest.TestCase):
    def test_upstream_id_is_preferred(self):
        doc_id, origin = resolve_document_id("file.pdf", "42", "some text")
        self.assertEqual(doc_id, "42")
        self.assertEqual(origin, "upstream_id")

    def test_hash_is_deterministic_without_upstream_id(self):
        first = stable_document_id("file.pdf", None, "text")
        second = stable_document_id("file.pdf", None, "text")
        self.assertEqual(first, second)
        self.assertNotEqual(first, stable_document_id("file.pdf", None, "other"))

    def test_chunk_id_is_stable(self):
        self.assertEqual(stable_chunk_id("42", 3), "42_3")


class ChunkingTests(unittest.TestCase):
    def test_empty_input(self):
        self.assertEqual(chunk_text("   "), [])

    def test_paragraph_boundaries_respected(self):
        paragraph_a = "First paragraph about the facts of the dispute. " * 3
        paragraph_b = "Second paragraph about the applicable law. " * 3
        chunks = chunk_text(f"{paragraph_a}\n\n{paragraph_b}", size=200, overlap=0)
        self.assertGreaterEqual(len(chunks), 2)
        self.assertEqual([c["chunk_index"] for c in chunks], list(range(len(chunks))))

    def test_long_paragraph_is_split(self):
        text = " ".join(f"Sentence number {i} about the dispute." for i in range(50))
        chunks = chunk_text(text, size=200, overlap=20)
        self.assertGreater(len(chunks), 1)
        # Overlap means adjacent chunks share some content.
        self.assertTrue(any(chunks[1]["text"][:20] in chunks[0]["text"] for _ in [0]))

    def test_fixed_strategy(self):
        chunks = chunk_text("abcdefghij" * 30, strategy="fixed", size=100, overlap=10)
        self.assertGreater(len(chunks), 1)


class IngestionStatusTests(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = IngestionStatus(Path(tmp) / "status.json")
            self.assertEqual(store.read()["status"], "idle")
            store.start("some/dataset", "sample")
            self.assertEqual(store.read()["status"], "running")
            store.update(processed_chunks=10)
            self.assertEqual(store.read()["processed_chunks"], 10)
            store.finish()
            self.assertEqual(store.read()["status"], "completed")

    def test_error_finish(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = IngestionStatus(Path(tmp) / "status.json")
            store.finish(error="boom")
            status = store.read()
            self.assertEqual(status["status"], "failed")
            self.assertEqual(status["error"], "boom")


class SchemaTests(unittest.TestCase):
    def test_dot_get_nested(self):
        record = {"metadata": {"source": "a.pdf"}}
        self.assertEqual(dot_get(record, "metadata.source"), "a.pdf")
        self.assertIsNone(dot_get(record, "metadata.missing"))

    def test_detect_field_mapping(self):
        records = [
            {"full_text": "judgment", "outcome": "allowed", "court": "Supreme Court",
             "year": 2020, "title": "A v. B"},
            {"full_text": "judgment2", "outcome": "dismissed", "court": "High Court",
             "year": 2021, "title": "C v. D"},
        ]
        mapping = detect_field_mapping(records)
        self.assertEqual(mapping["text"], "full_text")
        self.assertEqual(mapping["outcome"], "outcome")
        self.assertEqual(mapping["court"], "court")
        self.assertEqual(mapping["year"], "year")
        self.assertEqual(mapping["case_name"], "title")

    def test_undetectable_field_is_none(self):
        mapping = detect_field_mapping([{"full_text": "x"}])
        self.assertIsNone(mapping["outcome"])
        self.assertIsNone(mapping["source_url"])

    def test_detect_schema_reports_missing_pct(self):
        records = [{"a": "x", "b": None}, {"a": "y", "b": "z"}]
        schema = detect_schema(records)
        self.assertEqual(schema["field_count"], 2)
        self.assertEqual(schema["fields"]["b"]["missing_pct"], 50.0)


if __name__ == "__main__":
    unittest.main()
