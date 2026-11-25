"""DuckDuckGo HTML result page -> markdown. Regex and layout copied from fastReader's search_ddg
(planning_system/fastreader/web.py); its html_to_text is reused as is."""
from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape

from planning_system.fastreader.web import html_to_text

_RESULT_BLOCK = re.compile(
    r'class="result__title"[^>]*>.*?<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?class="result__snippet"[^>]*>(.*?)</span>',
    re.DOTALL)


@dataclass(frozen=True)
class ParsedResults:
    text: str
    result_count: int


def parse_results(page_html: str, limit: int) -> ParsedResults:
    """`## title`, URL, snippet per result; no results -> the page's plain text."""
    results = [f"## {html_to_text(title).strip()}\n{unescape(href)}\n\n{html_to_text(snippet).strip()}\n"
               for href, title, snippet in _RESULT_BLOCK.findall(page_html)[:limit]]
    if not results:
        return ParsedResults(html_to_text(page_html), 0)
    return ParsedResults("\n".join(results), len(results))
