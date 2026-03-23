"""Unit tests for tool registry."""

from __future__ import annotations

import pytest

from src.application.tool_registry import (
    build_command,
    get_tool,
    list_tools,
)


class TestGetTool:
    def test_valid_tool_resolves(self):
        tool = get_tool("python.run_script")
        assert tool.name == "python.run_script"
        assert tool.command_template == ("python", "-c")

    def test_shell_exec_resolves(self):
        tool = get_tool("shell.exec")
        assert tool.name == "shell.exec"
        assert tool.command_template == ("sh", "-c")

    def test_unknown_tool_raises(self):
        with pytest.raises(ValueError, match="Unknown tool"):
            get_tool("nonexistent.tool")

    def test_error_message_lists_registered_tools(self):
        with pytest.raises(ValueError, match="python.run_script"):
            get_tool("bad_tool")


class TestBuildCommand:
    def test_python_run_script(self):
        cmd = build_command("python.run_script", {"code": "print('hello')"})
        assert cmd == ["python", "-c", "print('hello')"]

    def test_shell_exec(self):
        cmd = build_command("shell.exec", {"code": "echo test"})
        assert cmd == ["sh", "-c", "echo test"]

    def test_empty_code_allowed(self):
        cmd = build_command("shell.exec", {"code": ""})
        assert cmd == ["sh", "-c", ""]

    def test_missing_code_defaults_empty(self):
        cmd = build_command("shell.exec", {})
        assert cmd == ["sh", "-c", ""]

    def test_non_string_code_raises(self):
        with pytest.raises(ValueError, match="must be a string"):
            build_command("shell.exec", {"code": 123})

    def test_oversized_code_raises(self):
        big_code = "x" * 1_100_000
        with pytest.raises(ValueError, match="exceeds maximum size"):
            build_command("shell.exec", {"code": big_code})

    def test_code_at_limit_is_accepted(self):
        code = "x" * 1_000_000
        cmd = build_command("shell.exec", {"code": code})
        assert len(cmd[2]) == 1_000_000

    def test_returns_list_not_shell_string(self):
        cmd = build_command("python.run_script", {"code": "x=1"})
        assert isinstance(cmd, list)
        assert all(isinstance(part, str) for part in cmd)


class TestListTools:
    def test_list_contains_registered_tools(self):
        tools = list_tools()
        assert "python.run_script" in tools
        assert "shell.exec" in tools

    def test_list_is_sorted(self):
        tools = list_tools()
        assert tools == sorted(tools)


class TestToolDefinitionProperties:
    def test_python_tool_container_only(self):
        tool = get_tool("python.run_script")
        assert "container" in tool.allowed_sandbox_types
        assert "subprocess" not in tool.allowed_sandbox_types

    def test_shell_tool_both_types(self):
        tool = get_tool("shell.exec")
        assert "container" in tool.allowed_sandbox_types
        assert "subprocess" in tool.allowed_sandbox_types

    def test_tool_definition_is_frozen(self):
        tool = get_tool("shell.exec")
        with pytest.raises(AttributeError):
            tool.name = "hacked"
