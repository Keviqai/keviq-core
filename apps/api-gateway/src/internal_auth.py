"""Internal auth bridge — re-exports from shared internal-auth package.

api-gateway uses this to sign outgoing requests to downstream services.
"""

import sys
import os

# Add shared package to path
sys.path.insert(0, os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', 'packages', 'internal-auth')
))

from internal_auth.bootstrap import bootstrap_internal_auth, get_auth_client  # noqa: E402
from internal_auth.client import InternalAuthClient  # noqa: E402

__all__ = [
    "bootstrap_internal_auth",
    "get_auth_client",
    "InternalAuthClient",
]
