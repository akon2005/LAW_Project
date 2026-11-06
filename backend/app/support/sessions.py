"""
Session-scoped conversation memory for the support assistant.

Design constraints, and why:

* **Isolation** — history is keyed by an opaque session id supplied by the
  client. Two sessions can never read each other's turns, and the API never
  accepts another session's id from the request body path.
* **Bounded** — only the last :data:`MAX_TURNS` turns are kept, and the number of
  live sessions is capped with least-recently-used eviction, so a long-running
  process cannot grow without limit.
* **Ephemeral** — nothing is written to disk. A restart, an expiry or an explicit
  reset drops the conversation. This is why no full conversation history is
  offered as a feature.
* **Minimal** — only role and text are stored. No page context, no user identity,
  no legal content, no credentials.
"""
from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional

MAX_TURNS = 12          # turns kept per session (user + assistant messages)
MAX_SESSIONS = 500      # live sessions before LRU eviction
SESSION_TTL = 60 * 60   # 1 hour of inactivity


class SessionStore:
    def __init__(
        self,
        max_turns: int = MAX_TURNS,
        max_sessions: int = MAX_SESSIONS,
        ttl_seconds: int = SESSION_TTL,
    ) -> None:
        self.max_turns = max_turns
        self.max_sessions = max_sessions
        self.ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._sessions: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()

    # ── internals ──────────────────────────────────────────────────────
    def _expire_locked(self, now: float) -> None:
        stale = [
            key for key, entry in self._sessions.items()
            if now - float(entry.get("updated_at", 0)) > self.ttl_seconds
        ]
        for key in stale:
            self._sessions.pop(key, None)

    def _entry_locked(self, session_id: str, now: float) -> Dict[str, Any]:
        entry = self._sessions.get(session_id)
        if entry is None:
            entry = {"turns": [], "created_at": now, "updated_at": now, "resets": 0}
            self._sessions[session_id] = entry
        entry["updated_at"] = now
        self._sessions.move_to_end(session_id)
        while len(self._sessions) > self.max_sessions:
            self._sessions.popitem(last=False)
        return entry

    # ── public API ─────────────────────────────────────────────────────
    def history(self, session_id: str) -> List[Dict[str, str]]:
        if not session_id:
            return []
        now = time.time()
        with self._lock:
            self._expire_locked(now)
            entry = self._sessions.get(session_id)
            if entry is None:
                return []
            entry["updated_at"] = now
            self._sessions.move_to_end(session_id)
            return [dict(turn) for turn in entry["turns"]]

    def append(self, session_id: str, role: str, content: str) -> None:
        if not session_id or not content:
            return
        if role not in {"user", "assistant"}:
            return
        now = time.time()
        with self._lock:
            self._expire_locked(now)
            entry = self._entry_locked(session_id, now)
            entry["turns"].append({"role": role, "content": content})
            if len(entry["turns"]) > self.max_turns:
                del entry["turns"][: len(entry["turns"]) - self.max_turns]

    def reset(self, session_id: str) -> bool:
        if not session_id:
            return False
        with self._lock:
            entry = self._sessions.pop(session_id, None)
            if entry is None:
                return False
            # Record the reset so a reused id still starts clean.
            self._sessions[session_id] = {
                "turns": [],
                "created_at": time.time(),
                "updated_at": time.time(),
                "resets": int(entry.get("resets", 0)) + 1,
            }
            return True

    def stats(self) -> Dict[str, int]:
        with self._lock:
            self._expire_locked(time.time())
            turns = sum(len(entry["turns"]) for entry in self._sessions.values())
            return {
                "sessions": len(self._sessions),
                "turns": turns,
                "max_sessions": self.max_sessions,
                "max_turns_per_session": self.max_turns,
            }


def normalize_history(raw: Optional[List[Any]], limit: int = 8) -> List[Dict[str, str]]:
    """
    Validate a client-supplied history tail.

    The client may send recent turns so a reloaded page keeps its thread, but the
    server never trusts that this is complete or well-formed: entries are
    filtered to known roles, strings are capped and the tail is bounded.
    """
    turns: List[Dict[str, str]] = []
    for item in raw or []:
        role = str(getattr(item, "role", "") or (item.get("role") if isinstance(item, dict) else "") or "")
        content = str(getattr(item, "content", "") or (item.get("content") if isinstance(item, dict) else "") or "")
        if role not in {"user", "assistant"} or not content.strip():
            continue
        turns.append({"role": role, "content": content.strip()[:2000]})
    return turns[-limit:]


session_store = SessionStore()
