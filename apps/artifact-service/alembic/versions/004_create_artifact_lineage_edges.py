"""Create artifact_lineage_edges table.

Revision ID: a006
Revises: a005
Create Date: 2026-03-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = 'a006'
down_revision = 'a005'
branch_labels = None
depends_on = None

SCHEMA = 'artifact_core'


def upgrade() -> None:
    op.create_table(
        'artifact_lineage_edges',
        sa.Column('id', UUID(), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('child_artifact_id', UUID(), nullable=False),
        sa.Column('parent_artifact_id', UUID(), nullable=False),
        sa.Column('edge_type', sa.Text(), nullable=False),
        sa.CheckConstraint(
            "edge_type IN ('derived_from', 'transformed_from', 'aggregated_from', 'promoted_from')",
            name='chk_edge_type',
        ),
        sa.Column('run_id', UUID(), nullable=True),
        sa.Column('step_id', UUID(), nullable=True),
        sa.Column('transform_detail', JSONB(), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        # FKs within same schema
        sa.ForeignKeyConstraint(
            ['child_artifact_id'], [f'{SCHEMA}.artifacts.id'],
            name='fk_lineage_child_artifact_id',
        ),
        sa.ForeignKeyConstraint(
            ['parent_artifact_id'], [f'{SCHEMA}.artifacts.id'],
            name='fk_lineage_parent_artifact_id',
        ),
        # Prevent duplicate edges
        sa.UniqueConstraint(
            'child_artifact_id', 'parent_artifact_id', 'edge_type',
            name='uq_lineage_edge',
        ),
        schema=SCHEMA,
    )

    op.create_index(
        'idx_lineage_child_artifact_id',
        'artifact_lineage_edges',
        ['child_artifact_id'],
        schema=SCHEMA,
    )
    op.create_index(
        'idx_lineage_parent_artifact_id',
        'artifact_lineage_edges',
        ['parent_artifact_id'],
        schema=SCHEMA,
    )

    # Check constraint: self-loop prevention at DB level
    op.execute(sa.text(
        f"ALTER TABLE {SCHEMA}.artifact_lineage_edges "
        f"ADD CONSTRAINT chk_no_self_loop "
        f"CHECK (child_artifact_id != parent_artifact_id)"
    ))


def downgrade() -> None:
    op.execute(sa.text(
        f"ALTER TABLE {SCHEMA}.artifact_lineage_edges "
        f"DROP CONSTRAINT IF EXISTS chk_no_self_loop"
    ))
    op.drop_index('idx_lineage_parent_artifact_id', table_name='artifact_lineage_edges', schema=SCHEMA)
    op.drop_index('idx_lineage_child_artifact_id', table_name='artifact_lineage_edges', schema=SCHEMA)
    op.drop_table('artifact_lineage_edges', schema=SCHEMA)
