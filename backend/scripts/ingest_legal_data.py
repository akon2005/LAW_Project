#!/usr/bin/env python
"""
VIDHIVEDA legal data ingestion (Step 6).

    python scripts/ingest_legal_data.py                  # index the whole corpus
    python scripts/ingest_legal_data.py --max-records 500 # dev/test subset
    python scripts/ingest_legal_data.py --enrich-only     # refresh metadata, no re-embedding
    python scripts/ingest_legal_data.py --inspect         # list registered datasets
    python scripts/ingest_legal_data.py --skip-existing   # only embed chunks not already stored

The script loads the real Hugging Face dataset, validates every record, cleans
the text, derives stable chunk ids, embeds in batches and upserts into the
persistent ChromaDB collection. It never writes placeholder or synthetic legal
content, and it never duplicates rows on re-run: ids are deterministic and
inserts use upsert.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Set

# Allow `python scripts/ingest_legal_data.py` from the backend directory.
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import CASE_LAW_COLLECTION, EMBEDDING_BATCH_SIZE  # noqa: E402
from app.db.vector_store import VectorStoreError, legal_cases_store  # noqa: E402
from app.rag.embedding_service import EmbeddingError, embedding_service  # noqa: E402
from app.services.dataset_service import (  # noqa: E402
    DATASET_REGISTRY,
    PRIMARY_DATASET,
    DatasetLoadError,
    chunk_index_at_or_below_1,
    extract_parties,
    extract_court,
    extract_judgment_date,
    extract_citation,
    extract_sections,
    extract_year_from_text,
    format_validation_report,
    get_dataset_config,
    list_datasets,
    load_validated_dataset,
    write_validation_report,
)

logger = logging.getLogger("vidhiveda.ingest")

# ChromaDB metadata values must be str/int/float/bool — never None, never a list.
METADATA_FIELDS = (
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


def build_chroma_metadata(record: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten a normalized record into ChromaDB-compatible metadata."""
    metadata: Dict[str, Any] = {}
    for field in METADATA_FIELDS:
        value = record.get(field)
        if value is None or value == "":
            continue
        metadata[field] = value

    # Lists are stored comma-joined (ChromaDB metadata cannot hold lists) and
    # re-split by the retrieval service.
    sections = record.get("sections") or []
    if sections:
        metadata["sections"] = ", ".join(str(item) for item in sections)
    articles = record.get("articles") or []
    if articles:
        metadata["articles"] = ", ".join(str(item) for item in articles)

    return metadata


def existing_chunk_ids() -> Set[str]:
    """Ids already present in the collection (used by --skip-existing)."""
    try:
        rows = legal_cases_store.get_metadatas()
        return {row["id"] for row in rows}
    except VectorStoreError as exc:
        logger.warning("Could not read existing ids (%s); embedding everything.", exc)
        return set()


def ingest(
    dataset_key: str,
    max_records: int,
    batch_size: int,
    skip_existing: bool,
    reset: bool,
) -> int:
    started = time.time()
    config = get_dataset_config(dataset_key)

    print("VIDHIVEDA Legal Data Ingestion")
    print("-" * 32)
    print(f"Dataset:      {config['hf_path']}")
    print(f"Collection:   {config['collection']}")
    print(f"Kind:         {config['kind']}")
    print(f"Max records:  {max_records if max_records > 0 else 'all'}")
    print()

    # 1-3. Load, clean and validate (validation report is written to disk).
    try:
        records, report = load_validated_dataset(
            dataset_key=dataset_key,
            max_records=max_records if max_records > 0 else None,
            split=config["split"],
        )
    except DatasetLoadError as exc:
        print(f"\nERROR: {exc}")
        print(
            "Check network access / Hugging Face availability, then re-run "
            "`python scripts/ingest_legal_data.py`."
        )
        return 2

    print(format_validation_report(report))
    print()

    if not records:
        print("No valid records to ingest. Nothing was written. Exiting.")
        return 1

    if reset:
        print(f"Resetting collection '{CASE_LAW_COLLECTION}' (--reset)...")
        legal_cases_store.reset()

    # 4. Stable ids + de-duplication against the existing collection.
    already_stored = existing_chunk_ids() if skip_existing else set()
    pending = [
        record for record in records if record["chunk_id"] not in already_stored
    ]
    if skip_existing:
        print(
            f"Already stored: {len(records) - len(pending)} chunks "
            f"(skipped) · to embed: {len(pending)}"
        )

    if not pending:
        finalise(report, embedded=0, total_in_store=legal_cases_store.get_count(), elapsed=time.time() - started)
        return 0

    # 5-8. Embed in batches, upsert documents + metadata.
    embedded = 0
    try:
        from tqdm import tqdm

        progress = tqdm(range(0, len(pending), batch_size), unit="batch")
    except ImportError:  # tqdm is optional
        progress = range(0, len(pending), batch_size)

    try:
        for start in progress:
            batch = pending[start : start + batch_size]
            texts = [record["text"] for record in batch]
            ids = [record["chunk_id"] for record in batch]
            metadatas = [build_chroma_metadata(record) for record in batch]

            embeddings = embedding_service.generate_embeddings(texts, batch_size=batch_size)
            legal_cases_store.insert_documents(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
            )
            embedded += len(ids)
            if hasattr(progress, "set_postfix"):
                progress.set_postfix(stored=embedded)
    except EmbeddingError as exc:
        print(f"\nERROR: embedding failed: {exc}")
        print(f"{embedded} chunks were stored before the failure; re-run to resume.")
        return 3
    except VectorStoreError as exc:
        print(f"\nERROR: ChromaDB write failed: {exc}")
        return 4

    finalise(report, embedded=embedded, total_in_store=legal_cases_store.get_count(), elapsed=time.time() - started)
    return 0


