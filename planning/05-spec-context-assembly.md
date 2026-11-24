# Spec: context_assembly

APPROVED by the user, 2026-11-23, in Slack ("approve the merge and context_assembly"). Decisions and the user's words are in `05-module-specs.md` ("Phase 2: context_assembly").

A node gets all of its own content, plus the `context_summary` of every non-abandoned node above it, root first. Stacked, the summaries tell the story of what's being built; ancestors' requirements and task details are not included.

```python
@dataclass(frozen=True)
class AssembledContext:
    node_id: NodeId
    text: str                        # the pre-prompt, ready to hand to an agent
    sources: tuple[NodeId, ...]      # which nodes contributed, root first

class ContextAssembler:
    def assemble(self, node_id) -> AssembledContext
        # reads the tree only, through ProjectTree.ancestors / get / content
```

## External integration tests (mocked ProjectTree)

1. The output holds every ancestor's context_summary, root first, then all of the node's own content.
2. Ancestors' requirements and other content are not included.
3. Abandoned ancestors are left out ("Abandoned means gone").
4. A changed context_summary shows up in the next assembly (nothing cached).
