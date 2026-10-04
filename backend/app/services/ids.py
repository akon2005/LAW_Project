"""
Deterministic document and chunk identifiers (Step 7).

The same source document must always produce the same ``document_id`` so that
re-ingestion is idempotent and citations stay stable across runs.

Preference order:
  1. the upstream record id, when the dataset provides one (already stable);
  2. otherwise ``sha256(source + original_id + normalized_text)``.
"""
from __future__ import annotations

import hashlib
from typing import Optional, Tuple


def stable_document_id(
    source: Optional[str], original_id: Optional[str], normalized_text: Optional[str]
) -> str:
    """Deterministic sha256 id over the source, original id and text."""
    payload = "\x1f".join(
        [str(source or ""), str(original_id or ""), str(normalized_text or "")]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def resolve_document_id(
    source: Optional[str], original_id: Optional[str], normalized_text: Optional[str]
) -> Tuple[str, str]:
    """
    Return ``(document_id, origin)`` where origin is ``upstream_id`` or
    ``sha256``. The upstream id wins when present so existing indexed corpora
    keep their ids; a hash is only derived when the dataset exposes no id.
    """
    if original_id is not None and str(original_id).strip():
        return str(original_id).strip(), "upstream_id"
    return stable_document_id(source, original_id, normalized_text), "sha256"


def stable_chunk_id(document_id: str, chunk_index: int) -> str:
    """Deterministic ``<document_id>_<chunk_index>`` chunk id."""
    return f"{document_id}_{int(chunk_index)}"
