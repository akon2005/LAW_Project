"""
VIDHIVEDA — Dataset loading, validation and normalization.

Implements Steps 1-3 (load real Hugging Face data, validate, preserve source
information) and Steps 15-16 (loader architecture for the follow-up case-law
and statute datasets).

Rules this module follows, without exception:

* Only real records from the upstream Hugging Face dataset are returned.
  Nothing here synthesises cases, judgments, parties, citations or dates.
* Fields that cannot be extracted from the source text stay empty. ``None``
  or ``""`` means "not present upstream", never "invented".
* Validation never drops a record silently. Every rejection is counted and
  the offending ids plus the reason are written to a validation report on
  disk (``data/dataset/validation_report_<dataset>.json``).
* Metadata is derived from the record's own text (or from a sibling chunk of
  the same source document). Provenance is recorded in ``metadata_origin``.
"""
from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

from app.core.config import BACKEND_ROOT, CASE_LAW_COLLECTION, STATUTE_COLLECTION

load_dotenv()

logger = logging.getLogger(__name__)

# ── Tunables (configurable through .env) ───────────────────────────────
MAX_RECORDS = int(os.getenv("MAX_RECORDS", "9375"))
MIN_TEXT_LENGTH = int(os.getenv("MIN_TEXT_LENGTH", "20"))
REPORT_DIR = Path(
    os.getenv("VALIDATION_REPORT_DIR", str(BACKEND_ROOT / "data" / "dataset"))
)

PRIMARY_DATASET = os.getenv("DATASET_NAME", "india-case-legal-rag")


class DatasetLoadError(RuntimeError):
    """Raised when the upstream dataset cannot be downloaded or read."""


# ── Dataset registry (Steps 1, 15, 16) ─────────────────────────────────
# Adding a dataset here (and flipping ``archived`` to False) is the only code
# change needed to bring a new corpus into the pipeline: the ingestion script,
# embedding service, vector store and RAG layer are all dataset-agnostic.
DATASET_REGISTRY: Dict[str, Dict[str, Any]] = {
    "india-case-legal-rag": {
        "hf_path": "dedol-hf/india-case-legal-rag",
        "split": "train",
        "kind": "case_law",
        "collection": CASE_LAW_COLLECTION,
        # Upstream record layout: {id, text, metadata: {source, chunk_index, total_pages}}
        "fields": {
            "id": "id",
            "text": "text",
            "source": "metadata.source",
            "chunk_index": "metadata.chunk_index",
            "total_pages": "metadata.total_pages",
        },
        "active": True,
        "archived": False,
        "note": "Chunked Supreme Court judgment text (RAG-ready).",
    },
    # Step 15 — prepared, not ingested. Do NOT merge into the case-law
    # collection until verified: it carries extra fields (outcome,
    # sections_cited, articles_cited, judgment_dates).
    "indian-supreme-court-judgments": {
        "hf_path": "sinhal/Indian_Supreme_Court_Judgments",
        "split": "train",
        "kind": "case_law",
        "collection": CASE_LAW_COLLECTION,
        "fields": {
            "id": None,
            "text": "full_text",
            "source": None,
            "chunk_index": None,
            "total_pages": None,
            "case_name": None,
            "outcome": "outcome",
            "sections": "sections_cited",
            "articles": "articles_cited",
            "judgment_dates": "judgment_dates",
        },
        "active": False,
        "archived": True,
        "note": (
            "Structured SC judgments. Field names above are the expected ones; "
            "they must be verified with `--inspect` before ingestion."
        ),
    },
    # Step 16 — future statute data, separate collection on purpose.
    "indian-laws": {
        "hf_path": "Vikaschou/Indian-Laws",
        "split": "train",
        "kind": "statute",
        "collection": STATUTE_COLLECTION,
        "fields": {
            "id": None,
            "text": "law",
            "act_title": "act_title",
            "section": "section",
        },
        "active": False,
        "archived": True,
        "note": "Statute sections. Must never be mixed with case-law chunks.",
    },
}


