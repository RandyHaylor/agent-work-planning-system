# Spec: document_extraction

DRAFT (agent-approved under the user's build handover; see BUILD-DECISIONS-LOG.md)

Package: `planning_system/document_extraction/`. Bytes + metadata in, citable text out. No network, no database, no knowledge of the temp cache, references or fastReader.

## Recorded decisions this builds on

- Tree v5 (`05-module-specs.md`): "document_extraction/ own package; bytes + metadata -> citable text; no network, no DB", with `text_decoding` ("header charset -> meta tag -> charset_normalizer"), `content_type_detection` ("header + leading bytes"), `fallback_runner` ("generic: tries interchangeable strategies in order; reports which one was used"), `text_normalization` ("line endings, soft wrap, JSON pretty-print -> citable form"), `strategies/` ("one per extractor").
- Round 4.4: "We need a clean strategy pattern for web extraction so we can port in and choose from a list of different options - even automatically trying mlutiple approaches after failtures." and "saying 'we need a generic strategy adapter/wrapper and way to choose/fall back to strategies' solves the design issue at a higher level".
- Round 4.5: "the primary retrieve attempt can still catch errors and look for markers of failure. you have not convinced me a separate check fetch adds anythihg but complexity".
- Recheck 8: "Pull decoding out. The fallback loop is logic and should be abstracted and generic: a strategy pattern, with extractors as interchangeable strategies."
- Recheck 9: "The reader interface tells the calling agent which extraction method was used, so it can ask for another. Obvious HTTP errors are caught and trigger the automatic fallback; if nothing works, return an error. No separate quality checks: the calling agent decides whether the text is readable."
- Round 4.3 (citable text, user chose normalizing at extraction): "JSON is pretty-printed with a fixed indent and key order kept; JSONL stays one record per line; prose is soft-wrapped at a fixed width. Citations are line ranges only".
- Phase 2 references 3: "The agent picks the extraction strategy through the interface and is told which one was used; if the result is bad, it tries another and moves on."
- Reader direction change: "It will read documents too (Word, PDF, whatever)"; references spec §1: "Word via a new docx strategy".
- Findings behind round 4 (research, recorded): HTML order "trafilatura (markdown; already has its own readability/jusText fallback) → readabilipy + markdownify → whole-page markdownify (never failed; keeps nav)"; "PDF: pypdf (BSD-3, license file checked) → pdfminer.six"; "Avoid html2text (GPL), pymupdf4llm (AGPL), marker"; "Text passes through; JSON pretty-printed; JSONL validated"; "Decoding by header charset → meta tag → charset_normalizer gave no garbled text".
- Build handover: "Ensure you build modularly, avoid monoliths".

## Nested modules

```
document_extraction/
  __init__.py                 public surface only: DocumentExtractor, build_document_extractor, types, errors
  extraction_types            SourceDocument, ExtractionInput, StrategyOutput, TextKind, AttemptRecord,
                              ExtractionResult, ExtractionFailed, StrategyFailed (data only)
  document_extractor          facade: detect type -> pick strategy list -> fallback_runner -> text_normalization
  text_decoding/              bytes -> str
    charset_sources           header charset, <meta charset>/<meta http-equiv>, BOM
    text_decoder              tries the sources in order, then charset_normalizer
  content_type_detection/     -> one ContentType string
    header_content_type       parses Content-Type header (media type only)
    leading_bytes_sniffer     magic bytes: %PDF-, PK..+word/ (docx), <!doctype html/<html, { or [ (JSON), BOM
    file_name_hint            extension of an uploaded file name (.pdf, .docx, .json, .jsonl, .md, .txt, .html)
    content_type_detector     combines the three: sniffed bytes win over header, header over file name
  fallback_runner/            generic; knows nothing about documents
    fallback_runner           FallbackRunner[I, O]: run(input, strategies) -> (output, used_name, attempts)
  text_normalization/         one function per text kind, called by the facade
    line_endings              CRLF/CR -> LF, strip trailing spaces, drop NULs, single trailing newline
    prose_wrapper             soft wrap at a fixed width; never wraps fenced code, tables, headings, list markers' indent
    json_formatter            pretty-print, fixed indent, key order kept
    jsonl_formatter           one compact record per line, blank lines dropped
    text_normalizer           dispatch by TextKind
  strategies/                 one per extractor; each implements ExtractionStrategy
    strategy_interface        ExtractionStrategy protocol
    strategy_registry         name -> strategy; default order per content type (from config)
    trafilatura_markdown
    readabilipy_markdownify
    whole_page_markdownify
    pypdf_text
    pdfminer_text
    docx_text
    text_passthrough
    json_pretty_print
    jsonl_passthrough
```

Each nested module is small; `document_extractor` reads as a list of steps and calls only these.

## Types

```python
TextKind = Literal["prose", "markdown", "json", "jsonl", "plain"]

@dataclass(frozen=True)
class SourceDocument:              # produced by a source fetcher (see 05-spec-source-fetching.md)
    raw_bytes: bytes
    locator: str                   # URL, uploaded file name, or search terms
    origin_kind: Literal["web", "upload", "web_search"]
    fetched_at: datetime
    content_type_header: str | None
    file_name: str | None
    metadata: Mapping[str, str]    # final URL, status, headers kept, etc. (passed through untouched)

@dataclass(frozen=True)
class ExtractionInput:             # what a strategy sees
    raw_bytes: bytes
    content_type: str
    decoded_text: Callable[[], str]   # lazy, cached; PDF/docx strategies never call it
    base_url: str | None

@dataclass(frozen=True)
class StrategyOutput:
    text: str
    kind: TextKind

@dataclass(frozen=True)
class AttemptRecord:
    strategy: str
    error: str | None              # None = this one was used

@dataclass(frozen=True)
class ExtractionResult:
    text: str                      # normalized, citable
    strategy_used: str
    content_type: str
    text_sha256: str               # full SHA-256 of `text` (UTF-8)
    raw_sha256: str
    attempts: tuple[AttemptRecord, ...]
    available_strategies: tuple[str, ...]   # for this content type, so the agent can ask for another

class StrategyFailed(Exception): ...        # raised by a strategy: library error, empty output, wrong input
class ExtractionFailed(Exception):          # every strategy failed; carries attempts
    attempts: tuple[AttemptRecord, ...]
class UnknownStrategy(Exception): ...       # --strategy names nothing registered
```

## Public interface

```python
class DocumentExtractor:
    def extract(self, document: SourceDocument, strategy: str | None = None) -> ExtractionResult
    def strategy_names(self, content_type: str | None = None) -> tuple[str, ...]

def build_document_extractor(config: Mapping) -> DocumentExtractor   # factory; config section "document_extraction"

class ExtractionStrategy(Protocol):
    name: str
    def extract(self, source: ExtractionInput) -> StrategyOutput     # raises StrategyFailed

class FallbackRunner(Generic[I, O]):
    def run(self, item: I, strategies: Sequence[Strategy[I, O]]) -> FallbackOutcome[O]
        # tries in order; a strategy's exception (of the configured failure type) is recorded and the next runs;
        # returns the first success with its name and all attempts; raises AllStrategiesFailed(attempts)
```

Behavior:
- `strategy=None`: the default order for the detected content type runs through `FallbackRunner`. `strategy="name"`: only that strategy runs (no fallback), whatever the detected type; failure returns `ExtractionFailed` with one attempt.
- A strategy fails only on: exception from its library, empty output (no non-whitespace), or input it can't read. No quality checks (length, ratio, heading counts, garbling) anywhere.
- Fetch-level failures (HTTP status, challenge markers) are caught by the source fetcher before extraction; see the conflict note at the end.
- After success the facade normalizes by `StrategyOutput.kind` and hashes the normalized text.

## Default strategy order per content type (config, overridable)

| Content type | Order |
|---|---|
| `text/html`, `application/xhtml+xml` | trafilatura_markdown → readabilipy_markdownify → whole_page_markdownify |
| `application/pdf` | pypdf_text → pdfminer_text |
| `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | docx_text |
| `application/json` | json_pretty_print → text_passthrough |
| `application/x-ndjson`, `application/jsonl` | jsonl_passthrough → text_passthrough |
| `text/markdown`, `text/plain`, other `text/*` | text_passthrough |
| anything else | text_passthrough (fails on undecodable binary) |

Strategy kinds: trafilatura/readabilipy/whole-page -> `markdown`; pypdf/pdfminer/docx -> `prose`; text_passthrough -> `plain` (markdown files -> `markdown`); json -> `json`; jsonl -> `jsonl`. Normalization: `json` and `jsonl` are formatted only; `prose` and `markdown` get line endings + soft wrap; `plain` gets line endings + soft wrap.

Libraries: trafilatura (`output_format="markdown"`), readabilipy (pure-Python mode, `use_readability=False`, so no extra Node dependency) + markdownify, markdownify, pypdf, pdfminer.six, python-docx, charset_normalizer.

## External integration tests (mocked up front)

Mocks replace each third-party library at the strategy boundary; the facade tests use fake strategies.

1. `extract` on HTML bytes with default order: fake trafilatura raises -> readabilipy fake returns markdown -> result `strategy_used == "readabilipy_markdownify"`, attempts list both, text soft-wrapped.
2. All fakes fail -> `ExtractionFailed` with one `AttemptRecord` per strategy, each with its error.
3. `strategy="whole_page_markdownify"` -> only that strategy is called, even if trafilatura would work.
4. `strategy="nope"` -> `UnknownStrategy`.
5. Empty output from a strategy counts as failure and falls back.
6. Decoding: header charset `iso-8859-1` wins; no header -> `<meta charset="shift_jis">`; neither -> charset_normalizer fake is called.
7. Content type: `%PDF-` bytes with header `text/html` -> `application/pdf`; `.docx` upload with no header -> docx; `.jsonl` file -> jsonl.
8. Normalization: JSON `{"b":1,"a":[1,2]}` -> fixed-indent pretty print, key order `b`, `a` kept; JSONL with blank lines -> one record per line; CRLF -> LF; a 300-char prose line wraps at the configured width; a fenced code block is not wrapped.
9. `text_sha256` equals SHA-256 of the returned text; identical input twice -> identical hash.
10. `strategy_names("application/pdf") == ("pypdf_text", "pdfminer_text")`; `available_strategies` is set on every result.
11. `FallbackRunner` alone, with plain functions: order kept, stops at first success, generic over input/output types.
12. Real-library smoke tests (marked, run on real libraries in level 7): one fixture each for HTML, PDF, docx, JSON, JSONL, text.

## Judgement calls in this spec

- Wrap width 100 columns, JSON indent 2 (config values). Decisions say "fixed"; numbers not recorded.
- Docx library python-docx (MIT): docx was never in the extractor research; no alternatives tested.
- readabilipy in pure-Python mode to avoid depending on its optional Node path.
- `--strategy` given = that strategy only, no fallback.
- Sniffed bytes beat the Content-Type header (servers mislabel PDFs/JSON).
- Hash is of the normalized text (dedupe identity); raw bytes hash kept in the result as metadata.

## Flagged, not resolved

- Recheck 9 says HTTP errors "trigger the automatic fallback", but no extraction strategy can recover from a 404 or a Cloudflare challenge, and only one HTTP fetcher exists. This spec: the fetcher catches them and returns an error (no extraction); `FallbackRunner` is generic so fetchers could be chained later. Needs the user's reading.
- Round 4.3 says "raw bytes are kept for reference"; the later stores (temp cache, Reference) list text + sha256 + metadata only. This spec returns `raw_sha256`; whether raw bytes are stored is for the temp cache / references spec.
