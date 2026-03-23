"""SQLAlchemy models mapping to execution_core schema (PR19 migrations).

These models are used only by the infrastructure layer.
Domain layer must NOT import this module.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


SCHEMA = "execution_core"


class Base(DeclarativeBase):
    pass


class SandboxRow(Base):
    __tablename__ = "sandboxes"
    __table_args__ = (
        CheckConstraint(
            "sandbox_type IN ('container', 'subprocess')",
            name="ck_sandboxes_type",
        ),
        CheckConstraint(
            "sandbox_status IN ('provisioning', 'ready', 'executing', 'idle', "
            "'terminating', 'terminated', 'failed')",
            name="ck_sandboxes_status",
        ),
        CheckConstraint(
            "termination_reason IS NULL OR termination_reason IN "
            "('completed', 'timeout', 'policy_violation', 'error', 'manual')",
            name="ck_sandboxes_termination_reason",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[str] = mapped_column(UUID(), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(UUID(), nullable=False)
    task_id: Mapped[str] = mapped_column(UUID(), nullable=False)
    run_id: Mapped[str] = mapped_column(UUID(), nullable=False)
    step_id: Mapped[str] = mapped_column(UUID(), nullable=False)
    agent_invocation_id: Mapped[str] = mapped_column(UUID(), nullable=False)
    sandbox_type: Mapped[str] = mapped_column(Text(), nullable=False)
    sandbox_status: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default="provisioning",
    )
    policy_snapshot: Mapped[dict] = mapped_column(
        JSONB(), nullable=False, server_default=text("'{}'"),
    )
    resource_limits: Mapped[dict] = mapped_column(
        JSONB(), nullable=False, server_default=text("'{}'"),
    )
    network_egress_policy: Mapped[dict] = mapped_column(
        JSONB(), nullable=False, server_default=text("'{}'"),
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    terminated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    termination_reason: Mapped[str | None] = mapped_column(Text(), nullable=True)
    error_detail: Mapped[dict | None] = mapped_column(JSONB(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False,
    )


class SandboxAttemptRow(Base):
    __tablename__ = "sandbox_attempts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'timed_out')",
            name="ck_sandbox_attempts_status",
        ),
        UniqueConstraint(
            "sandbox_id", "attempt_index",
            name="uq_sandbox_attempts_sandbox_attempt",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[str] = mapped_column(UUID(), primary_key=True)
    sandbox_id: Mapped[str] = mapped_column(
        UUID(),
        ForeignKey(f"{SCHEMA}.sandboxes.id", ondelete="CASCADE"),
        nullable=False,
    )
    attempt_index: Mapped[int] = mapped_column(Integer(), nullable=False)
    tool_name: Mapped[str] = mapped_column(Text(), nullable=False)
    tool_input: Mapped[dict | None] = mapped_column(JSONB(), nullable=True)
    status: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default="pending",
    )
    stdout: Mapped[str | None] = mapped_column(Text(), nullable=True)
    stderr: Mapped[str | None] = mapped_column(Text(), nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    truncated: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default="false",
    )
    error_detail: Mapped[dict | None] = mapped_column(JSONB(), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False,
    )


class OutboxRow(Base):
    __tablename__ = "outbox"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[str] = mapped_column(
        UUID(), primary_key=True, server_default=text("gen_random_uuid()"),
    )
    event_type: Mapped[str] = mapped_column(Text(), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB(), nullable=False)
    correlation_id: Mapped[str] = mapped_column(UUID(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    attempts: Mapped[int] = mapped_column(
        Integer(), server_default="0", nullable=False,
    )
