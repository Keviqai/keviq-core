"""Unit tests for workspace-service domain entities and errors."""

import sys
import os
import uuid
from datetime import timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from src.domain.workspace import Workspace, Member, VALID_ROLES, _slugify
from src.domain.workspace_errors import (
    WorkspaceNotFound,
    SlugAlreadyExists,
    MemberNotFound,
    MemberAlreadyExists,
    InvalidRole,
)
from src.domain.capabilities import resolve_capabilities, ROLE_CAPABILITIES


class TestSlugify:
    def test_spaces_become_dashes(self):
        assert _slugify("hello world") == "hello-world"

    def test_uppercase_lowercased(self):
        assert _slugify("MyWorkspace") == "myworkspace"

    def test_special_chars_become_dashes(self):
        # trailing special chars → dashes → stripped
        assert _slugify("hello@world!") == "hello-world"

    def test_multiple_dashes_collapsed(self):
        assert _slugify("hello---world") == "hello-world"

    def test_leading_trailing_dashes_stripped(self):
        assert _slugify("---hello---") == "hello"

    def test_empty_string(self):
        assert _slugify("") == ""

    def test_already_valid_slug(self):
        assert _slugify("my-workspace") == "my-workspace"


class TestWorkspaceCreate:
    def test_slug_is_slugified(self):
        ws = Workspace.create("My Workspace", "My Workspace", uuid.uuid4())
        assert ws.slug == "my-workspace"

    def test_display_name_stripped(self):
        ws = Workspace.create("ws", "  My Workspace  ", uuid.uuid4())
        assert ws.display_name == "My Workspace"

    def test_plan_is_personal(self):
        ws = Workspace.create("ws", "WS", uuid.uuid4())
        assert ws.plan == "personal"

    def test_deployment_mode_is_local(self):
        ws = Workspace.create("ws", "WS", uuid.uuid4())
        assert ws.deployment_mode == "local"

    def test_owner_id_set(self):
        owner = uuid.uuid4()
        ws = Workspace.create("ws", "WS", owner)
        assert ws.owner_id == owner

    def test_id_is_uuid(self):
        ws = Workspace.create("ws", "WS", uuid.uuid4())
        assert isinstance(ws.id, uuid.UUID)

    def test_unique_ids(self):
        owner = uuid.uuid4()
        ws1 = Workspace.create("ws1", "WS1", owner)
        ws2 = Workspace.create("ws2", "WS2", owner)
        assert ws1.id != ws2.id

    def test_timestamps_are_utc(self):
        ws = Workspace.create("ws", "WS", uuid.uuid4())
        assert ws.created_at.tzinfo == timezone.utc
        assert ws.updated_at.tzinfo == timezone.utc

    def test_settings_is_empty_dict(self):
        ws = Workspace.create("ws", "WS", uuid.uuid4())
        assert ws.settings == {}


class TestValidRoles:
    def test_valid_roles_set(self):
        assert VALID_ROLES == {"owner", "admin", "editor", "viewer"}


class TestWorkspaceErrors:
    def test_workspace_not_found_contains_id(self):
        err = WorkspaceNotFound("ws-123")
        assert "ws-123" in str(err)

    def test_slug_already_exists_contains_slug(self):
        err = SlugAlreadyExists("my-slug")
        assert "my-slug" in str(err)

    def test_member_not_found_contains_both_ids(self):
        err = MemberNotFound("ws-1", "user-1")
        assert "ws-1" in str(err)
        assert "user-1" in str(err)

    def test_member_already_exists_contains_both_ids(self):
        err = MemberAlreadyExists("ws-1", "user-1")
        assert "ws-1" in str(err) or "user-1" in str(err)

    def test_invalid_role_contains_role(self):
        err = InvalidRole("superuser")
        assert "superuser" in str(err)


class TestResolveCapabilities:
    def test_owner_gets_most_capabilities(self):
        caps = resolve_capabilities("owner")
        assert "workspace:view" in caps
        assert "workspace:manage_members" in caps
        assert "workspace:delete" in caps
        assert "task:create" in caps

    def test_viewer_gets_limited_capabilities(self):
        caps = resolve_capabilities("viewer")
        assert "workspace:view" in caps
        assert "task:view" in caps
        assert "task:create" not in caps
        assert "workspace:manage_members" not in caps

    def test_editor_can_create_tasks(self):
        caps = resolve_capabilities("editor")
        assert "task:create" in caps
        assert "workspace:delete" not in caps

    def test_unknown_role_returns_empty(self):
        caps = resolve_capabilities("superuser")
        assert caps == []

    def test_returns_list(self):
        caps = resolve_capabilities("admin")
        assert isinstance(caps, list)

    def test_viewer_subset_of_owner(self):
        owner_caps = set(resolve_capabilities("owner"))
        viewer_caps = set(resolve_capabilities("viewer"))
        assert viewer_caps.issubset(owner_caps)

    def test_all_roles_covered(self):
        for role in ROLE_CAPABILITIES:
            caps = resolve_capabilities(role)
            assert len(caps) > 0
