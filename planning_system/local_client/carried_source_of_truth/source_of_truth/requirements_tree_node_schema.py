"""Dataclasses + JSON schema for requirements-tree nodes (incl. project-paths node variant)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

PROJECT_PATHS_SPECIAL_NODE_KIND: str = "project_paths"
QUOTE_REFERENCE_NODE_KIND: str = "quote_reference"
GROUP_NODE_KIND: str = "group"

# Top-level group (text-less subject category) nodes seeded into every new
# project so agents have a consistent place to file things from turn one.
DEFAULT_PROJECT_SCAFFOLD_GROUP_TITLES: tuple[str, ...] = (
    "resources",                       # links/paths/docs/chunks supplied by the user
    "user-interaction-preferences",
    "technical-requirements",
    "current-project-documentation",
    # Instruction lifecycle: every explicit user instruction/decision/answer is
    # filed under pending-instructions, then moved (reparented) to completed- or
    # deprecated-instructions once it is done or no longer applies.
    "pending-instructions",
    "completed-instructions",
    "deprecated-instructions",
)

# The group new explicit instructions/decisions/answers MUST be filed under.
PENDING_INSTRUCTIONS_GROUP_TITLE: str = "pending-instructions"


@dataclass
class RawInputReference:
    raw_input_id: int
    char_range: Optional[list[int]] = None  # [start, end] inclusive into submission_text; only above threshold
    # Tri-state selection of the entry's agent pre-text (pre_submission_content):
    #   None        -> the WHOLE pre-text (the default every new node starts with),
    #   "none"      -> exclude the pre-text from this node,
    #   [start,end] -> only these 1-indexed lines of the pre-text.
    pre_text_line_range: Optional[object] = None

    def to_json_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"raw_input_id": self.raw_input_id}
        if self.char_range is not None:
            out["char_range"] = list(self.char_range)
        if self.pre_text_line_range is not None:
            out["pre_text_line_range"] = (
                list(self.pre_text_line_range)
                if isinstance(self.pre_text_line_range, (list, tuple))
                else self.pre_text_line_range
            )
        return out

    @classmethod
    def from_json_dict(cls, raw: dict[str, Any]) -> "RawInputReference":
        from .id_display import strip_raw_input_id_input_prefix

        raw_pre_text_line_range = raw.get("pre_text_line_range")
        if isinstance(raw_pre_text_line_range, (list, tuple)):
            raw_pre_text_line_range = list(raw_pre_text_line_range)
        return cls(
            raw_input_id=int(strip_raw_input_id_input_prefix(raw["raw_input_id"])),
            char_range=list(raw["char_range"]) if raw.get("char_range") is not None else None,
            pre_text_line_range=raw_pre_text_line_range,
        )


TOP_LEVEL_PARENT_SENTINEL: str = "0"


def _coerce_node_id_to_string(raw_value: Any) -> str:
    """Legacy ints become "1", "2"; new string ids ("a", "12", "aa") pass through.

    An optional display prefix (`nd-`) on input is stripped to the bare id; a bare
    on-disk id (no prefix) is a no-op, so saved trees round-trip unchanged.
    """
    from .id_display import strip_node_id_input_prefix

    return strip_node_id_input_prefix(raw_value)


def _coerce_parent_id_to_string_with_top_level_sentinel(raw_value: Any) -> str:
    """null/None/0/"0"/"nd-0" all collapse to TOP_LEVEL_PARENT_SENTINEL ("0").

    An optional `nd-` display prefix on input is stripped before the comparison.
    """
    from .id_display import strip_node_id_input_prefix

    if raw_value is None or raw_value == 0:
        return TOP_LEVEL_PARENT_SENTINEL
    stripped = strip_node_id_input_prefix(raw_value)
    if stripped == "0":
        return TOP_LEVEL_PARENT_SENTINEL
    return stripped


@dataclass
class RequirementsTreeNode:
    node_id: str
    parent_id: str  # "0" sentinel = top-level
    kind: str  # QUOTE_REFERENCE_NODE_KIND, PROJECT_PATHS_SPECIAL_NODE_KIND, or GROUP_NODE_KIND
    raw_input_reference: Optional[RawInputReference] = None  # required if kind=quote_reference
    project_paths: list[str] = field(default_factory=list)    # only for project_paths node
    child_node_ids: list[str] = field(default_factory=list)
    short_neutral_title: str = ""  # required for new add ops; legacy nodes load with ""

    def to_json_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "node_id": self.node_id,
            "parent_id": self.parent_id,
            "kind": self.kind,
            "child_node_ids": list(self.child_node_ids),
            "short_neutral_title": self.short_neutral_title,
        }
        if self.raw_input_reference is not None:
            out["raw_input_reference"] = self.raw_input_reference.to_json_dict()
        if self.kind == PROJECT_PATHS_SPECIAL_NODE_KIND:
            out["project_paths"] = list(self.project_paths)
        return out

    @classmethod
    def from_json_dict(cls, raw: dict[str, Any]) -> "RequirementsTreeNode":
        return cls(
            node_id=_coerce_node_id_to_string(raw["node_id"]),
            parent_id=_coerce_parent_id_to_string_with_top_level_sentinel(raw.get("parent_id")),
            kind=raw["kind"],
            raw_input_reference=(
                RawInputReference.from_json_dict(raw["raw_input_reference"])
                if raw.get("raw_input_reference") is not None
                else None
            ),
            project_paths=list(raw.get("project_paths", [])),
            child_node_ids=[_coerce_node_id_to_string(c) for c in raw.get("child_node_ids", [])],
            short_neutral_title=raw.get("short_neutral_title", ""),
        )


@dataclass
class RequirementsTree:
    project_id: str
    next_node_id: int  # counter for assigning quote-leaf node ids (1, 2, 3 ...) — stored as str on the node
    nodes_by_id: dict[str, RequirementsTreeNode] = field(default_factory=dict)
    next_group_letter_index: int = 0  # counter for assigning group node letter ids (a, b, ..., aa, ...)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "next_node_id": self.next_node_id,
            "next_group_letter_index": self.next_group_letter_index,
            "nodes_by_id": {nid: n.to_json_dict() for nid, n in self.nodes_by_id.items()},
        }

    @classmethod
    def from_json_dict(cls, raw: dict[str, Any]) -> "RequirementsTree":
        # top_level_node_ids was a stored field in the legacy schema; now derived,
        # so we ignore the field if present in legacy on-disk data.
        return cls(
            project_id=raw["project_id"],
            next_node_id=raw["next_node_id"],
            next_group_letter_index=raw.get("next_group_letter_index", 0),
            nodes_by_id={
                _coerce_node_id_to_string(nid): RequirementsTreeNode.from_json_dict(n)
                for nid, n in raw.get("nodes_by_id", {}).items()
            },
        )

    @classmethod
    def empty_for_project(cls, project_id: str) -> "RequirementsTree":
        return cls(project_id=project_id, next_node_id=1)

    @classmethod
    def scaffolded_for_new_project(cls, project_id: str) -> "RequirementsTree":
        """Empty tree pre-seeded with the default top-level group nodes
        (DEFAULT_PROJECT_SCAFFOLD_GROUP_TITLES), so every new project starts with
        consistent subject categories to file requirements under."""
        tree = cls(project_id=project_id, next_node_id=1)
        for group_title in DEFAULT_PROJECT_SCAFFOLD_GROUP_TITLES:
            group_letter_id = letter_id_for_index(tree.next_group_letter_index)
            tree.nodes_by_id[group_letter_id] = RequirementsTreeNode(
                node_id=group_letter_id,
                parent_id=TOP_LEVEL_PARENT_SENTINEL,
                kind=GROUP_NODE_KIND,
                short_neutral_title=group_title,
            )
            tree.next_group_letter_index += 1
        return tree

    def list_top_level_node_ids(self) -> list[str]:
        """Derived: nodes whose parent_id is the top-level sentinel '0'."""
        return [n.node_id for n in self.nodes_by_id.values() if n.parent_id == TOP_LEVEL_PARENT_SENTINEL]


def letter_id_for_index(zero_based_index: int) -> str:
    """0->'a', 25->'z', 26->'aa', 51->'az', 52->'ba', 701->'zz', 702->'aaa'.

    Spreadsheet-style base-26 with NO zero digit (Excel-column style).
    """
    if zero_based_index < 0:
        raise ValueError(f"zero_based_index must be >= 0; got {zero_based_index}")
    one_based_remainder = zero_based_index + 1
    letters_reversed: list[str] = []
    while one_based_remainder > 0:
        one_based_remainder, digit_zero_to_25 = divmod(one_based_remainder - 1, 26)
        letters_reversed.append(chr(ord("a") + digit_zero_to_25))
    return "".join(reversed(letters_reversed))


REQUIREMENTS_TREE_NODE_JSON_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "RequirementsTreeNode",
    "type": "object",
    "required": ["node_id", "parent_id", "kind", "child_node_ids"],
    "properties": {
        "node_id": {"type": "integer", "minimum": 1},
        "parent_id": {"type": ["integer", "null"]},
        "kind": {"enum": [QUOTE_REFERENCE_NODE_KIND, PROJECT_PATHS_SPECIAL_NODE_KIND, GROUP_NODE_KIND]},
        "raw_input_reference": {
            "type": "object",
            "required": ["raw_input_id"],
            "properties": {
                "raw_input_id": {"type": "integer", "minimum": 0},
                "char_range": {
                    "type": "array",
                    "items": {"type": "integer", "minimum": 0},
                    "minItems": 2,
                    "maxItems": 2,
                },
            },
        },
        "project_paths": {"type": "array", "items": {"type": "string"}},
        "child_node_ids": {"type": "array", "items": {"type": "integer"}},
        "short_neutral_title": {"type": "string", "maxLength": 50},
    },
}
