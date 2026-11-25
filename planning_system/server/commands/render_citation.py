"""POST /references/render: ReferenceLibrary.render."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from planning_system.contract import Principal
from planning_system.server.domain.references.citation_format import parse_citation

from .command import ReadCommand
from .permissions import CanRenderCitation, Permission


@dataclass(frozen=True)
class RenderCitation(ReadCommand):
    citation: str

    def required_permission(self) -> Permission:
        return CanRenderCitation(self.citation)

    def run(self, services, principal: Optional[Principal]) -> Any:
        return services.references.render(parse_citation(self.citation))
