"""Tests for bridge HTTP routes."""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..')))

from fastapi.testclient import TestClient
from src.main import app
from src.cli_runner import CLIResult

client = TestClient(app, raise_server_exceptions=False)


def test_health():
    resp = client.get("/internal/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_liveness():
    resp = client.get("/healthz/live")
    assert resp.status_code == 200
    assert resp.json()["status"] == "live"


def test_status_endpoint():
    with patch("src.routes.check_status", return_value={
        "binary_available": True,
        "binary_path": "/usr/bin/claude",
        "likely_authenticated": True,
        "api_key_warning": None,
        "bridge_mode": "local_only",
    }):
        resp = client.get("/internal/v1/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["binary_available"] is True
        assert data["bridge_mode"] == "local_only"


def test_query_success():
    mock_result = CLIResult(
        output_text="Here is my analysis...",
        model_name="sonnet",
        cost_usd=0.005,
        duration_ms=2000,
        session_id="sess-123",
    )
    with patch("src.routes.invoke_cli", return_value=mock_result):
        resp = client.post("/internal/v1/query", json={
            "prompt": "Analyze competitors",
            "model": "sonnet",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["output_text"] == "Here is my analysis..."
        assert data["provider"] == "claude_code_cli"
        assert data["is_error"] is False


def test_query_error():
    mock_result = CLIResult(
        output_text="",
        model_name="sonnet",
        is_error=True,
        error_message="claude binary not found",
    )
    with patch("src.routes.invoke_cli", return_value=mock_result):
        resp = client.post("/internal/v1/query", json={
            "prompt": "hello",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_error"] is True
        assert "not found" in data["error_message"]


def test_query_validates_empty_prompt():
    resp = client.post("/internal/v1/query", json={
        "prompt": "",
    })
    assert resp.status_code == 422


def test_query_validates_max_turns():
    resp = client.post("/internal/v1/query", json={
        "prompt": "hello",
        "max_turns": 50,
    })
    assert resp.status_code == 422
