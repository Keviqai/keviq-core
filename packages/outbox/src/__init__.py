"""Keviq Core outbox package — shared envelope builder for event outbox pattern."""

from .envelope import build_envelope

__all__ = ["build_envelope"]
