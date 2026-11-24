# Spec: references + reader

APPROVED by the user, 2026-11-23, in Slack: "approve references + reader (draft 2)". Decisions and the user's words are in `05-module-specs.md` ("Phase 2: references", "Reader direction change"). Answers folded in: Node is a requirement; the DuckDuckGo scraper stays and agents are encouraged to use it, and a reference can only be registered by pulling the URL up through the reader (prompting and tooling must say so); the two tools are copied in as our own independent modules (not "vendored"), loosely coupled, evolved as the app needs.

## 1. Copied-in reader modules (kept mostly intact)

```
fastReader/                 our copy of ai-agent-fastReader (source repo and commit noted once)
                            scanners, toc, get, search, slicing (load --line), help menus (--help-examples,
                            --help-use-cases), its 108 tests: all kept
quick_json_reader/          our copy of quick-json-reader (JavaScript, run with Node), with its 25 tests and SKILL.md
```

**Only these change (adaptations):**

| fastReader part | Today | Adapted to |
|---|---|---|
| `cache.py` (save/load text + manifest under `~/.fastReader`) | files keyed by 8-char hash | an adapter onto the server's **temp cache store**, per agent, full SHA-256 |
| `load` of a file or URL | reads local path; `web.py` fetch | takes text produced by **document_extraction** (fixes the HTML, encoding, PDF problems); Word via a new docx strategy |
| `web.py search` (DuckDuckGo) | writes `/tmp` file | result loaded into the agent's temp cache like any document |
| `/tmp` output paths, global dirs | shared | per-agent, in the store |
| quick-json-reader pass-through | exec of a sibling binary | called on cached JSON text; results reported with line ranges of the stored text so they can be cited |
| (new) cite | n/a | `cite(cache_id, start_line, end_line)` moves the item into references |

Everything else (scanner logic, TOC options, get, search options, slicing, help text, tests) is untouched.

## 2. How agents use it

The server exposes the reader's commands as read commands over HTTPS. The thin CLI passes them through, so agents keep fastReader's command shape and help menus:

```
load <url | uploaded file | web-search terms> [--strategy NAME] [--search ...] [--line START COUNT]
                                                   -> cache id(s) + TOC + the extraction strategy used
                                                   (agent picks the strategy, or the fallback order picks; output says which)
toc <cache id> [same options as today]
get <cache id> --section N ...
search <terms> --manifests <ids...> [--exact --all --case-sensitive]
json <cache id> [quick-json-reader flags]
cite <cache id> <start line> <end line>                                            -> reference id
```

Local files (Word, PDF, ...): the CLI or local client uploads the bytes, because the server can't see the agent's disk.

## 3. Stores and types

```
temp_cache store        per agent; visible to that agent + admin; wiped freely; TTL purge
references store        permanent; Reference = one fixed item: id, origin, text, sha256, metadata, owner, superseded_by
Citation                reference id + start line + end line
```

`cite` keeps the item's ID when it moves it, so anything holding the ID still works. Identical content (same hash) reuses the stored copy. Loading a URL always fetches live.

## 4. ReferenceLibrary (permanent references only)

```
get(ref_id, follow_superseded=True)      read_lines(ref_id, start, end)
store_user_exchange(...)                 store_proposal_response(...)
store_node_text(text, node_id, replaces=None)
render(citation)                         supersede(old_id, new_id)
```

Reading the cache (load, toc, get, search, json) belongs to the copied-in reader (fastReader), not here. You can also load a stored reference into the reader to browse it with toc/search.

## Answered (user)

1. quick-json-reader stays JavaScript; Node is a server requirement.
2. The DuckDuckGo scraper stays as is and agents are encouraged to use it.
3. Plain copies we own and modify directly; no upstream updates expected.
