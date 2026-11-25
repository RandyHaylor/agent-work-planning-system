"""reference_sync (NEW): sends one exchange to the server when it is referenced."""
from .interface import ReferenceSync
from .ports import ClientCredentialsPort, LocalExchangeCachePort, ServerReferencesPort
from .raw_input_log_reader import RawInputLogReader


class ReferenceSyncService(ReferenceSync):
    def __init__(self, cache: LocalExchangeCachePort, server: ServerReferencesPort,
                 credentials: ClientCredentialsPort):
        self._reader = RawInputLogReader(cache)
        self._server = server
        self._credentials = credentials

    def sync(self, local_exchange_id):
        exchange = self._reader.read(local_exchange_id)
        return self._server.store_user_exchange(self._credentials.quote_key(), exchange.session_id,
                                                exchange.user_message, exchange.pre_text)
