"""
OKFLinkResolver — resolve the markdown links that express relationships (§6).

Links may be bundle-relative (``/tables/customers.md``) or relative
(``./other.md``). Consumers MUST tolerate broken links: a target that does not
exist is not malformed, it may be not-yet-written knowledge (§6.1). The resolver
therefore *reports* broken links rather than failing on them.
"""
from __future__ import annotations

from pathlib import PurePosixPath
from typing import Dict, Iterable, List, Optional, Set, Tuple

from app.okf.model import OKFDocument


def _normalise(target: str) -> str:
    """Strip query/fragment and the ``.md`` suffix, returning a concept id."""
    clean = target.split("#", 1)[0].split("?", 1)[0]
    if clean.endswith(".md"):
        clean = clean[: -len(".md")]
    return clean.strip("/")


class OKFLinkResolver:
    """Resolve links and build the concept graph for a parsed bundle."""

    def __init__(self, documents: Iterable[OKFDocument]):
        self.documents: List[OKFDocument] = list(documents)
        # Reserved files (index.md / log.md) are real nodes to link *to*.
        self.known_ids: Set[str] = {doc.concept_id for doc in self.documents}
        # index.md entries link to subdirectories with a trailing slash (§8), so
        # the directories that exist in the tree are valid link targets too.
        self.known_dirs: Set[str] = set()
        for concept_id in self.known_ids:
            parts = PurePosixPath(concept_id).parts
            for depth in range(1, len(parts)):
                self.known_dirs.add("/".join(parts[:depth]))

    def resolve_directory(self, document: OKFDocument, target: str) -> Optional[str]:
        """Resolve a ``subdir/`` link to an existing directory, else ``None``."""
        clean = target.strip()
        if not clean.endswith("/"):
            return None
        clean = clean.strip("/")
        if clean.startswith("/"):
            candidate = clean.strip("/")
        else:
            base = PurePosixPath(document.concept_id).parent
            candidate = _normalise((base / clean).as_posix())
        return candidate if candidate in self.known_dirs else None

    # ── Resolution ─────────────────────────────────────────────────────
    def resolve(self, document: OKFDocument, target: str) -> Optional[str]:
        """
        Return the concept id a link points at, or ``None`` when the target
        escapes the bundle or does not exist.
        """
        if not target or target.startswith("#"):
            return None
        if target.startswith("/"):
            candidate = _normalise(target)
        else:
            base = PurePosixPath(document.concept_id).parent
            joined = (base / _normalise(target)).as_posix()
            # Collapse ".." without escaping the bundle root.
            parts: List[str] = []
            for part in PurePosixPath(joined).parts:
                if part in ("", "."):
                    continue
                if part == "..":
                    if not parts:
                        return None
                    parts.pop()
                    continue
                parts.append(part)
            candidate = "/".join(parts)
        return candidate if candidate in self.known_ids else None

    # ── Reporting ──────────────────────────────────────────────────────
    def broken_links(self) -> List[Dict[str, object]]:
        """Internal links whose target is not present in the bundle."""
        broken: List[Dict[str, object]] = []
        for doc in self.documents:
            for link in doc.links:
                if link.external:
                    continue
                # A ``subdir/`` entry is a directory link, valid when the
                # directory exists (§8); everything else must be a concept.
                if link.target.strip().endswith("/"):
                    if self.resolve_directory(doc, link.target) is None:
                        broken.append(
                            {
                                "concept_id": doc.concept_id,
                                "target": link.target,
                                "text": link.text,
                                "line": link.line,
                            }
                        )
                    continue
                if self.resolve(doc, link.target) is None:
                    broken.append(
                        {
                            "concept_id": doc.concept_id,
                            "target": link.target,
                            "text": link.text,
                            "line": link.line,
                        }
                    )
        return broken

    def backlinks(self, concept_id: str) -> List[str]:
        """Concept ids that link *to* ``concept_id`` (sorted)."""
        sources: List[str] = []
        for doc in self.documents:
            if doc.concept_id == concept_id:
                continue
            for link in doc.links:
                if not link.external and self.resolve(doc, link.target) == concept_id:
                    sources.append(doc.concept_id)
                    break
        return sorted(set(sources))

    def graph(self) -> Dict[str, List[str]]:
        """Directed adjacency list of resolved internal links."""
        adjacency: Dict[str, List[str]] = {doc.concept_id: [] for doc in self.documents}
        for doc in self.documents:
            targets: List[str] = []
            for link in doc.links:
                if link.external:
                    continue
                resolved = self.resolve(doc, link.target)
                if resolved and resolved not in targets:
                    targets.append(resolved)
            adjacency[doc.concept_id] = targets
        return adjacency

    def outgoing(self, document: OKFDocument) -> List[Tuple[str, str]]:
        """``(target_concept_id, link_text)`` for the resolved links of a doc."""
        resolved: List[Tuple[str, str]] = []
        seen: Set[str] = set()
        for link in document.links:
            if link.external:
                continue
            target = self.resolve(document, link.target)
            if target and target not in seen:
                seen.add(target)
                resolved.append((target, link.text))
        return resolved
