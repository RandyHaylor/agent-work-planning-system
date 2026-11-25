# Spec: fastReader adaptation

DRAFT (agent-approved under the user's build handover; see BUILD-DECISIONS-LOG.md)

Package: `planning_system/fastreader/`, our copy of `~/ai_skills_agents_resources/ai-agent-fastReader/fastReader/` (record the source commit in the package README once). Matches the APPROVED `05-spec-references-and-reader.md`.

## Recorded decisions this builds on

- Reader direction change: "leave fastReader and the quick-json-reader plugin more or less intact and integrate them as modules ... There's a lot in them already (the interactive help menu, a lot of testing), and they're robust, powerful tools. Don't plan to rewrite them now; implement and adapt them, changing only what's needed to work with the server's cache and references."
- Draft 2 answers: "just pull a copy down and modify it directly ... Keep them as independent modules: no hard coding, no rigid coupling. Improve them as independent modules as the app needs."
- Approved references spec §1 table: `cache.py` -> "an adapter onto the server's temp cache store, per agent, full SHA-256"; `load` -> "takes text produced by document_extraction"; `web.py search` -> "result loaded into the agent's temp cache like any document"; "/tmp output paths, global dirs" -> "per-agent, in the store"; "(new) cite" -> "`cite(cache_id, start_line, end_line)` moves the item into references". "Everything else (scanner logic, TOC options, get, search options, slicing, help text, tests) is untouched."
- Approved references spec §2: "The server exposes the reader's commands as read commands over HTTPS. The thin CLI passes them through, so agents keep fastReader's command shape and help menus", and the command list (`load ... [--strategy NAME] [--search ...] [--line START COUNT] -> cache id(s) + TOC + the extraction strategy used`, `toc`, `get`, `search ... --manifests`, `json`, `cite`).
- Approved references spec §3: "`cite` keeps the item's ID when it moves it ... Identical content (same hash) reuses the stored copy. Loading a URL always fetches live." §4: "You can also load a stored reference into the reader to browse it with toc/search."
- Phase 2 references 6: "Temp cache entries are visible only to the agent that fetched them and to the admin".
- Recheck 6/7: reads are commands; "read commands ... only read, run in a read-only transaction with the same permission check."
- CLI: "The CLI should be a very thin hand-written wrapper so agents can call the server".
- Findings behind round 4: "Section indexes depend on scanner config, so citations must use line ranges."

## File-by-file

**Kept as-is (copied, imports renamed `fastReader.` -> `planning_system.fastreader.` only):**

| File | Role |
|---|---|
| `scanner.py` | four structural scanners, `load_config`, `scan_document` |
| `toc_cli.py` (`build_toc`), `preview.py` | TOC building and previews |
| `html_parser/` | used only by the kept DuckDuckGo result parser |
| `config.json` | scanner config |
| `help_content.json` | `--help-examples`, `--help-use-cases` text (hash wording edited, see below) |
| `test/test_scanner.py`, `test_toc.py`, `test_preview.py`, `test_models.py`, `test_fixtures.py`, `test/fixtures/` | unchanged tests |
| `SKILL.md`, `README.md` | kept as docs; command lines updated to the `planning` CLI |

**Changed:**

| File | Today | Change |
|---|---|---|
| `models.py` | `Document.from_file(path)` | add `Document.from_text(source_label, text)`; `from_file` stays (tests use it). `Marker`, `Manifest` unchanged |
| `cache.py` | files `<8-char hash>.txt/.json` under `~/.fastReader/cache` | replaced by `reader_cache_port.py` (protocol below) + `manifest_codec.py` (the existing `asdict` / `load_manifest` rebuild logic, as dict <-> Manifest, no files). `generate_hash` -> full SHA-256 |
| `commands/load.py` | `run_load(file_path, cache_dir, config, slice...)` reads a file | `run_load(text, source_label, extraction_info, cache, config, slice...)`: slicing, scan, summary logic unchanged; stores text + manifest through the port; returns `cache_id`, summary, `strategy_used`, `available_strategies` |
| `commands/toc.py`, `get.py`, `search.py` | `cache_dir` + `os.path` reads of `<hash>.json/.txt` | take `cache: ReaderCachePort`; read manifest and lines from it. Marker, boundary, container and matching logic untouched. `FileNotFoundError` -> `contract.NotFound` |
| `read.py` | numbered lines of a local file | `read_lines(cache, id, start, end)`, same `N\t` output; serves `/reader/{id}/lines` |
| `web.py` | `fetch_url`, `html_to_text` page conversion, `/tmp` output, `__main__` | `fetch_url`, `page_to_text`, `__main__`, `/tmp` and `~/.fastReader` removed (fetch is `http_source_fetcher`, conversion is `document_extraction`). `search_ddg` split into `ddg_search_url(terms)` and `parse_ddg_results(html, limit)` with the regex and fallback unchanged; `_TextExtractor`/`html_to_text` kept for snippet text. Used by `web_search_source` |
| `cli.py` | argparse + execution + printing, global cache dir | split into `argument_parsing.py` (`parse_args`, help-content interception, `--help-examples`/`--help-use-cases`; adds `json` and `cite` subcommands, `load --strategy NAME`, load positionals accept URL / local path / `--web-search TERMS`) and `output_formatting.py` (today's printing of load/toc/get/search results, from JSON-able dicts to text). No execution, no cache dir |
| `agent_instructions.json` | hints like `python3 -m fastReader.toc <hash>` | same hints, worded for `planning toc <cache id>`; new hints: after load "strategy used: X; other strategies: ...; reload with --strategy NAME if the text is unreadable", after web search "to register a reference, load the result's URL", after cite "reference id ..." |
| `test/test_cache.py` | file cache | replaced by `test_reader_cache_port.py` (in-memory fake) + `test_manifest_codec.py` |
| `test/test_load_command.py`, `test_toc_command.py`, `test_get_command.py`, `test_search_command.py` | temp dirs | same assertions, using the in-memory fake port and text input |
| `test/test_cli.py` | runs `main` | split to `test_argument_parsing.py` and `test_output_formatting.py`; same cases |

**New:**

| File | Role |
|---|---|
| `reader_cache_port.py` | the port below |
| `commands/cite.py` | `run_cite(cache, id, start, end)`: checks the range against the item's line count, then `cache.cite(...)` |
| `commands/json.py` | `run_json(cache, id, flags, json_reader)`: hands the item's text to quick_json_reader integration (`05-spec-quick-json-reader-integration.md`) |

**Dropped:** `load.py`, `toc.py`, `get.py`, `search.py` (5-line `python -m` shims), `fastReader.sh`, `fastReader.bat`, `test/test_wrapper_script.py`. The wrapper help text in `wrapper_help_json_on.txt` becomes the `planning` reader top-level help (kept as a text file read by `argument_parsing`); `wrapper_help_json_off.txt` is dropped because Node and quick-json-reader are always present.

## Temp cache adapter port

```python
@dataclass(frozen=True)
class CachedItem:
    item_id: str                 # temp cache id or reference id (same id space; cite keeps the id)
    source_label: str            # URL, file name or search terms
    text: str
    manifest: Manifest
    metadata: Mapping[str, str]  # origin_kind, fetched_at, strategy_used, sha256 ...

class ReaderCachePort(Protocol):           # bound to one principal by the server
    def save(self, text: str, manifest: Manifest, source_label: str, metadata: Mapping[str, str]) -> str
        # full SHA-256 of text; identical text already in this agent's cache or in references -> existing id
    def get(self, item_id: str) -> CachedItem        # temp cache (own or admin) or a visible reference; NotFound otherwise
    def cite(self, item_id: str, start_line: int, end_line: int) -> tuple[str, Citation]
        # moves the item into references keeping its id; on an existing reference just returns a Citation
```

Implementation `server/domain/references/reader_cache_adapter.py` (in references, not in fastReader): implements the port over `temp_cache_lifecycle` + `ReferenceLibrary`, created per request for the acting principal. fastReader imports nothing from the server; the server imports fastReader. The manifest is stored as JSON metadata next to the text in the temp cache store; for a reference read into the reader with no stored manifest, `get` scans it on the fly with `scan_document`.

## Exposed as server read commands and through the CLI

Server command classes (in `server/commands/`, each one class, calling fastReader functions with the bound port), routes from `BUILD-PLAN.md`:

| CLI | Route | Command | Transaction |
|---|---|---|---|
| `planning load <url / path ...> [--web-search TERMS] [--strategy NAME] [--line S C] [--search ...]` | `POST /reader/load` | `LoadIntoReader`: fetch (source fetcher) -> extract (document_extraction) -> `run_load` -> optional `run_search` | write (temp cache) |
| `planning toc <id> [toc options]` | `GET /reader/{id}/toc` | `ReaderToc` -> `run_toc` | read-only |
| `planning get <id> --section N ...` | `GET /reader/{id}/get` | `ReaderGet` -> `run_get` | read-only |
| `planning search <terms> --manifests <ids> [...]` | `POST /reader/search` | `ReaderSearch` -> `run_search` | read-only |
| `planning json <id> [flags]` | `POST /reader/{id}/json` | `ReaderJson` -> `run_json` | read-only |
| `planning lines <id> <start> <end>` | `GET /reader/{id}/lines` | `ReaderLines` -> `read_lines` | read-only |
| `planning cite <id> <start> <end>` | `POST /reader/cite` | `CiteFromReader` -> `run_cite` | write |

CLI flow per command: `argument_parsing.parse_args(argv)` -> request JSON -> `api_client` -> response JSON -> `output_formatting` -> stdout. Help flags are answered locally from `help_content.json`, no server call. Local paths are read by the CLI and sent as `file_name + file_base64`; the CLI decides URL vs path by scheme (`http://`, `https://`).

Load output (single item): source, cache id, marker counts (as today), `strategy used: <name>`, `other strategies: <names>`, and the after-load hints. Multi-item: today's compact table plus a strategy column. Fetch or extraction failure for one item prints the error (with attempts) and continues with the rest, as today's loop does for missing files.

## External integration tests (mocked up front)

1. All kept fastReader tests pass unchanged (scanner, toc, preview, models, fixtures).
2. Adapted command tests with an in-memory fake `ReaderCachePort`: load text -> id is a 64-hex SHA-256; same text twice -> same id; `--line 10 5` -> new id for the slice; toc/get/search outputs equal today's for the same fixtures.
3. `run_cite` with a range past the end -> `Invalid`; valid range -> port `cite` called with the same id.
4. `get` of an id the fake raises `NotFound` for -> `NotFound` propagates.
5. `argument_parsing`: every existing flag parses as today; `toc --help-examples` prints without an id; `load --strategy pypdf_text file.pdf`; `cite abc 3 9`.
6. `output_formatting`: given recorded JSON responses, output text equals today's CLI output plus the strategy lines.
7. Server command tests with fakes for source fetcher, extractor and port: `LoadIntoReader` returns `[{cache_id, toc, strategy_used, metadata}]`; extraction failure -> error with attempts; web search -> item with `origin_kind=web_search`.
8. `reader_cache_adapter` against a fake temp cache store and fake ReferenceLibrary: another agent's id -> `NotFound`; admin can read it; cite moves the item and keeps its id; a reference id loads with a scanned manifest.
9. `parse_ddg_results` on a saved DuckDuckGo fixture gives the same markdown as today's `search_ddg`.

## Judgement calls in this spec

- `cli.py` split into `argument_parsing` + `output_formatting` so the thin `planning` CLI imports them and keeps fastReader's exact command shape and help, while execution moves to the server. The client therefore depends on the `fastreader` package (not on the server).
- Port adapter lives in `references/`, so fastReader never imports server code.
- `load` is a write command (it writes the temp cache), though the approved spec groups it with "read commands".
- New `planning lines` CLI command for the existing `/reader/{id}/lines` route, built from `read.py`.
- `CachedItem` ids shared between temp cache and references (follows "cite keeps the item's ID").
- Manifests for references are computed on read, not stored.
- `cite` refuses items with `origin_kind=web_search` (`Invalid`, with the hint to load the result URL), from "to register a reference they have to pull the URL up through the reader".
- `wrapper_help_json_off.txt` and the shell wrappers dropped (Node is required; the CLI replaces the wrappers).

## Flagged, not resolved

- Approved spec says "Everything else (... tests) is untouched", but `test_cache.py`, the four command tests, `test_cli.py` and `test_wrapper_script.py` exercise the file cache or wrappers and must change or go.
- Dedupe: "If content is identical (same hash), reuse what's there" vs per-agent visibility. If agent B loads text identical to agent A's uncited temp item, reusing A's item would expose it to B. This spec dedupes within the agent's own temp cache and against references only.
