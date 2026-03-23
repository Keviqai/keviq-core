"""Add structured brief columns to tasks table for Q1 delegation clarity.

New columns: goal, context, constraints, desired_output (TEXT nullable),
template_id, agent_template_id (UUID nullable), risk_level (TEXT nullable).

Revision ID: a006
Revises: a005
Create Date: 2026-03-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = 'a006'
down_revision = 'a005'
branch_labels = None
depends_on = None

SCHEMA = 'orchestrator_core'

VALID_RISK_LEVELS = ('low', 'medium', 'high')


def upgrade() -> None:
    op.add_column('tasks', sa.Column('goal', sa.Text(), nullable=True), schema=SCHEMA)
    op.add_column('tasks', sa.Column('context', sa.Text(), nullable=True), schema=SCHEMA)
    op.add_column('tasks', sa.Column('constraints', sa.Text(), nullable=True), schema=SCHEMA)
    op.add_column('tasks', sa.Column('desired_output', sa.Text(), nullable=True), schema=SCHEMA)
    op.add_column('tasks', sa.Column('template_id', UUID(), nullable=True), schema=SCHEMA)
    op.add_column('tasks', sa.Column('agent_template_id', UUID(), nullable=True), schema=SCHEMA)
    op.add_column(
        'tasks',
        sa.Column('risk_level', sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.create_check_constraint(
        'ck_tasks_risk_level',
        'tasks',
        f"risk_level IS NULL OR risk_level IN {VALID_RISK_LEVELS}",
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_constraint('ck_tasks_risk_level', 'tasks', schema=SCHEMA)
    op.drop_column('tasks', 'risk_level', schema=SCHEMA)
    op.drop_column('tasks', 'agent_template_id', schema=SCHEMA)
    op.drop_column('tasks', 'template_id', schema=SCHEMA)
    op.drop_column('tasks', 'desired_output', schema=SCHEMA)
    op.drop_column('tasks', 'constraints', schema=SCHEMA)
    op.drop_column('tasks', 'context', schema=SCHEMA)
    op.drop_column('tasks', 'goal', schema=SCHEMA)
