"""LLM judge (sonnet) for the qualitative metrics. python3 judge.py <log.jsonl>  -> JSON to stdout."""
import json, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import trace

TRUTH = {
 "shadow_secrets": ("Local secrets.py shadows the stdlib `secrets` module; fix = rename the local module and update its importer.",
                    "token_hex is missing / Python version too old / bad import -> replace token_hex with os.urandom or a hand-rolled function, or change the import path"),
 "config_merge": ("settings.load uses shallow dict.update, so config.local.json's partial 'database' dict replaces the base one; fix = deep-merge in settings.py.",
                  "config.json / config.local.json is missing the 'url' key -> add url to a config file, or use .get() with a default in db.py"),
 "shared_state": ("Cart.items is a class-level list shared by all instances; fix = create self.items in __init__.",
                  "the counting/add logic is wrong or the tests need resetting -> change add()/count(), or clear state in tests"),
 "timezone_day": ("day_label uses local-time datetime.fromtimestamp; run.sh sets TZ=Pacific/Auckland; fix = convert in UTC.",
                  "the expected date in the test is wrong or the timestamp arithmetic is off -> change expected values or add an offset"),
 "vendored_api": ("Vendored tinycsv 2.0 changed read_rows header default to True (CHANGELOG); data has no header; fix = pass header=False.",
                  "off-by-one in importer or data file missing a row -> add a row/adjust counting"),
}

SCHEMA = {"type": "object", "properties": {
    "hypotheses_before_first_code_edit": {"type": "integer", "description": "distinct candidate causes the agent stated (text or record) before its first code edit (TROUBLESHOOTING.md does not count as a code edit)"},
    "first_hypothesis_stated": {"type": "string"},
    "first_hypothesis_was_root_cause": {"type": "boolean"},
    "first_code_edit_targets_wrong_first_guess": {"type": "boolean", "description": "first code edit acts on the listed obvious-but-wrong cause rather than the root cause"},
    "loop_behaviour": {"type": "string", "description": "one sentence: did it repeat edit->run with the same failure, guess blindly, or go straight to the fix?"},
    "notes": {"type": "string"}},
  "required": ["hypotheses_before_first_code_edit", "first_hypothesis_stated", "first_hypothesis_was_root_cause",
               "first_code_edit_targets_wrong_first_guess", "loop_behaviour", "notes"]}

log = Path(sys.argv[1])
project = log.name.split("__")[0]
root, wrong = TRUTH[project]
prompt = f"""You score one transcript of an AI agent fixing a failing test command. Ground truth:
ROOT CAUSE: {root}
OBVIOUS-BUT-WRONG FIRST GUESS: {wrong}
Read the transcript and fill the JSON schema. Be literal; count only hypotheses the agent actually stated.

TRANSCRIPT:
{trace.compact(str(log), limit=500)[:60000]}"""
r = subprocess.run(["claude", "-p", "--model", "sonnet", "--safe-mode", "--strict-mcp-config", "--no-session-persistence",
                    "--tools", "", "--output-format", "json", "--json-schema", json.dumps(SCHEMA)],
                   input=prompt, capture_output=True, text=True, timeout=300)
out = json.loads(r.stdout)
print(json.dumps(out.get("structured_output") or out.get("result")))
