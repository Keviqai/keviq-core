"""Tests for template query functions and serialization.

Covers: list/get queries, task_template_to_dict, agent_template_to_dict.
"""

from __future__ import annotations

import pytest
from uuid import uuid4

from src.application.template_queries import (
    agent_template_to_dict,
    get_agent_template,
    get_task_template,
    list_system_agent_templates,
    list_system_task_templates,
    task_template_to_dict,
)
from src.domain.agent_template import AgentTemplate
from src.domain.errors import DomainError
from src.domain.task_template import TaskTemplate, TemplateScope

from .fake_uow import FakeUnitOfWork


# ── Factories ────────────────────────────────────────────────


def _make_task_template(**overrides) -> TaskTemplate:
    defaults = dict(name="Research Brief", category="research")
    defaults.update(overrides)
    return TaskTemplate(**defaults)


def _make_agent_template(**overrides) -> AgentTemplate:
    defaults = dict(name="Research Analyst", default_risk_profile="low")
    defaults.update(overrides)
    return AgentTemplate(**defaults)


def _seed_system_templates(uow: FakeUnitOfWork) -> None:
    """Seed 3 task + 3 agent templates into fake UoW."""
    for name, cat in [
        ("Research Brief", "research"),
        ("Data Analysis", "analysis"),
        ("Ops Prep", "operation"),
    ]:
        t = _make_task_template(name=name, category=cat)
        uow.task_templates.save(t)

    for name, risk in [
        ("Research Analyst", "low"),
        ("Ops Assistant", "medium"),
        ("General Agent", "medium"),
    ]:
        a = _make_agent_template(name=name, default_risk_profile=risk)
        uow.agent_templates.save(a)


# ── List Task Templates ──────────────────────────────────────


class TestListTaskTemplates:
    def test_list_system_returns_all(self):
        uow = FakeUnitOfWork()
        _seed_system_templates(uow)
        result = list_system_task_templates(uow)
        assert len(result) == 3

    def test_list_system_filter_by_category(self):
        uow = FakeUnitOfWork()
        _seed_system_templates(uow)
        result = list_system_task_templates(uow, category="research")
        assert len(result) == 1
        assert result[0].category == "research"

    def test_list_empty_returns_empty(self):
        uow = FakeUnitOfWork()
        result = list_system_task_templates(uow)
        assert result == []


# ── Get Task Template ─────────────────────────────────────────


class TestGetTaskTemplate:
    def test_get_existing(self):
        uow = FakeUnitOfWork()
        t = _make_task_template()
        uow.task_templates.save(t)
        result = get_task_template(t.id, uow)
        assert result.id == t.id
        assert result.name == "Research Brief"

    def test_get_nonexistent_raises(self):
        uow = FakeUnitOfWork()
        with pytest.raises(DomainError, match="not found"):
            get_task_template(uuid4(), uow)


# ── List Agent Templates ──────────────────────────────────────


class TestListAgentTemplates:
    def test_list_system_returns_all(self):
        uow = FakeUnitOfWork()
        _seed_system_templates(uow)
        result = list_system_agent_templates(uow)
        assert len(result) == 3

    def test_list_empty_returns_empty(self):
        uow = FakeUnitOfWork()
        result = list_system_agent_templates(uow)
        assert result == []


# ── Get Agent Template ────────────────────────────────────────


class TestGetAgentTemplate:
    def test_get_existing(self):
        uow = FakeUnitOfWork()
        a = _make_agent_template(
            capabilities_manifest=["web_search"],
        )
        uow.agent_templates.save(a)
        result = get_agent_template(a.id, uow)
        assert result.id == a.id
        assert result.capabilities_manifest == ["web_search"]

    def test_get_nonexistent_raises(self):
        uow = FakeUnitOfWork()
        with pytest.raises(DomainError, match="not found"):
            get_agent_template(uuid4(), uow)


# ── Serialization ─────────────────────────────────────────────


class TestTemplateSerialization:
    def test_task_template_to_dict_all_fields(self):
        t = _make_task_template(
            description="A research template",
            prefilled_fields={"goal": "Research topic"},
            expected_output_type="report",
        )
        d = task_template_to_dict(t)
        assert d["template_id"] == str(t.id)
        assert d["name"] == "Research Brief"
        assert d["category"] == "research"
        assert d["prefilled_fields"] == {"goal": "Research topic"}
        assert d["expected_output_type"] == "report"
        assert d["scope"] == "system"
        assert "workspace_id" not in d
        assert "created_at" in d

    def test_agent_template_to_dict_all_fields(self):
        a = _make_agent_template(
            description="A research agent",
            best_for="Literature review",
            not_for="Code execution",
            capabilities_manifest=["web_search", "summarization"],
            default_output_types=["report"],
        )
        d = agent_template_to_dict(a)
        assert d["template_id"] == str(a.id)
        assert d["name"] == "Research Analyst"
        assert d["best_for"] == "Literature review"
        assert d["not_for"] == "Code execution"
        assert d["capabilities_manifest"] == ["web_search", "summarization"]
        assert d["default_risk_profile"] == "low"
        assert "workspace_id" not in d

    def test_workspace_template_includes_workspace_id(self):
        wid = uuid4()
        t = _make_task_template(
            scope=TemplateScope.WORKSPACE, workspace_id=wid,
        )
        d = task_template_to_dict(t)
        assert d["workspace_id"] == str(wid)
        assert d["scope"] == "workspace"
