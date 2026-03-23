"""Create artifact_annotations table.

Revision ID: a008
Revises: a007
Create Date: 2026-03-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = 'a008'
down_revision = 'a007'
branch_labels = None
depends_on = None

SCHEMA = 'artifact_core'


def upgrade() -> None:
    op.create_table(
        'artifact_annotations',
        sa.Column('id', UUID(), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('artifact_id', UUID(), nullable=False),
        sa.Column('workspace_id', UUID(), nullable=False),
        sa.Column('author_id', UUID(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(
            ['artifact_id'], [f'{SCHEMA}.artifacts.id'],
            name='fk_annotation_artifact_id',
            ondelete='CASCADE',
        ),
        schema=SCHEMA,
    )

    op.create_index(
        'idx_annotations_artifact_id',
        'artifact_annotations',
        ['artifact_id'],
        schema=SCHEMA,
    )
    op.create_index(
        'idx_annotations_workspace_id',
        'artifact_annotations',
        ['workspace_id'],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index('idx_annotations_workspace_id', table_name='artifact_annotations', schema=SCHEMA)
    op.drop_index('idx_annotations_artifact_id', table_name='artifact_annotations', schema=SCHEMA)
    op.drop_table('artifact_annotations', schema=SCHEMA)
