"""The ProjectTree facade: delegates reads to TreeReader, writes to NodeEditor, content to NodeContentStore."""
from .citing_nodes import CitingNodesFinder
from .interface import ProjectTree
from .node_content import NodeContentStore
from .node_editor import NodeEditor
from .tree_reader import TreeReader


class ProjectTreeService(ProjectTree):
    def __init__(self, storage, references, clock):
        self._reader = TreeReader(storage)
        self._editor = NodeEditor(storage, clock)
        self._content = NodeContentStore(storage, references)
        self._citing = CitingNodesFinder(storage, references)

    def citing_nodes(self, reference_id):
        return self._citing.find(reference_id)

    def get(self, node_id):
        return self._reader.get(node_id)

    def children(self, node_id):
        return self._reader.children(node_id)

    def ancestors(self, node_id):
        return self._reader.ancestors(node_id)

    def content(self, node_id):
        return self._content.list(node_id)

    def ready_siblings(self, parent_id):
        return self._reader.ready_siblings(parent_id)

    def list_nodes(self, project_id, state=None):
        return self._reader.list_nodes(project_id, state)

    def create(self, parent_id, title, level_label, context_summary, labels=(), depends_on=None,
               position=None):
        return self._editor.create(parent_id, title, level_label, context_summary, labels,
                                   depends_on, position)

    def insert_before(self, task_id, title, labels, context_summary):
        return self._editor.insert_before(task_id, title, labels, context_summary)

    def update(self, node_id, **fields):
        return self._editor.update(node_id, fields)

    def move(self, node_id, new_parent_id, position):
        return self._editor.move(node_id, new_parent_id, position)

    def set_state(self, node_id, state):
        return self._editor.set_state(node_id, state)

    def assign(self, node_id, assignee):
        return self._editor.assign(node_id, assignee)

    def add_content(self, node_id, text, tags):
        content = self._content.add(node_id, text, tags)
        self._editor.touch(node_id)
        return content

    def replace_content(self, node_id, old_reference_id, new_text):
        content = self._content.replace(node_id, old_reference_id, new_text)
        self._editor.touch(node_id)
        return content
