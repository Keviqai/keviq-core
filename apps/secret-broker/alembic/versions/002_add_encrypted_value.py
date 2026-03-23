"""Add envelope encryption columns to workspace_secrets.

Revision ID: s002
Revises: s001
Create Date: 2026-03-18
"""
from alembic import op
import sqlalchemy as sa

revision = 's002'
down_revision = 's001'
branch_labels = None
depends_on = None

SCHEMA = 'secret_core'


def upgrade() -> None:
    op.add_column(
        'workspace_secrets',
        sa.Column('secret_ciphertext', sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        'workspace_secrets',
        sa.Column('encryption_key_version', sa.Integer(), nullable=False, server_default='1'),
        schema=SCHEMA,
    )
    op.alter_column(
        'workspace_secrets',
        'secret_hash',
        nullable=True,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.alter_column(
        'workspace_secrets',
        'secret_hash',
        nullable=False,
        schema=SCHEMA,
    )
    op.drop_column('workspace_secrets', 'encryption_key_version', schema=SCHEMA)
    op.drop_column('workspace_secrets', 'secret_ciphertext', schema=SCHEMA)
