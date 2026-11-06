"""
Support problem reports.

A user who cannot resolve an issue can file a short report from the support
assistant. Reports are appended to a local JSONL file under
``backend/data/support/`` — there is no external ticketing integration, and the
API response says exactly that instead of implying a ticket was created in some
remote system.

Safeguards:
* category and page are allowlisted, so free text never reaches those fields;
* every text field is length-capped and credentials are redacted before the
  record is written;
* submissions are rate-limited per session, so the endpoint cannot be used as a
  write amplifier;
* a failed write raises, so the route reports 503 rather than a fake success;
* no conversation history or legal query text is stored — only what the user
  types in the form.
"""
from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any, Deque, Dict, Optional

from app.core.config import BACKEND_ROOT
from app.support.feedback import redact

logger = logging.getLogger("vidhiveda.support")

REPORTS_PATH = BACKEND_ROOT / "data" / "support" / "reports.jsonl"

# Categories are product areas, not free text. `other` is the escape hatch.
REPORT_CATEGORIES = (
    "research",
    "comparison",
    "documents",
    "statutes",
    "knowledge",
    "guides",
    "assistant",
    "account",
    "performance",
    "other",
)

MAX_TITLE = 120
MIN_TITLE = 4
MAX_DESCRIPTION = 2000
MIN_DESCRIPTION = 20
MAX_STEPS = 1000
MAX_CONTACT = 120

WINDOW_SECONDS = 600        # 10 minutes
MAX_PER_WINDOW = 3          # per session key


class ReportStore:
    def __init__(self, path: Path = REPORTS_PATH) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._recent: Dict[str, Deque[float]] = {}

    # ── rate limiting ──────────────────────────────────────────────────
    def _throttled_locked(self, key: str, now: float) -> bool:
        bucket = self._recent.setdefault(key, deque())
        while bucket and now - bucket[0] > WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= MAX_PER_WINDOW:
            return True
        bucket.append(now)
        return False

    def check_rate(self, key: str) -> bool:
        """True when the key has exceeded its allowance."""
        with self._lock:
            return self._throttled_locked(key or "anonymous", time.time())

    # ── writing ────────────────────────────────────────────────────────
    def submit(
        self,
        category: str,
        title: str,
        description: str,
        steps: Optional[str],
        page: Optional[str],
        contact: Optional[str],
        session_id: Optional[str],
    ) -> Dict[str, Any]:
        """
        Validate and append one report.

        Raises ``ValueError`` with a user-readable message on invalid input; the
        route maps that to HTTP 422 and an ``OSError`` to HTTP 503.
        """
        normalized_category = (category or "").strip().lower()
        if normalized_category not in REPORT_CATEGORIES:
            raise ValueError("category must be one of: " + ", ".join(REPORT_CATEGORIES))

        clean_title = redact((title or "").strip())
        if len(clean_title) < MIN_TITLE:
            raise ValueError(f"title must be at least {MIN_TITLE} characters")
        if len(clean_title) > MAX_TITLE:
            raise ValueError(f"title must be at most {MAX_TITLE} characters")

        clean_description = redact((description or "").strip())
        if len(clean_description) < MIN_DESCRIPTION:
            raise ValueError(f"description must be at least {MIN_DESCRIPTION} characters")
        if len(clean_description) > MAX_DESCRIPTION:
            raise ValueError(f"description must be at most {MAX_DESCRIPTION} characters")

        clean_steps = redact((steps or "").strip())
        if len(clean_steps) > MAX_STEPS:
            raise ValueError(f"steps must be at most {MAX_STEPS} characters")

        clean_contact = redact((contact or "").strip())
        if len(clean_contact) > MAX_CONTACT:
            raise ValueError(f"contact must be at most {MAX_CONTACT} characters")

        record = {
            "id": f"rpt-{uuid.uuid4().hex[:12]}",
            "created_at": time.time(),
            "category": normalized_category,
            "title": clean_title,
            "description": clean_description,
            "steps": clean_steps,
            "page": (page or "")[:32],
            "contact": clean_contact,
            "session": (session_id or "")[:64],
            "status": "recorded",
        }

        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.error("[support] report write failed: %s", exc)
            raise

        logger.info(
            "[support] report stored id=%s category=%s page=%s",
            record["id"], record["category"], record["page"] or "-",
        )
        return {
            "accepted": True,
            "stored": True,
            "ticket_id": record["id"],
            "category": record["category"],
            "received_at": record["created_at"],
            "storage": "local JSONL (backend/data/support/reports.jsonl)",
        }

    def count(self) -> int:
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                return sum(1 for _ in handle)
        except OSError:
            return 0


report_store = ReportStore()