def get_dataset_config(dataset_key: str = PRIMARY_DATASET) -> Dict[str, Any]:
    """Return the registry entry for ``dataset_key``."""
    if dataset_key not in DATASET_REGISTRY:
        raise KeyError(
            f"Unknown dataset '{dataset_key}'. Known: {sorted(DATASET_REGISTRY)}"
        )
    return DATASET_REGISTRY[dataset_key]


def list_datasets() -> List[Dict[str, Any]]:
    """Human-readable view of the registry."""
    return [
        {
            "key": key,
            "hf_path": cfg["hf_path"],
            "kind": cfg["kind"],
            "collection": cfg["collection"],
            "enabled": bool(cfg.get("active")) and not cfg.get("archived"),
            "note": cfg.get("note", ""),
        }
        for key, cfg in DATASET_REGISTRY.items()
    ]


# ── Text cleaning (Step 6.3) ───────────────────────────────────────────
_JUDIS_URL = re.compile(r"https?://JUDIS\.NIC\.IN", re.IGNORECASE)
_INLINE_SPACE = re.compile(r"[ \t\x0b\x0c\xa0\u2000-\u200b]+")
_EXTRA_NEWLINES = re.compile(r"\n{3,}")


def clean_text(text: str) -> str:
    """
    Normalize a chunk for embedding without destroying its content.

    Only whitespace, control characters and the JUDIS download banner are
    touched. Case names, section references and dates are left verbatim so
    metadata extraction downstream stays traceable to the source.
    """
    if text is None:
        return ""
    normalized = unicodedata.normalize("NFKC", str(text))
    normalized = _JUDIS_URL.sub("", normalized)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    # Drop control characters (keep tab/newline).
    normalized = "".join(
        ch
        for ch in normalized
        if ch in "\n\t" or unicodedata.category(ch)[0] != "C"
    )
    normalized = _INLINE_SPACE.sub(" ", normalized)
    normalized = "\n".join(line.strip() for line in normalized.split("\n"))
    normalized = _EXTRA_NEWLINES.sub("\n\n", normalized)
    return normalized.strip()


# ── Metadata extraction (Step 3) ───────────────────────────────────────
_PARTY_LABEL = r"(?:PETITIONER|APPELLANT|APPLICANT|PLAINTIFF|WRIT\s+PETITIONER)"
_OPP_LABEL = r"(?:RESPONDENT|DEFENDANT|OPPOSITE\s+PARTY|NON-APPLICANT)"

# "PETITIONER: A Vs. RESPONDENT: B" — the JUDIS header layout.
_PARTY_BLOCK = re.compile(
    rf"{_PARTY_LABEL}\s*[:\-]\s*(?P<petitioner>.{{2,200}}?)\s*"
    rf"(?:V(?:s)?\.?|VERSUS)\s*(?:{_OPP_LABEL})?\s*[:\-]?\s*"
    rf"(?P<respondent>.{{2,200}}?)(?=\s*(?:DATE\s+OF\s+JUDGMENT|BENCH|CITATION|"
    rf"JUDGMENT|ACT|CORAM|\Z))",
    re.IGNORECASE | re.DOTALL,
)

# "A ... Petitioner Vs. B ... Respondent" — the appeal-memo layout.
_PARTY_INLINE = re.compile(
    rf"(?P<petitioner>[A-Z][^.\n]{{2,120}}?)\s*(?:\.\.\.|,)?\s*"
    rf"{_PARTY_LABEL}\s*(?:V(?:s)?\.?|VERSUS)\s*"
    rf"(?P<respondent>[A-Z][^.\n]{{2,120}}?)\s*(?:\.\.\.|,)?\s*{_OPP_LABEL}",
    re.IGNORECASE,
)

