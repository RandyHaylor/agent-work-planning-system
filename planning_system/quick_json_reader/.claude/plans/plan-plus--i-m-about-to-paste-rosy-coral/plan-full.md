# fastReader — finalize self-documentation, add GitHub README, measure real token savings

## Context

The previous session (`quick-json-reader` → renamed `fastReaderRefactorAndJsonReader`, JSONL loaded as fastReader manifest `8544820e`, ~7 MB / ~8800 blocks) ran out of context while finishing a self-documentation feature for the fastReader skill:

- Added `--help-examples` and `--help-use-cases` flags on all four subcommands (`load`, `toc`, `get`, `search`), backed by a new `help_content.json`.
- Added `intercept_help_content_flags_before_argparse()` so those flags work without the normally-required positional args (e.g. `toc --help-examples` no longer errors for a missing hash).
- All 98 tests pass (verified this turn: `bash /tmp/run_fast_reader_tests_script.sh` → `98 passed in 0.14s`).

What was *not* finished:

1. **Exploratory use-case testing** of the new `--help-examples` / `--help-use-cases` UX across all four subcommands, to confirm the printed content is actually useful from an agent's point of view.
2. **Real, measured token-savings examples** — the SKILL.md claims numbers like "~500 tokens for a full structural map" and "under 2 KB of output" but those were estimates, not measured in this session.
3. **Expanded built-in help content** (more recipes / more trigger→command rows in `help_content.json`).
4. **Alignment of SKILL.md** with the new `--help-*` flags (SKILL.md currently does not mention them).
5. **A GitHub-flavored `README.md`** at `~/.claude/skills/fastReader/README.md` that can later become the public face of the repo. Do **not** `git init` or create a repo yet.

Goal of this change: leave fastReader in a state where (a) an agent discovering it can self-onboard entirely from `--help` + `--help-examples` + `--help-use-cases`, (b) a human browsing the folder on GitHub gets a compelling, verified-with-numbers README, and (c) SKILL.md, README.md, and the built-in help stay internally consistent.

## Critical files

Existing (read/modify):

- `~/.claude/skills/fastReader/cli.py` — already has the `--help-*` flags; may need small tweaks only.
- `~/.claude/skills/fastReader/help_content.json` — expand with more recipes + use-cases.
- `~/.claude/skills/fastReader/SKILL.md` — update to mention `--help-examples` / `--help-use-cases` + refresh perf numbers.
- `~/.claude/skills/fastReader/agent_instructions.json` — small pointer additions so the "Browse / Search" hints after `load` also mention `--help-examples`.
- `~/.claude/skills/fastReader/test/` — 98 existing tests must stay green; add a couple of tests for `--help-examples` / `--help-use-cases` behavior if missing.

New:

- `~/.claude/skills/fastReader/README.md` — GitHub-flavored, standalone.
- `/tmp/fastReader_token_measurements_script.sh` (or similar) — reproducible script that runs scenarios and measures output bytes so the numbers in README/SKILL are real.

## Plan (phased; each phase is small, reversible, and leaves tests green)

### Phase A — Inventory & baseline (read-only)

1. Re-run `bash /tmp/run_fast_reader_tests_script.sh` — confirm 98/98 still pass on a cold start.
2. Quick audit via fastReader itself on manifest `8544820e` (the prior session) to:
   - `search "help_content" --manifests 8544820e` to see what was discussed about recipe content.
   - `search "token" --manifests 8544820e` and `search "README" --manifests 8544820e` to recover any ideas/decisions the user made that aren't yet in code.
3. Read each of the four subcommand `--help`, `--help-examples`, `--help-use-cases` outputs end-to-end (write a small `/tmp/dump_all_fast_reader_help_outputs_script.sh` that invokes all 12 combinations and concatenates). Note gaps or weak examples.

### Phase B — Real token-savings measurements (multi-case, the "impressive" suite)

JSONL-only numbers are easy but not the most compelling story — JSONL is homogeneous. The real showcase is **large technical reference docs in HTML/XML and long Claude Code plan files**, where the bracket/tag/indent scanners surface code blocks, headers, and node structure in one pass.

Target files (pick one per category; record exact paths in the script):

