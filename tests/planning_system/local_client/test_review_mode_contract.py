"""review_mode contract (05-spec-citation-enforcement-and-review.md client tests 18-20), on [fake, real].
No real model, harness or pi CLI runs here: local_llm uses an httpx MockTransport, claude_code the fake harness
adapter, pi a fake `pi --mode rpc` script."""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest

from planning_system.api_client import ClientSettings
from planning_system.api_client.fakes import FakePlanningApiClient
from planning_system.contract import Invalid
from planning_system.local_client.harness_adapters.fakes import FakeAiCliAdapter
from planning_system.local_client.review_mode import (ReviewerBackendFactory, ReviewerUnavailable, ReviewModeLoop,
                                                      ReviewPacket, UnparseableVerdict, Verdict)
from planning_system.local_client.review_mode.fakes import FakeReviewModeLoop
from planning_system.local_client.review_mode.review_turns import opening_turn
from planning_system.local_client.review_mode.reviewer_backends import ClaudeCodeBackend, PiBackend
from planning_system.model_calls import FakeOneShotModelCall, ModelCallFailed, load_model_endpoints
from planning_system.local_client.review_mode.reviewer_backends.fakes import (FakeReviewerBackend, turn_reply,
                                                                              verdict_json)
from planning_system.local_client.review_mode.verdict_parser import parse_verdict
from planning_system.local_client.review_worker import ReviewWorker

FAKE_PI = Path(__file__).with_name("fake_pi_rpc.py")

PACKET = ReviewPacket.from_json({
    "review_id": "rev-1", "node_title": "vendor placement", "node_context_summary": "where vendors go",
    "claim_tag": "requirement", "claim_text": "Vendors go on even floors [ref-7:3-3].",
    "citations": [{"citation": "[ref-7:3-3]", "origin": "user_exchange", "quoted_text": "yes",
                   "pre_text": "Shall vendors go on even floors?", "full_text": "yes"}]})


# --------------------------------------------------------------------------- loop

@pytest.fixture(params=[pytest.param(FakeReviewModeLoop, id="fake"), pytest.param(ReviewModeLoop, id="real")])
def loop_class(request):
    return request.param


@pytest.fixture
def review_task(server):
    project = server.seed_project("Proj")
    node = server._new_node(project["id"], "Task", "task", "do it", [], None)
    token = server.issue_token("worker", project["id"], node["id"], "reviewer-1")
    return project["id"], node["id"], token


@pytest.fixture
def reviewer_api(server, review_task):
    return FakePlanningApiClient(ClientSettings("https://127.0.0.1:8443", None, review_task[2]),
                                 transport=server.transport())


def test_18_run_once_takes_reviews_and_submits(loop_class, server, reviewer_api, review_task):
    project_id, node_id, _ = review_task
    record = server.seed_review(project_id, node_id)
    backend = FakeReviewerBackend([verdict_json(False, "slice does not say X", "x choice")])
    assert loop_class(reviewer_api, backend, project_id).run_once() == record["id"]
    assert server.reviews[record["id"]]["status"] == "failed"
    assert server.reviews[record["id"]]["reason"] == "slice does not say X"
    assert server.reviews[record["id"]]["suggested_title"] == "x choice"
    assert "I want X." in backend.prompts[0]


def test_18_run_once_empty_queue_returns_none(loop_class, reviewer_api, review_task):
    backend = FakeReviewerBackend()
    assert loop_class(reviewer_api, backend, review_task[0]).run_once() is None
    assert backend.prompts == []


def test_18_retry_once_then_submit(loop_class, server, reviewer_api, review_task):
    record = server.seed_review(review_task[0], review_task[1])
    backend = FakeReviewerBackend(["not json at all", verdict_json(True, "quote states it")])
    loop_class(reviewer_api, backend, review_task[0]).run_once()
    assert server.reviews[record["id"]]["status"] == "passed"
    assert len(backend.prompts) == 2


