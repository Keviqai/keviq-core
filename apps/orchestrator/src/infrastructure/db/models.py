"""SQLAlchemy models mapping to orchestrator_core schema (PR7 migrations).

These models are used only by the infrastructure layer.
Domain layer must NOT import this module.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
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


SCHEMA = "orchestrator_core"


class Base(DeclarativeBase):
    pass


class TaskRow(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(
            "task_type IN ('coding', 'research', 'analysis', 'operation', 'custom')",
            name="ck_tasks_task_type",
        ),
        CheckConstraint(
            "task_status IN ('draft', 'pending', 'running', 'waiting_approval', "
            "'completed', 'failed', 'cancelled', 'archived')",
            name="ck_tasks_task_status",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[str] = mapped_column(UUID(), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(UUID(), nullable=False)
    title: Mapped[str] = mapped_column(Text(), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    task_type: Mapped[str] = mapped_column(Text(), nullable=False)
    task_status: Mapped[str] = mapped_column(Text(), nullable=False, server_default="pending")
    input_config: Mapped[dict] = mapped_column(JSONB(), nullable=False, server_default=text("'{}'"))
    repo_snapshot_id: Mapped[str | None] = mapped_column(UUID(), nullable=True)
    policy_id: Mapped[str | None] = mapped_column(UUID(), nullable=True)
    parent_task_id: Mapped[str | None] = mapped_column(
        UUID(), ForeignKey(f"{SCHEMA}.tasks.id", ondelete="SET NULL"), nullable=True,
    )
    created_by_id: Mapped[str] = mapped_column(UUID(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False,
    )
    # Q1 brief fields
    goal: Mapped[str | None] = mapped_column(Text(), nullable=True)
    context: Mapped[str | None] = mapped_column(Text(), nullable=True)
    constraints: Mapped[str | None] = mapped_column(Text(), nullable=True)
    desired_output: Mapped[str | None] = mapped_column(Text(), nullable=True)
    template_id: Mapped[str | None] = mapped_column(UUID(), nullable=True)
    agent_template_id: Mapped[str | None] = mapped_column(UUID(), nullable=True)
    risk_level: Mapped[str | None] = mapped_column(Text(), nullable=True)


class RunRow(Base):
    __tablename__ = "runs"
    __table_args__ = (
        CheckConstraint(
            "run_status IN ('queued', 'preparing', 'running', 'waiting_approval', "
            "'completing', 'completed', 'failed', 'timed_out', 'cancelled')",
            name="ck_runs_run_status",
        ),
        CheckConstraint(
            "trigger_type IN ('manual', 'scheduled', 'event', 'approval')",
            name="ck_runs_trigger_type",
        ),
        CheckConstraint("duration_ms >= 0", name="ck_runs_duration_non_negative"),
        {"schema": SCHEMA},
    )

    id: Mapped[str] = mapped_column(UUID(), primary_key=True)
    task_id: Mapped[str] = mapped_column(
        UUID(), ForeignKey(f"{SCHEMA}.tasks.id", ondelete="CASCADE"), nullable=False,
    )
    workspace_id: Mapped[str] = mapped_column(UUID(), nullable=False)
    run_status: Mapped[str] = mapped_column(Text(), nullable=False, server_default="queued")
    trigger_type: Mapped[str] = mapped_column(Text(), nullable=False, server_default="manual")
    triggered_by_id: Mapped[str | None] = mapped_column(UUID(), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    run_config: Mapped[dict] = mapped_column(JSONB(), nullable=False, server_default=text("'{}'"))
    error_summary: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False,
    )


class StepRow(Base):
    __tablename__ = "steps"
    __table_args__ = (
        CheckConstraint(
            "step_type IN ('agent_invocation', 'tool_call', 'approval_gate', 'condition', 'transform')",
            name="ck_steps_step_type",
        ),
        CheckConstraint(
            "step_status IN ('pending', 'running', 'waiting_approval', "
            "'completed', 'failed', 'skipped', 'blocked', 'cancelled')",
            name="ck_steps_step_status",
        ),
        CheckConstraint("sequence > 0", name="ck_steps_sequence_positive"),
        UniqueConstraint("run_id", "sequence", name="uq_steps_run_sequence"),
        {"schema": SCHEMA},
    )

    id: Mapped[str] = mapped_column(UUID(), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        UUID(), ForeignKey(f"{SCHEMA}.runs.id", ondelete="CASCADE"), nullable=False,
    )
    workspace_id: Mapped[str] = mapped_column(UUID(), nullable=False)
    step_type: Mapped[str] = mapped_column(Text(), nullable=False, server_default="agent_invocation")
    step_status: Mapped[str] = mapped_column(Text(), nullable=False, server_default="pending")
    sequence: Mapped[int] = mapped_column(Integer(), nullable=False, server_default="1")
    parent_step_id: Mapped[str | None] = mapped_column(
        UUID(), ForeignKey(f"{SCHEMA}.steps.id", ondelete="SET NULL"), nullable=True,
    )
    input_snapshot: Mapped[dict | None] = mapped_column(JSONB(), nullable=True)
    output_snapshot: Mapped[dict | None] = mapped_column(JSONB(), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_detail: Mapped[dict | None] = mapped_column(JSONB(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False,
    )


class ApprovalRequestRow(Base):
    __tablename__ = "approval_requests"
    __table_args__ = (
        CheckConstraint(
            "target_type IN ('task', 'run', 'step', 'artifact')",
            name="ck_approval_requests_target_type",
        ),
        CheckConstraint(
            "decision IN ('pending', 'approved', 'rejected', 'timed_out', 'cancelled')",
            name="ck_approval_requests_decision",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[str] = mapped_column(UUID(), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(UUID(), nullable=False)
    target_type: Mapped[str] = mapped_column(Text(), nullable=False)
    target_id: Mapped[str] = mapped_column(UUID(), nullable=False)
    requested_by: Mapped[str] = mapped_column(Text(), nullable=False)
    reviewer_id: Mapped[str | None] = mapped_column(UUID(), nullable=True)
    prompt: Mapped[str | None] = mapped_column(Text(), nullable=True)
    timeout_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision: Mapped[str] = mapped_column(Text(), nullable=False, server_default="pending")
    decided_by_id: Mapped[str | None] = mapped_column(UUID(), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_comment: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False,
    )


class TaskTemplateRow(Base):
    __tablename__ = "task_templates"
    __table_args__ = (
        CheckConstraint(
            "scope IN ('system', 'workspace')", name="ck_tt_scope",
        ),
        CheckConstraint(
            "category IN ('research', 'analysis', 'operation', 'custom')",
            name="ck_tt_category",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[str] = mapped_column(UUID(), primary_key=True)
    name: Mapped[str] = mapped_column(Text(), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    category: Mapped[str] = mapped_column(Text(), nullable=False)
    prefilled_fields: Mapped[dict] = mapped_column(
        JSONB(), nullable=False, server_default=text("'{}'"),
    )
    expected_output_type: Mapped[str | None] = mapped_column(Text(), nullable=True)
    scope: Mapped[str] = mapped_column(Text(), nullable=False, server_default="system")
    workspace_id: Mapped[str | None] = mapped_column(UUID(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False,
    )


class AgentTemplateRow(Base):
    __tablename__ = "agent_templates"
    __table_args__ = (
        CheckConstraint(
            "scope IN ('system', 'workspace')", name="ck_at_scope",
        ),
        CheckConstraint(
            "default_risk_profile IN ('low', 'medium', 'high')",
            name="ck_at_risk",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[str] = mapped_column(UUID(), primary_key=True)
    name: Mapped[str] = mapped_column(Text(), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    best_for: Mapped[str | None] = mapped_column(Text(), nullable=True)
    not_for: Mapped[str | None] = mapped_column(Text(), nullable=True)
    capabilities_manifest: Mapped[list] = mapped_column(
        JSONB(), nullable=False, server_default=text("'[]'"),
    )
    default_output_types: Mapped[list] = mapped_column(
        JSONB(), nullable=False, server_default=text("'[]'"),
    )
    default_risk_profile: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default="medium",
    )
    scope: Mapped[str] = mapped_column(Text(), nullable=False, server_default="system")
    workspace_id: Mapped[str | None] = mapped_column(UUID(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False,
    )


class OutboxRow(Base):
    __tablename__ = "outbox"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[str] = mapped_column(UUID(), primary_key=True, server_default=text("gen_random_uuid()"))
    event_type: Mapped[str] = mapped_column(Text(), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB(), nullable=False)
    correlation_id: Mapped[str] = mapped_column(UUID(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer(), server_default="0", nullable=False)
