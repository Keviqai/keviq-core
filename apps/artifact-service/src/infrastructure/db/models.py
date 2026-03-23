"""SQLAlchemy models mapping to artifact_core schema (PR26 migrations).

These models are used only by the infrastructure layer.
Domain layer must NOT import this module.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


SCHEMA = "artifact_core"


class Base(DeclarativeBase):
    pass


class ArtifactRow(Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        CheckConstraint(
            "artifact_status IN ('pending', 'writing', 'ready', 'failed', "
            "'superseded', 'archived')",
            name="chk_artifact_status",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[str] = mapped_column(UUID(), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(UUID(), nullable=False)
    task_id: Mapped[str] = mapped_column(UUID(), nullable=False)
    run_id: Mapped[str] = mapped_column(UUID(), nullable=False)
    step_id: Mapped[str | None] = mapped_column(UUID(), nullable=True)
    agent_invocation_id: Mapped[str | None] = mapped_column(UUID(), nullable=True)
    root_type: Mapped[str] = mapped_column(Text(), nullable=False)
    artifact_type: Mapped[str] = mapped_column(Text(), nullable=False)
    artifact_status: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default="pending",
    )
    name: Mapped[str] = mapped_column(Text(), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(Text(), nullable=True)
    storage_ref: Mapped[str | None] = mapped_column(Text(), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger(), nullable=True)
    checksum: Mapped[str | None] = mapped_column(Text(), nullable=True)
    lineage: Mapped[dict] = mapped_column(
        JSONB(), nullable=False, server_default=text("'[]'"),
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB(), nullable=False, server_default=text("'{}'"),
    )
    ready_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    failed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False,
    )


class ProvenanceRow(Base):
    __tablename__ = "artifact_provenance"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[str] = mapped_column(
        UUID(), primary_key=True, server_default=text("gen_random_uuid()"),
    )
    artifact_id: Mapped[str] = mapped_column(UUID(), nullable=False)
    input_snapshot: Mapped[dict] = mapped_column(
        JSONB(), nullable=False, server_default=text("'[]'"),
    )
    run_config_hash: Mapped[str | None] = mapped_column(Text(), nullable=True)
    tool_name: Mapped[str | None] = mapped_column(Text(), nullable=True)
    tool_version: Mapped[str | None] = mapped_column(Text(), nullable=True)
    tool_config_hash: Mapped[str | None] = mapped_column(Text(), nullable=True)
    model_provider: Mapped[str | None] = mapped_column(Text(), nullable=True)
    model_name_concrete: Mapped[str | None] = mapped_column(Text(), nullable=True)
    model_version_concrete: Mapped[str | None] = mapped_column(Text(), nullable=True)
    model_temperature: Mapped[float | None] = mapped_column(Float(), nullable=True)
    model_max_tokens: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    system_prompt_hash: Mapped[str | None] = mapped_column(Text(), nullable=True)
    lineage_chain: Mapped[dict] = mapped_column(
        JSONB(), nullable=False, server_default=text("'[]'"),
    )
    correlation_id: Mapped[str | None] = mapped_column(UUID(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False,
    )


class LineageEdgeRow(Base):
    __tablename__ = "artifact_lineage_edges"
    __table_args__ = (
        CheckConstraint(
            "edge_type IN ('derived_from', 'transformed_from', "
            "'aggregated_from', 'promoted_from')",
            name="chk_edge_type",
        ),
        UniqueConstraint(
            "child_artifact_id", "parent_artifact_id", "edge_type",
            name="uq_lineage_edge",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[str] = mapped_column(
        UUID(), primary_key=True, server_default=text("gen_random_uuid()"),
    )
    child_artifact_id: Mapped[str] = mapped_column(UUID(), nullable=False)
    parent_artifact_id: Mapped[str] = mapped_column(UUID(), nullable=False)
    edge_type: Mapped[str] = mapped_column(Text(), nullable=False)
    run_id: Mapped[str | None] = mapped_column(UUID(), nullable=True)
    step_id: Mapped[str | None] = mapped_column(UUID(), nullable=True)
    transform_detail: Mapped[dict] = mapped_column(
        JSONB(), nullable=False, server_default=text("'{}'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False,
    )


class AnnotationRow(Base):
    __tablename__ = "artifact_annotations"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[str] = mapped_column(
        UUID(), primary_key=True, server_default=text("gen_random_uuid()"),
    )
    artifact_id: Mapped[str] = mapped_column(UUID(), nullable=False)
    workspace_id: Mapped[str] = mapped_column(UUID(), nullable=False)
    author_id: Mapped[str] = mapped_column(UUID(), nullable=False)
    body: Mapped[str] = mapped_column(Text(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False,
    )


class ArtifactTagRow(Base):
    __tablename__ = "artifact_tags"
    __table_args__ = (
        UniqueConstraint("artifact_id", "tag", name="uq_artifact_tag"),
        {"schema": SCHEMA},
    )

    id: Mapped[str] = mapped_column(
        UUID(), primary_key=True, server_default=text("gen_random_uuid()"),
    )
    artifact_id: Mapped[str] = mapped_column(UUID(), nullable=False)
    workspace_id: Mapped[str] = mapped_column(UUID(), nullable=False)
    tag: Mapped[str] = mapped_column(Text(), nullable=False)
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
