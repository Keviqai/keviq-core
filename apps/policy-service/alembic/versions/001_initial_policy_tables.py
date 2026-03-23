"""Create policy_core tables: workspace_policies, permission_audit_log + outbox.

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

SCHEMA = 'policy_core'


def upgrade() -> None:
    op.create_table(
        'workspace_policies',
        sa.Column('id', UUID(), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('workspace_id', UUID(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('scope', sa.Text(), nullable=False, server_default='workspace'),
        sa.Column('rules', JSONB(), nullable=False, server_default='[]'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        schema=SCHEMA,
    )
    op.create_index('idx_policies_workspace', 'workspace_policies', ['workspace_id'], schema=SCHEMA)

    op.create_table(
        'permission_audit_log',
        sa.Column('id', UUID(), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('actor_id', UUID(), nullable=False),
        sa.Column('workspace_id', UUID(), nullable=False),
        sa.Column('permission', sa.Text(), nullable=False),
        sa.Column('resource_id', sa.Text(), nullable=True),
        sa.Column('decision', sa.Text(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        schema=SCHEMA,
    )
    op.create_index('idx_audit_workspace', 'permission_audit_log', ['workspace_id', 'occurred_at'], schema=SCHEMA)
    op.create_index('idx_audit_actor', 'permission_audit_log', ['actor_id', 'occurred_at'], schema=SCHEMA)

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
    op.drop_index('idx_audit_actor', table_name='permission_audit_log', schema=SCHEMA)
    op.drop_index('idx_audit_workspace', table_name='permission_audit_log', schema=SCHEMA)
    op.drop_table('permission_audit_log', schema=SCHEMA)
    op.drop_index('idx_policies_workspace', table_name='workspace_policies', schema=SCHEMA)
    op.drop_table('workspace_policies', schema=SCHEMA)
