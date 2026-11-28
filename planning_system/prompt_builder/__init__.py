"""prompt_builder: our copy of ai-rule-builder plus per-role guidance (spec: planning/05-spec-prompt-builder.md).

Public interface: the types and interfaces in `guidance_types` / `guidance_interface`
(served over HTTP by server.http_api.guidance_routes; this module has no HTTP code), and (for the CLI's guidance editor) `GuidanceEditor` and
`resolve_user_rule_builder_folder`. Children (`role_guidance`, `guidance_editor`) stay private.
"""
from .ai_prompt_builder.rule_catalog import resolve_user_rule_builder_folder
from .guidance_editor import GuidanceEditor

__all__ = ["GuidanceEditor", "resolve_user_rule_builder_folder"]
