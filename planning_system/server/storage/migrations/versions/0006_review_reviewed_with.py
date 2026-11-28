"""content_reviews.reviewed_with: backend, model, profile, granularity and prompt version of each submitted verdict
(build log #70)

Revision ID: 0006_review_reviewed_with
Revises: 0005_halts
Create Date: 2026-11-28 19:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0006_review_reviewed_with'
down_revision = '0005_halts'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('content_reviews', sa.Column('reviewed_with', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('content_reviews', 'reviewed_with')
