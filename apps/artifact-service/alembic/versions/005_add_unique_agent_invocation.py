"""Add unique partial index on agent_invocation_id.

Enforces one artifact per invocation (Slice 5 invariant).
NULLs are excluded — tool-direct artifacts have no invocation.

Revision ID: a007
Revises: a006
Create Date: 2026-03-13
"""
from alembic import op

revision = 'a007'
down_revision = 'a006'
branch_labels = None
depends_on = None

SCHEMA = 'artifact_core'


def upgrade() -> None:
    op.create_index(
        'uq_artifacts_agent_invocation_id',
        'artifacts',
        ['agent_invocation_id'],
        unique=True,
        schema=SCHEMA,
        postgresql_where='agent_invocation_id IS NOT NULL',
    )
    # Drop the old non-unique index — superseded by the unique partial index
    op.drop_index(
        'idx_artifacts_agent_invocation_id',
        table_name='artifacts',
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.create_index(
        'idx_artifacts_agent_invocation_id',
        'artifacts',
        ['agent_invocation_id'],
        schema=SCHEMA,
    )
    op.drop_index(
        'uq_artifacts_agent_invocation_id',
        table_name='artifacts',
        schema=SCHEMA,
    )
