# Phase B — fastReader token-savings benchmark

Date: 2026-04-23
Script: `/tmp/fastReader_token_measurements_script.sh` (+ `/tmp/fastReader_jsonl_s6_script.sh` for the JSONL slice-drill, since bracket-depth-1 rows on JSONL are single-line and have no `(COUNT)` to pick a "biggest entry" from).
Output dir: `/tmp/fastReader_bench/`
Token approximation: `tokens ≈ bytes / 4` (rounded). `% of S1` is `bytes / S1_bytes * 100`.

## Targets

| Tag    | Path                                                                                                                         | Size (bytes) |
|--------|------------------------------------------------------------------------------------------------------------------------------|-------------:|
| HTML   | /home/aikenyon/HE/psychojs/node_modules/log4javascript/docs/manual.html                                                      |      213,868 |
| PLAN   | /home/aikenyon/.claude/plans/mutable-pondering-pascal.md                                                                     |       49,379 |
| CODEMD | /home/aikenyon/enhanceclaude/ai-tools/xstate/api-reference.md                                                                |      257,396 |
| JSONL  | /home/aikenyon/.claude/projects/-home-aikenyon-my-projects-quick-json-viewer-project-quick-json-reader/8539d3f6-….jsonl       |    7,041,642 |

Manifest hashes produced by `fastReader.load`:
`HTML=c3bf1ebb`, `PLAN=d66092f1`, `CODEMD=0e034c5f`, `JSONL=8544820e`.

## Scenario key

- **S1** — `wc -c` of the raw file (proxy for what `Read` would cost).
- **S2** — `fastReader.load <file>` (compact structural summary + hash).
- **S3** — `toc <hash> --sections --show-line-range-count --sample-size 80`.
- **S4** — S3 + `--end-sample-size 120 --limit 0` (start+end previews, no cap).
- **S5** — file-type-specific structural scan (see each table for exact invocation).
- **S6** — slice-drill: `load <file> --line START COUNT` on the biggest entry from S3 (or S5 fallback), then `toc <new_hash> --subsections --show-line-range-count`. Reported as total bytes of the drill-load + drill-toc.
- **S7** — realistic keyword search via `fastReader.search <kw> --manifests <hash> --sample-size 80`.

---

## HTML — `manual.html` (213,868 B)

S5 command: `toc <hash> --tag-depth 2 --sample-size 80 --show-line-range-count`
S7 keyword: `Example`
S6 fallback: S3 (`--sections`) was empty for this HTML file, so biggest entry was picked from S5 tag-depth-2 output.

| Scenario | Bytes | Approx tokens | % of S1 |
|---------:|------:|--------------:|--------:|
| S1 | 213,868 | 53,467 | 100.000% |
| S2 |     766 |    192 |   0.358% |
| S3 |     551 |    138 |   0.258% |
| S4 |     551 |    138 |   0.258% |
| S5 |     896 |    224 |   0.419% |
| S6 |   1,298 |    325 |   0.607% |
| S7 |   1,180 |    295 |   0.552% |

Headline: **S2 load costs 0.36% of a naïve Read (≈99.64% savings).**

---

## PLAN — `mutable-pondering-pascal.md` (49,379 B)

S5a: `toc <hash> --sections --show-line-range-count`
S5b: `toc <hash> --bracket-depth 1 --sample-size 120`
S7 keyword: `Implementation`

| Scenario | Bytes | Approx tokens | % of S1 |
|---------:|------:|--------------:|--------:|
| S1 | 49,379 | 12,345 | 100.000% |
| S2 |    492 |    123 |   0.996% |
| S3 |  1,471 |    368 |   2.979% |
| S4 |  3,313 |    828 |   6.709% |
| S5a|  1,353 |    338 |   2.740% |
| S5b|  1,915 |    479 |   3.878% |
| S6 |  1,386 |    347 |   2.807% |
| S7 |  3,327 |    832 |   6.738% |

Headline: **S2 load costs 1.0% of a naïve Read (≈99.0% savings).**

---

## CODEMD — `xstate/api-reference.md` (257,396 B)

S5a: `toc <hash> --indent-depth 0 --sample-size 80 --show-line-range-count`
S5b: `toc <hash> --bracket-depth 1 --sample-size 120`
S7 keyword: `Example`

| Scenario | Bytes | Approx tokens | % of S1 |
|---------:|------:|--------------:|--------:|
| S1 | 257,396 | 64,349 | 100.000% |
| S2 |     642 |    161 |   0.249% |
| S3 |   1,306 |    327 |   0.507% |
| S4 |   2,581 |    645 |   1.003% |
| S5a|     551 |    138 |   0.214% |
| S5b|   1,594 |    399 |   0.619% |
| S6 |   2,074 |    519 |   0.806% |
| S7 |   3,165 |    791 |   1.230% |

Headline: **S2 load costs 0.25% of a naïve Read (≈99.75% savings).**

---

## JSONL — 7 MB session log (7,041,642 B)

S5 command: `toc <hash> --bracket-depth 1 --sample-size 120 --limit 20`
S7 keyword: `error`
S6 note: JSONL bracket-depth-1 rows are one-line-per-record (no `(COUNT)` children to rank), so the slice-drill target was chosen manually as `--line 1 200`. Recorded bytes = load-slice stdout + subsequent subsections toc.

