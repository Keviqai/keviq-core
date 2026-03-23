"""Add 'tool_call' to approval_requests target_type check constraint.

O5-S1: Human control around agent actions — tool calls can now be
approval targets, enabling human-in-the-loop before risky tool execution.

Revision ID: a010
Revises: a009
Create Date: 2026-03-20
"""
from alembic import op

revision = 'a010'
down_revision = 'a009'
branch_labels = None
depends_on = None

SCHEMA = 'orchestrator_core'


def upgrade() -> None:
    op.drop_constraint(
        'ck_approval_requests_target_type',
        'approval_requests',
        schema=SCHEMA,
    )
    op.create_check_constraint(
        'ck_approval_requests_target_type',
        'approval_requests',
        "target_type IN ('task', 'run', 'step', 'artifact', 'tool_call')",
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_constraint(
        'ck_approval_requests_target_type',
        'approval_requests',
        schema=SCHEMA,
    )
    op.create_check_constraint(
        'ck_approval_requests_target_type',
        'approval_requests',
        "target_type IN ('task', 'run', 'step', 'artifact')",
        schema=SCHEMA,
    )
