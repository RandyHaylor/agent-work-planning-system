"""halts: the admin's stop switch, one row per halt in force (build log #68)

Revision ID: 0005_halts
Revises: 0004_supersede
Create Date: 2026-11-28 18:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0005_halts'
down_revision = '0004_supersede'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('halts',
    sa.Column('scope', sa.Text(), nullable=False),
    sa.Column('project_id', sa.BigInteger(), nullable=True),
    sa.Column('halted_by', sa.Text(), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('halted_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('scope')
    )


def downgrade() -> None:
    op.drop_table('halts')
