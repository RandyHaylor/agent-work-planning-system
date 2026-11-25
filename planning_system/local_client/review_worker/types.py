"""review_worker types. Constants carried verbatim from SoT reviewer_session_lifecycle_manager.py."""

CONTEXT_EXHAUSTION_RESPONSE_MARKERS: tuple[str, ...] = (
    "prompt is too long",
    "prompt too long",
    "context length exceeded",
    "context_length_exceeded",
    "maximum context",
)

REVIEWER_ALLOWED_TOOL_NAMES: list[str] = ["Read", "WebFetch", "WebSearch"]

REVIEWER_PRIMING_PROMPT = (
    "You are a reviewer. Answer the questions you are asked; be fast and terse; "
    "read the files you are pointed to."
)
