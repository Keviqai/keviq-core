"""Internal auth bridge — re-exports from shared internal-auth package.

Allows routes to do: from src.internal_auth import require_service
"""

import sys
import os

# Add shared package to path
sys.path.insert(0, os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', 'packages', 'internal-auth')
))

from internal_auth.fastapi_dep import (  # noqa: E402
    configure_verifier,
    require_internal_auth,
    require_service,
)
from internal_auth.bootstrap import bootstrap_internal_auth, get_auth_client  # noqa: E402
from internal_auth.token import InternalTokenVerifier  # noqa: E402
from internal_auth.config import load_internal_auth_config  # noqa: E402
from internal_auth.client import InternalAuthClient  # noqa: E402

__all__ = [
    "configure_verifier",
    "require_internal_auth",
    "require_service",
    "bootstrap_internal_auth",
    "get_auth_client",
    "InternalTokenVerifier",
    "load_internal_auth_config",
    "InternalAuthClient",
]
