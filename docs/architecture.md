# VIDHIVEDA — Architecture

VIDHIVEDA is a Retrieval-Augmented Generation framework for legal research and
judicial knowledge discovery. It is a **research and decision-support system** —
not an autonomous judge, not a lawyer, and not a source of legal advice.

## Components

| Layer | Location | Responsibility |
|---|---|---|
| Frontend | `frontend/` | React + Vite research workspace; calls the real API |
| API | `backend/app/api/routes/` | `/api/research`, `/api/retrieve`, `/api/predict`, `/api/rag`, status and lookup routes |
| Query understanding | `backend/app/rag/query_analyzer.py` | sections, issue, court, years, task |
| Retrieval | `backend/app/rag/retrieval_service.py` | dense search + metadata/section filters |
| Reranking | `backend/app/rag/reranker.py` | BM25 (+ optional cross-encoder) |
| Embeddings | `backend/app/rag/embedding_service.py` | configurable sentence-transformer |
| Vector store | `backend/app/db/vector_store.py` | persistent ChromaDB, cosine space |
| Generation + citations | `backend/app/rag/rag_service.py`, `citation_service.py` | grounded answer + verification |
| Outcome model | `backend/app/ml/` | separate supervised model (may be unavailable) |
| Data services | `backend/app/services/` | schema discovery, streaming ingestion, chunking, ids, status |

## Pipeline

```
User query (case facts + sections + optional filters)
   │
   ▼  query understanding (no invented entities)
LegalQueryAnalyzer → sections, issue, court, years, task
   │
   ▼  embedding
EmbeddingService (all-MiniLM-L6-v2 by default)
   │
   ▼  hybrid retrieval  (ChromaDB + metadata/section filters)
top-K candidate chunks
   │
   ▼  optional reranking (BM25 + cross-encoder when available)
top evidence chunks
   │
   ├──────────────► Outcome model (only if trained + evidence sufficient)
   │                     │
   ▼                     ▼
Evidence pack ──► RAG LLM ──► CitationVerifier ──► Structured result
   │
   ▼
React interface
```

## Four concepts kept strictly separate

1. **Retrieval relevance** — dense similarity of a chunk to the query
   (`confidence` / `retrieval.best_similarity`).
2. **Prediction confidence** — a calibrated class probability from a *separate*
   supervised model (`prediction.confidence`). Never derived from similarity.
3. **LLM answer generation** — `answer`, tagged with `answer_origin` so a
   templated retrieval listing is never mistaken for model analysis.
4. **Citation verification** — every citation is checked against the retrieved
   evidence; unsupported references are returned separately.

## Honesty guarantees

- No hard-coded legal answers, cases, citations, sections or confidence scores.
- Missing metadata is empty, never fabricated.
- If no outcome model is trained, `prediction.available` is `false` with a reason.
- If retrieval is weak, no answer is forced: the API returns a
  `low_confidence` / `no_results` payload and lists the limitations.

## Versioning (reproducibility)

Every response carries `versions`: `embedding_model`, `index_version`,
`retriever_version`, `reranker_version`, `prompt_version` and
`outcome_model_version` (from `app/core/config.py`).
