"""
OKFExporter — write OKF v0.2 documents to disk (§4).

Serialisation is deterministic: frontmatter keys are emitted in a fixed order so
a regenerated bundle produces a reviewable diff rather than churn. Unknown keys
are preserved (consumers MUST NOT reject unrecognised fields — §4.1), so the
exporter appends them after the canonical ones.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import yaml

from app.okf.model import OKFDocument
from app.okf.parser import OKFParser, split_frontmatter

# Canonical ordering of the frontmatter families defined by the spec.
_KEY_ORDER = (
    "type",
    "title",
    "description",
    "resource",
    "tags",
    "status",
    "stale_after",
    "runtime",
    "parameters",
    "computation",
    "executor",
    "attester",
    "generated",
    "verified",
    "sources",
    "usage_window",
)

# Reserved files that must not be written with concept frontmatter.
RESERVED_FILENAMES = {"index.md", "log.md"}


def _ordered(frontmatter: Dict[str, Any]) -> Dict[str, Any]:
    """Order known keys canonically, then keep the rest in insertion order."""
    ordered: Dict[str, Any] = {}
    for key in _KEY_ORDER:
        if key in frontmatter and frontmatter[key] not in (None, "", [], {}):
            ordered[key] = frontmatter[key]
    for key, value in frontmatter.items():
        if key not in ordered and not key.startswith("__"):
            ordered[key] = value
    return ordered


class OKFExporter:
    def __init__(self, bundle_root: Path, parser: Optional[OKFParser] = None):
        self.bundle_root = Path(bundle_root)
        self.parser = parser or OKFParser()
        self.written: List[str] = []

    # ── Serialisation ──────────────────────────────────────────────────
    def serialize(self, frontmatter: Dict[str, Any], body: str) -> str:
        """Render a concept document. The body is written verbatim."""
        block = yaml.safe_dump(
            _ordered(frontmatter),
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        ).rstrip()
        body_text = body if body.endswith("\n") or not body else body + "\n"
        return f"---\n{block}\n---\n{body_text}"

    def write_serialized(self, concept_id: str, text: str) -> Path:
        """Write a pre-rendered document (used for index.md / log.md)."""
        path = self.bundle_root / f"{concept_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        self.written.append(concept_id)
        return path

    def write_document(self, document: OKFDocument) -> Path:
        """Write one concept document from its parsed representation."""
        return self.write_serialized(
            document.concept_id, self.serialize(document.frontmatter, document.body)
        )

    def write_concept(
        self, concept_id: str, frontmatter: Dict[str, Any], body: str
    ) -> Path:
        """Convenience: build and write a concept from raw parts."""
        name = Path(concept_id).name
        if name in RESERVED_FILENAMES or f"{name}.md" in RESERVED_FILENAMES:
            raise ValueError(
                f"'{concept_id}' is a reserved filename and is not a concept (§3.1)"
            )
        if not str(frontmatter.get("type") or "").strip():
            raise ValueError(f"concept '{concept_id}' is missing the required 'type'")
        return self.write_serialized(concept_id, self.serialize(frontmatter, body))

    def write_index(self, concept_id: str, body: str, okf_version: Optional[str] = None) -> Path:
        """
        Write an ``index.md``. Root indexes MAY declare ``okf_version``; nested
        ones carry no frontmatter at all (§8).
        """
        if okf_version and Path(concept_id).name == "index.md" and concept_id == "index":
            text = f'---\nokf_version: "{okf_version}"\n---\n{body}'
        else:
            text = body
        return self.write_serialized(concept_id, text)

    def write_log(self, concept_id: str, body: str) -> Path:
        return self.write_serialized(concept_id, body)

    # ── Round-trip ─────────────────────────────────────────────────────
    def round_trip(self, text: str, concept_id: str) -> str:
        """Parse then re-serialise, so callers can assert stability."""
        document = self.parser.parse_text(text, concept_id)
        return self.serialize(document.frontmatter, document.body)
