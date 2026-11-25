"""Contract tests for document_extraction (spec 05-spec-document-extraction.md, external integration
tests 1-11), run against the fake and the real implementation (build log #11). Third-party libraries are
replaced at the strategy boundary by FakeStrategy."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from planning_system.document_extraction import (
    ExtractionFailed, SourceDocument, UnknownStrategy, build_document_extractor,
)
from planning_system.document_extraction.content_type_detection import LayeredContentTypeDetector
from planning_system.document_extraction.document_extractor import StrategyDocumentExtractor
from planning_system.document_extraction.fakes import (
    FakeContentTypeDetector, FakeDocumentExtractor, FakeFallbackRunner, FakeStrategy, FakeTextDecoder,
    FakeTextNormalizer,
)
from planning_system.document_extraction.fallback_runner import AllStrategiesFailed, FallbackRunner
from planning_system.document_extraction.strategies import StrategyRegistry
from planning_system.document_extraction.text_decoding import ChainedTextDecoder
from planning_system.document_extraction.text_normalization import KindTextNormalizer

FIXTURES = Path(__file__).parents[1] / "fixtures"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
LONG_PROSE = " ".join(["word"] * 60)  # 299 chars


def fake_strategies(**overrides):
    """Every registered name as a scripted fake; overrides replace by name."""
    defaults = {
        "trafilatura_markdown": FakeStrategy("trafilatura_markdown", "# Title\n\n" + LONG_PROSE, "markdown"),
        "readabilipy_markdownify": FakeStrategy("readabilipy_markdownify", "readabilipy " + LONG_PROSE, "markdown"),
        "whole_page_markdownify": FakeStrategy("whole_page_markdownify", "whole page", "markdown"),
        "pypdf_text": FakeStrategy("pypdf_text", "pdf text", "prose"),
        "pdfminer_text": FakeStrategy("pdfminer_text", "pdfminer text", "prose"),
        "docx_text": FakeStrategy("docx_text", "docx text", "prose"),
        "text_passthrough": FakeStrategy("text_passthrough", "plain text", "plain"),
        "json_pretty_print": FakeStrategy("json_pretty_print", '{"b":1,"a":[1,2]}', "json"),
        "jsonl_passthrough": FakeStrategy("jsonl_passthrough", '{"x":1}\n\n{"x":2}\n', "jsonl"),
    }
    defaults.update(overrides)
    return defaults


def make_fake(strategies):
    return FakeDocumentExtractor(list(strategies.values()))


def make_real(strategies):
    return build_document_extractor({}, strategies=list(strategies.values()))


EXTRACTORS = [pytest.param(make_fake, id="fake"), pytest.param(make_real, id="real")]


def html_document(body: bytes = (FIXTURES / "article.html").read_bytes()) -> SourceDocument:
    return SourceDocument(raw_bytes=body, locator="https://example.com/a", origin_kind="web",
                          fetched_at=datetime.now(timezone.utc), content_type_header="text/html; charset=utf-8",
                          file_name=None, metadata={"final_url": "https://example.com/a"})


@pytest.mark.parametrize("make", EXTRACTORS)
def test_1_html_falls_back_to_readabilipy_and_wraps(make):
    strategies = fake_strategies(trafilatura_markdown=FakeStrategy("trafilatura_markdown", error="boom"))
    result = make(strategies).extract(html_document())
    assert result.strategy_used == "readabilipy_markdownify"
    assert [(a.strategy, a.error is None) for a in result.attempts] == [
        ("trafilatura_markdown", False), ("readabilipy_markdownify", True)]
    assert all(len(line) <= 100 for line in result.text.splitlines())
    assert len(result.text.splitlines()) > 1


@pytest.mark.parametrize("make", EXTRACTORS)
def test_2_all_fail_raises_extraction_failed_with_every_attempt(make):
    strategies = fake_strategies(**{n: FakeStrategy(n, error=f"{n} broke") for n in
                                    ("trafilatura_markdown", "readabilipy_markdownify", "whole_page_markdownify")})
    with pytest.raises(ExtractionFailed) as caught:
        make(strategies).extract(html_document())
    assert [(a.strategy, a.error) for a in caught.value.attempts] == [
        ("trafilatura_markdown", "trafilatura_markdown broke"),
        ("readabilipy_markdownify", "readabilipy_markdownify broke"),
        ("whole_page_markdownify", "whole_page_markdownify broke")]


@pytest.mark.parametrize("make", EXTRACTORS)
def test_3_named_strategy_runs_alone(make):
    strategies = fake_strategies()
    result = make(strategies).extract(html_document(), strategy="whole_page_markdownify")
    assert result.strategy_used == "whole_page_markdownify"
    assert strategies["trafilatura_markdown"].calls == 0
    assert len(result.attempts) == 1


@pytest.mark.parametrize("make", EXTRACTORS)
def test_3b_named_strategy_failure_has_one_attempt(make):
    strategies = fake_strategies(whole_page_markdownify=FakeStrategy("whole_page_markdownify", error="nope"))
    with pytest.raises(ExtractionFailed) as caught:
        make(strategies).extract(html_document(), strategy="whole_page_markdownify")
    assert len(caught.value.attempts) == 1


@pytest.mark.parametrize("make", EXTRACTORS)
def test_4_unknown_strategy(make):
    with pytest.raises(UnknownStrategy):
        make(fake_strategies()).extract(html_document(), strategy="nope")


@pytest.mark.parametrize("make", EXTRACTORS)
def test_5_empty_output_falls_back(make):
    strategies = fake_strategies(trafilatura_markdown=FakeStrategy("trafilatura_markdown", " \n\t", "markdown"))
    result = make(strategies).extract(html_document())
    assert result.strategy_used == "readabilipy_markdownify"
    assert result.attempts[0].error


# --- 6: decoding --------------------------------------------------------------------------------

def make_fake_decoder(guess):
    return FakeTextDecoder(guess)


def make_real_decoder(guess):
    return ChainedTextDecoder(guess)


DECODERS = [pytest.param(make_fake_decoder, id="fake"), pytest.param(make_real_decoder, id="real")]


class RecordingGuess:
    def __init__(self, answer):
        self.answer, self.calls = answer, 0

    def __call__(self, raw):
        self.calls += 1
        return self.answer


@pytest.mark.parametrize("make", DECODERS)
def test_6_header_charset_wins(make):
    guess = RecordingGuess("utf-8")
    text = make(guess).decode((FIXTURES / "latin1.html").read_bytes(), "text/html; charset=iso-8859-1")
    assert "Café crème" in text
    assert guess.calls == 0


@pytest.mark.parametrize("make", DECODERS)
def test_6_meta_charset_without_header(make):
    guess = RecordingGuess("utf-8")
    text = make(guess).decode((FIXTURES / "shift_jis_meta.html").read_bytes(), None)
    assert "日本語の文章" in text
    assert guess.calls == 0


@pytest.mark.parametrize("make", DECODERS)
def test_6_neither_calls_charset_normalizer(make):
    guess = RecordingGuess("iso-8859-1")
    raw = "plain café".encode("iso-8859-1")
    assert make(guess).decode(raw, None) == "plain café"
    assert guess.calls == 1


# --- 7: content type ----------------------------------------------------------------------------

DETECTORS = [pytest.param(FakeContentTypeDetector, id="fake"),
             pytest.param(LayeredContentTypeDetector, id="real")]


@pytest.mark.parametrize("make", DETECTORS)
def test_7_content_type_detection(make):
    detector = make()
    assert detector.detect((FIXTURES / "tiny.pdf").read_bytes(), "text/html", None) == "application/pdf"
    assert detector.detect((FIXTURES / "report.docx").read_bytes(), None, "report.docx") == DOCX
    assert detector.detect((FIXTURES / "sample.jsonl").read_bytes(), None, "sample.jsonl") == "application/jsonl"


# --- 8: normalization ---------------------------------------------------------------------------

NORMALIZERS = [pytest.param(FakeTextNormalizer, id="fake"),
               pytest.param(KindTextNormalizer, id="real")]


@pytest.mark.parametrize("make", NORMALIZERS)
def test_8_json_pretty_printed_key_order_kept(make):
    out = make(100, 2).normalize('{"b":1,"a":[1,2]}', "json")
    assert out == '{\n  "b": 1,\n  "a": [\n    1,\n    2\n  ]\n}\n'


@pytest.mark.parametrize("make", NORMALIZERS)
def test_8_jsonl_one_record_per_line(make):
    out = make(100, 2).normalize((FIXTURES / "sample.jsonl").read_text(), "jsonl")
    lines = out.splitlines()
    assert len(lines) == 3
    assert [json.loads(line)["id"] for line in lines] == [1, 2, 3]


@pytest.mark.parametrize("make", NORMALIZERS)
def test_8_crlf_and_wrapping(make):
    normalizer = make(100, 2)
    assert "\r" not in normalizer.normalize((FIXTURES / "notes.txt").read_bytes().decode("utf-8"), "plain")
    wrapped = normalizer.normalize(LONG_PROSE, "prose")
    assert len(wrapped.splitlines()) == 3
    assert all(len(line) <= 100 for line in wrapped.splitlines())
    fenced = "```\n" + "x" * 300 + "\n```\n"
    assert normalizer.normalize(fenced, "markdown") == fenced


# --- 9, 10: hash and strategy names -------------------------------------------------------------

@pytest.mark.parametrize("make", EXTRACTORS)
def test_9_hash_of_returned_text_is_stable(make):
    extractor = make(fake_strategies())
    first, second = extractor.extract(html_document()), extractor.extract(html_document())
    assert first.text_sha256 == hashlib.sha256(first.text.encode("utf-8")).hexdigest()
    assert first.text_sha256 == second.text_sha256
    assert first.raw_sha256 == hashlib.sha256(html_document().raw_bytes).hexdigest()


@pytest.mark.parametrize("make", EXTRACTORS)
def test_10_strategy_names_and_available_strategies(make):
    extractor = make(fake_strategies())
    assert extractor.strategy_names("application/pdf") == ("pypdf_text", "pdfminer_text")
    result = extractor.extract(html_document())
    assert result.available_strategies == (
        "trafilatura_markdown", "readabilipy_markdownify", "whole_page_markdownify")


# --- 11: FallbackRunner alone -------------------------------------------------------------------

RUNNERS = [pytest.param(FakeFallbackRunner, id="fake"), pytest.param(FallbackRunner, id="real")]


@pytest.mark.parametrize("make", RUNNERS)
def test_11_fallback_runner_generic(make):
    calls = []

    def first(n: int) -> str:
        calls.append("first")
        raise ValueError("no")

    def second(n: int) -> str:
        calls.append("second")
        return str(n * 2)

    def third(n: int) -> str:
        calls.append("third")
        return "never"

    outcome = make(ValueError).run(21, [first, second, third])
    assert (outcome.output, outcome.used_name) == ("42", "second")
    assert calls == ["first", "second"]
    assert [(a.strategy, a.error is None) for a in outcome.attempts] == [("first", False), ("second", True)]
    with pytest.raises(AllStrategiesFailed) as caught:
        make(ValueError).run(1, [first])
    assert caught.value.attempts[0].strategy == "first"


def test_real_extractor_is_a_facade_over_its_parts():
    extractor = build_document_extractor({})
    assert isinstance(extractor, StrategyDocumentExtractor)
    assert isinstance(extractor.catalog, StrategyRegistry)
