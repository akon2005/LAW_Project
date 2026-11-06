"""
Structured troubleshooting lookup.

Twelve recognised problems, each with a fixed shape:

    meaning · likely_causes · steps · retry · escalate

Answers built from this data are returned with ``kind="troubleshooting"`` so the
UI can label them, and the content is deterministic — a troubleshooting answer is
never generated prose, so it cannot drift into guessing.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import BACKEND_ROOT

logger = logging.getLogger("vidhiveda.support")

TROUBLESHOOTING_PATH = BACKEND_ROOT / "support" / "troubleshooting.json"

_WORD = re.compile(r"[a-z0-9][a-z0-9\-']+")


def _normalize(text: str) -> str:
    return " ".join((text or "").lower().split())


class TroubleshootingStore:
    def __init__(self, path: Path = TROUBLESHOOTING_PATH) -> None:
        self.path = path
        self._data: Optional[Dict[str, Any]] = None

    def _load(self) -> Dict[str, Any]:
        if self._data is not None:
            return self._data
        try:
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            logger.error("[support] troubleshooting data missing: %s", self.path)
            self._data = {"entries": []}
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("[support] troubleshooting data unreadable: %s", exc)
            self._data = {"entries": []}
        return self._data

    def available(self) -> bool:
        return bool(self._load().get("entries"))

    def all(self) -> List[Dict[str, Any]]:
        return list(self._load().get("entries") or [])

    def get(self, entry_id: str) -> Optional[Dict[str, Any]]:
        target = (entry_id or "").strip().lower()
        for entry in self.all():
            if str(entry.get("id", "")).lower() == target:
                return entry
        return None

    def match(self, problem: str) -> Optional[Dict[str, Any]]:
        """
        Pick the best entry for a described problem, or ``None``.

        Keyword phrases are weighted above single-word overlap so "no results"
        selects the empty-search entry rather than a generic failure entry. A
        weak match returns ``None`` on purpose: the service then answers from the
        documentation or says it cannot verify, instead of showing the wrong
        troubleshooting entry.
        """
        text = _normalize(problem)
        if not text:
            return None

        best: Optional[Dict[str, Any]] = None
        best_score = 0.0

        for entry in self.all():
            score = 0.0
            for keyword in entry.get("keywords") or []:
                phrase = _normalize(keyword)
                if not phrase:
                    continue
                words = phrase.split()
                if len(words) == 1:
                    if re.search(rf"\b{re.escape(phrase)}\b", text):
                        score += 3.0
                    continue
                # Exact phrase first, then all-words-present-in-any-order so
                # "chatbot not responding" still matches "the chatbot is not
                # responding".
                if phrase in text:
                    score += 6.0 + len(words)
                elif all(re.search(rf"\b{re.escape(word)}\b", text) for word in words):
                    score += 3.0 + len(words)
            for token in _WORD.findall(_normalize(entry.get("title", ""))):
                if len(token) > 3 and re.search(rf"\b{re.escape(token)}\b", text):
                    score += 1.0
            if score > best_score:
                best_score = score
                best = entry

        return best if best_score >= 3.0 else None

    def summary(self) -> Dict[str, Any]:
        return {"available": self.available(), "count": len(self.all())}


troubleshooting_store = TroubleshootingStore()
