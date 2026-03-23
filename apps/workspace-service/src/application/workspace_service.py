"""Workspace application service — use cases for workspace and member management."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from src.domain.workspace import Workspace, VALID_ROLES
from src.domain.workspace_errors import (
    InvalidRole,
    MemberAlreadyExists,
    MemberNotFound,
    SlugAlreadyExists,
    WorkspaceNotFound,
)

from .bootstrap import get_outbox_writer, get_workspace_repo


def create_workspace(
    db,
    slug: str,
    display_name: str,
    owner_id: uuid.UUID,
    correlation_id: uuid.UUID | None = None,
) -> dict:
    workspace_repo = get_workspace_repo()
    outbox_writer = get_outbox_writer()

    ws = Workspace.create(slug=slug, display_name=display_name, owner_id=owner_id)

    existing = workspace_repo.find_workspace_by_slug(db, ws.slug)
    if existing:
        raise SlugAlreadyExists(ws.slug)

    ws_dict = {
        'id': ws.id,
        'slug': ws.slug,
        'display_name': ws.display_name,
        'plan': ws.plan,
        'deployment_mode': ws.deployment_mode,
        'owner_id': ws.owner_id,
        'created_at': ws.created_at,
        'updated_at': ws.updated_at,
        'settings': ws.settings,
    }
    result = workspace_repo.insert_workspace(db, ws_dict)

    now = datetime.now(timezone.utc)
    workspace_repo.insert_member(db, {
        'id': uuid.uuid4(),
        'workspace_id': ws.id,
        'user_id': owner_id,
        'role': 'owner',
        'joined_at': now,
        'updated_at': now,
        'invited_by_id': None,
    })

    corr_id = correlation_id or uuid.uuid4()
    outbox_writer.insert_event(
        db,
        event_type='workspace.created',
        workspace_id=ws.id,
        payload={
            'workspace_id': str(ws.id),
            'slug': ws.slug,
            'display_name': ws.display_name,
            'owner_id': str(owner_id),
        },
        correlation_id=corr_id,
        actor_id=str(owner_id),
    )

    db.commit()
    return result


def list_workspaces(db, user_id: uuid.UUID, *, limit: int = 50, offset: int = 0) -> list[dict]:
    return get_workspace_repo().find_workspaces_by_user(db, user_id, limit=limit, offset=offset)


def get_workspace(db, workspace_id: uuid.UUID) -> dict:
    ws = get_workspace_repo().find_workspace_by_id(db, workspace_id)
    if not ws:
        raise WorkspaceNotFound(str(workspace_id))
    return ws


def update_workspace(
    db,
    workspace_id: uuid.UUID,
    updates: dict,
    actor_id: uuid.UUID | None = None,
    correlation_id: uuid.UUID | None = None,
) -> dict:
    workspace_repo = get_workspace_repo()
    outbox_writer = get_outbox_writer()

    result = workspace_repo.update_workspace(db, workspace_id, updates)
    if not result:
        raise WorkspaceNotFound(str(workspace_id))

    corr_id = correlation_id or uuid.uuid4()
    outbox_writer.insert_event(
        db,
        event_type='workspace.updated',
        workspace_id=workspace_id,
        payload={
            'workspace_id': str(workspace_id),
            'updated_fields': list(updates.keys()),
        },
        correlation_id=corr_id,
        actor_id=str(actor_id) if actor_id else 'system',
    )

    db.commit()
    return result


def delete_workspace(
    db,
    workspace_id: uuid.UUID,
    actor_id: uuid.UUID | None = None,
    correlation_id: uuid.UUID | None = None,
) -> None:
    workspace_repo = get_workspace_repo()
    outbox_writer = get_outbox_writer()

    deleted = workspace_repo.delete_workspace(db, workspace_id)
    if not deleted:
        raise WorkspaceNotFound(str(workspace_id))

    corr_id = correlation_id or uuid.uuid4()
    outbox_writer.insert_event(
        db,
        event_type='workspace.deleted',
        workspace_id=workspace_id,
        payload={'workspace_id': str(workspace_id)},
        correlation_id=corr_id,
        actor_id=str(actor_id) if actor_id else 'system',
    )

    db.commit()


# ── Members ────────────────────────────────────────────────────────

def list_members(db, workspace_id: uuid.UUID, *, limit: int = 200, offset: int = 0) -> list[dict]:
    from .bootstrap import get_member_enricher
    members = get_workspace_repo().find_members_by_workspace(db, workspace_id, limit=limit, offset=offset)
    enricher = get_member_enricher()
    if enricher:
        enricher.enrich(members)
    return members


def get_member(db, workspace_id: uuid.UUID, user_id: uuid.UUID) -> dict:
    member = get_workspace_repo().find_member(db, workspace_id, user_id)
    if not member:
        raise MemberNotFound(str(workspace_id), str(user_id))
    return member


def invite_member(
    db,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str = 'viewer',
    invited_by_id: uuid.UUID | None = None,
    correlation_id: uuid.UUID | None = None,
) -> dict:
    workspace_repo = get_workspace_repo()
    outbox_writer = get_outbox_writer()

    if role not in VALID_ROLES:
        raise InvalidRole(role)

    existing = workspace_repo.find_member(db, workspace_id, user_id)
    if existing:
        raise MemberAlreadyExists(str(workspace_id), str(user_id))

    now = datetime.now(timezone.utc)
    result = workspace_repo.insert_member(db, {
        'id': uuid.uuid4(),
        'workspace_id': workspace_id,
        'user_id': user_id,
        'role': role,
        'joined_at': now,
        'updated_at': now,
        'invited_by_id': invited_by_id,
    })

    corr_id = correlation_id or uuid.uuid4()
    outbox_writer.insert_event(
        db,
        event_type='workspace.member_added',
        workspace_id=workspace_id,
        payload={
            'workspace_id': str(workspace_id),
            'user_id': str(user_id),
            'role': role,
            'invited_by_id': str(invited_by_id) if invited_by_id else None,
        },
        correlation_id=corr_id,
        actor_id=str(invited_by_id) if invited_by_id else str(user_id),
    )

    db.commit()
    return result


def update_member_role(
    db,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str,
    actor_id: uuid.UUID | None = None,
    correlation_id: uuid.UUID | None = None,
) -> dict:
    workspace_repo = get_workspace_repo()
    outbox_writer = get_outbox_writer()

    if role not in VALID_ROLES:
        raise InvalidRole(role)

    result = workspace_repo.update_member_role(db, workspace_id, user_id, role)
    if not result:
        raise MemberNotFound(str(workspace_id), str(user_id))

    corr_id = correlation_id or uuid.uuid4()
    outbox_writer.insert_event(
        db,
        event_type='workspace.member_role_updated',
        workspace_id=workspace_id,
        payload={
            'workspace_id': str(workspace_id),
            'user_id': str(user_id),
            'new_role': role,
        },
        correlation_id=corr_id,
        actor_id=str(actor_id) if actor_id else str(user_id),
    )

    db.commit()
    return result


def remove_member(
    db,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    actor_id: uuid.UUID | None = None,
    correlation_id: uuid.UUID | None = None,
) -> None:
    workspace_repo = get_workspace_repo()
    outbox_writer = get_outbox_writer()

    deleted = workspace_repo.delete_member(db, workspace_id, user_id)
    if not deleted:
        raise MemberNotFound(str(workspace_id), str(user_id))

    corr_id = correlation_id or uuid.uuid4()
    outbox_writer.insert_event(
        db,
        event_type='workspace.member_removed',
        workspace_id=workspace_id,
        payload={
            'workspace_id': str(workspace_id),
            'user_id': str(user_id),
        },
        correlation_id=corr_id,
        actor_id=str(actor_id) if actor_id else str(user_id),
    )

    db.commit()
