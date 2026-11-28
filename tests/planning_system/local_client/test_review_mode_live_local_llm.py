"""Opt-in live check of the local_llm backend: ONE short call to the existing llama.cpp gemma4 server
(127.0.0.1:8898, one slot shared with another team; never started or stopped here).
Run with PLANNING_RUN_LOCAL_LLM=1."""
from __future__ import annotations

import os

import pytest

from planning_system.local_client.review_mode import ReviewPacket, Verdict
from planning_system.local_client.review_mode.reviewer_backends import OneShotReviewerBackend
from planning_system.model_calls import load_model_endpoints
from planning_system.local_client.review_mode.reviewer_backends.backend_factory import DEFAULT_MODEL_ENDPOINTS_FILE

pytestmark = pytest.mark.skipif(os.environ.get("PLANNING_RUN_LOCAL_LLM") != "1",
                                reason="live local llm call; set PLANNING_RUN_LOCAL_LLM=1")


def test_live_local_llm_passes_a_clearly_supported_requirement():
    packet = ReviewPacket.from_json({
        "review_id": "rev-live", "node_title": "output format", "node_context_summary": "report output",
        "claim_tag": "requirement", "claim_text": "Reports are written as CSV [ref-1:1-1].",
        "citations": [{"citation": "[ref-1:1-1]", "origin": "user_exchange",
                       "quoted_text": "Write the reports as CSV files.", "pre_text": "What format for reports?",
                       "full_text": "Write the reports as CSV files."}]})
    model_call = load_model_endpoints(default_path=DEFAULT_MODEL_ENDPOINTS_FILE).create("local_gemma4")
    verdict = OneShotReviewerBackend(model_call, max_tokens=128).review(packet)
    assert isinstance(verdict, Verdict)
    assert verdict.passed, verdict.reason
