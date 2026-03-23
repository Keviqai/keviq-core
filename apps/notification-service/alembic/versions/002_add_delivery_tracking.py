"""Add delivery tracking columns to notifications table.

Revision ID: n002
Revises: n001
Create Date: 2026-03-20
"""
from alembic import op
import sqlalchemy as sa

revision = 'n002'
down_revision = 'n001'
branch_labels = None
depends_on = None

SCHEMA = 'notification_core'


def upgrade() -> None:
    op.add_column('notifications', sa.Column(
        'delivery_status', sa.Text(), nullable=False, server_default='pending',
    ), schema=SCHEMA)
    op.add_column('notifications', sa.Column(
        'delivery_attempts', sa.Integer(), nullable=False, server_default='0',
    ), schema=SCHEMA)
    op.add_column('notifications', sa.Column(
        'last_delivery_error', sa.Text(), nullable=True,
    ), schema=SCHEMA)
    op.add_column('notifications', sa.Column(
        'delivered_at', sa.DateTime(timezone=True), nullable=True,
    ), schema=SCHEMA)
    op.create_check_constraint(
        'ck_notification_delivery_status',
        'notifications',
        "delivery_status IN ('pending', 'sent', 'failed', 'skipped')",
        schema=SCHEMA,
    )
    op.create_index(
        'idx_notifications_delivery_status',
        'notifications',
        ['delivery_status'],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index('idx_notifications_delivery_status', table_name='notifications', schema=SCHEMA)
    op.drop_constraint('ck_notification_delivery_status', 'notifications', schema=SCHEMA)
    op.drop_column('notifications', 'delivered_at', schema=SCHEMA)
    op.drop_column('notifications', 'last_delivery_error', schema=SCHEMA)
    op.drop_column('notifications', 'delivery_attempts', schema=SCHEMA)
    op.drop_column('notifications', 'delivery_status', schema=SCHEMA)
