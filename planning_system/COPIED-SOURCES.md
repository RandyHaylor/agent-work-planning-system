# Copied-in sources

Copied 2026-11-25 as our own code (decided: copy in, keep mostly intact, adapt only what's needed; no upstream updates expected).

| Our folder | Copied from | Commit |
|---|---|---|
| `fastreader/` | `~/ai_skills_agents_resources/ai-agent-fastReader/fastReader/` | 166e3dd |
| `quick_json_reader/` | `~/my_projects/quick-json-viewer-project/quick-json-reader/` (without .git, web-ui) | a0cb992 |
| `prompt_builder/` | `~/ai_skills_agents_resources/ai-rule-builder/` (whole tool, website included) | 1c9a830 |
| `local_client/carried_source_of_truth/` | `~/ai_skills_agents_resources/source-of-truth/` (`source_of_truth/` package, `install.py`, `tests/`) | d22d770 |

Imports (2026-11-27, modularity fix 4): inside `fastreader/`, `quick_json_reader/` and `prompt_builder/`, each tool's own modules import each other with relative imports (`from .scanner import ...`), not `planning_system.<tool>.`, so the folder can be dropped into another project (empty `__init__.py` added to `fastreader/` and `fastreader/commands/`, which were namespace packages). Import-linter contracts in `pyproject.toml` keep the three tools independent of each other and of the server. Their copied tests (`fastreader/test/`, `prompt_builder/tests/`) still use absolute imports. `fastreader/commands/json.py` no longer imports quick_json_reader: it takes any reader matching its own `JsonTextReader` protocol (the server injects quick_json_reader). Remaining ties to this project: `prompt_builder` imports `planning_system.contract` / `planning_system.errors` (Principal, NotFound); `fastreader/web.py`'s argparse `prog` names the module path.

`carried_source_of_truth/` is the raw copy; the build keeps only the capture side (harness adapter interface, Claude Code adapter, UserPromptSubmit/AskUserQuestion capture, local raw log, installer) and leaves out SoT's local requirements tree, per the approved quote-capture spec.
