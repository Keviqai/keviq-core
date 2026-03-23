"""Create secret_core tables: workspace_secrets + outbox.

Revision ID: s001
Revises:
Create Date: 2026-03-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = 's001'
down_revision = None
branch_labels = None
depends_on = None

SCHEMA = 'secret_core'


def upgrade() -> None:
    op.create_table(
        'workspace_secrets',
        sa.Column('id', UUID(), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('workspace_id', UUID(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('secret_type', sa.Text(), nullable=False),
        sa.Column('secret_hash', sa.Text(), nullable=False),
        sa.Column('masked_display', sa.Text(), nullable=False),
        sa.Column('created_by_id', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.CheckConstraint("secret_type IN ('api_key', 'token', 'password', 'custom')", name='ck_secret_type'),
        schema=SCHEMA,
    )
    op.create_index('idx_secrets_workspace', 'workspace_secrets', ['workspace_id'], schema=SCHEMA)
    op.create_index(
        'idx_secrets_workspace_created',
        'workspace_secrets',
        ['workspace_id', sa.text('created_at DESC')],
        schema=SCHEMA,
    )

    op.create_table(
        'outbox',
        sa.Column('id', UUID(), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('event_type', sa.Text(), nullable=False),
        sa.Column('payload', sa.Text(), nullable=False),
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
    op.drop_index('idx_secrets_workspace_created', table_name='workspace_secrets', schema=SCHEMA)
    op.drop_index('idx_secrets_workspace', table_name='workspace_secrets', schema=SCHEMA)
    op.drop_table('workspace_secrets', schema=SCHEMA)
