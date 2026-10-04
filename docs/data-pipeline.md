# VIDHIVEDA — Data Pipeline

## 1. Dataset discovery (dynamic)

Datasets are never assumed to have a fixed schema.

```bash
cd backend
python scripts/inspect_dataset.py --samples 20        # inspect the active dataset
python scripts/inspect_dataset.py --list              # list registered datasets
python scripts/inspect_dataset.py --json report.json  # full machine-readable report
```

It reports configurations, splits, field names, types, missing-value
percentage, average text length, and the best match for text / outcome / court /
date / section fields. A field that cannot be found is reported as missing — it
is never invented.

Registered datasets live in `app/services/dataset_service.py:DATASET_REGISTRY`.

## 2. Field mapping

`app/services/schema_service.py` merges, in priority order:

1. registry defaults;
2. auto-detected columns from a sample;
3. `*_FIELD` environment overrides (`TEXT_FIELD`, `CASE_ID_FIELD`,
   `CASE_NAME_FIELD`, `COURT_FIELD`, `DATE_FIELD`, `YEAR_FIELD`,
   `OUTCOME_FIELD`, `SECTION_FIELD`, `SOURCE_URL_FIELD`).

Unresolved fields stay `None`.

## 3. Streaming ingestion

The corpus may be tens of GB, so nothing loads the whole dataset:

```
stream → batch → clean → chunk → embed → upsert → checkpoint → next batch
```

```bash
python scripts/ingest.py --sample 1000   # small development subset
python scripts/ingest.py --limit 10000   # bounded
python scripts/ingest.py --resume        # continue from the last checkpoint
python scripts/ingest.py --full          # whole corpus
python scripts/ingest.py --reset         # drop the collection first
python scripts/ingest.py --status        # persistent status
```

- **Streaming** via `datasets.load_dataset(..., streaming=True)`.
- **Idempotent** — deterministic ids, `upsert` writes.
- **Resumable** — a checkpoint (`data/checkpoints/<dataset>.json`) is written
  after every batch; `--resume` skips the records already consumed.
- **Observable** — `data/ingestion_status.json` and `GET /api/ingestion/status`.

## 4. Normalization

`clean_text` normalizes Unicode, strips control characters, the JUDIS banner and
repeated whitespace. It preserves paragraphs, headings, numbered provisions,
citations, dates, court and judge references. Missing fields stay empty.

## 5. Deduplication and stable ids

`app/services/ids.py`:
- `document_id` = upstream record id, else `sha256(source + original_id + text)`;
- `chunk_id` = `<document_id>_<chunk_index>`.

The same document always produces the same ids, so re-ingestion updates rows in
place instead of duplicating them. Duplicate `(document, chunk, text)` tuples
within a run are skipped.

## 6. Legal-aware chunking

`app/services/chunking.py` is used for **document-level** datasets (the active
`dedol-hf/india-case-legal-rag` corpus ships pre-chunked RAG rows and is not
re-chunked). It prefers paragraph boundaries, then sentence boundaries, then a
hard cut, with configurable `CHUNK_SIZE` / `CHUNK_OVERLAP` and
`CHUNK_STRATEGY` (`legal_aware` | `fixed`).

## 7. Vector store

Persistent ChromaDB, cosine space. Collections:

- `vidhiveda_legal_cases` — case law;
- `vidhiveda_statutes` — reserved for statute data (never blended).

Stored per chunk: id, text, embedding, and metadata (document/chunk id, source,
court, year, judgment date, citation, sections, articles, …).

## 8. Development order (recommended)

```bash
python scripts/inspect_dataset.py --samples 20
python scripts/ingest.py --sample 1000
python scripts/test_retrieval.py
python scripts/test_rag.py
python scripts/ingest.py --full      # only once everything works
```
