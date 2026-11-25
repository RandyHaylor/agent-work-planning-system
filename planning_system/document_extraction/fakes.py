"""In-memory fakes for document_extraction (build log #11). Simple, dependency-free stand-ins that
honour the same contracts as the real parts; consumers test against these."""
from __future__ import annotations

import hashlib
import json
import re
import textwrap
from typing import Callable, Mapping, Sequence

from planning_system.document_extraction.extraction_interface import (
    ContentTypeDetector, DocumentExtractor, TextDecoder, TextNormalizer,
)
from planning_system.document_extraction.extraction_types import (
    AttemptRecord, ExtractionFailed, ExtractionInput, ExtractionResult, SourceDocument, StrategyFailed,
    StrategyOutput, TextKind, UnknownStrategy,
)
from planning_system.document_extraction.fallback_runner import (
    AllStrategiesFailed, Attempt, FallbackOutcome, FallbackRunnerInterface, strategy_name,
)
from planning_system.document_extraction.strategies import DEFAULT_ORDERS, ExtractionStrategy

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_EXTENSIONS = {".pdf": "application/pdf", ".docx": DOCX, ".json": "application/json",
               ".jsonl": "application/jsonl", ".md": "text/markdown", ".txt": "text/plain",
               ".html": "text/html"}


class FakeStrategy(ExtractionStrategy):
    """Scripted strategy: returns `text` as `kind`, or raises StrategyFailed(error). Records calls."""

    def __init__(self, name: str, text: str = "", kind: TextKind = "plain", error: str | None = None) -> None:
        self.name = name
        self.text, self.kind, self.error = text, kind, error
        self.calls = 0

    def extract(self, source: ExtractionInput) -> StrategyOutput:
        self.calls += 1
        if self.error is not None:
            raise StrategyFailed(self.error)
        return StrategyOutput(self.text, self.kind)


class FakeFallbackRunner(FallbackRunnerInterface):
    def __init__(self, failure_type=Exception) -> None:
        self.failure_type = failure_type

    def run(self, item, strategies):
        attempts = []
        for strategy in strategies:
            try:
                output = strategy(item)
            except self.failure_type as error:  # type: ignore[misc]
                attempts.append(Attempt(strategy_name(strategy), str(error) or type(error).__name__))
                continue
            attempts.append(Attempt(strategy_name(strategy), None))
            return FallbackOutcome(output, strategy_name(strategy), tuple(attempts))
        raise AllStrategiesFailed(tuple(attempts))


class FakeContentTypeDetector(ContentTypeDetector):
    def detect(self, raw_bytes: bytes, content_type_header: str | None, file_name: str | None) -> str:
        head = raw_bytes.lstrip(b"\xef\xbb\xbf")[:512].lstrip()
        if head.startswith(b"%PDF-"):
            return "application/pdf"
        if head.startswith(b"PK") and b"word/" in raw_bytes:
            return DOCX
        if head.lower().startswith((b"<!doctype html", b"<html")):
            return "text/html"
        jsonl_hint = (file_name or "").lower().endswith(".jsonl") or any(
            t in (content_type_header or "").lower() for t in ("ndjson", "jsonl"))
        if head[:1] in (b"{", b"[") and not jsonl_hint:
            return "application/json"
        if content_type_header:
            return content_type_header.split(";")[0].strip().lower()
        if file_name and "." in file_name:
            return _EXTENSIONS.get(file_name[file_name.rfind("."):].lower(), "application/octet-stream")
        return "application/octet-stream"


class FakeTextDecoder(TextDecoder):
    def __init__(self, guess_charset: Callable[[bytes], str | None]) -> None:
        self.guess_charset = guess_charset

    def decode(self, raw_bytes: bytes, content_type_header: str | None) -> str:
        charset = None
        if content_type_header and "charset=" in content_type_header:
            charset = content_type_header.split("charset=")[1].split(";")[0].strip().strip('"')
        if not charset:
            match = re.search(rb"<meta[^>]+charset=[\"']?([\w-]+)", raw_bytes[:4096], re.I)
            charset = match.group(1).decode("ascii") if match else None
        if not charset:
            charset = self.guess_charset(raw_bytes) or "utf-8"
        return raw_bytes.decode(charset, errors="replace")


