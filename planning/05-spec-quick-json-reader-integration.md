# Spec: quick-json-reader integration

DRAFT (agent-approved under the user's build handover; see BUILD-DECISIONS-LOG.md)

Package: `planning_system/quick_json_reader/`, our copy of `~/my_projects/quick-json-viewer-project/quick-json-reader/` (record the source commit once). JavaScript, run with Node. Called by fastReader's `json` command on stored text; results are reported with line ranges of the stored text so they can be cited.

## Recorded decisions this builds on

- Reader direction change: "the quick-json-reader plugin for fastReader should be integrated too, because it has useful functionality." and "leave fastReader and the quick-json-reader plugin more or less intact ... changing only what's needed to work with the server's cache and references."
- Draft 2 answers: "Use Node for now as a requirement. It's not that big of a deal." and "just pull a copy down and modify it directly ... Keep them as independent modules: no hard coding, no rigid coupling."
- Approved references spec §1: "quick_json_reader/ our copy of quick-json-reader (JavaScript, run with Node), with its 25 tests and SKILL.md"; table: "quick-json-reader pass-through | exec of a sibling binary | called on cached JSON text; results reported with line ranges of the stored text so they can be cited". §2: `json <cache id> [quick-json-reader flags]`.
- Tree v5: "quick_json_reader/ our copy (JavaScript, Node), kept mostly intact; results as line ranges of stored text".
- Findings behind round 4: "Its line numbers belong to its rendered view, not the stored text, so citations must point at the stored text."
- Round 4.3: "JSON is pretty-printed with a fixed indent and key order kept; JSONL stays one record per line ... Citations are line ranges only".
- No /tmp or global dirs (approved spec §1: "/tmp output paths, global dirs | shared | per-agent, in the store").

## Nested modules

```
quick_json_reader/
  js/
    quick_json_reader.js        copied as-is (1,030 lines): parser, pipeline, renderer, runCli, runWithJsonText
    stdin_runner.js             NEW, ~30 lines: reads {"text", "argv"} JSON from stdin, parses argv with the
                                existing parseArgs (placeholder source), runs runWithJsonText, writes outputText
                                to stdout; same exit codes as runCli (2 usage, 1 invalid JSON)
    tests/test_quick_json_reader.js   copied as-is (25 tests), plus tests for stdin_runner
    SKILL.md, LICENSE, README.md      copied (help text for the `json` flags)
  node_runner                   Python: runs `node stdin_runner.js` as a subprocess; no shell, no temp files
  json_line_locator/            Python: address -> line range in the stored text
    pretty_json_locator         JSON: walks the stored pretty-printed text with a source-map library
    jsonl_locator               JSONL: record index -> its single line
  address_annotator             Python: adds "(ln S-E)" to each rendered line that carries an address
  json_reader                   facade used by fastReader's commands/json.py
```

Not copied: `web-ui/`, `screenshots/`, `examples/` (not part of the decided scope).

## Types

```python
@dataclass(frozen=True)
class NodeRunResult:
    stdout: str
    stderr: str
    exit_code: int

@dataclass(frozen=True)
class LineRange:
    start_line: int      # 1-based, in the stored text
    end_line: int

@dataclass(frozen=True)
class JsonReaderOutput:
    text: str                                  # rendered output, each addressed line annotated "(ln S-E)"
    line_ranges: Mapping[str, LineRange]       # address "0-3-1" -> range, for every annotated line
    output_format: Literal["txt", "csv", "json"]

class JsonReaderUsageError(Exception): ...     # exit 2 (bad flags) -> contract.Invalid
class JsonReaderInputError(Exception): ...     # exit 1 (not JSON/JSONL) -> contract.Invalid
```

## Public interface

```python
class JsonReader:
    def __init__(self, node_runner: NodeRunner, locator_factory: JsonLineLocatorFactory) -> None
    def run(self, stored_text: str, text_kind: Literal["json", "jsonl"], flags: Sequence[str]) -> JsonReaderOutput

class NodeRunner:
    def __init__(self, node_executable: str, script_path: Path, timeout_seconds: float) -> None   # from config
    def run(self, text: str, argv: Sequence[str]) -> NodeRunResult

class JsonLineLocator(Protocol):
    def locate(self, address_steps: Sequence[int]) -> LineRange      # raises KeyError for an unknown address
```

## Mapping results to stored-text line ranges

1. `JsonReader.run` always appends `--show-full-addresses` (unless the agent passed `--output csv|json` or `--show-schema`, which carry no tree lines) and passes the agent's flags otherwise untouched.
2. quick-json-reader renders `[a-b-c] label: value`, where each step is the child's ordinal (array index, or key position in insertion order). With `--show-node P`, rendered addresses are relative to P, so the annotator prefixes P's steps.
3. JSON (`text_kind="json"`): the stored text was written by `document_extraction`'s `json_formatter` (fixed indent, key order kept). `pretty_json_locator` parses the stored text with `json-source-map` (JSON pointer -> start/end line), converts ordinal steps to pointer segments by walking the parsed value (Python dicts keep key order), and returns `start_line`..`end_line` of that value (the key's line through its closing bracket).
4. JSONL (`text_kind="jsonl"`): stored one record per line, so the first step `n` maps to line `n+1`; deeper steps map to the same single line (a record is one line).
5. `address_annotator` adds ` (ln S-E)` after each addressed line and collects `line_ranges`. Its own rendered line numbers are left as the tool prints them; only the `ln` ranges are citable.
6. Lines without an address (stats header, schema output, csv/json formats) are returned unchanged.

