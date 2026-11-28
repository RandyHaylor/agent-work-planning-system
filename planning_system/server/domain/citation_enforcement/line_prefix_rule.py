"""line_prefix_rule (private): a tag whose every non-empty line must start with one of a fixed set of
prefixes (open_items: RESEARCH: / ASK USER: / VERIFY WITH USER:, build log #61). Deterministic."""
from __future__ import annotations

from planning_system.errors import Invalid


def check_line_prefixes(tag: str, text: str, prefixes: tuple[str, ...]) -> None:
    if not prefixes:
        return
    allowed = ", ".join(prefixes[:-1]) + f" or {prefixes[-1]}" if len(prefixes) > 1 else prefixes[0]
    lines = [(number, line.strip()) for number, line in enumerate(text.splitlines(), start=1) if line.strip()]
    if not lines:
        raise Invalid(f'a "{tag}" item needs at least one line, each starting with {allowed}')
    bad = [(number, line) for number, line in lines if not line.startswith(prefixes)]
    if bad:
        shown = "; ".join(f'line {number}: "{line[:60]}"' for number, line in bad)
        raise Invalid(f'a "{tag}" item lists one open item per line: every non-empty line must start with '
                      f"{allowed}. Lines that don't: {shown}")
