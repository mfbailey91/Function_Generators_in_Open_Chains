"""Version 3 OMPL adapter package (Sprint V3.5).

OMPL is an optional external backend. Importing this package does not require
OMPL to be installed; planner classes raise a clear ``ImportError`` or tests
skip via :func:`is_ompl_available` when bindings are missing.

Install OMPL Python bindings separately. Preferred paths:

- ``pip install ompl`` when a wheel exists for your platform/Python (e.g. CPython
  3.11 on macOS arm64), or
- ``conda install -c conda-forge ompl`` for the C++ library plus a matching
  ``pip install ompl`` wheel into that environment.

There is no reliable single pip wheel for every platform; see optional extra
``ompl`` in ``pyproject.toml`` (documentation marker only).
"""

from __future__ import annotations

from inequality_mechanisms.adapters.ompl._availability import (
    is_ompl_available,
    ompl_version_string,
    require_ompl,
)

__all__ = [
    "OmplPRMPlanner",
    "OmplRRTConnectPlanner",
    "is_ompl_available",
    "ompl_version_string",
    "require_ompl",
]


def __getattr__(name: str):
    """Lazily import planner classes so bare package import stays OMPL-free."""
    if name == "OmplPRMPlanner":
        from inequality_mechanisms.adapters.ompl.prm import OmplPRMPlanner

        return OmplPRMPlanner
    if name == "OmplRRTConnectPlanner":
        from inequality_mechanisms.adapters.ompl.rrt_connect import OmplRRTConnectPlanner

        return OmplRRTConnectPlanner
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
