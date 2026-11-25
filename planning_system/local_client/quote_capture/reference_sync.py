"""reference_sync (NEW): sends one exchange to the server when it is referenced (hollow)."""
from .interface import ReferenceSync


class ReferenceSyncService(ReferenceSync):
    def __init__(self, cache, server, credentials):
        self._cache = cache
        self._server = server
        self._credentials = credentials

    def sync(self, local_exchange_id):
        raise NotImplementedError
