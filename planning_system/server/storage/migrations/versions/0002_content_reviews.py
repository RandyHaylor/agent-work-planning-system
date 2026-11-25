"""content reviews

Revision ID: 0002_content_reviews
Revises: 0001_initial
Create Date: 2026-11-25 18:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0002_content_reviews'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('content_reviews',
    sa.Column('id', sa.Text(), nullable=False),
    sa.Column('project_id', sa.BigInteger(), nullable=False),
    sa.Column('node_id', sa.BigInteger(), nullable=False),
    sa.Column('content_reference_id', sa.Text(), nullable=False),
    sa.Column('claim_tag', sa.Text(), nullable=False),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('reviewer', sa.Text(), nullable=True),
    sa.Column('taken_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('suggested_title', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_content_reviews_node_id'), 'content_reviews', ['node_id'], unique=False)
    op.create_index(op.f('ix_content_reviews_content_reference_id'), 'content_reviews',
                    ['content_reference_id'], unique=False)
    op.create_index('ix_content_reviews_project_status', 'content_reviews', ['project_id', 'status'],
                    unique=False)


def downgrade() -> None:
    op.drop_index('ix_content_reviews_project_status', table_name='content_reviews')
    op.drop_index(op.f('ix_content_reviews_content_reference_id'), table_name='content_reviews')
    op.drop_index(op.f('ix_content_reviews_node_id'), table_name='content_reviews')
    op.drop_table('content_reviews')
