#!/usr/bin/env python3
"""
ChromaDB Showcase & Interactive Studio
Stand-alone visual explorer and vector database showcase for VIDHIVEDA.
"""
import os
import sys
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

# Ensure backend root is on PYTHONPATH
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import chromadb
from fastapi import FastAPI, Query, HTTPException, Body
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("chroma_showcase")

CHROMA_PATH = str(BACKEND_ROOT / "chroma_db")
COLLECTION_NAME = "vidhiveda_legal_cases"

# Initialize Chroma client
client = chromadb.PersistentClient(path=CHROMA_PATH)

# Lazy embedding service loader
_embedding_service = None

def get_embedding_service():
    global _embedding_service
    if _embedding_service is None:
        try:
            from app.rag.embedding_service import embedding_service
            _embedding_service = embedding_service
        except Exception as e:
            logger.warning(f"Could not load backend embedding service: {e}")
            from sentence_transformers import SentenceTransformer
            class FallbackEmbedder:
                def __init__(self):
                    self.model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
                def embed_query(self, text: str):
                    emb = self.model.encode(text, normalize_embeddings=True)
                    return emb.tolist()
            _embedding_service = FallbackEmbedder()
    return _embedding_service

app = FastAPI(title="ChromaDB Showcase & Studio", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache some corpus summary stats
cached_stats = {}

def compute_corpus_stats():
    global cached_stats
    if cached_stats:
        return cached_stats
    try:
        col = client.get_collection(COLLECTION_NAME)
        total_count = col.count()
        # Sample first 200 documents for distribution stats
        sample = col.get(limit=250, include=["metadatas"])
        years = {}
        courts = {}
        articles_count = {}
        for m in sample.get("metadatas", []):
            yr = m.get("year")
            if yr:
                years[str(yr)] = years.get(str(yr), 0) + 1
            ct = m.get("court")
            if ct:
                courts[ct] = courts.get(ct, 0) + 1
            arts = m.get("articles")
            if arts and isinstance(arts, str):
                for a in [x.strip() for x in arts.split(",") if x.strip()]:
                    articles_count[a] = articles_count.get(a, 0) + 1

        cached_stats = {
            "total_count": total_count,
            "years_sample": dict(sorted(years.items())),
            "courts_sample": courts,
            "top_articles": sorted(articles_count.items(), key=lambda x: x[1], reverse=True)[:10]
        }
    except Exception as e:
        logger.error(f"Error computing stats: {e}")
        cached_stats = {"total_count": 0, "years_sample": {}, "courts_sample": {}, "top_articles": []}
    return cached_stats


@app.get("/api/overview")
async def get_overview():
    cols = client.list_collections()
    col_info = []
    for c in cols:
        col_info.append({
            "name": c.name,
            "count": c.count(),
            "metadata": c.metadata or {}
        })
    stats = compute_corpus_stats()
    return {
        "status": "online",
        "chroma_version": chromadb.__version__,
        "persist_directory": CHROMA_PATH,
        "collections": col_info,
        "active_collection": COLLECTION_NAME,
        "total_documents": stats["total_count"],
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
        "vector_dimensions": 384,
        "distance_metric": "cosine",
        "sample_insights": stats
    }


@app.get("/api/documents")
async def get_documents(
    page: int = Query(1, ge=1),
    limit: int = Query(15, ge=1, le=100),
    collection: str = Query(COLLECTION_NAME),
    search_id: Optional[str] = Query(None)
):
    try:
        col = client.get_collection(collection)
        total = col.count()
        offset = (page - 1) * limit

        if search_id:
            res = col.get(ids=[search_id], include=["documents", "metadatas"])
            items = []
            for i in range(len(res.get("ids", []))):
                items.append({
                    "id": res["ids"][i],
                    "document": res["documents"][i] if res.get("documents") else "",
                    "metadata": res["metadatas"][i] if res.get("metadatas") else {}
                })
            return {"items": items, "total": len(items), "page": 1, "total_pages": 1}

        # Chroma doesn't have native SQL-like offset in .get(), but limit + ID slice or get limit
        # For showcase paging, get up to limit records
        res = col.get(limit=min(limit, 100), include=["documents", "metadatas"])
        items = []
        for i in range(len(res.get("ids", []))):
            items.append({
                "id": res["ids"][i],
                "document": res["documents"][i] if res.get("documents") else "",
                "metadata": res["metadatas"][i] if res.get("metadatas") else {}
            })
        return {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/search")
async def semantic_search(payload: Dict[str, Any] = Body(...)):
    query_text = payload.get("query", "").strip()
    top_k = int(payload.get("top_k", 5))
    collection_name = payload.get("collection", COLLECTION_NAME)
    year_filter = payload.get("year")
    court_filter = payload.get("court")

    if not query_text:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    embedder = get_embedding_service()
    query_vector = embedder.embed_query(query_text)

    col = client.get_collection(collection_name)
    where_filter = {}
    if year_filter:
        where_filter["year"] = int(year_filter)
    if court_filter:
        where_filter["court"] = court_filter

    query_args = {
        "query_embeddings": [query_vector],
        "n_results": min(top_k, 25),
        "include": ["metadatas", "documents", "distances"]
    }
    if where_filter:
        query_args["where"] = where_filter

    try:
        results = col.query(**query_args)
    except Exception as e:
        logger.warning(f"Chroma filtered search failed ({e}), falling back to unfiltered.")
        query_args.pop("where", None)
        results = col.query(**query_args)

    ids = results.get("ids", [[]])[0]
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    dists = results.get("distances", [[]])[0]

    hits = []
    for i in range(len(ids)):
        dist = float(dists[i]) if i < len(dists) else 0.0
        # Cosine distance ranges from 0 to 2; similarity score approx (1 - dist)
        similarity_score = max(0.0, min(1.0, 1.0 - (dist / 2.0 if dist > 1.0 else dist)))
        similarity_pct = round(similarity_score * 100, 1)

        hits.append({
            "id": ids[i],
            "distance": round(dist, 4),
            "similarity_pct": similarity_pct,
            "document": docs[i] if i < len(docs) else "",
            "metadata": metas[i] if i < len(metas) else {}
        })

    return {
        "query": query_text,
        "count": len(hits),
        "collection": collection_name,
        "hits": hits
    }


@app.get("/api/peek")
async def peek_collection(limit: int = Query(5, ge=1, le=20)):
    col = client.get_collection(COLLECTION_NAME)
    res = col.peek(limit=limit)
    return {
        "collection": COLLECTION_NAME,
        "ids": res.get("ids", []),
        "documents": [d[:300] + "..." if len(d) > 300 else d for d in res.get("documents", [])],
        "metadatas": res.get("metadatas", [])
    }


# HTML Showcase Dashboard
@app.get("/", response_class=HTMLResponse)
async def serve_showcase_dashboard():
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ChromaDB Interactive Studio & Showcase | VIDHIVEDA</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600&family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-base: #090d16;
      --bg-surface: #101726;
      --bg-surface-elevated: #162033;
      --bg-card: rgba(22, 32, 51, 0.7);
      --border-subtle: rgba(255, 255, 255, 0.08);
      --border-highlight: rgba(249, 115, 22, 0.35);
      --chroma-orange: #f97316;
      --chroma-glow: rgba(249, 115, 22, 0.4);
      --accent-cyan: #06b6d4;
      --accent-emerald: #10b981;
      --accent-purple: #8b5cf6;
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --text-dim: #64748b;
      --font-sans: 'Plus Jakarta Sans', system-ui, sans-serif;
      --font-mono: 'Fira Code', monospace;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg-base);
      color: var(--text-main);
      font-family: var(--font-sans);
      min-height: 100vh;
      overflow-x: hidden;
      line-height: 1.5;
      background-image:
        radial-gradient(circle at 15% 15%, rgba(249, 115, 22, 0.08) 0%, transparent 40%),
        radial-gradient(circle at 85% 85%, rgba(6, 182, 212, 0.06) 0%, transparent 40%);
    }

    /* Top Navigation */
    header {
      background: rgba(16, 23, 38, 0.85);
      backdrop-filter: blur(16px);
      border-bottom: 1px solid var(--border-subtle);
      position: sticky;
      top: 0;
      z-index: 50;
      padding: 0.85rem 2rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .brand-group {
      display: flex;
      align-items: center;
      gap: 1rem;
    }

    .chroma-logo-badge {
      display: flex;
      align-items: center;
      gap: 0.6rem;
      background: linear-gradient(135deg, rgba(249, 115, 22, 0.15), rgba(249, 115, 22, 0.05));
      border: 1px solid rgba(249, 115, 22, 0.3);
      padding: 0.4rem 0.85rem;
      border-radius: 9999px;
    }

    .chroma-dot {
      width: 10px;
      height: 10px;
      background: var(--chroma-orange);
      border-radius: 50%;
      box-shadow: 0 0 12px var(--chroma-orange);
      animation: pulse 2s infinite;
    }

    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.6; transform: scale(0.9); }
    }

    .brand-title {
      font-weight: 800;
      font-size: 1.15rem;
      letter-spacing: -0.02em;
      background: linear-gradient(135deg, #ffffff 40%, #fdba74 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }

    .meta-pills {
      display: flex;
      align-items: center;
      gap: 0.6rem;
    }

    .pill {
      font-size: 0.75rem;
      font-family: var(--font-mono);
      padding: 0.25rem 0.65rem;
      border-radius: 6px;
      background: var(--bg-surface-elevated);
      border: 1px solid var(--border-subtle);
      color: var(--text-muted);
      display: flex;
      align-items: center;
      gap: 0.35rem;
    }
    .pill.active {
      color: #34d399;
      border-color: rgba(52, 211, 153, 0.3);
      background: rgba(52, 211, 153, 0.1);
    }
    .pill.orange {
      color: #fdba74;
      border-color: rgba(249, 115, 22, 0.3);
      background: rgba(249, 115, 22, 0.1);
    }

    /* Container */
    .container {
      max-width: 1380px;
      margin: 0 auto;
      padding: 2rem;
    }

    /* Metric Grid */
    .metric-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 1.25rem;
      margin-bottom: 2rem;
    }

    .metric-card {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: 12px;
      padding: 1.25rem 1.5rem;
      backdrop-filter: blur(12px);
      position: relative;
      overflow: hidden;
      transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .metric-card:hover {
      transform: translateY(-2px);
      border-color: rgba(249, 115, 22, 0.4);
    }
    .metric-card::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 3px;
      background: linear-gradient(90deg, var(--chroma-orange), transparent);
    }

    .metric-label {
      font-size: 0.8rem;
      font-weight: 500;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 0.4rem;
    }

    .metric-value {
      font-size: 1.85rem;
      font-weight: 800;
      color: #ffffff;
      letter-spacing: -0.02em;
    }

    .metric-sub {
      font-size: 0.75rem;
      color: var(--text-dim);
      margin-top: 0.3rem;
      font-family: var(--font-mono);
    }

    /* Navigation Tabs */
    .tabs-bar {
      display: flex;
      gap: 0.5rem;
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: 10px;
      padding: 0.35rem;
      margin-bottom: 2rem;
      width: fit-content;
    }

    .tab-btn {
      background: transparent;
      border: none;
      color: var(--text-muted);
      font-family: var(--font-sans);
      font-weight: 600;
      font-size: 0.88rem;
      padding: 0.6rem 1.2rem;
      border-radius: 8px;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 0.5rem;
      transition: all 0.2s ease;
    }

    .tab-btn:hover {
      color: #ffffff;
    }

    .tab-btn.active {
      background: var(--chroma-orange);
      color: #ffffff;
      box-shadow: 0 4px 14px var(--chroma-glow);
    }

    /* Tab Panes */
    .tab-pane {
      display: none;
      animation: fadeIn 0.25s ease;
    }
    .tab-pane.active {
      display: block;
    }

    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(6px); }
      to { opacity: 1; transform: translateY(0); }
    }

    /* Search Playground */
    .search-panel {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: 16px;
      padding: 1.75rem;
      margin-bottom: 2rem;
      backdrop-filter: blur(12px);
    }

    .search-input-wrapper {
      position: relative;
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }

    .search-box {
      flex: 1;
      background: var(--bg-surface-elevated);
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-radius: 12px;
      padding: 0.95rem 1.25rem;
      color: #ffffff;
      font-size: 1rem;
      font-family: var(--font-sans);
      outline: none;
      transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }

    .search-box:focus {
      border-color: var(--chroma-orange);
      box-shadow: 0 0 0 3px rgba(249, 115, 22, 0.2);
    }

    .btn-search {
      background: linear-gradient(135deg, #f97316 0%, #ea580c 100%);
      color: white;
      border: none;
      border-radius: 12px;
      font-weight: 700;
      font-size: 0.95rem;
      padding: 0 1.75rem;
      height: 52px;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 0.5rem;
      box-shadow: 0 4px 15px rgba(249, 115, 22, 0.35);
      transition: transform 0.15s ease, filter 0.15s ease;
    }

    .btn-search:hover {
      transform: translateY(-1px);
      filter: brightness(1.1);
    }

    .btn-search:active {
      transform: translateY(1px);
    }

    /* Preset Showcase Queries */
    .presets-container {
      margin-top: 1.2rem;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 0.5rem;
    }

    .presets-title {
      font-size: 0.8rem;
      color: var(--text-dim);
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-right: 0.3rem;
    }

    .preset-chip {
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--border-subtle);
      color: var(--text-muted);
      border-radius: 8px;
      padding: 0.35rem 0.75rem;
      font-size: 0.8rem;
      cursor: pointer;
      transition: all 0.2s ease;
    }

    .preset-chip:hover {
      background: rgba(249, 115, 22, 0.15);
      border-color: rgba(249, 115, 22, 0.4);
      color: #fdba74;
    }

    .search-controls {
      display: flex;
      gap: 1.5rem;
      align-items: center;
      margin-top: 1rem;
      padding-top: 1rem;
      border-top: 1px solid var(--border-subtle);
      font-size: 0.85rem;
      color: var(--text-muted);
    }

    .control-item {
      display: flex;
      align-items: center;
      gap: 0.6rem;
    }

    .control-item input[type="range"] {
      accent-color: var(--chroma-orange);
      cursor: pointer;
    }

    /* Results section */
    .results-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1rem;
    }

    .results-count {
      font-size: 0.95rem;
      font-weight: 600;
      color: var(--text-muted);
    }

    .hit-card {
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: 14px;
      padding: 1.5rem;
      margin-bottom: 1.25rem;
      transition: border-color 0.2s ease;
      position: relative;
    }

    .hit-card:hover {
      border-color: rgba(249, 115, 22, 0.3);
    }

    .hit-top {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 0.85rem;
      gap: 1rem;
    }

    .hit-case-name {
      font-size: 1.15rem;
      font-weight: 700;
      color: #ffffff;
      line-height: 1.3;
    }

    .similarity-badge {
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      min-width: 110px;
    }

    .sim-pct {
      font-size: 1.1rem;
      font-weight: 800;
      color: #10b981;
      font-family: var(--font-mono);
    }

    .sim-dist {
      font-size: 0.75rem;
      color: var(--text-dim);
      font-family: var(--font-mono);
    }

    .meta-tags {
      display: flex;
      flex-wrap: wrap;
      gap: 0.45rem;
      margin-bottom: 1rem;
    }

    .meta-tag {
      font-size: 0.75rem;
      background: var(--bg-surface-elevated);
      border: 1px solid rgba(255, 255, 255, 0.08);
      padding: 0.2rem 0.55rem;
      border-radius: 6px;
      color: #cbd5e1;
    }

    .meta-tag.highlight {
      background: rgba(139, 92, 246, 0.15);
      border-color: rgba(139, 92, 246, 0.3);
      color: #c4b5fd;
    }

    .doc-excerpt {
      background: rgba(9, 13, 22, 0.6);
      border: 1px solid var(--border-subtle);
      border-radius: 8px;
      padding: 1rem 1.2rem;
      font-size: 0.88rem;
      color: #e2e8f0;
      line-height: 1.6;
      white-space: pre-wrap;
      font-family: var(--font-sans);
      max-height: 220px;
      overflow-y: auto;
    }

    .hit-actions {
      display: flex;
      gap: 0.75rem;
      margin-top: 0.85rem;
    }

    .btn-action {
      background: transparent;
      border: 1px solid var(--border-subtle);
      color: var(--text-muted);
      border-radius: 6px;
      padding: 0.3rem 0.65rem;
      font-size: 0.75rem;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 0.3rem;
      transition: all 0.2s ease;
    }

    .btn-action:hover {
      color: white;
      border-color: rgba(255, 255, 255, 0.25);
    }

    /* Corpus Explorer Table */
    .table-container {
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: 14px;
      overflow: hidden;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      text-align: left;
    }

    th {
      background: var(--bg-surface-elevated);
      padding: 0.85rem 1.2rem;
      font-size: 0.8rem;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      border-bottom: 1px solid var(--border-subtle);
    }

    td {
      padding: 0.95rem 1.2rem;
      font-size: 0.88rem;
      border-bottom: 1px solid var(--border-subtle);
      color: #cbd5e1;
    }

    tr:hover td {
      background: rgba(255, 255, 255, 0.02);
    }

    /* Modal */
    .modal-overlay {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0, 0, 0, 0.75);
      backdrop-filter: blur(8px);
      display: none;
      align-items: center;
      justify-content: center;
      z-index: 100;
      padding: 2rem;
    }

    .modal-overlay.active {
      display: flex;
    }

    .modal-box {
      background: var(--bg-surface);
      border: 1px solid var(--border-highlight);
      border-radius: 16px;
      max-width: 800px;
      width: 100%;
      max-height: 85vh;
      overflow-y: auto;
      padding: 2rem;
      position: relative;
    }

    .modal-close {
      position: absolute;
      top: 1.2rem;
      right: 1.2rem;
      background: transparent;
      border: none;
      color: var(--text-muted);
      font-size: 1.4rem;
      cursor: pointer;
    }

    /* Code Snippet Block */
    pre.code-block {
      background: #060910;
      border: 1px solid var(--border-subtle);
      border-radius: 8px;
      padding: 1rem;
      font-family: var(--font-mono);
      font-size: 0.82rem;
      color: #38bdf8;
      overflow-x: auto;
      margin-top: 0.6rem;
    }

    /* Empty and Loading States */
    .spinner {
      border: 3px solid rgba(255, 255, 255, 0.1);
      border-top-color: var(--chroma-orange);
      border-radius: 50%;
      width: 24px;
      height: 24px;
      animation: spin 0.8s linear infinite;
      display: inline-block;
    }

    @keyframes spin { to { transform: rotate(360deg); } }
  </style>
