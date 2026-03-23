"""Add updated_at column to runs and steps tables.

Revision ID: a004
Revises: a003
"""

from alembic import op
import sqlalchemy as sa

revision = "a004"
down_revision = "a003"

_SCHEMA = "orchestrator_core"


def upgrade() -> None:
    op.add_column(
        "runs",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        schema=_SCHEMA,
    )
    op.add_column(
        "steps",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        schema=_SCHEMA,
    )

    # Backfill: set updated_at = created_at for existing rows
    op.execute(f"UPDATE {_SCHEMA}.runs SET updated_at = created_at")
    op.execute(f"UPDATE {_SCHEMA}.steps SET updated_at = created_at")

    # Replace old recovery indexes (created_at) with updated_at
    op.drop_index("idx_runs_status_created", table_name="runs", schema=_SCHEMA)
    op.drop_index("idx_steps_status_created", table_name="steps", schema=_SCHEMA)

    op.create_index(
        "idx_runs_status_updated",
        "runs",
        ["run_status", "updated_at"],
        schema=_SCHEMA,
        postgresql_where="run_status NOT IN ('completed', 'failed', 'cancelled')",
    )
    op.create_index(
        "idx_steps_status_updated",
        "steps",
        ["step_status", "updated_at"],
        schema=_SCHEMA,
        postgresql_where="step_status NOT IN ('completed', 'failed', 'skipped', 'cancelled')",
    )


def downgrade() -> None:
    op.drop_index("idx_steps_status_updated", table_name="steps", schema=_SCHEMA)
    op.drop_index("idx_runs_status_updated", table_name="runs", schema=_SCHEMA)

    op.create_index(
        "idx_runs_status_created",
        "runs",
        ["run_status", "created_at"],
        schema=_SCHEMA,
        postgresql_where="run_status NOT IN ('completed', 'failed', 'cancelled')",
    )
    op.create_index(
        "idx_steps_status_created",
        "steps",
        ["step_status", "created_at"],
        schema=_SCHEMA,
        postgresql_where="step_status NOT IN ('completed', 'failed', 'skipped', 'cancelled')",
    )

    op.drop_column("steps", "updated_at", schema=_SCHEMA)
    op.drop_column("runs", "updated_at", schema=_SCHEMA)
