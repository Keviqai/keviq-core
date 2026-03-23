"""Add pending_tool_context JSONB column to agent_invocations.

Stores the tool call context when invocation enters WAITING_HUMAN state,
so the resume flow (O5-S2) can pick up where execution paused.

Revision ID: a010
Revises: a009
Create Date: 2026-03-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'a010'
down_revision = 'a009'
branch_labels = None
depends_on = None

SCHEMA = 'agent_runtime'


def upgrade() -> None:
    op.add_column(
        'agent_invocations',
        sa.Column('pending_tool_context', JSONB(), nullable=True),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column('agent_invocations', 'pending_tool_context', schema=SCHEMA)
