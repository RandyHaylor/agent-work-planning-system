"""readable_text_resolver: an id is a temp cache id OR a reference id; resolve it to the text a
fastReader / quick-json-reader view runs on (the permission check is the authorizer's, before this)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class ReadableText:
    reader_id: str
    text: str
    is_reference: bool                 # False: temp cache entry
    metadata: Mapping[str, str]


class ReadableTextResolver:
    def resolve(self, reader_id: str, services) -> ReadableText:
        """TempCache.get first, then ReferenceLibrary.get; NotFound when neither has it."""
        raise NotImplementedError("level 7")
