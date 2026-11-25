"""ReviewWorker: adapted from SoT reviewer_session_lifecycle_manager.py
(planning_system/local_client/carried_source_of_truth/source_of_truth/). Level 7 ports its
get_or_spawn / send_with_rotation_on_exhaustion logic here, minus SoT's project settings and requirements-tree
priming (the planning system has no local tree). Level 6 scaffold: hollow.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence

from ..harness_adapters import AiCliAdapterInterface
from .interface import ReviewWorkerInterface


class ReviewWorker(ReviewWorkerInterface):

    def __init__(self, adapter: AiCliAdapterInterface, reviewer_model_name: str = "sonnet",
                 thinking_log_path: Optional[Path] = None):
        self._adapter = adapter
        self._reviewer_model_name = reviewer_model_name
        self._thinking_log_path = thinking_log_path

    def ask(self, question: str, context_paths: Sequence[Path] = ()) -> str:
        raise NotImplementedError("level 7")
