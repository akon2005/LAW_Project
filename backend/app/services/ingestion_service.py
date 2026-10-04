"""
Streaming, resumable ingestion (Steps 3, 5, 37).

The pipeline is deliberately memory-bounded:

    stream → batch → clean → chunk → embed → upsert → checkpoint → next batch

Nothing loads the whole corpus: records are pulled from a Hugging Face
streaming iterator, buffered in batches, written to ChromaDB with deterministic
ids, and a checkpoint is written after each batch so an interrupted run resumes
without re-embedding what was already stored.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from app.core.config import CHECKPOINT_DIR, EMBEDDING_BATCH_SIZE
from app.db.vector_store import VectorStoreError, legal_cases_store
from app.rag.embedding_service import EmbeddingError, embedding_service
from app.services import schema_service
from app.services.chunking import chunk_text
from app.services.dataset_service import (
    MIN_TEXT_LENGTH,
    chunk_index_at_or_below_1,
    clean_text,
    extract_citation,
    extract_court,
    extract_judgment_date,
    extract_parties,
    extract_sections,
    extract_year_from_text,
    get_dataset_config,
)
from app.services.ids import resolve_document_id, stable_chunk_id
from app.services.ingestion_status import IngestionStatus, ingestion_status

logger = logging.getLogger("vidhiveda.ingestion")

# ChromaDB metadata accepts only str/int/float/bool.
_METADATA_SCALARS = (
    "document_id",
    "chunk_id",
    "source",
    "chunk_index",
    "total_pages",
    "case_name",
    "case_name_origin",
    "court",
    "year",
    "judgment_date",
    "citation",
    "petitioner",
    "respondent",
    "dataset",
    "source_url",
    "document_key",
)


def _is_pre_chunked(config: Dict[str, Any]) -> bool:
    """True when the dataset already provides one chunk per record."""
    if "pre_chunked" in config:
        return bool(config["pre_chunked"])
    fields = config.get("fields") or {}
    return bool(fields.get("chunk_index"))


def build_metadata(record: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten a normalized chunk record into ChromaDB-compatible metadata."""
    metadata: Dict[str, Any] = {}
    for field in _METADATA_SCALARS:
        value = record.get(field)
        if value is None or value == "":
            continue
        metadata[field] = value
    for list_field in ("sections", "articles"):
        values = record.get(list_field) or []
        if values:
            metadata[list_field] = ", ".join(str(item) for item in values)
    return metadata


