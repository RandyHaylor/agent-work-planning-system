# fastReader

**Deterministic, structural pre-reader for LLM agents and humans.** Turn "open this 7 MB file" into a handful of sub-kilobyte hops. No format-specific config — one tool handles markdown, code, HTML/XML, JSONL, YAML, logs, and plain prose.

---

## Why

An LLM that reads a file with the generic `Read` tool spends roughly `bytes / 4` tokens just to see it. For anything over a few hundred KB, that consumes the context window before you've even started reasoning. fastReader's first step, `load`, costs **≤ 1 %** of that on every file type tested — and what it returns isn't a preview, it's a **count histogram for every structural scanner family**. The agent reads the histogram, picks the scanner(s) that match the document's shape, and pulls a custom TOC. No preconceptions about the format needed.

Measured on four real files (2026-04-23, `tokens ≈ bytes / 4`):

| File                                  | Raw bytes | `load` bytes | Savings   |
|---------------------------------------|----------:|-------------:|----------:|
| log4javascript `manual.html` (HTML)   |   213,868 |          766 | **99.64 %** |
| Claude Code plan (markdown)           |    49,379 |          492 | **99.00 %** |
| xstate `api-reference.md` (code docs) |   257,396 |          642 | **99.75 %** |
| 7 MB Claude session JSONL             | 7,041,642 |          672 | **99.99 %** |

Full scenario-by-scenario table further down.

---

## Install

fastReader is a self-contained Python package. Copy the folder under any parent directory — for Claude Code users the natural home is `~/.claude/skills/fastReader/`.

Invoke via the cross-platform wrapper — **do not set `PYTHONPATH`**, the wrapper computes it from its own location.

```bash
# Linux / macOS
~/.claude/skills/fastReader/fastReader.sh load big_doc.md
~/.claude/skills/fastReader/fastReader.sh toc <hash> --sections --show-line-range-count
```

```bat
REM Windows
%USERPROFILE%\.claude\skills\fastReader\fastReader.bat load big_doc.md
%USERPROFILE%\.claude\skills\fastReader\fastReader.bat toc <hash> --sections --show-line-range-count
```

Running the wrapper with no args prints the subcommand list and tells you whether the optional `json` module (see below) is detected.

### Direct Python integration (skip the wrapper)

The wrapper is for convenience; the Python modules themselves are the public interface and are safe to invoke directly. Use this path when you want to:

- **Embed fastReader in your own CLI / dispatcher / orchestrator** — call `python3 -m fastReader.<cmd>` from any runner you already have.
- **Import as a library** — `from fastReader.commands.load import run_load`, `from fastReader.commands.toc import run_toc`, etc. Each subcommand's `run_*` function is the entry point used by the CLI itself and is stable.
- **Pipe output into another tool** — no shell-wrapper indirection between your pipeline and Python.
- **Run in a container / CI job** where the wrapper script is awkward to ship.

Invocation:

```bash
PYTHONPATH=<parent-of-fastReader> python3 -m fastReader.load big_doc.md
PYTHONPATH=<parent-of-fastReader> python3 -m fastReader.toc <hash> --sections --show-line-range-count
```

**PYTHONPATH foot-gun:** it must be the **parent** of the `fastReader/` folder, not `fastReader/` itself — `python3 -m fastReader.load` needs `fastReader` importable as a package. The wrapper exists specifically to absorb this; pick it up if you don't need the direct integration.

Manifest hashes are deterministic from file content + slice range, cached at `~/.fastReader/cache/`. Tests: `python3 -m pytest fastReader/test -q` (108 green as of this writing).

---

## The grammar in one paragraph

`load` reads a file (or several) and returns a short **count histogram** across every structural scanner family, plus a content-addressed hash. You read the histogram and pick a scanner family that matches this document. `toc <hash> --<family>` prints an annotated TOC — line range, child count, and a preview per row. Pick the interesting row, `load --line START COUNT` to slice it into its own hash, and recurse. `get` pulls a row's full content. `search` finds keywords across any number of loaded hashes and returns hits with chapter/section/subsection breadcrumbs.

---

## Live walkthrough 1 — an HTML manual the agent has never seen (214 KB)

```bash
$ fastReader.sh load log4javascript/docs/manual.html
```

```text
  Blocks: 264
  Bracket Depth 1: 87
  Indent Depth 5: 228
  Indent Depth 6: 235
  Tag Depth 2: 2
  Tag Depth 5: 20      ← one-screen TOC candidate
  Tag Depth 6: 85
  Tag Depth 7: 262
  ...
  Browse: fastReader.sh toc c3bf1ebb --sections --show-line-range-count
```

