"""
Query understanding and legal-section normalization (Steps 14-15).

``LegalQueryAnalyzer`` turns a free-text query into structured fields
(sections, issue, court, years, task) that drive hybrid retrieval. It never
invents an entity: a field is populated only when a matching pattern is
literally present in the query text, otherwise it is left empty.

``LegalSectionNormalizer`` normalizes the many written forms of a statutory
section ("IPC 302", "Section 302 IPC", "Sec. 302", "302 IPC", "BNS 103",
"Section 103 of Bharatiya Nyaya Sanhita") to a canonical
``{statute, section, original_text, normalized_text}`` record. It does **not**
treat IPC and BNS sections as equivalent; an explicit equivalence map can be
supplied but is only ever reported alongside, never substituted.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from app.services.dataset_service import extract_court

logger = logging.getLogger(__name__)

# ── Section normalization (Step 15) ────────────────────────────────────
_NUM = r"(?P<num>\d{1,4}[A-Za-z]{0,3}(?:\s*\(\s*\d+\s*\))?(?:\s*\(\s*[a-z]\s*\))?)"

# Canonical statute abbreviations and the strings that map onto them.
_STATUTE_ALIASES: Dict[str, List[str]] = {
    "IPC": ["ipc", "indian penal code"],
    "BNS": ["bns", "bharatiya nyaya sanhita"],
    "CrPC": ["crpc", "code of criminal procedure"],
    "BNSS": ["bnss", "bharatiya nagarik suraksha sanhita"],
    "CPC": ["cpc", "code of civil procedure"],
    "IEA": ["iea", "indian evidence act"],
    "BSA": ["bsa", "bharatiya sakshya adhiniyam"],
    "ICA": ["ica", "indian contract act"],
    "HMA": ["hma", "hindu marriage act"],
    "NI": ["ni act", "negotiable instruments act"],
}


def _canonical_statute(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    text = re.sub(r"\s+", " ", raw.strip().lower())
    for canonical, aliases in _STATUTE_ALIASES.items():
        for alias in aliases:
            if text == alias or text.startswith(f"{alias} ") or text.endswith(f" {alias}"):
                return canonical
    return None


# "Section 34(1) IPC" / "Sec. 73 of the Indian Contract Act"
_SECTION_OF = re.compile(
    rf"\b(?:section|sec\.?|s\.)\s*{_NUM}(?:\s+(?:of|under)\s+(?:the\s+)?(?P<statute>[A-Za-z][A-Za-z .&]+))?",
    re.IGNORECASE,
)
# "IPC 302" / "BNS Section 103"
_STATUTE_FIRST = re.compile(
    rf"\b(?P<statute>IPC|BNS|CrPC|CPC|IEA|BSA|ICA|HMA|BNSS)\s*(?:section|sec\.?)?\s*{_NUM}",
    re.IGNORECASE,
)
# "302 IPC" / "420 IPC"
_NUMBER_FIRST = re.compile(
    rf"\b{_NUM}\s+(?P<statute>IPC|BNS|CrPC|CPC|IEA|BSA|ICA|HMA|BNSS)\b",
    re.IGNORECASE,
)

_ARTICLE = re.compile(r"\b(?:article|art\.?)\s*(?P<num>\d{1,3}[A-Za-z]?(?:\s*\(\s*\d+\s*\))?)", re.IGNORECASE)


def _clean_number(num: str) -> str:
    return re.sub(r"\s+", "", num)


class LegalSectionNormalizer:
    """Normalize statutory-section references without assuming equivalence."""

    def __init__(self, equivalence_map: Optional[Dict[str, Any]] = None) -> None:
        self.equivalence_map = equivalence_map if equivalence_map is not None else self._load_map()

    @staticmethod
    def _load_map() -> Dict[str, Any]:
        path = os.getenv("SECTION_EQUIVALENCE_MAP", "").strip()
        if not path or not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("[sections] Could not read equivalence map %s: %s", path, exc)
            return {}

    def equivalents(self, statute: Optional[str], section: str) -> List[str]:
        """
        Explicit equivalents only. Empty unless a mapping file was configured —
        IPC and BNS are not assumed to be interchangeable (Step 15).
        """
        if not statute or not self.equivalence_map:
            return []
        key = f"{statute} {section}"
        value = self.equivalence_map.get(key)
        return list(value) if isinstance(value, list) else []

    def normalize_text(self, query: str) -> List[Dict[str, Any]]:
        """Extract and normalize every section reference in ``query``."""
        found: List[Dict[str, Any]] = []
        seen = set()

        def add(statute: Optional[str], num: str, original: str) -> None:
            section = _clean_number(num)
            key = (statute, section)
            if key in seen:
                return
            seen.add(key)
            normalized = f"{statute} Section {section}" if statute else f"Section {section}"
            found.append(
                {
                    "statute": statute,
                    "section": section,
                    "original_text": re.sub(r"\s+", " ", original).strip(),
                    "normalized_text": normalized,
                    "equivalents": self.equivalents(statute, section),
                }
            )

        for pattern in (_STATUTE_FIRST, _NUMBER_FIRST):
            for match in pattern.finditer(query or ""):
                add(_canonical_statute(match.group("statute")), match.group("num"), match.group(0))

        for match in _SECTION_OF.finditer(query or ""):
            add(_canonical_statute(match.group("statute")), match.group("num"), match.group(0))

        # "Section 302 IPC" is captured twice — once as a bare "Section 302"
        # and once as "302 IPC". Drop the statute-less form when the same
        # section number is also known to belong to a statute.
        qualified = {record["section"] for record in found if record["statute"]}
        found = [
            record for record in found
            if record["statute"] or record["section"] not in qualified
        ]
        return found

    def normalize_articles(self, query: str) -> List[str]:
        return [f"Article {_clean_number(m.group('num'))}" for m in _ARTICLE.finditer(query or "")]


legal_section_normalizer = LegalSectionNormalizer()


# ── Query analysis (Step 14) ───────────────────────────────────────────
# Only genuinely recognised phrases are reported; a query without one yields
# an empty issue list rather than a guess.
_ISSUE_PHRASES = [
    "self-defence", "self defence", "private defence", "murder", "culpable homicide",
    "attempt to murder", "cheating", "criminal breach of trust", "theft", "extortion",
    "dowry death", "cruelty", "conspiracy", "sedition", "kidnapping", "rape",
    "breach of contract", "specific performance", "arbitration", "compensation",
    "damages", "negligence", "defamation", "bail", "anticipatory bail", "maintenance",
    "divorce", "child custody", "adoption", "habeas corpus", "mandamus", "certiorari",
    "fundamental rights", "equal protection", "right to privacy", "environmental",
    "money laundering", "cyber", "trademark", "copyright", "patent", "insolvency",
]

_TASK_CUES = [
    ("outcome_prediction", ["will the court", "predict", "likely outcome", "chance of conviction",
                            "whether he will be convicted", "probability of"]),
    ("trend_analysis", ["trend", "over the years", "historical pattern", "evolution of"]),
    ("summarization", ["summar", "sum up", "brief the"]),
    ("provision_lookup", ["what is section", "what does section", "meaning of section",
                          "text of section", "provision under section"]),
    ("precedent_retrieval", ["precedent", "similar judgments", "similar cases", "case law",
                             "find cases", "relevant judgments"]),
]

_LAW_AREA_CUES = {
    "criminal": ["ipc", "bns", "criminal", "offence", "accused", "convict", "bail"],
    "contract": ["contract", "agreement", "breach", "damages"],
    "civil": ["civil", "suit", "plaintiff", "injunction"],
    "constitutional": ["constitution", "article", "fundamental right", "writ"],
    "family": ["marriage", "divorce", "custody", "maintenance", "adoption"],
    "property": ["property", "tenancy", "land", "possession"],
    "commercial": ["commercial", "arbitration", "company", "insolvency"],
    "tax": ["tax", "gst", "income tax", "customs"],
}

_YEAR = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")


class LegalQueryAnalyzer:
    """Extract structured legal intent from a natural-language query."""

    def __init__(self, section_normalizer: Optional[LegalSectionNormalizer] = None) -> None:
        self.sections = section_normalizer or legal_section_normalizer

    def analyze(self, query: str) -> Dict[str, Any]:
        text = (query or "").strip()
        lower = text.lower()

        section_records = self.sections.normalize_text(text)
        articles = self.sections.normalize_articles(text)

        issues = [phrase for phrase in _ISSUE_PHRASES if phrase in lower]
        # Court is only reported when the query literally names one. The bare
        # "Supreme Court" / "High Court" forms are recognised here (queries),
        # separately from the stricter document-header extraction used at
        # ingestion time.
        court = extract_court(text) or None
        if court is None:
            if "supreme court" in lower:
                court = "Supreme Court of India"
            elif "high court" in lower:
                court = "High Court"

        years = [int(y) for y in _YEAR.findall(text)]
        year_from = year_to = None
        single_year = None
        range_match = re.search(
            r"\b(?:between|from)\s+(1[89]\d{2}|20\d{2})\s+(?:and|to)\s+(1[89]\d{2}|20\d{2})",
            text,
            re.IGNORECASE,
        )
        if range_match:
            year_from, year_to = int(range_match.group(1)), int(range_match.group(2))
            if year_from > year_to:
                year_from, year_to = year_to, year_from
        elif years:
            single_year = years[0]

        law_area = None
        for area, cues in _LAW_AREA_CUES.items():
            if any(cue in lower for cue in cues):
                law_area = area
                break

        task = "precedent_retrieval"
        for candidate, cues in _TASK_CUES:
            if any(cue in lower for cue in cues):
                task = candidate
                break

        # Retrieval text = case facts + normalized sections + issue (Step 12).
        # The original query is always preserved verbatim as the facts portion.
        parts = [text]
        if section_records:
            parts.append(
                "Legal sections: "
                + "; ".join(record["normalized_text"] for record in section_records)
            )
        if issues:
            parts.append("Legal issue: " + ", ".join(issues[:3]))
        embedding_text = "\n".join(part for part in parts if part)

        return {
            "query": text,
            "case_facts": text,
            "legal_issue": issues[0] if issues else None,
            "legal_issues": issues,
            "legal_sections": section_records,
            "articles": articles,
            "court": court,
            "jurisdiction": "India" if "india" in lower else None,
            "year": single_year,
            "year_from": year_from,
            "year_to": year_to,
            "law_area": law_area,
            "task": task,
            "embedding_text": embedding_text,
        }


legal_query_analyzer = LegalQueryAnalyzer()
