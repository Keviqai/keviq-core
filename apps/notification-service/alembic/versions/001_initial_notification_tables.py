"""Create notification_core tables: notifications.

Revision ID: n001
Revises:
Create Date: 2026-03-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = 'n001'
down_revision = None
branch_labels = None
depends_on = None

SCHEMA = 'notification_core'


def upgrade() -> None:
    op.create_table(
        'notifications',
        sa.Column('id', UUID(), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('workspace_id', UUID(), nullable=False),
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False, server_default=''),
        sa.Column('category', sa.Text(), nullable=False, server_default='system'),
        sa.Column('priority', sa.Text(), nullable=False, server_default='normal'),
        sa.Column('link', sa.Text(), nullable=False, server_default=''),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "category IN ('task', 'run', 'approval', 'artifact', 'workspace', 'system')",
            name='ck_notification_category',
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'urgent')",
            name='ck_notification_priority',
        ),
        schema=SCHEMA,
    )
    op.create_index(
        'idx_notifications_workspace_user_unread',
        'notifications',
        ['workspace_id', 'user_id', 'is_read', sa.text('created_at DESC')],
        schema=SCHEMA,
    )
    op.create_index(
        'idx_notifications_workspace_user',
        'notifications',
        ['workspace_id', 'user_id'],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index('idx_notifications_workspace_user', table_name='notifications', schema=SCHEMA)
    op.drop_index('idx_notifications_workspace_user_unread', table_name='notifications', schema=SCHEMA)
    op.drop_table('notifications', schema=SCHEMA)
