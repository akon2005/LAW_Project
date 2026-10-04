"""
Dynamic dataset schema inspection, field mapping and streaming (Step 4).

The legal corpus is large and its schema is not guaranteed, so nothing here
assumes a fixed set of columns. ``inspect_schema`` reports what a dataset
actually contains; ``resolve_field_mapping`` turns that (or the registry
defaults / ``*_FIELD`` env overrides) into a canonical ``{canonical: dot.path}``
mapping; and ``iter_dataset`` streams records without ever materialising the
whole corpus in memory.

Rules:
  * A field that cannot be identified stays ``None`` — never fabricated.
  * Streaming uses ``datasets.load_dataset(..., streaming=True)``; only a
    bounded sample is ever held in memory.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional, Tuple

from dotenv import load_dotenv

from app.core.config import (
    CASE_ID_FIELD,
    CASE_NAME_FIELD,
    COURT_FIELD,
    DATE_FIELD,
    OUTCOME_FIELD,
    SECTION_FIELD,
    SOURCE_URL_FIELD,
    TEXT_FIELD,
    YEAR_FIELD,
)
from app.services.dataset_service import DatasetLoadError, get_dataset_config

load_dotenv()

logger = logging.getLogger(__name__)

# Canonical field -> upstream column-name hints (lowercased, order = priority).
FIELD_HINTS: Dict[str, List[str]] = {
    "text": ["text", "full_text", "judgment", "judgement", "content", "body", "document"],
    "id": ["id", "case_id", "doc_id", "document_id"],
    "case_name": ["case_name", "title", "case_title", "name"],
    "court": ["court", "court_name"],
    "date": ["judgment_date", "date_of_judgment", "decision_date", "date", "judgment_dates"],
    "year": ["year", "decision_year"],
    "outcome": ["outcome", "verdict", "disposition", "judgment_outcome", "decision"],
    "sections": ["sections_cited", "sections", "section", "ipc_sections", "provisions"],
    "articles": ["articles_cited", "articles"],
    "source": ["source", "source_file", "filename", "file"],
    "source_url": ["source_url", "url", "link", "pdf_url"],
}

# ``*_FIELD`` env overrides, keyed by the registry/canonical names they replace.
_ENV_OVERRIDES: Dict[str, Tuple[str, ...]] = {
    TEXT_FIELD: ("text",),
    CASE_ID_FIELD: ("id",),
    CASE_NAME_FIELD: ("case_name",),
    COURT_FIELD: ("court",),
    DATE_FIELD: ("date", "judgment_dates"),
    YEAR_FIELD: ("year",),
    OUTCOME_FIELD: ("outcome",),
    SECTION_FIELD: ("sections",),
    SOURCE_URL_FIELD: ("source_url",),
} if any([TEXT_FIELD, CASE_ID_FIELD, CASE_NAME_FIELD, COURT_FIELD, DATE_FIELD, YEAR_FIELD,
          OUTCOME_FIELD, SECTION_FIELD, SOURCE_URL_FIELD]) else {}


# ── dot-path helpers ───────────────────────────────────────────────────
def dot_get(record: Dict[str, Any], path: Optional[str]) -> Any:
    """Read a ``"metadata.source"`` style path out of a nested record."""
    if not path:
        return None
    current: Any = record
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
        if current is None:
            return None
    return current


def _flatten(record: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    """Flatten nested dicts to dot-paths (lists/dicts inside lists are skipped)."""
    flat: Dict[str, Any] = {}
    for key, value in (record or {}).items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(_flatten(value, prefix=f"{path}."))
        else:
            flat[path] = value
    return flat


def apply_env_overrides(fields: Dict[str, Any]) -> Dict[str, Any]:
    """Return ``fields`` with any configured ``*_FIELD`` env values applied."""
    resolved = dict(fields or {})
    for override, targets in _ENV_OVERRIDES.items():
        if not override:
            continue
        for target in targets:
            resolved[target] = override
    return resolved


# ── Schema discovery ───────────────────────────────────────────────────
def _sample_value_stats(values: List[Any]) -> Dict[str, Any]:
    present = [v for v in values if v not in (None, "")]
    missing = len(values) - len(present)
    types = sorted({type(v).__name__ for v in present}) or ["empty"]
    text_lengths = [len(str(v)) for v in present if isinstance(v, str)]
    stats: Dict[str, Any] = {
        "missing_pct": round(100 * missing / len(values), 2) if values else 0.0,
        "types": types,
        "samples": [str(v)[:120] for v in present[:3]],
    }
    if text_lengths:
        stats["avg_text_length"] = round(sum(text_lengths) / len(text_lengths), 1)
    return stats


def detect_schema(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Report the real columns present in a bounded sample of records.

    Returns field names, non-null counts, missing %, value types, average text
    length and the best-guess mapping for each canonical field.
    """
    if not records:
        return {"fields": {}, "field_count": 0, "records_sampled": 0}

    flat_rows = [_flatten(record) for record in records]
    all_paths: List[str] = sorted({path for row in flat_rows for path in row})

    fields_report: Dict[str, Any] = {}
    for path in all_paths:
        values = [row.get(path) for row in flat_rows]
        fields_report[path] = _sample_value_stats(values)

    return {
        "records_sampled": len(records),
        "field_count": len(all_paths),
        "fields": fields_report,
        "detected_mapping": detect_field_mapping(records),
    }


