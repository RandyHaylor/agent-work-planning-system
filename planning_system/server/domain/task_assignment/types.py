"""Types for task_assignment."""
from dataclasses import dataclass

from planning_system.server.domain.authentication.types import CredentialId
from planning_system.server.domain.project_tree.types import Node


@dataclass(frozen=True)
class Assignment:
    node: Node                       # state "assigned", assignee and branch set
    worker_token: str                # plaintext, shown once
    credential_id: CredentialId
