"""
OKF v0.2 data model.

Implements the vocabulary of the Open Knowledge Format specification:

    https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md

An OKF *bundle* is a directory tree of markdown files, each of which is a
*concept*. A concept has a YAML frontmatter block (``type`` is the only always
required key) and a markdown body. ``index.md`` and ``log.md`` are reserved
filenames and are not concept documents.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

# The specification version this implementation targets (§12).
OKF_VERSION = "0.2"

# Reserved filenames with defined meaning at any level of the hierarchy (§3.1).
RESERVED_FILENAMES = frozenset({"index.md", "log.md"})

# Lifecycle statuses (§5.4). An absent status means "stable".
VALID_STATUSES = ("draft", "stable", "deprecated")

# Trust tiers derived from ``verified`` (§5.3).
TRUST_UNVERIFIED = "unverified"
TRUST_MACHINE = "machine-confirmed"
TRUST_HUMAN = "human-reviewed"


@dataclass
class OKFLink:
    """A standard markdown link found in a concept body (§6.1)."""

    text: str
    target: str
    line: int
    external: bool = False


@dataclass
class OKFDocument:
    """
    One markdown document in a bundle.

    ``concept_id`` is the path of the file within the bundle with the ``.md``
    suffix removed (forward slashes), per §2. ``frontmatter`` holds only the
    parsed YAML block; ``body`` is everything after it.
    """

    concept_id: str
    path: Path
    frontmatter: Dict[str, Any] = field(default_factory=dict)
    body: str = ""
    links: List[OKFLink] = field(default_factory=list)

    # ── Identity ───────────────────────────────────────────────────────
    @property
    def filename(self) -> str:
        return self.path.name

    @property
    def is_reserved(self) -> bool:
        """``index.md`` / ``log.md`` are not concepts (§3.1)."""
        return self.filename in RESERVED_FILENAMES

    @property
    def is_index(self) -> bool:
        return self.filename == "index.md"

    @property
    def is_log(self) -> bool:
        return self.filename == "log.md"

    # ── Required / recommended frontmatter (§4.1) ──────────────────────
    @property
    def type(self) -> str:
        """The only always-required key. Empty string when absent."""
        return str(self.frontmatter.get("type") or "").strip()

    @property
    def title(self) -> str:
        """Display name; falls back to a title-cased filename (§4.1)."""
        declared = str(self.frontmatter.get("title") or "").strip()
        if declared:
            return declared
        return self.path.stem.replace("-", " ").replace("_", " ").strip().title()

    @property
    def description(self) -> str:
        return str(self.frontmatter.get("description") or "").strip()

    @property
    def resource(self) -> str:
        return str(self.frontmatter.get("resource") or "").strip()

    @property
    def tags(self) -> List[str]:
        raw = self.frontmatter.get("tags")
        if isinstance(raw, list):
            return [str(item) for item in raw if str(item).strip()]
        if isinstance(raw, str) and raw.strip():
            return [raw.strip()]
        return []

    # ── Lifecycle (§5.4, §5.5) ─────────────────────────────────────────
    @property
    def status(self) -> str:
        declared = str(self.frontmatter.get("status") or "").strip().lower()
        return declared if declared in VALID_STATUSES else "stable"

    @property
    def stale_after(self) -> str:
        return str(self.frontmatter.get("stale_after") or "").strip()

    # ── Provenance (§5.1) ──────────────────────────────────────────────
    @property
    def sources(self) -> List[Dict[str, Any]]:
        raw = self.frontmatter.get("sources")
        if isinstance(raw, list):
            return [entry for entry in raw if isinstance(entry, dict)]
        return []

    # ── Trust (§5.2) ───────────────────────────────────────────────────
    @property
    def generated(self) -> Dict[str, Any]:
        raw = self.frontmatter.get("generated")
        return raw if isinstance(raw, dict) else {}

    @property
    def verified(self) -> List[Dict[str, Any]]:
        """
        Verification events. A bare ``{by, at}`` mapping is treated as a
        one-element list (§5.2).
        """
        raw = self.frontmatter.get("verified")
        if isinstance(raw, dict):
            return [raw]
        if isinstance(raw, list):
            return [entry for entry in raw if isinstance(entry, dict)]
        return []

    def as_dict(self) -> Dict[str, Any]:
        """Serialisable projection used by the API and the index builder."""
        return {
            "concept_id": self.concept_id,
            "type": self.type,
            "title": self.title,
            "description": self.description,
            "resource": self.resource,
            "tags": self.tags,
            "status": self.status,
            "stale_after": self.stale_after,
            "generated": self.generated,
            "verified": self.verified,
            "sources": self.sources,
        }
