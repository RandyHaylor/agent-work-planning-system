"""Schema for batched change-sets submitted by the primary agent."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

OPERATION_KIND_ADD: str = "add"
OPERATION_KIND_ADD_GROUP: str = "add_group"
OPERATION_KIND_REPARENT: str = "reparent"
OPERATION_KIND_REMOVE: str = "remove"
OPERATION_KIND_MODIFY_REFERENCE: str = "modify_reference"
OPERATION_KIND_REORDER_CHILDREN: str = "reorder_children"

ALL_OPERATION_KINDS: tuple[str, ...] = (
    OPERATION_KIND_ADD,
    OPERATION_KIND_ADD_GROUP,
    OPERATION_KIND_REPARENT,
    OPERATION_KIND_REMOVE,
    OPERATION_KIND_MODIFY_REFERENCE,
    OPERATION_KIND_REORDER_CHILDREN,
)


@dataclass
class RequirementsTreeChangeSet:
    operations: list[dict[str, Any]]
    submitter_rationale: str = ""

    def to_json_dict(self) -> dict[str, Any]:
        return {"operations": list(self.operations), "submitter_rationale": self.submitter_rationale}

    @classmethod
    def from_json_dict(cls, raw: dict[str, Any]) -> "RequirementsTreeChangeSet":
        return cls(
            operations=list(raw.get("operations", [])),
            submitter_rationale=raw.get("submitter_rationale", ""),
        )


REQUIREMENTS_TREE_CHANGE_SET_JSON_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "RequirementsTreeChangeSet",
    "type": "object",
    "required": ["operations"],
    "properties": {
        "submitter_rationale": {"type": "string"},
        "operations": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["op"],
                "properties": {
                    "op": {"enum": list(ALL_OPERATION_KINDS)},
                    "parent_id": {"type": ["integer", "null"]},
                    "node_id": {"type": "integer"},
                    "new_parent_id": {"type": ["integer", "null"]},
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
                    "child_order": {"type": "array", "items": {"type": "integer"}},
                },
            },
        },
    },
}
