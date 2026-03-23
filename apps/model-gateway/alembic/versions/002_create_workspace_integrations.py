"""Create workspace_integrations table for user-managed integration configs.

Revision ID: a009
Revises: a008
Create Date: 2026-03-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = 'a009'
down_revision = 'a008'
branch_labels = None
depends_on = None

SCHEMA = 'model_gateway_core'


def upgrade() -> None:
    op.create_table(
        'workspace_integrations',
        sa.Column('id', UUID(), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('workspace_id', UUID(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('integration_type', sa.Text(), nullable=False),
        sa.Column('provider_kind', sa.Text(), nullable=False),
        sa.Column('endpoint_url', sa.Text(), nullable=True),
        sa.Column('default_model', sa.Text(), nullable=True),
        sa.Column('api_key_secret_ref', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('config', JSONB(), nullable=True),
        sa.Column('created_by_id', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.CheckConstraint(
            "integration_type IN ('llm_provider')",
            name='ck_integration_type',
        ),
        sa.CheckConstraint(
            "provider_kind IN ('openai', 'anthropic', 'azure_openai', 'custom')",
            name='ck_provider_kind',
        ),
        schema=SCHEMA,
    )

    op.create_index(
        'idx_integrations_workspace_created',
        'workspace_integrations',
        ['workspace_id', sa.text('created_at DESC')],
        schema=SCHEMA,
    )
    op.create_index(
        'idx_integrations_workspace_type',
        'workspace_integrations',
        ['workspace_id', 'integration_type'],
        schema=SCHEMA,
    )

    # Reuse set_updated_at() trigger function from migration 001
    op.execute(sa.text(f"""
        CREATE TRIGGER trg_workspace_integrations_updated_at
        BEFORE UPDATE ON {SCHEMA}.workspace_integrations
        FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.set_updated_at();
    """))


def downgrade() -> None:
    op.execute(sa.text(f'DROP TRIGGER IF EXISTS trg_workspace_integrations_updated_at ON {SCHEMA}.workspace_integrations'))
    op.drop_index('idx_integrations_workspace_type', table_name='workspace_integrations', schema=SCHEMA)
    op.drop_index('idx_integrations_workspace_created', table_name='workspace_integrations', schema=SCHEMA)
    op.drop_table('workspace_integrations', schema=SCHEMA)
