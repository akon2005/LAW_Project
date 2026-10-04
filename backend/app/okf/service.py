"""
OKF bundle service.

Single entry point over a parsed bundle for the API layer and for retrieval:

* :meth:`list_concepts` — enumerate/filter concepts
* :meth:`get_concept`   — one concept with resolved relationships
* :meth:`validate`      — conformance report (§11)
* :meth:`search`        — lightweight lexical lookup over concept text

The bundle is loaded lazily and cached; call :meth:`reload` after regeneration.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import OKF_BUNDLE_DIR
from app.okf.importer import OKFImporter
from app.okf.link_resolver import OKFLinkResolver
from app.okf.model import OKFDocument, OKF_VERSION
from app.okf.provenance import OKFProvenanceManager, is_stale, trust_tier
from app.okf.validator import OKFValidator


class OKFService:
    def __init__(self, bundle_root: Optional[Path] = None):
        self.bundle_root = Path(bundle_root or OKF_BUNDLE_DIR)
        self._lock = threading.Lock()
        self._documents: Optional[List[OKFDocument]] = None

    # ── Loading ────────────────────────────────────────────────────────
    def reload(self) -> List[OKFDocument]:
        with self._lock:
            self._documents = OKFImporter(self.bundle_root).load()
            return self._documents

    @property
    def documents(self) -> List[OKFDocument]:
        if self._documents is None:
            self.reload()
        assert self._documents is not None
        return self._documents

    @property
    def loaded(self) -> bool:
        return self._documents is not None

    def exists(self) -> bool:
        return self.bundle_root.is_dir()

    @property
    def concepts(self) -> List[OKFDocument]:
        return [doc for doc in self.documents if not doc.is_reserved]

    def _resolver(self) -> OKFLinkResolver:
        return OKFLinkResolver(self.documents)

    # ── Querying ───────────────────────────────────────────────────────
    def list_concepts(
        self,
        concept_type: Optional[str] = None,
        status: Optional[str] = None,
        tag: Optional[str] = None,
        query: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        results = self.concepts

        if concept_type:
            wanted = concept_type.strip().lower()
            results = [doc for doc in results if doc.type.lower() == wanted]
        if status:
            wanted = status.strip().lower()
            results = [doc for doc in results if doc.status == wanted]
        if tag:
            wanted = tag.strip().lower()
            results = [doc for doc in results if wanted in {t.lower() for t in doc.tags}]
        if query:
            results = self._filter_by_text(results, query)

        results = sorted(results, key=lambda doc: doc.concept_id)
        total = len(results)
        window = results[offset : offset + max(0, limit)]
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "concepts": [doc.as_dict() for doc in window],
        }

    def _filter_by_text(self, documents: List[OKFDocument], query: str) -> List[OKFDocument]:
        terms = [term for term in query.lower().split() if term]
        if not terms:
            return documents

        def haystack(doc: OKFDocument) -> str:
            return " ".join(
                [doc.title, doc.description, " ".join(doc.tags), doc.body]
            ).lower()

        return [doc for doc in documents if all(term in haystack(doc) for term in terms)]

    def get_concept(self, concept_id: str) -> Optional[Dict[str, Any]]:
        concept_id = concept_id.strip().strip("/")
        if concept_id.endswith(".md"):
            concept_id = concept_id[: -len(".md")]
        for doc in self.documents:
            if doc.concept_id == concept_id:
                return self._detail(doc)
        return None

    def _detail(self, doc: OKFDocument) -> Dict[str, Any]:
        resolver = self._resolver()
        outgoing = [
            {
                "concept_id": target,
                "title": self._title_for(target),
                "link_text": text,
            }
            for target, text in resolver.outgoing(doc)
        ]
        broken = [
            {"target": link.target, "line": link.line}
            for link in doc.links
            if not link.external and resolver.resolve(doc, link.target) is None
        ]
        detail = doc.as_dict()
        detail.update(
            {
                "body": doc.body,
                "is_reserved": doc.is_reserved,
                "trust_tier": trust_tier(doc),
                "stale": is_stale(doc),
                "outgoing": outgoing,
                "broken_links": broken,
                "backlinks": [
                    {"concept_id": cid, "title": self._title_for(cid)}
                    for cid in resolver.backlinks(doc.concept_id)
                ],
                "external_links": [
                    {"text": link.text, "target": link.target}
                    for link in doc.links
                    if link.external and not link.target.startswith("#")
                ],
            }
        )
        return detail

    def _title_for(self, concept_id: str) -> str:
        for doc in self.documents:
            if doc.concept_id == concept_id:
                return doc.title
        return concept_id

    # ── Validation ─────────────────────────────────────────────────────
    def validate(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        return OKFValidator(self.bundle_root, self.documents).validate(now)

    # ── Retrieval support (Phase 8: OKF retrieval) ─────────────────────
    def search(self, query: str, top_k: int = 5, concept_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Lexical lookup over concept text. Scores are term-overlap fractions —
        they are retrieval relevance, never a legal confidence (§8).
        """
        terms = [term for term in (query or "").lower().split() if len(term) > 2]
        if not terms:
            return []
        pool = self.concepts
        if concept_type:
            pool = [doc for doc in pool if doc.type.lower() == concept_type.lower()]

        scored: List[Dict[str, Any]] = []
        for doc in pool:
            title = doc.title.lower()
            description = doc.description.lower()
            tags = " ".join(doc.tags).lower()
            body = doc.body.lower()
            score = 0.0
            for term in terms:
                score += 2.0 if term in title else 0.0
                score += 1.0 if term in tags else 0.0
                score += 1.0 if term in description else 0.0
                score += 0.5 if term in body else 0.0
            if score > 0:
                scored.append(
                    {
                        "concept_id": doc.concept_id,
                        "type": doc.type,
                        "title": doc.title,
                        "description": doc.description,
                        "score": round(score / (len(terms) * 4.5), 4),
                    }
                )
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[: max(1, top_k)]

    # ── Summary ────────────────────────────────────────────────────────
    def stats(self) -> Dict[str, Any]:
        provenance = OKFProvenanceManager(self.concepts)
        types: Dict[str, int] = {}
        for doc in self.concepts:
            types[doc.type or "(untyped)"] = types.get(doc.type or "(untyped)", 0) + 1
        return {
            "bundle": str(self.bundle_root),
            "available": self.exists(),
            "okf_version": OKF_VERSION,
            "concepts": len(self.concepts),
            "documents": len(self.documents),
            "types": types,
            "trust": provenance.trust_summary(),
            "provenance": provenance.provenance_coverage(),
        }


okf_service = OKFService()
