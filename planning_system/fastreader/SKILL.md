---
name: fastReader
description: "Structural scanner and drilldown for text, JSON/JSONL, HTML, code, logs — USE FIRST BEFORE READING ANY LARGE FILE. Primary tool for navigating large or unfamiliar text. Load one or many files, get a structural TOC instantly, drill into the interesting sections, search across all loaded files with container context. Works on ANY text-like format (markdown, code, JSONL chat logs, YAML, HTML, plain prose) because it has four independent structural scanners (chapter/section regex, indent-depth, JSON bracket-depth, HTML/XML tag-depth) running simultaneously. To invoke: (1) load this skill via the Skill tool — the first line of the loaded skill prints its base directory, and that path is `<skill-dir>`; (2) run the cross-platform wrapper `<skill-dir>/fastReader.sh <subcmd>` (Linux/macOS) or `<skill-dir>\\fastReader.bat <subcmd>` (Windows). NEVER search the filesystem for the wrapper — loading the skill is the only way to learn its location. Subcommands: load | toc | get | search (plus optional `json` when quick-json-reader is installed alongside)."
user-invocable: true
---

# fastReader — Your first move on any big file

Reading a file with the Read tool costs roughly `bytes / 4` tokens. fastReader's initial `load` step costs **≤ 1 %** of that — and tells you the document's full structural histogram in one shot.

Measured against four real files on 2026-04-23 (`tokens ≈ bytes / 4`):

| File type               | Raw bytes | `load` bytes | `load` as % of raw | Savings on `load` |
|-------------------------|----------:|-------------:|-------------------:|------------------:|
| HTML reference manual   |   213,868 |          766 |              0.36 % |       **99.64 %** |
| Claude Code plan (.md)  |    49,379 |          492 |              1.00 % |       **99.00 %** |
| Code-reference markdown |   257,396 |          642 |              0.25 % |       **99.75 %** |
| 7 MB session JSONL      | 7,041,642 |          672 |            0.0095 % |       **99.99 %** |

Full benchmark (S1–S7 per file) lives in `README.md` in this skill folder. Reading the whole 7 MB session JSONL straight would blow the context window; fastReader navigates it in ≈1 KB increments.

**Use fastReader whenever a file is >500 lines, or you don't know its structure yet, or you have multiple files to search across.**

## How to invoke (Linux/macOS + Windows)

fastReader ships cross-platform wrapper scripts that auto-resolve `PYTHONPATH` for you. **You do not set any env var.** Use the wrapper:

- **Linux/macOS:** `<skill-dir>/fastReader.sh <subcmd> [args...]`
- **Windows:** `<skill-dir>\fastReader.bat <subcmd> [args...]`

