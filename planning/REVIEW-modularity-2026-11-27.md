# Modularity review: planning_system/ (2026-11-27)

Read-only review against CLAUDE.md design rules and `planning/process-levels.md` "Module design". Import map built by an AST scan of every `.py` under `planning_system/` (copied tools scanned separately). Suite run: `uv run --extra test python -m pytest -q tests/planning_system planning_system/prompt_builder/tests planning_system/fastreader/test` -> **881 passed, 2 skipped, 12.5 s**. The Postgres tests (`tests/planning_system/storage/`, part of `bootstrap/test_bootstrap_contract.py`) need a database; everything else runs on fakes.

## Verdict

The code is in good shape for modularity. The top-level package graph has no cycles, `document_extraction` imports nothing from the project, every domain module has an interface ABC, ports, a fake and contract tests, and storage depends on domain ports rather than the reverse. The weak spots are at the seams. (1) Two routers live in the wrong layer and make cycles: `server/domain/references/http_routes.py` imports `server.commands` and `server.http_api`, and the copied `prompt_builder/http_routes.py` imports `server.http_api`. (2) Seven of the nine domain packages have no public `__init__` surface, so every caller reaches into private files (`reader_service.numbered`, `citation_format.cites`, `types.TAKEN`, ...). (3) Modules that are generic enough to reuse are tied to this project in small ways: `contract.Invalid`, `configuration`, repo-relative default paths, and absolute `planning_system.` imports inside the copied tools. (4) `domain/references` is the one grab-bag (16 files: reader facade, ingestion, temp cache, citation syntax, line mapping, a fastReader cache adapter and an HTTP router). (5) One SLAP offender: `ClaudeCodeReviewerSessionHandleViaResume.send_prompt_and_await_response` (128 lines). None of this blocks work; fixes 1 to 4 below are cheap and are the ones that matter for "usable in other solutions".

## Per-package tables

Legend: Self = imports only what it should; Iso = interface + fake + tests runnable without Postgres/network/models; Reuse = liftable as-is.

### Top level

