#!/usr/bin/env python
"""
VIDHIVEDA streaming ingestion (Steps 3, 5, 37, 38).

    python scripts/ingest.py --sample 1000     # small development subset
    python scripts/ingest.py --limit 10000     # bounded run
    python scripts/ingest.py --full            # whole corpus
    python scripts/ingest.py --resume          # continue from the last checkpoint
    python scripts/ingest.py --reset           # drop the collection first
    python scripts/ingest.py --status          # show the persistent status

Records are streamed from the registered Hugging Face dataset, normalised,
chunked (when the dataset is document-level), embedded and upserted into the
persistent ChromaDB collection. Deterministic ids make the run idempotent; a
checkpoint after every batch makes it resumable without re-embedding.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import CASE_LAW_COLLECTION, EMBEDDING_BATCH_SIZE  # noqa: E402
from app.services.dataset_service import PRIMARY_DATASET, get_dataset_config  # noqa: E402
from app.services.ingestion_service import StreamingIngestor  # noqa: E402
from app.services.ingestion_status import ingestion_status  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main() -> int:
    parser = argparse.ArgumentParser(description="Stream a legal dataset into ChromaDB.")
    parser.add_argument("--dataset", default=PRIMARY_DATASET, help="registered dataset key")
    parser.add_argument("--sample", type=int, default=None, help="process N records (alias of --limit)")
    parser.add_argument("--limit", type=int, default=None, help="process at most N records")
    parser.add_argument("--full", action="store_true", help="process the whole corpus")
    parser.add_argument("--resume", action="store_true", help="resume from the last checkpoint")
    parser.add_argument("--reset", action="store_true", help="delete the collection before ingesting")
    parser.add_argument("--batch-size", type=int, default=EMBEDDING_BATCH_SIZE)
    parser.add_argument("--status", action="store_true", help="print the ingestion status and exit")
    args = parser.parse_args()

    if args.status:
        status = ingestion_status.read()
        print("VIDHIVEDA — Ingestion Status")
        print("-" * 40)
        for key in (
            "dataset", "status", "mode", "processed_documents", "processed_chunks",
            "failed_records", "last_checkpoint", "started_at", "updated_at", "error",
        ):
            print(f"  {key}: {status.get(key)}")
        return 0

    try:
        config = get_dataset_config(args.dataset)
    except KeyError as exc:
        print(f"ERROR: {exc}")
        return 2

    limit = args.sample if args.sample is not None else args.limit
    if args.full:
        limit = None
    if limit is None and not args.resume and not args.full:
        print("Refusing a full-corpus run without an explicit flag.")
        print("Use `--sample N`, `--limit N`, `--resume` or `--full`.")
        return 2

    print("VIDHIVEDA — Streaming Ingestion")
    print("-" * 40)
    print(f"Dataset:    {config['hf_path']}")
    print(f"Collection: {config['collection']}")
    print(f"Limit:      {limit if limit else 'full corpus'}")
    print(f"Mode:       {'resume' if args.resume else ('full' if args.full else 'bounded')}")
    print()

    ingestor = StreamingIngestor(args.dataset)
    summary = ingestor.run(
        limit=limit,
        resume=args.resume,
        reset=args.reset,
        batch_size=args.batch_size,
    )

    print()
    print("Ingestion summary")
    print("-" * 40)
    print(f"  records processed: {summary['processed_documents']}")
    print(f"  chunks stored:     {summary['processed_chunks']}")
    print(f"  failed records:    {summary['failed_records']}")
    print(f"  last checkpoint:   {summary['last_checkpoint']}")
    print(f"  collection size:   {summary['collection_size']}")
    print(f"  elapsed:           {summary['elapsed']}s")
    if summary["error"]:
        print(f"\nERROR: {summary['error']}")
        print("Re-run with `--resume` to continue from the last checkpoint.")
        return 3

    print(f"\nCollection '{CASE_LAW_COLLECTION}' is ready behind POST /api/research.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
