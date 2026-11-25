"""Runs `node stdin_runner.js` as a subprocess: {"text", "argv"} on stdin; no shell, no temp files."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Callable, Sequence

from planning_system.quick_json_reader.json_reader_interface import NodeRunnerInterface
from planning_system.quick_json_reader.json_reader_types import NodeRunResult, NodeRunTimeout

STDIN_RUNNER_SCRIPT = Path(__file__).parent / "src" / "stdin_runner.js"

RunProcess = Callable[..., subprocess.CompletedProcess]


class NodeRunner(NodeRunnerInterface):
    def __init__(self, node_executable: str = "node", script_path: Path = STDIN_RUNNER_SCRIPT,
                 timeout_seconds: float = 30.0, run_process: RunProcess = subprocess.run) -> None:
        self.node_executable = node_executable
        self.script_path = script_path
        self.timeout_seconds = timeout_seconds
        self.run_process = run_process

    def run(self, text: str, argv: Sequence[str]) -> NodeRunResult:
        """Raises NodeRunTimeout when the process exceeds `timeout_seconds`."""
        request = json.dumps({"text": text, "argv": list(argv)})
        args = [self.node_executable, str(self.script_path)]
        try:
            completed = self.run_process(args, input=request, capture_output=True, text=True, encoding="utf-8",
                                         timeout=self.timeout_seconds, shell=False, check=False)
        except subprocess.TimeoutExpired as error:
            raise NodeRunTimeout(f"node exceeded {self.timeout_seconds}s") from error
        return NodeRunResult(completed.stdout or "", completed.stderr or "", completed.returncode)
