"""Sandbox profiles — hardcoded, internal-only sandbox configurations.

Profiles define which Docker image, resource limits, and network settings
to use for each sandbox type. Request input must NOT choose arbitrary images
or mount paths (G20-3).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SandboxProfile:
    """Internal sandbox profile. Not user-controlled."""

    name: str
    image: str
    command: list[str]
    mem_limit: str = "512m"
    cpu_quota: int = 100_000  # microseconds (1 CPU)
    network_mode: str = "none"  # no network by default


# ── Built-in profiles ────────────────────────────────────────

_PROFILES: dict[str, SandboxProfile] = {
    "container": SandboxProfile(
        name="default-container",
        image="python:3.12-slim",
        command=["sleep", "infinity"],
        mem_limit="512m",
        cpu_quota=100_000,
        network_mode="none",
    ),
    "subprocess": SandboxProfile(
        name="default-subprocess",
        image="alpine:3.19",
        command=["sleep", "infinity"],
        mem_limit="256m",
        cpu_quota=50_000,
        network_mode="none",
    ),
}


def get_profile(sandbox_type: str) -> SandboxProfile:
    """Get the sandbox profile for a given type.

    Raises ValueError if the sandbox type is not recognized.
    """
    profile = _PROFILES.get(sandbox_type)
    if profile is None:
        raise ValueError(
            f"Unknown sandbox type {sandbox_type!r}. "
            f"Valid types: {list(_PROFILES.keys())}",
        )
    return profile
