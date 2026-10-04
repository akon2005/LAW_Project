"""
Persistent ChromaDB vector store (Step 5).

Two collections, deliberately separate:

* ``CASE_LAW_COLLECTION``  — real case-law chunks (the RAG corpus)
* ``STATUTE_COLLECTION``   — reserved for statute data; never mixed with case law

IDs are deterministic (``<document_id>_<chunk_index>``) and inserts use
``upsert``, so re-running the ingestion script updates records in place instead
of duplicating them or generating new random ids.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional

try:
    import chromadb
except ImportError:
    chromadb = None
from dotenv import load_dotenv

from app.core.config import CASE_LAW_COLLECTION, STATUTE_COLLECTION, VECTOR_STORE_DIR

load_dotenv()

logger = logging.getLogger(__name__)

# ChromaDB accepts at most 5461 ids per call; stay well below it.
WRITE_BATCH_SIZE = 500


class VectorStoreError(RuntimeError):
    """Raised when ChromaDB cannot be opened, written or queried."""


class VectorStore:
    def __init__(self, collection_name: str = CASE_LAW_COLLECTION, path: Optional[str] = None):
        self.collection_name = collection_name
        try:
            if chromadb is None:
                raise ImportError("chromadb is not installed")
            self.client = chromadb.PersistentClient(path=path or VECTOR_STORE_DIR)
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as exc:
            logger.warning(
                f"Vector store unavailable (Legal retrieval service is not configured for production): {exc}"
            )
            self.client = None
            self.collection = None

    # ── Writes ─────────────────────────────────────────────────────────
    def insert_documents(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        batch_size: int = WRITE_BATCH_SIZE,
    ) -> None:
        """
        Upsert chunks. Re-running ingestion with the same ids overwrites the
        existing rows rather than adding duplicates.
        """
        if self.collection is None:
            raise VectorStoreError("Legal retrieval service is not configured for production.")
        if not ids:
            return
        for start in range(0, len(ids), batch_size):
            end = start + batch_size
            try:
                self.collection.upsert(
                    ids=ids[start:end],
                    embeddings=embeddings[start:end],
                    documents=documents[start:end],
                    metadatas=metadatas[start:end],
                )
            except Exception as exc:
                raise VectorStoreError(
                    f"Upsert failed for '{self.collection_name}' "
                    f"(rows {start}-{end}): {exc}"
                ) from exc

    def update_metadata(self, ids: List[str], metadatas: List[Dict[str, Any]]) -> None:
        """Update metadata in place, leaving stored documents/vectors alone."""
        if self.collection is None:
            raise VectorStoreError("Legal retrieval service is not configured for production.")
        for start in range(0, len(ids), WRITE_BATCH_SIZE):
            end = start + WRITE_BATCH_SIZE
            try:
                self.collection.update(
                    ids=ids[start:end], metadatas=metadatas[start:end]
                )
            except Exception as exc:
                raise VectorStoreError(f"Metadata update failed: {exc}") from exc

    # ── Reads ──────────────────────────────────────────────────────────
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Semantic search. ``filters`` is a plain ``{metadata_key: value}`` dict;
        unsupported keys are dropped by ``build_where`` so a filter that does
        not match the stored schema can never silently empty the result set.
        """
        if self.collection is None:
            raise VectorStoreError("Legal retrieval service is not configured for production.")
        kwargs: Dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": max(1, int(top_k)),
            "include": ["metadatas", "documents", "distances"],
        }
        where = self.build_where(self.collection, filters)
        if where:
            kwargs["where"] = where

        try:
            results = self.collection.query(**kwargs)
        except Exception as exc:
            if where:
                logger.warning(
                    "[vectorstore] Filtered query failed (%s); retrying unfiltered.", exc
                )
                kwargs.pop("where", None)
                try:
                    results = self.collection.query(**kwargs)
                except Exception as inner:
                    raise VectorStoreError(f"ChromaDB query failed: {inner}") from inner
            else:
                raise VectorStoreError(f"ChromaDB query failed: {exc}") from exc

        # A filter that matches nothing is not an error, but it is worth
        # surfacing: callers decide whether to retry without constraints.
        if where and not (results.get("ids") and results["ids"][0]):
            return {"ids": [[]], "metadatas": [[]], "documents": [[]], "distances": [[]]}
        return results

    def get_rows(
        self, limit: Optional[int] = None, offset: int = 0, include_documents: bool = True
    ) -> Dict[str, Any]:
        """Iterate stored rows (used by the metadata enrichment pass)."""
        if self.collection is None:
            raise VectorStoreError("Legal retrieval service is not configured for production.")
        include = ["metadatas"]
        if include_documents:
            include.append("documents")
        try:
            return self.collection.get(include=include, limit=limit, offset=offset)
        except Exception as exc:
            raise VectorStoreError(f"Could not read '{self.collection_name}': {exc}") from exc

    def get_metadatas(self, batch_size: int = 2000) -> List[Dict[str, Any]]:
        """All row ids + metadatas, read in batches to bound memory."""
        total = self.get_count()
        rows: List[Dict[str, Any]] = []
        for offset in range(0, total, batch_size):
            result = self.collection.get(
                include=["metadatas"], limit=batch_size, offset=offset
            )
            ids = result.get("ids") or []
            metadatas = result.get("metadatas") or []
            for index, row_id in enumerate(ids):
                rows.append(
                    {"id": row_id, "metadata": metadatas[index] if index < len(metadatas) else {}}
                )
        return rows

    def get_count(self) -> int:
        if self.collection is None:
            return 0
        try:
            return int(self.collection.count())
        except Exception as exc:
            raise VectorStoreError(f"Could not count '{self.collection_name}': {exc}") from exc

    # ── Filters ────────────────────────────────────────────────────────
    @staticmethod
    def supported_filter_keys(collection) -> set:
        """Metadata keys actually present in the collection."""
        try:
            sample = collection.get(include=["metadatas"], limit=1)
            if sample.get("metadatas"):
                return set(sample["metadatas"][0].keys())
        except Exception:
            pass
        return set()

    @classmethod
    def build_where(cls, collection, filters: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Translate ``{key: value}`` into a ChromaDB ``where`` clause, keeping only
        keys the collection actually stores. Ranges use
        ``{"year_from": ..., "year_to": ...}`` for convenience.
        """
        if not filters:
            return None

        supported = cls.supported_filter_keys(collection)
        conditions: List[Dict[str, Any]] = []

        for key, value in filters.items():
            if value is None or value == "":
                continue

            if key == "year_from":
                if "year" in supported:
                    conditions.append({"year": {"$gte": int(value)}})
                continue
            if key == "year_to":
                if "year" in supported:
                    conditions.append({"year": {"$lte": int(value)}})
                continue
            if key == "year":
                if "year" in supported:
                    conditions.append({"year": {"$eq": int(value)}})
                continue
            # Only exact-match keys that exist in the stored schema.
            if key in supported:
                conditions.append({key: {"$eq": value}})

        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    def reset(self) -> None:
        """Delete and recreate the collection. Destructive."""
        if self.client is None:
            raise VectorStoreError("Legal retrieval service is not configured for production.")
        try:
            self.client.delete_collection(self.collection_name)
        except Exception:
            pass
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name, metadata={"hnsw:space": "cosine"}
        )


# ── Shared instances ───────────────────────────────────────────────────
# Instantiated lazily: importing this module must not fail when the vector
# store directory does not exist yet (e.g. before the first ingestion run).
_legal_cases_store: Optional[VectorStore] = None
_statutes_store: Optional[VectorStore] = None


def get_legal_cases_store() -> VectorStore:
    global _legal_cases_store
    if _legal_cases_store is None:
        _legal_cases_store = VectorStore(CASE_LAW_COLLECTION)
    return _legal_cases_store


def get_statutes_store() -> VectorStore:
    global _statutes_store
    if _statutes_store is None:
        _statutes_store = VectorStore(STATUTE_COLLECTION)
    return _statutes_store


class _LazyStore:
    """Attribute proxy so ``legal_cases_store.search(...)`` still works."""

    def __init__(self, factory):
        self._factory = factory
        self._store: Optional[VectorStore] = None

    def _resolve(self) -> VectorStore:
        if self._store is None:
            self._store = self._factory()
        return self._store

    def __getattr__(self, item):
        return getattr(self._resolve(), item)


legal_cases_store = _LazyStore(get_legal_cases_store)
statutes_store = _LazyStore(get_statutes_store)
