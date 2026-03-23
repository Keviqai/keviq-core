"""Tests for cli_runner module — subprocess wrapper + output parsing."""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest

import sys
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.cli_runner import (
    CLIResult,
    _parse_json_output,
    check_status,
    find_claude_binary,
    invoke_cli,
)


# ── find_claude_binary ────────────────────────────────


def test_find_binary_returns_path_when_available():
    with patch("src.cli_runner.shutil.which", return_value="/usr/bin/claude"):
        assert find_claude_binary() == "/usr/bin/claude"


def test_find_binary_returns_none_when_missing():
    with patch("src.cli_runner.shutil.which", return_value=None):
        assert find_claude_binary() is None


# ── check_status ──────────────────────────────────────


def test_status_reports_binary_unavailable():
    with patch("src.cli_runner.find_claude_binary", return_value=None):
        s = check_status()
        assert s["binary_available"] is False
        assert s["likely_authenticated"] is False
        assert s["bridge_mode"] == "local_only"


def test_status_reports_binary_available():
    with patch("src.cli_runner.find_claude_binary", return_value="/usr/bin/claude"):
        mock_proc = MagicMock(returncode=0)
        with patch("src.cli_runner.subprocess.run", return_value=mock_proc):
            s = check_status()
            assert s["binary_available"] is True
            assert s["likely_authenticated"] is True


def test_status_warns_about_api_key():
    with patch("src.cli_runner.find_claude_binary", return_value=None):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            s = check_status()
            assert s["api_key_warning"] is not None
            assert "ANTHROPIC_API_KEY" in s["api_key_warning"]


def test_status_no_api_key_warning_when_unset():
    with patch("src.cli_runner.find_claude_binary", return_value=None):
        with patch.dict(os.environ, {}, clear=True):
            # Ensure ANTHROPIC_API_KEY is not set
            os.environ.pop("ANTHROPIC_API_KEY", None)
            s = check_status()
            assert s["api_key_warning"] is None


# ── invoke_cli ────────────────────────────────────────


def test_invoke_returns_error_when_binary_missing():
    with patch("src.cli_runner.find_claude_binary", return_value=None):
        result = invoke_cli("hello")
        assert result.is_error is True
        assert "not found" in result.error_message


def test_invoke_handles_timeout():
    import subprocess

    with patch("src.cli_runner.find_claude_binary", return_value="/usr/bin/claude"):
        with patch(
            "src.cli_runner.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=10),
        ):
            result = invoke_cli("hello", timeout_s=10)
            assert result.is_error is True
            assert "timed out" in result.error_message


def test_invoke_handles_nonzero_exit():
    with patch("src.cli_runner.find_claude_binary", return_value="/usr/bin/claude"):
        mock_proc = MagicMock(returncode=1, stderr="auth error", stdout="")
        with patch("src.cli_runner.subprocess.run", return_value=mock_proc):
            result = invoke_cli("hello")
            assert result.is_error is True
            assert "code 1" in result.error_message


def test_invoke_success_json():
    json_output = json.dumps({
        "result": "Hello! How can I help?",
        "model": "claude-sonnet-4-20250514",
        "cost_usd": 0.003,
        "session_id": "abc123",
        "duration_ms": 1500,
    })
    with patch("src.cli_runner.find_claude_binary", return_value="/usr/bin/claude"):
        mock_proc = MagicMock(returncode=0, stdout=json_output, stderr="")
        with patch("src.cli_runner.subprocess.run", return_value=mock_proc):
            result = invoke_cli("hello")
            assert result.is_error is False
            assert result.output_text == "Hello! How can I help?"
            assert result.cost_usd == 0.003
            assert result.session_id == "abc123"


def test_invoke_success_plain_text_fallback():
    with patch("src.cli_runner.find_claude_binary", return_value="/usr/bin/claude"):
        mock_proc = MagicMock(returncode=0, stdout="Plain text reply", stderr="")
        with patch("src.cli_runner.subprocess.run", return_value=mock_proc):
            result = invoke_cli("hello")
            assert result.is_error is False
            assert result.output_text == "Plain text reply"


# ── _parse_json_output ────────────────────────────────


def test_parse_empty_output():
    result = _parse_json_output("", "sonnet")
    assert result.is_error is True
    assert "Empty" in result.error_message


def test_parse_valid_json_dict():
    data = json.dumps({"result": "answer", "model": "opus", "cost_usd": 0.01})
    result = _parse_json_output(data, "sonnet")
    assert result.output_text == "answer"
    assert result.model_name == "opus"
    assert result.cost_usd == 0.01


def test_parse_json_list():
    data = json.dumps([{"result": "part1"}, {"result": "part2"}])
    result = _parse_json_output(data, "sonnet")
    assert "part1" in result.output_text
    assert "part2" in result.output_text


def test_parse_invalid_json_returns_raw():
    result = _parse_json_output("Not JSON at all", "sonnet")
    assert result.output_text == "Not JSON at all"
    assert result.is_error is False


def test_invoke_passes_correct_cmd():
    with patch("src.cli_runner.find_claude_binary", return_value="/usr/bin/claude"):
        mock_proc = MagicMock(returncode=0, stdout='{"result":"ok"}', stderr="")
        with patch("src.cli_runner.subprocess.run", return_value=mock_proc) as mock_run:
            invoke_cli("test prompt", model="opus", max_turns=3)
            args = mock_run.call_args
            cmd = args[0][0]
            assert cmd[0] == "/usr/bin/claude"
            assert "-p" in cmd
            assert "test prompt" in cmd
            assert "--output-format" in cmd
            assert "json" in cmd
            assert "--model" in cmd
            assert "opus" in cmd
            assert "--max-turns" in cmd
            assert "3" in cmd
