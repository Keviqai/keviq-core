"""Create orchestrator_core tables: tasks, runs, steps.

Revision ID: a002
Revises: a001
Create Date: 2026-03-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = 'a002'
down_revision = 'a001'
branch_labels = None
depends_on = None

SCHEMA = 'orchestrator_core'

VALID_TASK_TYPES = ('coding', 'research', 'analysis', 'operation', 'custom')
VALID_TASK_STATUSES = ('draft', 'pending', 'running', 'waiting_approval', 'completed', 'failed', 'cancelled', 'archived')
VALID_RUN_STATUSES = ('queued', 'preparing', 'running', 'waiting_approval', 'completing', 'completed', 'failed', 'timed_out', 'cancelled')
VALID_STEP_TYPES = ('agent_invocation', 'tool_call', 'approval_gate', 'condition', 'transform')
VALID_STEP_STATUSES = ('pending', 'running', 'waiting_approval', 'completed', 'failed', 'skipped', 'blocked', 'cancelled')
VALID_TRIGGER_TYPES = ('manual', 'scheduled', 'event', 'approval')


def upgrade() -> None:
    # ── Tasks ──────────────────────────────────────────────────────
    op.create_table(
        'tasks',
        sa.Column('id', UUID(), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('workspace_id', UUID(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('task_type', sa.Text(), nullable=False),
        sa.Column('task_status', sa.Text(), nullable=False, server_default='pending'),
        sa.Column('input_config', JSONB(), nullable=False, server_default='{}'),
        sa.Column('repo_snapshot_id', UUID(), nullable=True),
        sa.Column('policy_id', UUID(), nullable=True),
        sa.Column('parent_task_id', UUID(), nullable=True),
        sa.Column('created_by_id', UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.CheckConstraint(
            f"task_type IN {VALID_TASK_TYPES}",
            name='ck_tasks_task_type',
        ),
        sa.CheckConstraint(
            f"task_status IN {VALID_TASK_STATUSES}",
            name='ck_tasks_task_status',
        ),
        sa.ForeignKeyConstraint(['parent_task_id'], [f'{SCHEMA}.tasks.id'], name='fk_tasks_parent', ondelete='SET NULL'),
        schema=SCHEMA,
    )

    # NOTE: No cross-schema FKs (S1 principle):
    # - tasks.workspace_id does NOT reference workspace_core.workspaces.id
    # - tasks.created_by_id does NOT reference identity_core.users.id
    # - tasks.policy_id does NOT reference policy_core.policies.id
    # - tasks.repo_snapshot_id does NOT reference any external schema
    # Consistency is maintained via events.

    # idx_tasks_workspace_status covers workspace_id as leading column (no separate workspace index needed)
    op.create_index('idx_tasks_workspace_status', 'tasks', ['workspace_id', 'task_status'], schema=SCHEMA)
    op.create_index('idx_tasks_created_by', 'tasks', ['created_by_id'], schema=SCHEMA)

    # ── Runs ───────────────────────────────────────────────────────
    op.create_table(
        'runs',
        sa.Column('id', UUID(), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('task_id', UUID(), sa.ForeignKey(f'{SCHEMA}.tasks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('workspace_id', UUID(), nullable=False),
        sa.Column('run_status', sa.Text(), nullable=False, server_default='queued'),
        sa.Column('trigger_type', sa.Text(), nullable=False, server_default='manual'),
        sa.Column('triggered_by_id', UUID(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('run_config', JSONB(), nullable=False, server_default='{}'),
        sa.Column('error_summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.CheckConstraint(
            f"run_status IN {VALID_RUN_STATUSES}",
            name='ck_runs_run_status',
        ),
        sa.CheckConstraint(
            f"trigger_type IN {VALID_TRIGGER_TYPES}",
            name='ck_runs_trigger_type',
        ),
        sa.CheckConstraint(
            'duration_ms >= 0',
            name='ck_runs_duration_non_negative',
        ),
        schema=SCHEMA,
    )

    op.create_index('idx_runs_task', 'runs', ['task_id'], schema=SCHEMA)
    op.create_index('idx_runs_workspace', 'runs', ['workspace_id'], schema=SCHEMA)

    # ── Steps ──────────────────────────────────────────────────────
    op.create_table(
        'steps',
        sa.Column('id', UUID(), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('run_id', UUID(), sa.ForeignKey(f'{SCHEMA}.runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('workspace_id', UUID(), nullable=False),
        sa.Column('step_type', sa.Text(), nullable=False, server_default='agent_invocation'),
        sa.Column('step_status', sa.Text(), nullable=False, server_default='pending'),
        sa.Column('sequence', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('parent_step_id', UUID(), nullable=True),
        sa.Column('input_snapshot', JSONB(), nullable=True),
        sa.Column('output_snapshot', JSONB(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_detail', JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.CheckConstraint(
            f"step_type IN {VALID_STEP_TYPES}",
            name='ck_steps_step_type',
        ),
        sa.CheckConstraint(
            f"step_status IN {VALID_STEP_STATUSES}",
            name='ck_steps_step_status',
        ),
        sa.CheckConstraint(
            'sequence > 0',
            name='ck_steps_sequence_positive',
        ),
        sa.ForeignKeyConstraint(['parent_step_id'], [f'{SCHEMA}.steps.id'], name='fk_steps_parent', ondelete='SET NULL'),
        sa.UniqueConstraint('run_id', 'sequence', name='uq_steps_run_sequence'),
        schema=SCHEMA,
    )

    # uq_steps_run_sequence covers run_id as leading column (no separate run index needed)
    op.create_index('idx_steps_workspace', 'steps', ['workspace_id'], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index('idx_steps_workspace', table_name='steps', schema=SCHEMA)
    op.drop_table('steps', schema=SCHEMA)
    op.drop_index('idx_runs_workspace', table_name='runs', schema=SCHEMA)
    op.drop_index('idx_runs_task', table_name='runs', schema=SCHEMA)
    op.drop_table('runs', schema=SCHEMA)
    op.drop_index('idx_tasks_created_by', table_name='tasks', schema=SCHEMA)
    op.drop_index('idx_tasks_workspace_status', table_name='tasks', schema=SCHEMA)
    op.drop_table('tasks', schema=SCHEMA)
