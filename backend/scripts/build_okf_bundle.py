#!/usr/bin/env python
"""
Build the VIDHIVEDA Open Knowledge Format (OKF v0.2) knowledge bundle.

    python scripts/build_okf_bundle.py
    python scripts/build_okf_bundle.py --bundle knowledge

Every concept is derived deterministically from the *real* indexed corpus in
ChromaDB. Nothing is invented: when the source metadata does not record a value
(for example the statute a section label belongs to), the field is left empty and
the omission is stated in the body rather than guessed.

Layout produced (following the OKF directory §3 and reserved-filename rules §3.1):

    knowledge/
        index.md              # declares okf_version: "0.2" (§8, §12)
        log.md                # update history (§9)
        judgments/            # one concept per source judgment PDF
        courts/               # one concept per recorded court
        legal-sections/       # one concept per section label seen in the corpus
        datasets/             # the Hugging Face corpus description
        models/               # embedding model + outcome model status
        evaluation/           # evaluation methodology
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import (  # noqa: E402
    CASE_LAW_COLLECTION,
    DATASET_NAME,
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL_NAME,
    OKF_BUNDLE_DIR,
    OKF_VERSION,
)
from app.okf import OKFExporter, OKFImporter, OKFIndexBuilder  # noqa: E402

DATASET_REPO = f"dedol-hf/{DATASET_NAME}"
DATASET_URL = f"https://huggingface.co/datasets/{DATASET_REPO}"
EMBEDDING_MODEL_URL = (
    f"https://huggingface.co/{EMBEDDING_MODEL_NAME}"
    if EMBEDDING_MODEL_NAME.startswith("sentence-transformers/")
    else None
)

# §7 — actor convention: <producer>/<version> and process:<id>.
BUILDER_ACTOR = "process:vidhiveda-okf-builder/1.0"
VALIDATOR_ACTOR = "process:vidhiveda-okf-validator/1.0"

READ_BATCH = 1000
EXCERPT_CHARS = 600
CHUNK_ID_SAMPLE = 10


def utc_now() -> str:
    """ISO 8601 datetime with an explicit UTC offset (§5)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def slugify(value: str, fallback: str = "concept") -> str:
    text = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return text or fallback


class SlugRegistry:
    """
    Assign a stable, unique file slug to every distinct source value.

    Two different source values must never map to the same concept id, or one
    would silently overwrite the other. On collision a deterministic short hash
    suffix is appended, and the collision is recorded for reporting.
    """

    def __init__(self) -> None:
        self._by_value: Dict[str, str] = {}
        self._used: Set[str] = set()
        self.collisions: List[Tuple[str, str, str]] = []

    def slug_for(self, value: str) -> str:
        if value in self._by_value:
            return self._by_value[value]
        base = slugify(value)
        candidate = base
        if candidate in self._used:
            suffix = hashlib.sha1(value.encode("utf-8")).hexdigest()[:6]
            candidate = f"{base}-{suffix}"
            self.collisions.append((value, base, candidate))
        self._used.add(candidate)
        self._by_value[value] = candidate
        return candidate


def sentence(text: str) -> str:
    """Collapse whitespace and guarantee a one-line description."""
    collapsed = re.sub(r"\s+", " ", str(text or "")).strip()
    return collapsed


def quote_excerpt(text: str, limit: int = EXCERPT_CHARS) -> str:
    collapsed = sentence(text)
    return collapsed[:limit].rstrip()