| Package | Self-contained | Isolated tests | Reusable | Issues |
|---|---|---|---|---|
| `contract.py` | Yes (stdlib only) | n/a | Tied: shared by all | Mixes two things: `Principal`/`ROLES` (planning auth) and the generic `DomainError` family. Generic modules (model_calls, configuration) import it only for `Invalid`. |
| `configuration/` | Imports `contract` only (5 files, for `Invalid`) | Yes | Almost: swap `contract.Invalid` for its own `ConfigError` | Fine otherwise. |
| `model_calls/` | Imports `configuration`, `contract` (`endpoint_factory.py:14-15`) | Yes (`FakeOneShotModelCall`, httpx transport injection, contract test) | Close | `endpoint_factory.py:22` default path `parents[2]/"config"/"model_endpoints.json"` is repo-relative; `Invalid` from contract; env var name `PLANNING_MODEL_ENDPOINTS_FILE`. Core (`interface`, `types`, `openai_compatible_chat_call`) is already standalone. |
| `document_extraction/` | Yes: zero project imports | Yes | **Yes, as-is** | Best package in the tree. Nested strategy/decoder/normalizer/fallback children each with `__all__`. |
| `api_client/` | Imports `contract` (`http_transport.py:8`, `fakes.py:23`) | Yes | No (it is this server's client) | `fakes.py` is 530 lines; `_build_routes` (`fakes.py:138`, 54 lines) is a hand-built fake server. Acceptable but heavy; see fix 9. |
| `admin_login/` | `api_client`, `contract` | Yes | No (project-specific) | Fine. |
| `cli/` | `admin_login`, `api_client`, `contract`, `local_client`, `prompt_builder` | Yes (`CliDependencies` injected) | No | Reaches into children: `argument_mappers.py:9` and `fakes.py:12` import `local_client.task_runner`; `entry_point.py:75` imports `prompt_builder.ai_prompt_builder.rule_catalog`; `entry_point.py:93-96` import `api_client.client_settings`, `local_client.client_credentials`, `local_client.client_paths`. CLI is the composition root, so wiring is fine there, but `argument_mappers` is not wiring. |
| `local_client/` | `api_client`, `contract`, `model_calls` | Yes (fakes per child; facade `local_client.py` delegates) | Parts: `review_mode/sentence_splitter.py`, `quote_capture/jsonl_exchange_cache.py`, `harness_adapters/claude_code/*` | Parent is a facade over 6 children; `build_local_client` (`local_client.py:57-87`) is composition, fine. See harness/pi notes below. |
| `server/` | `configuration`, `contract`, `document_extraction`, `fastreader`, `prompt_builder`, `quick_json_reader` | Mostly (Postgres only for storage) | No (it is the app) | Internal layering issues below. |
| `fastreader/` (copied) | Imports `quick_json_reader` (`commands/json.py:10`) | Yes (own tests) | Was standalone upstream; now tied by absolute `planning_system.fastreader.` imports everywhere and by the quick_json_reader import | Fix 4. |
| `quick_json_reader/` (copied) | Yes (only itself) | Yes | Tied only by absolute `planning_system.quick_json_reader.` imports | Fix 4. |
| `prompt_builder/` (copied) | **Imports `server.http_api.dependencies`** (`http_routes.py:15`) and `contract` (`http_routes.py:13`, `fakes.py:10`, `role_guidance/__init__.py:9`) | Yes | Was standalone; now tied to the server | Cycle `server -> prompt_builder -> server` (composition.py:22 imports `prompt_builder.http_routes`). Fix 1. |

### server/ (nested)

| Module | Self-contained | Isolated tests | Reusable | Issues |
|---|---|---|---|---|
| `domain/access` | Yes | Yes (contract test) | No | No package `__init__` surface; `principal.py` just re-exports `contract.Principal`. |
| `domain/authentication` | -> `domain/access.types` | Yes | `password_hashing.py`, `token_hashing.py` generic | No `__init__` surface. |
| `domain/agent_registry` | Yes | Yes | No | Fine. No `__init__` surface. |
| `domain/project_tree` | -> `references.interface`, `references.citation_format.cites` (`citing_nodes.py:4`) | Yes | No | No `__init__` surface. |
| `domain/context_assembly` | -> `project_tree`, `references` (via `ports.py`, good) | Yes | No | Fine. |
| `domain/task_assignment` | -> `agent_registry`, `authentication`, `project_tree` via `ports.py` | Yes | No | Fine; `types.py:4-5` pulls `CredentialId`, `Node` from their private `types`. |
| `domain/citation_enforcement` | -> `references` (`citation_checker.py:8-10`, `claim_policy.py:8`, `title_rules.py:4`) | Yes | No | Has `__all__`. Depends on citation syntax living inside `references` (fix 5). |
| `domain/content_review` | -> `references.citing_and_rendering.slice_lines`, `citation_format`, `types` | Yes | No | Has `__all__`. Same citation-syntax dependency. |
| `domain/references` | -> **`server.commands`, `server.http_api`** (`http_routes.py:11-14`), `fastreader` internals (`reader_cache_adapter.py:12-15`, `reader_service.py:10-15`), `quick_json_reader`, `document_extraction.extraction_types` | Yes (fakes + `reader_cache_adapter_fakes.py`) | `line_range_mapping.py` and `citation_format.py` are generic | **Grab-bag (16 files)** and a layer violation. `__init__.py` is a docstring only, so every caller imports private files. Fixes 1, 2, 5. |
| `commands/` | -> every domain package's private files; -> `storage.storage.Stores`, `storage.engine_setup.TransactionsInterface` (`command_runner.py:9`) | Yes (`commands/fakes.py` builds in-memory stores) | No | Command pattern, one class per file: good. `services.py:10-32` imports 11 concrete `*Service` classes; that is composition living in the command layer (fix 6). `request_authorizer.py:11-12` reaches into `content_review.types.TAKEN` and `references.citation_format`. |
| `http_api/` | -> `commands.command_runner`, `authentication.interface`, `references.citation_format` (`response_shapes.py:7`) | Yes (contract test, TestClient) | No | Fine apart from being imported by domain (fix 1). |
| `storage/` | -> domain `ports` and `types` (correct direction) | Contract tests need Postgres; fakes re-export domain in-memory stores | No | Correct dependency inversion. `fakes.py` imports in-memory stores from each domain's `fakes.py`, fine. |
| `adapters/*` | -> `domain/references.source_fetcher_port`, `document_extraction.extraction_types`, `fastreader.web` (`ddg_result_parser.py:9`) | Yes | `http_source_fetcher` near-generic | Fine. |
| `bootstrap/` | -> `storage`, `authentication.password_hashing` | Yes (Postgres for one test) | No | Fine. |
| `composition.py` | Imports everything (it is the root) | n/a | n/a | Fine; 147 lines, steps at one level. |

### local_client/ (nested)

| Module | Self | Iso | Reuse | Issues |
|---|---|---|---|---|
| `client_credentials` | Yes | Yes | Yes | Fine. |
| `task_runner` | -> `api_client`, `api_client.types` | Yes | No | Fine. |
| `review_worker` | Yes | Yes | No | Fine. |
| `quote_capture` | -> `api_client`, `contract` | Yes | `jsonl_exchange_cache`, `raw_input_log_*` generic | `raw_input_log_reader.py:2` imports `contract` for an error type only. |
| `review_mode` | -> `api_client`, `contract`, `model_calls` | Yes (contract test; one live test is skipped without a model) | `sentence_splitter.py` (pysbd wrapper, 19 lines), `verdict_parser.py` | `sentence_splitter.py` is labelled "Private" but is the most reusable piece; fine to leave private, lift when needed. |
| `review_mode/reviewer_backends` | -> `model_calls` | Yes (fakes, fake pi process) | No | `pi_backend.py:30` repo-relative `parents[4]/"tools"/"pi"` default (parked module, low priority). |
| `harness_adapters/claude_code` | Yes | Partly: subprocess code tested via fakes, not verified line by line | Yes in principle (Claude Code hooks are generic) | `ai_cli_adapter_claude_code.py:146-274` `send_prompt_and_await_response` is 128 lines mixing subprocess launch, thread setup, deadline/heartbeat loop and result fallback (SLAP; fix 7). `claude_cli_get_recent_agent_messages.py` is 611 lines: a hook script with argparse, transcript parsing and output in one file (fix 8). |

## Top 10 fixes (ranked by impact / effort)

| # | Fix | Impact | Effort | Files |
|---|---|---|---|---|
| 1 | **Move the two routers out of layers that must not know HTTP.** Move `server/domain/references/http_routes.py` to `server/http_api/reference_routes.py` (update `config/server.json:14` and the two tests that name it). Move `prompt_builder/http_routes.py` to `server/http_api/guidance_routes.py`, so the copied tool no longer imports `server.http_api.dependencies`. Removes both cycles (`domain/references -> commands -> domain/references`, `server -> prompt_builder -> server`). | High | Low | `server/domain/references/http_routes.py:11-14`, `prompt_builder/http_routes.py:13-15`, `server/composition.py:22`, `config/server.json:14`, `tests/planning_system/http_api/test_http_api_contract.py:33`, `tests/planning_system/end_to_end/test_end_to_end_in_process.py:27` |
| 2 | **Give every domain package a public `__init__` with `__all__`** (interface, types, constants, fake, service class) and import only from it outside the package. Today `references/__init__.py` is a docstring; `access`, `authentication`, `agent_registry`, `project_tree`, `context_assembly`, `task_assignment` have none either. Add an import-linter contract (`importlinter` "forbidden"/"layers") so it stays that way. | High | Low-Med | `server/domain/*/__init__.py`; callers in `server/commands/services.py`, `request_authorizer.py`, `read_reference_lines.py:10-11`, `storage/*.py`, `http_api/response_shapes.py:7` |
| 3 | **Split `contract.py`**: keep `Principal`/`ROLES` in contract (or `domain/access`); move `DomainError/NotFound/Forbidden/Invalid/Conflict` to a tiny `planning_system/errors.py`. Then give `configuration` and `model_calls` their own error types (`ConfigError`, `ModelEndpointError`) that the HTTP error mapper or caller translates. That makes both liftable. | Med-High | Low | `contract.py`, `configuration/*.py` (5 imports), `model_calls/endpoint_factory.py:15`, `server/http_api/error_mapping.py` |
| 4 | **Use relative imports inside copied tools** (`fastreader`, `quick_json_reader`, `prompt_builder`) so they can be dropped into another project unchanged; inject the JSON reader into `fastreader/commands/json.py` via its own small protocol instead of importing `planning_system.quick_json_reader`. | Med | Low (mechanical) | `fastreader/**` (~25 imports), `fastreader/commands/json.py:10`, `quick_json_reader/**`, `prompt_builder/**` |
| 5 | **Break up `domain/references`** into nested children with one public face: `citation_syntax/` (`citation_format.py`, `slice_lines` from `citing_and_rendering.py`), `line_range_mapping` (standalone, pure difflib), `reader/` (`reader_service.py`, `reader_cache_adapter*.py`, owns all fastReader/quick-json coupling), `temp_cache/`, `ingestion/`, and the library itself. `citation_enforcement`, `content_review`, `project_tree`, `http_api` then depend on `citation_syntax` only, not on the whole reference library. | Med-High | Med | `server/domain/references/*`, importers listed in the dependency map |
| 6 | **Move `DomainServicesFactory`/`DomainSettings`/`SystemClock` out of `commands/services.py` into `server/composition.py` (or `server/domain_wiring.py`).** Commands should see only `Services` (interfaces). Today the command layer imports 11 concrete classes. Also type `DomainSettings.source_fetcher/document_extractor/json_reader/clock` with their ports instead of `Any` (`services.py:68-72`). | Med | Low | `server/commands/services.py:10-32,64-100`, `server/composition.py`, `server/commands/fakes.py` |
| 7 | **SLAP split of `send_prompt_and_await_response`** into `_launch(command, prompt)`, `_start_pipe_readers(process)`, `_await_result(queue, deadline)` (the heartbeat/deadline loop as a small class), `_result_or_fallback(...)`. Then the loop is unit-testable without a subprocess. | Med | Low | `local_client/harness_adapters/claude_code/ai_cli_adapter_claude_code.py:146-274` |
| 8 | **Split `claude_cli_get_recent_agent_messages.py` (611 lines)** into a pure `transcript_events.py` (parse/find/extract functions, no I/O) and a thin hook entry (`parse_args`, `read_hook_payload`, `emit_*`, `main`). The pure half is reusable by any Claude Code tool and testable on strings. | Med | Low | `local_client/harness_adapters/claude_code/claude_cli_get_recent_agent_messages.py:150-607` |
| 9 | **Stop `cli/argument_mappers.py` reaching into `local_client.task_runner`**: export `TaskStartRequest` from `local_client/__init__.py` (the facade already uses it) and import from there. Same for `cli/fakes.py:12`. Optionally expose `rule_catalog.resolve_user_rule_builder_folder` from `prompt_builder/__init__`. | Low-Med | Low | `cli/argument_mappers.py:9`, `cli/fakes.py:12`, `cli/entry_point.py:75`, `local_client/__init__.py` |
| 10 | **Remove repo-relative defaults from reusable modules**: `model_calls/endpoint_factory.py:22` (`parents[2]/config/...`) and `reviewer_backends/pi_backend.py:30` (`parents[4]/tools/pi`). Require the path from the caller (composition root / CLI passes `config/model_endpoints.json`). | Low-Med | Low | the two lines above, plus callers of `load_model_endpoints` |

Not ranked, worth noting: `api_client/fakes.py` (530 lines) and `commands/fakes.py:_allowed` (44 lines) re-implement a lot of real behaviour; if they drift, contract tests run against the fakes stop proving anything. Consider running the api_client contract tests against the real client over the in-process `TestClient` as well (may already exist in `end_to_end/`; not verified).

## Import-dependency map

Top level (arrows = "imports from"; no cycles at this level except via `prompt_builder`):

```
main            -> configuration
configuration   -> contract
model_calls     -> configuration, contract
document_extraction -> (nothing in project)
api_client      -> contract
admin_login     -> api_client, contract
local_client    -> api_client, contract, model_calls
cli             -> admin_login, api_client, contract, local_client, prompt_builder
server          -> configuration, contract, document_extraction, fastreader, prompt_builder, quick_json_reader
fastreader      -> quick_json_reader                      (commands/json.py:10)
quick_json_reader -> (nothing)
prompt_builder  -> contract, server.http_api              (http_routes.py:13-15)  <-- CYCLE with server
```

Inside `server/`:

```
composition         -> adapters/*, bootstrap, commands, http_api, storage, domain/{authentication,citation_enforcement,references}
http_api            -> commands.command_runner, domain/authentication.interface, domain/references.citation_format
commands            -> domain/{access,agent_registry,authentication,citation_enforcement,content_review,
                        context_assembly,project_tree,references,task_assignment} (mostly private files),
                       storage.storage.Stores, storage.engine_setup.TransactionsInterface
storage             -> domain/{agent_registry,authentication,content_review,project_tree,references} .ports/.types/.fakes
bootstrap           -> storage, domain/authentication.password_hashing
adapters/*          -> domain/references.source_fetcher_port, document_extraction.extraction_types, fastreader.web

domain/authentication      -> domain/access.types
domain/project_tree        -> domain/references (interface, citation_format)
domain/context_assembly    -> domain/project_tree, domain/references          (via ports.py)
domain/task_assignment     -> domain/agent_registry, domain/authentication, domain/project_tree (via ports.py)
domain/citation_enforcement-> domain/references (interface, citation_format, types)
domain/content_review      -> domain/references (citation_format, citing_and_rendering, types)
domain/references          -> http_api, commands  (http_routes.py)   <-- CYCLE with commands; layer violation
                              fastreader (manifest_codec, models, reader_cache_port, scanner, commands.*),
                              quick_json_reader, document_extraction (extraction_types, extraction_interface)
domain/access, domain/agent_registry -> (contract only)
```

Inside `local_client/`: facade `local_client.py` -> children (`task_runner`, `review_worker`, `review_mode`, `quote_capture`, `harness_adapters`, `client_credentials`, `client_paths`). Children do not import each other except `review_mode/reviewer_backends` (own children) and `quote_capture_bridge.py` (adapter between facade and `quote_capture`). External: `api_client`, `model_calls`, `contract`.

Third-party libraries are confined correctly: `sqlalchemy` only in `server/storage` and `server/bootstrap/database_creation.py`; `fastapi` only in `server/http_api`, `server/composition.py` and the misplaced `server/domain/references/http_routes.py`; `httpx` in `api_client`, `model_calls`, `server/adapters/http_source_fetcher`; `pysbd` only in `review_mode/sentence_splitter.py`.

## Not verified

- Whether every fake is exercised by the same contract test as its real implementation (spot-checked names only: `test_*_contract.py` exist for access, citation_enforcement, content_review, model_calls, review_mode, cli, http_api, storage, prompt_builder).
- Line-level review of `prompt_builder/ai_prompt_builder/`, `fastreader/` internals, and the migrations.
