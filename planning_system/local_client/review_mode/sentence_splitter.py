"""Private: splits a claim into sentences with pysbd (rule-based; handles abbreviations, decimals, version numbers
and our [ref:start-end] markers). Code, not the model, decides the sentences, so every sentence gets reviewed."""
from __future__ import annotations

import warnings

with warnings.catch_warnings():         # pysbd 0.3.4 has unescaped regex strings (SyntaxWarning on Python 3.12+)
    warnings.simplefilter("ignore", SyntaxWarning)
    import pysbd


class SentenceSplitter:

    def __init__(self, language: str = "en"):
        self._segmenter = pysbd.Segmenter(language=language, clean=False)

    def split(self, text: str) -> list[str]:
        sentences = [sentence.strip() for sentence in self._segmenter.segment(text or "")]
        return [sentence for sentence in sentences if sentence]
