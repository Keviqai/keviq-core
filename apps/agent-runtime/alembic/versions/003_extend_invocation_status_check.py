"""Extend agent_invocations status CHECK for PR14 domain states.

Adds: starting, timed_out, cancelled to the allowed invocation_status values.
These states are defined in the AgentInvocation domain model (PR14) but were
not in the original CHECK constraint (PR13, which followed doc 05 verbatim).

Revision ID: a009
Revises: a007
Create Date: 2026-03-12
"""
from alembic import op

revision = 'a009'
down_revision = 'a007'
branch_labels = None
depends_on = None

SCHEMA = 'agent_runtime'


def upgrade() -> None:
    op.drop_constraint('ck_agent_invocations_status', 'agent_invocations', schema=SCHEMA)
    op.create_check_constraint(
        'ck_agent_invocations_status',
        'agent_invocations',
        "invocation_status IN ("
        "'initializing','starting','running','waiting_human','waiting_tool',"
        "'completed','failed','timed_out','cancelled','interrupted',"
        "'compensating','compensated'"
        ")",
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_constraint('ck_agent_invocations_status', 'agent_invocations', schema=SCHEMA)
    op.create_check_constraint(
        'ck_agent_invocations_status',
        'agent_invocations',
        "invocation_status IN ("
        "'initializing','running','waiting_human','waiting_tool',"
        "'completed','failed','interrupted','compensating','compensated'"
        ")",
        schema=SCHEMA,
    )
