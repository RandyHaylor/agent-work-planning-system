"""local_client: runs beside the agent harness (spec: planning/05-spec-local-client.md). Public: LocalClient.

Children: harness_adapters/, task_runner/, review_worker/, client_credentials/, quote_capture/ (separate spec).
The children were ported from source-of-truth (commit d22d770); the raw carried copy was removed once ported.
"""
from .interface import (ExchangeReaderPort, HookInstallerPort, LocalClientInterface, ReferenceSyncPort)
from .local_client import LocalClient, build_local_client

__all__ = ["LocalClient", "LocalClientInterface", "build_local_client", "ReferenceSyncPort",
           "ExchangeReaderPort", "HookInstallerPort"]