# Explicit judgment-date labels — safe to trust anywhere in a document.
_DATE_MARKER = re.compile(
    r"(?:DATE\s+OF\s+JUDGMENT|DATE\s+OF\s+ORDER|JUDGMENT\s+DATED|DECIDED\s+ON)\s*[:\-]?\s*"
    r"(?P<date>[0-3]?\d[/.\-][01]?\d[/.\-]\d{2,4})",
    re.IGNORECASE,
)

# A bare "DATED ..." is only trusted near the top of a document's first chunk.
# In body text it matches instrument dates — a "mortgage bond, dated 11-1-1893"
# is not the judgment date, and treating it as one produced wrong years.
_DATE_BARE = re.compile(
    r"\bDATED\s*[:\-]?\s*(?P<date>[0-3]?\d[/.\-][01]?\d[/.\-]\d{2,4})",
    re.IGNORECASE,
)

# Only the opening of a document carries the cause-title block.
_HEADER_WINDOW = 1200

_COURT_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"SUPREME\s+COURT\s+OF\s+INDIA", re.IGNORECASE), "Supreme Court of India"),
    (re.compile(r"IN\s+THE\s+SUPREME\s+COURT", re.IGNORECASE), "Supreme Court of India"),
    (
        re.compile(r"HIGH\s+COURT\s+OF\s+JUDICATURE\s+AT\s+([A-Z][A-Za-z ]+)", re.IGNORECASE),
        "High Court of Judicature at {0}",
    ),
    (
        re.compile(r"HIGH\s+COURT\s+OF\s+([A-Z][A-Za-z]+)", re.IGNORECASE),
        "High Court of {0}",
    ),
    (re.compile(r"\bHIGH\s+COURT\b", re.IGNORECASE), "High Court"),
]

_CITATION_PATTERNS = [
    re.compile(r"\bAIR\s+\d{4}\s+(?:SC|HC|[A-Z]{2,5})\s+\d+"),
    re.compile(r"\(\s*\d{4}\s*\)\s*\d+\s*SCC\s+\d+"),
    re.compile(r"\[\s*\d{4}\s*\]\s*\d+\s*SCR\s+\d+"),
    re.compile(r"\b\d{4}\s*\(\s*\d+\s*\)\s*[A-Z]{2,6}\s+\d+"),
]

_JUDIS_URL_REAL = re.compile(r"https?://JUDIS\.NIC\.IN", re.IGNORECASE)

# "Section 34", "Sec. 73(1)", "Arts. 134, 136, 374(4)", "Articles 14, 19"
_SECTION_BLOCK = re.compile(
    r"\b(?:Section|Sec\.|S\.)\s*(?P<nums>\d+[A-Za-z]{0,3}(?:\s*\(\s*\d+\s*\))?"
    r"(?:\s*,\s*\d+[A-Za-z]{0,3}(?:\s*\(\s*\d+\s*\))?)*)",
    re.IGNORECASE,
)
_ARTICLE_BLOCK = re.compile(
    r"\b(?:Article|Articles|Art\.|Arts\.)\s*(?P<nums>\d+[A-Za-z]{0,3}(?:\s*\(\s*\d+\s*\))?"
    r"(?:\s*,\s*\d+[A-Za-z]{0,3}(?:\s*\(\s*\d+\s*\))?)*)",
    re.IGNORECASE,
)

_YEAR = re.compile(r"\b(1[89]\d{2}|20[0-2]\d)\b")


def _tidy_party(value: str) -> str:
    """Trim a party name to a single clean line."""
    if not value:
        return ""
    value = re.sub(r"\s+", " ", value).strip(" .,:;\u2013\u2014-")
    # Drop trailing boilerplate that is not part of the name.
    value = re.sub(r"\s*(?:AND\s+OTHERS?|&?\s*ORS\.?|ETC\.?)$", "", value, flags=re.IGNORECASE)
    if len(value) < 2 or not re.search(r"[A-Za-z]{2}", value):
        return ""
    return value[:160].strip()