def _best_match(columns: List[str], hints: List[str]) -> Optional[str]:
    """Pick the column matching a hint, preferring exact then suffix matches."""
    lowered = {col.lower(): col for col in columns}
    for hint in hints:
        if hint in lowered:
            return lowered[hint]
    for hint in hints:
        for col in columns:
            leaf = col.lower().split(".")[-1]
            if leaf == hint:
                return col
    for hint in hints:
        for col in columns:
            if hint in col.lower():
                return col
    return None


def detect_field_mapping(records: List[Dict[str, Any]]) -> Dict[str, Optional[str]]:
    """Heuristically map canonical fields onto the real columns of a sample."""
    flat_rows = [_flatten(record) for record in records]
    columns = sorted({path for row in flat_rows for path in row})
    return {canonical: _best_match(columns, hints) for canonical, hints in FIELD_HINTS.items()}


def resolve_field_mapping(
    dataset_key: str,
    sample_records: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Optional[str]]:
    """
    Merge, in priority order: registry defaults < detected schema < env overrides.

    A canonical field that cannot be resolved is returned as ``None`` so the
    caller can leave it empty rather than inventing a value.
    """
    config = get_dataset_config(dataset_key)
    mapping: Dict[str, Optional[str]] = dict(config.get("fields") or {})

    if sample_records:
        for canonical, column in detect_field_mapping(sample_records).items():
            if column and not mapping.get(canonical):
                mapping[canonical] = column

    mapping = apply_env_overrides(mapping)
    return mapping


# ── Streaming iteration (Steps 3, 37) ──────────────────────────────────
def iter_dataset(
    dataset_key: str,
    split: Optional[str] = None,
    skip: int = 0,
    limit: Optional[int] = None,
) -> Iterator[Dict[str, Any]]:
    """
    Stream records from a registered Hugging Face dataset.

    ``skip`` supports resuming from a checkpoint (the dataset is never loaded
    whole); ``limit`` bounds the number of records yielded. Raises
    ``DatasetLoadError`` when the dataset cannot be opened.
    """
    config = get_dataset_config(dataset_key)
    split = split or config["split"]

    try:
        from datasets import load_dataset
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise DatasetLoadError(
            "The 'datasets' package is required. Install it with "
            "`pip install datasets huggingface_hub`."
        ) from exc

    logger.info(
        "[schema] Streaming %s (split=%s, skip=%s, limit=%s)",
        config["hf_path"], split, skip, limit,
    )
    try:
        stream = load_dataset(config["hf_path"], split=split, streaming=True)
    except Exception as exc:
        raise DatasetLoadError(
            f"Could not stream dataset '{config['hf_path']}' (split={split}): {exc}"
        ) from exc

    if skip:
        stream = stream.skip(skip)
    if limit is not None and limit > 0:
        stream = stream.take(limit)

    for record in stream:
        yield dict(record)


def sample_records(
    dataset_key: str, count: int = 20, split: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Read a bounded sample of streamed records for inspection."""
    collected: List[Dict[str, Any]] = []
    for record in iter_dataset(dataset_key, split=split, limit=count):
        collected.append(record)
        if len(collected) >= count:
            break
    return collected


def build_dataset_report(
    dataset_key: str,
    count: int = 20,
    split: Optional[str] = None,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    """Assemble the full inspection report used by ``scripts/inspect_dataset.py``."""
    config = get_dataset_config(dataset_key)
    return {
        "dataset_key": dataset_key,
        "hf_path": config["hf_path"],
        "split": split or config["split"],
        "kind": config["kind"],
        "collection": config["collection"],
        "source_url": f"https://huggingface.co/datasets/{config['hf_path']}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "records_sampled": count,
        "error": error,
    }
