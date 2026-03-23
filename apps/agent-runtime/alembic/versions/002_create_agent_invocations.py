"""Create agent_runtime.agent_invocations — execution tracking table.

Revision ID: a007
Revises: a002
Create Date: 2026-03-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = 'a007'
down_revision = 'a002'
branch_labels = None
depends_on = None

SCHEMA = 'agent_runtime'


def upgrade() -> None:
    op.create_table(
        'agent_invocations',
        sa.Column('id', UUID(), primary_key=True),  # Always supplied by orchestrator — no server_default by design
        sa.Column('step_id', UUID(), nullable=False),
        sa.Column('run_id', UUID(), nullable=False),
        sa.Column('task_id', UUID(), nullable=False),
        sa.Column('workspace_id', UUID(), nullable=False),
        sa.Column('correlation_id', UUID(), nullable=False),
        sa.Column('agent_id', sa.Text(), nullable=False),
        sa.Column('model_id', sa.Text(), nullable=False),
        sa.Column('invocation_status', sa.Text(), nullable=False, server_default='initializing'),
        sa.Column('prompt_tokens', sa.Integer(), nullable=True),
        sa.Column('completion_tokens', sa.Integer(), nullable=True),
        sa.Column('total_cost_usd', sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column('input_messages', JSONB(), nullable=True),
        sa.Column('output_messages', JSONB(), nullable=True),
        sa.Column('tool_calls', JSONB(), nullable=True),
        sa.Column('error_detail', JSONB(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.CheckConstraint(
            "invocation_status IN ("
            "'initializing','running','waiting_human','waiting_tool',"
            "'completed','failed','interrupted','compensating','compensated'"
            ")",
            name='ck_agent_invocations_status',
        ),
        schema=SCHEMA,
    )

    # NOTE: No FK to orchestrator_core — S1 Schema Isolation.
    # agent_invocations references step_id, run_id, task_id by value only.
    # Referential integrity is maintained by the orchestrator dispatch contract.

    # Primary query patterns:
    # 1. By step: WHERE step_id = ? ORDER BY created_at
    # 2. By run: WHERE run_id = ? ORDER BY created_at
    # 3. Correlation trace: WHERE correlation_id = ?
    # 4. Active invocations: WHERE invocation_status NOT IN (terminal states)

    op.create_index(
        'idx_invocations_step',
        'agent_invocations',
        ['step_id', 'created_at'],
        schema=SCHEMA,
    )
    op.create_index(
        'idx_invocations_run',
        'agent_invocations',
        ['run_id', 'created_at'],
        schema=SCHEMA,
    )
    op.create_index(
        'idx_invocations_task',
        'agent_invocations',
        ['task_id'],
        schema=SCHEMA,
    )
    op.create_index(
        'idx_invocations_correlation',
        'agent_invocations',
        ['correlation_id'],
        schema=SCHEMA,
    )
    op.create_index(
        'idx_invocations_workspace',
        'agent_invocations',
        ['workspace_id'],
        schema=SCHEMA,
    )
    op.create_index(
        'idx_invocations_status',
        'agent_invocations',
        ['invocation_status'],
        schema=SCHEMA,
        postgresql_where=sa.text(
            "invocation_status NOT IN ('completed','failed','interrupted','compensated')"
        ),
    )


def downgrade() -> None:
    op.drop_index('idx_invocations_status', table_name='agent_invocations', schema=SCHEMA)
    op.drop_index('idx_invocations_workspace', table_name='agent_invocations', schema=SCHEMA)
    op.drop_index('idx_invocations_correlation', table_name='agent_invocations', schema=SCHEMA)
    op.drop_index('idx_invocations_task', table_name='agent_invocations', schema=SCHEMA)
    op.drop_index('idx_invocations_run', table_name='agent_invocations', schema=SCHEMA)
    op.drop_index('idx_invocations_step', table_name='agent_invocations', schema=SCHEMA)
    op.drop_table('agent_invocations', schema=SCHEMA)
