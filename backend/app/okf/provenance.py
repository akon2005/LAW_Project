"""
OKFProvenanceManager — trust tiers, staleness, actors and the source registry.

Implements §5 (provenance, trust, lifecycle) and §7 (actor convention) of the
OKF v0.2 specification. OKF records objective signals; this module *derives*
the trust tier and staleness rather than storing a verdict.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from app.okf.model import (
    OKFDocument,
    TRUST_HUMAN,
    TRUST_MACHINE,
    TRUST_UNVERIFIED,
)

# §7 — the human: prefix is the only signal of human authorship/confirmation.
HUMAN_PREFIX = "human:"
PROCESS_PREFIX = "process:"


def parse_timestamp(value: Any) -> Optional[datetime]:
    """
    Parse an ISO 8601 datetime with an explicit UTC offset (§5).

    A naive timestamp is treated as UTC so comparisons never raise; ``None``
    means the value was absent or unparseable.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def actor_kind(actor: Any) -> str:
    """Classify an actor string as ``human``, ``process`` or ``machine`` (§7)."""
    text = str(actor or "").strip()
    if text.startswith(HUMAN_PREFIX):
        return "human"
    if text.startswith(PROCESS_PREFIX):
        return "process"
    return "machine"


def trust_tier(document: OKFDocument) -> str:
    """
    Derive the trust tier from ``verified`` (§5.3).

    No ``verified`` key ⇒ ``unverified``; only non-human actors ⇒
    ``machine-confirmed``; any ``human:<id>`` actor ⇒ ``human-reviewed``.
    """
    events = document.verified
    if not events:
        return TRUST_UNVERIFIED
    if any(actor_kind(event.get("by")) == "human" for event in events):
        return TRUST_HUMAN
    return TRUST_MACHINE


def is_stale(document: OKFDocument, now: Optional[datetime] = None) -> bool:
    """True when ``now >= stale_after`` (§5.5). Absent/unparseable ⇒ False."""
    deadline = parse_timestamp(document.stale_after)
    if deadline is None:
        return False
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    return reference >= deadline


def last_verified_at(document: OKFDocument) -> Optional[datetime]:
    """The most recent verification instant across all events (§5.2)."""
    stamps = [
        parse_timestamp(event.get("at"))
        for event in document.verified
    ]
    stamps = [stamp for stamp in stamps if stamp is not None]
    return max(stamps) if stamps else None


def content_hash(text: str) -> str:
    """Deterministic sha256 over UTF-8 text (used for provenance/lineage)."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


class OKFProvenanceManager:
    """Inspect provenance across a set of parsed documents."""

    def __init__(self, documents: Iterable[OKFDocument]):
        self.documents = [doc for doc in documents if not doc.is_reserved]

    def by_concept(self) -> Dict[str, OKFDocument]:
        return {doc.concept_id: doc for doc in self.documents}

    def documents_without_sources(self) -> List[str]:
        """Concepts that carry no ``sources`` entry at all."""
        return [doc.concept_id for doc in self.documents if not doc.sources]

    def sources_missing_resource(self) -> List[Dict[str, Any]]:
        """
        ``sources[].resource`` is REQUIRED within an entry (§5.1); report any
        entry that omits it instead of silently accepting it.
        """
        problems: List[Dict[str, Any]] = []
        for doc in self.documents:
            for index, entry in enumerate(doc.sources):
                if not str(entry.get("resource") or "").strip():
                    problems.append(
                        {"concept_id": doc.concept_id, "source_index": index}
                    )
        return problems

    def duplicate_source_ids(self) -> List[Dict[str, Any]]:
        """A ``sources[].id`` must be unique within a concept (it is a join key)."""
        problems: List[Dict[str, Any]] = []
        for doc in self.documents:
            seen = set()
            for entry in doc.sources:
                source_id = str(entry.get("id") or "").strip()
                if source_id and source_id in seen:
                    problems.append(
                        {"concept_id": doc.concept_id, "source_id": source_id}
                    )
                seen.add(source_id)
        return problems

    def source_registry(self) -> List[Dict[str, Any]]:
        """
        Every declared source across the bundle, with the concepts that cite it.

        Credibility signals (``author``, ``usage_count``, ``last_modified``) are
        carried through verbatim; OKF stores signals, not a score (§5.1).
        """
        registry: Dict[str, Dict[str, Any]] = {}
        for doc in self.documents:
            for entry in doc.sources:
                resource = str(entry.get("resource") or "").strip()
                if not resource:
                    continue
                record = registry.setdefault(
                    resource,
                    {
                        "resource": resource,
                        "id": entry.get("id"),
                        "title": entry.get("title"),
                        "author": entry.get("author"),
                        "usage_count": entry.get("usage_count"),
                        "last_modified": entry.get("last_modified"),
                        "cited_by": [],
                    },
                )
                if doc.concept_id not in record["cited_by"]:
                    record["cited_by"].append(doc.concept_id)
        return sorted(registry.values(), key=lambda item: item["resource"])

    def trust_summary(self) -> Dict[str, int]:
        """Count of concepts per trust tier (§5.3)."""
        summary = {TRUST_UNVERIFIED: 0, TRUST_MACHINE: 0, TRUST_HUMAN: 0}
        for doc in self.documents:
            summary[trust_tier(doc)] += 1
        return summary

    def stale_concepts(self, now: Optional[datetime] = None) -> List[str]:
        return [doc.concept_id for doc in self.documents if is_stale(doc, now)]

    def provenance_coverage(self) -> Dict[str, Any]:
        """Share of concepts that carry traceable provenance."""
        total = len(self.documents)
        with_sources = total - len(self.documents_without_sources())
        return {
            "total_concepts": total,
            "with_sources": with_sources,
            "without_sources": total - with_sources,
            "coverage": round(with_sources / total, 4) if total else 0.0,
        }
