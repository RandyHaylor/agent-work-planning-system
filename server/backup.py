"""Backup of a node subtree to disk.

Pure part: ``render`` turns plain dicts into a mapping of relative path -> file text.
IO part: ``write`` puts that mapping under a directory atomically: the whole set is
written to a sibling temp dir, then swapped into place, so a crash never leaves a
half-updated directory and stale files never survive.
Glue: ``backup_root_for`` and ``backup_subtree`` pull rows from a connection.

Layout: one directory per project, named by the project's uuid, under the backup dir;
one directory per knowledge base under ``kb/<uuid>/``. Inside:
    title                                      the project's or kb's title
    tree.json                                  every node in the subtree
    docs/<node-id>-<role>-<doc-id>.md          one file per doc: header block, blank line, body verbatim
    docs/<node-id>-<role>-<doc-id>.history.md  previous versions, oldest first; only when any exist
"""
import json
import re
import shutil
import uuid as _uuid
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

NODE_FIELDS = ("id", "parent_id", "uuid", "title", "state", "needs_review", "visible", "owner", "created_at")


class BackupError(RuntimeError):
    pass


def slug(title: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-").lower()
    return s or "untitled"


def _iso(v: Any) -> Any:
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if isinstance(v, _uuid.UUID):
        return str(v)
    return v


def _header(d: Mapping[str, Any], authors: Mapping[int, str], when_key: str) -> list[str]:
    header = [
        f"doc: {d['doc_id'] if 'doc_id' in d else d['id']}",
        f"node: {d['node_id']}",
        f"role: {d['role']}",
        f"author: {authors.get(d['author'], d['author'])}",
    ]
    if when_key == "updated_at":
        header.append(f"created_at: {_iso(d.get('created_at'))}")
    header.append(f"{when_key}: {_iso(d.get(when_key))}")
    if d.get("answer") is not None:
        header.append(f"answer: {d['answer']}")
    if d.get("resolved") is not None:
        header.append(f"resolved: {str(bool(d['resolved'])).lower()}")
    return header


def render(nodes: Iterable[Mapping[str, Any]], docs: Iterable[Mapping[str, Any]],
           authors: Optional[Mapping[int, str]] = None,
           versions: Optional[Mapping[int, Iterable[Mapping[str, Any]]]] = None,
           title: Optional[str] = None) -> dict[str, str]:
    """Return {relative path: content}. Nodes sorted by id; docs by id.
    ``versions`` maps doc id -> previous versions (each with body, answer, resolved, author, edited_at).
    ``title`` adds a ``title`` file naming the subtree."""
    authors = authors or {}
    versions = versions or {}
    tree = [{k: _iso(n.get(k)) for k in NODE_FIELDS} for n in sorted(nodes, key=lambda n: n["id"])]
    out = {"tree.json": json.dumps(tree, indent=2) + "\n"}
    if title is not None:
        out["title"] = title + "\n"
    for d in sorted(docs, key=lambda d: d["id"]):
        stem = f"docs/{d['node_id']}-{d['role']}-{d['id']}"
        out[f"{stem}.md"] = "\n".join(_header(d, authors, "updated_at")) + "\n\n" + d["body"]
        old = list(versions.get(d["id"], []))
        if old:
            parts = []
            for v in sorted(old, key=lambda v: (v.get("edited_at") or "", v.get("id", 0))):
                row = {**v, "doc_id": d["id"], "node_id": d["node_id"], "role": d["role"]}
                parts.append("\n".join(_header(row, authors, "edited_at")) + "\n\n" + v["body"])
            out[f"{stem}.history.md"] = "\n\n----\n\n".join(parts)
    return out


def write(dest: Path, files: Mapping[str, str]) -> None:
    """Atomically replace dest with exactly ``files``: build in a temp sibling, then swap."""
    tmp = dest.parent / (dest.name + ".tmp")
    old = dest.parent / (dest.name + ".old")
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        for leftover in (tmp, old):
            if leftover.exists():
                shutil.rmtree(leftover)
        (tmp / "docs").mkdir(parents=True)
        for rel, content in files.items():
            p = tmp / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        if dest.exists():
            dest.rename(old)
        tmp.rename(dest)
        if old.exists():
            shutil.rmtree(old)
    except OSError as e:
        raise BackupError(str(e)) from e


def backup_root_for(chain: list[int], plans_id: int, kb_id: int) -> Optional[int]:
    """Given [node, parent, ..., root], return the subtree root to back up:
    the project (direct child of plans) or the kb (direct child of the kb container), else None."""
    for container in (kb_id, plans_id):
        if container in chain:
            i = chain.index(container)
            return chain[i - 1] if i > 0 else None
    return None


def dest_for(base: Path, top: Mapping[str, Any], kb_id: int) -> Path:
    """Project: <base>/<uuid>. Knowledge base: <base>/kb/<uuid>. Falls back to id-slug if no uuid."""
    name = str(top["uuid"]) if top.get("uuid") else f"{top['id']}-{slug(top['title'])}"
    return (base / "kb" / name) if top.get("parent_id") == kb_id else (base / name)


def backup_subtree(conn, root_id: int, dest_base: Path, kb_id: int) -> Path:
    rows = conn.execute(
        """
        WITH RECURSIVE sub AS (
            SELECT * FROM nodes WHERE id = %s
            UNION ALL SELECT n.* FROM nodes n JOIN sub s ON n.parent_id = s.id
        ) SELECT * FROM sub
        """,
        (root_id,),
    ).fetchall()
    ids = [r["id"] for r in rows]
    docs = conn.execute("SELECT * FROM docs WHERE node_id = ANY(%s)", (ids,)).fetchall()
    doc_ids = [d["id"] for d in docs]
    versions: dict[int, list] = {}
    for v in conn.execute("SELECT * FROM doc_versions WHERE doc_id = ANY(%s) ORDER BY id", (doc_ids,)).fetchall():
        versions.setdefault(v["doc_id"], []).append(v)
    authors = {t["id"]: t["label"] for t in conn.execute("SELECT id, label FROM tokens").fetchall()}
    top = next(r for r in rows if r["id"] == root_id)
    dest = dest_for(dest_base, top, kb_id)
    write(dest, render(rows, docs, authors, versions, title=top["title"]))
    return dest
