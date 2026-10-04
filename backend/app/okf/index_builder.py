"""
OKFIndexBuilder — synthesize ``index.md`` files for a bundle (§8).

An index enumerates a directory's contents so a human or agent can see what is
available before opening individual documents. Producers MAY generate them; the
body groups entries under headings as ``* [Title](url) - description``.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from app.okf.model import OKFDocument, OKF_VERSION
from app.okf.exporter import OKFExporter


class OKFIndexBuilder:
    def __init__(self, bundle_root: Path, documents: Iterable[OKFDocument]):
        self.bundle_root = Path(bundle_root)
        self.documents = [doc for doc in documents if not doc.is_reserved]

    def _by_directory(self) -> Dict[str, List[OKFDocument]]:
        grouped: Dict[str, List[OKFDocument]] = defaultdict(list)
        for doc in self.documents:
            parent = str(Path(doc.concept_id).parent.as_posix())
            grouped["" if parent == "." else parent].append(doc)
        return grouped

    def _child_directories(self) -> Dict[str, List[str]]:
        children: Dict[str, List[str]] = defaultdict(list)
        for directory in self._by_directory():
            if not directory:
                continue
            parent = str(Path(directory).parent.as_posix())
            parent = "" if parent == "." else parent
            children[parent].append(directory)
        return children

    def render_index(self, directory: str) -> str:
        """Render the index body for one directory (no frontmatter)."""
        grouped = self._by_directory()
        children = self._child_directories()
        lines: List[str] = []

        subdirs = sorted(children.get(directory, []))
        if subdirs:
            lines.append("# Directories")
            for sub in subdirs:
                name = Path(sub).name
                url = f"{sub}/" if directory == "" else f"{name}/"
                lines.append(f"* [{name}]({url}) - knowledge group")
            lines.append("")

        by_type: Dict[str, List[OKFDocument]] = defaultdict(list)
        for doc in grouped.get(directory, []):
            by_type[doc.type or "Concept"].append(doc)

        for concept_type in sorted(by_type):
            lines.append(f"# {concept_type}")
            for doc in sorted(by_type[concept_type], key=lambda item: item.concept_id):
                name = Path(doc.concept_id).name
                url = f"{name}.md"
                description = doc.description or doc.title
                lines.append(f"* [{doc.title}]({url}) - {description}")
            lines.append("")

        lines.append("# Details")
        lines.append(
            f"* {len(grouped.get(directory, []))} concept(s) in this directory."
        )
        return "\n".join(lines).rstrip() + "\n"

    def build(self, write: bool = True) -> List[str]:
        """
        Write an ``index.md`` into every directory that holds concepts or
        subdirectories. Returns the concept ids of the indexes written.
        """
        exporter = OKFExporter(self.bundle_root)
        directories = set(self._by_directory()) | set(self._child_directories())
        written: List[str] = []
        for directory in sorted(directories):
            concept_id = f"{directory}/index" if directory else "index"
            body = self.render_index(directory)
            if write:
                exporter.write_index(
                    concept_id, body, okf_version=OKF_VERSION if directory == "" else None
                )
            written.append(concept_id)
        return written
