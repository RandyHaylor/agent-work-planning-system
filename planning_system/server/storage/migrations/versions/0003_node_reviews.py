"""node reviews: a review record may be about a whole node (guess screen, build log #60 (5))

Revision ID: 0003_node_reviews
Revises: 0002_content_reviews
Create Date: 2026-11-28 12:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0003_node_reviews'
down_revision = '0002_content_reviews'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('content_reviews', sa.Column('target_kind', sa.Text(), nullable=False,
                                               server_default='content'))
    op.alter_column('content_reviews', 'content_reference_id', existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM content_reviews WHERE target_kind <> 'content'")
    op.alter_column('content_reviews', 'content_reference_id', existing_type=sa.Text(), nullable=False)
    op.drop_column('content_reviews', 'target_kind')
