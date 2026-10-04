"""
Gold evaluation set schema and loader (Step 40).

Each entry:

    {"query": "...", "expected_documents": [], "expected_sections": [], "notes": ""}

An entry with an empty ``expected_documents`` is treated as an *unvalidated
placeholder* and is excluded from metric computation. Legal ground truth must
be supplied and reviewed by a human; this loader never invents it.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_GOLD_PATH = Path(__file__).resolve().parent / "gold_queries.jsonl"


@dataclass
class GoldQuery:
    query: str
    expected_documents: List[str] = field(default_factory=list)
    expected_sections: List[str] = field(default_factory=list)
    notes: str = ""
    family: str = ""

    @property
    def validated(self) -> bool:
        """True only when ground-truth document ids have been supplied."""
        return bool(self.expected_documents)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["validated"] = self.validated
        return data


def load_gold_set(path: Optional[Path] = None) -> List[GoldQuery]:
    """Load a JSONL gold set; malformed lines are skipped, not guessed."""
    target = Path(path or DEFAULT_GOLD_PATH)
    if not target.exists():
        return []

    entries: List[GoldQuery] = []
    with target.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                continue
            entries.append(
                GoldQuery(
                    query=str(raw.get("query", "")),
                    expected_documents=list(raw.get("expected_documents") or []),
                    expected_sections=list(raw.get("expected_sections") or []),
                    notes=str(raw.get("notes", "")),
                    family=str(raw.get("family", "")),
                )
            )
    return entries


def summarize_gold_set(entries: List[GoldQuery]) -> Dict[str, Any]:
    validated = [entry for entry in entries if entry.validated]
    return {
        "total": len(entries),
        "validated": len(validated),
        "placeholders": len(entries) - len(validated),
    }
