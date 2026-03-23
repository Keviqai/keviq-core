"""Unit tests for policy-service permission domain and resolution logic."""

import sys
import os
import uuid
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from src.domain.permissions import (
    ROLE_PERMISSIONS,
    ALL_PERMISSIONS,
    role_has_permission,
    resolve_permission,
)
from src.domain.policy_errors import PolicyNotFound


class TestRoleHasPermission:
    def test_owner_has_workspace_view(self):
        assert role_has_permission("owner", "workspace:view") is True

    def test_owner_has_delete(self):
        assert role_has_permission("owner", "workspace:delete") is True

    def test_viewer_has_workspace_view(self):
        assert role_has_permission("viewer", "workspace:view") is True

    def test_viewer_cannot_create_tasks(self):
        assert role_has_permission("viewer", "task:create") is False

    def test_viewer_cannot_delete_workspace(self):
        assert role_has_permission("viewer", "workspace:delete") is False

    def test_editor_can_create_tasks(self):
        assert role_has_permission("editor", "task:create") is True

    def test_editor_cannot_manage_members(self):
        assert role_has_permission("editor", "workspace:manage_members") is False

    def test_unknown_role_returns_false(self):
        assert role_has_permission("superuser", "workspace:view") is False

    def test_unknown_permission_returns_false(self):
        assert role_has_permission("owner", "workspace:fly") is False

    def test_admin_has_manage_secrets(self):
        assert role_has_permission("admin", "workspace:manage_secrets") is True

    def test_admin_cannot_delete_workspace(self):
        assert role_has_permission("admin", "workspace:delete") is False


class TestAllPermissions:
    def test_is_sorted(self):
        assert ALL_PERMISSIONS == sorted(ALL_PERMISSIONS)

    def test_no_duplicates(self):
        assert len(ALL_PERMISSIONS) == len(set(ALL_PERMISSIONS))

    def test_contains_core_permissions(self):
        assert "workspace:view" in ALL_PERMISSIONS
        assert "task:create" in ALL_PERMISSIONS
        assert "workspace:delete" in ALL_PERMISSIONS


class TestResolvePermission:
    """Test the 6-step permission resolution: deny rules → allow rules → role."""

    def test_role_grants_permission_no_rules(self):
        allowed, reason = resolve_permission("owner", "workspace:view")
        assert allowed is True
        assert "role:owner" in reason

    def test_role_denies_permission_no_rules(self):
        allowed, reason = resolve_permission("viewer", "workspace:delete")
        assert allowed is False
        assert "viewer" in reason

    def test_unknown_role_denied(self):
        allowed, reason = resolve_permission("ghost", "workspace:view")
        assert allowed is False

    def test_deny_rule_overrides_role_grant(self):
        """A deny rule must block even a role that normally grants the permission."""
        rules = [{"effect": "deny", "permission": "workspace:view"}]
        allowed, reason = resolve_permission("owner", "workspace:view", rules)
        assert allowed is False
        assert "deny" in reason

    def test_allow_rule_overrides_role_deny(self):
        """An allow rule elevates a role that normally lacks permission."""
        rules = [{"effect": "allow", "permission": "workspace:delete"}]
        allowed, reason = resolve_permission("viewer", "workspace:delete", rules)
        assert allowed is True
        assert "allow" in reason

    def test_deny_wins_over_allow_same_permission(self):
        """When both deny and allow rules exist for same permission, deny wins (checked first)."""
        rules = [
            {"effect": "allow", "permission": "workspace:delete"},
            {"effect": "deny", "permission": "workspace:delete"},
        ]
        allowed, reason = resolve_permission("owner", "workspace:delete", rules)
        assert allowed is False

    def test_rule_for_different_permission_has_no_effect(self):
        """Deny rule on unrelated permission does not affect the queried permission."""
        rules = [{"effect": "deny", "permission": "workspace:delete"}]
        allowed, reason = resolve_permission("owner", "workspace:view", rules)
        assert allowed is True

    def test_empty_rules_list_falls_back_to_role(self):
        allowed, reason = resolve_permission("editor", "task:create", [])
        assert allowed is True

    def test_none_rules_falls_back_to_role(self):
        allowed, reason = resolve_permission("editor", "task:create", None)
        assert allowed is True

    def test_returns_tuple_of_bool_and_str(self):
        result = resolve_permission("owner", "workspace:view")
        assert isinstance(result, tuple)
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)


class TestPolicyErrors:
    def test_policy_not_found_contains_id(self):
        err = PolicyNotFound("pol-123")
        assert "pol-123" in str(err)


class TestPolicyService:
    """Application layer: check_permission delegates to domain + repo."""

    def test_check_permission_allowed(self):
        import src.application.policy_service as svc

        mock_repo = MagicMock()
        mock_repo.find_policies_by_workspace.return_value = []
        mock_repo.log_permission_decision.return_value = None

        with patch.object(svc, "get_policy_repo", return_value=mock_repo):
            result = svc.check_permission(
                db=MagicMock(),
                actor_id=uuid.uuid4(),
                workspace_id=uuid.uuid4(),
                permission="workspace:view",
                role="owner",
            )

        assert result["allowed"] is True

    def test_check_permission_denied_for_viewer_on_delete(self):
        import src.application.policy_service as svc

        mock_repo = MagicMock()
        mock_repo.find_policies_by_workspace.return_value = []
        mock_repo.log_permission_decision.return_value = None

        with patch.object(svc, "get_policy_repo", return_value=mock_repo):
            result = svc.check_permission(
                db=MagicMock(),
                actor_id=uuid.uuid4(),
                workspace_id=uuid.uuid4(),
                permission="workspace:delete",
                role="viewer",
            )

        assert result["allowed"] is False

    def test_check_permission_deny_rule_applied(self):
        import src.application.policy_service as svc

        mock_repo = MagicMock()
        mock_repo.find_policies_by_workspace.return_value = [
            {"rules": [{"effect": "deny", "permission": "workspace:view"}]}
        ]
        mock_repo.log_permission_decision.return_value = None

        with patch.object(svc, "get_policy_repo", return_value=mock_repo):
            result = svc.check_permission(
                db=MagicMock(),
                actor_id=uuid.uuid4(),
                workspace_id=uuid.uuid4(),
                permission="workspace:view",
                role="owner",
            )

        assert result["allowed"] is False

    def test_get_policy_not_found_raises(self):
        import src.application.policy_service as svc

        mock_repo = MagicMock()
        mock_repo.find_policy_by_id.return_value = None

        with patch.object(svc, "get_policy_repo", return_value=mock_repo):
            with pytest.raises(PolicyNotFound):
                svc.get_policy(db=MagicMock(), policy_id=uuid.uuid4())
