"""
Persistent ingestion status (Step 36).

The status file is a small JSON document written atomically after every batch,
so a crashed or interrupted run can be inspected and resumed. It never
contains credentials and never stores legal text.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.config import INGESTION_STATUS_PATH

logger = logging.getLogger(__name__)

DEFAULT_STATUS: Dict[str, Any] = {
    "dataset": None,
    "status": "idle",  # idle | running | completed | failed
    "mode": None,  # sample | limit | full | resume
    "processed_documents": 0,
    "processed_chunks": 0,
    "failed_records": 0,
    "last_checkpoint": None,
    "started_at": None,
    "updated_at": None,
    "error": None,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class IngestionStatus:
    """Read/write helper around the on-disk ingestion status JSON."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path or INGESTION_STATUS_PATH)

    def read(self) -> Dict[str, Any]:
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            merged = dict(DEFAULT_STATUS)
            merged.update(data or {})
            return merged
        except FileNotFoundError:
            return dict(DEFAULT_STATUS)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("[ingestion] Could not read status file: %s", exc)
            return dict(DEFAULT_STATUS)

    def write(self, status: Dict[str, Any]) -> Dict[str, Any]:
        """Atomically persist the status document."""
        status = {**DEFAULT_STATUS, **(status or {})}
        status["updated_at"] = _now()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=str(self.path.parent), delete=False
            ) as handle:
                json.dump(status, handle, indent=2, ensure_ascii=False)
                temp_name = handle.name
            os.replace(temp_name, self.path)
        except OSError as exc:
            logger.warning("[ingestion] Could not write status file: %s", exc)
        return status

    def update(self, **fields: Any) -> Dict[str, Any]:
        current = self.read()
        current.update(fields)
        return self.write(current)

    def start(self, dataset: str, mode: str) -> Dict[str, Any]:
        status = dict(DEFAULT_STATUS)
        status.update(
            {
                "dataset": dataset,
                "status": "running",
                "mode": mode,
                "started_at": _now(),
                "error": None,
            }
        )
        return self.write(status)

    def finish(self, error: Optional[str] = None) -> Dict[str, Any]:
        return self.update(status="failed" if error else "completed", error=error)


ingestion_status = IngestionStatus()
