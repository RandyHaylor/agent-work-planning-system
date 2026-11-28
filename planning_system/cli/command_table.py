"""The `planning` command list (planning/05-spec-cli.md "Commands"), as data: one entry per line, one call each."""
from __future__ import annotations

from .types import (TARGET_API, TARGET_GUIDANCE_EDITOR, TARGET_HELP, TARGET_LOCAL, TARGET_LOGIN, Arg,
                    CommandSpec)

GUIDANCE_ROLES = ("admin", "planner", "worker")

NODE_ID = Arg("node_id", "node_id", "int")

COMMANDS: tuple[CommandSpec, ...] = (
    # Identity and credentials
    CommandSpec(("admin", "login"), TARGET_LOGIN, authenticated=False),
    CommandSpec(("admin", "logout"), TARGET_API, "end_admin_session"),
    CommandSpec(("me",), TARGET_API, "me"),
    CommandSpec(("credentials", "mint"), TARGET_API, "mint_credential", (
        Arg("--role", "role", required=True), Arg("--project", "project_id", "int", required=True),
        Arg("--scope", "scope_node_id", "int"), Arg("--agent", "agent_id", required=True))),
    CommandSpec(("credentials", "quote-key"), TARGET_API, "mint_quote_key",
                (Arg("--label", "install_label", required=True),), after="store_quote_key"),
    CommandSpec(("credentials", "revoke"), TARGET_API, "revoke_credential", (Arg("id", "credential_id"),)),
    CommandSpec(("credentials", "rotate"), TARGET_API, "rotate_credential", (Arg("id", "credential_id"),)),
    CommandSpec(("agents", "register"), TARGET_API, "register_agent", (
        Arg("agent_id", "agent_id"), Arg("--host", "host"), Arg("--platform", "platform"), Arg("--model", "model"),
        Arg("--path", "path"), Arg("--system", "system"), Arg("--url", "url")), mapper="drop_unset"),
    # Tree
    CommandSpec(("projects", "create"), TARGET_API, "create_project", (
        Arg("--title", "title", required=True), Arg("--summary", "context_summary", required=True))),
    CommandSpec(("nodes", "create"), TARGET_API, "create_node", (
        Arg("--parent", "parent_id", "int", required=True), Arg("--title", "title", required=True),
        Arg("--level", "level_label", required=True), Arg("--summary", "context_summary", required=True),
        Arg("--labels", "labels", "strs"), Arg("--depends-on", "depends_on", "ints"),
        Arg("--position", "position", "int"))),
    CommandSpec(("nodes", "list"), TARGET_API, "nodes_by_state", (
        Arg("--project", "project_id", "int", required=True), Arg("--state", "state", required=True))),
    CommandSpec(("nodes", "get"), TARGET_API, "get_node", (NODE_ID,)),
    CommandSpec(("nodes", "children"), TARGET_API, "children", (NODE_ID,)),
    CommandSpec(("nodes", "ancestors"), TARGET_API, "ancestors", (NODE_ID,)),
    CommandSpec(("nodes", "ready"), TARGET_API, "ready_children", (NODE_ID,)),
    CommandSpec(("nodes", "update"), TARGET_API, "update_node", (
        NODE_ID, Arg("--title", "title"), Arg("--summary", "context_summary"), Arg("--labels", "labels", "strs"),
        Arg("--depends-on", "depends_on", "ints")), mapper="drop_unset"),
    CommandSpec(("nodes", "move"), TARGET_API, "move_node", (
        NODE_ID, Arg("--parent", "new_parent_id", "int", required=True),
        Arg("--position", "position", "int", required=True))),
    CommandSpec(("nodes", "state"), TARGET_API, "set_state", (NODE_ID, Arg("state", "state"))),
    CommandSpec(("nodes", "context"), TARGET_API, "context", (NODE_ID,)),
    CommandSpec(("content", "add"), TARGET_API, "add_content", (
        NODE_ID, Arg("--text", "text"), Arg("--file", "file"), Arg("--tags", "tags", "strs")), mapper="text_or_file"),
    CommandSpec(("content", "replace"), TARGET_API, "replace_content", (
        NODE_ID, Arg("reference_id", "reference_id"), Arg("--text", "text"), Arg("--file", "file")),
        mapper="text_or_file"),
    CommandSpec(("supplementary", "create"), TARGET_API, "create_supplementary_task", (
        Arg("--kind", "kind", required=True), Arg("--title", "title", required=True),
        Arg("--summary", "context_summary", required=True)), mapper="own_task"),
    # Tasks (planner)
    CommandSpec(("task", "assign"), TARGET_API, "assign", (
        NODE_ID, Arg("--agent", "agent_id", required=True), Arg("--branch", "branch", required=True))),
    CommandSpec(("task", "start"), TARGET_LOCAL, "start_task", (
        NODE_ID, Arg("--agent", "agent_id", required=True), Arg("--token", "token", required=True),
        Arg("--dir", "working_directory", required=True), Arg("--role", "role"), Arg("--model", "model"),
        Arg("--allow-tools", "allowed_tools", "strs")),
        mapper="task_start_request"),
    CommandSpec(("task", "stop"), TARGET_LOCAL, "stop_task", (Arg("agent_id", "agent_id"),), authenticated=False),
    CommandSpec(("task", "list"), TARGET_LOCAL, "running_tasks", authenticated=False),
    CommandSpec(("review", "ask"), TARGET_LOCAL, "ask_reviewer", (
        Arg("question", "question"), Arg("--context", "context_paths", "strs")), authenticated=False),
    # Content reviews (05-spec-citation-enforcement-and-review.md "CLI"); serve runs under the review task's token
    CommandSpec(("review", "serve"), TARGET_LOCAL, "serve_reviews", (
        Arg("--project", "project_id", "int", required=True),
        Arg("--profile", "profile", help="reviewer profile from config/reviewer_profiles.json (default: local)"),
        Arg("--backend", "backend", help="overrides the profile: local_llm | claude_code"), Arg("--model", "model"),
        Arg("--granularity", "granularity", help="overrides the profile: per_sentence | bulk "
                                                 "(default per_sentence for local_llm, else bulk)"),
        Arg("--poll-seconds", "poll_seconds", "float", default=5.0), Arg("--once", "once", "flag"))),
    CommandSpec(("review", "list"), TARGET_API, "list_reviews", (
        Arg("--project", "project_id", "int", required=True),
        Arg("--status", "status", help="pending | taken | passed | failed | superseded"),
        Arg("--node", "node_id", "int"))),
    CommandSpec(("review", "show"), TARGET_API, "get_review", (Arg("review_id", "review_id"),)),
    # Reader
    CommandSpec(("load",), TARGET_API, "reader_load", (
        Arg("source", "source", "strs"), Arg("--search", "search_terms"), Arg("--strategy", "strategy"),
        Arg("--line-start", "line_start", "int"), Arg("--line-count", "line_count", "int")), mapper="load_source"),
    CommandSpec(("toc",), TARGET_API, "reader_toc", (Arg("id", "reader_id"),)),
    CommandSpec(("get",), TARGET_API, "reader_get", (
        Arg("id", "reader_id"), Arg("--section", "section"), Arg("--line-start", "line_start", "int"),
        Arg("--line-count", "line_count", "int")), mapper="drop_unset"),
    CommandSpec(("search",), TARGET_API, "reader_search", (Arg("terms", "terms"), Arg("--ids", "ids", "strs"))),
    CommandSpec(("json",), TARGET_API, "reader_json", (Arg("id", "reader_id"), Arg("flags", "flags", "remainder"))),
    CommandSpec(("lines",), TARGET_API, "reader_lines", (
        Arg("id", "reader_id"), Arg("start", "start", "int"), Arg("end", "end", "int"))),
    CommandSpec(("cite",), TARGET_API, "reader_cite", (
        Arg("id", "reader_id"), Arg("start", "start_line", "int"), Arg("end", "end_line", "int"))),
    CommandSpec(("cite-exchange",), TARGET_LOCAL, "cite_exchange", (Arg("local_id", "local_exchange_id"),),
                authenticated=False),
    CommandSpec(("help",), TARGET_HELP, arguments=(Arg("command", "command", "strs"),), authenticated=False),
    # References
    CommandSpec(("references", "get"), TARGET_API, "get_reference", (Arg("id", "reference_id"),)),
    CommandSpec(("references", "lines"), TARGET_API, "reference_lines", (
        Arg("id", "reference_id"), Arg("--start", "start", "int"), Arg("--end", "end", "int"))),
    CommandSpec(("references", "render"), TARGET_API, "render_citation", (Arg("citation", "citation"),)),
    # Guidance (one subcommand per role, so the cli never branches on a role)
    *(CommandSpec(("guidance", role), TARGET_API, "guidance", fixed={"role": role}) for role in GUIDANCE_ROLES),
    CommandSpec(("guidance", "templates"), TARGET_API, "guidance_templates"),
    CommandSpec(("guidance", "rules"), TARGET_API, "guidance_rules"),
    CommandSpec(("guidance-editor",), TARGET_GUIDANCE_EDITOR, authenticated=False),
    # Local client setup
    CommandSpec(("client", "install-hooks"), TARGET_LOCAL, "install_hooks", authenticated=False),
    CommandSpec(("client", "exchanges"), TARGET_LOCAL, "list_exchanges", (Arg("--last", "last", "int", default=20),),
                authenticated=False),
)
