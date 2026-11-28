"""The route -> command table (05-spec-commands.md "Command list" + log #17 routes). The routers and
the tests both check against it. /guidance routes are not here: they read files through
prompt_builder's own guidance_service, not a command (log #25)."""
from __future__ import annotations

from .add_node_content import AddNodeContent
from .assemble_node_context import AssembleNodeContext
from .assign_task import AssignTask
from .cite_cache_item import CiteCacheItem
from .create_node import CreateNode
from .create_project import CreateProject
from .create_supplementary_task import CreateSupplementaryTask
from .end_admin_session import EndAdminSession
from .get_current_principal import GetCurrentPrincipal
from .get_node import GetNode
from .get_reference import GetReference
from .list_ancestors import ListAncestors
from .list_children import ListChildren
from .list_nodes_by_state import ListNodesByState
from .list_open_items import ListOpenItems
from .list_ready_children import ListReadyChildren
from .get_review import GetReview
from .list_reviews import ListReviews
from .release_review import ReleaseReview
from .submit_review_verdict import SubmitReviewVerdict
from .take_review import TakeReview
from .search_references import SearchReferences
from .supersede_candidates import (ConfirmSupersede, ListSupersedeCandidates, ProposeSupersede,
                                   RejectSupersede)
from .load_into_reader import LoadIntoReader
from .mint_credential import MintCredential
from .mint_quote_key import MintQuoteKey
from .move_node import MoveNode
from .read_reference_lines import ReadReferenceLines
from .reader_view import ReaderGet, ReaderJson, ReaderLines, ReaderSearch, ReaderToc
from .register_agent import RegisterAgent
from .render_citation import RenderCitation
from .replace_node_content import ReplaceNodeContent
from .revoke_credential import RevokeCredential
from .rotate_credential import RotateCredential
from .set_node_state import SetNodeState
from .start_admin_session import StartAdminSession
from .store_user_exchange import StoreUserExchange
from .update_node import UpdateNode

CORE_ROUTES = {
    ("POST", "/admin/sessions"): StartAdminSession,
    ("DELETE", "/admin/sessions"): EndAdminSession,
    ("GET", "/me"): GetCurrentPrincipal,
    ("POST", "/credentials"): MintCredential,
    ("POST", "/credentials/quote-key"): MintQuoteKey,
    ("POST", "/credentials/{credential_id}/revoke"): RevokeCredential,
    ("POST", "/credentials/{credential_id}/rotate"): RotateCredential,
    ("POST", "/agents"): RegisterAgent,
    ("POST", "/projects"): CreateProject,
    ("POST", "/nodes"): CreateNode,
    ("GET", "/nodes"): ListNodesByState,
    ("GET", "/nodes/{node_id}"): GetNode,
    ("GET", "/nodes/{node_id}/children"): ListChildren,
    ("GET", "/nodes/{node_id}/ancestors"): ListAncestors,
    ("GET", "/nodes/{node_id}/ready-children"): ListReadyChildren,
    ("PATCH", "/nodes/{node_id}"): UpdateNode,
    ("POST", "/nodes/{node_id}/move"): MoveNode,
    ("POST", "/nodes/{node_id}/state"): SetNodeState,
    ("POST", "/nodes/{node_id}/assign"): AssignTask,
    ("POST", "/nodes/{node_id}/supplementary"): CreateSupplementaryTask,
    ("POST", "/nodes/{node_id}/content"): AddNodeContent,
    ("PUT", "/nodes/{node_id}/content/{reference_id}"): ReplaceNodeContent,
    ("GET", "/nodes/{node_id}/context"): AssembleNodeContext,
    ("GET", "/projects/{project_id}/open-items"): ListOpenItems,     # build log #61
    # content review (05-spec-citation-enforcement-and-review.md "Routes")
    ("GET", "/reviews"): ListReviews,
    ("POST", "/reviews/take"): TakeReview,
    ("GET", "/reviews/{review_id}"): GetReview,
    ("POST", "/reviews/{review_id}/verdict"): SubmitReviewVerdict,
    ("POST", "/reviews/{review_id}/release"): ReleaseReview,
    # supersede candidates (05-spec-reference-supersede.md)
    ("POST", "/supersede-candidates"): ProposeSupersede,
    ("GET", "/supersede-candidates"): ListSupersedeCandidates,
    ("POST", "/supersede-candidates/{candidate_id}/confirm"): ConfirmSupersede,
    ("POST", "/supersede-candidates/{candidate_id}/reject"): RejectSupersede,
}

REFERENCE_ROUTES = {
    ("POST", "/reader/load"): LoadIntoReader,
    ("GET", "/reader/{reader_id}/toc"): ReaderToc,
    ("GET", "/reader/{reader_id}/get"): ReaderGet,
    ("POST", "/reader/search"): ReaderSearch,
    ("POST", "/reader/{reader_id}/json"): ReaderJson,
    ("GET", "/reader/{reader_id}/lines"): ReaderLines,
    ("POST", "/reader/cite"): CiteCacheItem,
    ("GET", "/references/search"): SearchReferences,
    ("GET", "/references/{reference_id}"): GetReference,
    ("GET", "/references/{reference_id}/lines"): ReadReferenceLines,
    ("POST", "/references/render"): RenderCitation,
    ("POST", "/references/user-exchange"): StoreUserExchange,
}

ROUTES = {**CORE_ROUTES, **REFERENCE_ROUTES}
