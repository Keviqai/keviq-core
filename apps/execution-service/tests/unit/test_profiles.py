"""Unit tests for sandbox profiles."""

from __future__ import annotations

import pytest

from src.infrastructure.sandbox.profiles import SandboxProfile, get_profile


class TestSandboxProfiles:
    def test_container_profile(self):
        profile = get_profile("container")
        assert profile.name == "default-container"
        assert profile.image == "python:3.12-slim"
        assert profile.mem_limit == "512m"
        assert profile.network_mode == "none"

    def test_subprocess_profile(self):
        profile = get_profile("subprocess")
        assert profile.name == "default-subprocess"
        assert profile.image == "alpine:3.19"

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unknown sandbox type"):
            get_profile("vm")

    def test_profile_is_frozen(self):
        profile = get_profile("container")
        with pytest.raises(AttributeError):
            profile.image = "malicious:latest"

    def test_command_is_sleep(self):
        """Sandbox containers must run sleep infinity to stay alive."""
        profile = get_profile("container")
        assert profile.command == ["sleep", "infinity"]
