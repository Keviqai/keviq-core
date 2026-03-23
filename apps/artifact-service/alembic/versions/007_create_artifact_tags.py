"""Create artifact_tags table.

Revision ID: a009
Revises: a008
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = 'a009'
down_revision = 'a008'
branch_labels = None
depends_on = None

SCHEMA = 'artifact_core'


def upgrade() -> None:
    op.create_table(
        'artifact_tags',
        sa.Column(
            'id', UUID(),
            server_default=sa.text('gen_random_uuid()'),
            primary_key=True,
        ),
        sa.Column('artifact_id', UUID(), nullable=False),
        sa.Column('workspace_id', UUID(), nullable=False),
        sa.Column('tag', sa.Text(), nullable=False),
        sa.Column(
            'created_at', sa.DateTime(timezone=True),
            server_default=sa.text('NOW()'), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['artifact_id'], [f'{SCHEMA}.artifacts.id'],
            name='fk_tag_artifact_id',
            ondelete='CASCADE',
        ),
        sa.UniqueConstraint(
            'artifact_id', 'tag',
            name='uq_artifact_tag',
        ),
        schema=SCHEMA,
    )

    op.create_index(
        'idx_tags_workspace_tag',
        'artifact_tags',
        ['workspace_id', 'tag'],
        schema=SCHEMA,
    )
    op.create_index(
        'idx_tags_artifact_id',
        'artifact_tags',
        ['artifact_id'],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        'idx_tags_artifact_id',
        table_name='artifact_tags', schema=SCHEMA,
    )
    op.drop_index(
        'idx_tags_workspace_tag',
        table_name='artifact_tags', schema=SCHEMA,
    )
    op.drop_table('artifact_tags', schema=SCHEMA)
