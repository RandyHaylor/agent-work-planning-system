"""
fastReader.web — fetch a URL or search DuckDuckGo and save raw text to a file for fastReader.

Usage:
    python3 -m fastReader.web url <url> [--out /tmp/out.md]
    python3 -m fastReader.web search <keywords> [--out /tmp/results.md] [--limit N]
"""

import argparse
import sys
import os
import urllib.request
import urllib.parse
import re
from html import unescape as html_unescape
from fastReader.html_parser import HTMLParser

from fastReader.commands.load import run_load
from fastReader.scanner import load_config

DEFAULT_CACHE_DIR = os.path.expanduser("~/.fastReader/cache")
DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; fastReader/1.0)"
}


def fetch_url(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="replace")


class _TextExtractor(HTMLParser):
    SKIP_TAGS = {"script", "style", "noscript", "head", "meta", "link", "nav", "footer"}
    BLOCK_TAGS = {"p", "div", "li", "tr", "br", "h1", "h2", "h3", "h4", "h5", "h6",
                  "article", "section", "blockquote", "pre", "td", "th"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._parts = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
        elif tag in self.BLOCK_TAGS and self._parts and self._parts[-1] != "\n":
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in self.BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data):
        if self._skip_depth == 0:
            self._parts.append(data)

    def get_text(self):
        text = "".join(self._parts)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r" *\n *", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    return parser.get_text()


def search_ddg(keywords: str, limit: int = 10) -> str:
    query = urllib.parse.urlencode({"q": keywords})
    url = f"https://html.duckduckgo.com/html/?{query}"
    html = fetch_url(url)

    # Extract result blocks: title, url, snippet
    results = []
    blocks = re.findall(
        r'class="result__title"[^>]*>.*?<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?class="result__snippet"[^>]*>(.*?)</span>',
        html, flags=re.DOTALL
    )
    for href, title, snippet in blocks[:limit]:
        title = html_to_text(title).strip()
        snippet = html_to_text(snippet).strip()
        href = html_unescape(href)
        results.append(f"## {title}\n{href}\n\n{snippet}\n")

    if not results:
        # Fallback: plain text strip of the page
        return html_to_text(html)

    return "\n".join(results)


def page_to_text(url: str) -> str:
    html = fetch_url(url)
    return html_to_text(html)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="fastReader.web", description="Fetch URL or search DDG to a text file")
    sub = parser.add_subparsers(dest="cmd")

    url_p = sub.add_parser("url", help="Fetch a URL as plain text")
    url_p.add_argument("url", help="URL to fetch")
    url_p.add_argument("--out", default="/tmp/fastreader-fetch.md", help="Output file (default: /tmp/fastreader-fetch.md)")

    search_p = sub.add_parser("search", help="Search DuckDuckGo and save results")
    search_p.add_argument("keywords", nargs="+", help="Search keywords")
    search_p.add_argument("--out", default="/tmp/fastreader-search.md", help="Output file (default: /tmp/fastreader-search.md)")
    search_p.add_argument("--limit", type=int, default=10, help="Max results (default: 10)")

    args = parser.parse_args()

    os.makedirs(DEFAULT_CACHE_DIR, exist_ok=True)
    config = load_config(DEFAULT_CONFIG_PATH)

    if args.cmd == "url":
        print(f"Fetching {args.url} ...")
        text = page_to_text(args.url)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        result = run_load(args.out, DEFAULT_CACHE_DIR, config)
        manifest_id = result['manifest_id']
        summary = result['summary']
        counts = "  ".join(f"{k.split('_')[0]}:{v}" for k, v in summary.items() if v > 0 and k in ('chapters', 'sections', 'subsections', 'blocks'))
        print(f"  {os.path.basename(args.out):<40} hash:{manifest_id}  {counts}")
        print(f"\n  Browse: python3 -m fastReader.toc {manifest_id} --sections")
        print(f"  Search: python3 -m fastReader.search <keywords> --manifests {manifest_id}")

    elif args.cmd == "search":
        query = " ".join(args.keywords)
        print(f"Searching DDG: {query} ...")
        text = search_ddg(query, limit=args.limit)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        result = run_load(args.out, DEFAULT_CACHE_DIR, config)
        manifest_id = result['manifest_id']
        summary = result['summary']
        counts = "  ".join(f"{k.split('_')[0]}:{v}" for k, v in summary.items() if v > 0 and k in ('chapters', 'sections', 'subsections', 'blocks'))
        print(f"  {os.path.basename(args.out):<40} hash:{manifest_id}  {counts}")
        print(f"\n  Browse: python3 -m fastReader.toc {manifest_id} --sections")
        print(f"  Search: python3 -m fastReader.search <keywords> --manifests {manifest_id}")

    else:
        parser.print_help()
        sys.exit(1)
