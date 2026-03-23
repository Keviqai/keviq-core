"""Command DTOs for approval operations.

Pure data — no logic, no infra imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CreateApprovalRequest:
    workspace_id: UUID
    target_type: str  # "artifact" for Q4-S1; enum values from ApprovalTargetType
    target_id: UUID
    requested_by: str  # from gateway-injected X-User-Id header (never from request body)
    prompt: str
    correlation_id: UUID
    reviewer_id: UUID | None = None  # optional; validated as workspace member if provided


@dataclass(frozen=True, slots=True)
class DecideApproval:
    approval_id: UUID
    workspace_id: UUID
    decided_by_id: UUID
    decision: str  # "approve" or "reject"
    comment: str | None = None
