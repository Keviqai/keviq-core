"""Tool approval policy — decides whether a tool call requires human approval.

Baseline policy for O5-S1. Intentionally simple — not a policy engine.
Evaluates tool name + risk indicators to produce one of three decisions:
  - ALLOW: execute immediately (O4 behavior)
  - WARN: log warning, execute (O4 guardrail behavior)
  - GATE: pause execution, require human approval before dispatch

Policy mode is configurable via TOOL_APPROVAL_MODE env var:
  - "none": all tools ALLOW (backward compat with O4)
  - "warn": risky tools WARN, others ALLOW
  - "gate": risky tools GATE, others ALLOW (default)
"""

from __future__ import annotations

import enum
import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class ApprovalDecision(str, enum.Enum):
    """Policy decision for a single tool call."""
    ALLOW = "allow"
    WARN = "warn"
    GATE = "gate"


class ApprovalMode(str, enum.Enum):
    """System-wide tool approval mode."""
    NONE = "none"
    WARN = "warn"
    GATE = "gate"


@dataclass(frozen=True, slots=True)
class PolicyResult:
    """Result of policy evaluation for a tool call."""
    decision: ApprovalDecision
    reason: str


# Tools that always require gating when mode=gate
_GATED_TOOLS: frozenset[str] = frozenset({
    "shell.exec",
    "python.run_script",
})

# Risky patterns within shell.exec that escalate to gate/warn
_RISKY_SHELL_PATTERNS: tuple[str, ...] = (
    "curl ", "wget ", "nc ", "chmod +x", "rm -rf /", "base64 -d",
    "eval ", "exec ", "> /dev/", "| bash", "| sh",
)


def get_approval_mode() -> ApprovalMode:
    """Read TOOL_APPROVAL_MODE from env. Default: gate."""
    raw = os.getenv("TOOL_APPROVAL_MODE", "gate").lower().strip()
    try:
        return ApprovalMode(raw)
    except ValueError:
        logger.warning(
            "Invalid TOOL_APPROVAL_MODE '%s' — defaulting to 'gate'", raw,
        )
        return ApprovalMode.GATE


def evaluate_tool_approval(
    tool_name: str,
    tool_input: dict,
    *,
    mode: ApprovalMode | None = None,
) -> PolicyResult:
    """Evaluate whether a tool call requires human approval.

    Args:
        tool_name: Name of the tool (e.g. "shell.exec", "python.run_script").
        tool_input: Parsed tool input arguments.
        mode: Override approval mode. If None, reads from env var.

    Returns:
        PolicyResult with decision and reason.
    """
    if mode is None:
        mode = get_approval_mode()

    # Mode=none → always allow (backward compat with O4)
    if mode == ApprovalMode.NONE:
        return PolicyResult(
            decision=ApprovalDecision.ALLOW,
            reason="approval mode is 'none'",
        )

    # Check if tool is in the gated set
    if tool_name in _GATED_TOOLS:
        risk_reason = _assess_tool_risk(tool_name, tool_input)

        if mode == ApprovalMode.GATE:
            return PolicyResult(
                decision=ApprovalDecision.GATE,
                reason=risk_reason or f"{tool_name} requires approval in gate mode",
            )
        else:
            # mode == WARN
            return PolicyResult(
                decision=ApprovalDecision.WARN,
                reason=risk_reason or f"{tool_name} flagged in warn mode",
            )

    # Non-gated tools → always allow
    return PolicyResult(
        decision=ApprovalDecision.ALLOW,
        reason=f"{tool_name} not in gated tool set",
    )


def _assess_tool_risk(tool_name: str, tool_input: dict) -> str | None:
    """Assess specific risk reason for a gated tool. Returns reason or None."""
    if tool_name == "shell.exec":
        code = str(
            tool_input.get("code", "")
            or tool_input.get("command", "")
            or ""
        )
        for pattern in _RISKY_SHELL_PATTERNS:
            if pattern in code.lower():
                return f"shell.exec contains risky pattern: '{pattern}'"
        return "shell.exec: all shell commands gated"

    if tool_name == "python.run_script":
        return "python.run_script: script execution gated"

    return None
