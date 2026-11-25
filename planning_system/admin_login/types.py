"""admin_login types (spec: planning/05-spec-admin-login.md)."""

MAX_PASSWORD_ATTEMPTS = 3


class LoginError(Exception):
    """Base for admin login failures. Messages never contain the password."""


class LoginCancelled(LoginError):
    """The human closed or cancelled the window. No request was sent."""


class LoginFailed(LoginError):
    """Wrong password MAX_PASSWORD_ATTEMPTS times."""


class NoDisplay(LoginError):
    """No desktop display to open the window on. There is no terminal fallback (an agent could type into it)."""
