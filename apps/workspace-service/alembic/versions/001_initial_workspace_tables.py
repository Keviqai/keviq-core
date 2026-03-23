"""Create workspace_core tables: workspaces, members + outbox.

Revision ID: a001
Revises:
Create Date: 2026-03-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = 'a001'
down_revision = None
branch_labels = None
depends_on = None

SCHEMA = 'workspace_core'


def upgrade() -> None:
    op.create_table(
        'workspaces',
        sa.Column('id', UUID(), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('slug', sa.Text(), nullable=False, unique=True),
        sa.Column('display_name', sa.Text(), nullable=False),
        sa.Column('plan', sa.Text(), nullable=False, server_default='personal'),
        sa.Column('deployment_mode', sa.Text(), nullable=False, server_default='local'),
        sa.Column('owner_id', UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('settings', JSONB(), nullable=False, server_default='{}'),
        schema=SCHEMA,
    )
    # unique=True on slug already creates an index — only add owner index
    op.create_index('idx_workspaces_owner', 'workspaces', ['owner_id'], schema=SCHEMA)

    op.create_table(
        'members',
        sa.Column('id', UUID(), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('workspace_id', UUID(), sa.ForeignKey(f'{SCHEMA}.workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', UUID(), nullable=False),
        sa.Column('role', sa.Text(), nullable=False, server_default='viewer'),
        sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('invited_by_id', UUID(), nullable=True),
        sa.UniqueConstraint('workspace_id', 'user_id', name='uq_members_workspace_user'),
        schema=SCHEMA,
    )
    # uq_members_workspace_user covers workspace_id lookups (leading column)
    op.create_index('idx_members_user', 'members', ['user_id'], schema=SCHEMA)

    # NOTE: members.user_id does NOT reference identity_core.users.id
    # This is intentional — no cross-schema FK (S1 principle).
    # Consistency is maintained via events.

    op.create_table(
        'outbox',
        sa.Column('id', UUID(), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('event_type', sa.Text(), nullable=False),
        sa.Column('payload', JSONB(), nullable=False),
        sa.Column('correlation_id', UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
        schema=SCHEMA,
    )
    op.create_index(
        'idx_outbox_unpublished',
        'outbox',
        ['created_at'],
        schema=SCHEMA,
        postgresql_where=sa.text('published_at IS NULL'),
    )


def downgrade() -> None:
    op.drop_index('idx_outbox_unpublished', table_name='outbox', schema=SCHEMA)
    op.drop_table('outbox', schema=SCHEMA)
    op.drop_index('idx_members_user', table_name='members', schema=SCHEMA)
    op.drop_table('members', schema=SCHEMA)
    op.drop_index('idx_workspaces_owner', table_name='workspaces', schema=SCHEMA)
    op.drop_table('workspaces', schema=SCHEMA)
