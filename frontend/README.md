# VIDHIVEDA — Legal Research Frontend

The research interface for VIDHIVEDA. It runs entirely on the bundled project
dataset, so it works with no backend running.

## Run

```bash
npm install
npm run dev
```

## Scripts

| Command | What it does |
|---|---|
| `npm run dev` | Vite dev server |
| `npm run build` | Production build |
| `npm run build:dataset` | Regenerates `src/dataset.js` from `../VIDHIVEDA_Sample_Dataset.csv` |
| `npm run verify:search` | Asserts every example query and library card returns matches |

## Where the data comes from

`src/dataset.js` is **generated** — never edit it by hand. It is built from
`VIDHIVEDA_Sample_Dataset.csv` at the repo root (1,631 records) by
`scripts/build-dataset.js`. Re-run `npm run build:dataset` after the CSV changes.

Each record carries `title`, `citation`, `year`, `court`, `area` (legal domain),
`sections`, `summary`, `source` and `recordType`.

### Verified vs synthetic records

The sample dataset mixes two kinds of record, and the UI labels both:

- **Verified** (136) — curated landmark judgments with real citations.
- **Synthetic** (1,495) — illustrative templates generated for dataset scale.
  Their summaries repeat boilerplate wording and are **not real citations**.

Because those templated summaries contain common legal phrases verbatim, they
would otherwise outrank real judgments. `src/search.js` therefore ranks
synthetic records at half weight while still displaying their true match score.

## How search works

`src/search.js` is a plain function module with no React and no I/O, so it can be
run from Node (that is what `verify:search` does).

Ranking order:

1. weighted field match — title & sections (4) > summary (3) > area & court (2) > citation (1)
2. exact-phrase bonus, which is what lets short instrument names such as
   "IT Act" match despite tokenising dropping the stopword
3. verified records before synthetic ones
4. most recent year

This is keyword/field matching, not embedding-based semantic search — the
dataset ships no vectors to the browser.

## Backend integration points

The UI currently searches the bundled dataset client-side. `src/api/` does not
exist yet; to move retrieval server-side, the FastAPI backend in `../backend`
already exposes these routes (all under `/api`):

| Purpose | Route |
|---|---|
| RAG search | `POST /search` |
| Similar cases | `POST /similar` |
| Trend analysis | `POST /trends` |
| Summarisation | `POST /summarize` |
| Document browse | `GET /documents`, `GET /documents/{id}` |
| Legal sections | `GET /sections` |
| Reference data | `GET /reference-data` |
| Health | `GET /health` |

Note: this backend also holds the same 1,631 records in ChromaDB, so wiring
`POST /api/search` in would upgrade retrieval from keyword matching to real
semantic search. You will need a dev proxy for `/api` in `vite.config.js`
(the original `frontend-legacy` config has one pointing at `127.0.0.1:8000`).
