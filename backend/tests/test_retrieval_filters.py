"""Unit tests for retrieval filtering (Steps 12, 8)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.retrieval_service import _to_similarity, filter_by_sections


class SimilarityConversionTests(unittest.TestCase):
    def test_cosine_distance_to_similarity(self):
        self.assertAlmostEqual(_to_similarity(0.2), 0.8)
        self.assertAlmostEqual(_to_similarity(0.0), 1.0)

    def test_clamped_to_unit_interval(self):
        self.assertEqual(_to_similarity(2.0), 0.0)
        self.assertEqual(_to_similarity(-1.0), 1.0)

    def test_bad_value_is_zero(self):
        self.assertEqual(_to_similarity(None), 0.0)
        self.assertEqual(_to_similarity("not-a-number"), 0.0)


class SectionFilterTests(unittest.TestCase):
    def setUp(self):
        self.records = [
            {"chunk_id": "1_0", "sections": ["Section 302"], "text": "murder charge"},
            {"chunk_id": "2_0", "sections": ["Section 420"], "text": "cheating charge"},
            {"chunk_id": "3_0", "sections": [], "text": "The accused was charged under Section 103 BNS."},
        ]

    def test_filter_keeps_matching_section(self):
        kept = filter_by_sections(self.records, ["IPC Section 302"])
        self.assertEqual([r["chunk_id"] for r in kept], ["1_0"])

    def test_filter_can_match_text(self):
        kept = filter_by_sections(self.records, ["BNS Section 103"])
        self.assertEqual([r["chunk_id"] for r in kept], ["3_0"])

    def test_filter_returns_empty_when_no_match(self):
        self.assertEqual(filter_by_sections(self.records, ["IPC Section 999"]), [])

    def test_no_filter_returns_all(self):
        self.assertEqual(filter_by_sections(self.records, []), self.records)


if __name__ == "__main__":
    unittest.main()
