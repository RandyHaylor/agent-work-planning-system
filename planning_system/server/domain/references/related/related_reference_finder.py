"""related_reference_finder: stored references related to a source an agent loads (05-spec-reference-supersede.md
"Search first"): the current references from the same source (URL or file name: metadata "locator") and the top
same-topic matches (full-text search in the store: Postgres full-text in the real store). Also the plain search
behind `planning references search`. Read-only; never supersedes anything."""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass
from typing import Optional

from ..ports import ReferenceStoragePort
from ..types import ORIGIN_NODE, Reference

LOCATOR = "locator"
TOPIC_TERMS = 8                  # most frequent content words of the loaded text
TEXT_SAMPLE = 20_000             # characters of the loaded text the terms are taken from
STOPWORDS = frozenset("""about above after again also always because been before being below between both
could does doing done down during each every from further have having here into just like more most much must
need only other over same should some such than that their them then there these they this those through under
until very want were what when where which while will with would your yours""".split())


@dataclass(frozen=True)
class ReferenceSummary:
    id: str
    origin: str
    locator: Optional[str]
    preview: str                 # first non-empty line, shortened


@dataclass(frozen=True)
class RelatedFound:
    same_source: tuple[ReferenceSummary, ...]
    same_topic: tuple[ReferenceSummary, ...]


def content_terms(text: str, limit: int = TOPIC_TERMS) -> list[str]:
    words = [w for w in re.findall(r"[a-z0-9]+", text[:TEXT_SAMPLE].lower()) if len(w) >= 4 and w not in STOPWORDS]
    return [word for word, _ in Counter(words).most_common(limit)]


def summary(ref: Reference) -> ReferenceSummary:
    first = next((line.strip() for line in ref.text.splitlines() if line.strip()), "")
    return ReferenceSummary(ref.id, ref.origin, ref.metadata.get(LOCATOR), first[:100])


class RelatedReferences(ABC):

    @abstractmethod
    def related(self, locator: Optional[str], text: str, exclude_id: Optional[str] = None,
                limit: int = 5) -> RelatedFound:
        """Current references from the same locator, and the top same-topic matches (not from that locator)."""

    @abstractmethod
    def search(self, query: str, limit: int = 10) -> list[ReferenceSummary]:
        """Current stored references matching any of the query's words, best first."""


class RelatedReferenceFinder(RelatedReferences):

    def __init__(self, storage: ReferenceStoragePort):
        self._storage = storage

    def related(self, locator, text, exclude_id=None, limit=5):
        same_source = [r for r in self._storage.find_by_locator(locator)
                       if r.id != exclude_id and r.origin != ORIGIN_NODE] if locator else []
        skip = {exclude_id, *(r.id for r in same_source)}
        topic = [r for r in self._evidence(content_terms(text), limit + len(skip)) if r.id not in skip]
        return RelatedFound(tuple(summary(r) for r in same_source), tuple(summary(r) for r in topic[:limit]))

    def search(self, query, limit=10):
        terms = content_terms(query, limit=20) or [w for w in re.findall(r"[a-z0-9]+", query.lower()) if w]
        return [summary(r) for r in self._evidence(terms, limit)] if terms else []

    def _evidence(self, terms, limit) -> list[Reference]:
        """Node text is not evidence ("A summary is never treated as proof"): only stored evidence is listed."""
        return [r for r in self._storage.search_text(terms, limit * 3) if r.origin != ORIGIN_NODE][:limit]
