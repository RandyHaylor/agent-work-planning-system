"""password_prompt_window: tkinter masked-entry window; returns the typed string or None; no I/O beyond the window."""
from __future__ import annotations

from typing import Optional

from .interface import PasswordPrompt
from .types import NoDisplay


class TkPasswordPromptWindow(PasswordPrompt):

    def ask(self, message: str) -> Optional[str]:
        try:
            import tkinter as tk
        except ImportError as error:  # no Tk on this Python
            raise NoDisplay("tkinter is not available for the admin password window") from error
        try:
            root = tk.Tk()
        except tk.TclError as error:
            raise NoDisplay("no display available for the admin password window") from error

        result: dict = {"password": None}
        root.title("Planning admin login")
        root.resizable(False, False)
        tk.Label(root, text=message).pack(padx=16, pady=(16, 4))
        entry = tk.Entry(root, show="*", width=32)
        entry.pack(padx=16, pady=4)

        def submit(_event=None):
            result["password"] = entry.get()
            root.destroy()

        def cancel(_event=None):
            result["password"] = None
            root.destroy()

        buttons = tk.Frame(root)
        buttons.pack(padx=16, pady=(4, 16))
        tk.Button(buttons, text="OK", command=submit).pack(side="left", padx=4)
        tk.Button(buttons, text="Cancel", command=cancel).pack(side="left", padx=4)
        root.bind("<Return>", submit)
        root.bind("<Escape>", cancel)
        root.protocol("WM_DELETE_WINDOW", cancel)
        root.attributes("-topmost", True)
        entry.focus_force()
        root.mainloop()
        return result["password"]
