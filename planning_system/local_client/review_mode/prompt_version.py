"""PROMPT_VERSION: a short hash of every file that writes review prompt text or reads the answers, so a verdict and a
log record name the exact prompts that produced them without anyone having to bump a number (build log #70)."""
from __future__ import annotations

import hashlib
from pathlib import Path

PROMPT_FILES = ("review_turns.py", "node_screen_turns.py", "trial_review.py", "quote_check.py", "verdict_parser.py",
                "sentence_splitter.py")


def prompt_version(directory: Path = Path(__file__).resolve().parent) -> str:
    digest = hashlib.sha256()
    for name in PROMPT_FILES:
        digest.update(name.encode())
        digest.update((directory / name).read_bytes())
    return digest.hexdigest()[:12]


PROMPT_VERSION = prompt_version()
