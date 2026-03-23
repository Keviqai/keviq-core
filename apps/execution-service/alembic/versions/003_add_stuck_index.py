"""Add composite index for recovery sweep on stuck sandboxes.

Revision ID: a010
Revises: a009
Create Date: 2026-03-13
"""
from alembic import op

revision = 'a010'
down_revision = 'a009'
branch_labels = None
depends_on = None

_SCHEMA = 'execution_core'


def upgrade() -> None:
    op.create_index(
        'idx_sandboxes_stuck',
        'sandboxes',
        ['sandbox_status', 'updated_at'],
        schema=_SCHEMA,
        postgresql_where="sandbox_status IN ('provisioning', 'executing')",
    )


def downgrade() -> None:
    op.drop_index(
        'idx_sandboxes_stuck',
        table_name='sandboxes',
        schema=_SCHEMA,
    )
