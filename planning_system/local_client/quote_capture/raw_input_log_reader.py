"""raw_input_log_reader: reads exchanges by local id."""


class RawInputLogReader:
    def __init__(self, cache):
        self._cache = cache

    def read(self, local_id):
        raise NotImplementedError
