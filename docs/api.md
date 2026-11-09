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

## Comparison

### `POST /api/comparison`

Evidence-based comparison of two competing accounts of one dispute (or a single
account when `scenario_b` is omitted). Retrieval runs once per scenario over the
same indexed corpus; precedents are grouped per source document and every
citation carries a stored chunk id. The endpoint returns argument analysis and an
explicit evidence-quality status — never a verdict — and reports an outcome
estimate only when a trained, evaluated classifier is loaded.

Request:

```json
{
  "legal_issue": "Whether the termination was lawful",
  "case_facts": "optional shared facts",
  "provisions": ["Industrial Disputes Act, 1947 s. 25F"],
  "scenario_a": { "label": "Employer", "position": "The contract permitted termination without notice." },
  "scenario_b": { "label": "Employee", "position": "No notice was given and natural justice applied." },
  "court": null,
  "year_from": null,
  "year_to": null,
  "top_k": 8
}
```

Response (abridged):

```json
{
  "status": "ok",
  "mode": "comparison | single_scenario",
  "legal_issue": "...",
  "case_summary": "...",
  "legal_issues": [ ... ],
  "applicable_law": [ ... ],
  "scenario_a": {
    "label": "Employer",
    "position": "...",
    "supporting_precedents": [ ... ],
    "contrary_precedents": [ ... ],
    "strengths": [ ... ],
    "weaknesses": [ ... ],
    "missing_evidence": [ ... ],
    "supporting_count": 4,
    "contrary_count": 1,
    "best_alignment_similarity": 0.71,
    "provisions": [ ... ]
  },
  "scenario_b": { ... },
  "comparative_analysis": { ... },
  "evidence_comparison": [ ... ],
  "evidence_quality": {
    "status": "SUFFICIENT_EVIDENCE_FOR_ANALYSIS",
    "best_similarity": 0.71,
    "reasons": [ ... ],
    "precedent_count": 12
  },
  "outcome_prediction": {
    "available": true,
    "status": "EXPERIMENTAL_PREDICTION",
    "target": "historical_disposition_class",
    "predicted_class": "...",
    "calibrated_probability": 0.62,
    "model_version": "...",
    "per_scenario": { ... }
  },
  "precedents": [ ... ],
  "citations": [ ... ],
  "retrieval": { ... },
  "limitations": [ ... ],
  "disclaimer": "..."
}
```

`evidence_quality.status` is one of `SUFFICIENT_EVIDENCE_FOR_ANALYSIS`,
`LIMITED_EVIDENCE`, `INSUFFICIENT_EVIDENCE`. `outcome_prediction.available` is
`false` with a `reason` when no trained classifier is loaded or the evidence is
insufficient; `calibrated_probability` is a model estimate, never a retrieval
similarity.

`503` — the vector store is empty or unavailable, or retrieval failed.

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
