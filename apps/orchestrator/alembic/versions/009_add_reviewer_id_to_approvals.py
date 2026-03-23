"""Add reviewer_id to approval_requests.

Revision ID: a009
Revises: a008
Create Date: 2026-03-18

Adds optional reviewer_id (UUID nullable) for Q4-S2 Reviewer Assignment.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = 'a009'
down_revision = 'a008'
branch_labels = None
depends_on = None

SCHEMA = 'orchestrator_core'


def upgrade() -> None:
    op.add_column(
        'approval_requests',
        sa.Column('reviewer_id', postgresql.UUID(), nullable=True),
        schema=SCHEMA,
    )
    op.create_index(
        'ix_approval_requests_reviewer_id',
        'approval_requests',
        ['reviewer_id'],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        'ix_approval_requests_reviewer_id',
        table_name='approval_requests',
        schema=SCHEMA,
    )
    op.drop_column('approval_requests', 'reviewer_id', schema=SCHEMA)
