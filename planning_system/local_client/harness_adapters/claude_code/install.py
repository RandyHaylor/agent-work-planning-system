"""Claude Code hook installer (planning system port of SoT install.py).

Registers this client's two capture hooks in Claude Code's user settings.json, idempotently:
  - UserPromptSubmit (matcher "*")            -> user_prompt_submit_hook
  - PostToolUse (matcher "AskUserQuestion")   -> post_tool_use_capture_askuserquestion_answers
Each hook runs `<this python> -m <module>`, so no wrapper scripts or copied install folder are needed (SoT's
copy-to-skills-dir, wrapper, PATH-stub and global-settings steps are dropped). Kept from SoT: load-or-init,
scrub stale entries for this tool (e.g. an older interpreter path), append, back up, write.

The settings path is injected; tests pass a temporary file and never touch the user's real settings.
"""
from __future__ import annotations

import datetime
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Optional

from planning_system.local_client.interface import HookInstallerPort

HOOK_PACKAGE = "planning_system.local_client.harness_adapters.claude_code"
USER_PROMPT_SUBMIT_MODULE = f"{HOOK_PACKAGE}.user_prompt_submit_hook"
ASKUSERQUESTION_MODULE = f"{HOOK_PACKAGE}.post_tool_use_capture_askuserquestion_answers"

# (hook event, matcher, module)
HOOKS: tuple[tuple[str, str, str], ...] = (
    ("UserPromptSubmit", "*", USER_PROMPT_SUBMIT_MODULE),
    ("PostToolUse", "AskUserQuestion", ASKUSERQUESTION_MODULE),
)


def default_settings_json_path() -> Path:
    return Path.home() / ".claude" / "settings.json"


def load_or_init_settings_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    content = path.read_text(encoding="utf-8").strip()
    return json.loads(content) if content else {}


def remove_stale_hook_entries(settings_data: dict, hook_event_name: str, module: str, current_command: str) -> int:
    """Remove entries that run `module` with a different command (e.g. another interpreter). Returns count."""
    hooks_root = settings_data.get("hooks")
    if not isinstance(hooks_root, dict) or not isinstance(hooks_root.get(hook_event_name), list):
        return 0
    removed_count = 0
    surviving_matcher_entries = []
    for matcher_entry in hooks_root[hook_event_name]:
        kept = []
        for hook_item in matcher_entry.get("hooks", []):
            command_text = hook_item.get("command", "")
            if module in command_text and command_text != current_command:
                removed_count += 1
                continue
            kept.append(hook_item)
        if kept:
            matcher_entry["hooks"] = kept
            surviving_matcher_entries.append(matcher_entry)
    if surviving_matcher_entries:
        hooks_root[hook_event_name] = surviving_matcher_entries
    else:
        hooks_root.pop(hook_event_name, None)
        if not hooks_root:
            settings_data.pop("hooks", None)
    return removed_count


def hook_command_present(settings_data: dict, hook_event_name: str, command: str) -> bool:
    return any(hook_item.get("command") == command
               for matcher_entry in settings_data.get("hooks", {}).get(hook_event_name, [])
               for hook_item in matcher_entry.get("hooks", []))


def append_hook_entry(settings_data: dict, hook_event_name: str, matcher: str, command: str) -> None:
    settings_data.setdefault("hooks", {}).setdefault(hook_event_name, []).append({
        "matcher": matcher,
        "hooks": [{"type": "command", "command": command}],
    })


def backup_file(path: Path) -> Optional[Path]:
    if not path.is_file():
        return None
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = path.with_name(f"{path.name}.bak.{timestamp}")
    shutil.copyfile(path, backup_path)
    return backup_path


def write_settings_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


class ClaudeCodeHookInstaller(HookInstallerPort):

    def __init__(self, settings_path: Optional[Path] = None, python_executable: Optional[str] = None):
        self._settings_path = Path(settings_path) if settings_path else default_settings_json_path()
        self._python = python_executable or sys.executable

    def command_for(self, module: str) -> str:
        return f'"{self._python}" -m {module}'

    def install(self) -> None:
        self.ensure_hook_entries()

    def ensure_hook_entries(self) -> bool:
        """Returns True if settings.json was changed (backed up first)."""
        settings_data = load_or_init_settings_json(self._settings_path)
        modified = False
        for event, matcher, module in HOOKS:
            command = self.command_for(module)
            if remove_stale_hook_entries(settings_data, event, module, command):
                modified = True
            if not hook_command_present(settings_data, event, command):
                append_hook_entry(settings_data, event, matcher, command)
                modified = True
        if modified:
            backup_file(self._settings_path)
            write_settings_json(self._settings_path, settings_data)
        return modified


def main() -> int:
    installer = ClaudeCodeHookInstaller()
    changed = installer.ensure_hook_entries()
    print(f"{'updated' if changed else 'already up to date'}: {default_settings_json_path()}")
    print("Start a NEW Claude Code session so the hooks load.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