No chapters, no sections (this isn't markdown). The histogram tells the agent `Tag Depth 5: 20` is the one-screen structural view.

```bash
$ fastReader.sh toc c3bf1ebb --tag-depth 5 --show-line-range-count --sample-size 100 --limit 0
```

```text
tag_depth_5 9   ln 122-253  (132)   <div id="loggersappenderslayoutslevels">   (8 children)
tag_depth_5 12  ln 495-928  (434)   <div id="loggers">                         (8 children)
tag_depth_5 13  ln 929-2396 (1468)  <div id="appenders">                       (7 children)
tag_depth_5 14  ln 2397-3033 (637)  <div id="layouts">                         (8 children)
# WARNING: 'tag_depth_5 13' spans 1468 lines but the preview is a tiny window.
```

fastReader auto-fires the integrity warning on the 1468-line giant. Slice-load it to get a fresh hash scoped to those lines, then drill one more level:

```bash
$ fastReader.sh load log4javascript/docs/manual.html --line 929 1468
# → new hash 0c8aca73
$ fastReader.sh toc 0c8aca73 --tag-depth 2 --show-line-range-count --sample-size 100
```

```text
tag_depth_2 2  ln 3-96    (94)   <div id="appender">              (5 children)
tag_depth_2 3  ln 97-113  (17)   <div id="alertappender">         (6 children)
tag_depth_2 4  ln 114-502 (389)  <div id="ajaxappender">          (12 children)
tag_depth_2 5  ln 503-1025 (523) <div id="popupappender">         (11 children)
tag_depth_2 6  ln 1026-1423 (398) <div id="inpageappender">       (10 children)
tag_depth_2 7  ln 1424-1468 (45)  <div id="browserconsoleappender"> (8 children)
```

**Four commands, ≈ 4.3 KB total output, zero preconceptions about the doc.** If the task was "tell me about PopUpAppender", the agent now knows to slice lines 503–1025.

---

## Live walkthrough 2 — a Claude Code plan file (49 KB markdown with code fences)

```bash
$ fastReader.sh load mutable-pondering-pascal.md
```

```text
  Chapters: 10
  Sections: 14            ← narrative TOC
  Subsections: 22
  Bracket Depth 1: 37     ← every fenced code / JSON / subprocess line
  Indent Depth 1: 20
```

Two perpendicular views are useful here — pull BOTH:

```bash
$ fastReader.sh toc d66092f1 --sections --show-line-range-count --sample-size 100
```

```text
section  7  ln 427-566 (140)  ## Periodic Review Loop (Sanity Checks)
section  8  ln 567-639  (73)  ## Loop Lifecycle: Templates, Archiving, and Recovery
section 14  ln 694-751  (58)  ## User Control — Pause, Override, Exit
```

```bash
$ fastReader.sh toc d66092f1 --bracket-depth 1 --show-line-range-count --sample-size 80
```

```text
bracket_depth_1 17  ln 202-206  (5)   ["git", ...])` works cross-platform ...
bracket_depth_1 29  ln 447-549  (103) {  (4 children)    ← nested JSON/Python block
bracket_depth_1 32  ln 556-588  (33)  {"systemMessage": "REVIEW REJECTED: ..."}
```

The same 49 KB document, two maps (~6 KB combined): narrative structure AND an inventory of every executable artifact. Raw `Read` gives you neither view at any price — just a wall of text.

---

## The four structural scanners (one pass, all at once)

| Scanner            | Flag                                             | Good for                                                             |
|--------------------|--------------------------------------------------|----------------------------------------------------------------------|
| Header regex       | `--chapters` / `--sections` / `--subsections`    | Markdown / reST / RFCs / anything with `#` or `##` heading syntax    |
| Indent-depth       | `--indent-depth N`                               | Python, YAML, outlined notes, pretty-printed JSON                    |
| Bracket-depth      | `--bracket-depth N`                              | JSONL (record per line), JSON, braces/brackets inside any text       |
| Tag-depth          | `--tag-depth N`                                  | HTML, XML, SVG, any balanced-tag markup                              |
| Blocks (fallback)  | `--blocks`                                       | Files with no detectable structure — fixed-size chunk-and-preview    |

`load` runs every scanner simultaneously. You pick which to surface at `toc` time.

---

## Self-documenting CLI

Three help views per subcommand — ask the tool instead of guessing:

```bash
fastReader.sh toc --help             # argparse flag reference
fastReader.sh toc --help-examples    # copy-paste recipes
fastReader.sh toc --help-use-cases   # "user said X → run Y" mapping
```

Works for `load`, `toc`, `get`, `search`. `--help-examples` / `--help-use-cases` do **not** require the subcommand's normal positional args — `fastReader.sh toc --help-examples` works with no hash.

Example (truncated):

```text
$ fastReader.sh toc --help-examples
# Copy-paste examples for: fastReader.toc
# (replace <hash>, <h1>, <h2>, <file> with real values)

# Sections with line ranges and sizes - the essential overview
fastReader.sh toc <hash> --sections --show-line-range-count --sample-size 80

# Hypothesis + conclusion view: intro AND closing thought of every section, no entry cap
fastReader.sh toc <hash> --sections --show-line-range-count \
    --sample-size 80 --end-sample-size 120 --limit 0
...
```

---

## Optional `json` module — quick-json-reader integration

If the sister [quick-json-reader](https://github.com/RandyHaylor/quick-json-reader) skill is installed alongside fastReader (typical path: `<parent-of-fastReader>/quick-json-reader/`, or set `FAST_READER_JSON_BIN`), the wrapper auto-detects it and enables a `json` subcommand — pure pass-through to that binary:

```bash
fastReader.sh json file.json --search-vals error timeout
fastReader.sh json file.json --search-keys user profile --include-search-children
fastReader.sh json file.json --exclude-fields-matching token password secret
fastReader.sh json file.json --show-schema
fastReader.sh json file.json --search-vals user123 --exclude-fields-matching token --output json
```

Output formats: `txt` (default), `csv`, `json`, `schema`. Full flag grammar documented in quick-json-reader's own repo.

**When to use which tool**

| You want to …                                                              | Use                                                                |
|----------------------------------------------------------------------------|--------------------------------------------------------------------|
| Navigate a 7 MB JSONL chat log by record                                   | `fastReader.sh load` + `fastReader.sh toc --bracket-depth 1`        |
| Find every `"error"` value regardless of nesting                           | `fastReader.sh json file.json --search-vals error`                  |
| Strip `token`/`password` fields before handing JSON to another agent       | `fastReader.sh json file.json --exclude-fields-matching token password --output json` |
| Learn the shape of an unfamiliar JSON API response                         | `fastReader.sh json file.json --show-schema`                        |

fastReader's own `--bracket-depth N` is *where is it*; quick-json-reader is *what does it contain*. Complementary, not redundant. When the binary is absent, `fastReader.sh` (no args) prints `json (NOT INSTALLED)` with install guidance — never a silent failure.

---

## Integrity warnings (do not ignore)

fastReader truncates aggressively — that's the feature. But tidy previews can look authoritative even when the middle of a long block held the critical detail.

1. **After scanning, read in full before concluding.** Once a row of interest is identified, `fastReader.sh get <hash> --section N` (or slice-load just that range). Previews are for navigation, not final answers.
2. **If new terminology appeared in a preview, search for it** (`fastReader.sh search <term> --manifests <hash>`) before drawing a conclusion.
3. **Heed the high-ratio warning.** When a section spans ≈ 10× the preview size, fastReader prints a `WARNING` line noting the end-preview is the LAST line of the block, **not** a summary.
4. **Don't confuse shape with content.** Tag / bracket / indent counts give you structure. The actual rules live in the content.

fastReader appends an `INTEGRITY NOTE` after every `toc` run. Follow it.

---

## Full benchmark

Four target files. Scenarios:

- **S1** — `wc -c` (raw `Read` cost proxy).
- **S2** — `fastReader.sh load <file>`.
- **S3** — `fastReader.sh toc <hash> --sections --show-line-range-count --sample-size 80`.
- **S4** — S3 + `--end-sample-size 120 --limit 0`.
- **S5** — file-type-specific scanner (tag-depth-2 on HTML, bracket-depth-1 on JSONL, etc.).
- **S6** — slice-drill the biggest entry and re-TOC the slice.
- **S7** — realistic keyword search.

All numbers are stdout bytes; tokens ≈ bytes / 4.

| Scenario                  |    HTML (214 KB) | PLAN (49 KB) | CODEMD (257 KB) | JSONL (7 MB) |
|---------------------------|-----------------:|-------------:|----------------:|-------------:|
| S1 raw (wc -c)            |          213,868 |       49,379 |         257,396 |    7,041,642 |
| S2 load                   |              766 |          492 |             642 |          672 |
| S3 sections               |              551 |        1,471 |           1,306 |          551 |
| S4 sections + end-previews|              551 |        3,313 |           2,581 |          551 |
| S5 format-specific        |              896 |        1,353 |             551 |        3,685 |
| S5b (2nd complementary)   |                — |        1,915 |           1,594 |            — |
| S6 slice-drill            |            1,298 |        1,386 |           2,074 |        1,138 |
| S7 keyword search         |            1,180 |        3,327 |           3,165 |       45,646 |

S3/S4 returning only the boilerplate footer on HTML and JSONL is **correct** — those formats have no markdown-header markers, and the histogram already told the agent to reach for `--tag-depth` / `--bracket-depth` instead. That choice is the feature.

---

## What fastReader is NOT

- **Not a renderer** — use the optional `json` module (quick-json-reader) for JSON extraction/visualization.
- **Not a web fetcher** — use your harness's fetch tool; pipe the parsed text through `load`.
- **Not a code understander** — it sees structure, not semantics.
- **Not a replacement for reading** — it's a scope-reducing pre-step. Always pull content in full for decisions that matter.

---

## Contributing / status

Pre-1.0. File layout:

```text
fastReader/
├── cli.py                  # argparse + dispatch; --help-examples interception
├── scanner.py              # the four structural scanners
├── cache.py                # content-addressed manifest cache (~/.fastReader/cache)
├── fastReader.sh           # Linux/macOS wrapper (auto-resolves PYTHONPATH; detects json module)
├── fastReader.bat          # Windows wrapper
├── help_content.json       # data-driven --help-examples / --help-use-cases
├── agent_instructions.json # hints injected after load / toc
├── SKILL.md                # Claude Code skill descriptor + recipes (loaded on skill invocation)
├── README.md               # this file
└── test/                   # pytest suite (108 tests as of 2026-04-24)
```

License: **TBD**.
