"""The ReferenceLibrary facade: delegates to ingestion and citing_and_rendering."""
from .citing_and_rendering import CitingAndRendering
from .ingestion import Ingestion
from .interface import ReferenceLibrary


class ReferenceLibraryService(ReferenceLibrary):
    def __init__(self, storage):
        self._ingestion = Ingestion(storage)
        self._citing = CitingAndRendering(storage)

    def get(self, ref_id, follow_superseded=True):
        return self._citing.get(ref_id, follow_superseded)

    def read_lines(self, ref_id, start, end):
        return self._citing.read_lines(ref_id, start, end)

    def store_user_exchange(self, session_id, user_message, pre_text):
        return self._ingestion.store_user_exchange(session_id, user_message, pre_text)

    def store_proposal_response(self, node_id, text):
        return self._ingestion.store_proposal_response(node_id, text)

    def store_node_text(self, text, node_id, replaces=None):
        new = self._ingestion.store_node_text(text, node_id)
        if replaces is not None:
            self._citing.supersede(replaces, new.id)
        return new

    def render(self, citation):
        return self._citing.render(citation)

    def supersede(self, old_id, new_id):
        self._citing.supersede(old_id, new_id)
