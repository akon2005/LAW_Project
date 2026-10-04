"""
Result re-ranking (Step 8).

The pipeline keeps three ranking stages apart so each can be enabled on its own:

    dense retrieval (ChromaDB)  →  lexical (BM25)  →  cross-encoder  →  top-K

Reranking is **off by default** (``USE_RERANKER=false``), in which case dense
retrieval order is returned untouched — the first implementation the spec asks
for. Turning it on adds a dependency-free BM25 pass and, if the cross-encoder
model is available, a semantic rerank. If either stage fails, the function
degrades to the dense order instead of failing the request.
"""
from __future__ import annotations

import logging
import math
import re
from collections import Counter
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from app.core.config import RERANK_CANDIDATES, RERANKER_MODEL, USE_RERANKER

load_dotenv()

logger = logging.getLogger(__name__)

_TOKEN = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "the", "a", "an", "of", "and", "or", "to", "in", "on", "for", "with",
    "under", "is", "are", "was", "were", "be", "by", "as", "at", "from",
    "that", "this", "it", "its", "his", "her", "their", "which", "who",
}

_cross_encoder = None
_cross_encoder_failed = False


def content_tokens(text: str) -> List[str]:
    """Lowercased content words (stopwords and 1-character tokens removed)."""
    return [
        token
        for token in _TOKEN.findall((text or "").lower())
        if len(token) > 1 and token not in _STOPWORDS
    ]


# Internal alias kept short for the scoring code below.
_tokenize = content_tokens


def bm25_scores(query: str, documents: List[str], k1: float = 1.5, b: float = 0.75) -> List[float]:
    """
    Small self-contained BM25 implementation.

    Kept in-tree (no ``rank_bm25`` dependency) because the corpus documents are
    already in memory at this point and the scoring formula is short.
    """
    query_terms = _tokenize(query)
    if not query_terms or not documents:
        return [0.0] * len(documents)

    tokenized = [_tokenize(doc) for doc in documents]
    lengths = [len(tokens) for tokens in tokenized]
    avg_length = sum(lengths) / len(lengths) if lengths else 0.0

    doc_freq: Counter = Counter()
    for tokens in tokenized:
        for term in set(tokens):
            doc_freq[term] += 1

    total_docs = len(tokenized)
    scores: List[float] = []
    for tokens, length in zip(tokenized, lengths):
        term_freq = Counter(tokens)
        score = 0.0
        for term in query_terms:
            frequency = term_freq.get(term, 0)
            if not frequency:
                continue
            idf = math.log(1 + (total_docs - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
            denominator = frequency + k1 * (1 - b + b * (length / avg_length if avg_length else 1))
            score += idf * (frequency * (k1 + 1)) / denominator
        scores.append(score)
    return scores


def _get_cross_encoder():
    """Load the cross-encoder once; remember failure so we only warn once."""
    global _cross_encoder, _cross_encoder_failed
    if _cross_encoder is not None or _cross_encoder_failed:
        return _cross_encoder
    try:
        from sentence_transformers import CrossEncoder

        logger.info("[reranker] Loading cross-encoder %s", RERANKER_MODEL)
        _cross_encoder = CrossEncoder(RERANKER_MODEL)
    except Exception as exc:
        _cross_encoder_failed = True
        logger.warning(
            "[reranker] Cross-encoder unavailable (%s); using BM25 reranking only.", exc
        )
    return _cross_encoder


def is_enabled() -> bool:
    return bool(USE_RERANKER)


def rerank(
    query: str,
    candidates: List[Dict[str, Any]],
    top_k: Optional[int] = None,
    enabled: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """
    Reorder retrieved candidates.

    Each candidate must carry ``text`` (or ``retrieval_document``) and
    ``similarity_score``. Reranking annotates the dicts with
    ``dense_score``/``lexical_score``/``rerank_score`` and ``rerank_method`` so
    the UI can explain where the final order came from.
    """
    if not candidates:
        return []

    should_rerank = is_enabled() if enabled is None else enabled
    if not should_rerank:
        result = [dict(candidate) for candidate in candidates]
        for candidate in result:
            candidate.setdefault("rerank_method", "dense")
        return result[:top_k] if top_k else result

    candidates = candidates[: max(RERANK_CANDIDATES, len(candidates) if top_k is None else top_k)]
    result = [dict(candidate) for candidate in candidates]

    texts = [
        candidate.get("text") or candidate.get("retrieval_document") or ""
        for candidate in result
    ]
    dense_scores = [float(candidate.get("similarity_score") or 0.0) for candidate in result]

    # Stage 2 — lexical (BM25), normalized to 0..1 against the best hit.
    lexical_raw = bm25_scores(query, texts)
    lexical_max = max(lexical_raw) if lexical_raw else 0.0
    lexical_scores = [score / lexical_max if lexical_max > 0 else 0.0 for score in lexical_raw]

    # Stage 3 — cross-encoder, when the model is installed.
    cross_scores: Optional[List[float]] = None
    encoder = _get_cross_encoder()
    if encoder is not None:
        try:
            pairs = [(query, text[:2000]) for text in texts]
            cross_scores = [float(score) for score in encoder.predict(pairs)]
        except Exception as exc:
            logger.warning("[reranker] Cross-encoder scoring failed: %s", exc)
            cross_scores = None

    for index, candidate in enumerate(result):
        candidate["dense_score"] = round(dense_scores[index], 4)
        candidate["lexical_score"] = round(lexical_scores[index], 4)
        if cross_scores is not None:
            candidate["rerank_score"] = round(cross_scores[index], 4)
            candidate["rerank_method"] = "dense+bm25+cross-encoder"
            combined = 0.6 * cross_scores[index] + 0.25 * dense_scores[index] + 0.15 * lexical_scores[index]
        else:
            candidate["rerank_score"] = round(
                0.7 * dense_scores[index] + 0.3 * lexical_scores[index], 4
            )
            candidate["rerank_method"] = "dense+bm25"
        candidate["combined_score"] = round(combined, 4)

    result.sort(key=lambda item: item.get("combined_score", 0.0), reverse=True)
    return result[:top_k] if top_k else result
