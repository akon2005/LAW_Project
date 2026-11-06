"""
Demo example gallery (teacher demonstration mode).

The examples live in one version-controlled file
(``backend/support/examples.json``) and are served to every surface — the
assistant's quick action and the workspace's Guides panel read the same data, so
an example can never mean two different things in two places.

Each example records whether it is **verified** (answered from project
documentation or a live backend call) or **illustrative** (a labelled teaching
example that must not be presented as legal output), which is what lets the UI
mark them honestly.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import BACKEND_ROOT

logger = logging.getLogger("vidhiveda.support")

EXAMPLES_PATH = BACKEND_ROOT / "support" / "examples.json"


class ExamplesStore:
    def __init__(self, path: Path = EXAMPLES_PATH) -> None:
        self.path = path
        self._data: Optional[Dict[str, Any]] = None

    def _load(self) -> Dict[str, Any]:
        if self._data is not None:
            return self._data
        try:
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            logger.error("[support] example gallery missing: %s", self.path)
            self._data = {"examples": [], "categories": []}
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("[support] example gallery unreadable: %s", exc)
            self._data = {"examples": [], "categories": []}
        return self._data

    def available(self) -> bool:
        return bool(self._load().get("examples"))

    def categories(self) -> List[Dict[str, Any]]:
        return list(self._load().get("categories") or [])

    def all(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        examples = list(self._load().get("examples") or [])
        if category:
            target = category.strip().lower()
            examples = [item for item in examples if str(item.get("category", "")).lower() == target]
        return examples

    def get(self, example_id: str) -> Optional[Dict[str, Any]]:
        target = (example_id or "").strip().lower()
        for example in self.all():
            if str(example.get("id", "")).lower() == target:
                return example
        return None

    def note(self) -> str:
        """The gallery's own explanation of its labelling rules."""
        return str(self._load().get("note") or "")

    def summary(self) -> Dict[str, Any]:
        return {
            "available": self.available(),
            "count": len(self.all()),
            "categories": self.categories(),
            "updated": self._load().get("updated"),
            "note": self._load().get("note"),
        }


examples_store = ExamplesStore()
