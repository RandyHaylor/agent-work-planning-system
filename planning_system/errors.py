"""errors: the shared error family (stdlib only). http_api maps each to an HTTP status; the CLI and
bootstrap print them. Generic modules (configuration, model_calls) depend on this file only, not on
the planning contract (Principal, roles)."""


class DomainError(Exception):
    """Base for errors http_api maps to HTTP status codes."""


class NotFound(DomainError):
    """-> 404"""


class Forbidden(DomainError):
    """-> 403"""


class Invalid(DomainError):
    """-> 422"""


class Conflict(DomainError):
    """-> 409 (e.g. a review verdict from someone not holding the review)"""


__all__ = ["Conflict", "DomainError", "Forbidden", "Invalid", "NotFound"]
