"""model_calls: one-shot calls to a model (no tools, no session). Knows nothing of its callers.

Public: OneShotModelCall, OneShotRequest, OneShotResponse, ModelCallFailed, OpenAiCompatibleChatCall,
FakeOneShotModelCall, ModelEndpointFactory, load_model_endpoints."""
from .endpoint_factory import ENDPOINTS_FILE_ENV, ModelEndpointFactory, load_model_endpoints
from .fake import FakeOneShotModelCall
from .interface import OneShotModelCall
from .openai_compatible_chat_call import OpenAiCompatibleChatCall
from .types import ModelCallFailed, OneShotRequest, OneShotResponse

__all__ = ["ENDPOINTS_FILE_ENV", "FakeOneShotModelCall", "ModelCallFailed", "ModelEndpointFactory",
           "OneShotModelCall", "OneShotRequest", "OneShotResponse", "OpenAiCompatibleChatCall",
           "load_model_endpoints"]
