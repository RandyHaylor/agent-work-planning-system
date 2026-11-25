"""Contract tests for source fetching (spec 05-spec-source-fetching.md, external integration tests 1-10),
run against the fakes and the real adapters (build log #11). No network: the real HTTP fetcher gets an
httpx.Client on httpx.MockTransport scripted with the same responses the fake serves."""
from __future__ import annotations

import urllib.parse
from pathlib import Path

import httpx
import pytest

from planning_system.server.adapters.fakes import (
    FakeHttpSourceFetcher, FakeResponse, FakeUploadedFileSource, FakeWebSearchSource,
)
from planning_system.server.adapters.http_source_fetcher import HttpSourceFetcher
from planning_system.server.adapters.uploaded_file_source import UploadedFileSource
from planning_system.server.adapters.web_search_source import WebSearchSource
from planning_system.server.domain.references.source_fetcher_port import (
    FetchFailed, UploadRequest, UrlRequest, WebSearchRequest,
)

FIXTURES = Path(__file__).parents[1] / "fixtures"
LEVEL_7 = pytest.mark.xfail(strict=False, reason="level 7")
URL = "https://example.com/page"
HTML = (FIXTURES / "article.html").read_bytes()


class Calls:
    def __init__(self, urls):
        self.urls = urls

    def __len__(self):
        return len(self.urls)


def make_fake_http(responses, max_bytes=25 * 1024 * 1024):
    fetcher = FakeHttpSourceFetcher(responses, max_bytes)
    return fetcher, Calls(fetcher.requested)


def make_real_http(responses, max_bytes=25 * 1024 * 1024):
    requested = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        requested.append(url)
        if url in responses:
            response = responses[url]
            if response.timeout:
                raise httpx.ReadTimeout("timed out", request=request)
            if response.final_url and response.final_url != url:
                return httpx.Response(302, headers={"location": response.final_url})
            return httpx.Response(response.status, headers=dict(response.headers), content=response.body)
        for response in responses.values():  # redirect target
            if response.final_url == url:
                return httpx.Response(response.status, headers=dict(response.headers), content=response.body)
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    return HttpSourceFetcher(client, max_bytes), Calls(requested)


HTTP = [pytest.param(make_fake_http, id="fake"), pytest.param(make_real_http, id="real", marks=LEVEL_7)]


@pytest.mark.parametrize("make", HTTP)
def test_1_200_html_with_redirect(make):
    fetcher, _ = make({URL: FakeResponse(200, HTML, {"content-type": "text/html; charset=utf-8", "etag": "abc"},
                                         final_url="https://example.com/final")})
    document = fetcher.fetch(UrlRequest(URL))
    assert document.origin_kind == "web"
    assert document.locator == URL
    assert document.raw_bytes == HTML
    assert document.content_type_header == "text/html; charset=utf-8"
    assert document.metadata["final_url"] == "https://example.com/final"
    assert document.metadata["status"] == "200"
    assert document.metadata["etag"] == "abc"


@pytest.mark.parametrize("make", HTTP)
def test_2_404(make):
    fetcher, _ = make({URL: FakeResponse(404, b"not found")})
    with pytest.raises(FetchFailed) as caught:
        fetcher.fetch(UrlRequest(URL))
    assert (caught.value.reason, caught.value.status) == ("http 404", 404)


@pytest.mark.parametrize("make", HTTP)
def test_3_cloudflare_challenge(make):
    fetcher, _ = make({URL: FakeResponse(403, b"<html>challenge</html>", {"cf-mitigated": "challenge"})})
    with pytest.raises(FetchFailed) as caught:
        fetcher.fetch(UrlRequest(URL))
    assert caught.value.reason == "cloudflare challenge (cf-mitigated)"


@pytest.mark.parametrize("make", HTTP)
def test_4_empty_body(make):
    fetcher, _ = make({URL: FakeResponse(200, b"", {"content-type": "text/html"})})
    with pytest.raises(FetchFailed) as caught:
        fetcher.fetch(UrlRequest(URL))
    assert caught.value.reason == "empty body"


