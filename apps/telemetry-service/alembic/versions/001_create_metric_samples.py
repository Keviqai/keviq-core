"""Create telemetry_core.metric_samples table.

O8-S3: Stores scraped metric values from service /metrics endpoints.
Simple time-series: timestamp + service + metric_name + labels + value.

Revision ID: t001
Revises: None
Create Date: 2026-03-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 't001'
down_revision = None
branch_labels = None
depends_on = None

SCHEMA = 'telemetry_core'


def upgrade() -> None:
    op.create_table(
        'metric_samples',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('scraped_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('source_service', sa.Text(), nullable=False),
        sa.Column('metric_name', sa.Text(), nullable=False),
        sa.Column('labels', JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column('value', sa.Float(), nullable=False),
        schema=SCHEMA,
    )

    # Primary query: latest metrics by service
    op.create_index(
        'idx_metric_samples_service_time',
        'metric_samples',
        ['source_service', 'scraped_at'],
        schema=SCHEMA,
    )

    # Query by metric name
    op.create_index(
        'idx_metric_samples_name',
        'metric_samples',
        ['metric_name', 'scraped_at'],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index('idx_metric_samples_name', table_name='metric_samples', schema=SCHEMA)
    op.drop_index('idx_metric_samples_service_time', table_name='metric_samples', schema=SCHEMA)
    op.drop_table('metric_samples', schema=SCHEMA)
