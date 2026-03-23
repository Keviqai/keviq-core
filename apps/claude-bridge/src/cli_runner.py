"""Subprocess wrapper for Claude Code CLI invocations.

LOCAL-ONLY: This module shells out to the `claude` binary that the host user
has already authenticated via `claude login`.  It never reads internal auth
files, tokens, or session data.

Supported CLI flags (official, documented):
  claude -p "<prompt>" --output-format json --model <model> --max-turns <n>
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Map friendly aliases → Claude Code model identifiers
MODEL_ALIASES: dict[str, str] = {
    "sonnet": "sonnet",
    "opus": "opus",
    "haiku": "haiku",
}

_DEFAULT_TIMEOUT_S = 120


@dataclass(frozen=True, slots=True)
class CLIResult:
    """Normalized result from a Claude Code CLI invocation."""

    output_text: str
    model_name: str
    is_error: bool = False
    error_message: str = ""
    cost_usd: float | None = None
    duration_ms: int = 0
    session_id: str = ""


def find_claude_binary() -> str | None:
    """Return the absolute path to the `claude` binary, or None."""
    return shutil.which("claude")


def check_status() -> dict:
    """Return a status dict describing bridge readiness.

    Keys: binary_available, likely_authenticated, api_key_warning,
          bridge_mode, binary_path.
    """
    binary = find_claude_binary()
    api_key_present = bool(os.environ.get("ANTHROPIC_API_KEY"))

    authenticated = False
    if binary:
        try:
            proc = subprocess.run(
                [binary, "--version"],
                capture_output=True, text=True, timeout=10,
            )
            authenticated = proc.returncode == 0
        except Exception:
            pass

    return {
        "binary_available": binary is not None,
        "binary_path": binary,
        "likely_authenticated": authenticated,
        "api_key_warning": (
            "ANTHROPIC_API_KEY is set — this overrides subscription auth "
            "in Claude Code and may cause unexpected billing"
            if api_key_present else None
        ),
        "bridge_mode": "local_only",
    }


def invoke_cli(
    prompt: str,
    *,
    model: str = "sonnet",
    max_turns: int = 1,
    timeout_s: int = _DEFAULT_TIMEOUT_S,
) -> CLIResult:
    """Run Claude Code CLI in print mode and return parsed result.

    Uses: claude -p "<prompt>" --output-format json --model <m> --max-turns <n>
    """
    binary = find_claude_binary()
    if not binary:
        return CLIResult(
            output_text="",
            model_name=model,
            is_error=True,
            error_message="claude binary not found in PATH",
        )

    resolved_model = MODEL_ALIASES.get(model, model)

    cmd = [
        binary, "-p", prompt,
        "--output-format", "json",
        "--model", resolved_model,
        "--max-turns", str(max_turns),
    ]

    logger.info("claude-bridge invoke: model=%s max_turns=%d", resolved_model, max_turns)

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout_s,
            env={**os.environ, "NO_COLOR": "1"},
        )
    except subprocess.TimeoutExpired:
        return CLIResult(
            output_text="",
            model_name=resolved_model,
            is_error=True,
            error_message=f"CLI timed out after {timeout_s}s",
        )
    except OSError as exc:
        return CLIResult(
            output_text="",
            model_name=resolved_model,
            is_error=True,
            error_message=f"Failed to execute claude: {exc}",
        )

    if proc.returncode != 0:
        stderr = proc.stderr.strip()[:500] if proc.stderr else ""
        return CLIResult(
            output_text="",
            model_name=resolved_model,
            is_error=True,
            error_message=f"CLI exited with code {proc.returncode}: {stderr}",
        )

    return _parse_json_output(proc.stdout, resolved_model)


def _parse_json_output(raw: str, model: str) -> CLIResult:
    """Parse Claude Code --output-format json output."""
    if not raw.strip():
        return CLIResult(
            output_text="",
            model_name=model,
            is_error=True,
            error_message="Empty output from CLI",
        )

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: treat entire stdout as plain text response
        return CLIResult(output_text=raw.strip(), model_name=model)

    # Claude Code JSON output has a "result" field with the text
    if isinstance(data, dict):
        text = data.get("result", data.get("text", data.get("content", "")))
        cost = data.get("cost_usd")
        session_id = data.get("session_id", "")
        duration = data.get("duration_ms", 0)
        model_used = data.get("model", model)
        return CLIResult(
            output_text=str(text),
            model_name=model_used,
            cost_usd=cost,
            duration_ms=duration,
            session_id=session_id,
        )

    # If it's a list (stream-json fragments), join text blocks
    if isinstance(data, list):
        texts = [
            item.get("result", item.get("content", ""))
            for item in data
            if isinstance(item, dict)
        ]
        return CLIResult(output_text="\n".join(str(t) for t in texts if t), model_name=model)

    return CLIResult(output_text=str(data), model_name=model)
