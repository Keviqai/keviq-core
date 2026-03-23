"""Application-layer port interfaces for api-gateway.

Infrastructure implements these. No httpx, no jwt here.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from fastapi import Request, Response


class JwtVerifier(ABC):
    @abstractmethod
    def verify_token(self, token: str) -> dict: ...


class PolicyClient(ABC):
    @abstractmethod
    async def check_permission(
        self,
        *,
        actor_id: str,
        workspace_id: str,
        permission: str,
        role: str,
        resource_id: str | None = None,
    ) -> dict: ...


class WorkspaceClient(ABC):
    @abstractmethod
    async def get_member(self, workspace_id: str, user_id: str) -> dict | None: ...


class ServiceProxy(ABC):
    @abstractmethod
    async def proxy_request(
        self,
        service: str,
        path: str,
        request: Request,
        extra_headers: dict | None = None,
        extra_params: dict | None = None,
    ) -> Response: ...
