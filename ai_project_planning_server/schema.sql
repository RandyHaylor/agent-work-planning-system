CREATE TABLE IF NOT EXISTS nodes (
    id          BIGSERIAL PRIMARY KEY,
    parent_id   BIGINT REFERENCES nodes(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    owner       BIGINT,
    state       TEXT NOT NULL DEFAULT 'open' CHECK (state IN ('open', 'blocked', 'done')),
    needs_review BOOLEAN NOT NULL DEFAULT false,
    uuid        UUID UNIQUE,                      -- set for projects (children of plans) and kbs (children of kb)
    visible     BOOLEAN NOT NULL DEFAULT true,    -- projects only: readable by other projects' planners
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS nodes_parent_idx ON nodes(parent_id);

CREATE TABLE IF NOT EXISTS tokens (
    id              BIGSERIAL PRIMARY KEY,
    label           TEXT NOT NULL,
    token_hash      TEXT NOT NULL UNIQUE,
    scope_node_id   BIGINT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    parent_token_id BIGINT REFERENCES tokens(id),
    role            TEXT NOT NULL CHECK (role IN ('planner', 'worker')),
    revoked         BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- The admin is never a token row: it is an in-memory session approved by the user (ai_project_planning_server/admin.py).
ALTER TABLE tokens DROP CONSTRAINT IF EXISTS tokens_role_check;
ALTER TABLE tokens ADD CONSTRAINT tokens_role_check CHECK (role IN ('planner', 'worker'));
-- A token's plaintext can be reissued (rotated) without changing its id, scope, role, or minting chain.
ALTER TABLE tokens ADD COLUMN IF NOT EXISTS rotated_at TIMESTAMPTZ;

-- The plaintext of every token, so the admin (any token) or a planner (its own, and its project's
-- workers) can retrieve it later. Auth still checks tokens.token_hash; this table is only for retrieval.
CREATE TABLE IF NOT EXISTS token_secrets (
    token_id   BIGINT PRIMARY KEY REFERENCES tokens(id) ON DELETE CASCADE,
    plaintext  TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE nodes
    DROP CONSTRAINT IF EXISTS nodes_owner_fkey,
    ADD CONSTRAINT nodes_owner_fkey FOREIGN KEY (owner) REFERENCES tokens(id);
-- owner / author NULL means the admin session wrote it.

-- Which knowledge bases a project may read.
CREATE TABLE IF NOT EXISTS project_kbs (
    project_node_id BIGINT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    kb_node_id      BIGINT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    PRIMARY KEY (project_node_id, kb_node_id)
);

-- Explicit read grants: viewer project may read target project even when target is hidden.
CREATE TABLE IF NOT EXISTS project_visibility (
    viewer_project_id BIGINT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    target_project_id BIGINT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    PRIMARY KEY (viewer_project_id, target_project_id)
);

CREATE TABLE IF NOT EXISTS docs (
    id          BIGSERIAL PRIMARY KEY,
    node_id     BIGINT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    role        TEXT NOT NULL CHECK (role IN ('summary', 'instruction', 'environment', 'report', 'spike', 'escalation', 'question', 'kb_proposal', 'survey', 'approval', 'review')),
    body        TEXT NOT NULL,
    author      BIGINT REFERENCES tokens(id),      -- NULL = admin session
    answer      TEXT,
    resolved    BOOLEAN NOT NULL DEFAULT false,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE docs ALTER COLUMN author DROP NOT NULL;
CREATE INDEX IF NOT EXISTS docs_node_idx ON docs(node_id);
CREATE UNIQUE INDEX IF NOT EXISTS docs_one_summary ON docs(node_id) WHERE role = 'summary';

-- Version history: every UPDATE of a doc stores the previous row. Append-only; nothing deletes from it.
CREATE TABLE IF NOT EXISTS doc_versions (
    id          BIGSERIAL PRIMARY KEY,
    doc_id      BIGINT NOT NULL REFERENCES docs(id) ON DELETE CASCADE,
    body        TEXT NOT NULL,
    answer      TEXT,
    resolved    BOOLEAN NOT NULL,
    author      BIGINT,                             -- NULL = admin session
    edited_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE doc_versions ALTER COLUMN author DROP NOT NULL;
CREATE INDEX IF NOT EXISTS doc_versions_doc_idx ON doc_versions(doc_id);

CREATE OR REPLACE FUNCTION docs_keep_version() RETURNS trigger AS $$
BEGIN
    INSERT INTO doc_versions (doc_id, body, answer, resolved, author, edited_at)
    VALUES (OLD.id, OLD.body, OLD.answer, OLD.resolved, OLD.author, OLD.updated_at);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS docs_keep_version ON docs;
CREATE TRIGGER docs_keep_version BEFORE UPDATE ON docs FOR EACH ROW EXECUTE FUNCTION docs_keep_version();

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Depth limit. Project = direct child of plans = level 1. Level 4 -> needs_review. Level 5 -> refused.
-- kb subtree and the fixed roots (root, kb, plans) are exempt: anything not under plans returns -1.
CREATE OR REPLACE FUNCTION project_level(p_parent BIGINT) RETURNS INT AS $$
DECLARE
    plans_id BIGINT := (SELECT value::bigint FROM meta WHERE key = 'plans_node_id');
    lvl INT := 0;
    cur BIGINT := p_parent;
    hops INT := 0;
BEGIN
    IF plans_id IS NULL THEN RETURN -1; END IF;
    WHILE cur IS NOT NULL LOOP
        IF cur = plans_id THEN RETURN lvl + 1; END IF;
        lvl := lvl + 1;
        hops := hops + 1;
        IF hops > 64 THEN RETURN -1; END IF;  -- cycle guard: treat as exempt rather than hang
        SELECT parent_id INTO cur FROM nodes WHERE id = cur;
    END LOOP;
    RETURN -1;
END;
$$ LANGUAGE plpgsql;

-- Depth guard, plus: a direct child of plans or of kb gets a uuid (project / knowledge base identity).
CREATE OR REPLACE FUNCTION nodes_depth_guard() RETURNS trigger AS $$
DECLARE
    lvl INT;
    kb_id BIGINT := (SELECT value::bigint FROM meta WHERE key = 'kb_node_id');
BEGIN
    lvl := project_level(NEW.parent_id);
    IF lvl >= 5 THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'depth limit: level 5 is refused. Open a separate project under plans for that branch, with its own plan and the same procedure.';
    END IF;
    IF lvl = 4 THEN NEW.needs_review := true; END IF;
    IF NEW.uuid IS NULL AND (lvl = 1 OR (kb_id IS NOT NULL AND NEW.parent_id = kb_id)) THEN
        NEW.uuid := gen_random_uuid();
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS nodes_depth_guard ON nodes;
CREATE TRIGGER nodes_depth_guard BEFORE INSERT ON nodes FOR EACH ROW EXECUTE FUNCTION nodes_depth_guard();

-- Node-level kb override: the planner narrows (or widens) which kbs workers scoped at or beneath
-- this node may read. The nearest ancestor override wins; without one, the project's set applies.
-- A row in node_kb_overrides with no node_kbs rows means "no kbs" for that subtree.
CREATE TABLE IF NOT EXISTS node_kb_overrides (
    node_id BIGINT PRIMARY KEY REFERENCES nodes(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS node_kbs (
    node_id    BIGINT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    kb_node_id BIGINT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    PRIMARY KEY (node_id, kb_node_id)
);
