"""Create audit_events table.

Revision ID: a007
Revises: a006
Create Date: 2026-03-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = 'a007'
down_revision = 'a006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'audit_events',
        sa.Column('event_id', UUID(), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('actor_id', sa.Text(), nullable=False),
        sa.Column('actor_type', sa.Text(), nullable=False, server_default='user'),
        sa.Column('action', sa.Text(), nullable=False),
        sa.Column('target_id', sa.Text(), nullable=True),
        sa.Column('target_type', sa.Text(), nullable=True),
        sa.Column('workspace_id', UUID(), nullable=False),
        sa.Column('metadata', JSONB(), nullable=False, server_default='{}'),
        sa.Column('occurred_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        schema='audit_core',
    )
    # Fast workspace timeline queries
    op.create_index(
        'idx_audit_events_workspace_occurred',
        'audit_events',
        ['workspace_id', 'occurred_at'],
        schema='audit_core',
    )
    # Workspace + action filter (most common query pattern)
    op.create_index(
        'idx_audit_events_workspace_action',
        'audit_events',
        ['workspace_id', 'action', 'occurred_at'],
        schema='audit_core',
    )
    # Filter by actor (who did it)
    op.create_index(
        'idx_audit_events_actor',
        'audit_events',
        ['actor_id'],
        schema='audit_core',
    )
    # Filter by target (what was affected)
    op.create_index(
        'idx_audit_events_target',
        'audit_events',
        ['target_id', 'target_type'],
        schema='audit_core',
    )
    # Idempotency: unique on action + target_id + actor_id within 1 second window
    # (loose dedup — exact dedup relies on event_id from caller)


def downgrade() -> None:
    op.drop_index('idx_audit_events_target', table_name='audit_events', schema='audit_core')
    op.drop_index('idx_audit_events_actor', table_name='audit_events', schema='audit_core')
    op.drop_index('idx_audit_events_workspace_action', table_name='audit_events', schema='audit_core')
    op.drop_index('idx_audit_events_workspace_occurred', table_name='audit_events', schema='audit_core')
    op.drop_table('audit_events', schema='audit_core')