class StreamingIngestor:
    """Stream, normalize, embed and upsert a registered dataset."""

    def __init__(
        self,
        dataset_key: str,
        status_store: Optional[IngestionStatus] = None,
        checkpoint_dir: Optional[Path] = None,
    ) -> None:
        self.dataset_key = dataset_key
        self.config = get_dataset_config(dataset_key)
        self.status = status_store or ingestion_status
        self.checkpoint_dir = Path(checkpoint_dir or CHECKPOINT_DIR)

    # ── Checkpoints ────────────────────────────────────────────────────
    @property
    def checkpoint_path(self) -> Path:
        return self.checkpoint_dir / f"{self.dataset_key}.json"

    def read_checkpoint(self) -> int:
        import json

        try:
            data = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
            return int(data.get("offset") or 0)
        except (OSError, ValueError, TypeError):
            return 0

    def write_checkpoint(self, offset: int) -> None:
        import json

        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        payload = {"offset": int(offset), "updated_at": datetime.now(timezone.utc).isoformat()}
        self.checkpoint_path.write_text(json.dumps(payload), encoding="utf-8")

    def reset_checkpoint(self) -> None:
        try:
            self.checkpoint_path.unlink()
        except OSError:
            pass

    # ── Normalization ──────────────────────────────────────────────────
    def _normalize(self, raw: Dict[str, Any], mapping: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Turn one upstream record into normalized chunk dict(s)."""
        raw_text = schema_service.dot_get(raw, mapping.get("text"))
        if raw_text is None or not str(raw_text).strip():
            return []

        text = clean_text(raw_text)
        if len(text) < MIN_TEXT_LENGTH:
            return []

        original_id = schema_service.dot_get(raw, mapping.get("id"))
        source = schema_service.dot_get(raw, mapping.get("source")) or ""
        source = str(source)
        upstream_chunk_index = schema_service.dot_get(raw, mapping.get("chunk_index"))
        total_pages = schema_service.dot_get(raw, mapping.get("total_pages"))
        document_id, id_origin = resolve_document_id(source, original_id, text)
        document_key = source or f"document:{document_id}"

        # Metadata printed in the document itself (never invented).
        header = chunk_index_at_or_below_1(upstream_chunk_index) if _is_pre_chunked(self.config) else True
        extracted = self._extract(text, allow_bare_dated=header)
        parties = extract_parties(text)
        inferred_year = extracted.pop("year_from_date", None) or extract_year_from_text(text)

        base: Dict[str, Any] = {
            "document_id": document_id,
            "document_id_origin": id_origin,
            "document_key": document_key,
            "source": source,
            "total_pages": int(total_pages) if isinstance(total_pages, (int, float)) else 0,
            "case_name": extracted.get("case_name") or "",
            "case_name_origin": "derived_from_document_text" if extracted.get("case_name") else "unavailable",
            "court": extracted.get("court") or "",
            "year": inferred_year,
            "judgment_date": extracted.get("judgment_date") or "",
            "citation": extracted.get("citation") or "",
            "petitioner": parties.get("petitioner") or "",
            "respondent": parties.get("respondent") or "",
            "sections": extracted.get("sections") or [],
            "articles": extracted.get("articles") or [],
            "source_url": extracted.get("source_url") or "",
            "dataset": self.config["hf_path"],
        }

        chunks: List[Dict[str, Any]] = []
        if _is_pre_chunked(self.config):
            chunk_index = int(upstream_chunk_index) if isinstance(upstream_chunk_index, (int, float)) else 0
            chunks.append(
                {
                    **base,
                    "chunk_index": chunk_index,
                    "chunk_id": stable_chunk_id(document_id, chunk_index),
                    "text": text,
                }
            )
        else:
            for piece in chunk_text(text):
                chunks.append(
                    {
                        **base,
                        "chunk_index": int(piece["chunk_index"]),
                        "chunk_id": stable_chunk_id(document_id, int(piece["chunk_index"])),
                        "text": str(piece["text"]),
                    }
                )
        return chunks

    @staticmethod
    def _extract(text: str, allow_bare_dated: bool) -> Dict[str, Any]:
        """Extract honest metadata from chunk/document text (no placeholders)."""
        extracted: Dict[str, Any] = {}
        court = extract_court(text)
        if court:
            extracted["court"] = court
        iso_date, year = extract_judgment_date(text, allow_bare_dated=allow_bare_dated)
        if iso_date:
            extracted["judgment_date"] = iso_date
        if year:
            extracted["year_from_date"] = year
        citation = extract_citation(text)
        if citation:
            extracted["citation"] = citation
        sections, articles = extract_sections(text)
        if sections:
            extracted["sections"] = sections
        if articles:
            extracted["articles"] = articles
        # Derive a case name only from the cause-title the document prints.
        parties = extract_parties(text)
        if parties.get("petitioner") and parties.get("respondent"):
            extracted["case_name"] = f"{parties['petitioner']} v. {parties['respondent']}"
        return extracted

    # ── Run ────────────────────────────────────────────────────────────
    def run(
        self,
        limit: Optional[int] = None,
        resume: bool = False,
        reset: bool = False,
        batch_size: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Dict[str, Any]:
        batch_size = batch_size or EMBEDDING_BATCH_SIZE
        mode = "resume" if resume else ("limit" if limit else "full")

        if reset:
            logger.warning("[ingestion] Resetting collection %s", self.config["collection"])
            legal_cases_store.reset()

        mapping = schema_service.resolve_field_mapping(self.dataset_key)
        start_offset = offset if offset is not None else (self.read_checkpoint() if resume else 0)
        if not resume and offset is None:
            self.reset_checkpoint()

        self.status.start(self.config["hf_path"], mode)
        self.status.update(last_checkpoint=start_offset)

        processed_documents = 0
        processed_chunks = 0
        failed_records = 0
        fingerprints: set = set()
        buffer: List[Dict[str, Any]] = []
        embedded = 0
        started = time.time()
        raw_read = start_offset

        # Pre-chunked datasets emit one chunk per record; document-level ones
        # expand into several chunks, so we count chunks as we go.
        def flush(batch: List[Dict[str, Any]]) -> int:
            if not batch:
                return 0
            ids = [record["chunk_id"] for record in batch]
            texts = [record["text"] for record in batch]
            metadatas = [build_metadata(record) for record in batch]
            vectors = embedding_service.generate_embeddings(texts, batch_size=batch_size)
            legal_cases_store.insert_documents(
                ids=ids, embeddings=vectors, documents=texts, metadatas=metadatas
            )
            return len(ids)

        fatal_error: Optional[str] = None
        try:
            stream = schema_service.iter_dataset(
                self.dataset_key, skip=start_offset, limit=limit
            )
            for raw in stream:
                raw_read += 1
                try:
                    chunks = self._normalize(raw, mapping)
                except Exception as exc:  # a single bad record must not stop the run
                    failed_records += 1
                    logger.warning("[ingestion] record %s failed: %s", raw_read, exc)
                    continue

                if not chunks:
                    failed_records += 1
                    continue

                new_chunks = []
                for chunk in chunks:
                    fingerprint = (chunk["document_id"], chunk["chunk_index"], chunk["text"][:2000])
                    if fingerprint in fingerprints:
                        continue
                    fingerprints.add(fingerprint)
                    new_chunks.append(chunk)

                if not new_chunks:
                    continue

                processed_documents += 1
                buffer.extend(new_chunks)

                while len(buffer) >= batch_size:
                    batch, buffer = buffer[:batch_size], buffer[batch_size:]
                    embedded += flush(batch)
                    processed_chunks = embedded
                    self.write_checkpoint(raw_read)
                    self.status.update(
                        processed_documents=processed_documents,
                        processed_chunks=processed_chunks,
                        failed_records=failed_records,
                        last_checkpoint=raw_read,
                    )

            if buffer:
                embedded += flush(buffer)
                processed_chunks = embedded
                buffer = []
                self.write_checkpoint(raw_read)
                self.status.update(
                    processed_documents=processed_documents,
                    processed_chunks=processed_chunks,
                    failed_records=failed_records,
                    last_checkpoint=raw_read,
                )

        except EmbeddingError as exc:
            fatal_error = f"Embedding failed: {exc}"
        except VectorStoreError as exc:
            fatal_error = f"Vector store failed: {exc}"
        except Exception as exc:  # dataset/network/stream failure
            fatal_error = f"Ingestion failed: {exc}"

        if fatal_error:
            logger.error("[ingestion] %s", fatal_error)
            self.status.finish(error=fatal_error)
        else:
            self.status.finish()
            self.write_checkpoint(raw_read)

        collection_size: Optional[int] = None
        if not fatal_error or "vector" not in fatal_error.lower():
            try:
                collection_size = legal_cases_store.get_count()
            except VectorStoreError:
                collection_size = None

        return {
            "error": fatal_error,
            "processed_documents": processed_documents,
            "processed_chunks": embedded,
            "failed_records": failed_records,
            "last_checkpoint": raw_read,
            "elapsed": round(time.time() - started, 2),
            "collection_size": collection_size,
        }
