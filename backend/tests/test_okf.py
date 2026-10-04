"""
OKF v0.2 tests (Phase 19).

Covers parsing, the data model, provenance/trust derivation, link resolution,
conformance validation, export/import round-tripping, index generation and the
knowledge API.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.okf import (
    OKFDocument,
    OKFExporter,
    OKFImporter,
    OKFIndexBuilder,
    OKFLinkResolver,
    OKFParser,
    OKFParseError,
    OKFProvenanceManager,
    OKFService,
    OKFValidator,
    trust_tier,
)
from app.okf.model import OKF_VERSION
from app.okf.provenance import actor_kind, is_stale, parse_timestamp


def concept_text(**frontmatter) -> str:
    lines = ["---"]
    for key, value in frontmatter.items():
        lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("# Body")
    return "\n".join(lines) + "\n"


class ParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = OKFParser()

    def test_parses_frontmatter_and_body(self):
        doc = self.parser.parse_text(
            concept_text(type="Metric", title="Revenue"), "metrics/revenue"
        )
        self.assertEqual(doc.type, "Metric")
        self.assertEqual(doc.title, "Revenue")
        self.assertIn("# Body", doc.body)

    def test_missing_frontmatter_is_none_not_an_error(self):
        doc = self.parser.parse_text("# Just a body\n", "index")
        self.assertEqual(doc.frontmatter, {})
        self.assertEqual(doc.type, "")

    def test_unclosed_frontmatter_raises(self):
        with self.assertRaises(OKFParseError):
            self.parser.parse_text("---\ntype: Metric\n# never closed\n", "x")

    def test_non_mapping_frontmatter_raises(self):
        with self.assertRaises(OKFParseError):
            self.parser.parse_text("---\n- just\n- a list\n---\nbody\n", "x")

    def test_links_carry_line_numbers(self):
        doc = self.parser.parse_text(
            "---\ntype: A\n---\n# H\n\nSee [B](/b.md) and [C](./c.md).\n", "a"
        )
        targets = [link.target for link in doc.links]
        self.assertEqual(targets, ["/b.md", "./c.md"])
        self.assertTrue(all(link.line >= 4 for link in doc.links))

    def test_external_links_are_tagged(self):
        doc = self.parser.parse_text(
            "---\ntype: A\n---\n[X](https://example.com) [Y](mailto:a@b.c)\n", "a"
        )
        self.assertTrue(all(link.external for link in doc.links))

    def test_images_are_not_links(self):
        doc = self.parser.parse_text("---\ntype: A\n---\n![alt](/img.png)\n", "a")
        self.assertEqual(doc.links, [])


class ModelTests(unittest.TestCase):
    def test_trust_tier_unverified(self):
        doc = OKFDocument("a", Path("a.md"), {"type": "A"}, "")
        self.assertEqual(trust_tier(doc), "unverified")

    def test_trust_tier_machine_confirmed(self):
        doc = OKFDocument(
            "a",
            Path("a.md"),
            {"type": "A", "verified": [{"by": "process:nightly", "at": "2026-06-01T00:00:00Z"}]},
            "",
        )
        self.assertEqual(trust_tier(doc), "machine-confirmed")

    def test_bare_verified_mapping_is_one_element_list(self):
        doc = OKFDocument(
            "a",
            Path("a.md"),
            {"type": "A", "verified": {"by": "human:ada", "at": "2026-06-01T00:00:00Z"}},
            "",
        )
        self.assertEqual(len(doc.verified), 1)
        self.assertEqual(trust_tier(doc), "human-reviewed")

    def test_unknown_status_defaults_to_stable(self):
        doc = OKFDocument("a", Path("a.md"), {"type": "A", "status": "weird"}, "")
        self.assertEqual(doc.status, "stable")

    def test_actor_kind(self):
        self.assertEqual(actor_kind("human:ada"), "human")
        self.assertEqual(actor_kind("process:nightly"), "process")
        self.assertEqual(actor_kind("agent/gemini"), "machine")


class ProvenanceTests(unittest.TestCase):
    def _doc(self, concept_id, sources, stale_after=None):
        fm = {"type": "A", "sources": sources}
        if stale_after:
            fm["stale_after"] = stale_after
        return OKFDocument(concept_id, Path(f"{concept_id}.md"), fm, "")

    def test_coverage_and_missing_sources(self):
        docs = [
            self._doc("a", [{"id": "s", "resource": "https://x"}]),
            self._doc("b", []),
        ]
        manager = OKFProvenanceManager(docs)
        coverage = manager.provenance_coverage()
        self.assertEqual(coverage["with_sources"], 1)
        self.assertEqual(coverage["without_sources"], 1)
        self.assertEqual(manager.documents_without_sources(), ["b"])

    def test_source_without_resource_is_reported(self):
        manager = OKFProvenanceManager([self._doc("a", [{"id": "s"}])])
        self.assertEqual(len(manager.sources_missing_resource()), 1)

    def test_duplicate_source_ids_are_reported(self):
        manager = OKFProvenanceManager(
            [self._doc("a", [{"id": "s", "resource": "https://x"}, {"id": "s", "resource": "https://y"}])]
        )
        self.assertEqual(len(manager.duplicate_source_ids()), 1)

    def test_source_registry_groups_citations(self):
        manager = OKFProvenanceManager(
            [
                self._doc("a", [{"id": "s", "resource": "https://x", "author": "team:t"}]),
                self._doc("b", [{"id": "s", "resource": "https://x"}]),
            ]
        )
        registry = manager.source_registry()
        self.assertEqual(len(registry), 1)
        self.assertEqual(sorted(registry[0]["cited_by"]), ["a", "b"])
        self.assertEqual(registry[0]["author"], "team:t")

    def test_staleness(self):
        past = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        future = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertTrue(is_stale(self._doc("a", [], stale_after=past)))
        self.assertFalse(is_stale(self._doc("a", [], stale_after=future)))
        self.assertFalse(is_stale(self._doc("a", [])))

    def test_parse_timestamp_treats_naive_as_utc(self):
        parsed = parse_timestamp("2026-01-01T00:00:00")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.tzinfo, timezone.utc)
        self.assertIsNone(parse_timestamp("not a date"))


class LinkResolverTests(unittest.TestCase):
    def _bundle(self):
        return [
            OKFDocument("a", Path("a.md"), {"type": "A"}, "", []),
            OKFDocument("dir/b", Path("dir/b.md"), {"type": "A"}, "", []),
            OKFDocument("dir/index", Path("dir/index.md"), {}, "", []),
        ]

    def test_absolute_and_relative_resolution(self):
        resolver = OKFLinkResolver(self._bundle())
        a = next(d for d in self._bundle() if d.concept_id == "a")
        b = next(d for d in self._bundle() if d.concept_id == "dir/b")
        self.assertEqual(resolver.resolve(a, "/dir/b.md"), "dir/b")
        self.assertEqual(resolver.resolve(b, "./b.md"), "dir/b")
        self.assertIsNone(resolver.resolve(a, "/missing.md"))

    def test_escaping_the_bundle_is_not_resolved(self):
        resolver = OKFLinkResolver(self._bundle())
        a = self._bundle()[0]
        self.assertIsNone(resolver.resolve(a, "../../etc/passwd"))

    def test_broken_links_are_reported_not_fatal(self):
        doc = OKFParser().parse_text("---\ntype: A\n---\n[X](/missing.md)\n", "a")
        self.assertEqual(len(OKFLinkResolver([doc]).broken_links()), 1)

    def test_directory_links_are_valid(self):
        doc = OKFParser().parse_text("---\ntype: A\n---\n* [dir](dir/) - group\n", "index")
        resolver = OKFLinkResolver([doc, OKFDocument("dir/x", Path("dir/x.md"), {"type": "A"}, "", [])])
        self.assertEqual(resolver.broken_links(), [])
        self.assertEqual(resolver.resolve_directory(doc, "dir/"), "dir")

    def test_backlinks_and_graph(self):
        a = OKFParser().parse_text("---\ntype: A\n---\n[B](/b.md)\n", "a")
        b = OKFParser().parse_text("---\ntype: A\n---\nno links\n", "b")
        resolver = OKFLinkResolver([a, b])
        self.assertEqual(resolver.backlinks("b"), ["a"])
        self.assertEqual(resolver.graph()["a"], ["b"])


class ValidatorTests(unittest.TestCase):
    def _validate(self, docs):
        return OKFValidator(Path("."), docs).validate()

    def test_valid_concept_passes(self):
        doc = OKFParser().parse_text("---\ntype: Metric\n---\nbody\n", "m")
        report = self._validate([doc])
        self.assertTrue(report["valid"])
        self.assertEqual(report["concepts_total"], 1)
        self.assertEqual(report["valid_concepts"], 1)

    def test_missing_type_is_invalid(self):
        doc = OKFParser().parse_text("---\ntitle: x\n---\nbody\n", "m")
        report = self._validate([doc])
        self.assertFalse(report["valid"])
        self.assertEqual(report["invalid_concepts"], 1)
        self.assertIn("m", report["missing_metadata"])

    def test_broken_links_do_not_break_conformance(self):
        doc = OKFParser().parse_text("---\ntype: A\n---\n[x](/missing.md)\n", "a")
        report = self._validate([doc])
        self.assertTrue(report["valid"])
        self.assertEqual(len(report["broken_links"]), 1)

    def test_root_index_may_declare_okf_version(self):
        index = OKFParser().parse_text('---\nokf_version: "0.2"\n---\n# Root\n', "index")
        report = self._validate([index])
        self.assertTrue(report["valid"])
        self.assertEqual(report["okf_version"], "0.2")
        self.assertTrue(report["version_compatible"])

    def test_nested_index_must_not_carry_frontmatter(self):
        index = OKFParser().parse_text("---\ntype: X\n---\nbody\n", "dir/index")
        report = self._validate([index])
        self.assertFalse(report["valid"])

    def test_incompatible_version_is_flagged_but_consumable(self):
        index = OKFParser().parse_text('---\nokf_version: "2.0"\n---\n# Root\n', "index")
        report = self._validate([index])
        self.assertFalse(report["version_compatible"])
        self.assertTrue(report["structural_errors"])

    def test_log_needs_date_heading(self):
        bad = OKFParser().parse_text("# Log\nno date\n", "log")
        good = OKFParser().parse_text("# Log\n## 2026-06-01\n* **Update**: x\n", "log")
        self.assertFalse(self._validate([bad])["valid"])
        self.assertTrue(self._validate([good])["valid"])


class ExportImportTests(unittest.TestCase):
    def test_round_trip_is_stable(self):
        exporter = OKFExporter(Path("."))
        original = '---\ntype: Metric\ntitle: Revenue\nsources:\n- id: s\n  resource: https://x\n---\n# Definition\n\nText.\n'
        once = exporter.round_trip(original, "m")
        twice = exporter.round_trip(once, "m")
        self.assertEqual(once, twice)

    def test_write_concept_requires_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            exporter = OKFExporter(Path(tmp))
            with self.assertRaises(ValueError):
                exporter.write_concept("a", {"title": "no type"}, "body")

    def test_reserved_filenames_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            exporter = OKFExporter(Path(tmp))
            with self.assertRaises(ValueError):
                exporter.write_concept("index", {"type": "A"}, "body")

    def test_import_loads_written_bundle_and_index_declares_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exporter = OKFExporter(root)
            exporter.write_concept(
                "metrics/revenue",
                {"type": "Metric", "title": "Revenue", "sources": [{"id": "s", "resource": "https://x"}]},
                "# Definition\n",
            )
            documents = OKFImporter(root).load()
            OKFIndexBuilder(root, documents).build(write=True)

            reloaded = OKFImporter(root).load()
            ids = {doc.concept_id for doc in reloaded}
            self.assertIn("metrics/revenue", ids)
            self.assertIn("index", ids)
            self.assertIn("metrics/index", ids)

            report = OKFValidator(root, reloaded).validate()
            self.assertTrue(report["valid"])
            self.assertEqual(report["okf_version"], OKF_VERSION)


class ServiceTests(unittest.TestCase):
    def _service(self, tmp: str) -> OKFService:
        root = Path(tmp)
        exporter = OKFExporter(root)
        exporter.write_concept(
            "judgments/a",
            {
                "type": "Legal Judgment",
                "title": "A v. B",
                "description": "A contract dispute.",
                "tags": ["contract"],
                "sources": [{"id": "c", "resource": "https://dataset"}],
            },
            "# Source\n\n[B v. C](/judgments/b.md)\n",
        )
        exporter.write_concept(
            "judgments/b",
            {
                "type": "Legal Judgment",
                "title": "B v. C",
                "sources": [{"id": "c", "resource": "https://dataset"}],
            },
            "# Source\n",
        )
        service = OKFService(root)
        service.reload()
        return service

    def test_list_and_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = self._service(tmp)
            everything = service.list_concepts()
            self.assertEqual(everything["total"], 2)
            filtered = service.list_concepts(tag="contract")
            self.assertEqual(filtered["total"], 1)
            self.assertEqual(filtered["concepts"][0]["concept_id"], "judgments/a")

    def test_get_concept_with_relationships(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = self._service(tmp)
            concept = service.get_concept("judgments/a")
            self.assertIsNotNone(concept)
            self.assertEqual(concept["trust_tier"], "unverified")
            self.assertEqual(concept["outgoing"][0]["concept_id"], "judgments/b")
            self.assertIsNone(service.get_concept("missing"))

    def test_backlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = self._service(tmp)
            concept = service.get_concept("judgments/b")
            self.assertEqual(concept["backlinks"][0]["concept_id"], "judgments/a")

    def test_search_returns_relevance_not_confidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = self._service(tmp)
            results = service.search("contract dispute")
            self.assertTrue(results)
            self.assertEqual(results[0]["concept_id"], "judgments/a")
            self.assertLessEqual(results[0]["score"], 1.0)

    def test_validate(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = self._service(tmp)
            report = service.validate()
            self.assertTrue(report["valid"])
            self.assertEqual(report["provenance"]["coverage"], 1.0)


class KnowledgeApiTests(unittest.TestCase):
    """The knowledge API must never 500, whether or not a bundle is built."""

    def setUp(self) -> None:
        from fastapi.testclient import TestClient

        from app.main import app

        self.client = TestClient(app, raise_server_exceptions=False)

    def test_stats(self):
        response = self.client.get("/api/knowledge/stats")
        self.assertEqual(response.status_code, 200)
        self.assertIn("okf_version", response.json())

    def test_validate(self):
        response = self.client.get("/api/knowledge/validate")
        self.assertIn(response.status_code, (200, 503))
        if response.status_code == 200:
            body = response.json()
            self.assertIn("valid", body)
            self.assertIn("provenance", body)

    def test_list(self):
        response = self.client.get("/api/knowledge")
        self.assertIn(response.status_code, (200, 503))

    def test_missing_concept_returns_404_or_503(self):
        response = self.client.get("/api/knowledge/definitely/not/here")
        self.assertIn(response.status_code, (404, 503))


class CommittedBundleTests(unittest.TestCase):
    """If the generated bundle is present, it must be conformant."""

    def test_bundle_is_conformant_when_present(self):
        from app.core.config import OKF_BUNDLE_DIR

        if not Path(OKF_BUNDLE_DIR).is_dir():
            self.skipTest("OKF bundle not built in this checkout")
        service = OKFService(OKF_BUNDLE_DIR)
        service.reload()
        report = service.validate()
        self.assertTrue(report["valid"], report["invalid_documents"][:5])
        self.assertEqual(report["broken_links"], [])
        self.assertEqual(report["provenance"]["without_sources"], 0)


if __name__ == "__main__":
    unittest.main()
