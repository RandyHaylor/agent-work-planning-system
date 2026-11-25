"""raw_input_log_reader: reads exchanges by local id."""
from planning_system.contract import NotFound

from .ports import LocalExchangeCachePort
from .types import Exchange


class RawInputLogReader:
    def __init__(self, cache: LocalExchangeCachePort):
        self._cache = cache

    def read(self, local_id) -> Exchange:
        exchange = self._cache.get(local_id)
        if exchange is None:
            raise NotFound(f"no local exchange {local_id!r}")
        return exchange
