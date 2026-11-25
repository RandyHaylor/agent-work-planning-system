"""agent_session_keys: persistent keys so agents can resume (carried pattern)."""


class AgentSessionKeys:
    def new_key(self) -> str:
        """A fresh random plaintext token."""
        raise NotImplementedError
