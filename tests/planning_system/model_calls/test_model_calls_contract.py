"""model_calls contract on [fake, real-with-MockTransport]; no live model is called here."""
from __future__ import annotations

import json
from pathlib import Path
import threading
import time

import httpx
import pytest

from planning_system.contract import Invalid
from planning_system.model_calls import (FakeOneShotModelCall, ModelCallFailed, OneShotRequest, OneShotResponse,
                                         OpenAiCompatibleChatCall, load_model_endpoints)

REPO_ENDPOINTS_FILE = Path(__file__).resolve().parents[3] / "config" / "model_endpoints.json"


class _Server:
    def __init__(self, reply="hello", delay=0.0):
        self.reply, self.delay = reply, delay
        self.requests: list[httpx.Request] = []
        self.in_flight = self.peak = 0
        self._lock = threading.Lock()

    def __call__(self, request):
        with self._lock:
            self.in_flight += 1
            self.peak = max(self.peak, self.in_flight)
        try:
            time.sleep(self.delay)
            self.requests.append(request)
            body = json.loads(request.content)
            return httpx.Response(200, json={"model": body["model"], "usage": {"total_tokens": 7},
                                             "choices": [{"message": {"role": "assistant", "content": self.reply}}]})
        finally:
            with self._lock:
                self.in_flight -= 1

    def body(self, index=0):
        return json.loads(self.requests[index].content)


def _fake(reply):
    return FakeOneShotModelCall([reply], model="m1")


def _real(reply):
    return OpenAiCompatibleChatCall("http://test.invalid/v1", "m1", transport=httpx.MockTransport(_Server(reply)))


IMPLEMENTATIONS = [pytest.param(_fake, id="fake"), pytest.param(_real, id="real")]


@pytest.mark.parametrize("make", IMPLEMENTATIONS)
def test_complete_returns_text_and_model(make):
    response = make("an answer").complete(OneShotRequest(user_text="q"))
    assert isinstance(response, OneShotResponse)
    assert response.text == "an answer" and response.model == "m1"


def test_fake_records_requests_and_raises_scripted_errors():
    fake = FakeOneShotModelCall(["a", ModelCallFailed("down")])
    request = OneShotRequest(user_text="q", json_output=True)
    assert fake.complete(request).text == "a"
    with pytest.raises(ModelCallFailed):
        fake.complete(request)
    with pytest.raises(ModelCallFailed):
        fake.complete(request)
    assert fake.requests == [request] * 3


def test_real_request_shape():
    server = _Server()
    call = OpenAiCompatibleChatCall("http://test.invalid/v1/", "m1", transport=httpx.MockTransport(server),
                                    extra_body={"chat_template_kwargs": {"enable_thinking": False}})
    response = call.complete(OneShotRequest(user_text="u", system_text="s", json_output=True, max_tokens=64,
                                            temperature=0.2))
    assert str(server.requests[0].url) == "http://test.invalid/v1/chat/completions"
    body = server.body()
    assert body["messages"] == [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
    assert body["response_format"] == {"type": "json_object"}
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert (body["max_tokens"], body["temperature"], body["stream"]) == (64, 0.2, False)
    assert response.usage == {"total_tokens": 7}
    call.complete(OneShotRequest(user_text="u"))
    assert "response_format" not in server.body(1)
    assert [m["role"] for m in server.body(1)["messages"]] == ["user"]


def test_real_one_call_at_a_time_by_default():
    server = _Server(delay=0.05)
    calls = [OpenAiCompatibleChatCall("http://shared.invalid/v1", "m", transport=httpx.MockTransport(server))
             for _ in range(3)]
    threads = [threading.Thread(target=c.complete, args=(OneShotRequest(user_text="q"),)) for c in calls]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert server.peak == 1


@pytest.mark.parametrize("response", [httpx.Response(503, text="busy"), httpx.Response(200, json={"choices": []}),
                                      httpx.Response(200, text="not json")])
def test_real_bad_answers_raise_model_call_failed(response):
    call = OpenAiCompatibleChatCall("http://test.invalid/v1", "m", transport=httpx.MockTransport(lambda r: response))
    with pytest.raises(ModelCallFailed):
        call.complete(OneShotRequest(user_text="q"))


def test_real_connection_error_raises_model_call_failed():
    def refuse(request):
        raise httpx.ConnectError("refused")
    call = OpenAiCompatibleChatCall("http://test.invalid/v1", "m", transport=httpx.MockTransport(refuse))
    with pytest.raises(ModelCallFailed):
        call.complete(OneShotRequest(user_text="q"))


def test_shipped_local_gemma4_endpoint():
    server = _Server()
    endpoints = load_model_endpoints(environ={}, transport=httpx.MockTransport(server), default_path=REPO_ENDPOINTS_FILE)
    assert "local_gemma4" in endpoints.names()
    endpoints.create("local_gemma4").complete(OneShotRequest(user_text="q", json_output=True))
    assert str(server.requests[0].url) == "http://127.0.0.1:8898/v1/chat/completions"
    body = server.body()
    assert body["model"] == "gemma4-31b-jang-q3:latest"
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert body["response_format"] == {"type": "json_object"}


def test_endpoints_file_env_override_and_model_override(tmp_path):
    path = tmp_path / "endpoints.json"
    path.write_text(json.dumps({"model_endpoints": {"other": {
        "kind": "openai_compatible_chat", "base_url": "http://${HOST}/v1", "model": "x"}}}))
    server = _Server()
    endpoints = load_model_endpoints(environ={"PLANNING_MODEL_ENDPOINTS_FILE": str(path), "HOST": "h.invalid"},
                                     transport=httpx.MockTransport(server))
    endpoints.create("other", model="y").complete(OneShotRequest(user_text="q"))
    assert str(server.requests[0].url) == "http://h.invalid/v1/chat/completions"
    assert server.body()["model"] == "y"
    with pytest.raises(Invalid):
        endpoints.create("local_gemma4")


def test_load_model_endpoints_needs_a_path_env_or_default():
    with pytest.raises(Invalid):
        load_model_endpoints(environ={})
