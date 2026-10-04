# VIDHIVEDA — Deployment & CI/CD

This document is the operating manual for how VIDHIVEDA ships. It is the
reference for the "make a change → test → push → deploy → verify" loop.

## 1. Architecture at a glance

| Layer | Host | What runs there | Notes |
|---|---|---|---|
| Frontend | **Vercel** (`frontend-akon2005s-projects.vercel.app`) | Vite + React static build | Root `vercel.json` builds `frontend/` and outputs `frontend/dist`. |
| Backend + RAG | **Render** (`vidhiveda-backend`, Docker) | FastAPI, sentence-transformers, ChromaDB | `render.yaml` blueprint, `backend/Dockerfile`. Full `backend/requirements.txt`. |
| Vector store | **Committed in `backend/chroma_db/`** | 9,375 chunks in `vidhiveda_legal_cases` | Baked into the Docker image, so no host re-embeds on deploy. |
| Metadata DB | SQLite (`backend/data/metadata.db`, committed) | SQLAlchemy `cases` table | Created via `init_db()`; no destructive migrations run automatically. |
| Source of truth | **GitHub `main`** (`https://github.com/akon2005/VIDHIVEDA`, backup: `https://github.com/akon2005/LAW_Project`) | All of the above | Every deploy is a response to a commit on `main`. |


**Why the backend is on Render, not Vercel serverless.** The unified Vercel
config (`api/index.py` + root `requirements.txt`) is kept as a fallback, but the
real pipeline needs `chromadb` and `sentence-transformers`, which exceed Vercel's
serverless bundle limit and cannot persist a vector store on its ephemeral
filesystem. Render runs the actual Docker image, so retrieval and embeddings work
in production. See README §5.1.

**Why the vector store is committed.** Free-tier hosts have no persistent disk
(persistent disks on Render require a paid instance). Committing
`backend/chroma_db/` means every deploy already carries the 9,375 indexed chunks,
so ordinary code changes never trigger a re-ingest. The corpus is refreshed only
through the **Ingest Legal Corpus** workflow.

## 2. Workflows (`.github/workflows/`)

| Workflow | Trigger | What it does |
|---|---|---|
| `ci.yml` | every PR + every push to `main` | Backend test suite (118 tests, includes retrieval/RAG unit tests) and frontend production build. No deploy. |
| `deploy-frontend.yml` | push to `main` touching `frontend/**` or `vercel.json`; or manual | Builds and deploys the frontend to **Vercel production** with the official Vercel CLI. |
| `deploy-backend.yml` | push to `main` touching `backend/**`, `api/**`, or `render.yaml`; or manual | Runs backend tests, then triggers the **Render deploy hook**, then polls `/health` until the new revision is live. |
| `ingest.yml` | manual only (`workflow_dispatch`) | The **only** path that re-embeds the dataset. Commits the refreshed store, which re-triggers `deploy-backend`. |

Documentation-only and data-file-only changes match no deploy path, so they land
on GitHub without redeploying the app.

### Deployment triggers, mapped to the requirement

- **Frontend change** → `deploy-frontend.yml` (build + Vercel).
- **Backend change** → `deploy-backend.yml` (tests + Render).
- **RAG change** → `backend/app/rag/**` lives under `backend/**`, so it runs the
  backend tests (which cover retrieval/ranking) and redeploys the backend.
- **Dataset / ingestion change** → `ingest.yml` (manual, guarded).
- **Docs-only change** → no deploy.

## 3. Required GitHub secrets and variables

Set these under **Repository → Settings → Secrets and variables → Actions**.

### Secrets

| Name | Used by | Where to get it |
|---|---|---|
| `VERCEL_TOKEN` | `deploy-frontend.yml` | Vercel → Account Settings → Tokens. |
| `VERCEL_ORG_ID` | `deploy-frontend.yml` | Vercel project → Settings → General (or `.vercel/project.json`). |
| `VERCEL_PROJECT_ID` | `deploy-frontend.yml` | Same as above. |
| `RENDER_DEPLOY_HOOK_URL` | `deploy-backend.yml` | Render service → Settings → Deploy Hook. |
| `HF_API_TOKEN` | `ingest.yml` (optional, for HF datasets/LLM) | huggingface.co → Settings → Access Tokens. |