def read_corpus() -> Tuple[List[Dict[str, Any]], Dict[str, dict]]:
    """
    Stream every indexed row out of ChromaDB in batches.

    Returns ``(rows, documents)`` where ``documents`` maps row id → stored text.
    Metadata and text are read in bounded batches so the build does not depend on
    a single monolithic query.
    """
    import chromadb

    client = chromadb.PersistentClient(path=str(BACKEND_DIR / "chroma_db"))
    collection = client.get_collection(CASE_LAW_COLLECTION)
    total = collection.count()

    rows: List[Dict[str, Any]] = []
    documents: Dict[str, str] = {}
    for offset in range(0, total, READ_BATCH):
        batch = collection.get(
            include=["metadatas", "documents"], limit=READ_BATCH, offset=offset
        )
        ids = batch.get("ids") or []
        metadatas = batch.get("metadatas") or []
        docs = batch.get("documents") or []
        for index, row_id in enumerate(ids):
            metadata = metadatas[index] if index < len(metadatas) else {}
            rows.append({"id": row_id, "metadata": metadata or {}})
            documents[row_id] = docs[index] if index < len(docs) else ""
    return rows, documents


def group_sources(rows: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        source = str((row["metadata"] or {}).get("source") or "unattributed")
        grouped[source].append(row)
    return grouped


def split_sections(raw: Any) -> List[str]:
    if not raw:
        return []
    return [part.strip() for part in str(raw).split(",") if part.strip()]


def build(source_filename: str, rows: List[Dict[str, Any]], documents: Dict[str, str]) -> Dict[str, Any]:
    """Aggregate one source judgment PDF from its chunk rows."""
    courts = Counter()
    case_names = Counter()
    dates = Counter()
    years = Counter()
    sections = Counter()
    articles = Counter()
    chunk_ids: List[str] = []
    hasher = hashlib.sha256()
    excerpt = ""
    excerpt_index = None

    ordered = sorted(
        rows, key=lambda row: (row["metadata"].get("chunk_index") or 0, row["id"])
    )
    for row in ordered:
        metadata = row["metadata"]
        if metadata.get("court"):
            courts[str(metadata["court"])] += 1
        if metadata.get("case_name"):
            case_names[str(metadata["case_name"])] += 1
        if metadata.get("judgment_date"):
            dates[str(metadata["judgment_date"])] += 1
        if metadata.get("year"):
            years[str(metadata["year"])] += 1
        for section in split_sections(metadata.get("sections")):
            sections[section] += 1
        for article in split_sections(metadata.get("articles")):
            articles[article] += 1
        chunk_id = str(metadata.get("chunk_id") or row["id"])
        chunk_ids.append(chunk_id)

        text = documents.get(row["id"], "")
        if text:
            hasher.update(text.encode("utf-8"))
            chunk_index = metadata.get("chunk_index")
            if excerpt_index is None or (
                chunk_index is not None and chunk_index < excerpt_index
            ):
                excerpt_index = chunk_index if chunk_index is not None else 0
                excerpt = quote_excerpt(text)

    return {
        "source": source_filename,
        "chunks": len(rows),
        "court": courts.most_common(1)[0][0] if courts else "",
        "case_name": case_names.most_common(1)[0][0] if case_names else "",
        "judgment_date": dates.most_common(1)[0][0] if dates else "",
        "year": int(years.most_common(1)[0][0]) if years else None,
        "all_courts": dict(courts),
        "sections": sorted(sections),
        "section_counts": sections,
        "articles": sorted(articles),
        "content_hash": hasher.hexdigest(),
        "chunk_ids_sample": sorted(chunk_ids)[:CHUNK_ID_SAMPLE],
        "excerpt": excerpt,
    }


# ── Concept renderers ──────────────────────────────────────────────────
def judgment_concept(
    summary: Dict[str, Any],
    ts: str,
    court_slugs: Dict[str, str],
    section_slugs: Dict[str, str],
    slug: str,
) -> Tuple[str, dict, str]:
    case_name = summary["case_name"] or f"Judgment in {summary['source']}"
    court = summary["court"]
    year = summary["year"]
    title = case_name
    description = sentence(
        f"{case_name} — {court or 'court not recorded'}"
        f"{', ' + str(year) if year else ''}."
    )

    frontmatter: Dict[str, Any] = {
        "type": "Legal Judgment",
        "title": title,
        "description": description,
        "tags": ["legal-judgment", "case-law", *([slugify(court)] if court else [])],
        "status": "stable",
        "generated": {"by": BUILDER_ACTOR, "at": ts},
        "verified": [{"by": VALIDATOR_ACTOR, "at": ts}],
        "sources": [
            {
                "id": "corpus",
                "resource": DATASET_URL,
                "title": f"{DATASET_REPO} · {summary['source']}",
                "author": "team:dedol-hf",
            }
        ],
        "dataset": DATASET_REPO,
        "source_file": summary["source"],
        "court": court or None,
        "judgment_date": summary["judgment_date"] or None,
        "year": year,
        "chunks_indexed": summary["chunks"],
        "chunk_ids_sample": summary["chunk_ids_sample"],
        "content_hash": summary["content_hash"],
    }

    lines: List[str] = []
    lines.append("# Source information")
    lines.append("")
    lines.append(f"* Dataset: [{DATASET_REPO}]({DATASET_URL})")
    lines.append(f"* Source file: `{summary['source']}`")
    lines.append(
        f"* Court: {court if court else 'not recorded in the source metadata'}"
    )
    lines.append(
        f"* Judgment date: {summary['judgment_date'] or 'not recorded upstream'}"
    )
    lines.append(f"* Year: {year if year else 'not recorded upstream'}")
    lines.append(f"* Indexed chunks: {summary['chunks']}")
    lines.append(f"* Content hash (sha256 over indexed chunks): `{summary['content_hash']}`")
    lines.append("")

    lines.append("# Extracted metadata")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    lines.append(f"| Case name | {case_name} |")
    lines.append(f"| Court | {court or '(not recorded)'} |")
    lines.append(f"| Judgment date | {summary['judgment_date'] or '(not recorded)'} |")
    lines.append(f"| Year | {year or '(not recorded)'} |")
    lines.append(f"| Indexed chunks | {summary['chunks']} |")
    lines.append(
        f"| Chunk ids (first {len(summary['chunk_ids_sample'])}) | "
        f"{', '.join(summary['chunk_ids_sample']) or '(none)'} |"
    )
    lines.append("")

    if court and court in court_slugs:
        lines.append("# Court")
        lines.append("")
        lines.append(f"Recorded under [{court}](/courts/{court_slugs[court]}.md).")
        lines.append("")

    if summary["sections"]:
        lines.append("# Referenced provisions")
        lines.append("")
        lines.append(
            "Section labels printed in this judgment's indexed chunks. The "
            "originating statute is not recorded in the source metadata and was "
            "deliberately not inferred."
        )
        lines.append("")
        for section in summary["sections"]:
            lines.append(
                f"* [{section}](/legal-sections/{section_slugs[section]}.md)"
            )
        lines.append("")

    if summary["articles"]:
        lines.append("# Constitutional articles")
        lines.append("")
        for article in summary["articles"]:
            lines.append(f"* {article}")
        lines.append("")

    if summary["excerpt"]:
        lines.append("# Extracted excerpt")
        lines.append("")
        lines.append(
            "Verbatim from the source document (normalised whitespace only). The "
            "full judicial text is not reproduced here; retrieve it from the "
            "vector store by chunk id."
        )
        lines.append("")
        lines.append(f"> {summary['excerpt']}")
        lines.append("")

    lines.append("# Provenance")
    lines.append("")
    lines.append(
        f"Deterministically extracted from the indexed corpus "
        f"[{DATASET_REPO}]({DATASET_URL}) (source file `{summary['source']}`)."
    )
    lines.append(
        "This document is machine-generated metadata, not judicial text, and has "
        "not been reviewed by a human."
    )
    return slug, frontmatter, "\n".join(lines)


def court_concept(
    court: str, member_slugs: List[str], chunks: int, ts: str, slug: str
) -> Tuple[str, dict, str]:
    frontmatter = {
        "type": "Court",
        "title": court,
        "description": sentence(f"Court recorded on {chunks} indexed chunk(s)."),
        "tags": ["court", "jurisdiction"],
        "status": "stable",
        "generated": {"by": BUILDER_ACTOR, "at": ts},
        "verified": [{"by": VALIDATOR_ACTOR, "at": ts}],
        "sources": [
            {"id": "corpus", "resource": DATASET_URL, "title": DATASET_REPO, "author": "team:dedol-hf"}
        ],
        "chunks": chunks,
        "judgments": len(member_slugs),
        "court_name_source": "as_stored_in_corpus",
    }
    lines = [
        "# Court",
        "",
        f"Court name exactly as recorded in the indexed corpus metadata: **{court}**.",
        "",
        f"Indexed chunks: {chunks}. Judgments: {len(member_slugs)}.",
        "",
        "# Judgments",
        "",
    ]
    for slug in sorted(member_slugs):
        lines.append(f"* [Judgment](/judgments/{slug}.md)")
    lines.append("")
    lines.append("# Note")
    lines.append("")
    lines.append(
        "Court names are preserved verbatim. Some values in this corpus are "
        "truncated or malformed by upstream OCR; they were not corrected here."
    )
    return slug, frontmatter, "\n".join(lines)


def section_concept(
    label: str, occurrences: int, member_slugs: List[str], ts: str, slug: str
) -> Tuple[str, dict, str]:
    frontmatter = {
        "type": "Legal Provision Reference",
        "title": label,
        "description": sentence(
            f"Section label '{label}' printed in {occurrences} indexed chunk(s)."
        ),
        "tags": ["legal-provision", "section-reference"],
        "status": "stable",
        "generated": {"by": BUILDER_ACTOR, "at": ts},
        "verified": [{"by": VALIDATOR_ACTOR, "at": ts}],
        "sources": [
            {"id": "corpus", "resource": DATASET_URL, "title": DATASET_REPO, "author": "team:dedol-hf"}
        ],
        "occurrences": occurrences,
        "statute": None,
        "statute_status": "not_recorded_upstream",
    }
    lines = [
        "# Provision reference",
        "",
        f"Section label exactly as printed in the corpus: **{label}**.",
        "",
        f"Occurrences across indexed chunks: {occurrences}.",
        "",
        "# Statute",
        "",
        "The originating statute (for example IPC, BNS, CrPC or a State Act) is "
        "**not recorded** in the source metadata, so it has deliberately not been "
        "inferred. Do not treat this label as a verified citation on its own.",
        "",
        "# Judgments",
        "",
    ]
    for slug in sorted(member_slugs):
        lines.append(f"* [Judgment](/judgments/{slug}.md)")
    return slug, frontmatter, "\n".join(lines)


def dataset_concept(
    chunks: int, judgments: int, courts: int, sections: int, years: List[int], ts: str
) -> Tuple[str, dict, str]:
    frontmatter = {
        "type": "Dataset",
        "title": DATASET_REPO,
        "description": sentence(
            "Indian Supreme Court and High Court judgment chunks used as the "
            "VIDHIVEDA retrieval corpus."
        ),
        "resource": DATASET_URL,
        "tags": ["dataset", "case-law", "india", "rag"],
        "status": "stable",
        "generated": {"by": BUILDER_ACTOR, "at": ts},
        "verified": [{"by": VALIDATOR_ACTOR, "at": ts}],
        "sources": [
            {
                "id": "hf-dataset",
                "resource": DATASET_URL,
                "title": f"Hugging Face dataset {DATASET_REPO}",
                "author": "team:dedol-hf",
                "last_modified": None,
            }
        ],
        "chunk_count": chunks,
        "judgment_count": judgments,
    }
    lines = [
        "# Overview",
        "",
        f"`{DATASET_REPO}` is the case-law corpus indexed into the ChromaDB "
        f"collection `{CASE_LAW_COLLECTION}`.",
        "",
        "# Observed schema",
        "",
        "| Field | Description |",
        "|---|---|",
        "| `text` | Judgment chunk text. |",
        "| `case_name` | Case title, derived from document text where available. |",
        "| `court` | Court name as recorded upstream. |",
        "| `judgment_date` | Judgment date when recorded. |",
        "| `year` | Judgment year. |",
        "| `sections` | Section labels printed in the chunk. |",
        "| `articles` | Constitutional articles printed in the chunk. |",
        "| `source` | Source PDF filename. |",
        "",
        "# Corpus facts (observed)",
        "",
        f"* Indexed chunks: {chunks}",
        f"* Source judgments: {judgments}",
        f"* Distinct courts (as recorded): {courts}",
        f"* Distinct section labels: {sections}",
        f"* Years present: {', '.join(str(y) for y in years) or 'none'}",
        "",
        "# License and usage",
        "",
        "License and redistribution terms are determined by the upstream dataset "
        "and its source judgments; consult the dataset card before redistribution.",
        "",
        "# Related",
        "",
        "* [Embedding model](/models/all-minilm-l6-v2.md)",
        "* [Retrieval evaluation](/evaluation/retrieval-evaluation.md)",
    ]
    return "india-case-legal-rag", frontmatter, "\n".join(lines)


def embedding_model_concept(ts: str) -> Tuple[str, dict, str]:
    frontmatter = {
        "type": "Embedding Model",
        "title": EMBEDDING_MODEL_NAME,
        "description": sentence(
            f"Sentence-transformer producing {EMBEDDING_DIMENSION}-dimensional "
            "vectors for the VIDHIVEDA corpus."
        ),
        "resource": EMBEDDING_MODEL_URL,
        "tags": ["embedding", "sentence-transformers", "retrieval"],
        "status": "stable",
        "generated": {"by": BUILDER_ACTOR, "at": ts},
        "verified": [{"by": VALIDATOR_ACTOR, "at": ts}],
        "sources": [
            {"id": "model-card", "resource": EMBEDDING_MODEL_URL or EMBEDDING_MODEL_NAME, "title": EMBEDDING_MODEL_NAME}
        ],
        "dimensions": EMBEDDING_DIMENSION,
        "provider": "sentence-transformers",
    }
    lines = [
        "# Model",
        "",
        f"* Identifier: `{EMBEDDING_MODEL_NAME}`",
        f"* Embedding dimension: {EMBEDDING_DIMENSION}",
        "* Provider: sentence-transformers",
        "",
        "# Index compatibility",
        "",
        "Changing the embedding model changes the vector space. The ChromaDB "
        "collection must be re-ingested after any change; vectors from "
        "incompatible embedding spaces must never be mixed.",
        "",
        "# Related",
        "",
        "* [Dataset](/datasets/india-case-legal-rag.md)",
    ]
    return "all-minilm-l6-v2", frontmatter, "\n".join(lines)


def outcome_model_concept(ts: str) -> Tuple[str, dict, str]:
    frontmatter = {
        "type": "Model",
        "title": "Outcome prediction model",
        "description": sentence(
            "Experimental case-outcome classifier. Currently unavailable because "
            "no reliable labelled training set was identified."
        ),
        "tags": ["ml", "outcome-prediction", "unavailable"],
        "status": "draft",
        "generated": {"by": BUILDER_ACTOR, "at": ts},
        "verified": [{"by": VALIDATOR_ACTOR, "at": ts}],
        "sources": [
            {"id": "dataset", "resource": DATASET_URL, "title": DATASET_REPO}
        ],
        "available": False,
        "reason": (
            "The active corpus carries no outcome/label field, and its text is "
            "judgment text, so training an outcome model on it would leak the "
            "verdict into the features."
        ),
        "version": "untrained",
    }
    lines = [
        "# Status",
        "",
        "**Unavailable.** No outcome model is trained or served.",
        "",
        "# Why",
        "",
        "The active corpus has no outcome label, and the judgment text contains "
        "the verdict itself, so it cannot be used as a feature without leakage. "
        "The system reports `prediction.available = false` with a reason instead "
        "of inventing a classifier.",
        "",
        "# Boundary",
        "",
        "Retrieval relevance and prediction confidence are separate quantities. "
        "This project never derives a prediction from retrieval similarity.",
    ]
    return "outcome-model", frontmatter, "\n".join(lines)


def evaluation_concept(ts: str) -> Tuple[str, dict, str]:
    frontmatter = {
        "type": "Evaluation Methodology",
        "title": "Retrieval evaluation",
        "description": sentence(
            "Reproducible retrieval and citation evaluation for the VIDHIVEDA "
            "pipeline, run by scripts/evaluate.py."
        ),
        "tags": ["evaluation", "retrieval", "reproducibility"],
        "status": "stable",
        "generated": {"by": BUILDER_ACTOR, "at": ts},
        "verified": [{"by": VALIDATOR_ACTOR, "at": ts}],
        "sources": [
            {"id": "gold-set", "resource": "scripts/build_gold_set.py", "title": "Derived gold set builder"},
        ],
        "metrics": [
            "recall_at_5",
            "recall_at_10",
            "recall_at_20",
            "mrr",
            "ndcg_at_10",
        ],
    }
    lines = [
        "# Metrics",
        "",
        "Retrieval: Recall@5, Recall@10, Recall@20, MRR, nDCG@10.",
        "Generation: citation precision, citation coverage, unsupported-claim rate.",
        "",
        "# How to run",
        "",
        "```bash",
        "python scripts/build_gold_set.py",
        "python scripts/evaluate.py --no-rerank",
        "python scripts/evaluate.py --rerank",
        "```",
        "",
        "# Honesty",
        "",
        "The gold set is derived from the corpus, not hand-labelled legal ground "
        "truth. Metric values are produced by the scripts above and are never "
        "asserted in documentation without a run.",
        "",
        "# Related",
        "",
        "* [Dataset](/datasets/india-case-legal-rag.md)",
    ]
    return "retrieval-evaluation", frontmatter, "\n".join(lines)


def write_log(exporter: OKFExporter, ts: str, counts: Dict[str, int], version: str) -> None:
    day = ts.split("T", 1)[0]
    body = "\n".join(
        [
            "# Directory Update Log",
            "",
            f"## {day}",
            f"* **Creation**: Generated OKF v{version} knowledge bundle from the indexed corpus "
            f"({counts['judgments']} judgments, {counts['courts']} courts, "
            f"{counts['sections']} provision references).",
            "",
        ]
    )
    exporter.write_log("log", body)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the VIDHIVEDA OKF v0.2 bundle.")
    parser.add_argument("--bundle", default=str(OKF_BUNDLE_DIR), help="output bundle directory")
    parser.add_argument("--version", default=OKF_VERSION, help="OKF version to declare")
    args = parser.parse_args()

    bundle_root = Path(args.bundle)
    ts = utc_now()

    print("VIDHIVEDA — OKF v0.2 bundle build")
    print("-" * 40)
    print(f"Bundle:    {bundle_root}")
    print(f"Version:   {args.version}")

    rows, documents = read_corpus()
    if not rows:
        print(f"ERROR: collection '{CASE_LAW_COLLECTION}' is empty. Run scripts/ingest.py first.")
        return 3

    grouped = group_sources(rows)
    export = OKFExporter(bundle_root)

    summaries: List[Dict[str, Any]] = [
        build(source_filename, source_rows, documents)
        for source_filename, source_rows in sorted(grouped.items())
    ]

    # Pass 1 — assign a unique slug to every court, section and judgment before
    # any body is rendered, so cross-links always point at the file that is
    # actually written and no concept silently overwrites another.
    court_registry, section_registry, judgment_registry = (
        SlugRegistry(),
        SlugRegistry(),
        SlugRegistry(),
    )
    court_slugs: Dict[str, str] = {
        name: court_registry.slug_for(name)
        for name in sorted({court for item in summaries for court in item["all_courts"]})
    }
    section_slugs: Dict[str, str] = {
        label: section_registry.slug_for(label)
        for label in sorted(
            {label for item in summaries for label in item["section_counts"]}
        )
    }
    judgment_slugs: Dict[str, str] = {
        item["source"]: judgment_registry.slug_for(item["source"].rsplit(".", 1)[0])
        for item in summaries
    }

    judgments: List[Tuple[str, dict, str]] = []
    court_members: Dict[str, Set[str]] = defaultdict(set)
    court_chunks: Counter = Counter()
    section_counts: Counter = Counter()
    section_members: Dict[str, Set[str]] = defaultdict(set)
    years: set = set()

    # Pass 2 — render and index the concepts.
    for summary in summaries:
        slug = judgment_slugs[summary["source"]]
        _, frontmatter, body = judgment_concept(
            summary, ts, court_slugs, section_slugs, slug
        )
        judgments.append((slug, frontmatter, body))
        # A judgment contributes to every court value recorded anywhere in its
        # chunks, so the bundle reflects all courts present in the corpus rather
        # than only each document's modal court.
        for court_name, court_count in summary["all_courts"].items():
            court_members[court_name].add(slug)
            court_chunks[court_name] += court_count
        if summary["year"]:
            years.add(int(summary["year"]))
        for section, count in summary["section_counts"].items():
            section_counts[section] += count
            section_members[section].add(slug)

    for slug, frontmatter, body in judgments:
        export.write_concept(f"judgments/{slug}", frontmatter, body)

    for court, members in sorted(court_members.items()):
        _, frontmatter, body = court_concept(
            court, sorted(members), court_chunks[court], ts, court_slugs[court]
        )
        export.write_concept(f"courts/{court_slugs[court]}", frontmatter, body)

    for label, occurrences in sorted(section_counts.items()):
        _, frontmatter, body = section_concept(
            label,
            occurrences,
            sorted(section_members[label]),
            ts,
            section_slugs[label],
        )
        export.write_concept(f"legal-sections/{section_slugs[label]}", frontmatter, body)

    slug, frontmatter, body = dataset_concept(
        len(rows), len(judgments), len(court_members), len(section_counts), sorted(years), ts
    )
    export.write_concept(f"datasets/{slug}", frontmatter, body)

    slug, frontmatter, body = embedding_model_concept(ts)
    export.write_concept(f"models/{slug}", frontmatter, body)

    slug, frontmatter, body = outcome_model_concept(ts)
    export.write_concept(f"models/{slug}", frontmatter, body)

    slug, frontmatter, body = evaluation_concept(ts)
    export.write_concept(f"evaluation/{slug}", frontmatter, body)

    write_log(
        export,
        ts,
        {
            "judgments": len(judgments),
            "courts": len(court_members),
            "sections": len(section_counts),
        },
        args.version,
    )

    # Synthesize index.md for every directory (including the root, which declares
    # okf_version per §8/§12).
    documents_in_bundle = OKFImporter(bundle_root).load()
    index_ids = OKFIndexBuilder(bundle_root, documents_in_bundle).build(write=True)

    print()
    print("Bundle summary")
    print("-" * 40)
    print(f"  judgments:        {len(judgments)}")
    print(f"  courts:           {len(court_members)}")
    print(f"  provision refs:   {len(section_counts)}")
    print(f"  other concepts:   4")
    print(f"  indexes written:  {len(index_ids)}")
    print(f"  total concepts:   {len(judgments) + len(court_members) + len(section_counts) + 4}")

    collisions = (
        court_registry.collisions
        + section_registry.collisions
        + judgment_registry.collisions
    )
    if collisions:
        print()
        print(f"  slug collisions disambiguated: {len(collisions)}")
        for value, base, disambiguated in collisions[:20]:
            print(f"    '{value}' -> {base} -> {disambiguated}")
    print()
    print("Validate with:  python scripts/validate_okf.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
