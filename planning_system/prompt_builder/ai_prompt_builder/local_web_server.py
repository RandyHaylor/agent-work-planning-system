"""A local web server for one person's session: serves the prompt-builder page and a small
API, bound to this computer only (127.0.0.1), on a free port the operating system picks,
so any number can run at once (one per agent session).

API (all JSON):
  GET  /api/session-settings   {sendToAgentEnabled, storeFolder, openedRuleset}
  GET  /api/customizations     the user's own categories, options and presets
  PUT  /api/customizations     replace them (saved to the user's prompt-builder folder)
  POST /api/send-to-agent      {ruleset, composedText} -> written to the send file
"""

from __future__ import annotations

import json
import mimetypes
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .rule_catalog import REPOSITORY_FOLDER, RuleCatalog, write_json

FILES_THE_PAGE_NEEDS = ("index.html", "css/", "js/", "data/", "docs/")


class RuleBuilderSession:
    """What one running server serves: the catalog, the ruleset to open, and where
    (if anywhere) the Send to local AI agent button writes."""

    def __init__(self, catalog: RuleCatalog, opened_ruleset_path: "Path | None",
                 send_to_agent_file: "Path | None"):
        self.catalog = catalog
        self.opened_ruleset_path = opened_ruleset_path
        self.send_to_agent_file = send_to_agent_file

    def session_settings(self) -> dict:
        opened = None
        if self.opened_ruleset_path and self.opened_ruleset_path.exists():
            opened = json.loads(self.opened_ruleset_path.read_text(encoding="utf-8"))
        return {
            "sendToAgentEnabled": self.send_to_agent_file is not None,
            "storeFolder": str(self.catalog.user_folder),
            "openedRuleset": opened,
        }

    def read_customizations(self) -> dict:
        customizations = self.catalog.read_customizations()
        customizations["customPresets"] = [
            {"presetName": preset["name"], "entries": preset["entries"],
             "customText": preset.get("customText")}
            for preset in self.catalog.read_user_presets()
        ]
        return customizations

    def save_customizations(self, customizations: dict) -> None:
        self.catalog.write_customizations(customizations)
        self.catalog.replace_user_presets([
            {"name": preset["presetName"], "entries": preset["entries"],
             "customText": preset.get("customText")}
            for preset in customizations.get("customPresets", [])
        ])

    def send_to_agent(self, payload: dict) -> Path:
        content = {
            "sentAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "ruleset": payload.get("ruleset"),
            "composedText": payload.get("composedText", ""),
        }
        write_json(self.send_to_agent_file, content)
        # The ruleset also goes back to the file it was opened from, so the agent's copy
        # matches what the person built.
        if self.opened_ruleset_path and payload.get("ruleset"):
            write_json(self.opened_ruleset_path, payload["ruleset"])
        return self.send_to_agent_file


def make_request_handler(session: RuleBuilderSession):
    class RuleBuilderRequestHandler(BaseHTTPRequestHandler):
        def log_message(self, *_arguments):
            pass  # quiet: the agent reads the server's first line, not a request log

        def send_json(self, status: int, content) -> None:
            body = json.dumps(content).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def read_json_body(self):
            length = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(length) or b"{}")

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/api/session-settings":
                return self.send_json(200, session.session_settings())
            if path == "/api/customizations":
                return self.send_json(200, session.read_customizations())
            self.serve_page_file(path)

        def do_PUT(self):
            if self.path == "/api/customizations":
                session.save_customizations(self.read_json_body())
                return self.send_json(200, {"saved": True})
            self.send_json(404, {"error": "not found"})

        def do_POST(self):
            if self.path == "/api/send-to-agent":
                if session.send_to_agent_file is None:
                    return self.send_json(403, {"error": "sending is not enabled for this session"})
                written = session.send_to_agent(self.read_json_body())
                return self.send_json(200, {"sentTo": str(written)})
            self.send_json(404, {"error": "not found"})

        def serve_page_file(self, path: str) -> None:
            relative = path.lstrip("/") or "index.html"
            target = (REPOSITORY_FOLDER / relative).resolve()
            allowed = target.is_relative_to(REPOSITORY_FOLDER) and any(
                relative == item or relative.startswith(item) for item in FILES_THE_PAGE_NEEDS)
            if not allowed or not target.is_file():
                return self.send_json(404, {"error": "not found"})
            body = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(str(target))[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    return RuleBuilderRequestHandler


def start_server(session: RuleBuilderSession, port: int = 0) -> ThreadingHTTPServer:
    """Start serving in a background thread and return the server. Port 0 = a free port
    chosen by the operating system (read it from server.server_address)."""
    server = ThreadingHTTPServer(("127.0.0.1", port), make_request_handler(session))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
