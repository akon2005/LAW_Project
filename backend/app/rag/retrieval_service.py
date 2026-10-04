"""
Real semantic search over the ingested legal corpus (Step 7).

Query → embedding → ChromaDB → top-K real chunks → optional rerank → metadata.

Nothing here is static: every result carries the chunk id, source filename and
similarity score of the row that produced it, so a result can always be traced
back to the corpus (and re-read straight out of ChromaDB).
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional

from app.core.config import CASE_LAW_COLLECTION, LOW_CONFIDENCE_THRESHOLD, RETRIEVAL_TOP_K
from app.db.vector_store import VectorStoreError, legal_cases_store
from app.rag.embedding_service import EmbeddingError, embedding_service
from app.rag.reranker import content_tokens, rerank


logger = logging.getLogger(__name__)

METADATA_LIST_FIELDS = ("sections", "articles")

_SECTION_TOKEN = re.compile(r"\d+[A-Za-z]{0,3}(?:\(\d+\))?")


def _section_tokens(values: Any) -> set:
    """Numeric section tokens ('302', '34(1)') from a list or free text."""
    if values is None:
        return set()
    if isinstance(values, (list, tuple, set)):
        text = " ".join(str(item) for item in values)
    else:
        text = str(values)
    return {token.lower() for token in _SECTION_TOKEN.findall(text)}


def filter_by_sections(results: List[Dict[str, Any]], sections: List[str]) -> List[Dict[str, Any]]:
    """
    Keep only chunks that actually reference one of the requested sections.

    Matching uses the stored ``sections`` metadata first, then the chunk text,
    so a query for ``IPC 302`` cannot silently return unrelated precedents. If
    nothing matches, an empty list is returned rather than a fabricated match.
    """
    wanted = _section_tokens(sections)
    if not wanted:
        return results
    kept: List[Dict[str, Any]] = []
    for record in results:
        stored = _section_tokens(record.get("sections"))
        if stored & wanted:
            kept.append(record)
            continue
        if _section_tokens((record.get("text") or "")[:6000]) & wanted:
            kept.append(record)
    return kept

# Dense similarity alone is a weak signal: an unrelated query still scores
# ~0.30 with MiniLM because every English sentence is somewhat "close" in that
# space. So a *marginal* top score is additionally required to share at least
# one content word with the query, otherwise the result is reported as
# low-confidence rather than dressed up as a match (Step 11).
LEXICAL_GATE_MARGIN = 0.15


def _topical_overlap(query: str, text: str) -> float:
    """Share of the query's content words that appear in ``text`` (0..1)."""
    query_terms = set(content_tokens(query))
    if not query_terms:
        return 0.0
    document_terms = set(content_tokens((text or "")[:6000]))
    return len(query_terms & document_terms) / len(query_terms)


class RetrievalError(RuntimeError):
    """Raised when the query cannot be embedded or the store cannot be read."""


def _as_list(value: Any) -> List[str]:
    """ChromaDB metadata cannot hold lists, so lists are stored comma-joined."""
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [part.strip() for part in re.split(r"\s*,\s*", str(value)) if part.strip()]


def _to_similarity(distance: Any) -> float:
    """
    ChromaDB cosine space returns ``distance = 1 - cosine_similarity``.

    Written defensively because a store created without ``hnsw:space=cosine``
    returns squared L2 distances instead, which would otherwise read as
    artificially high similarity.
    """
    try:
        value = float(distance)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, 1.0 - value))


