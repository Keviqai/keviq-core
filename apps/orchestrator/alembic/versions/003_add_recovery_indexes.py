"""Add indexes for orchestrator recovery sweep on stuck runs and steps.

Revision ID: a003
Revises: a002
Create Date: 2026-03-13
"""
from alembic import op

revision = 'a003'
down_revision = 'a002'
branch_labels = None
depends_on = None

_SCHEMA = 'orchestrator_core'


def upgrade() -> None:
    op.create_index(
        'idx_runs_status_created',
        'runs',
        ['run_status', 'created_at'],
        schema=_SCHEMA,
        postgresql_where="run_status NOT IN ('completed', 'failed', 'cancelled')",
    )
    op.create_index(
        'idx_steps_status_created',
        'steps',
        ['step_status', 'created_at'],
        schema=_SCHEMA,
        postgresql_where="step_status NOT IN ('completed', 'failed', 'skipped', 'cancelled')",
    )


def downgrade() -> None:
    op.drop_index(
        'idx_steps_status_created',
        table_name='steps',
        schema=_SCHEMA,
    )
    op.drop_index(
        'idx_runs_status_created',
        table_name='runs',
        schema=_SCHEMA,
    )
