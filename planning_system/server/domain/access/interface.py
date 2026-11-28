"""Public interface of access: pure rules; callers pass in the tree facts they need."""
from abc import ABC, abstractmethod
from typing import Optional, Sequence

from .types import (CredentialScope, KnowledgeBaseFacts, NodeFacts, Principal,
                    ReferenceFacts, TempEntryFacts)


class PermissionPolicy(ABC):
    # reading
    @abstractmethod
    def can_read_node(self, p: Principal, node: NodeFacts, ancestors: Sequence[NodeFacts]) -> bool: ...
    @abstractmethod
    def can_read_reference(self, p: Principal, ref: ReferenceFacts, nodes_citing_it: Sequence[NodeFacts]) -> bool: ...
    @abstractmethod
    def can_read_temp_entry(self, p: Principal, entry: TempEntryFacts) -> bool: ...
    @abstractmethod
    def can_read_knowledge_base(self, p: Principal, kb: KnowledgeBaseFacts) -> bool: ...

    # tree writes
    @abstractmethod
    def can_create_node(self, p: Principal, parent: NodeFacts) -> bool: ...
    @abstractmethod
    def can_edit_node(self, p: Principal, node: NodeFacts) -> bool: ...
    @abstractmethod
    def can_set_state(self, p: Principal, node: NodeFacts, new_state: str) -> bool: ...
    @abstractmethod
    def can_assign(self, p: Principal, node: NodeFacts) -> bool: ...
    @abstractmethod
    def can_create_supplementary_task(self, p: Principal, task: NodeFacts) -> bool: ...
    @abstractmethod
    def can_answer_requirement_request(self, p: Principal, request: NodeFacts) -> bool: ...
    @abstractmethod
    def can_add_content(self, p: Principal, node: NodeFacts) -> bool: ...

    # content review (build log #49/#50)
    @abstractmethod
    def can_review(self, p: Principal, project_id: int, own_task: Optional[NodeFacts]) -> bool:
        """List/take/decide reviews in a project: admin, its planner, or a worker whose own task
        (own_task) is in that project, labelled "review" and in progress."""

    # supersede candidates (05-spec-reference-supersede.md "Confirm")
    @abstractmethod
    def can_propose_supersede(self, p: Principal, project_id: int) -> bool:
        """Any agent of the project (planner or worker) or admin: "the agent or user proposes it"."""

    @abstractmethod
    def can_decide_supersede(self, p: Principal, project_id: int, user_quote: bool) -> bool:
        """Confirm / reject: documents -> the project's planner or admin ("Planner, you can override");
        user quotes -> admin only ("only the user confirms")."""

    # references
    @abstractmethod
    def can_submit_user_quote(self, p: Principal) -> bool: ...
    @abstractmethod
    def can_store_proposal_response(self, p: Principal) -> bool: ...

    # credentials
    @abstractmethod
    def can_mint(self, p: Principal, scope: CredentialScope, role: str) -> bool: ...
    @abstractmethod
    def can_revoke(self, p: Principal, token_scope: CredentialScope) -> bool: ...
    @abstractmethod
    def can_rotate(self, p: Principal, token: CredentialScope) -> bool: ...
