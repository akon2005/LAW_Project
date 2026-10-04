# VIDHIVEDA — RAG Pipeline

## 1. Query understanding (no invented entities)

`LegalQueryAnalyzer` extracts only what is literally present in the query:

- statutory sections (normalized — see below);
- constitutional articles;
- legal issue (from a fixed phrase list, e.g. "self-defence");
- court, jurisdiction, year / year range;
- requested research task (`precedent_retrieval`, `outcome_prediction`,
  `trend_analysis`, `summarization`, `provision_lookup`).

The retrieval text combines **case facts + normalized sections + issue**
(Step 12 of the specification).

## 2. Section normalization

`LegalSectionNormalizer` accepts `IPC 302`, `Section 302 IPC`, `Sec. 302`,
`302 IPC`, `BNS 103`, `Section 103 of Bharatiya Nyaya Sanhita`, … and returns
`{statute, section, original_text, normalized_text}`. The original wording is
preserved. IPC and BNS are **not** assumed equivalent; an explicit equivalence
map can be supplied via `SECTION_EQUIVALENCE_MAP` but is only reported alongside.

## 3. Hybrid retrieval

- **Semantic** — query embedding → ChromaDB top-K.
- **Metadata filter** — court, `year`, `year_from`/`year_to`. Only filters backed
  by real stored metadata are applied.
- **Section filter** — when specific sections are requested, a wider pool is
  fetched and post-filtered against stored `sections` metadata and the chunk
  text. If nothing matches, the result is empty rather than padded.

## 4. Reranking

`reranker.rerank` keeps three stages separate: dense → BM25 → optional
cross-encoder. It is **off by default** (`USE_RERANKER=false`); enabling it adds
a dependency-free BM25 pass and, if the cross-encoder model is available, a
semantic rerank. Any failure degrades gracefully to dense order.

## 5. Evidence pack and generation

Only retrieved chunks are placed in the prompt, labelled `SOURCE 1…n`. The
system prompt forbids inventing cases, citations, statutes, dates, sections or
facts, and instructs the model to state when evidence is insufficient.

Providers: Hugging Face router / OpenAI / Anthropic, selected by
`LLM_PROVIDER`. For Hugging Face, `HF_API_TOKEN` is used when set; otherwise the
token stored by `huggingface-cli login` is picked up automatically, so a locally
authenticated machine works without duplicating the token in `.env`. Without any
usable key the pipeline stays retrieval-only and says so
(`answer_origin = "retrieval_template"`).

## 6. Citation verification

`citation_service.verify` maps `[SOURCE n]` markers, numeric markers, case names
and source filenames back onto the retrieved chunks. Verified citations are
returned in `citations`; anything that cannot be mapped is returned in
`unverified_references` and is never rendered as a verified citation.

## 7. Confidence and low-confidence handling

- `confidence` is a **retrieval** number (best dense similarity).
- `prediction.confidence` is a **model** number and only appears when a model
  exists.
- Below `LOW_CONFIDENCE_THRESHOLD` the API returns `status="low_confidence"` and
  no answer is generated.
- Below `MIN_EVIDENCE_SCORE`, `evidence_sufficient=false`.

## 8. No-evidence behaviour

If retrieval returns no sufficiently relevant evidence, the API does not
generate a pretend answer. It returns a message such as
`No sufficiently relevant legal evidence was retrieved for this query.` and
suggests narrowing by section, court or year.

## 9. Structured output

`POST /api/research` returns `answer`, `legal_provisions`, `prediction`,
`precedents`/`sources`, `citations`, `retrieval`, `confidence`,
`evidence_sufficient`, `limitations`, `disclaimer` and `versions`.