1. **Large HTML reference doc** — e.g. a downloaded language/stdlib reference page (hundreds of KB of HTML with nested `<section>`, `<h1/2/3>`, `<pre><code>` blocks). If none on disk, use a saved copy of a sizeable docs page the user points at, or fall back to any large HTML under `~/` that `find` turns up.
2. **Large XML doc** — e.g. an API spec, sitemap, or configuration dump. Fall back to generating one from a real source if nothing suitable is on disk (confirm with user before generating).
3. **Original (non-stripped) Claude Code plan file** — search `~/.claude/plans/` for the largest plan that looks like an unmodified reference copy, not one of the user's trimmed working plans. If nothing qualifies, confirm with user which path to use.
4. **Markdown technical doc with embedded code blocks** — a code-reference markdown file if available; this is the "massive speed-up for reading code reference docs" case the user specifically called out.
5. **(Baseline for comparison) the 7 MB session JSONL** — still included as a single row, but framed as "even the homogeneous case saves X".

Write `/tmp/fastReader_token_measurements_script.sh` that, for each target file, runs and measures the stdout byte count of:

- **S1 — naïve read baseline:** `wc -c` on the file (proxy for "what `Read` would cost").
- **S2 — load only:** `fastReader.load <file>` (the compact structural summary + hash).
- **S3 — toc default section view:** `toc <hash> --sections --show-line-range-count --sample-size 80` (use the existing `--show-line-range-count` feature so readers see `ln START-END (COUNT)` for each entry).
- **S4 — toc with start+end previews + node ids + child counts (if those flags exist):** `toc <hash> --sections --show-line-range-count --sample-size 80 --end-sample-size 120 --limit 0`; also attempt `--show-node-id` / `--show-child-count` style flags if scanner.py already supports them — verify by reading `cli.py` in Phase A and include whichever exist.
- **S5 — structural scanner most relevant to that file type:**
  - HTML case: `toc <hash> --tag-depth 2 --sample-size 80 --show-line-range-count`.
  - XML case: `toc <hash> --tag-depth 1 --sample-size 80 --show-line-range-count`.
  - Plan file / markdown-with-code: `toc <hash> --bracket-depth 1 --sample-size 120` to surface fenced code blocks, plus `--sections` for headers.
  - Code-reference markdown: `toc <hash> --indent-depth 0 --sample-size 80` for structural outline.
- **S6 — slice-drill:** `load <file> --line START COUNT` on the biggest entry surfaced in S3, then `toc <new_hash> --subsections --show-line-range-count`.
- **S7 — targeted search:** one realistic keyword per file (e.g. `"Example"` for a reference doc, `"Implementation"` for a plan file).

Approximate tokens as `bytes / 4`. Emit a markdown table per file plus a roll-up table showing `scenario → bytes → approx-tokens → % of S1`. Replace every estimated number in README/SKILL with these measured figures, citing the target file and date.

Before running for real, read `cli.py` and `scanner.py` to confirm which of `--show-line-range-count`, node-id display, and child-count display actually exist today; if the user-referenced "show node ids" / "show child counts" aren't yet flags, note them in Phase C as candidate additions rather than pretending they exist.

### Phase C — Content: expand built-in help

Edit `help_content.json` only:

- `load.examples`: add (i) `--search` shortcut example with two keywords, (ii) a multi-file load showing the hash-per-file output shape expectation.
- `toc.examples`: add (i) a `--blocks` fallback example for files with no headers, (ii) a `--pages` example.
- `toc.use_cases`: add "'list the TODOs / WARNs in this file'" → tip to use `search` not `toc`, because those are not structural markers.
- `get.examples`: add `--chapter` usage and `--block` with line-range context.
- `search.examples`: add `--all` (AND) with 3 keywords; add mixed `--exact` + `--case-sensitive` combo.
- Add one top-level `"_shared"` hint printed verbatim: **"After `--help-examples` run `--help-use-cases` for the trigger→command cheat sheet; both are per-subcommand."**

Test: add `test_help_content_flags.py` covering:

- `toc --help-examples` exits 0, prints `Copy-paste examples for: fastReader.toc`, and does not require a manifest.
- `search --help-use-cases` exits 0 and contains `--manifests`.
- `load --help-examples` mentions `--line`.

