"""
OKFImporter — load an OKF bundle from disk (§3).

The bundle is a directory tree of markdown files; every ``.md`` file is a node
(concept documents plus the reserved ``index.md`` / ``log.md`` files).
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from app.okf.model import OKFDocument
from app.okf.parser import OKFParser, OKFParseError


class OKFImporter:
    def __init__(self, bundle_root: Path, parser: Optional[OKFParser] = None):
        self.bundle_root = Path(bundle_root)
        self.parser = parser or OKFParser()

    def exists(self) -> bool:
        return self.bundle_root.is_dir()

    def paths(self) -> List[Path]:
        if not self.exists():
            return []
        return sorted(self.bundle_root.rglob("*.md"))

    def load(self, strict: bool = False) -> List[OKFDocument]:
        """
        Parse every markdown file in the bundle.

        ``strict=True`` re-raises a structural parse error (frontmatter opened
        but not closed, non-mapping YAML). The default keeps going and records
        the failure as an ``OKFDocument`` with an empty frontmatter so the
        validator can report it rather than the loader crashing.
        """
        documents: List[OKFDocument] = []
        for path in self.paths():
            try:
                documents.append(self.parser.parse_file(path, self.bundle_root))
            except OKFParseError as exc:
                if strict:
                    raise
                try:
                    relative = path.relative_to(self.bundle_root)
                except ValueError:
                    relative = Path(path.name)
                documents.append(
                    OKFDocument(
                        concept_id=relative.with_suffix("").as_posix(),
                        path=path,
                        frontmatter={},
                        body="",
                    )
                )
                # Stash the reason on the instance so the validator can report it.
                documents[-1].frontmatter["__parse_error__"] = str(exc)
        return documents
