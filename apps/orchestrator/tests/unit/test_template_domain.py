"""Tests for TaskTemplate and AgentTemplate domain models.

Covers: init validation, scope rules, field storage.
"""

from __future__ import annotations

import pytest
from uuid import uuid4

from src.domain.errors import DomainValidationError
from src.domain.task_template import TaskTemplate, TemplateScope, VALID_CATEGORIES
from src.domain.agent_template import AgentTemplate


# ── TaskTemplate domain tests ─────────────────────────────────


class TestTaskTemplateInit:
    def test_creates_with_required_fields(self):
        t = TaskTemplate(name="Research Brief", category="research")
        assert t.name == "Research Brief"
        assert t.category == "research"
        assert t.scope == TemplateScope.SYSTEM
        assert t.workspace_id is None
        assert t.prefilled_fields == {}

    def test_rejects_blank_name(self):
        with pytest.raises(DomainValidationError, match="name must not be blank"):
            TaskTemplate(name="   ", category="research")

    def test_rejects_empty_name(self):
        with pytest.raises(DomainValidationError, match="name must not be blank"):
            TaskTemplate(name="", category="research")

    def test_rejects_invalid_category(self):
        with pytest.raises(DomainValidationError, match="invalid category"):
            TaskTemplate(name="Test", category="coding")

    def test_accepts_all_valid_categories(self):
        for cat in VALID_CATEGORIES:
            t = TaskTemplate(name="Test", category=cat)
            assert t.category == cat

    def test_rejects_invalid_scope(self):
        with pytest.raises(ValueError):
            TaskTemplate(name="Test", category="research", scope="global")

    def test_system_scope_rejects_workspace_id(self):
        with pytest.raises(
            DomainValidationError, match="must not have workspace_id",
        ):
            TaskTemplate(
                name="Test", category="research",
                scope=TemplateScope.SYSTEM, workspace_id=uuid4(),
            )

    def test_workspace_scope_requires_workspace_id(self):
        with pytest.raises(
            DomainValidationError, match="requires workspace_id",
        ):
            TaskTemplate(
                name="Test", category="research",
                scope=TemplateScope.WORKSPACE,
            )

    def test_workspace_scope_with_workspace_id(self):
        wid = uuid4()
        t = TaskTemplate(
            name="Custom", category="custom",
            scope=TemplateScope.WORKSPACE, workspace_id=wid,
        )
        assert t.workspace_id == wid
        assert t.scope == TemplateScope.WORKSPACE

    def test_stores_prefilled_fields(self):
        fields = {"goal": "Research AI", "desired_output": "Report"}
        t = TaskTemplate(
            name="Test", category="research",
            prefilled_fields=fields,
        )
        assert t.prefilled_fields == fields

    def test_stores_expected_output_type(self):
        t = TaskTemplate(
            name="Test", category="research",
            expected_output_type="report",
        )
        assert t.expected_output_type == "report"

    def test_generates_id_and_timestamps(self):
        t = TaskTemplate(name="Test", category="research")
        assert t.id is not None
        assert t.created_at is not None
        assert t.updated_at is not None


# ── AgentTemplate domain tests ────────────────────────────────


class TestAgentTemplateInit:
    def test_creates_with_required_fields(self):
        a = AgentTemplate(name="Research Analyst")
        assert a.name == "Research Analyst"
        assert a.default_risk_profile == "medium"
        assert a.capabilities_manifest == []
        assert a.default_output_types == []
        assert a.scope == TemplateScope.SYSTEM

    def test_rejects_blank_name(self):
        with pytest.raises(DomainValidationError, match="name must not be blank"):
            AgentTemplate(name="  ")

    def test_rejects_invalid_risk_profile(self):
        with pytest.raises(
            DomainValidationError, match="invalid default_risk_profile",
        ):
            AgentTemplate(name="Test", default_risk_profile="critical")

    def test_accepts_valid_risk_profiles(self):
        for level in ("low", "medium", "high"):
            a = AgentTemplate(name="Test", default_risk_profile=level)
            assert a.default_risk_profile == level

    def test_stores_capabilities_manifest(self):
        caps = ["web_search", "document_analysis"]
        a = AgentTemplate(name="Test", capabilities_manifest=caps)
        assert a.capabilities_manifest == caps

    def test_stores_best_for_not_for(self):
        a = AgentTemplate(
            name="Test",
            best_for="Research tasks",
            not_for="Code execution",
        )
        assert a.best_for == "Research tasks"
        assert a.not_for == "Code execution"

    def test_system_scope_rejects_workspace_id(self):
        with pytest.raises(
            DomainValidationError, match="must not have workspace_id",
        ):
            AgentTemplate(name="Test", workspace_id=uuid4())

    def test_workspace_scope_with_workspace_id(self):
        wid = uuid4()
        a = AgentTemplate(
            name="Custom", scope=TemplateScope.WORKSPACE,
            workspace_id=wid,
        )
        assert a.workspace_id == wid

    def test_stores_default_output_types(self):
        types = ["report", "code"]
        a = AgentTemplate(name="Test", default_output_types=types)
        assert a.default_output_types == types

    def test_generates_id_and_timestamps(self):
        a = AgentTemplate(name="Test")
        assert a.id is not None
        assert a.created_at is not None
