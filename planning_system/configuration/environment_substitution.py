"""environment_substitution: replaces "${NAME}" in config string values with the environment's
value, else the .env file's (secrets stay out of JSON). An unset name is an error naming it."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping, Optional

from planning_system.contract import Invalid

_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def read_dotenv(path: Optional[Path]) -> dict[str, str]:
    """Plain KEY=VALUE lines; '#' comments and blank lines skipped; surrounding quotes removed."""
    if path is None or not Path(path).is_file():
        return {}
    values = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values


class EnvironmentSubstitution:
    def __init__(self, environ: Mapping[str, str], dotenv: Mapping[str, str]):
        self._environ, self._dotenv = environ, dotenv

    def apply(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {k: self.apply(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.apply(v) for v in value]
        if isinstance(value, str):
            return _PATTERN.sub(lambda m: self._lookup(m.group(1)), value)
        return value

    def _lookup(self, name: str) -> str:
        if name in self._environ:
            return self._environ[name]
        if name in self._dotenv:
            return self._dotenv[name]
        raise Invalid(f"config needs ${{{name}}} but {name} is not set in the environment or .env")
