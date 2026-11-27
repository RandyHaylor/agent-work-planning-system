"""Prior-art experiment: does a required, cited prior-art step stop Haiku planners reinventing wheels?
Conditions A (baseline), B (prompt rule), C (MADR record + web), D (C + registry/URL checker + 1 revision).
Usage: python3 run.py   (writes raw/*.json and scores.json)
"""
import json, re, sys, urllib.request, urllib.error, concurrent.futures as cf
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import ask  # noqa: E402

RAW = HERE / "raw"; RAW.mkdir(exist_ok=True)

TASKS = {
    "iso_duration": "parse ISO-8601 durations (e.g. 'P3DT4H') into seconds in a Python service",
    "retry_backoff": "retry flaky HTTP calls with exponential backoff and jitter in a Python client",
    "rate_limit": "rate-limit outgoing calls of a Node.js API client to 10 requests/second",
    "text_diff": "show a unified diff of two text files in a Python CLI tool",
    "json_schema": "validate incoming JSON payloads against a JSON Schema in a Node.js server",
    "cron_jobs": "schedule cron-like recurring jobs inside a long-running Python process",
    "dotenv": "read configuration from .env files in a Python app",
    "fuzzy_match": "fuzzy-match user-typed product names against a catalog of 5,000 names in Python",
    # novel: nothing standard should exist
    "novel_heat": "compute our company's internal 'ticket heat score' (0.4*age_days + 0.35*priority_rank + 0.25*customer_tier_weight, tiers defined in our wiki) for our in-house helpdesk, in Python",
    "novel_qrx": "convert our proprietary in-house '.qrx' sensor log format (12-byte records: u32 timestamp, i16 temp*100, u16 humidity*100, u32 device id, little-endian) to CSV, in Python",
}
NOVEL = {"novel_heat", "novel_qrx"}

USER_WORDS = ('The user\'s rule: "every direction/suggestion/plan should be questioned \'do common patterns/examples/'
              'open source solutions exist already? are there lessons learned out there we can lean on?\'"')
LIMIT = "Keep it under 250 words."
PKG_LINE = ('End with one line exactly like: PACKAGES: pypi:name1, npm:name2  (every third-party package you cite, '
            'with its registry; write PACKAGES: none if none).')

def prompt(cond, task):
    if cond == "A":
        return f"Write a short implementation plan for: {task}. {LIMIT} {PKG_LINE}"
    if cond == "B":
        return (f"Write a short implementation plan for: {task}. {USER_WORDS} Before proposing, list existing "
                f"libraries/patterns you know of and decide build vs reuse. {LIMIT} {PKG_LINE}")
    # C and D
    return (f"Write a short implementation plan for: {task}. {USER_WORDS}\n"
            "First, research with WebSearch/WebFetch and write a PRIOR ART record (MADR style):\n"
            "- Considered options: at least 2, one of which must be 'use an existing library' (if any exists).\n"
            "- For each option: a source URL you actually visited/found, and a one-line reason.\n"
            "- Chosen option, with the deciding reason in quotes.\n"
            "- If your search finds no existing library/standard, say 'NONE FOUND' and list the queries and registries you searched.\n"
            "Do not cite any package or URL you have not confirmed exists.\n"
            f"Then the plan. Keep the whole answer under 350 words. {PKG_LINE}")

def call(p, web):
    # Isolated via common.ask: --safe-mode, neutral cwd, prompt on stdin (no CLAUDE.md, hooks or skills leak in).
    return ask(p, web=web)

# ---------- checker (used by D and for scoring all) ----------
def parse_packages(text):
    m = re.findall(r"PACKAGES:\s*(.*)", text)
    if not m: return []
    out = []
    for tok in re.split(r"[,\s]+", m[-1].strip().strip("`*")):
        tok = tok.strip("`*.;")
        if ":" in tok and tok.split(":")[0].lower() in ("pypi", "npm"):
            reg, name = tok.split(":", 1)
            if name: out.append((reg.lower(), name))
    return out

def url_ok(u, timeout=15):
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(u, method=method, headers={"User-Agent": "Mozilla/5.0 prior-art-check"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                if r.status < 400: return True
        except urllib.error.HTTPError as e:
            if e.code in (403, 429): return True  # bot-blocked, not dead
        except Exception:
            pass
    return False

def pkg_ok(reg, name):
    u = f"https://pypi.org/pypi/{name}/json" if reg == "pypi" else f"https://registry.npmjs.org/{name}"
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "prior-art-check"}), timeout=15) as r:
            return r.status == 200
    except Exception:
        return False

def check(text):
    urls = sorted(set(u.rstrip(").,]>`*'\"") for u in re.findall(r"https?://[^\s)\]>`\"']+", text)))
    pkgs = parse_packages(text)
    dead = [u for u in urls if not url_ok(u)]
    missing = [f"{r}:{n}" for r, n in pkgs if not pkg_ok(r, n)]
    return {"urls": urls, "dead_urls": dead, "packages": [f"{r}:{n}" for r, n in pkgs], "missing_packages": missing}

def run_one(cond, task, rep):
    out = RAW / f"{cond}_{task}_{rep}.json"
    if out.exists(): return json.loads(out.read_text())
    p = prompt(cond, TASKS[task])
    res = call(p, web=cond in ("C", "D"))
    rec = {"cond": cond, "task": task, "rep": rep, "prompt": p, "first": res}
    if cond == "D":
        chk = check(res["result"]); rec["first_check"] = chk
        if chk["dead_urls"] or chk["missing_packages"] or not chk["packages"] and "NONE FOUND" not in res["result"].upper():
            fb = ("An automatic checker found problems in your answer below.\n"
                  f"Dead/unreachable URLs: {chk['dead_urls']}\nPackages not found on the registry: {chk['missing_packages']}\n"
                  + ("No PACKAGES line with a package and no NONE FOUND record.\n" if not chk["packages"] and "NONE FOUND" not in res["result"].upper() else "")
                  + "Revise the whole answer once: replace or drop the failing citations (verify with WebSearch/WebFetch), "
                  "keep the same format and the PACKAGES line.\n\n---\n" + res["result"])
            rec["revised"] = call(fb, web=True)
    final = rec.get("revised", res)["result"]
    rec["final"] = final
    rec["final_check"] = check(final)
    out.write_text(json.dumps(rec, indent=1))
    return rec

if __name__ == "__main__":
    jobs = [(c, t, r) for c in "ABCD" for t in TASKS for r in (1,)]  # 1 rep: budget ~dozens of calls
    with cf.ThreadPoolExecutor(int(sys.argv[1]) if len(sys.argv) > 1 else 8) as ex:
        for f in cf.as_completed([ex.submit(run_one, *j) for j in jobs]):
            try:
                r = f.result(); print(r["cond"], r["task"], r["rep"], r["final_check"]["missing_packages"], len(r["final_check"]["dead_urls"]), flush=True)
            except Exception as e:
                print("ERR", e, flush=True)