def extract_parties(text: str) -> Dict[str, str]:
    """Petitioner/respondent, only when the label is present in the text."""
    for pattern in (_PARTY_BLOCK, _PARTY_INLINE):
        match = pattern.search(text)
        if not match:
            continue
        petitioner = _tidy_party(match.group("petitioner"))
        respondent = _tidy_party(match.group("respondent"))
        if petitioner and respondent:
            return {"petitioner": petitioner, "respondent": respondent}
        if petitioner and not respondent:
            return {"petitioner": petitioner}
    return {}


def extract_court(text: str) -> Optional[str]:
    """Court name, only when the document names one."""
    for pattern, template in _COURT_PATTERNS:
        match = pattern.search(text)
        if match:
            if "{0}" in template and match.lastindex:
                return template.format(match.group(1).strip().title())
            return template
    return None


def extract_lower_court(text: str) -> Optional[str]:
    """Some JUDIS headers name the court below ('High Court of X')."""
    match = re.search(
        r"HIGH\s+COURT\s+OF\s+([A-Z][A-Za-z]+)", text, re.IGNORECASE
    )
    if match:
        return f"High Court of {match.group(1).strip().title()}"
    return None


def _parse_date(raw: str) -> Tuple[Optional[str], Optional[int]]:
    """
    Strict d/m/Y parse. Returns ``(None, None)`` for impossible dates such as
    29/02/1959 rather than emitting a year that never existed.
    """
    parts = re.split(r"[/.\-]", (raw or "").strip())
    if len(parts) != 3:
        return None, None
    day, month, year = parts
    if len(year) == 2:
        year = f"19{year}"
    try:
        parsed = datetime.strptime(f"{int(day)}/{int(month)}/{int(year)}", "%d/%m/%Y")
    except (ValueError, TypeError):
        return None, None
    if not (1800 <= parsed.year <= datetime.now().year + 1):
        return None, None
    return parsed.strftime("%Y-%m-%d"), parsed.year


def extract_judgment_date(
    text: str, allow_bare_dated: bool = False
) -> Tuple[Optional[str], Optional[int]]:
    """
    Return ``(iso_date, year)`` for a document's judgment date.

    Only explicit markers are trusted anywhere; the looser ``DATED`` form is
    accepted solely when ``allow_bare_dated`` is set, which callers do for a
    document's first chunk (where the cause-title block is printed). The date
    must also be a real calendar date.
    """
    if not text:
        return None, None

    match = _DATE_MARKER.search(text)
    if match is None and allow_bare_dated:
        match = _DATE_BARE.search(text[:_HEADER_WINDOW])
    if match is None:
        return None, None

    return _parse_date(match.group("date"))


def extract_citation(text: str) -> Optional[str]:
    """Neutral/authorised citation, only when the text actually prints one."""
    for pattern in _CITATION_PATTERNS:
        match = pattern.search(text)
        if match:
            return re.sub(r"\s+", " ", match.group(0)).strip()
    return None


def extract_sections(text: str) -> Tuple[List[str], List[str]]:
    """Statutory sections and constitutional articles cited in the chunk."""
    sections: List[str] = []
    articles: List[str] = []

    for match in _SECTION_BLOCK.finditer(text):
        for number in re.split(r"\s*,\s*", match.group("nums")):
            number = re.sub(r"\s+", "", number)
            if number:
                label = f"Section {number}"
                if label not in sections:
                    sections.append(label)

    for match in _ARTICLE_BLOCK.finditer(text):
        for number in re.split(r"\s*,\s*", match.group("nums")):
            number = re.sub(r"\s+", "", number)
            if number:
                label = f"Article {number}"
                if label not in articles:
                    articles.append(label)

    return sections[:40], articles[:40]


def extract_year_from_text(text: str) -> Optional[int]:
    """Last-resort year, used only when no judgment date was found."""
    years = [int(m.group(1)) for m in _YEAR.finditer(text or "")]
    # Indian Supreme Court reports begin in 1950; earlier matches are usually
    # statute/volume numbers, not the judgment year.
    plausible = [y for y in years if 1950 <= y <= datetime.now().year]
    return max(plausible) if plausible else None


