"""Create identity_core tables: users + outbox.

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

SCHEMA = 'identity_core'


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', UUID(), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('email', sa.Text(), nullable=False, unique=True),
        sa.Column('display_name', sa.Text(), nullable=False),
        sa.Column('password_hash', sa.Text(), nullable=True),  # nullable for OAuth/SSO users
        sa.Column('auth_provider', sa.Text(), nullable=False, server_default='local'),
        sa.Column('auth_provider_id', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('last_active_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        schema=SCHEMA,
    )
    # unique=True on email already creates an index — no separate create_index needed
    op.create_index('idx_users_auth_provider', 'users', ['auth_provider', 'auth_provider_id'], schema=SCHEMA)

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
    op.drop_index('idx_users_auth_provider', table_name='users', schema=SCHEMA)
    op.drop_table('users', schema=SCHEMA)
