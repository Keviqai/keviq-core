"""Create artifact_provenance table.

Revision ID: a005
Revises: a004
Create Date: 2026-03-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = 'a005'
down_revision = 'a004'
branch_labels = None
depends_on = None

SCHEMA = 'artifact_core'


def upgrade() -> None:
    op.create_table(
        'artifact_provenance',
        sa.Column('id', UUID(), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column(
            'artifact_id', UUID(), nullable=False,
        ),
        # Reproducibility tuple component 1: input_snapshot
        sa.Column('input_snapshot', JSONB(), server_default='[]', nullable=False),
        # Reproducibility tuple component 2: run_config
        sa.Column('run_config_hash', sa.Text(), nullable=True),
        # Reproducibility tuple component 3: tool_provenance
        sa.Column('tool_name', sa.Text(), nullable=True),
        sa.Column('tool_version', sa.Text(), nullable=True),
        sa.Column('tool_config_hash', sa.Text(), nullable=True),
        # Reproducibility tuple component 4: model_provenance
        sa.Column('model_provider', sa.Text(), nullable=True),
        sa.Column('model_name_concrete', sa.Text(), nullable=True),
        sa.Column('model_version_concrete', sa.Text(), nullable=True),
        sa.Column('model_temperature', sa.Float(), nullable=True),
        sa.Column('model_max_tokens', sa.Integer(), nullable=True),
        sa.Column('system_prompt_hash', sa.Text(), nullable=True),
        # Reproducibility tuple component 5: lineage_chain
        sa.Column('lineage_chain', JSONB(), server_default='[]', nullable=False),
        # Metadata
        sa.Column('correlation_id', UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        # FK within same schema — artifact_core owns both tables
        sa.ForeignKeyConstraint(
            ['artifact_id'], [f'{SCHEMA}.artifacts.id'],
            name='fk_provenance_artifact_id',
        ),
        schema=SCHEMA,
    )

    op.create_index(
        'idx_provenance_artifact_id',
        'artifact_provenance',
        ['artifact_id'],
        unique=True,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index('idx_provenance_artifact_id', table_name='artifact_provenance', schema=SCHEMA)
    op.drop_table('artifact_provenance', schema=SCHEMA)