def enrich_existing_metadata(batch_size: int = 2000) -> int:
    """
    Re-derive metadata for chunks already in the collection — no re-embedding.

    Chunk text is read back out of ChromaDB, fields are extracted from it (with
    document-level propagation, so a cause-title on chunk 1 also labels chunks
    2..n of the same PDF), and only the metadata rows are updated. Vectors and
    document text are untouched.
    """
    print("VIDHIVEDA — Metadata Enrichment (no re-embedding)")
    print("-" * 32)

    store = legal_cases_store
    total = store.get_count()
    if total == 0:
        print(f"Collection '{CASE_LAW_COLLECTION}' is empty. Nothing to enrich.")
        return 1
    print(f"Collection: {CASE_LAW_COLLECTION} · chunks: {total}")

    # Read every row (id, metadata, text) in batches.
    rows: List[Dict[str, Any]] = []
    for offset in range(0, total, batch_size):
        page = store.collection.get(
            include=["metadatas", "documents"], limit=batch_size, offset=offset
        )
        ids = page.get("ids") or []
        metadatas = page.get("metadatas") or []
        documents = page.get("documents") or []
        for index, row_id in enumerate(ids):
            rows.append(
                {
                    "id": row_id,
                    "metadata": metadatas[index] if index < len(metadatas) else {},
                    "text": documents[index] if index < len(documents) else "",
                }
            )
    print(f"Read {len(rows)} rows from the vector store.")

    # Document-level aggregation: key on the source PDF, falling back to the
    # per-chunk document id when the upstream source name is missing.
    #
    # Chunks are visited in chunk_index order so the cause-title chunk (index 1)
    # is merged first and wins each field. The store returns rows in arbitrary
    # order, and merging in that order previously let a body-text instrument date
    # ("a mortgage bond, dated 11-1-1893") override the real judgment date.
    doc_fields: Dict[str, Dict[str, Any]] = {}
    ordered_rows = sorted(
        rows, key=lambda row: ((row["metadata"] or {}).get("chunk_index") or 0)
    )
    for row in ordered_rows:
        metadata = row["metadata"] or {}
        key = metadata.get("source") or f"document:{metadata.get('document_id', row['id'])}"
        text = row["text"] or ""
        target = doc_fields.setdefault(key, {})
        is_header = chunk_index_at_or_below_1(metadata.get("chunk_index"))

        parties = extract_parties(text)
        court = extract_court(text)
        iso_date, year_from_date = extract_judgment_date(
            text, allow_bare_dated=is_header
        )
        citation = extract_citation(text)
        sections, articles = extract_sections(text)

        for field, value in (("petitioner", parties.get("petitioner")), ("respondent", parties.get("respondent"))):
            if value and not target.get(field):
                target[field] = value
        if court and not target.get("court"):
            target["court"] = court
        # Only the opening chunk (or an explicit judgment-date marker) may set a
        # document's date; see extract_judgment_date.
        if (is_header or iso_date) and iso_date and not target.get("judgment_date"):
            target["judgment_date"] = iso_date
        if (is_header or year_from_date) and year_from_date and not target.get("year_from_date"):
            target["year_from_date"] = year_from_date
        if citation and not target.get("citation"):
            target["citation"] = citation
        if sections:
            merged = target.setdefault("sections", [])
            for item in sections:
                if item not in merged:
                    merged.append(item)
        if articles:
            merged = target.setdefault("articles", [])
            for item in articles:
                if item not in merged:
                    merged.append(item)

    # Build updated metadata per row.
    updated_ids: List[str] = []
    updated_metadatas: List[Dict[str, Any]] = []
    changed = 0

    for row in rows:
        metadata = dict(row["metadata"] or {})
        key = metadata.get("source") or f"document:{metadata.get('document_id', row['id'])}"
        derived = doc_fields.get(key, {})
        text = row["text"] or ""
        before = dict(metadata)

        is_header = chunk_index_at_or_below_1(metadata.get("chunk_index"))

        # Chunk-level parties win when the chunk itself names them.
        parties = extract_parties(text)
        petitioner = parties.get("petitioner") or derived.get("petitioner") or ""
        respondent = parties.get("respondent") or derived.get("respondent") or ""
        if petitioner:
            metadata["petitioner"] = petitioner
        if respondent:
            metadata["respondent"] = respondent

        court = extract_court(text) or derived.get("court") or ""
        if court:
            metadata["court"] = court

        iso_date, year_from_date = extract_judgment_date(text, allow_bare_dated=is_header)
        if not is_header:
            # A body-text date is not this judgment's date.
            iso_date, year_from_date = None, None
        judgment_date = iso_date or derived.get("judgment_date") or ""
        if judgment_date:
            metadata["judgment_date"] = judgment_date

        year = year_from_date or derived.get("year_from_date")
        if not year:
            # Prefer an explicit judgment date; only then fall back to the stored
            # value. Values that no longer pass date validation are dropped rather
            # than kept as if they were a judgment year.
            existing_year = metadata.get("year")
            year = int(existing_year) if existing_year else None
        if year:
            metadata["year"] = int(year)

        citation = extract_citation(text) or derived.get("citation") or ""
        if citation:
            metadata["citation"] = citation

        sections, articles = extract_sections(text)
        merged_sections = list(dict.fromkeys((derived.get("sections") or []) + sections))
        merged_articles = list(dict.fromkeys((derived.get("articles") or []) + articles))
        if merged_sections:
            metadata["sections"] = ", ".join(merged_sections[:40])
        if merged_articles:
            metadata["articles"] = ", ".join(merged_articles[:40])

        # Case name: keep an upstream one, else use the document's own cause-title.
        current_name = (metadata.get("case_name") or "").strip()
        if not current_name or current_name.lower() in {"unknown case", "unknown", "n/a"}:
            if petitioner and respondent:
                metadata["case_name"] = f"{petitioner} v. {respondent}"
                metadata["case_name_origin"] = "derived_from_document_text"
            elif petitioner:
                metadata["case_name"] = petitioner
                metadata["case_name_origin"] = "derived_from_document_text"

        if metadata != before:
            changed += 1
            updated_ids.append(row["id"])
            updated_metadatas.append(metadata)

    if not updated_ids:
        print("Metadata already up to date; nothing changed.")
        return 0

    print(f"Updating metadata for {changed} chunks...")
    store.update_metadata(updated_ids, updated_metadatas)

    # Summary of what the enrichment produced.
    def coverage(field: str) -> int:
        return sum(
            1
            for meta in updated_metadatas
            if meta.get(field) and str(meta.get(field)).lower() not in {"unknown case", "unknown"}
        )

    print()
    print("VIDHIVEDA Metadata Enrichment Summary")
    print("-" * 32)
    print(f"Chunks in collection:  {total}")
    print(f"Chunks updated:        {changed}")
    print(f"With case name:        {coverage('case_name')}")
    print(f"With petitioner:       {coverage('petitioner')}")
    print(f"With court:            {coverage('court')}")
    print(f"With judgment date:    {coverage('judgment_date')}")
    print(f"With citation:         {coverage('citation')}")
    print(f"With sections:         {coverage('sections')}")
    print(f"With articles:         {coverage('articles')}")
    print("\nMetadata enrichment completed successfully.")
    return 0


