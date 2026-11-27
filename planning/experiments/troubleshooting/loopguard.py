"""Condition C harness loop limiter. Installed as run.sh in the agent's copy:
    run.sh -> python3 loopguard.py <workdir> <statefile>
Runs .real_run.sh, signs the failure by its last `XxxError:` line, and after 2 identical
failures prints STOP and refuses further runs until TROUBLESHOOTING.md has been updated."""
import json, re, subprocess, sys, time
from pathlib import Path

wd, state_path = Path(sys.argv[1]), Path(sys.argv[2])
record = wd / "TROUBLESHOOTING.md"
st = json.loads(state_path.read_text()) if state_path.exists() else {"sig": None, "count": 0, "stop_time": None, "log": []}

def save():
    state_path.write_text(json.dumps(st))

STOP = ("STOP: same failure twice. Re-research the error only and update your record "
        "(TROUBLESHOOTING.md) before editing. Further runs are refused until the record is updated.")

if st["stop_time"] is not None:
    if record.exists() and record.stat().st_mtime > st["stop_time"]:
        st["stop_time"], st["count"] = None, 0
        st["log"].append({"t": time.time(), "event": "unlocked"})
    else:
        st["log"].append({"t": time.time(), "event": "refused"})
        save()
        print(STOP)
        sys.exit(3)

r = subprocess.run(["bash", str(wd / ".real_run.sh")], capture_output=True, text=True)
out = r.stdout + r.stderr
sys.stdout.write(out)
if r.returncode == 0:
    st.update(sig=None, count=0)
    st["log"].append({"t": time.time(), "event": "pass"})
    save()
    sys.exit(0)
errs = re.findall(r"^\s*(\w+(?:\.\w+)*(?:Error|Exception)\b.*)$", out, re.M)
sig = errs[-1].strip() if errs else out.strip().splitlines()[-1]
sig = re.sub(r"/\S+/", "/", sig)  # path-independent
if sig == st["sig"]:
    st["count"] += 1
else:
    st["sig"], st["count"] = sig, 1
st["log"].append({"t": time.time(), "event": "fail", "sig": sig, "count": st["count"]})
if st["count"] >= 2:
    st["stop_time"] = time.time()
    st["log"].append({"t": time.time(), "event": "stop_injected"})
    print("\n" + STOP)
save()
sys.exit(r.returncode)
