# VIDHIVEDA — OKF v0.2 Implementation

VIDHIVEDA represents its curated legal knowledge in the **Open Knowledge Format
(OKF) v0.2** — an open, human- and agent-friendly representation of knowledge: a
directory of markdown files with YAML frontmatter.

Specification: <https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md>

OKF is **not** Frictionless Data Packages, JSON-LD, RDF, OWL, plain markdown, or a
vector database. Those may be integrated alongside it; they are not substitutes.
The bundle here is conformant to the actual v0.2 specification, not to an invented
look-alike.

---

## 1. Bundle location and structure

The bundle is generated at `backend/knowledge/` (override with `OKF_BUNDLE_DIR`).

```text
backend/knowledge/
    index.md              # bundle-root listing; declares okf_version: "0.2" (§8, §12)
    log.md                # update history, ISO date headings (§9)
    judgments/
        index.md
        <source-pdf-slug>.md      # one concept per source judgment PDF
    courts/
        index.md
        <court-slug>.md           # one concept per court value recorded in the corpus
    legal-sections/
        index.md
        <section-slug>.md         # one concept per section label seen in the corpus
    datasets/
        index.md
        india-case-legal-rag.md
    models/
        index.md
        all-minilm-l6-v2.md
        outcome-model.md
    evaluation/
        index.md
        retrieval-evaluation.md
```

`index.md` and `log.md` are **reserved filenames** (§3.1) and are never concept
documents.

### Concept types produced

| Type | Source | Count (current build) |
|---|---|---|
| `Legal Judgment` | one per source PDF in ChromaDB | 100 |
| `Court` | one per distinct `court` value | 44 |
| `Legal Provision Reference` | one per distinct section label | 316 |

Two distinct court values slugify to the same file name (they differ only by a
trailing word); the builder detects the collision and appends a deterministic
hash suffix rather than letting one concept silently overwrite the other.
| `Dataset` | the Hugging Face corpus | 1 |
| `Embedding Model` | configured embedding model | 1 |
| `Model` | outcome-prediction status (unavailable) | 1 |
| `Evaluation Methodology` | retrieval evaluation | 1 |

## 2. Provenance and honesty rules

Every concept carries traceable provenance. The generator never invents a value
that the corpus does not record:

- **Sources** — each concept has a `sources` entry pointing at the concrete
  artifact it derives from (the Hugging Face dataset). `sources[].resource` is
  always present.
- **Content hash** — judgments carry `content_hash`, a sha256 over the indexed
  chunk text, for lineage and change detection.
- **Statute is not inferred** — the corpus records section labels (e.g.
  `Section 3`) but never the originating Act. `Legal Provision Reference`
  concepts therefore leave `statute` empty and state in the body that the
  statute is not recorded upstream and was deliberately not guessed.
- **Court names are preserved verbatim** — including values truncated by upstream
  OCR. They are not silently "corrected".
- **No judicial text is reproduced as knowledge** — a judgment concept stores
  metadata, an explicitly-labelled verbatim excerpt, and a pointer to the chunk
  ids. It is machine-generated metadata, not judicial language.

### Trust

Concepts are generated and checked by deterministic processes, so they carry:

```yaml
generated: { by: process:vidhiveda-okf-builder/1.0, at: <ISO-8601Z> }
verified:
- { by: process:vidhiveda-okf-validator/1.0, at: <ISO-8601Z> }
```

Because no `human:<id>` actor has confirmed them, every concept derives the trust
tier **`machine-confirmed`** — never `human-reviewed`. This is the honest signal;
human legal review remains outstanding (see "Remaining work").

## 3. Components

| Component | Module |
|---|---|
| `OKFParser` | `app/okf/parser.py` |
| `OKFValidator` | `app/okf/validator.py` |
| `OKFExporter` | `app/okf/exporter.py` |
| `OKFImporter` | `app/okf/importer.py` |
| `OKFIndexBuilder` | `app/okf/index_builder.py` |
| `OKFProvenanceManager` | `app/okf/provenance.py` |
| `OKFLinkResolver` | `app/okf/link_resolver.py` |
| `OKFService` | `app/okf/service.py` |

The parser validates YAML frontmatter and extracts markdown links with line
numbers. The link resolver handles bundle-relative (`/path.md`) and relative
(`./path.md`) links, refuses to resolve targets that escape the bundle, treats
`subdir/` entries in indexes as directory links (§8), and reports broken links
rather than failing (§6.1, §11).

## 4. Conformance

A bundle is conformant when every non-reserved `.md` file has a parseable
frontmatter block with a non-empty `type`, and reserved files follow §8/§9.
Missing optional families, unknown types/keys, and broken links **do not** break
conformance.

Current build result (`python scripts/validate_okf.py`):

```text
OKF version:       0.2 (target 0.2, compatible=True)
Documents:         472
Concepts:          464
Valid concepts:    464
Invalid documents: 0
Provenance:        464/464 with sources (100.0%)
Broken internal links: 0
Trust:             464 machine-confirmed · 0 human-reviewed
Result: CONFORMANT
```

## 5. Commands

```bash
cd backend

# generate / regenerate the bundle from the indexed corpus
python scripts/build_okf_bundle.py
python scripts/build_okf_bundle.py --bundle knowledge

# validate (exit 0 conformant, 1 non-conformant, 2 bundle missing)
python scripts/validate_okf.py
python scripts/validate_okf.py --json
```

## 6. API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/knowledge` | list/filter concepts (`type`, `status`, `tag`, `q`, `limit`, `offset`) |
| GET | `/api/knowledge/stats` | counts by type, trust tiers, provenance coverage |
| GET | `/api/knowledge/validate` | conformance report (§11) |
| GET | `/api/knowledge/search?q=` | lexical concept lookup |
| GET | `/api/knowledge/{concept_id}` | one concept with resolved relationships and backlinks |

## 7. Synchronization and RAG integration

```text
Original legal source (ChromaDB corpus)
        ↓
Deterministic extraction (scripts/build_okf_bundle.py)
        ↓
Structured metadata (frontmatter)
        ↓
OKF knowledge document (markdown + frontmatter)
        ↓
Validation (scripts/validate_okf.py)
        ↓
Retrieval index (OKFService.search)  →  /api/knowledge/search
```

Re-running the builder regenerates the bundle deterministically from the current
corpus, so a stale concept cannot silently override a newer source: the concept
is a projection of the indexed source, and `content_hash` records which source
content produced it.

### Retrieval priority

Original source material stays authoritative. `POST /api/research` adds a
supplementary `knowledge` field (related OKF concepts) but **never** injects OKF
summaries into the generation prompt in place of the retrieved original chunks.
OKF search scores are term-overlap relevance, not a legal confidence.

## 8. Known limitations

- Concepts are machine-generated metadata and have not been verified by a legal
  expert (trust tier `machine-confirmed`). Human review is required before any
  legal use.
- Section labels are not mapped to statutes because the corpus does not record
  them; no IPC/BNS equivalence is assumed.
- Court values include upstream OCR artefacts and are preserved verbatim.
- Full judicial text is not reproduced in the bundle; retrieve it from ChromaDB
  by chunk id.
- `Attested Computation` concepts (§10) are not produced: nothing in this corpus
  is a sanctioned computation, so inventing one would be fabrication.
