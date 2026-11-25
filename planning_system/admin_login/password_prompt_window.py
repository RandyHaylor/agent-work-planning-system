"""password_prompt_window: tkinter masked-entry window; returns the typed string or None; no I/O beyond the window.

Level 6 scaffold: hollow.
"""
from __future__ import annotations

from typing import Optional

from .interface import PasswordPrompt


class TkPasswordPromptWindow(PasswordPrompt):

    def ask(self, message: str) -> Optional[str]:
        raise NotImplementedError("level 7")
