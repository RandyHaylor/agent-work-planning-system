"""Types for quote_capture."""
from dataclasses import dataclass
from datetime import datetime

LocalExchangeId = str
ReferenceId = str

KIND_PROMPT = "prompt"
KIND_QUESTION_ANSWER = "question_answer"


@dataclass(frozen=True)
class Exchange:
    """One captured exchange in the local client cache.

    prompt: user_message is the verbatim prompt, pre_text the preceding agent output.
    question_answer: user_message is the chosen answer, pre_text the question asked.
    """
    local_id: LocalExchangeId
    session_id: str
    kind: str
    user_message: str
    pre_text: str
    captured_at: datetime
