"""supersede: candidates table, trial / quote-check review columns, full-text index on references
(05-spec-reference-supersede.md)

Revision ID: 0004_supersede
Revises: 0003_node_reviews
Create Date: 2026-11-28 15:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0004_supersede'
down_revision = '0003_node_reviews'
branch_labels = None
depends_on = None

# the same expression postgres_reference_store.search_text queries (a tsvector holds at most 1 MB)
FULL_TEXT = "to_tsvector('english'::regconfig, left(text, 200000))"


def upgrade() -> None:
    op.create_table('supersede_candidates',
    sa.Column('id', sa.Text(), nullable=False),
    sa.Column('project_id', sa.BigInteger(), nullable=False),
    sa.Column('old_reference_id', sa.Text(), nullable=False),
    sa.Column('new_reference_id', sa.Text(), nullable=False),
    sa.Column('kind', sa.Text(), nullable=False),
    sa.Column('found_by', sa.Text(), nullable=False),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('proposed_by', sa.Text(), nullable=True),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('decided_by', sa.Text(), nullable=True),
    sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('request_node_id', sa.BigInteger(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_supersede_candidates_old_reference_id'), 'supersede_candidates', ['old_reference_id'],
                    unique=False)
    op.create_index(op.f('ix_supersede_candidates_new_reference_id'), 'supersede_candidates', ['new_reference_id'],
                    unique=False)
    op.create_index('ix_supersede_candidates_project_status', 'supersede_candidates', ['project_id', 'status'],
                    unique=False)
    op.add_column('content_reviews', sa.Column('against_reference_id', sa.Text(), nullable=True))
    op.add_column('content_reviews', sa.Column('replaces_reference_id', sa.Text(), nullable=True))
    op.add_column('content_reviews', sa.Column('candidate_id', sa.Text(), nullable=True))
    op.add_column('content_reviews', sa.Column('findings', sa.JSON(), nullable=False, server_default='[]'))
    op.create_index(op.f('ix_content_reviews_candidate_id'), 'content_reviews', ['candidate_id'], unique=False)
    op.execute(f'CREATE INDEX ix_references_full_text ON "references" USING gin ({FULL_TEXT})')


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS ix_references_full_text')
    op.drop_index(op.f('ix_content_reviews_candidate_id'), table_name='content_reviews')
    op.drop_column('content_reviews', 'findings')
    op.drop_column('content_reviews', 'candidate_id')
    op.drop_column('content_reviews', 'replaces_reference_id')
    op.drop_column('content_reviews', 'against_reference_id')
    op.drop_index('ix_supersede_candidates_project_status', table_name='supersede_candidates')
    op.drop_index(op.f('ix_supersede_candidates_new_reference_id'), table_name='supersede_candidates')
    op.drop_index(op.f('ix_supersede_candidates_old_reference_id'), table_name='supersede_candidates')
    op.drop_table('supersede_candidates')