def test_18_backend_error_twice_releases(loop_class, server, reviewer_api, review_task):
    record = server.seed_review(review_task[0], review_task[1])
    backend = FakeReviewerBackend([ReviewerUnavailable("down"), "garbage"])
    assert loop_class(reviewer_api, backend, review_task[0]).run_once() == record["id"]
    assert server.reviews[record["id"]]["status"] == "pending"
    assert server.requests[-1].path == f"/reviews/{record['id']}/release"


def test_18_serve_handles_one_at_a_time_and_stops_gracefully(loop_class, server, reviewer_api, review_task):
    first = server.seed_review(review_task[0], review_task[1])
    second = server.seed_review(review_task[0], review_task[1])
    stop = threading.Event()

    class StopAfterTwo(FakeReviewerBackend):
        def _ask(self, prompt):
            taken = [r for r in server.reviews.values() if r["status"] == "taken"]
            assert len(taken) == 1                        # never two reviews in hand
            if len(self.prompts) == 1:
                stop.set()                                # stop requested mid-review: this one still finishes
            return super()._ask(prompt)

    backend = StopAfterTwo([verdict_json(True), verdict_json(True)])
    loop_class(reviewer_api, backend, review_task[0], poll_seconds=0.01).serve(stop)
    assert server.reviews[first["id"]]["status"] == "passed"
    assert server.reviews[second["id"]]["status"] == "passed"


def test_serve_returns_promptly_when_stopped_while_idle(loop_class, reviewer_api, review_task):
    stop = threading.Event()
    thread = threading.Thread(target=loop_class(reviewer_api, FakeReviewerBackend(), review_task[0],
                                                poll_seconds=30).serve, args=(stop,))
    thread.start()
    time.sleep(0.05)
    stop.set()
    thread.join(2)
    assert not thread.is_alive()


# --------------------------------------------------------------------------- prompt + parser

def test_opening_turn_inlines_quotes_and_the_sentence_question():
    prompt = opening_turn(PACKET)
    for expected in ("NEW REVIEW rev-1", "PRE-INPUT CONTEXT", "Shall vendors go on even floors?", "CITED TEXT",
                     "Vendors go on even floors [ref-7:3-3].", "vendor placement", "CLAIM TAG: requirement",
                     "Does this sentence make a claim not fully supported by an included user or document reference?",
                     '"answer"'):
        assert expected in prompt


@pytest.mark.parametrize("answer, expected", [
    ('{"passed": true, "reason": "ok"}', Verdict(True, "ok")),
    ('```json\n{"passed": false, "reason": "no", "suggested_title": "x y"}\n```', Verdict(False, "no", "x y")),
    ('Example {"passed": true, "reason": "e"} then final {"passed": false, "reason": "final"}',
     Verdict(False, "final")),
    ('{"passed": true, "reason": "has } brace \\" quote"}', Verdict(True, 'has } brace " quote')),
])
def test_parser_accepts_strict_json_and_falls_back_to_last_object(answer, expected):
    assert parse_verdict(answer) == expected


@pytest.mark.parametrize("answer", ["", "yes", '{"passed": "yes", "reason": "x"}', '{"reason": "x"}', "[1]"])
def test_parser_rejects_anything_else(answer):
    with pytest.raises(UnparseableVerdict):
        parse_verdict(answer)


# --------------------------------------------------------------------------- backends (strategy contract)

class _LlmServer:
    """MockTransport handler: answers chat completions, records bodies and the peak number of requests in flight."""

    def __init__(self, reply: str, delay: float = 0.0):
        self.reply, self.delay = reply, delay
        self.bodies: list[dict] = []
        self.in_flight = self.peak = 0
        self._lock = threading.Lock()

    def __call__(self, request: httpx.Request) -> httpx.Response:
        with self._lock:
            self.in_flight += 1
            self.peak = max(self.peak, self.in_flight)
        try:
            time.sleep(self.delay)
            self.bodies.append(json.loads(request.content))
            return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": self.reply}}]})
        finally:
            with self._lock:
                self.in_flight -= 1


