"""ExchangeCapture facade: harness adapter for pre-text -> raw input log writer; reads via the reader."""
from .interface import ExchangeCapture
from .raw_input_log_reader import RawInputLogReader
from .raw_input_log_writer import RawInputLogWriter
from .types import KIND_PROMPT, KIND_QUESTION_ANSWER


class ExchangeCaptureService(ExchangeCapture):
    def __init__(self, adapter, cache, clock):
        self._adapter = adapter
        self._writer = RawInputLogWriter(cache, clock)
        self._reader = RawInputLogReader(cache)

    def capture_prompt(self, session_id, user_message):
        pre_text = self._adapter.get_preceding_agent_output(session_id)
        return self._writer.append(session_id, KIND_PROMPT, user_message, pre_text)

    def capture_question_answer(self, session_id, question, answer):
        return self._writer.append(session_id, KIND_QUESTION_ANSWER, answer, question)

    def read(self, local_exchange_id):
        return self._reader.read(local_exchange_id)
