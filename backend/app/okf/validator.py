"""
OKFValidator — conformance checks for an OKF v0.2 bundle (§11).

Conformance is deliberately undemanding. A bundle is conformant when:

* every non-reserved ``.md`` file contains a parseable YAML frontmatter block;
* every frontmatter block contains a non-empty ``type``;
* reserved files (``index.md`` / ``log.md``) follow §8 / §9 when present.

It is explicitly **not** invalid for a bundle to have missing optional
frontmatter families, unknown types, unknown keys, broken cross-links or absent
indexes. Those are surfaced as findings, never as failures — so this validator
reports far more than it rejects.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from app.okf.link_resolver import OKFLinkResolver
from app.okf.model import OKFDocument, OKF_VERSION, RESERVED_FILENAMES
from app.okf.provenance import OKFProvenanceManager, is_stale, trust_tier


def _major(version: str) -> Optional[str]:
    text = str(version or "").strip().strip('"').strip("'")
    return text.split(".", 1)[0] if text else None


class OKFValidator:
    def __init__(self, bundle_root: Path, documents: Iterable[OKFDocument]):
        self.bundle_root = Path(bundle_root)
        self.documents: List[OKFDocument] = list(documents)

    # ── Helpers ────────────────────────────────────────────────────────
    @property
    def concepts(self) -> List[OKFDocument]:
        return [doc for doc in self.documents if not doc.is_reserved]

    @property
    def reserved(self) -> List[OKFDocument]:
        return [doc for doc in self.documents if doc.is_reserved]

    def _declared_version(self) -> Optional[str]:
        """``okf_version`` is only legal in a bundle-root ``index.md`` (§12)."""
        for doc in self.documents:
            if doc.concept_id == "index" and doc.is_index:
                declared = doc.frontmatter.get("okf_version")
                if declared:
                    return str(declared)
        return None

    def _validate_concept(self, doc: OKFDocument) -> List[str]:
        errors: List[str] = []
        parse_error = doc.frontmatter.get("__parse_error__")
        if parse_error:
            errors.append(str(parse_error))
            return errors
        if not doc.frontmatter:
            errors.append("missing YAML frontmatter block (§4.1)")
            return errors
        if not doc.type:
            errors.append("frontmatter is missing the required non-empty 'type' (§4.1)")
        return errors

    def _validate_index(self, doc: OKFDocument) -> List[str]:
        """
        An ``index.md`` carries no frontmatter, except a bundle-root index which
        MAY declare ``okf_version`` (§8).
        """
        errors: List[str] = []
        if not doc.frontmatter:
            return errors
        keys = {k for k in doc.frontmatter if not k.startswith("__")}
        if doc.concept_id == "index":
            unexpected = keys - {"okf_version"}
            if unexpected:
                errors.append(
                    "bundle-root index.md may only declare 'okf_version' (§8); "
                    f"found: {', '.join(sorted(unexpected))}"
                )
        elif keys:
            errors.append(
                "index.md must not carry a frontmatter block (§8); "
                f"found: {', '.join(sorted(keys))}"
            )
        return errors

    def _validate_log(self, doc: OKFDocument) -> List[str]:
        """A log.md uses ISO ``## YYYY-MM-DD`` date headings (§9)."""
        errors: List[str] = []
        has_heading = any(
            line.strip().startswith("## ") for line in doc.body.splitlines()
        )
        if not has_heading:
            errors.append("log.md has no '## YYYY-MM-DD' date heading (§9)")
        return errors

    def _duplicate_concept_ids(self) -> List[Dict[str, str]]:
        """Case-insensitive id collisions break case-insensitive filesystems."""
        seen: Dict[str, str] = {}
        duplicates: List[Dict[str, str]] = []
        for doc in self.documents:
            key = doc.concept_id.lower()
            if key in seen:
                duplicates.append({"first": seen[key], "duplicate": doc.concept_id})
            else:
                seen[key] = doc.concept_id
        return duplicates

    # ── Report ─────────────────────────────────────────────────────────
    def validate(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        reference = now or datetime.now(timezone.utc)
        invalid: List[Dict[str, Any]] = []
        structural_errors: List[str] = []

        for doc in self.reserved:
            if doc.is_index:
                errs = self._validate_index(doc)
            elif doc.is_log:
                errs = self._validate_log(doc)
            else:  # pragma: no cover - reserved set is fixed
                errs = []
            if errs:
                invalid.append({"concept_id": doc.concept_id, "errors": errs})

        for doc in self.concepts:
            errs = self._validate_concept(doc)
            if errs:
                invalid.append({"concept_id": doc.concept_id, "errors": errs})

        resolver = OKFLinkResolver(self.documents)
        provenance = OKFProvenanceManager(self.concepts)

        declared = self._declared_version()
        compatible = True
        if declared is not None:
            compatible = _major(declared) == _major(OKF_VERSION)
            if not compatible:
                structural_errors.append(
                    f"bundle declares okf_version '{declared}', which is not a "
                    f"{_major(OKF_VERSION)}.x series; consuming best-effort (§12)."
                )

        valid = not invalid

        return {
            "bundle": str(self.bundle_root),
            "okf_version": declared or OKF_VERSION,
            "target_version": OKF_VERSION,
            "version_compatible": compatible,
            "documents_total": len(self.documents),
            "concepts_total": len(self.concepts),
            "valid_concepts": len(self.concepts) - len(
                [item for item in invalid if item["concept_id"] in {c.concept_id for c in self.concepts}]
            ),
            "invalid_concepts": len(
                [item for item in invalid if item["concept_id"] in {c.concept_id for c in self.concepts}]
            ),
            "invalid_documents": invalid,
            "missing_metadata": [
                item["concept_id"]
                for item in invalid
                if any("type" in err or "frontmatter" in err for err in item["errors"])
            ],
            "broken_links": resolver.broken_links(),
            "missing_provenance": provenance.documents_without_sources(),
            "missing_source_resource": provenance.sources_missing_resource(),
            "duplicate_source_ids": provenance.duplicate_source_ids(),
            "duplicate_concept_ids": self._duplicate_concept_ids(),
            "stale_concepts": provenance.stale_concepts(reference),
            "trust": provenance.trust_summary(),
            "provenance": provenance.provenance_coverage(),
            "types": sorted({doc.type for doc in self.concepts if doc.type}),
            "structural_errors": structural_errors,
            "valid": valid,
        }

    # ── Convenience ────────────────────────────────────────────────────
    def invalid_documents(self, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
        return self.validate(now)["invalid_documents"]
