---
id: data-and-corpus
title: Where the legal data comes from
category: architecture
tags: [data, dataset, corpus, huggingface, india, supreme court, ingestion, coverage, how many documents]
intents: [project_architecture, feature_explanation, supported_feature_query]
features: [corpus]
updated: 2026-10-16
---

## The indexed corpus

* Dataset: `dedol-hf/india-case-legal-rag` (configurable with `DATASET_NAME`).
* Size: 9,375 RAG chunks from **100 Indian Supreme Court judgment PDFs**.
* Stored in ChromaDB at `backend/chroma_db/`, collection
  `vidhiveda_legal_cases`, committed to the repository so deployments do not
  re-ingest.
* No sample, mock or generated judgments are used anywhere in the retrieval path.

## Ingestion

```bash
cd backend
python scripts/ingest_legal_data.py             # full corpus
python scripts/ingest_legal_data.py --max-records 500   # dev subset
python scripts/ingest.py --status               # streaming pipeline status
```

The streaming pipeline (`scripts/ingest.py`) is batched and resumable, writes a
checkpoint per batch and a persistent status file, and uses deterministic ids so
re-runs are idempotent. Rejected rows are counted and written to a validation
report rather than dropped silently.

## Coverage limits

100 judgments is a useful research sample, not all of Indian law. If a topic is
absent from the corpus, no amount of query refinement will retrieve it. The
project also declares two further datasets (`sinhal/Indian_Supreme_Court_Judgments`
for case law and `Vikaschou/Indian-Laws` for statutes) that are marked inactive
until their field names are verified.

## Checking what is indexed

* `GET /api/research/corpus` — collection, chunk count, embedding model,
  thresholds.
* `GET /api/research/corpus/facets` — the courts and years the corpus can
  actually satisfy.
* `GET /api/health` — document count and collection.