`<skill-dir>` is the absolute path to this skill folder (shown at the top of this message when the skill fires — typically `~/.claude/skills/fastReader` or your platform's equivalent).

Subcommands: `load | toc | get | search` (plus optional `json` — see below). Run the wrapper with **no args** to see available subcommands and whether the `json` module is detected.

In the recipes below, `fastReader.sh` is shorthand — prepend `<skill-dir>/` (or use `fastReader.bat` on Windows).

## The histogram IS the TOC-chooser (the core idea)

`load` doesn't guess what kind of document you gave it. It runs every structural scanner in parallel and prints the count for each marker family: chapters / sections / subsections / blocks, and then `Bracket Depth 1…N`, `Tag Depth 1…N`, `Indent Depth 1…N`. **You read those counts and pick the scanner that matches this document's shape.**

- `Sections: 14` on a markdown plan? → `fastReader.sh toc <hash> --sections`.
- `Sections: 0` but `Tag Depth 5: 20` on an HTML page? → `fastReader.sh toc <hash> --tag-depth 5`.
- Both `Sections: 14` and `Bracket Depth 1: 37`? → do BOTH — one gives the narrative TOC, the other an inventory of every fenced code block.
- `Bracket Depth 1: 3159` on a 7 MB JSONL? → `fastReader.sh toc <hash> --bracket-depth 1 --limit 20` — one record per line.

Every `toc` row prints line range + child count + a preview. Pick the interesting one, `fastReader.sh load --line START COUNT` to slice it into its own hash, and recurse. Four commands takes you from "214 KB HTML file I've never seen" to "these are the 7 appender subtypes, `#popupappender` is the big one at lines 1428–1950" — measured ~4 KB of output total.

## The one-paragraph grammar

`load` → fastReader scans the file once and returns the marker-count histogram + a hash. You read the histogram and pick a scanner family. Use that hash with `toc <flag>` to see the real map. Pick an entry, use `get` to pull its full content, or use `load --line START COUNT` to carve out a sub-document with its own hash (for recursive drilling). Multi-file loads give you parallel hashes and one cross-search across all of them.

## Discovering commands without leaving the shell

Every subcommand exposes three help views — use these instead of guessing flags:

- `fastReader.sh <cmd> --help` — argparse flag reference.
- `fastReader.sh <cmd> --help-examples` — copy-paste recipes curated per subcommand.
- `fastReader.sh <cmd> --help-use-cases` — "user said X → run Y" trigger mapping.

Applies to `load`, `toc`, `get`, `search`. The `--help-*` flags **do not require** the subcommand's normal positional arguments — `fastReader.sh toc --help-examples` works with no hash.

## Optional `json` module — quick-json-reader integration

If the sister [quick-json-reader](https://github.com/RandyHaylor/quick-json-reader) skill is installed at `<parent-of-skill-dir>/quick-json-reader/` (or `FAST_READER_JSON_BIN` points at its binary), the wrapper auto-detects it and enables a `json` subcommand that pass-throughs to that binary:

```bash
fastReader.sh json file.json --search-vals error timeout
fastReader.sh json file.json --show-schema
fastReader.sh json file.json --exclude-fields-matching token password
fastReader.sh json file.json --search-keys user profile --output json
```

fastReader's own `--bracket-depth N` navigates JSON/JSONL structurally (where is it); quick-json-reader adds semantic extraction — value search, field filtering, schema inference, CSV/JSON output (what does it contain). They share the skills folder. When the binary isn't detected, `fastReader.sh` (no args) reports `json (NOT INSTALLED)` with an install hint — never a silent failure.

## Trigger patterns — when to use what

| User said | First call |
|---|---|
| "find what hooks.md says about SessionStart" | `fastReader.sh load hooks.md` → `fastReader.sh search SessionStart --manifests <hash>` |
| "summarize this 10k-line doc" | `fastReader.sh load doc.md` → `fastReader.sh toc <hash> --sections --show-line-range-count --sample-size 80 --end-sample-size 120` |
| "look at the event handlers in this Python file" | `fastReader.sh load file.py` → `fastReader.sh toc <hash> --indent-depth 1` |
| "what record types are in this Claude session?" | `fastReader.sh load session.jsonl` → `fastReader.sh toc <hash> --bracket-depth 1 --sample-size 80` |
| "read just this specific section" | `fastReader.sh get <hash> --section N` or `fastReader.sh load <file> --line START COUNT` |
| "search all my log files for errors" | `fastReader.sh load log1 log2 log3` → `fastReader.sh search error --manifests <h1> <h2> <h3>` |
| "we talked about X earlier" (session JSONL lost) | `fastReader.sh load ~/.claude/projects/<slug>/<session>.jsonl` → `fastReader.sh search "X" --manifests <hash>` |
| "deep JSON filter / schema" (quick-json-reader present) | `fastReader.sh json file.json --search-vals error` |

## Recipe book (copy-paste, prepend `<skill-dir>/` to each `fastReader.sh`)

### Recipe 1 — Scan an unfamiliar large file

```bash
fastReader.sh load big_doc.md
```
Output: chapters/sections/subsections counts, indentation/bracket/tag depth counts, block count, and the hash.

### Recipe 2 — Get a navigable TOC with size info and end-peek

```bash
fastReader.sh toc <hash> \
  --sections --show-line-range-count \
  --sample-size 80 --end-sample-size 120 --limit 0
```
Each row: `section 4  ln 668-2049 (1382)  ## Hook events` plus start preview and end preview. For a 10-section 2400-line file this costs ~1.5 KB. You see where the biggest sections are AND what they conclude with.

### Recipe 3 — Drill into a big section without loading the whole file

```bash
# First see a huge section in the TOC above. Say it spans line 668, 1382 lines.
fastReader.sh load big_doc.md --line 668 1382
# → produces a NEW hash for just those 1382 lines.
fastReader.sh toc <new_hash> \
  --subsections --show-line-range-count --sample-size 60 --end-sample-size 80
```
Line numbers re-zero to the slice. You can drill again recursively (slice the slice).

### Recipe 4 — Find what you want, with context

```bash
fastReader.sh search SessionStart --manifests <hash> --sample-size 80
```
Every hit returns: line number, preview, and "chapter X / section Y / subsection Z" breadcrumb with line numbers.

### Recipe 5 — Multi-file cross-search

```bash
fastReader.sh load doc1.md doc2.md doc3.md
# Compact table returns 3 hashes. Search all three at once:
fastReader.sh search "error code" --manifests <h1> <h2> <h3>
```
Zero-hit files say `0 hits`; skip them. High-hit files get drilled.

### Recipe 6 — Navigate code by indentation (Python, YAML, outlines)

```bash
fastReader.sh load some_module.py
fastReader.sh toc <hash> --indent-depth 0 --sample-size 80   # top-level defs/classes
fastReader.sh toc <hash> --indent-depth 1 --sample-size 80   # methods, inner scopes
```

### Recipe 7 — Navigate JSONL by record

```bash
fastReader.sh load session.jsonl
# Each JSONL line starts at bracket depth 1. Preview each record's first 120 chars.
fastReader.sh toc <hash> --bracket-depth 1 --sample-size 120 --limit 20
```

### Recipe 8 — Navigate HTML/XML

```bash
fastReader.sh load page.html
fastReader.sh toc <hash> --tag-depth 2 --sample-size 60
# → Direct children of <html>: <head>, <body>, etc.
```

### Recipe 9 — Find what a user remembers from an earlier session

When the user says "we talked about X" or "you said before" or "I told you earlier":

```bash
fastReader.sh load ~/.claude/projects/<project-slug>/<session-id>.jsonl
fastReader.sh search "X" --manifests <hash>
```
Do this BEFORE claiming you don't recall. Session JSONLs hold the real transcript.

### Recipe 10 — JSON semantic extraction (requires quick-json-reader)

```bash
fastReader.sh json big_api_response.json --search-vals user123 --exclude-fields-matching token --output json
fastReader.sh json config.json --show-schema
```

## Flag cheat sheet

| `toc` flag | Effect |
|---|---|
| `--sections` / `--chapters` / `--subsections` / `--blocks` / `--pages` | Pick which marker kind to list |
| `--indent-depth N` | Lines entering indent level N |
| `--bracket-depth N` | Positions entering JSON nesting level N |
| `--tag-depth N` | Balanced HTML/XML tags at level N |
| `--show-line-range-count` | Print `ln START-END (COUNT)` for each entry |
| `--sample-size N` | First N chars of each entry (default 30) |
| `--end-sample-size N` | Last N chars of each entry's span (default 0 = off) |
| `--limit N` | Max entries shown (default 15, 0 = no cap) |

| `load` flag | Effect |
|---|---|
| `--line START COUNT` | Ingest only lines START..START+COUNT-1 as a new hashed doc |
| `--search kw [kw...]` | Immediately search after load |
| `--sample-size N` | Search preview length (default 80) |
| `--exact` / `--case-sensitive` / `--all` | Search modifiers when paired with `--search` |

| `search` flag | Effect |
|---|---|
| `--manifests <h1> [h2 ...]` | REQUIRED. Which loaded hashes to search |
| `--exact` | Whole-word match (vs substring) |
| `--case-sensitive` | Default is case-insensitive |
| `--all` | All keywords must appear on same line (default: any match) |
| `--sample-size N` | Preview chars per hit (default 80) |

## INTEGRITY — the warning fastReader itself prints

This tool truncates aggressively. That's the feature. But it creates a real failure mode: a tidy 120-char end-preview can look authoritative even when the middle 1,300 lines contained the critical rule.

Rules of the road:

1. **After scanning, read in full before concluding.** If you identified a section, `fastReader.sh get <hash> --section N` it (or `fastReader.sh load --line START COUNT` to re-ingest). Previews are for navigation, NOT for final answers.
2. **If new terminology appeared in a preview, search for it.** A term glimpsed in an end-preview may appear elsewhere with different context. `fastReader.sh search <term> --manifests <hash>` before you draw a conclusion.
3. **Heed the high-ratio warning.** When a section spans ~10× the preview size or more, fastReader prints a `WARNING` line explicitly noting the end-preview is the LAST line of the block, NOT a summary. Respect it — `get` that section.
4. **Don't confuse "shape" with "content."** Tag/bracket/indent scanners give you structure. The actual rules/values live in the content. Always pull content for decisions that matter.

fastReader itself appends an `INTEGRITY NOTE` after every `toc` output. Follow it.

## What fastReader is NOT

- **Not a renderer** — use the optional `json` module (quick-json-reader) for JSON extraction/visualization, or pair with it for semantic work.
- **Not a web fetcher** — use Claude Code's WebFetch; pipe the parsed text through `load`.
- **Not a code understander** — it sees structure, not semantics. For "what does this function do" you still need to read the code.
- **Not a replacement for reading** — it's a scope-reducing pre-step. Always read in full once you've narrowed the target.

## Tiny mental model

```
LOAD   →   hash   →   TOC   →   pick an entry   →   GET or SLICE-LOAD   →   content
                                      ↓
                                   SEARCH (find, with breadcrumbs)
```

Ten files? Ten hashes in parallel from one `load`. Cross-search them as a group.

For a human-friendly walkthrough with live transcripts and the benchmark table, see `README.md` in this skill folder.

---

**If the user invoked this skill, assume they want you to use it for something.**
