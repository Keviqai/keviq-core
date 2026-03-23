"""Create event_core.events — append-only event store.

Revision ID: a006
Revises: a005
Create Date: 2026-03-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = 'a006'
down_revision = 'a005'
branch_labels = None
depends_on = None

SCHEMA = 'event_core'


def upgrade() -> None:
    op.create_table(
        'events',
        sa.Column('id', UUID(), primary_key=True),  # event_id from source — NOT auto-generated
        sa.Column('event_type', sa.Text(), nullable=False),
        sa.Column('schema_version', sa.Text(), nullable=False, server_default='1.0'),
        sa.Column('workspace_id', UUID(), nullable=False),
        sa.Column('task_id', UUID(), nullable=True),
        sa.Column('run_id', UUID(), nullable=True),
        sa.Column('step_id', UUID(), nullable=True),
        sa.Column('correlation_id', UUID(), nullable=False),
        sa.Column('causation_id', UUID(), nullable=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('emitted_by', JSONB(), nullable=False),
        sa.Column('actor', JSONB(), nullable=False),
        sa.Column('payload', JSONB(), nullable=False),
        sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.CheckConstraint(
            "event_type ~ '^[a-z_]+\\.[a-z_]+$'",
            name='ck_events_event_type_format',
        ),
        schema=SCHEMA,
    )

    # NOTE: No FK to orchestrator_core or workspace_core — S1 Schema Isolation.
    # Event store receives events from any service's outbox.
    # Referential integrity is maintained by the emitting service.

    # Primary query patterns:
    # 1. Timeline by task: WHERE task_id = ? ORDER BY occurred_at
    # 2. Timeline by run: WHERE run_id = ? ORDER BY occurred_at
    # 3. Events by workspace: WHERE workspace_id = ? ORDER BY occurred_at
    # 4. Correlation trace: WHERE correlation_id = ?
    # 5. SSE resume: WHERE id > ? AND (task_id = ? OR run_id = ?)

    op.create_index(
        'idx_events_workspace_occurred',
        'events',
        ['workspace_id', 'occurred_at'],
        schema=SCHEMA,
    )
    op.create_index(
        'idx_events_task_occurred',
        'events',
        ['task_id', 'occurred_at'],
        schema=SCHEMA,
    )
    op.create_index(
        'idx_events_run_occurred',
        'events',
        ['run_id', 'occurred_at'],
        schema=SCHEMA,
    )
    op.create_index(
        'idx_events_correlation',
        'events',
        ['correlation_id'],
        schema=SCHEMA,
    )
    op.create_index(
        'idx_events_type',
        'events',
        ['event_type'],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index('idx_events_type', table_name='events', schema=SCHEMA)
    op.drop_index('idx_events_correlation', table_name='events', schema=SCHEMA)
    op.drop_index('idx_events_run_occurred', table_name='events', schema=SCHEMA)
    op.drop_index('idx_events_task_occurred', table_name='events', schema=SCHEMA)
    op.drop_index('idx_events_workspace_occurred', table_name='events', schema=SCHEMA)
    op.drop_table('events', schema=SCHEMA)