class FakeTextNormalizer(TextNormalizer):
    def __init__(self, wrap_width: int = 100, json_indent: int = 2) -> None:
        self.wrap_width, self.json_indent = wrap_width, json_indent

    def normalize(self, text: str, kind: TextKind) -> str:
        if kind == "json":
            return json.dumps(json.loads(text), indent=self.json_indent, ensure_ascii=False) + "\n"
        if kind == "jsonl":
            return "".join(json.dumps(json.loads(line), ensure_ascii=False) + "\n"
                           for line in text.splitlines() if line.strip())
        text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
        lines, in_fence = [], False
        for line in (raw.rstrip() for raw in text.split("\n")):
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
            if in_fence or line.lstrip().startswith(("```", "#", "|")) or len(line) <= self.wrap_width:
                lines.append(line)
                continue
            indent = " " * (len(line) - len(line.lstrip()))
            lines.extend(textwrap.wrap(line, self.wrap_width, subsequent_indent=indent))
        return "\n".join(lines).strip("\n") + "\n"


class FakeDocumentExtractor(DocumentExtractor):
    """Whole pipeline in memory, built from the other fakes and the given strategies."""

    def __init__(self, strategies: Sequence[ExtractionStrategy],
                 default_orders: Mapping[str, Sequence[str]] = DEFAULT_ORDERS,
                 guess_charset: Callable[[bytes], str | None] = lambda _: "utf-8",
                 wrap_width: int = 100, json_indent: int = 2) -> None:
        self.strategies = {s.name: s for s in strategies}
        self.default_orders = default_orders
        self.detector = FakeContentTypeDetector()
        self.decoder = FakeTextDecoder(guess_charset)
        self.normalizer = FakeTextNormalizer(wrap_width, json_indent)
        self.runner = FakeFallbackRunner(StrategyFailed)

    def _order(self, content_type: str) -> tuple[str, ...]:
        orders = self.default_orders
        if content_type in orders:
            return tuple(orders[content_type])
        if content_type.startswith("text/") and "text/*" in orders:
            return tuple(orders["text/*"])
        return tuple(orders.get("*", ()))

    def _strategy(self, name: str) -> Callable[[ExtractionInput], StrategyOutput]:
        if name not in self.strategies:
            raise UnknownStrategy(name)
        strategy = self.strategies[name]

        def call(source: ExtractionInput) -> StrategyOutput:
            output = strategy.extract(source)
            if not output.text.strip():
                raise StrategyFailed("empty output")
            return output
        call.name = name  # type: ignore[attr-defined]
        return call

    def extract(self, document: SourceDocument, strategy: str | None = None) -> ExtractionResult:
        content_type = self.detector.detect(document.raw_bytes, document.content_type_header, document.file_name)
        calls = [self._strategy(n) for n in ((strategy,) if strategy else self._order(content_type))]
        source = ExtractionInput(document.raw_bytes, content_type,
                                 lambda: self.decoder.decode(document.raw_bytes, document.content_type_header),
                                 document.metadata.get("final_url"))
        try:
            outcome = self.runner.run(source, calls)
        except AllStrategiesFailed as failure:
            raise ExtractionFailed(tuple(AttemptRecord(a.strategy, a.error) for a in failure.attempts)) from failure
        text = self.normalizer.normalize(outcome.output.text, outcome.output.kind)
        return ExtractionResult(
            text=text, strategy_used=outcome.used_name, content_type=content_type,
            text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            raw_sha256=hashlib.sha256(document.raw_bytes).hexdigest(),
            attempts=tuple(AttemptRecord(a.strategy, a.error) for a in outcome.attempts),
            available_strategies=self._order(content_type))

    def strategy_names(self, content_type: str | None = None) -> tuple[str, ...]:
        return self._order(content_type) if content_type else tuple(self.strategies)
