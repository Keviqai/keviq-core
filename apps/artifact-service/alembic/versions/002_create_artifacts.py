"""Create artifacts table.

Revision ID: a004
Revises: a003
Create Date: 2026-03-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = 'a004'
down_revision = 'a003'
branch_labels = None
depends_on = None

SCHEMA = 'artifact_core'


def upgrade() -> None:
    op.create_table(
        'artifacts',
        sa.Column('id', UUID(), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('workspace_id', UUID(), nullable=False),
        sa.Column('task_id', UUID(), nullable=False),
        sa.Column('run_id', UUID(), nullable=False),
        sa.Column('step_id', UUID(), nullable=True),
        sa.Column('agent_invocation_id', UUID(), nullable=True),
        sa.Column('root_type', sa.Text(), nullable=False),
        sa.Column('artifact_type', sa.Text(), nullable=False),
        sa.Column('artifact_status', sa.Text(), nullable=False, server_default='pending'),
        sa.CheckConstraint(
            "artifact_status IN ('pending', 'writing', 'ready', 'failed', 'superseded', 'archived')",
            name='chk_artifact_status',
        ),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('mime_type', sa.Text(), nullable=True),
        sa.Column('storage_ref', sa.Text(), nullable=True),
        sa.Column('size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('checksum', sa.Text(), nullable=True),
        sa.Column('lineage', JSONB(), server_default='[]', nullable=False),
        sa.Column('metadata', JSONB(), server_default='{}', nullable=False),
        sa.Column('ready_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        schema=SCHEMA,
    )

    # Query indexes
    op.create_index('idx_artifacts_workspace_id', 'artifacts', ['workspace_id'], schema=SCHEMA)
    op.create_index('idx_artifacts_run_id', 'artifacts', ['run_id'], schema=SCHEMA)
    op.create_index('idx_artifacts_step_id', 'artifacts', ['step_id'], schema=SCHEMA)
    op.create_index('idx_artifacts_task_id', 'artifacts', ['task_id'], schema=SCHEMA)
    op.create_index('idx_artifacts_agent_invocation_id', 'artifacts', ['agent_invocation_id'], schema=SCHEMA)
    op.create_index('idx_artifacts_workspace_status', 'artifacts', ['workspace_id', 'artifact_status'], schema=SCHEMA)
    op.create_index(
        'idx_artifacts_workspace_created',
        'artifacts',
        ['workspace_id', 'created_at'],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index('idx_artifacts_workspace_created', table_name='artifacts', schema=SCHEMA)
    op.drop_index('idx_artifacts_workspace_status', table_name='artifacts', schema=SCHEMA)
    op.drop_index('idx_artifacts_agent_invocation_id', table_name='artifacts', schema=SCHEMA)
    op.drop_index('idx_artifacts_task_id', table_name='artifacts', schema=SCHEMA)
    op.drop_index('idx_artifacts_step_id', table_name='artifacts', schema=SCHEMA)
    op.drop_index('idx_artifacts_run_id', table_name='artifacts', schema=SCHEMA)
    op.drop_index('idx_artifacts_workspace_id', table_name='artifacts', schema=SCHEMA)
    op.drop_table('artifacts', schema=SCHEMA)
