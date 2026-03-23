"""SQLAlchemy models for terminal sessions and commands.

Maps to execution_core.terminal_sessions and execution_core.terminal_commands.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .models import SCHEMA, Base


class TerminalSessionRow(Base):
    __tablename__ = "terminal_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'closed')",
            name="ck_terminal_sessions_status",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[str] = mapped_column(UUID(), primary_key=True)
    sandbox_id: Mapped[str] = mapped_column(
        UUID(),
        ForeignKey(f"{SCHEMA}.sandboxes.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_id: Mapped[str] = mapped_column(UUID(), nullable=False)
    workspace_id: Mapped[str] = mapped_column(UUID(), nullable=False)
    user_id: Mapped[str] = mapped_column(Text(), nullable=False)
    status: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default="active",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False,
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )


class TerminalCommandRow(Base):
    __tablename__ = "terminal_commands"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'timed_out')",
            name="ck_terminal_commands_status",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[str] = mapped_column(UUID(), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        UUID(),
        ForeignKey(f"{SCHEMA}.terminal_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    command: Mapped[str] = mapped_column(Text(), nullable=False)
    stdout: Mapped[str | None] = mapped_column(
        Text(), nullable=True, server_default="",
    )
    stderr: Mapped[str | None] = mapped_column(
        Text(), nullable=True, server_default="",
    )
    exit_code: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    status: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default="running",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