def extract_record_metadata(text: str, allow_bare_dated: bool = False) -> Dict[str, Any]:
    """
    Extract every field VIDHIVEDA can honestly support from a chunk of text.

    Missing fields are omitted from the returned dict entirely — callers must
    treat absence as "unknown", never fill it in.
    """
    extracted: Dict[str, Any] = {}

    parties = extract_parties(text)
    if parties.get("petitioner"):
        extracted["petitioner"] = parties["petitioner"]
    if parties.get("respondent"):
        extracted["respondent"] = parties["respondent"]

    court = extract_court(text)
    if court:
        extracted["court"] = court

    iso_date, year = extract_judgment_date(text, allow_bare_dated=allow_bare_dated)
    if iso_date:
        extracted["judgment_date"] = iso_date
    if year:
        extracted["year_from_date"] = year

    citation = extract_citation(text)
    if citation:
        extracted["citation"] = citation

    sections, articles = extract_sections(text)
    if sections:
        extracted["sections"] = sections
    if articles:
        extracted["articles"] = articles

    if _JUDIS_URL_REAL.search(text):
        # Only recorded because the URL really is printed in the document.
        extracted["source_url"] = _JUDIS_URL_REAL.search(text).group(0)

    return extracted


def chunk_index_at_or_below_1(chunk_index: Any) -> bool:
    """True for a document's opening chunk, where the cause-title is printed."""
    try:
        return int(chunk_index) <= 1
    except (TypeError, ValueError):
        return True


def _dot_get(record: Dict[str, Any], path: Optional[str]) -> Any:
    """Read ``"metadata.source"`` style paths out of an upstream record."""
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


