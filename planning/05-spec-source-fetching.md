# Spec: source fetching

DRAFT (agent-approved under the user's build handover; see BUILD-DECISIONS-LOG.md)

Modules: `server/domain/references/source_fetcher_port`, `server/adapters/http_source_fetcher`, `server/adapters/uploaded_file_source`, `server/adapters/web_search_source`. They turn a load request into a `SourceDocument` (bytes + metadata, type defined in `05-spec-document-extraction.md`). They never extract, store or cache.

## Recorded decisions this builds on

- Tree v5: `source_fetcher_port` "any source the reader loads, not web-only"; `http_source_fetcher` "one implementation of source_fetcher_port (URLs); catches HTTP errors and failure markers"; `uploaded_file_source` "another: file bytes uploaded by the CLI / local client (Word, PDF, ...)"; ingestion: "anything the reader loads (URL, uploaded file, web search) -> document_extraction -> temp cache".
- Reader direction change: "I'm not comfortable with a web-specific fetch. I want a more universal interface into the reader, because it's not just web. It will read documents too (Word, PDF, whatever)".
- References spec §2: "Local files (Word, PDF, ...): the CLI or local client uploads the bytes, because the server can't see the agent's disk."
- Round 4.5: "the primary retrieve attempt can still catch errors and look for markers of failure. you have not convinced me a separate check fetch adds anythihg but complexity".
- Recheck 9: "Obvious HTTP errors are caught and trigger the automatic fallback; if nothing works, return an error."
- Round 2.3: "plain HTTP plus converters for HTML and PDF to text, building on fastReader's `web.py`. JavaScript-only pages fail with a clear error."
- Phase 2 references 2 and 3: "Cache each fetch with its URL, when it was pulled, and the other metadata. If content is identical (same hash), reuse what's there. No heavy reuse beyond that: a new web search does a new web search." and "When an agent visits a URL, even one it found in a reference, the reader always goes to the live web and never to the local cache."
- Draft 2 answers: "Leave the DuckDuckGo scraper as is, and encourage agents to use it ... to register a reference they have to pull the URL up through the reader. Make that clear in prompting and tooling."
- Findings behind round 4: "4 sites blocked plain HTTP behind Cloudflare"; "Cloudflare challenges are documented by the `cf-mitigated: challenge` header".
- Round 1.3 (ports and adapters): storage and I/O behind interfaces; the core has no HTTP code.

## Nested modules

```
server/domain/references/
  source_fetcher_port         SourceRequest types, SourceFetcher protocol, FetchFailed
server/adapters/
  http_source_fetcher/
    http_client_setup         httpx.Client with timeout, redirects, user agent, size cap (from config)
    failure_markers           status >= 400; `cf-mitigated: challenge`; empty body -> reason text
    http_source_fetcher       fetch(UrlRequest) -> SourceDocument
  uploaded_file_source/
    uploaded_file_source      fetch(UploadRequest) -> SourceDocument (size cap, base64 already decoded by http_api)
  web_search_source/
    web_search_source         fetch(WebSearchRequest): builds the DuckDuckGo URL and parses results with
                              fastReader's kept scraper functions; fetches through http_source_fetcher
```

Ingestion picks the fetcher by request type from a mapping injected at startup (`{UrlRequest: http, UploadRequest: upload, WebSearchRequest: search}`); no fetcher knows about the others except web search, which is given the HTTP fetcher.

## Types

```python
@dataclass(frozen=True)
class UrlRequest:        url: str
@dataclass(frozen=True)
class UploadRequest:     file_name: str; file_bytes: bytes
@dataclass(frozen=True)
class WebSearchRequest:  terms: str; limit: int = 10
SourceRequest = UrlRequest | UploadRequest | WebSearchRequest

class FetchFailed(Exception):
    locator: str
    reason: str          # "http 404", "cloudflare challenge (cf-mitigated)", "empty body", "timeout", "too large"
    status: int | None
```

`SourceDocument` fields set per adapter:

| Adapter | origin_kind | locator | content_type_header | metadata |
|---|---|---|---|---|
| http | `web` | requested URL | response header | `final_url`, `status`, `fetched_at` ISO, `etag`/`last_modified` if present |
| upload | `upload` | file name | None | `size_bytes` |
| web search | `web_search` | search terms | `text/markdown` | `engine: duckduckgo`, `result_count` |

## Public interface

```python
class SourceFetcher(Protocol):
    def fetch(self, request: SourceRequest) -> SourceDocument     # raises FetchFailed
```

Behavior:
- HTTP: always a live GET (`Cache-Control: no-cache`); never consults the temp cache or references. Dedup by hash happens later in the temp cache store, not here.
- HTTP failure markers are checked on the one response (no second fetch): status >= 400, `cf-mitigated: challenge` header, empty body. Any of them -> `FetchFailed`; ingestion returns it to the agent as an error. JavaScript-only pages are not detected here (no quality checks); they surface as empty extraction -> extraction error.
- Upload: bytes as given; the CLI/local client reads the local file and sends `file_name + file_base64` (`POST /reader/load`).
- Web search: the result page is markdown (`## title`, URL, snippet per result) loaded into the agent's temp cache like any document. Prompting and the load output tell the agent: to register a reference, load the result's URL through the reader.

## External integration tests (mocked up front)

HTTP is mocked with `respx` (httpx's mock transport); no network in tests.

1. 200 HTML -> `SourceDocument` with `origin_kind="web"`, header content type, `final_url` after a redirect.
2. 404 -> `FetchFailed(reason="http 404", status=404)`.
3. 403 with `cf-mitigated: challenge` -> `FetchFailed` with the Cloudflare reason.
4. 200 empty body -> `FetchFailed("empty body")`.
5. Timeout -> `FetchFailed("timeout")`; body over the size cap -> `FetchFailed("too large")`.
6. Two fetches of the same URL make two HTTP calls (always live).
7. Upload `report.docx` bytes -> `SourceDocument` with `file_name`, `origin_kind="upload"`, bytes unchanged; over cap -> `FetchFailed`.
8. Web search with a saved DuckDuckGo HTML fixture -> markdown with one `## ` block per result, `limit` respected; URL built as `https://html.duckduckgo.com/html/?q=...`.
9. Web search page with no parsable results -> fastReader's existing fallback (plain text of the page) is returned, not an error.
10. Ingestion dispatch: each request type reaches its fetcher (fake fetchers).

## Judgement calls in this spec

- `web_search_source` added as a third adapter; tree v5 has no entry for it (it lists web search under ingestion only).
- httpx instead of fastReader's urllib (timeouts, redirects, mocking via respx); timeout default 15 s kept from fastReader.
- Size caps (default 25 MB for both HTTP and uploads) are config values; no recorded number.
- Web search reuses the HTTP fetcher, so DuckDuckGo blocks surface as the same `FetchFailed`.
- Ingestion's fetcher mapping is injected (no factory module added).

## Flagged, not resolved

- Recheck 9 "HTTP errors ... trigger the automatic fallback" vs one HTTP fetcher: here HTTP errors end the load with an error. See the same note in `05-spec-document-extraction.md`.
- Whether a web-search result item itself may be cited. "to register a reference they have to pull the URL up through the reader" suggests not; this spec doesn't block it (cite lives in the fastReader adaptation spec, which does refuse it; see there).
