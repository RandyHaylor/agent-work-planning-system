"""model_calls: one-shot and multi-turn chat calls to a model (no tools; the caller keeps any history). Knows
nothing of its callers.

Public: OneShotModelCall, ChatModelCall, OneShotRequest, ChatRequest, ChatMessage, OneShotResponse,
ModelCallFailed, OpenAiCompatibleChatCall, FakeOneShotModelCall, ModelEndpointFactory, load_model_endpoints."""
from .endpoint_factory import ENDPOINTS_FILE_ENV, ModelEndpointFactory, load_model_endpoints
from .fake import FakeOneShotModelCall
from .interface import ChatModelCall, OneShotModelCall
from .openai_compatible_chat_call import OpenAiCompatibleChatCall
from .types import ChatMessage, ChatRequest, ModelCallFailed, OneShotRequest, OneShotResponse

__all__ = ["ENDPOINTS_FILE_ENV", "ChatMessage", "ChatModelCall", "ChatRequest", "FakeOneShotModelCall",
           "ModelCallFailed", "ModelEndpointFactory", "OneShotModelCall", "OneShotRequest", "OneShotResponse",
           "OpenAiCompatibleChatCall", "load_model_endpoints"]
