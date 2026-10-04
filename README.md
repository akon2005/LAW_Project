# VIDHIVEDA — AI-Powered Legal Research Engine

**Live VIDHIVEDA Application:** [Open Application](https://frontend-akon2005s-projects.vercel.app)

| Environment | URL |
|---|---|
| Frontend (Vercel, production) | https://frontend-akon2005s-projects.vercel.app |
| Backend API (Render, production) | https://vidhiveda-backend.onrender.com |
| API documentation (Swagger) | https://vidhiveda-backend.onrender.com/docs |
| Health check | https://vidhiveda-backend.onrender.com/health |

> These URLs are defined in [`render.yaml`](render.yaml) and the Vercel project.
> If a host issues a different URL, update this table and redeploy.
>
> Deployment, CI/CD, required secrets and rollback are documented in
> [docs/deployment.md](docs/deployment.md).

## 1. What VIDHIVEDA Does
VIDHIVEDA is a sophisticated AI-powered legal research and judicial knowledge discovery system. It allows users to input natural language queries regarding legal matters, retrieves relevant Indian case-law precedents from a vector database (ChromaDB), and synthesizes a well-structured, citation-backed response using Large Language Models (LLMs). The frontend provides a professional legal-research interface that highlights case citations and displays exact matched precedents.

## 2. Major Parts of the Project
- **Frontend (React.js):** The polished, professional UI the user interacts with.
- **Backend (Python + FastAPI):** The application server handling API requests, managing system configuration, and orchestrating responses.
- **AI/RAG Pipeline:** The core intelligence layer that turns user queries into vector embeddings, performs semantic searches over legal data, and prompts an LLM for synthesis.
- **Data & Ingestion:** Independent scripts and storage for pulling actual datasets (like from Hugging Face), generating embeddings, and hydrating the vector database.

## 3. Project Structure
The project is logically divided to separate concerns according to modern software architecture best practices:

- **`frontend/`**: The complete React.js frontend.
  - **`src/data/`**: Static datasets and data structures for UI mocking and constants.
  - **`src/styles/`**: CSS styling for animations and UI.
  - **`src/utils/`**: Helper utilities and keyword search fallbacks.
  - **`src/App.jsx`**: The main application component holding the UI logic.
- **`backend/`**: The FastAPI backend application.
  - **`app/api/routes/`**: API endpoint definitions (e.g., `/api/research`).
  - **`app/core/`**: Configuration files (e.g., loading environment variables).
  - **`app/db/`**: Database connections, ChromaDB vector store clients, and ORM setups.
  - **`app/schemas/`**: Pydantic models validating incoming requests and formatting API responses.
  - **`app/rag/`**: AI logic including embedding generation, semantic retrieval, and LLM text generation.
  - **`app/main.py`**: The application entry point.
- **`data_processing/`**: Scripts and utilities (`ingest_legal_data.py`, `preprocess.py`, etc.) for downloading datasets, parsing legal documents, and embedding data into ChromaDB.
- **`datasets/`**: Directory for storing local CSVs or raw dataset files.
- **`docs/`**: Extra documentation, old READMEs, and text files.

## 4. Local Development

**Frontend (Vite + React):**
```bash
cd frontend
npm install
npm run dev
```
Access the UI at: `http://localhost:5173`

**Backend (FastAPI):**
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Mac/Linux
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
Access the API at: `http://localhost:8000/docs`

## 5. Vercel Deployment

This project is configured for a single, unified Vercel deployment:
- **Frontend:** Vite React static build
- **Backend:** FastAPI via Vercel Python Serverless Functions

**Deployment Steps:**
1. Import the repository into Vercel.
2. Set **Root Directory** to `./` (the repository root).
3. Set **Framework Preset** to Vite.
4. Set **Build Command** to `cd frontend && npm install && npm run build`.
5. Set **Output Directory** to `frontend/dist`.
6. Configure the necessary environment variables in the Vercel dashboard (see `.env.example`).
7. Deploy Preview and verify functionality, then promote to Production.

**Environment Variables:**
- `VITE_API_URL`: `/api` (for the frontend to route requests to the same origin).
- `LLM_PROVIDER`, `OPENAI_API_KEY`, etc. for server-side generation.
- `REMOTE_EMBEDDING_PROVIDER`: set to `openai` to use remote embeddings (bypasses heavy local ML dependencies).

## 5.1. AI/RAG Production Architecture

In production (Vercel Serverless), the application operates in a lightweight mode to comply with size limits (250MB):
- The massive `sentence-transformers` and `chromadb` libraries are omitted from the root `requirements.txt`.
- Vector storage must be provided via a remote database (e.g., Pinecone or a managed Chroma service). If unconfigured, the API safely reports it as unavailable.
- Large legal corpora are externalized. Run ingestion separately using `backend/scripts/ingest_legal_data.py` on a persistent machine, targeting your remote vector database.

## 6. Where the AI/RAG Components Are Located
The AI and RAG components are entirely isolated within `backend/app/rag/`.
- `embedding_service.py`: Generates dense vector embeddings for text.
- `retrieval_service.py`: Searches the vector database for the top-K relevant cases.
- `rag_service.py`: Takes the retrieved cases and formats them into a prompt for the LLM to synthesize an answer.
- `pipeline.py` & `generator.py`: Additional tools orchestrating complex retrieval logic.

## 7. Where Datasets and Vector Database Files Are Located
- **Raw Datasets:** Stored locally in `datasets/` or downloaded dynamically from Hugging Face by the scripts in `data_processing/`.
- **Vector Database:** The persisted ChromaDB vector database files are located at `backend/chroma_db/`. This folder holds all indexed embeddings for semantic search.

---

## 8. Real Legal-Data Pipeline (current implementation)

The search box is backed by the real Hugging Face dataset **`dedol-hf/india-case-legal-rag`** (9,375 RAG chunks from 100 Indian Supreme Court judgment PDFs). No sample, mock or generated judgments are used anywhere in the retrieval path.

### Flow
```
React UI  →  POST /api/research  →  embedding  →  ChromaDB (vidhiveda_legal_cases)
          →  optional rerank  →  RAG generation  →  citation verification  →  JSON
```

### Ingestion
```bash
cd backend
.venv\Scripts\activate                     # or: source .venv/bin/activate
pip install -r requirements.txt
python scripts/ingest_legal_data.py            # full corpus (MAX_RECORDS from .env)
python scripts/ingest_legal_data.py --max-records 500   # dev subset
python scripts/ingest_legal_data.py --enrich-only       # re-derive metadata, no re-embedding
python scripts/ingest_legal_data.py --inspect           # registered datasets
```
Validation is never silent: every rejected row is counted and written to
`backend/data/dataset/validation_report_<dataset>.json`.

### Run
```bash
# terminal 1 — API
cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000

# terminal 2 — UI
cd frontend && npm install && npm run dev
```
UI: `http://localhost:5173` · API docs: `http://localhost:8000/docs`

### API
| Method | Path | Purpose |
|---|---|---|
| POST | `/api/research` | `{query, law_area?, court?, year?, top_k?}` → grounded answer + verified citations |
| GET | `/api/research/corpus` | collection name, chunk count, embedding model, thresholds |
| GET | `/api/research/chunk/{chunk_id}` | the exact stored row for a chunk (verification) |
| GET | `/api/health` | document count + collection |

Status codes: `200` ok / low-confidence payload · `404` unknown chunk · `422` invalid request · `503` corpus empty, embedding or vector-store failure.

### Sample query
```bash
curl -s -X POST http://127.0.0.1:8000/api/research \
  -H "Content-Type: application/json" \
  -d '{"query":"What are the precedents related to breach of contract?","top_k":5}'
```

### How to verify a result really came from ChromaDB
1. Take a `chunk_id` from the response (e.g. `157_62`).
2. Fetch it directly from the store: `curl http://127.0.0.1:8000/api/research/chunk/157_62`.
3. Compare that row's `text` with the `text` in the research response — they are the same stored document.
4. Or read the store without the app:
   ```python
   import chromadb
   col = chromadb.PersistentClient(path="backend/chroma_db").get_collection("vidhiveda_legal_cases")
   print(col.count(), col.get(ids=["157_62"], include=["metadatas", "documents"]))
   ```

### Configuration (`backend/.env`)
`DATASET_NAME`, `MAX_RECORDS`, `EMBEDDING_MODEL`, `EMBEDDING_BATCH_SIZE`, `VECTOR_STORE_DIR`,
`CASE_LAW_COLLECTION`, `STATUTE_COLLECTION`, `TOP_K`, `LOW_CONFIDENCE_THRESHOLD`, `USE_RERANKER`,
`RERANKER_MODEL`, `HF_API_TOKEN`, `LLM_PROVIDER`, `LLM_TIMEOUT_SECONDS`. See `.env.example`.

### Sign-in experience

The research workspace is gated behind a sign-in screen. There is **no backend auth system
in this repo**, so `AuthService` runs in one of two clearly-signalled modes:

| Mode | When | Behaviour |
|---|---|---|
| `live` | `VITE_AUTH_ENDPOINT` resolves (or `VITE_API_BASE` + `/auth/login`) | POSTs `{email, password, role}`, expects `{access_token, user: {email, name?, role?}}` |
| `demo` | no endpoint configured, or it answers `404`/`501` | validates locally, stores a session flagged `mode: 'demo'` |

The screen states which mode is active (`Your research workspace is protected with secure
authentication.` vs `Demo workspace — authentication is not yet connected to a server.`) rather
than implying a credential check that did not happen.

| File | Role |
|---|---|
| `src/services/authService.js` | validation, live/demo login, session storage, error codes |
| `src/auth/AuthProvider.jsx` | session context; `login` verifies, `commit` publishes after the exit transition |
| `src/components/auth/LoginPage.jsx` | split layout, brand, corpus facts, footer |
| `src/components/auth/LoginForm.jsx` | fields, inline validation, loading/error/success states |
| `src/components/auth/PasswordInput.jsx` | password field with show/hide |
| `src/components/auth/RoleSelector.jsx` | accessible "Sign in as" radiogroup |
| `src/components/auth/AuthVisual.jsx` | inline-SVG reading-room artwork |
| `src/styles/login.css` | all sign-in styling, built on the existing tokens |

```bash
# point the UI at a real endpoint later (frontend/.env.local)
VITE_API_BASE=http://localhost:8000
VITE_AUTH_ENDPOINT=http://localhost:8000/api/auth/login

# replace the line artwork with a photograph
VITE_LOGIN_VISUAL=/assets/courthouse.jpg
```

"Remember me" keeps the session in `localStorage`; otherwise it lives in `sessionStorage` and
expires after 12 hours. Sign out clears it and returns to the sign-in screen.

### Research workspace and reading view

The workspace fills the viewport instead of a fixed 1240px strip, and the result list flows into
as many columns as the screen can carry (2 columns at 1440px, 3 at 1920px, 4 at 2560px).

Filter options are read from the corpus itself — `GET /api/research/corpus/facets` — so a filter
value that no indexed chunk contains can no longer be offered. The earlier hard-coded
`1955–2026` year list was the worst case: the corpus only holds 1950/1951, so every year filter
returned zero results. Area of law is not part of the corpus metadata at all and is therefore no
longer offered as a filter.

Clicking a result opens a full-screen reading view (`src/components/ReaderView.jsx`), rendered
through a React portal into `<body>` so no transformed ancestor can hijack its positioning.

| Control | Options |
|---|---|
| Text size | 80%–240% (+, −, reset, fit to window) |
| Line spacing | compact / normal / relaxed |
| Column width | narrow / standard / wide / full |
| Typeface | serif / sans |
| Theme | light / sepia / dark |
| Also | Copy text, Print, previous/next record, source trail |

Keyboard: `+` / `−` resize, `0` resets, `←` `→` move between records, `Esc` closes.
Preferences persist in `localStorage` under `vidhiveda.reader`. A text-size control in the results
toolbar drives the same scale for the cards and the answer panel.

| File | Role |
|---|---|
| `src/components/ReaderView.jsx` | the reading view, its preference model and keyboard handling |
| `src/utils/readerText.js` | pure paragraph shaping (PDF hard wraps, walls of text); unit-checkable from Node |
| `src/utils/clipboard.js` | bounded clipboard write with a selection fallback; reports real success |
| `src/styles/styles.css` | shell width tokens, workspace grid, reader styling, print rules |

### Preparation for further datasets
`app/services/dataset_service.py:DATASET_REGISTRY` already declares
`sinhal/Indian_Supreme_Court_Judgments` (case law) and `Vikaschou/Indian-Laws`
(statutes, separate `vidhiveda_statutes` collection). They are marked
`active: False`, so nothing is ingested or blended until their field names are
verified and the flag is flipped.

---

## 9. Pipeline stages, streaming ingestion and prediction

The research pipeline is now exposed stage by stage, and ingestion streams the
corpus instead of loading it into memory.

### New commands

```bash
cd backend

# 1. Inspect the real dataset schema (configs, splits, fields, label availability)
python scripts/inspect_dataset.py --samples 20

# 2. Stream a small sample, then a bounded run, then resume / full
python scripts/ingest.py --sample 1000
python scripts/ingest.py --limit 10000
python scripts/ingest.py --resume
python scripts/ingest.py --full
python scripts/ingest.py --status

# 3. Smoke-test retrieval and RAG
python scripts/test_retrieval.py "breach of contract damages" --top-k 5
python scripts/test_rag.py

# 4. Outcome model (refuses honestly when labels are unavailable)
python scripts/train_outcome_model.py
python scripts/train_outcome_model.py --status

# 5. Evaluation
python scripts/build_gold_set.py            # derived, reproducible gold set
python scripts/evaluate.py --no-rerank
python scripts/evaluate.py --rerank
```

`scripts/ingest.py` is a streaming, batched, resumable pipeline: it writes a
checkpoint after every batch (`data/checkpoints/`) and a persistent status file
(`data/ingestion_status.json`), and deterministic ids make re-runs idempotent.
`scripts/ingest_legal_data.py` remains for `--enrich-only` metadata refreshes.

### New API endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/research` | grounded answer + verified citations + structured output |
| POST | `/api/rag` | identical to `/api/research` |
| POST | `/api/retrieve` | hybrid retrieval only (no generation) |
| POST | `/api/predict` | outcome prediction only |
| GET | `/api/model/status` | loaded models + pipeline versions |
| GET | `/api/ingestion/status` | persistent ingestion state |
| GET | `/api/cases/{document_id}` | every stored chunk of one document |

`/api/research` now also returns `prediction`, `legal_provisions`,
`evidence_sufficient`, `retrieval`, `query_analysis`, `limitations`, `disclaimer`
and `versions`. Query understanding normalizes IPC/BNS section references and the
section filter is applied to retrieval.

### Outcome prediction: currently unavailable (by design)

The active corpus has **no outcome/label field**, and its text is judgment text,
so training an outcome model on it would leak the verdict into the features.
The system therefore reports `prediction.available = false` with a reason rather
than inventing a classifier. See [docs/model.md](docs/model.md).

### Documentation

- [docs/architecture.md](docs/architecture.md)
- [docs/data-pipeline.md](docs/data-pipeline.md)
- [docs/rag-pipeline.md](docs/rag-pipeline.md)
- [docs/model.md](docs/model.md)
- [docs/evaluation.md](docs/evaluation.md)
- [docs/api.md](docs/api.md)
- [docs/okf-implementation.md](docs/okf-implementation.md)

### Tests

```bash
cd backend
python -m unittest discover -s tests -t .
```

---

## 10. Open Knowledge Format (OKF v0.2) knowledge layer

The curated legal knowledge the corpus supports is exported as a conformant
[Open Knowledge Format v0.2](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
bundle at `backend/knowledge/` — a portable directory of markdown files with YAML
frontmatter (100 judgments, 44 courts, 316 provision references, plus dataset,
model and evaluation concepts).

```bash
cd backend
python scripts/build_okf_bundle.py     # regenerate from the indexed corpus
python scripts/validate_okf.py         # conformance report (exit 0 = conformant)
```

Every concept carries traceable provenance and a trust tier. They are
deterministically generated and checked by processes, so they are
`machine-confirmed` — **not** `human-reviewed`. Values the corpus does not record
(a section's statute, for example) are left empty and stated as unknown rather
than guessed.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/knowledge` | list/filter concepts (type, status, tag, q) |
| GET | `/api/knowledge/stats` | counts by type, trust tiers, provenance coverage |
| GET | `/api/knowledge/validate` | conformance report |
| GET | `/api/knowledge/search?q=` | lexical concept lookup |
| GET | `/api/knowledge/{concept_id}` | one concept with resolved links and backlinks |

`POST /api/research` returns a supplementary `knowledge` field listing related
OKF concepts, but original retrieved chunks remain authoritative — OKF summaries
are never injected into the generation prompt in place of source evidence.
See [docs/okf-implementation.md](docs/okf-implementation.md).
