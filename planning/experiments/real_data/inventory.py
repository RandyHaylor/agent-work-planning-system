"""Inventory of real node content across the local Postgres databases (read-only).
Usage (repo root): uv run python -I planning/experiments/real_data/inventory.py
Prints per database: nodes, content items, and content items not written by the live test scripts."""
from __future__ import annotations

import sys
from pathlib import Path

import sqlalchemy as sa

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
from live_smoke_test import db_password  # noqa: E402


def engine(db: str):
    return sa.create_engine(f"postgresql+psycopg://planner:{db_password()}@127.0.0.1:5433/{db}")


def main():
    with engine("postgres").connect() as conn:
        dbs = [r[0] for r in conn.execute(sa.text("SELECT datname FROM pg_database WHERE NOT datistemplate"))]
    for db in dbs:
        try:
            with engine(db).connect() as conn:
                tables = {r[0] for r in conn.execute(sa.text(
                    "SELECT tablename FROM pg_tables WHERE schemaname='public'"))}
                if "node_content" not in tables:
                    print(f"{db}: (not a planning_system database)")
                    continue
                nodes = conn.execute(sa.text("SELECT count(*) FROM nodes")).scalar()
                items = conn.execute(sa.text("SELECT count(*) FROM node_content")).scalar()
                projects = [r[0] for r in conn.execute(sa.text(
                    "SELECT title FROM nodes WHERE parent_id IS NULL ORDER BY id"))]
                print(f"{db}: {nodes} nodes, {items} content items, projects: {projects[:15]}")
        except Exception as exc:
            print(f"{db}: error {type(exc).__name__}")


if __name__ == "__main__":
    main()