@pytest.mark.parametrize("make", HTTP)
def test_5_timeout_and_too_large(make):
    fetcher, _ = make({URL: FakeResponse(timeout=True), URL + "/big": FakeResponse(200, b"x" * 101)},
                      max_bytes=100)
    with pytest.raises(FetchFailed) as caught:
        fetcher.fetch(UrlRequest(URL))
    assert caught.value.reason == "timeout"
    with pytest.raises(FetchFailed) as caught:
        fetcher.fetch(UrlRequest(URL + "/big"))
    assert caught.value.reason == "too large"


@pytest.mark.parametrize("make", HTTP)
def test_6_always_live(make):
    fetcher, calls = make({URL: FakeResponse(200, HTML, {"content-type": "text/html"})})
    fetcher.fetch(UrlRequest(URL))
    fetcher.fetch(UrlRequest(URL))
    assert len(calls) == 2


UPLOADS = [pytest.param(FakeUploadedFileSource, id="fake"),
           pytest.param(UploadedFileSource, id="real", marks=LEVEL_7)]


@pytest.mark.parametrize("make", UPLOADS)
def test_7_upload(make):
    data = (FIXTURES / "report.docx").read_bytes()
    document = make(max_bytes=len(data)).fetch(UploadRequest("report.docx", data))
    assert (document.origin_kind, document.file_name, document.locator) == ("upload", "report.docx", "report.docx")
    assert document.raw_bytes == data
    assert document.content_type_header is None
    assert document.metadata["size_bytes"] == str(len(data))
    with pytest.raises(FetchFailed):
        make(max_bytes=len(data) - 1).fetch(UploadRequest("report.docx", data))


def ddg_url(terms: str) -> str:
    return "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": terms})


def make_fake_search(responses):
    return FakeWebSearchSource(FakeHttpSourceFetcher(responses))


def make_real_search(responses):
    return WebSearchSource(make_real_http(responses)[0])


SEARCHES = [pytest.param(make_fake_search, id="fake"), pytest.param(make_real_search, id="real", marks=LEVEL_7)]


@pytest.mark.parametrize("make", SEARCHES)
def test_8_web_search_markdown_results(make):
    page = (FIXTURES / "ddg_results.html").read_bytes()
    search = make({ddg_url("planning tools"): FakeResponse(200, page, {"content-type": "text/html"})})
    document = search.fetch(WebSearchRequest("planning tools", limit=2))
    text = document.raw_bytes.decode("utf-8")
    assert text.count("## ") == 2
    assert "## Result 1\nhttps://example.com/page1\n\nSnippet number 1 & more" in text
    assert (document.origin_kind, document.locator, document.content_type_header) == (
        "web_search", "planning tools", "text/markdown")
    assert document.metadata == {"engine": "duckduckgo", "result_count": "2"}


@pytest.mark.parametrize("make", SEARCHES)
def test_9_web_search_without_results_falls_back_to_page_text(make):
    page = (FIXTURES / "ddg_no_results.html").read_bytes()
    search = make({ddg_url("zzz"): FakeResponse(200, page, {"content-type": "text/html"})})
    text = search.fetch(WebSearchRequest("zzz")).raw_bytes.decode("utf-8")
    assert "No results found for your query." in text
    assert "## " not in text


def test_10_dispatch_by_request_type_reaches_each_fetcher():
    """Ingestion (references) holds an injected {request type: fetcher} mapping; checked here with fakes."""
    http = FakeHttpSourceFetcher({URL: FakeResponse(200, HTML)})
    upload = FakeUploadedFileSource()
    search = FakeWebSearchSource(FakeHttpSourceFetcher({ddg_url("x"): FakeResponse(200, b"<p>none</p>")}))
    fetchers = {UrlRequest: http, UploadRequest: upload, WebSearchRequest: search}
    for request, origin in [(UrlRequest(URL), "web"), (UploadRequest("a.txt", b"hi"), "upload"),
                            (WebSearchRequest("x"), "web_search")]:
        assert fetchers[type(request)].fetch(request).origin_kind == origin
