"""Hardcoded tool registry — maps tool names to safe command templates.

Tools are the only commands that can be executed inside sandboxes.
No raw shell strings, no user-supplied commands (G21-1).
Command is always built as an argv list, never via shell=True.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """A registered tool with its command template and argument schema."""

    name: str
    command_template: tuple[str, ...]
    description: str = ""
    allowed_sandbox_types: frozenset[str] = field(
        default_factory=lambda: frozenset({"container", "subprocess"}),
    )


# ── Registry ────────────────────────────────────────────────────
# The ONLY commands that can run in sandboxes.  Adding a new tool
# requires a code change + review — never runtime or user input.

_TOOL_REGISTRY: dict[str, ToolDefinition] = {
    "python.run_script": ToolDefinition(
        name="python.run_script",
        command_template=("python", "-c"),
        description="Execute a Python script from string input.",
        allowed_sandbox_types=frozenset({"container"}),
    ),
    "shell.exec": ToolDefinition(
        name="shell.exec",
        command_template=("sh", "-c"),
        description="Execute a shell command inside sandbox.",
        allowed_sandbox_types=frozenset({"container", "subprocess"}),
    ),
}


def get_tool(tool_name: str) -> ToolDefinition:
    """Get a registered tool by name. Raises ValueError if not found."""
    tool = _TOOL_REGISTRY.get(tool_name)
    if tool is None:
        raise ValueError(
            f"Unknown tool: {tool_name!r}. "
            f"Registered tools: {sorted(_TOOL_REGISTRY.keys())}"
        )
    return tool


_MAX_INPUT_SIZE = 1_000_000  # 1 MB — reject oversized tool input


def build_command(tool_name: str, tool_input: dict[str, Any]) -> list[str]:
    """Build a safe argv list for the given tool and input.

    Returns a list of strings suitable for Docker exec.
    Never uses shell=True or string concatenation.
    """
    tool = get_tool(tool_name)

    code = tool_input.get("code", "")
    if not isinstance(code, str):
        raise ValueError("tool_input['code'] must be a string")
    if len(code) > _MAX_INPUT_SIZE:
        raise ValueError(
            f"tool_input['code'] exceeds maximum size "
            f"({len(code)} > {_MAX_INPUT_SIZE} bytes)"
        )

    return [*tool.command_template, code]


def list_tools() -> list[str]:
    """List all registered tool names."""
    return sorted(_TOOL_REGISTRY.keys())
