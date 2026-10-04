"""Unit tests for query understanding (Steps 14, 15)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.query_analyzer import LegalQueryAnalyzer, LegalSectionNormalizer


class SectionNormalizationTests(unittest.TestCase):
    def setUp(self):
        self.normalizer = LegalSectionNormalizer(equivalence_map={})

    def test_ipc_forms_normalize_equally(self):
        for text in ("IPC 302", "Section 302 IPC", "Sec. 302 IPC", "302 IPC"):
            records = self.normalizer.normalize_text(text)
            self.assertTrue(records, f"no section parsed from {text!r}")
            self.assertEqual(records[0]["statute"], "IPC", text)
            self.assertEqual(records[0]["section"], "302", text)
            self.assertEqual(records[0]["normalized_text"], "IPC Section 302", text)

    def test_bns_full_name(self):
        records = self.normalizer.normalize_text("Section 103 of Bharatiya Nyaya Sanhita")
        self.assertEqual(records[0]["statute"], "BNS")
        self.assertEqual(records[0]["section"], "103")

    def test_original_text_preserved(self):
        records = self.normalizer.normalize_text("charged under Sec. 420 IPC")
        self.assertIn("420", records[0]["section"])
        self.assertTrue(records[0]["original_text"])

    def test_bare_section_has_no_statute(self):
        records = self.normalizer.normalize_text("Section 34")
        self.assertIsNone(records[0]["statute"])
        self.assertEqual(records[0]["normalized_text"], "Section 34")

    def test_ipc_and_bns_not_assumed_equivalent(self):
        records = self.normalizer.normalize_text("IPC 302 and BNS 103")
        self.assertEqual(records[0]["equivalents"], [])
        self.assertEqual(records[1]["equivalents"], [])

    def test_articles(self):
        self.assertEqual(self.normalizer.normalize_articles("Article 21"), ["Article 21"])


class QueryAnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.analyzer = LegalQueryAnalyzer(LegalSectionNormalizer(equivalence_map={}))

    def test_does_not_invent_entities(self):
        analysis = self.analyzer.analyze("Tell me about the weather in Mumbai")
        self.assertEqual(analysis["legal_sections"], [])
        self.assertIsNone(analysis["legal_issue"])
        self.assertIsNone(analysis["court"])

    def test_issue_only_when_present(self):
        analysis = self.analyzer.analyze("The accused claims self-defence under Section 302 IPC.")
        self.assertEqual(analysis["legal_issue"], "self-defence")
        self.assertEqual(analysis["legal_sections"][0]["normalized_text"], "IPC Section 302")

    def test_court_and_year(self):
        analysis = self.analyzer.analyze("Supreme Court judgment from 2019")
        self.assertEqual(analysis["court"], "Supreme Court of India")
        self.assertEqual(analysis["year"], 2019)

    def test_year_range(self):
        analysis = self.analyzer.analyze("cases between 2015 and 2020 about arbitration")
        self.assertEqual(analysis["year_from"], 2015)
        self.assertEqual(analysis["year_to"], 2020)

    def test_task_classification(self):
        self.assertEqual(
            self.analyzer.analyze("Will the court convict the accused?")["task"],
            "outcome_prediction",
        )
        self.assertEqual(
            self.analyzer.analyze("Find similar judgments on cheating")["task"],
            "precedent_retrieval",
        )

    def test_embedding_text_includes_sections(self):
        analysis = self.analyzer.analyze("A person is charged under IPC 302")
        self.assertIn("IPC Section 302", analysis["embedding_text"])


if __name__ == "__main__":
    unittest.main()
