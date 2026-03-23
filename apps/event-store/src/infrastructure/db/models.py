"""SQLAlchemy models for event_core schema."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class EventRow(Base):
    __tablename__ = "events"
    __table_args__ = {"schema": "event_core"}

    id: Mapped[str] = mapped_column(UUID(), primary_key=True)
    event_type: Mapped[str] = mapped_column(Text(), nullable=False)
    schema_version: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default="1.0"
    )
    workspace_id: Mapped[str] = mapped_column(UUID(), nullable=False)
    task_id: Mapped[str | None] = mapped_column(UUID(), nullable=True)
    run_id: Mapped[str | None] = mapped_column(UUID(), nullable=True)
    step_id: Mapped[str | None] = mapped_column(UUID(), nullable=True)
    correlation_id: Mapped[str] = mapped_column(UUID(), nullable=False)
    causation_id: Mapped[str | None] = mapped_column(UUID(), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    emitted_by: Mapped[dict] = mapped_column(JSONB(), nullable=False)
    actor: Mapped[dict] = mapped_column(JSONB(), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB(), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("NOW()"),
        nullable=False,
    )
