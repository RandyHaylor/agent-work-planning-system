"""One-shot Haiku call for the prior-art experiment (recreated 2026-11-27; the original shared copy was
written by a headless session the auto-resume hook hijacked, see memory/BUILD-DECISIONS-LOG #55).

Isolation: runs from a neutral empty directory OUTSIDE the repo with --safe-mode (no CLAUDE.md, hooks,
memory, skills, plugins, MCP), so neither the project's instructions nor its Stop hook reach the call.
The prompt goes on stdin, so the variadic --tools flag cannot swallow it.
"""
import json
import subprocess
import tempfile
from pathlib import Path

NEUTRAL = Path(tempfile.gettempdir()) / "haiku-exp-neutral"
NEUTRAL.mkdir(exist_ok=True)
WEB_TOOLS = "WebSearch,WebFetch"


def ask(prompt, web=False, timeout=600):
    """Return {"result", "usage", "cost", "is_error"}. Never raises on a bad call."""
    cmd = ["claude", "-p", "--model", "haiku", "--output-format", "json", "--safe-mode"]
    if web:
        cmd += ["--allowed-tools", WEB_TOOLS, "--tools", WEB_TOOLS]
    else:
        cmd += ["--tools", ""]
    try:
        proc = subprocess.run(cmd, input=prompt, cwd=NEUTRAL, capture_output=True, text=True, timeout=timeout)
        data = json.loads(proc.stdout)
        return {"result": data.get("result", ""), "usage": data.get("usage", {}),
                "cost": data.get("total_cost_usd", 0.0), "is_error": bool(data.get("is_error"))}
    except (subprocess.TimeoutExpired, ValueError, OSError) as error:
        return {"result": "", "usage": {}, "cost": 0.0, "is_error": True, "error": str(error)}
