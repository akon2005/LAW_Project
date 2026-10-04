"""
Citation verification (Step 10).

Every citation shown to a user must point at a chunk that was actually
retrieved. This module maps the references an answer makes (``[SOURCE 3]``,
``[3]``, an explicit case name, or a source filename) back onto the retrieved
documents and marks each one ``verified`` or not.

Unverified references are returned separately and must never be rendered as
verified citations.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_SOURCE_MARKER = re.compile(r"\[\s*(?:SOURCE|Source|source)\s*(\d+)\s*\]")
_NUMERIC_MARKER = re.compile(r"\[(\d{1,2})\]")
_FILENAME = re.compile(r"[\w\-]+\.pdf", re.IGNORECASE)


def _display_name(case: Dict[str, Any]) -> str:
    """Human-readable case name, falling back to the real source filename."""
    name = (case.get("case_name") or "").strip()
    if name and name.lower() not in {"unknown case", "unknown", "n/a"}:
        return name
    petitioner = (case.get("petitioner") or "").strip()
    respondent = (case.get("respondent") or "").strip()
    if petitioner and respondent:
        return f"{petitioner} v. {respondent}"
    if petitioner:
        return petitioner
    return (case.get("source") or case.get("source_file") or "Unnamed document").strip()


def build_citation(case: Dict[str, Any], verified: bool, reference: str = "") -> Dict[str, Any]:
    """Normalize a retrieved chunk into the citation contract from Step 10."""
    return {
        "case_name": _display_name(case),
        "source": case.get("source") or case.get("source_file") or "",
        "chunk_id": case.get("chunk_id") or "",
        "document_id": case.get("document_id") or "",
        "court": case.get("court") or "",
        "year": case.get("year") or "",
        "judgment_date": case.get("judgment_date") or "",
        "citation": case.get("citation") or "",
        "source_url": case.get("source_url") or "",
        "sections": case.get("sections") or [],
        "articles": case.get("articles") or [],
        "similarity_score": case.get("similarity_score", 0.0),
        "verified": verified,
        "reference": reference,
    }


def _referenced_indices(answer: str) -> List[int]:
    """1-based source numbers the answer points at, in order of appearance."""
    found: List[int] = []
    for match in _SOURCE_MARKER.finditer(answer or ""):
        index = int(match.group(1))
        if index not in found:
            found.append(index)
    for match in _NUMERIC_MARKER.finditer(answer or ""):
        index = int(match.group(1))
        # Skip markers already captured as [SOURCE n] and out-of-range values.
        if index not in found:
            found.append(index)
    return found


def _mentioned_in_answer(answer: str, case: Dict[str, Any]) -> Optional[str]:
    """Return the reference text when the answer names this document."""
    if not answer:
        return None
    haystack = answer.lower()

    for candidate in {case.get("case_name"), _display_name(case)}:
        candidate = (candidate or "").strip()
        if len(candidate) > 6 and candidate.lower() in haystack:
            return candidate

    source = (case.get("source") or "").strip()
    if source and source.lower() in haystack:
        return source

    return None


def verify(
    answer: str,
    retrieved: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Split references into ``(verified_citations, unverified_references)``.

    A reference is verified when it maps to a retrieved chunk. Chunks the answer
    never mentions still appear in ``verified_citations`` only if the caller
    passes ``include_unreferenced=True`` (see ``verify_citations``); by default
    the returned list is limited to what the answer actually cites.
    """
    verified: List[Dict[str, Any]] = []
    unverified: List[Dict[str, Any]] = []

    if not retrieved:
        return verified, unverified

    seen_chunk_ids = set()

    # 1. Explicit [SOURCE n] / [n] markers.
    for index in _referenced_indices(answer or ""):
        if 1 <= index <= len(retrieved):
            case = retrieved[index - 1]
            citation = build_citation(case, True, reference=f"[SOURCE {index}]")
            if citation["chunk_id"] not in seen_chunk_ids:
                seen_chunk_ids.add(citation["chunk_id"])
                verified.append(citation)
        else:
            unverified.append(
                {
                    "reference": f"[SOURCE {index}]",
                    "reason": "reference does not correspond to any retrieved document",
                }
            )

    # 2. Case names / source filenames written out in the answer.
    for case in retrieved:
        reference = _mentioned_in_answer(answer or "", case)
        if reference:
            citation = build_citation(case, True, reference=reference)
            if citation["chunk_id"] not in seen_chunk_ids:
                seen_chunk_ids.add(citation["chunk_id"])
                verified.append(citation)

    return verified, unverified


def verify_citations(
    answer: str,
    retrieved: List[Dict[str, Any]],
    include_unreferenced: bool = True,
) -> Dict[str, Any]:
    """
    Full citation report for an answer.

    ``include_unreferenced`` appends retrieved-but-uncited chunks as evidence of
    what the answer was grounded on. They are explicitly flagged so the UI can
    show them as "supporting sources" rather than as claims the model made.
    """
    verified, unverified = verify(answer, retrieved)

    cited_ids = {citation["chunk_id"] for citation in verified}
    supporting: List[Dict[str, Any]] = []
    if include_unreferenced:
        for case in retrieved:
            chunk_id = case.get("chunk_id") or ""
            if chunk_id and chunk_id not in cited_ids:
                supporting.append(build_citation(case, True, reference="retrieved"))

    return {
        "citations": verified,
        "supporting_sources": supporting,
        "unverified_references": unverified,
        "all_citations_verified": len(unverified) == 0,
        "cited_chunk_ids": sorted(cited_ids),
    }


def build_context_sources(retrieved: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Step 10 response payload: one entry per retrieved chunk, with a verification
    flag. ``verified`` is True because the chunk provably came from the store
    (its id is in the retrieval result) — it is *not* a claim about the answer.
    """
    return [build_citation(case, True, reference="retrieved") for case in retrieved]
