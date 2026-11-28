"""project_citations: every citation in the current content items of a project's nodes (supersede spec: find the
items citing a reference, and every user quote cited in the project)."""
from planning_system.server.domain.references.citation_syntax import citations_in

from .types import ProjectCitation


class ProjectCitationsFinder:
    def __init__(self, storage, references):
        self._storage = storage
        self._references = references

    def find(self, project_id):
        found = []
        for node in sorted(self._storage.subtree(project_id), key=lambda n: n.id):
            for item in self._storage.content(node.id):
                text = self._references.get(item.reference_id, follow_superseded=False).text
                found += [ProjectCitation(node.id, item.reference_id, frozenset(item.tags), c)
                          for c in citations_in(text)]
        return found
