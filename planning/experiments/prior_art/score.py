"""Score raw outputs. Reuse/none-found judged by a Haiku judge given the expected answers; package/URL checks are code.
Writes scores.json and prints a table."""
import json, re, sys, concurrent.futures as cf
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
from common import ask  # noqa: E402
from run import NOVEL  # noqa: E402
EXPECTED = {
    "iso_duration": "isodate / pendulum / aniso8601 (pypi)",
    "retry_backoff": "tenacity / backoff / urllib3 Retry (pypi)",
    "rate_limit": "bottleneck / p-limit / p-throttle / limiter (npm)",
    "text_diff": "Python stdlib difflib (unified_diff)",
    "json_schema": "ajv (npm) or similar JSON Schema validator",
    "cron_jobs": "APScheduler / schedule / croniter (pypi)",
    "dotenv": "python-dotenv / environs / pydantic-settings (pypi)",
    "fuzzy_match": "rapidfuzz / thefuzz (pypi), or stdlib difflib.get_close_matches",
    "novel_heat": "nothing standard: plain custom code is correct",
    "novel_qrx": "nothing standard for the format; stdlib struct + csv is the right reuse",
}

def judge(rec):
    t = rec["task"]
    q = (f"Task: {rec['prompt'][:300]}\nAppropriate existing solutions: {EXPECTED[t]}\n\nPLAN:\n{rec['final'][:4000]}\n\n"
         "Answer ONLY a JSON object: {\"reuses_existing\": true|false (plan's chosen approach uses an appropriate existing "
         "library or stdlib module rather than hand-writing the core algorithm), \"says_none_found\": true|false (plan "
         "explicitly states no existing library/standard solution exists for the core task), \"invents_lib\": true|false "
         "(plan claims a specific library exists for this exact in-house formula/format)}")
    out = ask(q, timeout=300)["result"]
    m = re.search(r"\{.*\}", out, re.S)
    try: return json.loads(m.group(0))
    except Exception: return {"error": out[-300:]}

def main():
    recs = [json.loads(p.read_text()) for p in sorted((HERE / "raw").glob("*.json"))]
    with cf.ThreadPoolExecutor(10) as ex:
        js = list(ex.map(judge, recs))
    rows = []
    for rec, j in zip(recs, js):
        u = rec["first"].get("usage", {}); u2 = rec.get("revised", {}).get("usage", {})
        out_tok = (u.get("output_tokens") or 0) + (u2.get("output_tokens") or 0)
        rows.append({"cond": rec["cond"], "task": rec["task"], "rep": rec["rep"], "novel": rec["task"] in NOVEL,
                     "judge": j, "pkgs": rec["final_check"]["packages"], "missing": rec["final_check"]["missing_packages"],
                     "urls": len(rec["final_check"]["urls"]), "dead": rec["final_check"]["dead_urls"],
                     "first_missing": rec.get("first_check", {}).get("missing_packages"),
                     "first_dead": rec.get("first_check", {}).get("dead_urls"), "revised": "revised" in rec,
                     "words": len(rec["final"].split()), "out_tokens": out_tok,
                     "cost": (rec["first"].get("cost") or 0) + (rec.get("revised", {}).get("cost") or 0)})
    (HERE / "scores.json").write_text(json.dumps(rows, indent=1))
    print("cond | reuse (std tasks) | pkgs cited | missing pkgs | URLs | dead URLs | novel: none-found | novel: invented lib | avg words | avg out tok | avg $")
    for c in "ABCD":
        R = [r for r in rows if r["cond"] == c]; S = [r for r in R if not r["novel"]]; N = [r for r in R if r["novel"]]
        f = lambda k, rs: sum(1 for r in rs if r["judge"].get(k))
        print(f"{c} | {f('reuses_existing', S)}/{len(S)} | {sum(len(r['pkgs']) for r in R)} | {sum(len(r['missing']) for r in R)} "
              f"{[m for r in R for m in r['missing']]} | {sum(r['urls'] for r in R)} | {sum(len(r['dead']) for r in R)} | "
              f"{f('says_none_found', N)}/{len(N)} | {f('invents_lib', N)}/{len(N)} | {sum(r['words'] for r in R)//max(len(R),1)} | "
              f"{sum(r['out_tokens'] for r in R)//max(len(R),1)} | {sum(r['cost'] for r in R)/max(len(R),1):.3f}")
    D = [r for r in rows if r["cond"] == "D"]
    print("D before checker: missing", [m for r in D for m in (r["first_missing"] or [])],
          "dead", sum(len(r["first_dead"] or []) for r in D), "revised runs", sum(r["revised"] for r in D))

if __name__ == "__main__":
    main()
