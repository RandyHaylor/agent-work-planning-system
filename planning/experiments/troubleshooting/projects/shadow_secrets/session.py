from secrets import token_hex

from config import SIGNING_SALT


def new_session_id():
    """32 hex chars from the stdlib CSPRNG."""
    return token_hex(16)


def tag(session_id):
    return f"{SIGNING_SALT}:{session_id}"
