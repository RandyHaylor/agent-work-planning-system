"""The command-line tool and the local server, used the way an agent uses them: real
commands on real ruleset files, and a real server answered over HTTP."""

from __future__ import annotations

import contextlib
import io
import json
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from contextlib import redirect_stdout

REPOSITORY = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPOSITORY))

from ai_prompt_builder.command_line import main  # noqa: E402


def run(*arguments) -> str:
    output = io.StringIO()
    with redirect_stdout(output):
        main(list(arguments))
    return output.getvalue()


class CommandLineTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.user_folder = str(pathlib.Path(self.folder.name) / "user")
        self.ruleset_file = str(pathlib.Path(self.folder.name) / "mine.json")

    def cli(self, *arguments) -> str:
        return run("--user-folder", self.user_folder, *arguments)

    def test_a_new_ruleset_holds_the_presets_rules_and_lists_the_rest_as_not_added(self):
        self.cli("new", self.ruleset_file, "--preset", "Careful developer")
        ruleset = json.loads(pathlib.Path(self.ruleset_file).read_text())
        preset = json.loads((REPOSITORY / "data/presets/careful-developer.json").read_text())
        self.assertEqual([e["categoryId"] for e in ruleset["entries"]],
                         [e["categoryId"] for e in preset["entries"]])
        self.assertIn("Not added yet:", self.cli("show", self.ruleset_file))
        text = self.cli("compose", self.ruleset_file)
        self.assertIn("## Source of truth", text)
        self.assertIn("## Build skeleton first", text)
        self.assertNotIn("## Pull requests", text)           # off in this preset
        self.assertTrue(text.strip().endswith("could not merge."))  # example custom text at end

    def test_switching_choosing_editing_moving_and_custom_text(self):
        self.cli("new", self.ruleset_file, "--blank")
        self.assertEqual(self.cli("compose", self.ruleset_file).strip(), "")
        self.cli("set", self.ruleset_file, "testing", "--on", "--option", "simple-post-testing")
        self.cli("set", self.ruleset_file, "naming", "--on", "--text", "MY NAMING RULE")
        self.cli("move", self.ruleset_file, "naming", "1")
        self.cli("custom-text", self.ruleset_file, "--text", "DO THE THING", "--at", "start")
        text = self.cli("compose", self.ruleset_file)
        self.assertTrue(text.startswith("DO THE THING\n\n## Naming\n\nMY NAMING RULE"))
        self.assertIn("## Testing\n\n- Test what you've made", text)
        self.cli("all", self.ruleset_file, "reset-text")
        self.assertNotIn("MY NAMING RULE", self.cli("compose", self.ruleset_file))
        self.cli("all", self.ruleset_file, "off")
        self.cli("custom-text", self.ruleset_file, "--off")
        self.assertEqual(self.cli("compose", self.ruleset_file).strip(), "")

    def test_own_options_categories_and_presets_are_kept(self):
        self.cli("add-option", "testing", "--name", "Smoke only", "--text", "Run a smoke test.")
        category_id = self.cli("add-category", "Deployment").split()[2].rstrip(";")
        self.cli("add-option", category_id, "--name", "Staging first", "--text", "Deploy to staging first.")
        self.cli("new", self.ruleset_file, "--blank")
        self.cli("set", self.ruleset_file, category_id, "--on")
        self.cli("set", self.ruleset_file, "testing", "--on", "--option", "custom-smoke-only")
        self.cli("save-preset", self.ruleset_file, "My deploys")
        self.assertIn("My deploys (yours)", self.cli("presets"))
        second = str(pathlib.Path(self.folder.name) / "second.json")
        self.cli("new", second, "--preset", "my deploys")
        text = self.cli("compose", second)
        self.assertIn("## Deployment\n\nDeploy to staging first.", text)
        self.assertIn("Run a smoke test.", text)

    def test_set_adds_a_rule_that_is_not_added_yet_and_remove_takes_it_out(self):
        self.cli("new", self.ruleset_file, "--preset", "Small one-off")
        self.assertNotIn("## Design patterns", self.cli("compose", self.ruleset_file))
        self.cli("set", self.ruleset_file, "design-patterns", "--option", "functional")
        self.assertIn("## Design patterns\n\n- Functional", self.cli("compose", self.ruleset_file))
        self.cli("remove", self.ruleset_file, "design-patterns")
        self.assertIn("Design patterns (design-patterns)", self.cli("show", self.ruleset_file))

    def test_deleting_a_rule_removes_it_from_the_catalog_for_good(self):
        self.cli("delete-rule", "prs")
        self.assertNotIn("prs", [c["categoryId"] for c in json.loads(self.cli("categories", "--json"))])
        self.cli("new", self.ruleset_file, "--preset", "Careful dev manager")   # lists prs
        self.assertNotIn("## Pull requests", self.cli("compose", self.ruleset_file))
        warning = io.StringIO()
        with contextlib.redirect_stderr(warning):
            self.cli("new", self.ruleset_file, "--preset", "Careful dev manager")
        self.assertIn("warning, these rules were not found: Pull requests", warning.getvalue())
        own = self.cli("add-category", "Deployment").split()[2].rstrip(";")
        self.cli("delete-rule", own)
        self.assertIsNone(next((c for c in json.loads(self.cli("categories", "--json"))
                                if c["categoryId"] == own), None))

    def test_every_shipped_preset_points_only_at_rules_and_options_that_exist(self):
        for preset in json.loads(self.cli("presets", "--json")):
            warning = io.StringIO()
            with contextlib.redirect_stderr(warning):
                self.cli("new", self.ruleset_file, "--preset", preset["name"])
            self.assertEqual(warning.getvalue(), "", preset["name"])

    def test_a_built_in_preset_name_cannot_be_overwritten(self):
        self.cli("new", self.ruleset_file)
        with self.assertRaises(SystemExit):
            self.cli("save-preset", self.ruleset_file, "Careful developer")


class LocalServerTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        base = pathlib.Path(self.folder.name)
        self.user_folder = base / "user"
        self.ruleset_file = base / "instance.json"
        self.send_file = base / "sent.json"
        run("--user-folder", str(self.user_folder), "new", str(self.ruleset_file), "--preset", "Quick developer")

    def start_server(self, *extra):
        process = subprocess.Popen(
            [sys.executable, "-m", "ai_prompt_builder", "--user-folder", str(self.user_folder),
             "serve", "--ruleset-file", str(self.ruleset_file), *extra],
            cwd=REPOSITORY, stdout=subprocess.PIPE, text=True)
        self.addCleanup(process.wait)
        self.addCleanup(process.terminate)
        return json.loads(process.stdout.readline())["url"]

    def get(self, url):
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.read()

    def post(self, url, content, method="POST"):
        request = urllib.request.Request(url, data=json.dumps(content).encode(), method=method,
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.loads(response.read())

    def test_two_servers_run_at_once_on_different_free_ports(self):
        first, second = self.start_server(), self.start_server()
        self.assertNotEqual(first, second)
        self.assertIn(b"AI Prompt Builder", self.get(first))
        self.assertIn(b"AI Prompt Builder", self.get(second))

    def test_the_page_opens_the_ruleset_and_sending_is_off_unless_enabled(self):
        url = self.start_server()
        settings = json.loads(self.get(url + "api/session-settings"))
        self.assertFalse(settings["sendToAgentEnabled"])
        self.assertEqual(settings["openedRuleset"]["name"], "Quick developer")
        with self.assertRaises(urllib.error.HTTPError):
            self.post(url + "api/send-to-agent", {"ruleset": {}, "composedText": "x"})

    def test_send_to_agent_writes_the_file_and_wait_for_send_reports_it(self):
        url = self.start_server("--send-to-agent-file", str(self.send_file))
        self.assertTrue(json.loads(self.get(url + "api/session-settings"))["sendToAgentEnabled"])
        waiter = subprocess.Popen(
            [sys.executable, "-m", "ai_prompt_builder", "wait-for-send", str(self.send_file), "--timeout", "20"],
            cwd=REPOSITORY, stdout=subprocess.PIPE, text=True)
        time.sleep(1)
        ruleset = json.loads(self.ruleset_file.read_text())
        ruleset["name"] = "Edited in the page"
        self.post(url + "api/send-to-agent", {"ruleset": ruleset, "composedText": "THE TEXT"})
        output, _ = waiter.communicate(timeout=25)
        reported = json.loads(output)
        self.assertEqual(reported["composedText"], "THE TEXT")
        self.assertEqual(reported["rulesetName"], "Edited in the page")
        self.assertEqual(json.loads(self.ruleset_file.read_text())["name"], "Edited in the page")

    def test_customizations_saved_from_the_page_are_kept_as_files(self):
        url = self.start_server()
        self.post(url + "api/customizations", {
            "customCategories": [], "customOptions": [
                {"categoryId": "testing", "optionId": "custom-x", "shortName": "X", "fullText": "X text"}],
            "customPresets": [{"presetName": "Page preset", "entries": [], "customText": None}],
        }, method="PUT")
        self.assertTrue((self.user_folder / "presets" / "page-preset.json").exists())
        listed = json.loads(self.get(url + "api/customizations"))
        self.assertEqual(listed["customOptions"][0]["optionId"], "custom-x")
        self.assertEqual(listed["customPresets"][0]["presetName"], "Page preset")

    def test_only_the_pages_own_files_are_served(self):
        url = self.start_server()
        with self.assertRaises(urllib.error.HTTPError):
            self.get(url + "ai_prompt_builder/rule_catalog.py")


if __name__ == "__main__":
    unittest.main()
