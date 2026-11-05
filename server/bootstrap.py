"""Create schema, root tree (root -> kb, plans) and print the root token once."""
from server import db


def main():
    with db.connect() as conn:
        db.apply_schema(conn)
        if db.meta_get(conn, "root_node_id"):
            print("Already bootstrapped. Root token was printed at first bootstrap and is not stored.")
            return
        root = conn.execute("INSERT INTO nodes (parent_id, title) VALUES (NULL, 'root') RETURNING id").fetchone()["id"]
        raw = db.new_token()
        tok = conn.execute(
            "INSERT INTO tokens (label, token_hash, scope_node_id, can_spawn) VALUES ('root', %s, %s, true) RETURNING id",
            (db.hash_token(raw), root),
        ).fetchone()["id"]
        conn.execute("UPDATE nodes SET owner = %s WHERE id = %s", (tok, root))
        conn.execute("INSERT INTO docs (node_id, role, body, author) VALUES (%s, 'summary', 'Root of the planning tree.', %s)", (root, tok))
        kb = conn.execute("INSERT INTO nodes (parent_id, title, owner) VALUES (%s, 'kb', %s) RETURNING id", (root, tok)).fetchone()["id"]
        conn.execute("INSERT INTO docs (node_id, role, body, author) VALUES (%s, 'summary', 'Knowledge base: product, company, broader context. Read-only to agents.', %s)", (kb, tok))
        plans = conn.execute("INSERT INTO nodes (parent_id, title, owner) VALUES (%s, 'plans', %s) RETURNING id", (root, tok)).fetchone()["id"]
        conn.execute("INSERT INTO docs (node_id, role, body, author) VALUES (%s, 'summary', 'All plans live beneath this node.', %s)", (plans, tok))
        for k, v in (("root_node_id", root), ("kb_node_id", kb), ("plans_node_id", plans), ("root_token_id", tok)):
            conn.execute("INSERT INTO meta (key, value) VALUES (%s, %s)", (k, str(v)))
        print(f"root_node_id={root} kb_node_id={kb} plans_node_id={plans}")
        print(f"ROOT_TOKEN={raw}")


if __name__ == "__main__":
    main()
