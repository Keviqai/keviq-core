"""FastAPI dependencies for internal service auth.

Usage in routes:

    from internal_auth import require_internal_auth, require_service

    @router.post("/internal/v1/something")
    async def handle(claims=Depends(require_internal_auth)):
        ...

    @router.post("/internal/v1/invocations/execute")
    async def handle(claims=Depends(require_service("orchestrator"))):
        ...
"""

from __future__ import annotations

import logging
from typing import Callable

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from internal_auth.token import (
    InternalTokenClaims,
    InternalTokenVerifier,
    InternalAuthError,
    ExpiredTokenError,
    InvalidTokenError,
    WrongAudienceError,
    UnauthorizedServiceError,
)

logger = logging.getLogger(__name__)

# Module-level verifier — set during service bootstrap
_verifier: InternalTokenVerifier | None = None

_bearer_scheme = HTTPBearer(auto_error=False)


def configure_verifier(verifier: InternalTokenVerifier) -> None:
    """Set the module-level verifier. Called once at service startup."""
    global _verifier
    _verifier = verifier


def _get_verifier() -> InternalTokenVerifier:
    if _verifier is None:
        raise RuntimeError(
            "Internal auth verifier not configured. "
            "Call configure_verifier() or bootstrap_internal_auth() during startup."
        )
    return _verifier


async def require_internal_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> InternalTokenClaims:
    """FastAPI dependency: require a valid internal service token."""
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Internal service authentication required",
        )

    verifier = _get_verifier()
    try:
        return verifier.verify(credentials.credentials)
    except ExpiredTokenError:
        raise HTTPException(status_code=401, detail="Internal token expired")
    except WrongAudienceError as exc:
        logger.warning("Internal auth: wrong audience — %s", exc)
        raise HTTPException(status_code=403, detail="Wrong service audience")
    except InvalidTokenError as exc:
        logger.warning("Internal auth: invalid token — %s", exc)
        raise HTTPException(status_code=401, detail="Invalid internal token")
    except InternalAuthError as exc:
        logger.warning("Internal auth: error — %s", exc)
        raise HTTPException(status_code=401, detail="Internal authentication failed")


def require_service(
    *allowed_services: str,
) -> Callable:
    """Factory: return a dependency that requires specific caller services."""
    allowed = list(allowed_services)

    async def _dependency(
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    ) -> InternalTokenClaims:
        if credentials is None:
            raise HTTPException(
                status_code=401,
                detail="Internal service authentication required",
            )

        verifier = _get_verifier()
        try:
            return verifier.verify(
                credentials.credentials,
                allowed_services=allowed,
            )
        except ExpiredTokenError:
            raise HTTPException(status_code=401, detail="Internal token expired")
        except WrongAudienceError as exc:
            logger.warning("Internal auth: wrong audience — %s", exc)
            raise HTTPException(status_code=403, detail="Wrong service audience")
        except UnauthorizedServiceError as exc:
            logger.warning("Internal auth: unauthorized service — %s", exc)
            raise HTTPException(
                status_code=403,
                detail="Service not authorized for this endpoint",
            )
        except InvalidTokenError as exc:
            logger.warning("Internal auth: invalid token — %s", exc)
            raise HTTPException(status_code=401, detail="Invalid internal token")
        except InternalAuthError as exc:
            logger.warning("Internal auth: error — %s", exc)
            raise HTTPException(status_code=401, detail="Internal authentication failed")

    return _dependency
