"""Contract tests for storage (spec: planning/05-spec-storage.md).

Each Postgres store implements one domain port; the port's expectations run against
[the domain's in-memory fake port, the Postgres store (xfail until level 7)]. The level-7 run needs
a real `planning_system` database (PLANNING_TEST_DSN); the hollow stores fail before touching one.
"""
import dataclasses
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import Table

from planning_system.contract import Principal
from planning_system.server.domain.agent_registry.fakes import InMemoryAgentRegistryStorage
from planning_system.server.domain.agent_registry.ports import AgentRegistryStoragePort
from planning_system.server.domain.agent_registry.types import AgentSession
from planning_system.server.domain.authentication.fakes import InMemoryCredentialStorage
from planning_system.server.domain.authentication.ports import CredentialStoragePort
from planning_system.server.domain.authentication.types import KIND_AGENT, StoredCredential
from planning_system.server.domain.project_tree.fakes import InMemoryTreeStorage
from planning_system.server.domain.project_tree.ports import TreeStoragePort
from planning_system.server.domain.project_tree.types import Node, NodeContent
from planning_system.server.domain.references.fakes import (InMemoryReferenceStorage,
                                                            InMemoryTempCacheStorage)
from planning_system.server.domain.references.ports import ReferenceStoragePort, TempCacheStoragePort
from planning_system.server.domain.references.types import Reference, TempCacheEntry
from planning_system.server.storage import (PostgresAgentRegistryStore, PostgresCredentialStore,
                                            PostgresReferenceStore, PostgresTempCacheStore,
                                            PostgresTreeStore, Storage, Stores, Transactions)
from planning_system.server.storage.fakes import InMemoryStorage, RecordingTransactions
from planning_system.server.storage.metadata import METADATA

LEVEL7 = pytest.mark.xfail(strict=False, reason="level 7")
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def store_fixture(fake_cls, real_cls):
    @pytest.fixture(params=["fake", pytest.param("real", marks=LEVEL7)])
    def fixture(request):
        # real: bound to a connection from a throwaway schema at level 7; hollow now
        return fake_cls() if request.param == "fake" else real_cls(None)
    return fixture


tree_store = store_fixture(InMemoryTreeStorage, PostgresTreeStore)
reference_store = store_fixture(InMemoryReferenceStorage, PostgresReferenceStore)
temp_store = store_fixture(InMemoryTempCacheStorage, PostgresTempCacheStore)
credential_store = store_fixture(InMemoryCredentialStorage, PostgresCredentialStore)
agent_store = store_fixture(InMemoryAgentRegistryStorage, PostgresAgentRegistryStore)


def node(id, parent=None, position=0, **kw):
    base = dict(id=id, parent_id=parent, position=position, title=f"n{id}", level_label="build",
                state="assigned", labels=frozenset({"x"}), context_summary="s", last_verified=T0,
                depends_on=None, assignee=None, branch=None)
    base.update(kw)
    return Node(**base)


# ---- shape

def test_each_store_implements_exactly_its_domain_port():
    assert issubclass(PostgresTreeStore, TreeStoragePort)
    assert issubclass(PostgresReferenceStore, ReferenceStoragePort)
    assert issubclass(PostgresTempCacheStore, TempCacheStoragePort)
    assert issubclass(PostgresCredentialStore, CredentialStoragePort)
    assert issubclass(PostgresAgentRegistryStore, AgentRegistryStoragePort)


def test_every_store_declares_its_tables_on_the_shared_metadata():
    assert {"nodes", "node_dependencies", "node_content", "references", "temp_cache_entries",
            "credentials", "admin_password", "agent_sessions"} <= set(METADATA.tables)
    assert all(isinstance(t, Table) for t in METADATA.tables.values())


def test_credentials_table_stores_only_digests():
    columns = set(METADATA.tables["credentials"].c.keys())
    assert "token_digest" in columns and "token" not in columns


def test_stores_for_binds_all_five_stores_to_one_connection():
    marker = object()
    stores = Storage(Transactions(None)).stores_for(marker)
    assert isinstance(stores, Stores)
    bound = [getattr(stores, f.name) for f in dataclasses.fields(stores)]
    assert {type(s) for s in bound} == {
        PostgresTreeStore, PostgresReferenceStore, PostgresTempCacheStore, PostgresCredentialStore,
        PostgresAgentRegistryStore}
    assert all(s._conn is marker for s in bound)


# ---- transactions (1, 2)

@pytest.fixture(params=["fake", pytest.param("real", marks=LEVEL7)])
def transactions(request):
    if request.param == "fake":
        return RecordingTransactions()
    from sqlalchemy import create_engine
    import os
    return Transactions(create_engine(os.environ.get(
        "PLANNING_TEST_DSN", "postgresql+psycopg://localhost:1/planning_system_test")))


