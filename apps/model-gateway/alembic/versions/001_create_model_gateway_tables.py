"""Create model_gateway_core tables — model_usage_records + provider_configs.

Revision ID: a008
Revises:
Create Date: 2026-03-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = 'a008'
down_revision = None
branch_labels = None
depends_on = None

SCHEMA = 'model_gateway_core'


def upgrade() -> None:
    # ── model_usage_records: append-only LLM call log ─────────────
    op.create_table(
        'model_usage_records',
        sa.Column('id', UUID(), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('agent_invocation_id', UUID(), nullable=False),
        sa.Column('workspace_id', UUID(), nullable=False),
        sa.Column('correlation_id', UUID(), nullable=False),
        # Model resolution: alias → concrete version (PP9, DNB12)
        sa.Column('model_alias', sa.Text(), nullable=False),
        sa.Column('model_concrete', sa.Text(), nullable=False),
        sa.Column('provider', sa.Text(), nullable=False),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completion_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_cost_usd', sa.Numeric(precision=12, scale=6), nullable=False, server_default='0'),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('status', sa.Text(), nullable=False, server_default='success'),
        sa.Column('error_code', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.CheckConstraint(
            "status IN ('success','error','timeout')",
            name='ck_usage_records_status',
        ),
        sa.CheckConstraint(
            'prompt_tokens >= 0 AND completion_tokens >= 0 AND total_cost_usd >= 0',
            name='ck_usage_records_non_negative',
        ),
        schema=SCHEMA,
    )

    # NOTE: No FK to agent_runtime or orchestrator_core — S1 Schema Isolation.
    # References agent_invocation_id and workspace_id by value only.

    # Query patterns:
    # 1. By invocation: WHERE agent_invocation_id = ?
    # 2. By workspace (billing): WHERE workspace_id = ? ORDER BY created_at
    # 3. By correlation: WHERE correlation_id = ?
    # 4. Cost aggregation: WHERE workspace_id = ? AND created_at BETWEEN ...

    op.create_index(
        'idx_usage_invocation',
        'model_usage_records',
        ['agent_invocation_id'],
        schema=SCHEMA,
    )
    op.create_index(
        'idx_usage_workspace_created',
        'model_usage_records',
        ['workspace_id', 'created_at'],
        schema=SCHEMA,
    )
    op.create_index(
        'idx_usage_correlation',
        'model_usage_records',
        ['correlation_id'],
        schema=SCHEMA,
    )

    # ── provider_configs: LLM provider connection config ──────────
    op.create_table(
        'provider_configs',
        sa.Column('id', UUID(), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('provider_name', sa.Text(), nullable=False, unique=True),
        sa.Column('endpoint_url', sa.Text(), nullable=False),
        sa.Column('api_key_ref', sa.Text(), nullable=False),  # Reference to secret-broker, NOT the key itself
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('config', JSONB(), nullable=True),  # Provider-specific config (rate limits, etc.)
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        schema=SCHEMA,
    )

    # Auto-update updated_at on provider_configs
    op.execute(sa.text(f"""
        CREATE OR REPLACE FUNCTION {SCHEMA}.set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """))
    op.execute(sa.text(f"""
        CREATE TRIGGER trg_provider_configs_updated_at
        BEFORE UPDATE ON {SCHEMA}.provider_configs
        FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.set_updated_at();
    """))


def downgrade() -> None:
    op.execute(sa.text(f'DROP TRIGGER IF EXISTS trg_provider_configs_updated_at ON {SCHEMA}.provider_configs'))
    op.execute(sa.text(f'DROP FUNCTION IF EXISTS {SCHEMA}.set_updated_at()'))
    op.drop_table('provider_configs', schema=SCHEMA)
    op.drop_index('idx_usage_correlation', table_name='model_usage_records', schema=SCHEMA)
    op.drop_index('idx_usage_workspace_created', table_name='model_usage_records', schema=SCHEMA)
    op.drop_index('idx_usage_invocation', table_name='model_usage_records', schema=SCHEMA)
    op.drop_table('model_usage_records', schema=SCHEMA)