### Variables (not secret)

| Name | Used by | Value |
|---|---|---|
| `VITE_API_BASE` | `deploy-frontend.yml` | Backend origin, e.g. `https://vidhiveda-backend.onrender.com`. Baked into the frontend bundle; without it the UI calls same-origin `/api`. |
| `BACKEND_URL` | `deploy-backend.yml` | Backend origin, used for the post-deploy `/health` poll. |

No credential is ever stored in the repository. `render.yaml` marks every secret
`sync: false`, so it is supplied from the Render dashboard instead.

## 4. One-time setup (if any piece is missing)

1. **Vercel** — confirm the project's Root Directory is the repo root and the
   framework preset is Vite (the root `vercel.json` drives the build). Add
   `VITE_API_BASE` in Vercel env vars too, so dashboard/preview builds match CI.
   Under **Project Settings → Deployment Protection**, ensure **Vercel Authentication**
   is **Disabled** (or disabled for production) so public users can access the app
   without an SSO redirect.
2. **Render** — create the service from `render.yaml` (`Blueprint`). Set
   `HF_API_TOKEN` (and `OPENAI_API_KEY` if used) in the dashboard. Copy the
   **Deploy Hook URL** into the `RENDER_DEPLOY_HOOK_URL` GitHub secret.
3. **GitHub** — add the secrets/variables above. Optionally protect `main` and
   require the **CI** workflow to pass before merge.


> **Paid-service note:** the current setup deliberately avoids paid services by
> committing the corpus and using the free Render web plan. If you later want the
> corpus to live on a persistent disk instead, Render requires a paid instance —
> add a `disk:` block to `render.yaml` and stop committing `backend/chroma_db/`.

## 5. Updating the project (the routine)

1. Edit the relevant files locally.
2. Run the same checks CI runs:
   ```bash
   cd backend && python -m unittest discover -s tests -t .
   cd ../frontend && npm ci && npm run build
   ```
3. Review the diff with `git diff`.
4. Commit and push to `main`.
5. GitHub Actions runs `ci.yml`; the matching deploy workflow ships the change.
6. Verify the live app at the URLs in the README and the Actions run summary.

## 6. Refreshing the legal corpus (controlled)

Only do this when the dataset or ingestion pipeline actually changes.

1. Actions → **Ingest Legal Corpus** → **Run workflow**.
2. Choose `sample` (safe dev subset), `resume`, or `full`. A `full` run requires
   typing `INGEST` in the confirmation field.
3. The workflow ingests, commits the refreshed `backend/chroma_db`, and pushes —
   which automatically triggers `deploy-backend.yml`, so production picks up the
   new corpus with no manual deploy.

## 7. Rolling back a bad deployment

Nothing is force-pushed and no history is rewritten, so rollback is ordinary Git.

**Fastest — frontend:**
- Vercel → Project → Deployments → pick the last good deployment → **Promote to
  Production**. The production URL is unchanged.

**Fastest — backend:**
- Render → Service → Deploys → pick the last healthy deploy → **Redeploy**.

**Permanent — both:**
```bash
git revert <bad_commit_sha>      # creates a new commit that undoes it
git push origin main             # CI runs, then the matching deploy workflow
```
Reverting never deletes data: the vector store and metadata DB are additive, and
no workflow runs destructive migrations.

## 8. Safety guarantees

- Deploys only run after tests pass (`needs: test`).
- Render's own auto-deploy is disabled; releases go through CI.
- Preview/pull-request runs are never production (no deploy workflow runs on PRs).
- Secrets stay in GitHub/Render/Vercel settings, never in source.
- `backend/chroma_db` is never reset by a code deploy; ingestion upserts by
  deterministic id.
- No automatic destructive database migration exists in the pipeline.
