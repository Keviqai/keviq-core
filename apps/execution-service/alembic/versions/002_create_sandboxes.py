"""Create sandboxes and sandbox_attempts tables.

Revision ID: a009
Revises: a004
Create Date: 2026-03-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = 'a009'
down_revision = 'a004'
branch_labels = None
depends_on = None

SCHEMA = 'execution_core'


def upgrade() -> None:
    # ── sandboxes ────────────────────────────────────────────────
    op.create_table(
        'sandboxes',
        sa.Column('id', UUID(), primary_key=True),
        sa.Column('workspace_id', UUID(), nullable=False),
        sa.Column('task_id', UUID(), nullable=False),
        sa.Column('run_id', UUID(), nullable=False),
        sa.Column('step_id', UUID(), nullable=False),
        sa.Column('agent_invocation_id', UUID(), nullable=False),
        sa.Column('sandbox_type', sa.Text(), nullable=False),
        sa.Column('sandbox_status', sa.Text(), nullable=False,
                  server_default='provisioning'),
        sa.Column('policy_snapshot', JSONB(), nullable=False,
                  server_default='{}'),
        sa.Column('resource_limits', JSONB(), nullable=False,
                  server_default='{}'),
        sa.Column('network_egress_policy', JSONB(), nullable=False,
                  server_default='{}'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('terminated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('termination_reason', sa.Text(), nullable=True),
        sa.Column('error_detail', JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),
        sa.CheckConstraint(
            "sandbox_type IN ('container', 'subprocess')",
            name='ck_sandboxes_type',
        ),
        sa.CheckConstraint(
            "sandbox_status IN ("
            "'provisioning', 'ready', 'executing', 'idle', "
            "'terminating', 'terminated', 'failed')",
            name='ck_sandboxes_status',
        ),
        sa.CheckConstraint(
            "termination_reason IS NULL OR termination_reason IN ("
            "'completed', 'timeout', 'policy_violation', 'error', 'manual')",
            name='ck_sandboxes_termination_reason',
        ),
        schema=SCHEMA,
    )

    # Lookup indexes
    op.create_index(
        'idx_sandboxes_workspace', 'sandboxes', ['workspace_id'],
        schema=SCHEMA,
    )
    op.create_index(
        'idx_sandboxes_invocation', 'sandboxes', ['agent_invocation_id'],
        schema=SCHEMA,
    )
    op.create_index(
        'idx_sandboxes_run', 'sandboxes', ['run_id'],
        schema=SCHEMA,
    )
    op.create_index(
        'idx_sandboxes_step', 'sandboxes', ['step_id'],
        schema=SCHEMA,
    )
    op.create_index(
        'idx_sandboxes_task', 'sandboxes', ['task_id'],
        schema=SCHEMA,
    )
    # Active sandbox query (for cleanup / recovery)
    op.create_index(
        'idx_sandboxes_active',
        'sandboxes',
        ['sandbox_status'],
        schema=SCHEMA,
        postgresql_where=sa.text(
            "sandbox_status NOT IN ('terminated', 'failed')"
        ),
    )

    # ── sandbox_attempts ─────────────────────────────────────────
    op.create_table(
        'sandbox_attempts',
        sa.Column('id', UUID(), primary_key=True),
        sa.Column('sandbox_id', UUID(), nullable=False),
        sa.Column('attempt_index', sa.Integer(), nullable=False),
        sa.Column('tool_name', sa.Text(), nullable=False),
        sa.Column('tool_input', JSONB(), nullable=True),
        sa.Column('status', sa.Text(), nullable=False,
                  server_default='pending'),
        sa.Column('stdout', sa.Text(), nullable=True),
        sa.Column('stderr', sa.Text(), nullable=True),
        sa.Column('exit_code', sa.Integer(), nullable=True),
        sa.Column('truncated', sa.Boolean(), nullable=False,
                  server_default='false'),
        sa.Column('error_detail', JSONB(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'timed_out')",
            name='ck_sandbox_attempts_status',
        ),
        sa.UniqueConstraint(
            'sandbox_id', 'attempt_index',
            name='uq_sandbox_attempts_sandbox_attempt',
        ),
        sa.ForeignKeyConstraint(
            ['sandbox_id'], [f'{SCHEMA}.sandboxes.id'],
            name='fk_sandbox_attempts_sandbox_id',
            ondelete='CASCADE',
        ),
        schema=SCHEMA,
    )

    op.create_index(
        'idx_sandbox_attempts_sandbox', 'sandbox_attempts', ['sandbox_id'],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        'idx_sandbox_attempts_sandbox',
        table_name='sandbox_attempts', schema=SCHEMA,
    )
    op.drop_table('sandbox_attempts', schema=SCHEMA)

    op.drop_index('idx_sandboxes_active', table_name='sandboxes', schema=SCHEMA)
    op.drop_index('idx_sandboxes_task', table_name='sandboxes', schema=SCHEMA)
    op.drop_index('idx_sandboxes_step', table_name='sandboxes', schema=SCHEMA)
    op.drop_index('idx_sandboxes_run', table_name='sandboxes', schema=SCHEMA)
    op.drop_index('idx_sandboxes_invocation', table_name='sandboxes', schema=SCHEMA)
    op.drop_index('idx_sandboxes_workspace', table_name='sandboxes', schema=SCHEMA)
    op.drop_table('sandboxes', schema=SCHEMA)
