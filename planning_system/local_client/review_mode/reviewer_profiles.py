"""Reviewer profiles: named settings for review mode (backend, model, granularity), read from the
`reviewer_profiles` config section. Explicit CLI flags override a profile's values.
Default granularity when a profile or flag doesn't say: per_sentence for local_llm (Gemma 4), bulk otherwise
(user 2026-11-27)."""
from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Mapping, Optional

from planning_system.configuration import load_config_file
from planning_system.errors import Invalid

from .review_method import BULK, GRANULARITIES, PER_SENTENCE

SECTION = "reviewer_profiles"
PROFILES_FILE_ENV = "PLANNING_REVIEWER_PROFILES_FILE"
DEFAULT_PROFILES_FILE = Path(__file__).resolve().parents[3] / "config" / "reviewer_profiles.json"
DEFAULT_PROFILE = "local"
DEFAULT_GRANULARITY_BY_BACKEND = {"local_llm": PER_SENTENCE}


def default_granularity(backend: str) -> str:
    return DEFAULT_GRANULARITY_BY_BACKEND.get(backend, BULK)


@dataclass(frozen=True)
class ReviewerProfile:
    name: str
    backend: str
    model: Optional[str] = None
    granularity: Optional[str] = None

    def with_overrides(self, backend: Optional[str] = None, model: Optional[str] = None,
                       granularity: Optional[str] = None) -> "ReviewerProfile":
        changed_backend = backend is not None and backend != self.backend
        return replace(self, backend=backend or self.backend,
                       model=model if model is not None else (None if changed_backend else self.model),
                       granularity=granularity or (None if changed_backend else self.granularity))

    def resolved_granularity(self) -> str:
        granularity = self.granularity or default_granularity(self.backend)
        if granularity not in GRANULARITIES:
            raise Invalid(f"unknown review granularity {granularity!r}; choose one of {', '.join(GRANULARITIES)}")
        return granularity


@dataclass(frozen=True)
class ReviewerChoice:
    """What the user asked for on the command line: a profile name and/or explicit overrides."""
    profile: Optional[str] = None
    backend: Optional[str] = None
    model: Optional[str] = None
    granularity: Optional[str] = None

    def resolve(self, profiles: "ReviewerProfiles") -> ReviewerProfile:
        return profiles.get(self.profile).with_overrides(self.backend, self.model, self.granularity)


class ReviewerProfiles:

    def __init__(self, profiles: Mapping[str, ReviewerProfile]):
        self._profiles = dict(profiles)

    def names(self) -> list[str]:
        return sorted(self._profiles)

    def get(self, name: Optional[str] = None) -> ReviewerProfile:
        profile = self._profiles.get(name or DEFAULT_PROFILE)
        if profile is None:
            raise Invalid(f"unknown reviewer profile {name!r}; configured: {', '.join(self.names()) or 'none'}")
        return profile


def load_reviewer_profiles(path: Optional[Path] = None,
                           environ: Optional[Mapping[str, str]] = None) -> ReviewerProfiles:
    environ = os.environ if environ is None else environ
    section = load_config_file(Path(path or environ.get(PROFILES_FILE_ENV) or DEFAULT_PROFILES_FILE),
                               environ=environ).section(SECTION)
    return ReviewerProfiles({name: ReviewerProfile(name, **values) for name, values in section.as_dict().items()})
