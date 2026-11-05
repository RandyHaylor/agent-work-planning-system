import os
import hashlib
import secrets
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

DSN = os.environ.get("PLANNER_DSN", "postgresql://planner:planner@localhost:5433/planner")
SCHEMA = Path(__file__).with_name("schema.sql")


def connect():
    return psycopg.connect(DSN, row_factory=dict_row, autocommit=True)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_token() -> str:
    return "pln_" + secrets.token_urlsafe(32)


def apply_schema(conn):
    conn.execute(SCHEMA.read_text())


def ancestors_fn(conn):
    """Return a function node_id -> [node_id, parent, ..., root]. Empty if unknown."""
    def anc(node_id: int) -> list[int]:
        rows = conn.execute(
            """
            WITH RECURSIVE chain AS (
                SELECT id, parent_id, 0 AS depth FROM nodes WHERE id = %s
                UNION ALL
                SELECT n.id, n.parent_id, c.depth + 1 FROM nodes n JOIN chain c ON n.id = c.parent_id
            )
            SELECT id FROM chain ORDER BY depth
            """,
            (node_id,),
        ).fetchall()
        return [r["id"] for r in rows]
    return anc


def meta_get(conn, key: str):
    row = conn.execute("SELECT value FROM meta WHERE key = %s", (key,)).fetchone()
    return row["value"] if row else None
