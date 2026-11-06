"""
Support feedback storage.

Deliberately small: an append-only JSONL file under ``backend/data/support/``.
No database, no analytics pipeline, no message content beyond the optional short
comment the user types.

Safeguards:
* only two ratings are accepted (``helpful`` / ``not_helpful``);
* the comment is length-capped and obvious credentials are redacted before the
  line is written;
* submissions are rate-limited per session so the endpoint cannot be used as a
  write amplifier;
* nothing here is ever fed back into the assistant's answers.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any, Deque, Dict, Optional

from app.core.config import BACKEND_ROOT

logger = logging.getLogger("vidhiveda.support")

FEEDBACK_PATH = BACKEND_ROOT / "data" / "support" / "feedback.jsonl"

ALLOWED_RATINGS = {"helpful", "not_helpful"}
MAX_COMMENT = 500
WINDOW_SECONDS = 600        # 10 minutes
MAX_PER_WINDOW = 5          # per session key

_SECRET_PATTERNS = [
    re.compile(r"\b(sk|pk)-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"\bhf_[A-Za-z0-9]{8,}"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{8,}", re.IGNORECASE),
    re.compile(r"\beyJ[A-Za-z0-9._\-]{10,}"),
]


def redact(text: str) -> str:
    """Remove obvious credentials before anything is written to disk."""
    result = text or ""
    for pattern in _SECRET_PATTERNS:
        result = pattern.sub("[redacted]", result)
    return result


class FeedbackStore:
    def __init__(self, path: Path = FEEDBACK_PATH) -> None:
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
        now = time.time()
        with self._lock:
            return self._throttled_locked(key or "anonymous", now)

    # ── writing ────────────────────────────────────────────────────────
    def submit(
        self,
        rating: str,
        comment: Optional[str],
        message_id: Optional[str],
        session_id: Optional[str],
        page: Optional[str],
    ) -> Dict[str, Any]:
        """
        Validate and append one feedback record.

        Raises ``ValueError`` with a user-readable message on invalid input; the
        route maps that to an HTTP 422. Callers should call :meth:`check_rate`
        first so an over-quota client gets 429 rather than 422.
        """
        normalized = (rating or "").strip().lower()
        if normalized not in ALLOWED_RATINGS:
            raise ValueError("rating must be one of: " + ", ".join(sorted(ALLOWED_RATINGS)))

        cleaned = redact((comment or "").strip())
        if len(cleaned) > MAX_COMMENT:
            raise ValueError(f"comment must be at most {MAX_COMMENT} characters")

        record = {
            "id": uuid.uuid4().hex,
            "created_at": time.time(),
            "rating": normalized,
            "comment": cleaned,
            "message_id": (message_id or "")[:80],
            "session": (session_id or "")[:64],
            "page": (page or "")[:40],
        }

        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.error("[support] feedback write failed: %s", exc)
            raise ValueError("feedback could not be stored right now") from exc

        logger.info("[support] feedback stored rating=%s", normalized)
        return {"accepted": True, "id": record["id"], "rating": normalized}

    def count(self) -> int:
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                return sum(1 for _ in handle)
        except OSError:
            return 0


feedback_store = FeedbackStore()
