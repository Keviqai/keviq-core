"""Create terminal_sessions and terminal_commands tables.

Revision ID: a011
Revises: a010
Create Date: 2026-03-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = 'a011'
down_revision = 'a010'
branch_labels = None
depends_on = None

SCHEMA = 'execution_core'


def upgrade() -> None:
    # -- terminal_sessions ------------------------------------------------
    op.create_table(
        'terminal_sessions',
        sa.Column('id', UUID(), primary_key=True),
        sa.Column('sandbox_id', UUID(), nullable=False),
        sa.Column('run_id', UUID(), nullable=False),
        sa.Column('workspace_id', UUID(), nullable=False),
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False,
                  server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('active', 'closed')",
            name='ck_terminal_sessions_status',
        ),
        sa.ForeignKeyConstraint(
            ['sandbox_id'], [f'{SCHEMA}.sandboxes.id'],
            name='fk_terminal_sessions_sandbox_id',
            ondelete='CASCADE',
        ),
        schema=SCHEMA,
    )

    op.create_index(
        'idx_terminal_sessions_sandbox', 'terminal_sessions', ['sandbox_id'],
        schema=SCHEMA,
    )
    op.create_index(
        'idx_terminal_sessions_run', 'terminal_sessions', ['run_id'],
        schema=SCHEMA,
    )

    # -- terminal_commands ------------------------------------------------
    op.create_table(
        'terminal_commands',
        sa.Column('id', UUID(), primary_key=True),
        sa.Column('session_id', UUID(), nullable=False),
        sa.Column('command', sa.Text(), nullable=False),
        sa.Column('stdout', sa.Text(), nullable=True, server_default=''),
        sa.Column('stderr', sa.Text(), nullable=True, server_default=''),
        sa.Column('exit_code', sa.Integer(), nullable=True),
        sa.Column('status', sa.Text(), nullable=False,
                  server_default='running'),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'timed_out')",
            name='ck_terminal_commands_status',
        ),
        sa.ForeignKeyConstraint(
            ['session_id'], [f'{SCHEMA}.terminal_sessions.id'],
            name='fk_terminal_commands_session_id',
            ondelete='CASCADE',
        ),
        schema=SCHEMA,
    )

    op.create_index(
        'idx_terminal_commands_session', 'terminal_commands', ['session_id'],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        'idx_terminal_commands_session',
        table_name='terminal_commands', schema=SCHEMA,
    )
    op.drop_table('terminal_commands', schema=SCHEMA)

    op.drop_index(
        'idx_terminal_sessions_run',
        table_name='terminal_sessions', schema=SCHEMA,
    )
    op.drop_index(
        'idx_terminal_sessions_sandbox',
        table_name='terminal_sessions', schema=SCHEMA,
    )
    op.drop_table('terminal_sessions', schema=SCHEMA)
