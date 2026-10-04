"""
Outcome label normalization (Step 16).

Indian judgments describe dispositions with many different phrasings, and
different phrasings do **not** always mean the same thing (an "appeal allowed"
is not an "appeal dismissed"). This module therefore maps a raw label onto one
of a small set of classes through an *explicit, configurable* table and refuses
(category ``unmapped``) rather than guessing.

The mapping can be overridden with ``OUTCOME_LABEL_MAP`` (path to a JSON file
of ``{class: [synonyms...]}``). Unmapped labels are dropped from training —
they are never silently merged.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Class -> ordered synonym phrases. Matched case-insensitively as substrings,
# longest phrase first, so "appeal partly allowed" beats "allowed".
DEFAULT_LABEL_MAPPING: Dict[str, List[str]] = {
    "allowed": [
        "appeal allowed",
        "petition allowed",
        "suit decreed",
        "conviction upheld",
        "allowed",
    ],
    "dismissed": [
        "appeal dismissed",
        "petition dismissed",
        "suit dismissed",
        "dismissed",
    ],
    "partly_allowed": [
        "partly allowed",
        "partially allowed",
        "partly decreed",
        "partly dismissed",
    ],
    "convicted": ["convicted", "found guilty", "conviction"],
    "acquitted": ["acquitted", "acquittal", "set aside the conviction"],
    "disposed": ["disposed", "disposed of", "closed"],
}

UNMAPPED = "unmapped"


def _load_mapping() -> Dict[str, List[str]]:
    path = os.getenv("OUTCOME_LABEL_MAP", "").strip()
    if not path or not os.path.exists(path):
        return DEFAULT_LABEL_MAPPING
    try:
        with open(path, "r", encoding="utf-8") as handle:
            custom = json.load(handle)
        if isinstance(custom, dict) and custom:
            logger.info("[labels] Loaded outcome mapping from %s", path)
            return {str(k): [str(v) for v in values] for k, values in custom.items()}
        logger.warning("[labels] %s is not a non-empty mapping; using defaults.", path)
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        logger.warning("[labels] Could not read %s (%s); using defaults.", path, exc)
    return DEFAULT_LABEL_MAPPING


class OutcomeLabelNormalizer:
    """Map raw disposition text onto a fixed set of outcome classes."""

    def __init__(self, mapping: Optional[Dict[str, List[str]]] = None) -> None:
        self.mapping = mapping or _load_mapping()
        # Build a longest-phrase-first lookup table.
        self._lookup: List[tuple] = []
        for label, phrases in self.mapping.items():
            for phrase in phrases:
                normalized_phrase = re.sub(r"\s+", " ", str(phrase).strip().lower())
                if normalized_phrase:
                    self._lookup.append((normalized_phrase, label))
        self._lookup.sort(key=lambda item: len(item[0]), reverse=True)

    @property
    def classes(self) -> List[str]:
        return sorted(self.mapping.keys())

    def normalize(self, raw: Optional[str]) -> str:
        """
        Return a known class, or ``"unmapped"`` when the label cannot be mapped.

        ``"unmapped"`` is a real, explicit answer — the caller must exclude it
        from training rather than coerce it into a nearby class.
        """
        if raw is None:
            return UNMAPPED
        text = re.sub(r"\s+", " ", str(raw).strip().lower())
        if not text:
            return UNMAPPED
        for phrase, label in self._lookup:
            if phrase in text:
                return label
        return UNMAPPED


outcome_label_normalizer = OutcomeLabelNormalizer()
