"""ModelEndpointFactory: endpoint name (from the `model_endpoints` config section) -> ChatModelCall.

Each endpoint: {"kind": "openai_compatible_chat", "base_url", "model", "extra_body"?, "timeout_seconds"?,
"max_concurrency"?}. load_model_endpoints() reads config/model_endpoints.json, or the file named by
PLANNING_MODEL_ENDPOINTS_FILE."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Mapping, Optional

import httpx

from planning_system.configuration import ConfigSection, load_config_file
from planning_system.errors import Invalid

from .interface import ChatModelCall
from .openai_compatible_chat_call import OpenAiCompatibleChatCall

SECTION = "model_endpoints"
ENDPOINTS_FILE_ENV = "PLANNING_MODEL_ENDPOINTS_FILE"
DEFAULT_ENDPOINTS_FILE = Path(__file__).resolve().parents[2] / "config" / "model_endpoints.json"


class ModelEndpointFactory:

    def __init__(self, endpoints: ConfigSection, transport: Optional[httpx.BaseTransport] = None):
        self._endpoints = endpoints
        self._transport = transport
        self._builders: dict[str, Callable[[ConfigSection, Optional[str]], ChatModelCall]] = {
            "openai_compatible_chat": self._openai_compatible_chat,
        }

    def names(self) -> list[str]:
        return sorted(self._endpoints.as_dict())

    def create(self, name: str, model: Optional[str] = None) -> ChatModelCall:
        """model overrides the endpoint's configured model."""
        if not self._endpoints.has(name):
            raise Invalid(f"unknown model endpoint {name!r}; configured: {', '.join(self.names()) or 'none'}")
        endpoint = self._endpoints.child(name)
        kind = endpoint.get("kind", "openai_compatible_chat")
        builder = self._builders.get(kind)
        if builder is None:
            raise Invalid(f"model endpoint {name!r} has unknown kind {kind!r}")
        return builder(endpoint, model)

    def _openai_compatible_chat(self, endpoint: ConfigSection, model: Optional[str]) -> ChatModelCall:
        return OpenAiCompatibleChatCall(
            base_url=endpoint.get("base_url"), model=model or endpoint.get("model"),
            extra_body=endpoint.get("extra_body", {}), timeout_seconds=float(endpoint.get("timeout_seconds", 120)),
            max_concurrency=int(endpoint.get("max_concurrency", 1)), transport=self._transport)


def load_model_endpoints(path: Optional[Path] = None, environ: Optional[Mapping[str, str]] = None,
                         transport: Optional[httpx.BaseTransport] = None) -> ModelEndpointFactory:
    environ = os.environ if environ is None else environ
    path = Path(path or environ.get(ENDPOINTS_FILE_ENV) or DEFAULT_ENDPOINTS_FILE)
    return ModelEndpointFactory(load_config_file(path, environ=environ).section(SECTION), transport=transport)
