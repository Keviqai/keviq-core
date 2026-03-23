"""Resilience bridge — adds shared resilience package to sys.path.

Import this module early (before any infrastructure client imports)
so that `from resilience import ...` works.
"""

import os
import sys

_pkg_path = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', 'packages', 'resilience')
)
if _pkg_path not in sys.path:
    sys.path.insert(0, _pkg_path)