def LocalLlmBackend(transport, model=None):
    """local_llm as the CLI builds it: the factory, the shipped config/model_endpoints.json, a mock transport."""
    endpoints = load_model_endpoints(environ={}, transport=transport)
    return ReviewerBackendFactory(model_endpoints=endpoints).create("local_llm", model)


def _local_llm_backend(reply, tmp_path):
    server = _LlmServer(reply)
    return (LocalLlmBackend(transport=httpx.MockTransport(server)),
            lambda: [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "user"])


def _claude_code_backend(reply, tmp_path):
    adapter = FakeAiCliAdapter(reply=lambda handle, prompt: reply)
    backend = ClaudeCodeBackend(ReviewWorker(adapter, reviewer_model_name="haiku", allowed_tool_names=[]))
    return backend, lambda: adapter.sessions[0].prompts[1:]          # [0] is the priming prompt


def _pi_backend(reply, tmp_path):
    record = tmp_path / "pi.json"
    backend = PiBackend(command=[sys.executable, str(FAKE_PI)], timeout_seconds=20,
                        extra_environment={"FAKE_PI_REPLY": reply, "FAKE_PI_RECORD": str(record)})
    # one pi process per turn; the last one gets the title turn with every earlier turn replayed in it
    return backend, lambda: [json.loads(record.read_text())["commands"][-1]["message"]]


BACKENDS = [pytest.param(_local_llm_backend, id="local_llm"),
            pytest.param(_claude_code_backend, id="claude_code"), pytest.param(_pi_backend, id="pi")]

TWO_SENTENCE_PACKET = ReviewPacket.from_json({
    **{k: v for k, v in PACKET.__dict__.items() if k != "citations"}, "review_id": "rev-2",
    "claim_text": "Vendors go on even floors [ref-7:3-3]. Stairs never get vendors.",
    "citations": [c.__dict__ for c in PACKET.citations]})


@pytest.mark.parametrize("make_backend", BACKENDS)
def test_19_20_backend_asks_every_sentence_in_one_conversation(make_backend, tmp_path):
    backend, sent_turns = make_backend(turn_reply(True, "stairs not mentioned", "vendor placement"), tmp_path)
    verdict = backend.review(TWO_SENTENCE_PACKET)
    assert verdict == Verdict(False, "sentence 1 unsupported: stairs not mentioned; "
                                     "sentence 2 unsupported: stairs not mentioned", "vendor placement")
    sent = "\n".join(sent_turns())
    for expected in ("Shall vendors go on even floors?", 'Sentence 1 of 2: "Vendors go on even floors [ref-7:3-3]."',
                     'Sentence 2 of 2: "Stairs never get vendors."', "suggested_title"):
        assert expected in sent


@pytest.mark.parametrize("make_backend", BACKENDS)
def test_backend_passes_when_every_sentence_is_supported(make_backend, tmp_path):
    backend, _ = make_backend(turn_reply(False), tmp_path)
    assert backend.review(TWO_SENTENCE_PACKET) == Verdict(True, "all 2 sentences supported")


@pytest.mark.parametrize("make_backend", BACKENDS)
def test_backend_unparseable_answer_raises(make_backend, tmp_path):
    backend, _ = make_backend("I think it is fine.", tmp_path)
    with pytest.raises(UnparseableVerdict):
        backend.review(PACKET)


