"""Keviq Core config — shared configuration validation and deployment metadata."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


def require_env(name: str, *, description: str = "") -> str:
    """Return the value of a required environment variable.

    Raises RuntimeError with a clear message if the variable is missing.
    """
    value = os.environ.get(name)
    if not value:
        hint = f" ({description})" if description else ""
        raise RuntimeError(
            f"{name} environment variable is required{hint}"
        )
    return value


def optional_env(name: str, default: str = "") -> str:
    """Return the value of an optional environment variable with a default."""
    return os.getenv(name, default)


def optional_env_int(name: str, default: int = 0) -> int:
    """Return an optional env var parsed as int."""
    raw = os.getenv(name, str(default))
    try:
        return int(raw)
    except ValueError:
        raise RuntimeError(f"{name} must be an integer, got {raw!r}") from None


def optional_env_float(name: str, default: float = 0.0) -> float:
    """Return an optional env var parsed as float."""
    raw = os.getenv(name, str(default))
    try:
        return float(raw)
    except ValueError:
        raise RuntimeError(f"{name} must be a number, got {raw!r}") from None


# ── Deployment metadata ─────────────────────────────────────────

VALID_PROFILES = ("local", "hardened", "cloud")
VALID_EXECUTION_BACKENDS = ("docker-local", "noop", "k8s-job")
VALID_STORAGE_BACKENDS = ("local", "s3")


@dataclass(frozen=True)
class DeploymentInfo:
    """Runtime deployment metadata — exposed via /healthz."""
    service: str
    app_env: str
    deployment_profile: str
    execution_backend: str = "noop"
    storage_backend: str = "local"
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result = {
            "service": self.service,
            "app_env": self.app_env,
            "deployment_profile": self.deployment_profile,
            "execution_backend": self.execution_backend,
            "storage_backend": self.storage_backend,
        }
        if self.extra:
            result["extra"] = self.extra
        return result


def get_deployment_info(service: str) -> DeploymentInfo:
    """Build DeploymentInfo from environment variables."""
    return DeploymentInfo(
        service=service,
        app_env=optional_env("APP_ENV", "development"),
        deployment_profile=optional_env("DEPLOYMENT_PROFILE", "local"),
        execution_backend=optional_env("EXECUTION_BACKEND", "noop"),
        storage_backend=optional_env("ARTIFACT_STORAGE_BACKEND", "local"),
    )


# ── Workspace isolation naming conventions ───────────────────────

def sandbox_container_name(sandbox_id: str) -> str:
    """Deterministic container name for a sandbox. Includes sandbox UUID for uniqueness."""
    return f"mona-sandbox-{sandbox_id}"


def artifact_storage_prefix(workspace_id: str, run_id: str) -> str:
    """Hierarchical storage prefix for artifacts scoped to a workspace and run.

    Used for both local filesystem and remote object storage (S3).
    Pattern: workspaces/<workspace_id>/runs/<run_id>/artifacts/
    """
    return f"workspaces/{workspace_id}/runs/{run_id}/artifacts"


def artifact_storage_key(workspace_id: str, run_id: str, artifact_id: str) -> str:
    """Full storage key for a specific artifact."""
    return f"workspaces/{workspace_id}/runs/{run_id}/artifacts/{artifact_id}"


def workspace_temp_dir(workspace_id: str, run_id: str) -> str:
    """Scoped temp directory path for workspace run execution."""
    return f"tmp/workspaces/{workspace_id}/runs/{run_id}"


def relay_consumer_id(service: str, instance_id: str = "") -> str:
    """Deterministic relay consumer identity for event bus.

    Ensures no collision between service instances.
    """
    suffix = f"-{instance_id}" if instance_id else ""
    return f"relay-{service}{suffix}"