# ── Loading (Step 1) ───────────────────────────────────────────────────
def load_raw_dataset(
    dataset_key: str = PRIMARY_DATASET,
    split: Optional[str] = None,
    max_records: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Download (or use the local HF cache of) a registered dataset.

    Raises ``DatasetLoadError`` on any download/read failure so the API layer
    can turn it into a 503 instead of an empty result set.
    """
    config = get_dataset_config(dataset_key)
    split = split or config["split"]
    limit = MAX_RECORDS if max_records is None else max_records

    try:
        from datasets import load_dataset
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise DatasetLoadError(
            "The 'datasets' package is required. Install it with "
            "`pip install datasets huggingface_hub`."
        ) from exc

    logger.info(
        "[dataset] Loading %s (split=%s, limit=%s)", config["hf_path"], split, limit
    )
    try:
        dataset = load_dataset(config["hf_path"], split=split)
    except Exception as exc:  # network, auth, gated-repo, schema changes
        raise DatasetLoadError(
            f"Could not load dataset '{config['hf_path']}' (split={split}): {exc}"
        ) from exc

    total = len(dataset)
    take = total if limit is None or limit <= 0 else min(total, limit)
    records = [dict(dataset[i]) for i in range(take)]
    logger.info("[dataset] %s rows available, %s read into memory", total, take)
    return records


# ── Validation (Step 2) ────────────────────────────────────────────────
def _is_corrupted(text: str) -> Optional[str]:
    """Return a rejection reason when the text is obviously unusable."""
    if len(text) < MIN_TEXT_LENGTH:
        return f"text shorter than {MIN_TEXT_LENGTH} characters"
    letters = sum(1 for ch in text if ch.isalpha())
    if letters < 10:
        return "text contains almost no alphabetic content"
    if text.count("\ufffd") > max(5, len(text) * 0.2):
        return "text is mostly replacement characters (encoding corruption)"
    return None


def validate_and_normalize(
    raw_records: List[Dict[str, Any]],
    dataset_key: str = PRIMARY_DATASET,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Validate, clean and normalize raw upstream records.

    Returns ``(valid_records, report)``. Records are never discarded silently:
    each rejection increments a counter and its id plus reason is captured in
    the report (first 25 of each kind, to keep the file small).
    """
    config = get_dataset_config(dataset_key)
    fields = config["fields"]

    invalid_samples: List[Dict[str, str]] = []
    duplicate_samples: List[Dict[str, str]] = []
    missing_field_samples: List[Dict[str, str]] = []

    counters = {
        "empty_or_null_text": 0,
        "corrupted_text": 0,
        "missing_id": 0,
        "duplicate_text": 0,
        "missing_source": 0,
        "missing_chunk_index": 0,
        "missing_total_pages": 0,
    }

    seen_text: Dict[str, str] = {}
    staged: List[Dict[str, Any]] = []

    for row in raw_records:
        row_id = _dot_get(row, fields.get("id") or "id")
        raw_text = _dot_get(row, fields.get("text") or "text")
        source = _dot_get(row, fields.get("source")) if fields.get("source") else None
        chunk_index = (
            _dot_get(row, fields.get("chunk_index")) if fields.get("chunk_index") else None
        )
        total_pages = (
            _dot_get(row, fields.get("total_pages")) if fields.get("total_pages") else None
        )

        # 1. Text must exist.
        if raw_text is None or not str(raw_text).strip():
            counters["empty_or_null_text"] += 1
            if len(invalid_samples) < 25:
                invalid_samples.append(
                    {"id": str(row_id), "reason": "empty or null text"}
                )
            continue

        text = clean_text(raw_text)

        # 2. Text must be usable.
        reason = _is_corrupted(text)
        if reason:
            counters["corrupted_text"] += 1
            if len(invalid_samples) < 25:
                invalid_samples.append({"id": str(row_id), "reason": reason})
            continue

        # 3. An id is required to build a stable chunk id.
        if row_id is None or str(row_id).strip() == "":
            counters["missing_id"] += 1
            if len(invalid_samples) < 25:
                invalid_samples.append({"id": "<none>", "reason": "missing id"})
            continue

        # 4. Duplicate text (same content under two ids).
        fingerprint = text[:2000].lower()
        if fingerprint in seen_text:
            counters["duplicate_text"] += 1
            if len(duplicate_samples) < 25:
                duplicate_samples.append(
                    {"id": str(row_id), "duplicate_of": seen_text[fingerprint]}
                )
            continue
        seen_text[fingerprint] = str(row_id)

        # 5. Source metadata: recorded as missing, but a chunk is still usable
        #    when the source PDF name is absent (the text itself remains the
        #    traceable artefact and the upstream row id is kept).
        if source is None or str(source).strip() == "":
            counters["missing_source"] += 1
            if len(missing_field_samples) < 25:
                missing_field_samples.append(
                    {"id": str(row_id), "field": "metadata.source"}
                )
        if chunk_index is None:
            counters["missing_chunk_index"] += 1
            if len(missing_field_samples) < 25:
                missing_field_samples.append(
                    {"id": str(row_id), "field": "metadata.chunk_index"}
                )
        if total_pages is None:
            counters["missing_total_pages"] += 1
            if len(missing_field_samples) < 25:
                missing_field_samples.append(
                    {"id": str(row_id), "field": "metadata.total_pages"}
                )

        staged.append(
            {
                "row_id": str(row_id),
                "source_file": str(source) if source else "",
                "chunk_index": int(chunk_index) if isinstance(chunk_index, (int, float)) else 0,
                "total_pages": int(total_pages) if isinstance(total_pages, (int, float)) else 0,
                "text": text,
                "extracted": extract_record_metadata(
                    text, allow_bare_dated=chunk_index_at_or_below_1(chunk_index)
                ),
                "upstream": {
                    key: value
                    for key, value in row.items()
                    if key not in {"text", "metadata"}
                },
            }
        )

    # ── Document-level enrichment ──────────────────────────────────────
    # A judgment is split across many chunks; only the first chunk usually
    # carries the cause-title, court and judgment date. Those facts are
    # propagated to the sibling chunks of the *same source document* so every
    # chunk stays traceable, without inventing anything.
    document_fields: Dict[str, Dict[str, Any]] = {}
    # Merge in chunk order: the cause-title chunk (index 1) is processed first
    # and therefore wins each field. Store/row order is arbitrary, and merging in
    # it previously let a body-text instrument date override the document's real
    # judgment date.
    for record in sorted(
        staged, key=lambda item: (item["source_file"], item["chunk_index"])
    ):
        key = record["source_file"] or f"row:{record['row_id']}"
        effective = dict(record["extracted"])
        if not chunk_index_at_or_below_1(record["chunk_index"]):
            # A date in the body belongs to a document quoted in the text.
            effective.pop("judgment_date", None)
            effective.pop("year_from_date", None)
        record["effective"] = effective

        current = document_fields.setdefault(key, {})
        for field, value in effective.items():
            if field in {"sections", "articles"}:
                merged = current.setdefault(field, [])
                for item in value:
                    if item not in merged:
                        merged.append(item)
                continue
            if not current.get(field):
                current[field] = value

    valid_records: List[Dict[str, Any]] = []
    for record in staged:
        doc_key = record["source_file"] or f"row:{record['row_id']}"
        doc_fields = document_fields.get(doc_key, {})
        chunk_fields = record.get("effective", record["extracted"])

        def pick(field: str) -> Any:
            return chunk_fields.get(field) or doc_fields.get(field)

        petitioner = pick("petitioner") or ""
        respondent = pick("respondent") or ""
        court = pick("court") or ""
        judgment_date = pick("judgment_date")
        citation = pick("citation") or ""
        source_url = chunk_fields.get("source_url") or ""
        sections = pick("sections") or []
        articles = pick("articles") or []

        year = pick("year_from_date") or extract_year_from_text(record["text"])

        # Case name: upstream value if one exists, else the cause-title the
        # document itself prints. Never a placeholder like "Unknown Case".
        upstream_case_name = (
            record["upstream"].get("case_name")
            or record["upstream"].get("title")
            or ""
        ).strip()
        if upstream_case_name.lower() in {"unknown case", "unknown", "n/a"}:
            upstream_case_name = ""
        if upstream_case_name:
            case_name = upstream_case_name
            case_name_origin = "upstream_metadata"
        elif petitioner and respondent:
            case_name = f"{petitioner} v. {respondent}"
            case_name_origin = "derived_from_document_text"
        elif petitioner:
            case_name = petitioner
            case_name_origin = "derived_from_document_text"
        else:
            case_name = ""
            case_name_origin = "unavailable"

        chunk_id = f"{record['row_id']}_{record['chunk_index']}"

        valid_records.append(
            {
                # ── Stable identity ────────────────────────────────────
                "id": record["row_id"],
                "document_id": record["row_id"],
                "chunk_id": chunk_id,
                "chunk_index": record["chunk_index"],
                # ── Source traceability ────────────────────────────────
                "source_file": record["source_file"],
                "source_url": source_url,
                "total_pages": record["total_pages"],
                "dataset": config["hf_path"],
                "dataset_key": dataset_key,
                "document_key": doc_key,
                # ── Extracted legal metadata ───────────────────────────
                "case_name": case_name,
                "case_name_origin": case_name_origin,
                "petitioner": petitioner,
                "respondent": respondent,
                "court": court,
                "judgment_date": judgment_date or "",
                "year": year,
                "citation": citation,
                "sections": sections,
                "articles": articles,
                # ── Payload ────────────────────────────────────────────
                "text": record["text"],
            }
        )

    distinct_docs = len({r["document_key"] for r in valid_records})
    report: Dict[str, Any] = {
        "dataset": config["hf_path"],
        "dataset_key": dataset_key,
        "kind": config["kind"],
        "target_collection": config["collection"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_records_read": len(raw_records),
        "valid_records": len(valid_records),
        "invalid_records": (
            counters["empty_or_null_text"]
            + counters["corrupted_text"]
            + counters["missing_id"]
        ),
        "duplicate_records": counters["duplicate_text"],
        "final_records_used": len(valid_records),
        "distinct_source_documents": distinct_docs,
        "rejection_breakdown": counters,
        "coverage": {
            "with_case_name": sum(1 for r in valid_records if r["case_name"]),
            "with_court": sum(1 for r in valid_records if r["court"]),
            "with_judgment_date": sum(1 for r in valid_records if r["judgment_date"]),
            "with_year": sum(1 for r in valid_records if r["year"]),
            "with_citation": sum(1 for r in valid_records if r["citation"]),
            "with_sections": sum(1 for r in valid_records if r["sections"]),
            "with_articles": sum(1 for r in valid_records if r["articles"]),
        },
        "invalid_samples": invalid_samples,
        "duplicate_samples": duplicate_samples,
        "missing_field_samples": missing_field_samples,
    }
    return valid_records, report


def write_validation_report(
    report: Dict[str, Any], dataset_key: str = PRIMARY_DATASET
) -> Path:
    """Persist the validation report so the run stays auditable."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"validation_report_{dataset_key}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("[dataset] Validation report written to %s", path)
    return path


def format_validation_report(report: Dict[str, Any]) -> str:
    """Console summary of a validation run (Step 2)."""
    coverage = report.get("coverage", {})
    lines = [
        "VIDHIVEDA — Dataset Validation",
        "-" * 32,
        f"Dataset:              {report.get('dataset')}",
        f"Records read:         {report.get('total_records_read')}",
        f"Valid records:        {report.get('valid_records')}",
        f"Invalid records:      {report.get('invalid_records')}",
        f"Duplicate records:    {report.get('duplicate_records')}",
        f"Final records used:   {report.get('final_records_used')}",
        f"Source documents:     {report.get('distinct_source_documents')}",
        "Metadata coverage (of valid records):",
    ]
    for key, value in coverage.items():
        lines.append(f"  - {key}: {value}")
    breakdown = report.get("rejection_breakdown", {})
    if any(breakdown.values()):
        lines.append("Rejection breakdown:")
        for key, value in breakdown.items():
            if value:
                lines.append(f"  - {key}: {value}")
    return "\n".join(lines)


def load_validated_dataset(
    dataset_key: str = PRIMARY_DATASET,
    max_records: Optional[int] = None,
    split: Optional[str] = None,
    write_report: bool = True,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Load → clean → validate → report. The single entry point for ingestion."""
    raw = load_raw_dataset(dataset_key, split=split, max_records=max_records)
    records, report = validate_and_normalize(raw, dataset_key)
    if write_report:
        try:
            write_validation_report(report, dataset_key)
        except OSError as exc:  # e.g. read-only filesystem
            logger.warning("[dataset] Could not write validation report: %s", exc)
    return records, report


# ── Backwards-compatible alias ─────────────────────────────────────────
def load_and_validate_dataset() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Legacy entry point used by ``data_processing/ingest_legal_data.py``.

    Kept so the older script keeps working; new code should call
    ``load_validated_dataset``.
    """
    records, report = load_validated_dataset()
    legacy_report = {
        "Total records (in split)": report.get("total_records_read", 0),
        "Processed limit": report.get("total_records_read", 0),
        "Valid records": report.get("valid_records", 0),
        "Invalid records": report.get("invalid_records", 0),
        "Duplicate records": report.get("duplicate_records", 0),
        "Final records used": report.get("final_records_used", 0),
    }
    legacy_records = []
    for record in records:
        legacy_records.append(
            {
                "id": record["document_id"],
                "chunk_id": record["chunk_id"],
                "document_id": record["document_id"],
                "text": record["text"],
                "source_file": record["source_file"],
                "chunk_index": record["chunk_index"],
                "total_pages": record["total_pages"],
                "case_name": record["case_name"],
                "court": record["court"],
                "year": record["year"],
            }
        )
    return legacy_records, legacy_report
