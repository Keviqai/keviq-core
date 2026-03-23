"""Add 'artifact' to approval_requests target_type check constraint.

Revision ID: a008
Revises: a007
Create Date: 2026-03-18
"""
from alembic import op

revision = 'a008'
down_revision = 'a007'
branch_labels = None
depends_on = None

SCHEMA = 'orchestrator_core'


def upgrade() -> None:
    # Drop the old constraint (task/run/step only) and replace with extended one
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


def downgrade() -> None:
    op.drop_constraint(
        'ck_approval_requests_target_type',
        'approval_requests',
        schema=SCHEMA,
    )
    op.create_check_constraint(
        'ck_approval_requests_target_type',
        'approval_requests',
        "target_type IN ('task', 'run', 'step')",
        schema=SCHEMA,
    )
