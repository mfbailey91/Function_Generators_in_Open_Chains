"""Optional OMPL Python-bindings availability gate (Sprint V3.5 / V3-501).

OMPL is an optional algorithm backend. Install the Python bindings separately
(for example via conda-forge ``ompl``). The core ``inequality-mechanisms``
package must import and run without OMPL present.
"""

from __future__ import annotations

from typing import Any


def is_ompl_available() -> bool:
    """Return True when ``ompl.base`` and ``ompl.geometric`` import successfully."""
    try:
        import ompl.base  # noqa: F401
        import ompl.geometric  # noqa: F401
    except Exception:
        return False
    return True


def ompl_version_string() -> str | None:
    """Return a best-effort OMPL version string, or None if unavailable."""
    if not is_ompl_available():
        return None
    try:
        import ompl

        for attr in ("__version__", "OMPL_VERSION", "version"):
            value = getattr(ompl, attr, None)
            if value is not None:
                return str(value)
        # Some builds expose version only through the C++ binding helper.
        import ompl.util as ou  # type: ignore[attr-defined]

        if hasattr(ou, "OMPL_VERSION"):
            return str(ou.OMPL_VERSION)
        # Nanobind pip wheels may only expose package metadata.
        from importlib.metadata import PackageNotFoundError, version

        try:
            return str(version("ompl"))
        except PackageNotFoundError:
            pass
    except Exception:
        return "unknown"
    return "unknown"


def require_ompl() -> tuple[Any, Any]:
    """Import and return ``(ompl.base, ompl.geometric)`` or raise ImportError."""
    if not is_ompl_available():
        raise ImportError(
            "OMPL Python bindings are not available. Install them separately "
            "(e.g. conda-forge package 'ompl') to use adapters.ompl planners."
        )
    import ompl.base as ob
    import ompl.geometric as og

    return ob, og