The agent then cites with `planning cite <id> S E` on the same stored item.

## External integration tests (mocked up front)

1. `NodeRunner` with a fake subprocess function: passes `{"text","argv"}` on stdin, no shell, timeout enforced -> error on timeout.
2. `JsonReader` with a fake `NodeRunner` returning recorded rendered output with addresses: each addressed line gets the right `(ln S-E)` for a fixture stored text.
3. `--show-node 2-0` output with relative addresses -> ranges of the absolute node.
4. Exit 2 -> `JsonReaderUsageError`; exit 1 -> `JsonReaderInputError`, stderr in the message.
5. `pretty_json_locator` on a 2-indent fixture: `[]` -> whole document; `[1]` -> second key's value lines; nested array element; scalar value -> single line.
6. `jsonl_locator`: `[3]` -> line 4; `[3-2]` -> line 4.
7. `--output json` -> output untouched, empty `line_ranges`.
8. JS: the 25 copied tests pass under `node --test` (or their current runner); new `stdin_runner` tests: valid input -> same output as `runCli` on a file with the same content; bad flags -> exit 2.
9. Real Node smoke test (level 7): `JsonReader` on a stored fixture end to end, then the annotated ranges cut from the stored text parse back to the addressed values.

## Judgement calls in this spec

- A new `stdin_runner.js` beside the unchanged `quick_json_reader.js` so text goes in over stdin (no temp files, no `/tmp`); the original file needs no edit.
- `--show-full-addresses` forced on so every tree line can be mapped; agents' other flags pass through.
- Line mapping done in Python against the stored text, not by changing the JS renderer.
- `json-source-map` (PyPI) for JSON pointer -> line positions instead of a hand-written tokenizer; to confirm the package and its license at scaffold.
- JSONL sub-record addresses map to the whole record line.
- `web-ui/`, `screenshots/`, `examples/` not copied.

## Flagged, not resolved

- The approved spec allows `json <cache id>` on any cached item, but the line mapping relies on the text being in `json_formatter`'s fixed form. An item extracted as `text_passthrough` (e.g. JSON that failed `json_pretty_print`) or a JSON reference whose text came from elsewhere may not map; this spec returns output without ranges for lines it can't locate rather than failing.
