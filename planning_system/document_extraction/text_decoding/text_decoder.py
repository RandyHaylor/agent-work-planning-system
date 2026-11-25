"""Tries the charset sources in order, then charset_normalizer."""
from __future__ import annotations

from typing import Callable

from planning_system.document_extraction.extraction_interface import TextDecoder

CharsetGuesser = Callable[[bytes], "str | None"]


def charset_normalizer_guess(raw_bytes: bytes) -> str | None:
    """Default guesser: charset_normalizer's best match."""
    raise NotImplementedError("level 7")


class ChainedTextDecoder(TextDecoder):
    def __init__(self, guess_charset: CharsetGuesser = charset_normalizer_guess) -> None:
        self.guess_charset = guess_charset

    def decode(self, raw_bytes: bytes, content_type_header: str | None) -> str:
        raise NotImplementedError("level 7")