class RetrievalService:
    def retrieve(
        self,
        query: str,
        top_k: int = RETRIEVAL_TOP_K,
        filters: Optional[Dict[str, Any]] = None,
        use_reranker: Optional[bool] = None,
        sections: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Retrieve the top-K chunks most similar to ``query``."""
        start = time.time()
        top_k = max(1, int(top_k or RETRIEVAL_TOP_K))
        # A section filter is applied after retrieval, so fetch a wider pool to
        # avoid losing all candidates before the post-filter runs.
        fetch_k = max(top_k, top_k * 4) if sections else top_k

        if not query or not query.strip():
            return {
                "query": query,
                "results": [],
                "is_low_confidence": True,
                "low_confidence_reason": "empty query",
                "best_similarity": 0.0,
                "topical_overlap": 0.0,
                "retrieval_time": 0.0,
                "reranked": False,
                "candidate_count": 0,
                "collection": CASE_LAW_COLLECTION,
            }

        # 1. Query → embedding
        try:
            query_embedding = embedding_service.embed_query(query)
        except EmbeddingError as exc:
            raise RetrievalError(str(exc)) from exc

        # 2. Embedding → ChromaDB
        try:
            raw = legal_cases_store.search(
                query_embedding=query_embedding, top_k=fetch_k, filters=filters
            )
        except VectorStoreError as exc:
            raise RetrievalError(str(exc)) from exc

        ids = (raw.get("ids") or [[]])[0]
        metadatas = (raw.get("metadatas") or [[]])[0]
        documents = (raw.get("documents") or [[]])[0]
        distances = (raw.get("distances") or [[]])[0]

        results: List[Dict[str, Any]] = []
        for index, chunk_id in enumerate(ids):
            metadata = dict(metadatas[index]) if index < len(metadatas) and metadatas[index] else {}
            document = documents[index] if index < len(documents) else ""
            distance = distances[index] if index < len(distances) else None
            similarity = _to_similarity(distance)

            record: Dict[str, Any] = {
                **metadata,
                "chunk_id": metadata.get("chunk_id") or chunk_id,
                "document_id": metadata.get("document_id") or "",
                "chunk_index": metadata.get("chunk_index", 0),
                "total_pages": metadata.get("total_pages", 0),
                "case_name": metadata.get("case_name") or "",
                "court": metadata.get("court") or "",
                "year": metadata.get("year") or "",
                "judgment_date": metadata.get("judgment_date") or "",
                "citation": metadata.get("citation") or "",
                "petitioner": metadata.get("petitioner") or "",
                "respondent": metadata.get("respondent") or "",
                "source": metadata.get("source") or metadata.get("source_file") or "",
                "source_url": metadata.get("source_url") or "",
                "dataset": metadata.get("dataset") or "",
                "text": document or "",
                "similarity_score": round(similarity, 4),
                "distance": distance,
            }
            for field in METADATA_LIST_FIELDS:
                record[field] = _as_list(metadata.get(field))
            record.setdefault("rerank_method", "dense")
            results.append(record)

        # 2b. Section filter (Step 12C) — applied only when the caller asks for
        # specific statutory sections, and never padded with unrelated rows.
        if sections:
            results = filter_by_sections(results, sections)

        # 3. Optional reranking (Step 8)
        reranked = False
        if results and (use_reranker if use_reranker is not None else True):
            before = [item["chunk_id"] for item in results]
            results = rerank(query, results, top_k=top_k, enabled=use_reranker)
            after = [item["chunk_id"] for item in results]
            reranked = before != after or (results and results[0].get("rerank_method") != "dense")

        best_similarity = max(
            (float(item.get("similarity_score") or 0.0) for item in results), default=-1.0
        )
        best_similarity = max(0.0, best_similarity)
        topical_overlap = _topical_overlap(query, results[0].get("text", "")) if results else 0.0

        if not results:
            is_low_confidence = True
            low_confidence_reason = "no documents retrieved"
        elif best_similarity < LOW_CONFIDENCE_THRESHOLD:
            is_low_confidence = True
            low_confidence_reason = (
                f"best similarity {best_similarity:.3f} is below the "
                f"{LOW_CONFIDENCE_THRESHOLD:.2f} threshold"
            )
        elif (
            best_similarity < LOW_CONFIDENCE_THRESHOLD + LEXICAL_GATE_MARGIN
            and topical_overlap == 0.0
        ):
            is_low_confidence = True
            low_confidence_reason = (
                "top result shares no content word with the query (marginal "
                f"similarity {best_similarity:.3f})"
            )
        else:
            is_low_confidence = False
            low_confidence_reason = None

        return {
            "query": query,
            "results": results,
            "is_low_confidence": is_low_confidence,
            "low_confidence_reason": low_confidence_reason,
            "best_similarity": best_similarity,
            "topical_overlap": round(topical_overlap, 4),
            "retrieval_time": round(time.time() - start, 4),
            "reranked": reranked,
            "candidate_count": len(results),
            "sections_filter": sections or [],
            "collection": CASE_LAW_COLLECTION,
        }

    def corpus_size(self) -> int:
        """Number of chunks currently indexed."""
        try:
            return legal_cases_store.get_count()
        except VectorStoreError:
            return 0


retrieval_service = RetrievalService()
