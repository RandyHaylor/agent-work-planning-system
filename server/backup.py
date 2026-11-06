"""Backup of a node subtree to disk.

Pure part: ``render`` turns plain dicts into a mapping of relative path -> file text.
IO part: ``write`` puts that mapping under a directory, replacing stale files.
Glue: ``backup_root_for`` and ``backup_subtree`` pull rows from a connection.

Layout under the destination dir:
    tree.json                          every node in the subtree
    docs/<node-id>-<role>-<doc-id>.md  one file per doc: header block, blank line, body verbatim
"""
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

NODE_FIELDS = ("id", "parent_id", "title", "state", "needs_review", "owner", "created_at")


class BackupError(RuntimeError):
    pass


def slug(title: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-").lower()
    return s or "untitled"


def _iso(v: Any) -> Any:
    return v.isoformat() if hasattr(v, "isoformat") else v


def render(nodes: Iterable[Mapping[str, Any]], docs: Iterable[Mapping[str, Any]],
           authors: Optional[Mapping[int, str]] = None) -> dict[str, str]:
    """Return {relative path: content}. Nodes sorted by id; docs by id."""
    authors = authors or {}
    tree = [{k: _iso(n.get(k)) for k in NODE_FIELDS} for n in sorted(nodes, key=lambda n: n["id"])]
    out = {"tree.json": json.dumps(tree, indent=2) + "\n"}
    for d in sorted(docs, key=lambda d: d["id"]):
        header = [
            f"doc: {d['id']}",
            f"node: {d['node_id']}",
            f"role: {d['role']}",
            f"author: {authors.get(d['author'], d['author'])}",
            f"created_at: {_iso(d.get('created_at'))}",
            f"updated_at: {_iso(d.get('updated_at'))}",
        ]
        if d.get("answer") is not None:
            header.append(f"answer: {d['answer']}")
        if d.get("resolved") is not None:
            header.append(f"resolved: {str(bool(d['resolved'])).lower()}")
        out[f"docs/{d['node_id']}-{d['role']}-{d['id']}.md"] = "\n".join(header) + "\n\n" + d["body"]
    return out


def write(dest: Path, files: Mapping[str, str]) -> None:
    """Write files under dest. Files under dest/docs not in ``files`` are removed."""
    try:
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "docs").mkdir(exist_ok=True)
        for rel, content in files.items():
            p = dest / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        for p in (dest / "docs").iterdir():
            if f"docs/{p.name}" not in files:
                p.unlink()
    except OSError as e:
        raise BackupError(str(e)) from e


def backup_root_for(chain: list[int], plans_id: int, kb_id: int) -> Optional[int]:
    """Given [node, parent, ..., root], return the subtree root to back up:
    the project (direct child of plans), kb for anything under kb, else None."""
    if kb_id in chain:
        return kb_id
    if plans_id in chain:
        i = chain.index(plans_id)
        return chain[i - 1] if i > 0 else None
    return None


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
    authors = {t["id"]: t["label"] for t in conn.execute("SELECT id, label FROM tokens").fetchall()}
    top = next(r for r in rows if r["id"] == root_id)
    name = "kb" if root_id == kb_id else f"{root_id}-{slug(top['title'])}"
    dest = dest_base / name
    write(dest, render(rows, docs, authors))
    return dest
