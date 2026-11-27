"""One trial: python3 run_trial.py <project> <A|B|C> <rep>
Copies the project to a temp dir, runs `claude -p --model haiku` headless, logs stream-json, runs checks."""
import json, os, shutil, subprocess, sys, time
from pathlib import Path

EXP = Path(__file__).resolve().parent
SCRATCH = Path(os.environ.get("TRIAL_SCRATCH", "/tmp/ts-trials"))
project, cond, rep = sys.argv[1], sys.argv[2], sys.argv[3]
tag = f"{project}__{cond}__{rep}"
base = SCRATCH / tag
shutil.rmtree(base, ignore_errors=True)
wd, pristine, guard = base / "work", base / "pristine", base / "guard"
shutil.copytree(EXP / "projects" / project, wd)
guard.mkdir(parents=True)

if cond == "C":
    shutil.copy(EXP / "loopguard.py", guard / "loopguard.py")
    (wd / "run.sh").rename(wd / ".real_run.sh")
    (wd / "run.sh").write_text(
        f'#!/usr/bin/env bash\nexec python3 {guard}/loopguard.py "$(cd "$(dirname "$0")" && pwd)" {guard}/state.json\n')
    (wd / "run.sh").chmod(0o755)
shutil.copytree(wd, pristine)

PROTOCOL = """Troubleshooting protocol (mandatory):
1. Before changing any code: run the command once, then create TROUBLESHOOTING.md in the project root containing:
   - The error, copied verbatim.
   - Research. You have no web access. Research ONLY the error: read the error text, the code it points at, and docs/changelogs in the repo. Do not research your own guesses. List each file/doc you looked at as evidence.
   - At least 3 candidate causes, each with a likelihood (high/medium/low) and a cost to rule out (by logic / trivial check / costly). Check them cheapest-to-eliminate first.
   - The result of each check.
2. Fix the root cause, not the symptom.
3. Change one thing at a time; run the command after each change and record the result in TROUBLESHOOTING.md.
4. If the same failure appears twice, stop editing, re-research the error only, and update the record before the next change."""
SYS = {
    "A": "Fix the failing command.",
    "B": "Fix the failing command.\n\n" + PROTOCOL,
    "C": "Fix the failing command.\n\n" + PROTOCOL + "\n\nNote: ./run.sh is wrapped by a loop limiter. After two identical failures it prints STOP and refuses to run until TROUBLESHOOTING.md is updated.",
}
USER = "`./run.sh` in this directory fails. Make it pass. Do not edit run.sh or the test files."

cmd = ["claude", "-p", USER, "--model", "haiku", "--append-system-prompt", SYS[cond],
       "--output-format", "stream-json", "--verbose",
       "--safe-mode", "--strict-mcp-config", "--no-session-persistence",
       "--tools", "Read,Edit,Write,Glob,Grep,Bash",
       "--allowedTools", "Read", "Edit", "Write", "Glob", "Grep", "Bash(./run.sh)", "Bash(ls)", "Bash(ls *)", "Bash(mv *)",
       "--permission-mode", "dontAsk", "--permission-prompts", "none", "--max-budget-usd", "1.50"]
logdir = EXP / "logs"
logdir.mkdir(exist_ok=True)
t0 = time.time()
with open(logdir / f"{tag}.jsonl", "w") as log:
    try:
        subprocess.run(cmd, cwd=wd, stdout=log, stderr=subprocess.STDOUT, timeout=900,
                       env={k: v for k, v in os.environ.items() if k != "CLAUDECODE"})
        timed_out = False
    except subprocess.TimeoutExpired:
        timed_out = True
wall = time.time() - t0

chk = subprocess.run([sys.executable, str(EXP / "checks.py"), project, str(wd), str(pristine)],
                     capture_output=True, text=True)
res = json.loads(chk.stdout) if chk.stdout.strip() else {"check_error": chk.stderr[-500:]}
res.update(cond=cond, rep=rep, wall_s=round(wall, 1), timed_out=timed_out)
if (guard / "state.json").exists():
    res["guard_log"] = json.loads((guard / "state.json").read_text())["log"]
rec = wd / "TROUBLESHOOTING.md"
if rec.exists():
    (logdir / f"{tag}.TROUBLESHOOTING.md").write_text(rec.read_text())
# final diff of the work dir vs pristine
d = subprocess.run(["diff", "-ruN", "-x", "__pycache__", "-x", "TROUBLESHOOTING.md", str(pristine), str(wd)],
                   capture_output=True, text=True)
(logdir / f"{tag}.diff").write_text(d.stdout)
(logdir / f"{tag}.check.json").write_text(json.dumps(res, indent=1))
print(json.dumps({k: res.get(k) for k in ("project", "cond", "rep", "root_fixed", "symptom_patch", "command_passes", "wall_s")}))
