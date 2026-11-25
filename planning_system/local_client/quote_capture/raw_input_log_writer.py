"""raw_input_log_writer: appends each exchange to the local client cache (as in SoT)."""


class RawInputLogWriter:
    def __init__(self, cache, clock):
        self._cache = cache
        self._clock = clock

    def append(self, session_id, kind, user_message, pre_text):
        """Returns the new local exchange id."""
        raise NotImplementedError
