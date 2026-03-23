"""Create orchestrator_core.task_comments table.

P6-S2: Inline task comments for team collaboration.

Revision ID: a011
Revises: a010
Create Date: 2026-03-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = 'a011'
down_revision = 'a010'
branch_labels = None
depends_on = None

SCHEMA = 'orchestrator_core'


def upgrade() -> None:
    op.create_table(
        'task_comments',
        sa.Column('id', UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workspace_id', UUID(), nullable=False),
        sa.Column('task_id', UUID(), nullable=False),
        sa.Column('author_id', UUID(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        schema=SCHEMA,
    )

    op.create_index(
        'idx_task_comments_task',
        'task_comments',
        ['task_id', 'created_at'],
        schema=SCHEMA,
    )

    op.create_index(
        'idx_task_comments_workspace',
        'task_comments',
        ['workspace_id'],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index('idx_task_comments_workspace', table_name='task_comments', schema=SCHEMA)
    op.drop_index('idx_task_comments_task', table_name='task_comments', schema=SCHEMA)
    op.drop_table('task_comments', schema=SCHEMA)
