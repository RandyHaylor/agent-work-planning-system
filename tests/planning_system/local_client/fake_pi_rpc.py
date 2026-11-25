"""A fake `pi --mode rpc` process for tests: reads JSONL commands on stdin, answers a prompt with the
event stream pi emits (response ack, agent_start, turn_end with the text, agent_end).

FAKE_PI_REPLY   the assistant text to answer with
FAKE_PI_RECORD  file to write {"argv", "env", "commands"} to after each prompt
FAKE_PI_MODE    "crash" -> exit 3 on the prompt; "fail" -> unsuccessful response to the prompt
"""
import json
import os
import sys

commands = []
for line in sys.stdin:
    command = json.loads(line)
    commands.append(command)
    if command.get("type") != "prompt":
        print(json.dumps({"type": "response", "command": command.get("type"), "success": True}), flush=True)
        continue
    record = os.environ.get("FAKE_PI_RECORD")
    if record:
        with open(record, "w", encoding="utf-8") as handle:
            json.dump({"argv": sys.argv[1:], "env": {k: v for k, v in os.environ.items() if k.startswith("PI_")},
                       "commands": commands}, handle)
    mode = os.environ.get("FAKE_PI_MODE", "")
    if mode == "crash":
        sys.exit(3)
    if mode == "fail":
        print(json.dumps({"type": "response", "id": command.get("id"), "command": "prompt", "success": False,
                          "error": "model not found"}), flush=True)
        continue
    reply = os.environ.get("FAKE_PI_REPLY", "")
    for event in (
        {"type": "response", "id": command.get("id"), "command": "prompt", "success": True},
        {"type": "agent_start"},
        {"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "delta": reply[:5]}},
        {"type": "turn_end", "message": {"role": "assistant", "content": [{"type": "text", "text": reply}],
                                         "usage": {"input": 10, "output": 5}}},
        {"type": "agent_end"},
    ):
        print(json.dumps(event), flush=True)
