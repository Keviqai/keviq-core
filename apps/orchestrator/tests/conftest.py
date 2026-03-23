"""Shared test configuration for orchestrator tests.

Ensures shared packages (resilience, internal-auth) are importable.
"""

import os
import sys

# Add resilience package to sys.path for tests
_resilience_path = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', 'packages', 'resilience')
)
if _resilience_path not in sys.path:
    sys.path.insert(0, _resilience_path)