### Phase D — Update SKILL.md

- Add a short section "**Discovering commands without leaving the shell**" documenting `--help`, `--help-examples`, `--help-use-cases` and that these are the canonical source — SKILL.md only summarizes.
- Replace the two estimated-token numbers in the opening paragraph with the **measured** numbers from Phase B (cite "measured against `<file>` on `<date>`").
- Add a one-liner in the "Tiny mental model" section pointing to README.md for the human-friendly walkthrough.

### Phase E — New `README.md` (GitHub-flavored)

Create `~/.claude/skills/fastReader/README.md`. Structure:

1. **Title + one-sentence pitch** — e.g. "Deterministic, structural pre-reader for LLM agents and humans. Turn 'open this 14 MB file' into five sub-kilobyte hops."
2. **Badges placeholder** (empty HTML comment block, no real badges yet since no repo).
3. **Why** — the token-cost problem in 2–3 sentences; show the Phase B measurement table.
4. **Install / use as a Claude Code skill** — **pre-repo phrasing**: "Copy the `fastReader/` folder into `~/.claude/skills/` (or any parent you like)." Show the `PYTHONPATH=<parent>` invocation pattern. No `git clone` line — the skill is pre-repo.
5. **Five-minute tour** — load → toc → drill → search, each step with a real copy-pasteable command and a truncated real output.
6. **Four scanners, one pass** — brief table: `--sections` / `--indent-depth` / `--bracket-depth` / `--tag-depth` with a one-line "good for" column.
7. **Self-documenting CLI** — call out `--help-examples` and `--help-use-cases` as first-class; one short example per subcommand.
8. **Integrity warnings** — the existing INTEGRITY block from SKILL.md, condensed.
9. **Token-savings benchmark** — paste the full Phase B table (and the script path `/tmp/...`) so the numbers are reproducible.
10. **What fastReader is NOT** — mirror SKILL.md.
11. **Contributing / status** — "Pre-repo. No issue tracker yet. File layout: `cli.py`, `scanner.py`, `help_content.json`, `SKILL.md`, tests under `test/`."
12. **License placeholder** — `TBD`.

Constraints:

- Pure GitHub-flavored Markdown; no HTML-only features.
- All code blocks use a language hint (```bash```, ```text```).
- Every number in the README must come from Phase B's script, not guessed.

### Phase F — Verification

- `bash /tmp/run_fast_reader_tests_script.sh` → 98 + new tests all green.
- Visual check of `README.md` by piping through `glow` if available, else `cat`, confirming headings render and tables align.
- Cross-check that each command shown in README actually executes (add a `/tmp/verify_fast_reader_readme_commands_script.sh` that runs each fenced `bash` block's first line against a tiny fixture file under `fastReader/test/fixtures/`).
- End on a diff summary of what changed.

## Verification checklist (end-to-end)

1. `bash /tmp/run_fast_reader_tests_script.sh` — tests green including new ones.
2. `PYTHONPATH=~/.claude/skills python3 -m fastReader.toc --help-examples` — still works.
3. `PYTHONPATH=~/.claude/skills python3 -m fastReader.toc --help-use-cases` — still works.
4. `bash /tmp/fastReader_token_measurements_script.sh` — produces the table consumed by README/SKILL.
5. `bash /tmp/verify_fast_reader_readme_commands_script.sh` — every command in README runs on a fixture.
6. `git status` shows exactly: modified `cli.py` (if touched), `help_content.json`, `agent_instructions.json`, `SKILL.md`, new `README.md`, new `test_help_content_flags.py`. Nothing else.
7. Explicitly **no** `git init`, no commit, no push in this plan.

## Decisions captured from the user

- **Benchmark suite = multi-case** (HTML, XML, large original Claude Code plan file, code-reference markdown, plus the JSONL as a baseline row). JSONL alone is too homogeneous to be the headline.
- **README install phrasing = pre-repo "copy the folder"**; no `git clone` lines.
- **Use the new display features** in every benchmark where they exist: `--show-line-range-count`, node ids, child counts. Phase A must confirm which of these are already implemented in `cli.py` / `scanner.py`; any that were discussed but not built are candidates for Phase C additions, not silently skipped.
