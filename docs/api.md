# VIDHIVEDA — API Reference

Base URL: `http://localhost:8000`. Interactive docs: `/docs`.

## Research

### `POST /api/research` (and `POST /api/rag`, identical)

Request:

```json
{
  "query": "case facts...",
  "sections": ["IPC 302"],
  "court": null,
  "year": null,
  "year_from": null,
  "year_to": null,
  "law_area": null,
  "document_type": null,
  "top_k": 20
}
```

Response (abridged):

```json
{
  "query": "...",
  "status": "ok | low_confidence | no_results",
  "answer": "...",
  "confidence": 0.72,
  "confidence_basis": "dense_retrieval_similarity",
  "sources": [ ... ],
  "precedents": [ ... ],
  "citations": [ ... ],
  "unverified_references": [],
  "prediction": {
    "available": false,
    "label": null,
    "confidence": null,
    "low_confidence": false,
    "reason": "Outcome prediction model is not currently available ..."
  },
  "legal_provisions": [ ... ],
  "evidence_sufficient": true,
  "retrieval": { "semantic_count": 20, "reranked_count": 10 },
  "query_analysis": { "legal_sections": [], "legal_issue": null, "task": "..." },
  "limitations": [],
  "disclaimer": "VIDHIVEDA is a research and decision-support system ...",
  "versions": { "embedding_model": "...", "index_version": "1", ... }
}
```

`confidence` is **retrieval** similarity; `prediction.confidence` is a **model**
probability. They are never the same number.

## Pipeline stages

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/retrieve` | hybrid retrieval only (no generation) |
| POST | `/api/predict` | outcome prediction only (honest if untrained) |
| POST | `/api/rag` | full structured answer (same as `/api/research`) |

## Status and lookup

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | service + corpus health |
| GET | `/api/model/status` | which models are loaded + pipeline versions |
| GET | `/api/ingestion/status` | persistent ingestion state |
| GET | `/api/research/corpus` | collection, chunk count, embedding model |
| GET | `/api/research/corpus/facets` | filter values the corpus can satisfy |
| GET | `/api/research/chunk/{chunk_id}` | the exact stored row for a chunk |
| GET | `/api/cases/{document_id}` | every stored chunk of one document |

## Legacy routes

`/api/search` (deprecated), `/api/documents`, `/api/sections`, `/api/similar`,
`/api/summarize`, `/api/trends` are backed by the bundled SQLite sample corpus,
not the ChromaDB research corpus.

## Status codes

`200` ok · `404` unknown chunk/document · `422` invalid request ·
`503` empty corpus, embedding or vector-store failure.