| Scenario | Bytes | Approx tokens | % of S1 |
|---------:|------:|--------------:|--------:|
| S1 | 7,041,642 | 1,760,411 | 100.0000% |
| S2 |       672 |       168 |   0.0095% |
| S3 |       551 |       138 |   0.0078% |
| S4 |       551 |       138 |   0.0078% |
| S5 |     3,685 |       921 |   0.0523% |
| S6 |     1,138 |       285 |   0.0162% |
| S7 |    45,646 |    11,412 |   0.6482% |

Headline: **S2 load costs 0.0095% of a naïve Read (≈99.99% savings).**

Note: JSONL S3/S4 (`--sections`) returned the boilerplate footer only — `--sections` is not a meaningful scanner for JSONL. The real structural view for JSONL is S5 (`--bracket-depth 1`), which lists one record per line at ~0.05% of the raw cost. S7's comparatively large 46 KB reflects a broad keyword (`error`) across 8,792 JSONL records; narrower keywords would shrink it further.

---

## Roll-up — bytes per scenario per file

| Scenario                | HTML    | PLAN    | CODEMD   | JSONL       |
|-------------------------|--------:|--------:|---------:|------------:|
| S1 raw (wc -c)          | 213,868 | 49,379  | 257,396  | 7,041,642   |
| S2 load                 |     766 |    492  |     642  |       672   |
| S3 sections             |     551 |  1,471  |   1,306  |       551   |
| S4 sections + end-prev  |     551 |  3,313  |   2,581  |       551   |
| S5 / S5a                |     896 |  1,353  |     551  |     3,685   |
| S5b                     |       — |  1,915  |   1,594  |         —   |
| S6 slice-drill          |   1,298 |  1,386  |   2,074  |     1,138   |
| S7 keyword search       |   1,180 |  3,327  |   3,165  |    45,646   |

## Headline savings (S2 load vs. S1 Read)

| File   | S1 bytes   | S2 bytes | % of S1  | Savings   |
|--------|-----------:|---------:|---------:|----------:|
| HTML   |    213,868 |      766 |  0.358%  | **99.64%** |
| PLAN   |     49,379 |      492 |  0.996%  | **99.00%** |
| CODEMD |    257,396 |      642 |  0.249%  | **99.75%** |
| JSONL  |  7,041,642 |      672 |  0.0095% | **99.99%** |

Across all four target files, the initial `fastReader.load` step costs **≤1%** of what a naïve `Read` of the same file would cost, and every subsequent structural drill (S3–S6) stays within a few percent of S1 — with S6's targeted slice-drill coming in well under 1% even for the 257 KB code-reference markdown.

## The histogram IS the TOC-chooser (the feature, not a quirk)

The "empty `--sections` on HTML/JSONL" result in the tables above is not a weakness — it's the intended behavior. `fastReader.load` prints the full marker-count histogram across EVERY scanner family (chapters/sections/subsections, blocks, bracket-depth-1…N, tag-depth-1…N, indent-depth-1…N). The agent reads those counts and chooses the scanner family (or families) that matches the document's actual shape. No per-file-type configuration, no guessing.

### Live walkthrough 1 — HTML manual (no markdown sections; 214 KB)

`load` histogram (key rows): `Sections: 0`, `Tag Depth 5: 20`, `Tag Depth 6: 85`, `Bracket Depth 1: 87`, `Indent Depth 5: 228`.

→ Agent picks `--tag-depth 5` (20 entries = one-screen TOC).

```
tag_depth_5 9   ln 122-253 (132)  <div id="loggersappenderslayoutslevels">  (8 children)
tag_depth_5 12  ln 495-928 (434)  <div id="loggers">  (8 children)
tag_depth_5 13  ln 929-2396 (1468) <div id="appenders">  (7 children)  ← giant; INTEGRITY WARNING auto-fires
tag_depth_5 14  ln 2397-3033 (637) <div id="layouts">  (8 children)
```

Slice-load `--line 929 1468`, then `--tag-depth 2` on the slice → 7 appender subtypes (`#alertappender`, `#ajaxappender` 389 lines 12 children, `#popupappender` 523 lines 11 children, etc.) in 900 B.

Four commands, ~4.3 KB total, no preconceived knowledge of the doc's shape. ≈50× cheaper than reading the file.

### Live walkthrough 2 — Claude Code plan file (markdown with fenced code; 49 KB)

`load` histogram: `Chapters: 10`, `Sections: 14`, `Subsections: 22`, `Bracket Depth 1: 37`.

→ Agent picks `--sections` AND `--bracket-depth 1` for perpendicular views:
- `--sections` (14 entries, ~1.5 KB) → phase breakdown / narrative TOC.
- `--bracket-depth 1` (37 entries, ~4 KB) → inventory of every code/JSON/Python artifact in the doc with line range.

Two maps of the same 49 KB doc in ~6 KB combined. Raw Read gives neither view at any price — just a wall of text.

## Errors / anomalies

- None of the S1–S7 runs errored on the final pass.
- First-pass bug (now fixed): the hash-extraction regex greedily matched the filename UUID inside the JSONL path before reaching the real manifest hash printed in the `--manifests <HASH>` footer. Fixed by anchoring the regex to `(--manifests|--sections) <hash>`.
- `--sections` being "empty" on HTML/JSONL is NOT an error — it correctly reports those formats have no markdown-header markers, and the agent is expected to read the histogram and pick `--tag-depth` (HTML) or `--bracket-depth` (JSONL) instead.
- JSONL S6 required a manually chosen slice range since bracket-depth-1 output has no `(COUNT)` children ranking; documented above.
