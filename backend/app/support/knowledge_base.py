"""
Support knowledge base (User Guide & Support Assistant).

Support articles are ordinary markdown files with YAML frontmatter under
``backend/support/articles/``. They are deliberately kept **outside** the legal
corpus and outside the generated OKF bundle: website documentation must never be
retrievable as if it were legal authority.

Retrieval here is deterministic hybrid lexical matching over a small, curated
set of articles (title / tag / category / intent weighting plus phrase bonuses).
No embedding model is loaded and no second vector collection is created, which
keeps support retrieval:
  * independent of the legal embedding pipeline (no cross-contamination),
  * testable without downloading a model,
  * explainable — every hit can say which terms matched and where.

A semantic layer can be added later behind ``search()`` without changing callers.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.core.config import BACKEND_ROOT

logger = logging.getLogger("vidhiveda.support")

SUPPORT_DIR = BACKEND_ROOT / "support"
ARTICLE_DIR = SUPPORT_DIR / "articles"

_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
_WORD = re.compile(r"[a-z0-9][a-z0-9\-']+")

# Very small stoplist: enough to keep matching meaningful without stemming.
_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is", "are",
    "do", "does", "did", "how", "what", "why", "when", "where", "which", "who",
    "i", "me", "my", "we", "you", "your", "it", "its", "this", "that", "these",
    "those", "can", "could", "should", "would", "will", "be", "been", "was",
    "with", "at", "by", "from", "as", "if", "but", "not", "no", "so", "there",
    "please", "tell", "about", "want", "need", "help", "all", "anything",
    "something", "everything", "nothing", "thing", "things", "stuff", "any",
}

# Where a term was found decides how much it counts. Body occurrences are worth
# the least on purpose: a term like the product name appears in many articles and
# should not outrank a title or tag match.
_WEIGHT_TITLE = 3.0
_WEIGHT_TAGS = 3.0
_WEIGHT_INTENTS = 2.0
_WEIGHT_CATEGORY = 1.5
_WEIGHT_BODY = 0.6
_BODY_TERM_CAP = 3
# Bonus for a title that covers most of what the user asked about.
_TITLE_COVERAGE_BONUS = 5.0

# Relevance is normalised against a fixed reference score, NOT against the best
# hit in the result set. Normalising by the maximum would make whatever ranked
# first look maximally relevant even when nothing matched the question, which is
# exactly the failure mode that produces confident answers from nothing.
REFERENCE_SCORE = 12.0

# A hit below this normalised score is reported as weak/absent rather than
# presented as an answer. The threshold sits at the "partial" level on purpose:
# answering an off-topic question from a body-text coincidence is worse than
# saying the documentation does not cover it. This is a retrieval confidence,
# NOT a probability that the article is correct.
MIN_RELEVANCE = 0.3


@dataclass
class Article:
    id: str
    title: str
    category: str
    tags: List[str] = field(default_factory=list)
    intents: List[str] = field(default_factory=list)
    features: List[str] = field(default_factory=list)
    updated: str = ""
    # Editorial relevance boost for canonical articles, read from the article's
    # own frontmatter (``priority: 4``). Kept in the data file rather than tuned
    # in code so a maintainer can see and change it.
    priority: float = 0.0
    body: str = ""
    path: str = ""

    def as_ref(self) -> Dict[str, Any]:
        """A citation-shaped reference to this article (no body)."""
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "updated": self.updated,
        }

    def as_summary(self) -> Dict[str, Any]:
        ref = self.as_ref()
        ref["tags"] = list(self.tags)
        ref["features"] = list(self.features)
        ref["excerpt"] = self.excerpt()
        return ref

    def excerpt(self, limit: int = 260) -> str:
        text = re.sub(r"^#+ .*$", "", self.body, flags=re.MULTILINE)
        text = re.sub(r"[*`>]", "", text)
        text = " ".join(text.split())
        return text[: limit - 1] + "…" if len(text) > limit else text


def _parse_frontmatter(raw: str) -> Tuple[Dict[str, Any], str]:
    match = _FRONTMATTER.match(raw)
    if not match:
        return {}, raw
    meta: Dict[str, Any] = {}
    for line in match.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            items = [item.strip().strip("'\"") for item in value[1:-1].split(",")]
            meta[key] = [item for item in items if item]
        else:
            meta[key] = value.strip("'\"")
    return meta, raw[match.end():]


def term_pattern(term: str) -> str:
    """
    Word-boundary pattern for a query term, with a light suffix allowance.

    Deliberately minimal (no stemmer dependency). It covers the mismatches that
    actually occur in this knowledge base:

    * plural in the question, singular in the article — "judgments" → "judgment",
      "citations" → "citation";
    * inflected verbs — "switch" → "switching", "estimate" → "estimates",
      "use" → "using";
    * "...ies" → "...y".

    It still refuses substring matches, so "use" does not match "user" and "all"
    does not match "locally".
    """
    stems = {term}
    if term.endswith("ies") and len(term) > 4:
        stems.add(term[:-3] + "y")
    elif term.endswith("s") and len(term) > 3:
        stems.add(term[:-1])

    variants = set(stems)
    for stem in stems:
        if stem.endswith("e"):
            variants.update({stem + "s", stem + "d", stem + "ing", stem[:-1] + "ing", stem[:-1] + "ed", stem[:-1] + "es"})
        else:
            variants.update({stem + "s", stem + "es", stem + "ed", stem + "ing"})

    alternatives = "|".join(
        re.escape(variant) for variant in sorted(variants, key=len, reverse=True)
    )
    return rf"\b(?:{alternatives})\b"


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _as_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


class SupportKnowledgeBase:
    """Loads, caches and searches the support articles."""

    def __init__(self, directory: Path = ARTICLE_DIR) -> None:
        self.directory = directory
        self._articles: Optional[List[Article]] = None
        self._signature: Optional[Tuple[Tuple[str, float], ...]] = None

    # ── Loading ────────────────────────────────────────────────────────
    def _signature_for(self, files: Iterable[Path]) -> Tuple[Tuple[str, float], ...]:
        return tuple(sorted((str(p), p.stat().st_mtime) for p in files))

    def articles(self) -> List[Article]:
        """All articles, re-read only when the directory content changes."""
        if not self.directory.exists():
            logger.warning("[support] article directory missing: %s", self.directory)
            self._articles = []
            return self._articles

        files = sorted(self.directory.glob("*.md"))
        signature = self._signature_for(files)
        if self._articles is not None and signature == self._signature:
            return self._articles

        loaded: List[Article] = []
        for path in files:
            try:
                raw = path.read_text(encoding="utf-8")
            except OSError as exc:
                logger.error("[support] cannot read %s: %s", path.name, exc)
                continue
            meta, body = _parse_frontmatter(raw)
            article_id = str(meta.get("id") or path.stem)
            loaded.append(
                Article(
                    id=article_id,
                    title=str(meta.get("title") or article_id.replace("-", " ").title()),
                    category=str(meta.get("category") or "general"),
                    tags=_as_list(meta.get("tags")),
                    intents=_as_list(meta.get("intents")),
                    features=_as_list(meta.get("features")),
                    updated=str(meta.get("updated") or ""),
                    priority=_as_float(meta.get("priority")),
                    body=body.strip(),
                    path=str(path),
                )
            )
        self._articles = loaded
        self._signature = signature
        logger.info("[support] loaded %d support articles", len(loaded))
        return loaded

    def get(self, article_id: str) -> Optional[Article]:
        target = (article_id or "").strip().lower()
        for article in self.articles():
            if article.id.lower() == target:
                return article
        return None

    def categories(self) -> List[Dict[str, Any]]:
        counts: Dict[str, int] = {}
        for article in self.articles():
            counts[article.category] = counts.get(article.category, 0) + 1
        return [
            {"id": name, "count": counts[name]}
            for name in sorted(counts)
        ]

    def stats(self) -> Dict[str, Any]:
        articles = self.articles()
        return {
            "available": bool(articles),
            "articles": len(articles),
            "categories": self.categories(),
            "directory": str(self.directory),
        }

    # ── Search ─────────────────────────────────────────────────────────
    @staticmethod
    def tokenize(text: str) -> List[str]:
        tokens = _WORD.findall((text or "").lower())
        return [token for token in tokens if token not in _STOPWORDS and len(token) > 1]

    def search(
        self,
        query: str,
        limit: int = 4,
        intent: Optional[str] = None,
        feature: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Rank articles against a query.

        Returns dicts of ``{article, score, relevance, matched}``. ``relevance``
        is a normalised retrieval score for ranking and thresholding only — it is
        never presented to a user as a probability of being correct.
        """
        articles = self.articles()
        if not articles:
            return []

        terms = self.tokenize(query)
        if not terms and not feature and not category:
            return []

        phrase = " ".join(terms)
        scored: List[Dict[str, Any]] = []

        for article in articles:
            if category and article.category != category:
                continue

            title = article.title.lower()
            tags = [tag.lower() for tag in article.tags]
            intents = [item.lower() for item in article.intents]
            category_name = article.category.lower()
            body = article.body.lower()

            # ``term_score`` is what the question actually matched; the editorial
            # ``priority`` only biases ranking and must never create a match on
            # its own (otherwise a canonical article would answer every question).
            term_score = 0.0
            matched: List[str] = []
            title_terms_matched = 0

            for term in set(terms):
                hit = 0.0
                pattern = term_pattern(term)
                if re.search(pattern, title):
                    hit += _WEIGHT_TITLE
                    title_terms_matched += 1
                if any(term in tag for tag in tags):
                    hit += _WEIGHT_TAGS
                if any(term == item or term in item for item in intents):
                    hit += _WEIGHT_INTENTS
                if term in category_name:
                    hit += _WEIGHT_CATEGORY
                occurrences = len(re.findall(pattern, body))
                if occurrences:
                    hit += _WEIGHT_BODY * min(occurrences, _BODY_TERM_CAP)
                if hit:
                    term_score += hit
                    matched.append(term)

            # A title that carries most of the question is the strongest signal.
            if terms and title_terms_matched / len(set(terms)) >= 0.5:
                term_score += _TITLE_COVERAGE_BONUS
                matched.append("title_coverage")

            if term_score <= 0:
                continue

            score = term_score

            # Phrase bonuses reward an exact multi-word match. They are added
            # after the per-term score is established; previously they were
            # applied to a variable that did not exist yet and then discarded.
            if len(terms) >= 2 and phrase and phrase in title:
                score += 6.0
                matched.append("phrase_title")
            if len(terms) >= 3 and phrase and phrase in body:
                score += 2.0
                matched.append("phrase_body")

            # Intent / feature agreement nudges the right article to the top.
            if intent and intent in article.intents:
                score += 4.0
            if feature and feature in article.features:
                score += 5.0
            score += article.priority

            scored.append(
                {
                    "article": article,
                    "score": round(score, 3),
                    "term_score": round(term_score, 3),
                    "matched": sorted(set(matched)),
                }
            )

        if not scored:
            return []

        for item in scored:
            item["relevance"] = round(min(1.0, item["score"] / REFERENCE_SCORE), 3)
            item["match"] = (
                "strong" if item["relevance"] >= 0.6
                else "partial" if item["relevance"] >= 0.35
                else "weak"
            )

        scored.sort(key=lambda item: (-item["score"], item["article"].id))
        return scored[: max(1, limit)]


support_knowledge_base = SupportKnowledgeBase()
