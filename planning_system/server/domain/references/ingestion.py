"""ingestion: synced user exchanges and node/proposal text into references; anything the reader
loads (URL, uploaded file, web search) -> document_extraction -> temp cache."""


class Ingestion:
    def __init__(self, storage, fetcher=None, temp_cache=None):
        self._storage = storage
        self._fetcher = fetcher
        self._temp_cache = temp_cache

    def store(self, origin, text, metadata, owner=None):
        """Store one fixed item; identical content (same SHA-256) reuses the stored copy."""
        raise NotImplementedError

    def store_user_exchange(self, session_id, user_message, pre_text):
        raise NotImplementedError

    def store_proposal_response(self, node_id, text):
        raise NotImplementedError

    def store_node_text(self, text, node_id):
        raise NotImplementedError

    def load_into_temp_cache(self, owner, source):
        """Fetch live through the source fetcher, extract text, put it in the owner's temp cache."""
        raise NotImplementedError