def finalise(report: Dict[str, Any], embedded: int, total_in_store: int, elapsed: float) -> None:
    """Print the Step 6 final statistics block."""
    print()
    print("VIDHIVEDA Legal Data Ingestion")
    print("-" * 32)
    print(f"Dataset: {report.get('dataset')}")
    print(f"Total records: {report.get('total_records_read')}")
    print(f"Valid records: {report.get('valid_records')}")
    print(f"Invalid records: {report.get('invalid_records')}")
    print(f"Duplicate records: {report.get('duplicate_records')}")
    print(f"Embedded records: {embedded}")
    print(f"ChromaDB records: {total_in_store}")
    print(f"Elapsed: {elapsed:.1f}s")
    print()
    print("Ingestion completed successfully.")


def main() -> int:
    parser = argparse.ArgumentParser(description="VIDHIVEDA legal data ingestion")
    parser.add_argument("--dataset", default=PRIMARY_DATASET, choices=sorted(DATASET_REGISTRY))
    parser.add_argument(
        "--max-records",
        type=int,
        default=0,
        help="Cap the number of records read (0 = use MAX_RECORDS from .env).",
    )
    parser.add_argument("--batch-size", type=int, default=EMBEDDING_BATCH_SIZE)
    parser.add_argument("--skip-existing", action="store_true", help="Skip chunks already stored.")
    parser.add_argument("--reset", action="store_true", help="Delete the collection first (destructive).")
    parser.add_argument("--enrich-only", action="store_true", help="Refresh metadata only; no re-embedding.")
    parser.add_argument("--inspect", action="store_true", help="List registered datasets and exit.")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.inspect:
        print("Registered datasets")
        print("-" * 32)
        for entry in list_datasets():
            state = "enabled" if entry["enabled"] else "not ingested"
            print(f"{entry['key']:34} {state:14} {entry['hf_path']}")
            print(f"{'':34} collection: {entry['collection']} ({entry['kind']})")
            if entry["note"]:
                print(f"{'':34} {entry['note']}")
        return 0

    if args.enrich_only:
        return enrich_existing_metadata()

    return ingest(
        dataset_key=args.dataset,
        max_records=args.max_records,
        batch_size=args.batch_size,
        skip_existing=args.skip_existing,
        reset=args.reset,
    )


if __name__ == "__main__":
    raise SystemExit(main())
