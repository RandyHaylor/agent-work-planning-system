# Copied-in sources

Copied 2026-11-25 as our own code (decided: copy in, keep mostly intact, adapt only what's needed; no upstream updates expected).

| Our folder | Copied from | Commit |
|---|---|---|
| `fastreader/` | `~/ai_skills_agents_resources/ai-agent-fastReader/fastReader/` | 166e3dd |
| `quick_json_reader/` | `~/my_projects/quick-json-viewer-project/quick-json-reader/` (without .git, web-ui) | a0cb992 |
| `prompt_builder/` | `~/ai_skills_agents_resources/ai-rule-builder/` (whole tool, website included) | 1c9a830 |
| `local_client/carried_source_of_truth/` | `~/ai_skills_agents_resources/source-of-truth/` (`source_of_truth/` package, `install.py`, `tests/`) | d22d770 |

`carried_source_of_truth/` is the raw copy; the build keeps only the capture side (harness adapter interface, Claude Code adapter, UserPromptSubmit/AskUserQuestion capture, local raw log, installer) and leaves out SoT's local requirements tree, per the approved quote-capture spec.
