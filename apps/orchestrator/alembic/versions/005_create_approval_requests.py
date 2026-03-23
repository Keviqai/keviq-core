"""Create approval_requests table in orchestrator_core schema.

Revision ID: a005
Revises: a004
Create Date: 2026-03-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = 'a005'
down_revision = 'a004'
branch_labels = None
depends_on = None

SCHEMA = 'orchestrator_core'

VALID_TARGET_TYPES = ('task', 'run', 'step')
VALID_DECISIONS = ('pending', 'approved', 'rejected', 'timed_out', 'cancelled')


def upgrade() -> None:
    op.create_table(
        'approval_requests',
        sa.Column('id', UUID(), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('workspace_id', UUID(), nullable=False),
        sa.Column('target_type', sa.Text(), nullable=False),
        sa.Column('target_id', UUID(), nullable=False),
        sa.Column('requested_by', sa.Text(), nullable=False),
        sa.Column('prompt', sa.Text(), nullable=True),
        sa.Column('timeout_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('decision', sa.Text(), nullable=False, server_default='pending'),
        sa.Column('decided_by_id', UUID(), nullable=True),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('decision_comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.CheckConstraint(
            f"target_type IN {VALID_TARGET_TYPES}",
            name='ck_approval_requests_target_type',
        ),
        sa.CheckConstraint(
            f"decision IN {VALID_DECISIONS}",
            name='ck_approval_requests_decision',
        ),
        schema=SCHEMA,
    )

    op.create_index(
        'idx_approvals_workspace_decision',
        'approval_requests',
        ['workspace_id', 'decision', sa.text('created_at DESC')],
        schema=SCHEMA,
    )
    op.create_index(
        'idx_approvals_target',
        'approval_requests',
        ['target_type', 'target_id'],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index('idx_approvals_target', table_name='approval_requests', schema=SCHEMA)
    op.drop_index('idx_approvals_workspace_decision', table_name='approval_requests', schema=SCHEMA)
    op.drop_table('approval_requests', schema=SCHEMA)
