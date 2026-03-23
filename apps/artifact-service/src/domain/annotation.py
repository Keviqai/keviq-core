"""ArtifactAnnotation domain entity.

Simple body-only annotation — no disposition enum.
Body is capped at MAX_BODY_LENGTH to prevent abuse.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from .errors import DomainValidationError

MAX_BODY_LENGTH = 4000


class ArtifactAnnotation:
    """An annotation left on an artifact by a workspace member."""

    __slots__ = (
        '_id', '_artifact_id', '_workspace_id', '_author_id',
        '_body', '_created_at',
    )

    def __init__(
        self,
        *,
        id: UUID,
        artifact_id: UUID,
        workspace_id: UUID,
        author_id: UUID,
        body: str,
        created_at: datetime,
    ) -> None:
        if not body or not body.strip():
            raise DomainValidationError("Annotation body must not be empty")
        if len(body) > MAX_BODY_LENGTH:
            raise DomainValidationError(
                f"Annotation body exceeds {MAX_BODY_LENGTH} characters"
            )
        self._id = id
        self._artifact_id = artifact_id
        self._workspace_id = workspace_id
        self._author_id = author_id
        self._body = body
        self._created_at = created_at

    @classmethod
    def create(
        cls,
        *,
        artifact_id: UUID,
        workspace_id: UUID,
        author_id: UUID,
        body: str,
    ) -> ArtifactAnnotation:
        return cls(
            id=uuid4(),
            artifact_id=artifact_id,
            workspace_id=workspace_id,
            author_id=author_id,
            body=body,
            created_at=datetime.now(timezone.utc),
        )

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def artifact_id(self) -> UUID:
        return self._artifact_id

    @property
    def workspace_id(self) -> UUID:
        return self._workspace_id

    @property
    def author_id(self) -> UUID:
        return self._author_id

    @property
    def body(self) -> str:
        return self._body

    @property
    def created_at(self) -> datetime:
        return self._created_at