def test_19_local_llm_request_shape_and_sequential():
    server = _LlmServer(turn_reply(False), delay=0.02)
    backend = LocalLlmBackend(transport=httpx.MockTransport(server))
    threads = [threading.Thread(target=backend.review, args=(PACKET,)) for _ in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert server.peak == 1
    body = server.bodies[0]
    assert body["model"] == "gemma4-31b-jang-q3:latest"
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert body["response_format"] == {"type": "json_object"}
    assert body["temperature"] == 0
    assert 0 < body["max_tokens"] <= 512
    assert body.get("stream") in (None, False)


def test_local_llm_sends_the_growing_history_each_turn():
    server = _LlmServer(turn_reply(False))
    LocalLlmBackend(transport=httpx.MockTransport(server)).review(PACKET)   # opening, 1 sentence, title
    roles = [[m["role"] for m in body["messages"]] for body in server.bodies]
    assert roles == [["user"], ["user", "assistant", "user"], ["user", "assistant", "user", "assistant", "user"]]


@pytest.mark.parametrize("response", [httpx.Response(503, text="busy"), httpx.Response(200, json={"choices": []})])
def test_local_llm_failures_are_reviewer_unavailable(response):
    backend = LocalLlmBackend(transport=httpx.MockTransport(lambda request: response))
    with pytest.raises(ReviewerUnavailable):
        backend.review(PACKET)


def test_local_llm_connection_error_is_reviewer_unavailable():
    def refuse(request):
        raise httpx.ConnectError("refused")
    with pytest.raises(ReviewerUnavailable):
        LocalLlmBackend(transport=httpx.MockTransport(refuse)).review(PACKET)


def test_20_claude_code_uses_no_tools_and_given_model():
    adapter = FakeAiCliAdapter(reply=lambda handle, prompt: turn_reply(False))
    factory = ReviewerBackendFactory(review_worker_factory=lambda model: ReviewWorker(
        adapter, reviewer_model_name=model, allowed_tool_names=[]))
    factory.create("claude_code", "haiku").review(PACKET)
    assert adapter.sessions[0].reviewer_spawn == {"allowed_tool_names": [], "model": "haiku"}


def test_pi_launch_command_and_environment(tmp_path):
    backend = PiBackend(pi_directory=tmp_path)
    command = backend.launch_command
    assert command[:2] == ["node", str(tmp_path / "node_modules/@earendil-works/pi-coding-agent/dist/cli.js")]
    for flag in (["--mode", "rpc"], ["--provider", "local-llamacpp"], ["--model", "gemma4-31b-jang-q3:latest"]):
        index = command.index(flag[0])
        assert command[index:index + 2] == flag
    assert "--no-tools" in command and "--no-session" in command
    environment = backend.launch_environment
    assert environment["PI_CODING_AGENT_DIR"] == str(tmp_path / "agent")
    assert json.loads(environment["PI_REQUEST_PAYLOAD_INJECTION_JSON"]) == {
        "chat_template_kwargs": {"enable_thinking": False}}


@pytest.mark.parametrize("mode", ["crash", "fail"])
def test_pi_process_failure_is_reviewer_unavailable(mode):
    backend = PiBackend(command=[sys.executable, str(FAKE_PI)], timeout_seconds=20,
                        extra_environment={"FAKE_PI_MODE": mode})
    with pytest.raises(ReviewerUnavailable):
        backend.review(PACKET)


def test_19_factory_defaults_to_local_llm_and_rejects_unknown_and_parked_pi():
    factory = ReviewerBackendFactory()
    assert factory.create().name == "local_llm"
    for name in ("pi", "nope"):
        with pytest.raises(Invalid):
            factory.create(name)


def test_local_llm_model_flag_overrides_endpoint_model():
    server = _LlmServer(turn_reply(False))
    LocalLlmBackend(httpx.MockTransport(server), model="other-model").review(PACKET)
    assert server.bodies[0]["model"] == "other-model"
    assert server.bodies[0]["chat_template_kwargs"] == {"enable_thinking": False}


def test_one_shot_backend_maps_model_call_failure_to_reviewer_unavailable():
    from planning_system.local_client.review_mode.reviewer_backends import OneShotReviewerBackend
    model_call = FakeOneShotModelCall([ModelCallFailed("down")])
    with pytest.raises(ReviewerUnavailable):
        OneShotReviewerBackend(model_call).review(PACKET)
    assert model_call.requests[0].json_output and model_call.requests[0].temperature == 0
