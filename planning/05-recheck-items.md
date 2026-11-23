# Module recheck against the commandments (agent review, 2026-11-23)

NOT APPROVED. An agent rechecked module tree v4 and the round 4/5 decisions against "Module design" in `process-levels.md`. Each item is for the user to review one at a time after the walkthrough. It did not read the old server code, so items 4 and 13 need checking against it.

1. **Tree text is stale.** `operations_tooling` still listed; `commands/`, `storage/`, `http_api/` mis-indented under `document_reader/`; `references` is prose, not modules. Option: redraw the tree.
2. **references: no children listed; several reasons to change** (versions, citations, rendering, supersession, origin policies, temp cache TTL/promotion/purge, two ingestion paths). Option: nest `text_versions/`, `citations/`, `origin_policies/` (strategy per origin), `fetch_cache/`, `ingestion/`, plus its ports.
3. **storage contradicts the merge.** Quote and source stores should become one `postgres_reference_store`; missing blob store, `migrations/` (yoyo), Postgres unit of work. Each store implements one port.
4. **project_tree placement.** `node_claimer` may be a pass-through over one SKIP LOCKED query; `node_state_views` (reads) changes for different reasons than the editors; content version history overlaps references' versions. Options: content reuses references' immutable versions, or state why two version systems exist.
5. **commands: unit of work needs a domain port** with a storage implementation; flat command list will grow to dozens. Option: nest only by shared mechanics, never by subject.
6. **Reads have no module.** Add `queries/` beside `commands/` (one class per query, same authorizer).
7. **Nothing connects references to document_reader** on the server. Option: a small `reference_reading` query module.
8. **document_extraction:** no file for the pipeline; detection mixed with charset decoding. Option: `extraction_pipeline.py` and a separate `text_decoding.py`.
9. **Failure markers need a written owner:** HTTP-level markers in the fetcher, content-level checks in quality checks.
10. **tree_export mixes levels:** split `subtree_renderer` from a small generic `atomic_file_writer`.
11. **database_backup:** dump, encryption, retention, restore change for different reasons; "task done" trigger couples it to commands. Option: nest the four; commands raise an event a backup scheduler listens to.
12. **Missing: composition root (wiring adapters into ports) and server configuration** (TTL, harness config, TLS).
13. **authentication:** if the carried admin session store keeps sessions itself, that's storage in the domain. Option: session policy in domain, store behind the credential storage port.
14. **api_client (approved in walkthrough):** may be shallow or huge, and may duplicate the OpenAPI-generated client from the CLI spike. Options: generate the client from OpenAPI and use it everywhere incl. local_client, or drop api_client for the generated one.
15. **cli:** generator file disappears if a library wins the spike; the admin login window has no home. Option: shared `admin_login` client module.
16. **web_ui pages by subject** (approval, escalation pages treat queues as types). Option: one state-filtered node list page, a node detail page, a login page.
17. **local_client flat, several reasons to change.** Option: nest `quote_capture/`, `review_worker/`, `harness_adapters/` (per harness: a capture hook strategy and a session runner strategy), `client_credentials`; use the API client.

Fine as drafted: access, context_assembly, document_reader internals, http_api protocol files.