</head>
<body>

  <!-- Top Bar -->
  <header>
    <div class="brand-group">
      <div class="chroma-logo-badge">
        <div class="chroma-dot"></div>
        <span style="font-weight: 700; font-size: 0.9rem; color: #fdba74;">ChromaDB</span>
      </div>
      <div class="brand-title">Vector Engine Showcase · VIDHIVEDA</div>
    </div>
    <div class="meta-pills">
      <div class="pill active" id="pill-status">● Live Engine</div>
      <div class="pill orange" id="pill-count">Loading vectors...</div>
      <div class="pill" id="pill-dim">384-D Cosine</div>
      <div class="pill" id="pill-ver">ChromaDB</div>
    </div>
  </header>

  <div class="container">
    <!-- Top Metric Cards -->
    <div class="metric-grid">
      <div class="metric-card">
        <div class="metric-label">Vector Store Volume</div>
        <div class="metric-value" id="card-total-docs">—</div>
        <div class="metric-sub" id="card-active-col">vidhiveda_legal_cases</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Embedding Dimensions</div>
        <div class="metric-value">384 <span style="font-size: 1rem; font-weight: 500; color: var(--text-dim);">dims</span></div>
        <div class="metric-sub">all-MiniLM-L6-v2</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Similarity Metric</div>
        <div class="metric-value">Cosine <span style="font-size: 1rem; font-weight: 500; color: var(--text-dim);">HNSW</span></div>
        <div class="metric-sub">Space: cosine</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Active Storage Path</div>
        <div class="metric-value" style="font-size: 1.25rem; font-family: var(--font-mono); margin-top: 0.4rem; color: #38bdf8;">/backend/chroma_db</div>
        <div class="metric-sub">Persistent SQLite + HNSW segment</div>
      </div>
    </div>

    <!-- Navigation Tabs -->
    <div class="tabs-bar">
      <button class="tab-btn active" onclick="switchTab('search')">
        <svg width="16" height="16" fill="currentColor" viewBox="0 0 24 24"><path d="M10 18a7.952 7.952 0 0 0 4.897-1.688l4.396 4.395 1.414-1.414-4.395-4.396A7.952 7.952 0 0 0 18 10c0-4.411-3.589-8-8-8s-8 3.589-8 8 3.589 8 8 8zm0-14c3.309 0 6 2.691 6 6s-2.691 6-6 6-6-2.691-6-6 2.691-6 6-6z"/></svg>
        Semantic Search Showcase
      </button>
      <button class="tab-btn" onclick="switchTab('corpus')">
        <svg width="16" height="16" fill="currentColor" viewBox="0 0 24 24"><path d="M19 4H5c-1.103 0-2 .897-2 2v12c0 1.103.897 2 2 2h14c1.103 0 2-.897 2-2V6c0-1.103-.897-2-2-2zM5 18V6h14l.002 12H5z"/><path d="M7 8h10v2H7zm0 4h10v2H7z"/></svg>
        Chunk & Document Explorer
      </button>
      <button class="tab-btn" onclick="switchTab('analytics')">
        <svg width="16" height="16" fill="currentColor" viewBox="0 0 24 24"><path d="M3 3v18h18v-2H5V3H3zm4 14h2v-5H7v5zm4 0h2v-9h-2v9zm4 0h2v-3h-2v3zm4 0h2v-7h-2v7z"/></svg>
        Corpus Analytics
      </button>
      <button class="tab-btn" onclick="switchTab('api')">
        <svg width="16" height="16" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 14.5v-9l6 4.5-6 4.5z"/></svg>
        Chroma Client API
      </button>
    </div>

    <!-- TAB 1: Search Showcase -->
    <div id="tab-search" class="tab-pane active">
      <div class="search-panel">
        <div class="search-input-wrapper">
          <input
            type="text"
            id="searchInput"
            class="search-box"
            placeholder="Search the legal vector store (e.g. 'arbitration clause', 'Article 21 privacy', 'cheque dishonour section 138')..."
            value="arbitration clause commercial contract enforcement"
          />
          <button class="btn-search" id="searchBtn" onclick="executeSearch()">
            <span>Query ChromaDB</span>
          </button>
        </div>

        <div class="presets-container">
          <span class="presets-title">Showcase Prompts:</span>
          <span class="preset-chip" onclick="setPreset('Arbitration clause enforcement in commercial dispute')">Arbitration Enforcement</span>
          <span class="preset-chip" onclick="setPreset('Article 21 right to privacy and personal liberty')">Article 21 & Privacy</span>
          <span class="preset-chip" onclick="setPreset('Section 138 Negotiable Instruments Act cheque bounce notice')">Section 138 NI Act</span>
          <span class="preset-chip" onclick="setPreset('Insolvency and Bankruptcy Code moratorium under Section 14')">IBC Moratorium</span>
          <span class="preset-chip" onclick="setPreset('Anticipatory bail exceptional circumstances and parameters')">Anticipatory Bail</span>
        </div>

        <div class="search-controls">
          <div class="control-item">
            <span>Top-K Results:</span>
            <input type="range" id="topKSlider" min="1" max="15" value="5" oninput="document.getElementById('topKVal').innerText = this.value">
            <span id="topKVal" style="font-weight: 700; color: #fdba74;">5</span>
          </div>
          <div class="control-item">
            <span>Collection:</span>
            <span style="font-family: var(--font-mono); color: #38bdf8;">vidhiveda_legal_cases</span>
          </div>
        </div>
      </div>

      <div class="results-header">
        <div class="results-count" id="resultsCount">Ready to query vector database</div>
        <div id="searchSpinner" style="display: none;"><div class="spinner"></div></div>
      </div>

      <div id="searchResultsList"></div>
    </div>

    <!-- TAB 2: Chunk & Document Explorer -->
    <div id="tab-corpus" class="tab-pane">
      <div style="margin-bottom: 1rem; display: flex; justify-content: space-between; align-items: center;">
        <div>
          <h3 style="font-size: 1.15rem; font-weight: 700;">Indexed Chunks Browser</h3>
          <p style="font-size: 0.85rem; color: var(--text-muted);">Explore raw documents and their corresponding vector metadata.</p>
        </div>
        <button class="btn-action" onclick="loadCorpusDocuments()">Refresh List</button>
      </div>

      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Chunk ID</th>
              <th>Case Name</th>
              <th>Court</th>
              <th>Year</th>
              <th>Constitutional Articles</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody id="corpusTableBody">
            <tr><td colspan="6" style="text-align: center; color: var(--text-dim); padding: 2rem;">Loading documents...</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- TAB 3: Analytics -->
    <div id="tab-analytics" class="tab-pane">
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 1.5rem;">
        <div class="hit-card">
          <h4 style="font-size: 1.05rem; font-weight: 700; margin-bottom: 1rem; color: #fdba74;">Most Frequently Cited Articles</h4>
          <div id="articlesList" style="display: flex; flex-direction: column; gap: 0.5rem;">
            <!-- Populated dynamically -->
          </div>
        </div>
        <div class="hit-card">
          <h4 style="font-size: 1.05rem; font-weight: 700; margin-bottom: 1rem; color: #38bdf8;">Judicial Forums in Collection</h4>
          <div id="courtsList" style="display: flex; flex-direction: column; gap: 0.5rem;">
            <!-- Populated dynamically -->
          </div>
        </div>
      </div>
    </div>

    <!-- TAB 4: API & Client Integration -->
    <div id="tab-api" class="tab-pane">
      <div class="hit-card">
        <h4 style="font-size: 1.1rem; font-weight: 700; margin-bottom: 0.5rem; color: #fdba74;">Direct Python Client Integration</h4>
        <p style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 1rem;">
          How VIDHIVEDA connects to this exact ChromaDB persistent store in production:
        </p>
        <pre class="code-block">
