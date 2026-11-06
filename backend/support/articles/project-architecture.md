---
id: project-architecture
title: How the system is put together
category: architecture
tags: [architecture, backend, frontend, fastapi, react, stack, components, structure]
intents: [project_architecture, feature_explanation, how_to]
features: []
updated: 2026-10-16
---

## Frontend

React with Vite. `frontend/src/App.jsx` holds the workspace shell and the tab
state (the app does not use a URL router — tabs are React state, so there are no
deep links to individual pages). Supporting pieces:

* `src/components/ReaderView.jsx` — the full-screen reading view.
* `src/components/comparison/ComparePanel.jsx` — the Compare tab.
* `src/components/settings/AppearancePanel.jsx` — appearance settings.
* `src/components/assistant/AssistantBubble.jsx` — this support assistant.
* `src/theme/` — the single source of theme state (mode + palette).
* `src/services/apiBase.js` — the one place the backend origin is defined
  (`VITE_API_BASE`, defaulting to `http://localhost:8000` in development).

## Backend

Python + FastAPI, `backend/app/`:

* `app/main.py` — app entry point, CORS, router registration, `/api/health`.
* `app/api/routes/` — the HTTP layer. Research and RAG live in `research.py`;
  the support assistant lives in `support.py`.
* `app/rag/` — embedding, retrieval, reranking, query analysis, RAG generation
  and citation verification.
* `app/db/vector_store.py` — the ChromaDB client.
* `app/ml/` — outcome-model loading; the fitted classifier is committed under
  `data/models/outcome/`.
* `app/okf/` — the Open Knowledge Format knowledge layer.
* `app/support/` — the User Guide & Support Assistant subsystem: knowledge base,
  intent routing, tool registry, sessions and health checks.
* `app/core/config.py` — every setting, read from the environment.

## Data

* **Vector store:** `backend/chroma_db/` (collection `vidhiveda_legal_cases`),
  committed so deployments never re-ingest.
* **Support articles:** `backend/support/articles/` — markdown with YAML
  frontmatter. Deliberately separate from the legal corpus and from the generated
  OKF bundle, so website documentation is never retrieved as legal authority.
* **Demo examples and the capability registry:** `backend/support/examples.json`
  and `backend/support/features.json`.

## Request flow for one research question

```
React UI -> POST /api/research -> query analysis -> embedding
         -> ChromaDB search -> section/metadata filter -> optional rerank
         -> RAG generation -> citation verification -> JSON
```
