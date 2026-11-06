CREATE TABLE IF NOT EXISTS nodes (
    id          BIGSERIAL PRIMARY KEY,
    parent_id   BIGINT REFERENCES nodes(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    owner       BIGINT,
    state       TEXT NOT NULL DEFAULT 'open' CHECK (state IN ('open', 'blocked', 'done')),
    needs_review BOOLEAN NOT NULL DEFAULT false,
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

ALTER TABLE nodes
    DROP CONSTRAINT IF EXISTS nodes_owner_fkey,
    ADD CONSTRAINT nodes_owner_fkey FOREIGN KEY (owner) REFERENCES tokens(id);

CREATE TABLE IF NOT EXISTS docs (
    id          BIGSERIAL PRIMARY KEY,
    node_id     BIGINT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    role        TEXT NOT NULL CHECK (role IN ('summary', 'instruction', 'environment', 'report', 'spike', 'escalation', 'question', 'kb_proposal', 'survey', 'approval', 'review')),
    body        TEXT NOT NULL,
    author      BIGINT NOT NULL REFERENCES tokens(id),
    answer      TEXT,
    resolved    BOOLEAN NOT NULL DEFAULT false,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS docs_node_idx ON docs(node_id);
CREATE UNIQUE INDEX IF NOT EXISTS docs_one_summary ON docs(node_id) WHERE role = 'summary';

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
BEGIN
    IF plans_id IS NULL THEN RETURN -1; END IF;
    WHILE cur IS NOT NULL LOOP
        IF cur = plans_id THEN RETURN lvl + 1; END IF;
        lvl := lvl + 1;
        SELECT parent_id INTO cur FROM nodes WHERE id = cur;
    END LOOP;
    RETURN -1;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION nodes_depth_guard() RETURNS trigger AS $$
DECLARE lvl INT;
BEGIN
    lvl := project_level(NEW.parent_id);
    IF lvl >= 5 THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'depth limit: level 5 is refused. Open a separate project under plans for that branch, with its own plan and the same procedure.';
    END IF;
    IF lvl = 4 THEN NEW.needs_review := true; END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS nodes_depth_guard ON nodes;
CREATE TRIGGER nodes_depth_guard BEFORE INSERT ON nodes FOR EACH ROW EXECUTE FUNCTION nodes_depth_guard();
