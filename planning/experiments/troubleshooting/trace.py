"""Parse a stream-json log. python3 trace.py <log.jsonl> [--print]  -> metrics JSON (and compact trace with --print)."""
import json, sys

def parse(path):
    steps, result, model = [], {}, None
    for line in open(path):
        try:
            e = json.loads(line)
        except Exception:
            continue
        t = e.get("type")
        if t == "system" and e.get("subtype") == "init":
            model = e.get("model")
        elif t == "assistant":
            for c in e["message"]["content"]:
                if c["type"] == "text":
                    steps.append(("text", c["text"]))
                elif c["type"] == "tool_use":
                    steps.append(("tool", c["name"], c["input"]))
        elif t == "user" and isinstance(e["message"].get("content"), list):
            for c in e["message"]["content"]:
                if c.get("type") == "tool_result":
                    cont = c.get("content")
                    if isinstance(cont, list):
                        cont = " ".join(x.get("text", "") for x in cont if isinstance(x, dict))
                    steps.append(("result", str(cont)))
        elif t == "result":
            result = e
    return steps, result, model

def is_code_edit(s):
    return s[0] == "tool" and s[1] in ("Edit", "Write", "MultiEdit") and not str(s[2].get("file_path", "")).endswith("TROUBLESHOOTING.md")

def is_run(s):
    return s[0] == "tool" and s[1] == "Bash" and "run.sh" in s[2].get("command", "")

def metrics(path):
    steps, res, model = parse(path)
    edits = sum(1 for s in steps if is_code_edit(s))
    runs = sum(1 for s in steps if is_run(s))
    cycles, dirty = 0, False
    for s in steps:
        if is_code_edit(s):
            dirty = True
        elif is_run(s) and dirty:
            cycles, dirty = cycles + 1, False
    denied = sum(1 for s in steps if s[0] == "result" and ("permission" in s[1].lower() and "denied" in s[1].lower() or "requires approval" in s[1].lower()))
    u = res.get("usage", {})
    return {"model": model, "code_edits": edits, "runs": runs, "edit_run_cycles": cycles, "denied_tool_calls": denied,
            "wrote_record": any(s[0] == "tool" and str(s[2].get("file_path", "")).endswith("TROUBLESHOOTING.md") for s in steps),
            "turns": res.get("num_turns"), "cost_usd": res.get("total_cost_usd"), "duration_s": round((res.get("duration_ms") or 0) / 1000, 1),
            "out_tokens": u.get("output_tokens"), "in_tokens": (u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)),
            "result_subtype": res.get("subtype")}

def compact(path, limit=600):
    steps, _, _ = parse(path)
    out = []
    for s in steps:
        if s[0] == "text":
            out.append("ASSISTANT: " + s[1][:limit * 3])
        elif s[0] == "tool":
            inp = s[2]
            if s[1] in ("Edit",):
                out.append(f"EDIT {inp.get('file_path','').split('/work/')[-1]}:\n- {inp.get('old_string','')[:limit]}\n+ {inp.get('new_string','')[:limit]}")
            elif s[1] == "Write":
                out.append(f"WRITE {inp.get('file_path','').split('/work/')[-1]}:\n{inp.get('content','')[:limit * 4]}")
            else:
                out.append(f"TOOL {s[1]} {json.dumps(inp)[:200]}")
        else:
            out.append("RESULT: " + s[1][:limit])
    return "\n".join(out)

if __name__ == "__main__":
    print(json.dumps(metrics(sys.argv[1])))
    if "--print" in sys.argv:
        print(compact(sys.argv[1]))
