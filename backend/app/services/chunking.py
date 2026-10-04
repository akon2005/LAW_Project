"""
Legal-aware chunking (Step 8).

Chunking a judgment into arbitrary fixed windows destroys the structure that
makes it usable as legal evidence. This module prefers, in order:

  1. paragraph boundaries (blank-line separated blocks);
  2. sentence boundaries inside an over-long paragraph;
  3. a hard character cut as a last resort.

Overlap is applied between adjacent chunks so a sentence split across a
boundary is still retrievable. The unit is characters because the default
embedding model (``all-MiniLM-L6-v2``) is character/BPE based; the strategy is
configurable through ``CHUNK_STRATEGY``.
"""
from __future__ import annotations

import re
from typing import Dict, List

from app.core.config import CHUNK_OVERLAP, CHUNK_SIZE, CHUNK_STRATEGY

_PARAGRAPH = re.compile(r"\n\s*\n+")
# Sentence boundary: terminator + whitespace + capital/number. Kept simple and
# conservative — an over-eager splitter would break citations.
_SENTENCE = re.compile(r"(?<=[.!?;:])\s+(?=[A-Z0-9(\[])")


def _split_paragraphs(text: str) -> List[str]:
    return [part.strip() for part in _PARAGRAPH.split(text or "") if part.strip()]


def _split_sentences(paragraph: str) -> List[str]:
    return [part.strip() for part in _SENTENCE.split(paragraph) if part.strip()]


def _pack_units(units: List[str], size: int, overlap: int) -> List[str]:
    """Greedily pack units into chunks of at most ``size`` characters."""
    chunks: List[str] = []
    current = ""
    for unit in units:
        candidate = f"{current} {unit}".strip() if current else unit
        if len(candidate) <= size:
            current = candidate
            continue
        if current.strip():
            chunks.append(current.strip())
        current = unit
    if current.strip():
        chunks.append(current.strip())

    # Post-pass overlap: seed each chunk with the tail of the previous one so a
    # sentence split across a boundary stays retrievable.
    if overlap > 0 and len(chunks) > 1:
        overlapped = [chunks[0]]
        for previous, current_chunk in zip(chunks, chunks[1:]):
            prefix = previous[-overlap:].strip()
            if prefix and not current_chunk.startswith(prefix):
                overlapped.append(f"{prefix} {current_chunk}".strip())
            else:
                overlapped.append(current_chunk)
        chunks = overlapped
    return chunks


def _hard_windows(text: str, size: int, overlap: int) -> List[str]:
    step = max(1, size - overlap)
    return [text[i : i + size] for i in range(0, len(text), step)]


def chunk_text(
    text: str,
    strategy: str = CHUNK_STRATEGY,
    size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> List[Dict[str, object]]:
    """
    Split ``text`` into legal-aware chunks.

    Returns a list of ``{"chunk_index": int, "text": str}`` in reading order.
    Empty or whitespace-only input returns an empty list.
    """
    clean = (text or "").strip()
    if not clean:
        return []
    size = max(100, int(size))
    overlap = max(0, min(int(overlap), size // 2))

    if strategy not in {"legal_aware", "fixed"}:
        strategy = "legal_aware"

    if strategy == "fixed":
        pieces = _hard_windows(clean, size, overlap)
        return [{"chunk_index": i, "text": piece} for i, piece in enumerate(pieces) if piece.strip()]

    # 1-2. Paragraphs, falling back to sentences for over-long paragraphs.
    units: List[str] = []
    for paragraph in _split_paragraphs(clean):
        if len(paragraph) <= size:
            units.append(paragraph)
            continue
        sentences = _split_sentences(paragraph)
        # A single unbroken wall of text still has to be cut somewhere.
        if len(sentences) == 1:
            units.extend(_hard_windows(paragraph, size, overlap))
        else:
            units.extend(sentences)

    # 3. Pack into size-bounded chunks with overlap between neighbours.
    chunks = _pack_units(units, size, overlap)
    return [{"chunk_index": i, "text": chunk} for i, chunk in enumerate(chunks) if chunk.strip()]