import chromadb
from sentence_transformers import SentenceTransformer

# 1. Connect to persistent store
client = chromadb.PersistentClient(path="backend/chroma_db")

# 2. Access the Indian case-law collection
collection = client.get_collection(
    name="vidhiveda_legal_cases"
)

# 3. Vectorize query & search top-K nearest neighbors
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
query_vec = model.encode("arbitration clause breach", normalize_embeddings=True).tolist()

results = collection.query(
    query_embeddings=[query_vec],
    n_results=5,
    include=["metadatas", "documents", "distances"]
)

for doc_id, dist, meta in zip(results['ids'][0], results['distances'][0], results['metadatas'][0]):
    print(f"Match: {meta.get('case_name')} | Distance: {dist:.4f}")
        </pre>
      </div>

      <div class="hit-card" style="margin-top: 1.5rem;">
        <h4 style="font-size: 1.1rem; font-weight: 700; margin-bottom: 0.5rem; color: #34d399;">Test ChromaDB Peek</h4>
        <p style="font-size: 0.85rem; color: var(--text-muted);">Inspect raw peek payload from collection:</p>
        <button class="btn-action" style="margin-top: 0.5rem;" onclick="testPeek()">Execute collection.peek(3)</button>
        <pre class="code-block" id="peekOutput">// Click execute to inspect peek output...</pre>
      </div>
    </div>
  </div>

  <!-- Detail Modal -->
  <div class="modal-overlay" id="detailModal">
    <div class="modal-box">
      <button class="modal-close" onclick="closeModal()">&times;</button>
      <h3 id="modalTitle" style="font-size: 1.3rem; margin-bottom: 0.5rem; color: #ffffff;">Case Details</h3>
      <div id="modalMeta" class="meta-tags" style="margin-bottom: 1rem;"></div>
      <div style="font-size: 0.8rem; font-weight: 600; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.4rem;">Indexed Chunk Text:</div>
      <div id="modalText" class="doc-excerpt" style="max-height: 380px;"></div>
      <div style="font-size: 0.8rem; font-weight: 600; text-transform: uppercase; color: var(--text-muted); margin-top: 1rem; margin-bottom: 0.4rem;">Raw Metadata JSON:</div>
      <pre class="code-block" id="modalRawJson"></pre>
    </div>
  </div>

  <script>
    let overviewData = null;

    async function initDashboard() {
      try {
        const res = await fetch('/api/overview');
        overviewData = await res.json();

        document.getElementById('card-total-docs').innerText = Number(overviewData.total_documents).toLocaleString();
        document.getElementById('pill-count').innerText = `${Number(overviewData.total_documents).toLocaleString()} chunks indexed`;
        document.getElementById('pill-ver').innerText = `v${overviewData.chroma_version}`;

        renderAnalytics(overviewData.sample_insights);
        loadCorpusDocuments();
        executeSearch();
      } catch (err) {
        console.error('Failed to load overview:', err);
      }
    }

    function switchTab(tabName) {
      document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('active'));

      const activeBtn = Array.from(document.querySelectorAll('.tab-btn')).find(b => b.getAttribute('onclick').includes(tabName));
      if (activeBtn) activeBtn.classList.add('active');

      const pane = document.getElementById(`tab-${tabName}`);
      if (pane) pane.classList.add('active');
    }

    function setPreset(query) {
      document.getElementById('searchInput').value = query;
      executeSearch();
    }

    async function executeSearch() {
      const q = document.getElementById('searchInput').value.trim();
      if (!q) return;

      const topK = document.getElementById('topKSlider').value;
      const listEl = document.getElementById('searchResultsList');
      const spinner = document.getElementById('searchSpinner');
      const countEl = document.getElementById('resultsCount');

      spinner.style.display = 'block';
      countEl.innerText = `Searching 9,375 vectors using all-MiniLM-L6-v2...`;

      try {
        const res = await fetch('/api/search', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: q, top_k: parseInt(topK) })
        });
        const data = await res.json();
        spinner.style.display = 'none';

        if (!data.hits || data.hits.length === 0) {
          listEl.innerHTML = `<div style="text-align: center; color: var(--text-dim); padding: 3rem;">No matching documents found.</div>`;
          countEl.innerText = `0 results found`;
          return;
        }

        countEl.innerText = `Found ${data.hits.length} nearest neighbors in vector space (Cosine Metric)`;

        listEl.innerHTML = data.hits.map(hit => {
          const m = hit.metadata || {};
          const caseName = m.case_name || 'Legal Judgment';
          const court = m.court || 'Court of Record';
          const year = m.year || '—';
          const articles = m.articles || '';

          return `
            <div class="hit-card">
              <div class="hit-top">
                <div>
                  <div class="hit-case-name">${escapeHtml(caseName)}</div>
                  <div style="font-size: 0.8rem; color: var(--text-dim); margin-top: 0.2rem;">
                    Petitioner: ${escapeHtml(m.petitioner || 'N/A')} · Respondent: ${escapeHtml(m.respondent || 'N/A')}
                  </div>
                </div>
                <div class="similarity-badge">
                  <span class="sim-pct">${hit.similarity_pct}%</span>
                  <span class="sim-dist">Cosine: ${hit.distance}</span>
                </div>
              </div>

              <div class="meta-tags">
                <span class="meta-tag highlight">${escapeHtml(court)}</span>
                <span class="meta-tag">Year ${year}</span>
                <span class="meta-tag">Chunk ID: ${hit.id}</span>
                ${articles ? `<span class="meta-tag highlight">Articles: ${escapeHtml(articles)}</span>` : ''}
              </div>

              <div class="doc-excerpt">${escapeHtml(hit.document)}</div>

              <div class="hit-actions">
                <button class="btn-action" onclick="openDetails('${hit.id}', ${escapeAttr(JSON.stringify(hit))})">
                  Inspect Raw Metadata & Vector ID
                </button>
              </div>
            </div>
          `;
        }).join('');
      } catch (err) {
        spinner.style.display = 'none';
        countEl.innerText = `Error performing vector search: ${err.message}`;
      }
    }

    async function loadCorpusDocuments() {
      const tbody = document.getElementById('corpusTableBody');
      try {
        const res = await fetch('/api/documents?page=1&limit=15');
        const data = await res.json();

        if (!data.items || data.items.length === 0) {
          tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;">No documents returned.</td></tr>`;
          return;
        }

        tbody.innerHTML = data.items.map(item => {
          const m = item.metadata || {};
          return `
            <tr>
              <td style="font-family: var(--font-mono); color: #fdba74;">${escapeHtml(item.id)}</td>
              <td style="font-weight: 600;">${escapeHtml(m.case_name || 'N/A')}</td>
              <td>${escapeHtml(m.court || 'N/A')}</td>
              <td>${m.year || '—'}</td>
              <td style="font-size: 0.8rem; color: var(--text-muted);">${escapeHtml(m.articles || '—')}</td>
              <td>
                <button class="btn-action" onclick="openDetails('${item.id}', ${escapeAttr(JSON.stringify(item))})">
                  View Chunk
                </button>
              </td>
            </tr>
          `;
        }).join('');
      } catch (err) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color: red;">Error: ${err.message}</td></tr>`;
      }
    }

    function renderAnalytics(insights) {
      if (!insights) return;
      const articlesEl = document.getElementById('articlesList');
      if (insights.top_articles && insights.top_articles.length > 0) {
        articlesEl.innerHTML = insights.top_articles.map(([art, cnt]) => `
          <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(255,255,255,0.03); padding: 0.5rem 0.8rem; border-radius: 6px;">
            <span style="font-weight: 600; font-size: 0.85rem; color: #e2e8f0;">${escapeHtml(art)}</span>
            <span class="pill" style="font-size: 0.75rem;">${cnt} citations in sample</span>
          </div>
        `).join('');
      }

      const courtsEl = document.getElementById('courtsList');
      if (insights.courts_sample) {
        courtsEl.innerHTML = Object.entries(insights.courts_sample).map(([ct, cnt]) => `
          <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(255,255,255,0.03); padding: 0.5rem 0.8rem; border-radius: 6px;">
            <span style="font-weight: 600; font-size: 0.85rem; color: #e2e8f0;">${escapeHtml(ct)}</span>
            <span class="pill active" style="font-size: 0.75rem;">${cnt} cases</span>
          </div>
        `).join('');
      }
    }

    async function testPeek() {
      const output = document.getElementById('peekOutput');
      output.innerText = 'Calling collection.peek(3)...';
      try {
        const res = await fetch('/api/peek?limit=3');
        const data = await res.json();
        output.innerText = JSON.stringify(data, null, 2);
      } catch (err) {
        output.innerText = 'Error: ' + err.message;
      }
    }

    function openDetails(id, item) {
      const modal = document.getElementById('detailModal');
      const m = item.metadata || {};
      document.getElementById('modalTitle').innerText = m.case_name || `Chunk ${id}`;
      document.getElementById('modalMeta').innerHTML = `
        <span class="meta-tag highlight">${m.court || 'Court'}</span>
        <span class="meta-tag">Year: ${m.year || 'N/A'}</span>
        <span class="meta-tag">ID: ${id}</span>
        <span class="meta-tag">Date: ${m.judgment_date || 'N/A'}</span>
      `;
      document.getElementById('modalText').innerText = item.document || 'No document text found.';
      document.getElementById('modalRawJson').innerText = JSON.stringify(m, null, 2);
      modal.classList.add('active');
    }

    function closeModal() {
      document.getElementById('detailModal').classList.remove('active');
    }

    function escapeHtml(str) {
      if (!str) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    function escapeAttr(str) {
      if (!str) return "''";
      return JSON.stringify(str);
    }

    window.onload = initDashboard;
  </script>
</body>
</html>
"""

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8008))
    print(f"[*] Starting ChromaDB Showcase Studio at http://localhost:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
