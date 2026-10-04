# VIDHIVEDA — Evaluation

Evaluation is never fabricated. A metric is only reported when the data needed
to compute it exists. Ground-truth relevance ids are used **exactly as supplied**
— the evaluator never widens the relevant set to whatever happened to be
retrieved.

## 1. Gold set (Step 40)

Schema — `backend/evaluation/gold_queries.jsonl`:

```json
{"query": "...", "expected_documents": [], "expected_sections": [], "family": "", "notes": ""}
```

An entry with an empty `expected_documents` is unlabeled and excluded from
metric computation.

### Derived gold set

Because no human-validated legal relevance labels exist for this corpus, a
**machine-derived, reproducible** set is generated from the corpus's own stored
metadata:

```bash
cd backend
python scripts/build_gold_set.py --documents 10 --chunks 10 --seed 7
```

Two families (each entry's `notes` states its derivation):

| Family | Query | Relevant ids |
|---|---|---|
| `source_document` | a judgment's real case name + year | every stored chunk of that source PDF |
| `chunk_self_retrieval` | a real snippet from a chunk | that exact `chunk_id` |

**These labels are machine-derived from provenance, not human-validated legal
relevance.** They are objective and reproducible, but a human must still review
any entry before it is called ground truth.

## 2. Running evaluation

```bash
cd backend
python scripts/evaluate.py --no-rerank --top-k 20
python scripts/evaluate.py --rerank    --top-k 20
python scripts/evaluate.py --json evaluation/last_run.json
```

## 3. Measured retrieval metrics (this corpus, seed 7, top-k 20)

| Metric | Dense only | Dense + BM25 + cross-encoder |
|---|---|---|
| Recall@5 | 0.4591 | 0.4625 |
| Recall@10 | 0.4625 | 0.4655 |
| Recall@20 | 0.4655 | 0.4655 |
| MRR | 0.7705 | **0.8917** |
| nDCG@10 | 0.4917 | **0.5697** |

By family:

| Family | MRR (dense) | MRR (rerank) | nDCG@10 (dense) | nDCG@10 (rerank) |
|---|---|---|---|---|
| `chunk_self_retrieval` | 0.7583 | **0.9000** | 0.7931 | **0.9000** |
| `source_document` | 0.7827 | **0.8833** | 0.1904 | **0.2394** |

Reranking reorders the same candidate set, so recall is unchanged and ranking
metrics (MRR, nDCG) improve. `source_document` recall is naturally low because a
single judgment spans 12–1222 chunks (avg ~94) while only the top 20 are
retrieved; the high MRR shows the first relevant chunk is usually ranked near the
top.

## 4. Generation and citation metrics

Citation metrics come from the citation verifier's own output. Collect
`POST /api/research` responses and pass their `citations` and
`unverified_references` to `evaluation.metrics.evaluate_citations` (citation
coverage, validity, unsupported rate).

Observed on a live query ("breach of contract damages"): 5 citations, 5 verified,
0 unverified. That is a single sample, not an aggregate score.

## 5. Outcome metrics

Read from the trained model's recorded metrics (`/api/model/status` →
`outcome_model.metrics`). No model is trained in this repository, so outcome
metrics are **UNAVAILABLE** (no labels; see [model.md](model.md)).

## 6. Tests

```bash
cd backend
python -m unittest discover -s tests -t .
```

Covers data/ids/chunking, retrieval filtering, query analysis, citation metrics,
gold-set parsing, ML label handling and the outcome-model unavailability path,
and the API surface.

Not claimed: outcome-model accuracy/F1, generation-quality scores.
