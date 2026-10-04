"""
OKFParser — read OKF v0.2 documents (markdown + YAML frontmatter).

Conformant with §4 of the specification:

    https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md

The parser is deliberately permissive (it never rejects a document for missing
optional fields) while still reporting structural problems — a frontmatter block
that opens but never closes, or YAML that is not a mapping — as errors.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from app.okf.model import OKFDocument, OKFLink

# Markdown inline links: [text](target). Images (![..](..)) are excluded.
_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(\s*([^)\s]+)(?:\s+\"[^\"]*\")?\s*\)")
# A URI scheme prefix (http:, https:, mailto:, ...) marks an external link.
_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:")

_FRONTMATTER_DELIMITER = "---"


class OKFParseError(ValueError):
    """Raised when a document's frontmatter block is structurally invalid."""


def split_frontmatter(text: str) -> Tuple[Optional[Dict[str, Any]], str, int]:
    """
    Split a markdown document into ``(frontmatter, body, body_start_line)``.

    ``frontmatter`` is ``None`` when the file has no frontmatter block, which is
    valid for ``index.md`` / ``log.md`` and is reported by the validator for
    concept documents. ``body_start_line`` is 1-indexed and lets the caller
    report accurate line numbers for links found in the body.
    """
    if not text:
        return None, "", 1

    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_DELIMITER:
        return None, text, 1

    closing = None
    for index in range(1, len(lines)):
        if lines[index].strip() == _FRONTMATTER_DELIMITER:
            closing = index
            break
    if closing is None:
        raise OKFParseError(
            "frontmatter opens with '---' but is never closed by a '---' line"
        )

    raw_yaml = "\n".join(lines[1:closing])
    try:
        parsed = yaml.safe_load(raw_yaml) if raw_yaml.strip() else {}
    except yaml.YAMLError as exc:  # pragma: no cover - exercised via tests
        raise OKFParseError(f"invalid YAML frontmatter: {exc}") from exc

    if parsed is None:
        parsed = {}
    if not isinstance(parsed, dict):
        raise OKFParseError("frontmatter must be a YAML mapping of key/value pairs")

    body_lines = lines[closing + 1 :]
    body = "\n".join(body_lines)
    # Preserve a trailing newline only when the source had content after it.
    if body_lines:
        body += "\n"
    return parsed, body, closing + 2


def extract_links(body: str, body_start_line: int = 1) -> List[OKFLink]:
    """Extract markdown links from a body, tagging external ones (§6.1)."""
    links: List[OKFLink] = []
    for match in _LINK_RE.finditer(body):
        target = match.group(2).strip()
        line = body_start_line + body[: match.start()].count("\n")
        external = bool(_SCHEME_RE.match(target)) or target.startswith("#")
        links.append(
            OKFLink(text=match.group(1), target=target, line=line, external=external)
        )
    return links


class OKFParser:
    """Parse concept documents into :class:`OKFDocument` objects."""

    def parse_text(
        self, text: str, concept_id: str, path: Optional[Path] = None
    ) -> OKFDocument:
        frontmatter, body, body_start = split_frontmatter(text)
        return OKFDocument(
            concept_id=concept_id,
            path=path or Path(f"{concept_id}.md"),
            frontmatter=frontmatter or {},
            body=body,
            links=extract_links(body, body_start),
        )

    def parse_file(self, path: Path, bundle_root: Optional[Path] = None) -> OKFDocument:
        """
        Parse one file inside a bundle. ``concept_id`` is the path relative to
        the bundle root without the ``.md`` suffix (§2).
        """
        path = Path(path)
        text = path.read_text(encoding="utf-8")
        root = Path(bundle_root) if bundle_root is not None else path.parent
        try:
            relative = path.relative_to(root)
        except ValueError:
            relative = Path(path.name)
        concept_id = relative.with_suffix("").as_posix()
        return self.parse_text(text, concept_id, path)


parser = OKFParser()
