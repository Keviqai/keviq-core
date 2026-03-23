"""Pydantic request/response schemas for notification-service API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateNotificationRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=200)
    title: str = Field(..., min_length=1, max_length=200)
    body: str | None = Field(default=None, max_length=2000)
    category: str = Field(default='system', pattern=r'^(task|run|approval|artifact|workspace|system)$')
    priority: str = Field(default='normal', pattern=r'^(low|normal|high|urgent)$')
    link: str | None = Field(default=None, max_length=500)
    recipient_email: str | None = Field(default=None, max_length=320)


class NotificationResponse(BaseModel):
    id: str
    workspace_id: str
    user_id: str
    title: str
    body: str
    category: str
    priority: str
    link: str
    is_read: bool
    created_at: str
    read_at: str | None
