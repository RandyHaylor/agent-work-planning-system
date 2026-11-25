"""production_ports: the real implementations of the small ports quote_capture needs (server, quote key, clock)."""
from datetime import datetime, timezone

from planning_system.api_client import PlanningApiClientInterface
from planning_system.contract import Forbidden

from ..client_credentials import ClientCredentialsInterface
from .ports import ClientCredentialsPort, Clock, ServerReferencesPort


class ApiServerReferences(ServerReferencesPort):
    """POST /references/user-exchange through api_client, authenticated with the given credential only."""

    def __init__(self, api: PlanningApiClientInterface):
        self._api = api

    def store_user_exchange(self, credential, session_id, user_message, pre_text):
        return self._api.with_token(credential).store_user_exchange(session_id, user_message,
                                                                    pre_text)["reference_id"]


class StoredQuoteKey(ClientCredentialsPort):
    """The install's quote key from client_credentials; raises Forbidden when none is stored."""

    def __init__(self, credentials: ClientCredentialsInterface):
        self._credentials = credentials

    def quote_key(self) -> str:
        key = self._credentials.read_quote_key()
        if not key:
            raise Forbidden("this install has no quote key (admin: `planning credentials quote-key`, "
                            "then store it with the local client)")
        return key


class SystemClock(Clock):
    def now(self):
        return datetime.now(timezone.utc)
