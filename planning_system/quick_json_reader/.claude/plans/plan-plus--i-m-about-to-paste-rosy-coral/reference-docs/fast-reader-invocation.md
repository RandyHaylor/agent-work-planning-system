# fastReader invocation reference

Skill lives at `/home/aikenyon/.claude/skills/fastReader/`.
Parent for PYTHONPATH: `/home/aikenyon/.claude/skills`.

## Preferred invocation (always via /tmp script — hook blocks chained commands)

Write a short `/tmp/<verbose_name>_script.sh` file for anything with env vars, pipes, or multiple commands. Example:

```bash
#!/bin/bash
export PYTHONPATH=/home/aikenyon/.claude/skills
python3 -m fastReader.toc <hash> --sections --show-line-range-count --sample-size 80
```

Then `bash /tmp/<verbose_name>_script.sh`.

## Subcommands and known-good flags (as of 2026-04-23, pre-Phase-A verification)

- `fastReader.load <file1> [file2 ...] [--line START COUNT] [--search kw...] [--sample-size N] [--help-examples] [--help-use-cases]`
- `fastReader.toc <hash> [--chapters|--sections|--subsections|--pages|--blocks] [--indent-depth N] [--bracket-depth N] [--tag-depth N] [--sample-size N] [--end-sample-size N] [--limit N] [--show-line-range-count] [--help-examples] [--help-use-cases]`
- `fastReader.get <hash> [--chapter N|--section N|--subsection N|--page N|--block N] [--help-examples] [--help-use-cases]`
- `fastReader.search <kw...> --manifests <hash> [...] [--exact] [--case-sensitive] [--all] [--sample-size N] [--help-examples] [--help-use-cases]`

Node-id / child-count display flags: UNVERIFIED — Phase A must check `cli.py` and `scanner.py`.

## Prior session manifest (already loaded this session)

`8544820e` → `/home/aikenyon/.claude/projects/-home-aikenyon-my-projects-quick-json-viewer-project-quick-json-reader/8539d3f6-21f1-421c-bef6-a4a7970c8b2f.jsonl` (≈7 MB, ≈8792 blocks).

## Test runner

`bash /tmp/run_fast_reader_tests_script.sh` currently prints `98 passed in 0.14s`. Keep green.