def test_1_read_write_commits_on_success_and_rolls_back_on_error(transactions):
    with transactions.read_write():
        pass
    with pytest.raises(RuntimeError):
        with transactions.read_write():
            raise RuntimeError("boom")
    if isinstance(transactions, RecordingTransactions):
        assert [(r.committed, r.rolled_back) for r in transactions.records] == [(True, False), (False, True)]


@LEVEL7
def test_2_read_only_rejects_an_insert():
    from sqlalchemy import create_engine, text
    import os
    tx = Transactions(create_engine(os.environ.get("PLANNING_TEST_DSN", "postgresql+psycopg://localhost:1/x")))
    with pytest.raises(Exception):
        with tx.read_only() as conn:
            conn.execute(text("CREATE TEMP TABLE t (x int)"))


# ---- tree (3, 4)

def test_tree_round_trip_and_children_and_subtree(tree_store):
    root_id = tree_store.new_id()
    tree_store.save(node(root_id))
    child_id = tree_store.new_id()
    tree_store.save(node(child_id, parent=root_id, depends_on=(), labels=frozenset()))
    assert tree_store.get(root_id) == node(root_id)
    assert tree_store.get(child_id).depends_on == ()
    assert [n.id for n in tree_store.children(root_id)] == [child_id]
    assert [n.id for n in tree_store.children(None)] == [root_id]
    assert {n.id for n in tree_store.subtree(root_id)} == {root_id, child_id}
    assert tree_store.get(10**9) is None


def test_tree_content_add_and_replace(tree_store):
    nid = tree_store.new_id()
    tree_store.save(node(nid))
    tree_store.add_content(nid, NodeContent("r1", frozenset({"a"})))
    tree_store.add_content(nid, NodeContent("r2", frozenset()))
    tree_store.replace_content(nid, "r1", NodeContent("r3", frozenset({"a"})))
    assert [c.reference_id for c in tree_store.content(nid)] == ["r3", "r2"]


def test_tree_has_no_delete(tree_store):
    assert not any(hasattr(tree_store, n) for n in ("delete", "remove"))


# ---- references (5)

def test_references_round_trip_find_by_sha_and_supersede(reference_store):
    ref = Reference("r1", "node", "text", "sha-1", {"k": "v"}, "agent-1")
    reference_store.save(ref)
    assert reference_store.get("r1") == ref
    assert reference_store.find_by_sha256("sha-1") == ref
    assert reference_store.find_by_sha256("nope") is None
    reference_store.save(dataclasses.replace(ref, superseded_by="r2"))
    assert reference_store.get("r1").superseded_by == "r2"
    assert not hasattr(reference_store, "delete")


# ---- temp cache (6)

def test_temp_cache_round_trip_delete_and_created_before(temp_store):
    old = TempCacheEntry("c1", "a1", "old", "s1", T0, {"url": "u"})
    new = TempCacheEntry("c2", "a1", "new", "s2", T0 + timedelta(days=2))
    temp_store.save(old)
    temp_store.save(new)
    assert temp_store.get("c1") == old
    assert [e.cache_id for e in temp_store.created_before(T0 + timedelta(days=1))] == ["c1"]
    temp_store.delete("c1")
    assert temp_store.get("c1") is None and temp_store.get("c2") == new


# ---- credentials (7)

def test_credentials_round_trip_by_id_digest_and_minted_by(credential_store):
    planner = StoredCredential("k1", "d1", Principal("p1", "planner", 1), KIND_AGENT, minted_by=None)
    worker = StoredCredential("k2", "d2", Principal("w1", "worker", 1, 5), KIND_AGENT, minted_by="p1")
    credential_store.save(planner)
    credential_store.save(worker)
    assert credential_store.get("k1") == planner
    assert credential_store.find_by_digest("d2") == worker
    assert credential_store.minted_by("p1") == [worker]
    credential_store.save(dataclasses.replace(worker, revoked=True))
    assert credential_store.get("k2").revoked


# ---- agent registry (8)

def test_agent_registry_upsert_and_list(agent_store):
    first = AgentSession(agent_id="a1", host="box", first_seen=T0, last_seen=T0)
    agent_store.save(first)
    later = dataclasses.replace(first, model="m", last_seen=T0 + timedelta(hours=1))
    agent_store.save(later)
    assert agent_store.get("a1") == later
    assert agent_store.list() == [later]
    assert agent_store.get("nope") is None
    assert not hasattr(agent_store, "delete")


# ---- migrations (9)

@LEVEL7
def test_9_upgrade_head_creates_exactly_the_metadata_tables():
    import os
    from planning_system.configuration import ConfigSection
    from planning_system.server.storage import run_migrations
    run_migrations(ConfigSection("storage", {"dsn": os.environ.get("PLANNING_TEST_DSN", "postgresql+psycopg://localhost:1/x")}))
    raise AssertionError("compare inspector table names with METADATA at level 7")


def test_in_memory_storage_shares_one_set_of_stores():
    storage = InMemoryStorage()
    with storage.transactions.read_write() as conn:
        assert storage.stores_for(conn) is storage.stores
