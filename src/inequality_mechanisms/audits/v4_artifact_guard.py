"""Fail-closed output path guards for Sprint V4.0 artifacts.

V4.0 may write only under ``results/v4_review/v4_0_kinematic_geometry_core/``.
Every package under ``results/v3_review/`` is frozen for Version 4 writers,
including the accepted V3.6C closeout. Other ``results/v4_review/`` packages
are unauthorized until a later sprint is activated.
"""

from __future__ import annotations

from pathlib import Path

from inequality_mechanisms.audits.artifact_freeze import FROZEN_EXPLICIT_PACKAGES

# Repo root: src/inequality_mechanisms/audits/v4_artifact_guard.py -> parents[3]
REPO_ROOT = Path(__file__).resolve().parents[3]

V4_0_ALLOWED_PACKAGE = "v4_0_kinematic_geometry_core"
V4_0_ALLOWED_OUTPUT_REL = Path("results") / "v4_review" / V4_0_ALLOWED_PACKAGE

# Accepted V3 closeout packages that V3.6C could write, but V4 must not.
FROZEN_V3_CLOSEOUT_PACKAGES: frozenset[str] = frozenset(
    {
        "v3_5_closeout",
        "v3_6c_planar2r_closeout",
    }
)

FROZEN_V3_REVIEW_PACKAGES: frozenset[str] = (
    FROZEN_EXPLICIT_PACKAGES | FROZEN_V3_CLOSEOUT_PACKAGES
)


class ArtifactPathForbiddenError(ValueError):
    """Raised when a Version 4 writer targets a forbidden output path."""

    failure_code = "artifact_path_forbidden"


def allowed_v4_0_output_root() -> Path:
    """Absolute allowed V4.0 geometry-core output root."""
    return (REPO_ROOT / V4_0_ALLOWED_OUTPUT_REL).resolve()


def _is_under(path: Path, parent: Path) -> bool:
    path_r = path.resolve()
    parent_r = parent.resolve()
    return path_r == parent_r or parent_r in path_r.parents


def _package_name_under(path: Path, review_rel: Path) -> str | None:
    """Return the top-level package name under ``review_rel``, if any."""
    review = (REPO_ROOT / review_rel).resolve()
    try:
        rel = path.resolve().relative_to(review)
    except ValueError:
        return None
    if not rel.parts:
        return None
    return rel.parts[0]


def _v3_review_package_name(path: Path) -> str | None:
    return _package_name_under(path, Path("results") / "v3_review")


def _v4_review_package_name(path: Path) -> str | None:
    return _package_name_under(path, Path("results") / "v4_review")


def assert_v4_0_output_allowed(path: Path) -> Path:
    """Resolve ``path`` and assert it is under the V4.0 output root.

    Parameters
    ----------
    path :
        Candidate output directory (absolute or relative).

    Returns
    -------
    pathlib.Path
        Resolved absolute path when the write is allowed.

    Raises
    ------
    ArtifactPathForbiddenError
        If ``path`` is under ``results/v3_review/``, under a different
        ``results/v4_review/`` package, or otherwise outside the allowed
        V4.0 root.
    """
    resolved = Path(path).expanduser().resolve()
    allowed = allowed_v4_0_output_root()
    if _is_under(resolved, allowed):
        return resolved

    v3_review = (REPO_ROOT / "results" / "v3_review").resolve()
    if _is_under(resolved, v3_review):
        v3_package = _v3_review_package_name(resolved) or "v3_review"
        raise ArtifactPathForbiddenError(
            f"Refusing to write into frozen V3 evidence package {v3_package!r} "
            f"at {resolved}. V4.0 may write only under {allowed}."
        )

    v4_package = _v4_review_package_name(resolved)
    if v4_package is not None and v4_package != V4_0_ALLOWED_PACKAGE:
        raise ArtifactPathForbiddenError(
            f"Refusing to write into unauthorized V4 package {v4_package!r} "
            f"at {resolved}. V4.0 may write only under {allowed}."
        )

    raise ArtifactPathForbiddenError(
        f"V4.0 output path {resolved} is not under the allowed root {allowed}."
    )


def prepare_v4_0_output_dir(path: Path) -> Path:
    """Assert ``path`` is allowed and create the directory from a clean tree.

    Parameters
    ----------
    path :
        Candidate V4.0 output directory.

    Returns
    -------
    pathlib.Path
        Resolved allowed directory after ``mkdir(parents=True, exist_ok=True)``.
    """
    resolved = assert_v4_0_output_allowed(path)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


__all__ = [
    "FROZEN_V3_CLOSEOUT_PACKAGES",
    "FROZEN_V3_REVIEW_PACKAGES",
    "REPO_ROOT",
    "V4_0_ALLOWED_OUTPUT_REL",
    "V4_0_ALLOWED_PACKAGE",
    "ArtifactPathForbiddenError",
    "allowed_v4_0_output_root",
    "assert_v4_0_output_allowed",
    "prepare_v4_0_output_dir",
]
