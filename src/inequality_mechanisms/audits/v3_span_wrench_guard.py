"""Fail-closed output path guards for the V3.6D–F span/wrench lineage.

Sprint writers may write only under their authorized package:

- V3.6D: ``results/v3_review/v3_6d_span_corpus/``
- V3.6E: ``results/v3_review/v3_6e_static_wrench_core/``
- V3.6F: ``results/v3_review/v3_6f_static_wrench_atlas/``

Frozen V3 review packages and retained V4.0/V4.1 packages remain read-only.
"""

from __future__ import annotations

from pathlib import Path

from inequality_mechanisms.audits.artifact_freeze import FROZEN_EXPLICIT_PACKAGES
from inequality_mechanisms.audits.v4_artifact_guard import (
    V4_0_ALLOWED_PACKAGE,
    V4_1_ALLOWED_PACKAGE,
    canonical_v4_0_retained_root,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
CANONICAL_REPO_ROOT = REPO_ROOT

V3_6D_ALLOWED_PACKAGE = "v3_6d_span_corpus"
V3_6D_ALLOWED_OUTPUT_REL = Path("results") / "v3_review" / V3_6D_ALLOWED_PACKAGE
V3_6E_ALLOWED_PACKAGE = "v3_6e_static_wrench_core"
V3_6F_ALLOWED_PACKAGE = "v3_6f_static_wrench_atlas"

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
    """Raised when a span/wrench writer targets a forbidden output path."""

    failure_code = "artifact_path_forbidden"


def allowed_v3_6d_output_root() -> Path:
    """Absolute allowed V3.6D corpus output root (may be monkeypatched)."""
    return (REPO_ROOT / V3_6D_ALLOWED_OUTPUT_REL).resolve()


def canonical_v4_1_retained_root() -> Path:
    """Committed V4.1 atlas package (never monkeypatched)."""
    return (
        CANONICAL_REPO_ROOT / "results" / "v4_review" / V4_1_ALLOWED_PACKAGE
    ).resolve()


def _is_under(path: Path, parent: Path) -> bool:
    path_r = path.resolve()
    parent_r = parent.resolve()
    return path_r == parent_r or parent_r in path_r.parents


def _package_name_under(path: Path, review_rel: Path) -> str | None:
    review = (REPO_ROOT / review_rel).resolve()
    try:
        rel = path.resolve().relative_to(review)
    except ValueError:
        return None
    if not rel.parts:
        return None
    return rel.parts[0]


def assert_v3_6d_output_allowed(path: Path) -> Path:
    """Resolve ``path`` and assert it is under the V3.6D corpus root."""
    resolved = Path(path).expanduser().resolve()
    allowed = allowed_v3_6d_output_root()
    if _is_under(resolved, allowed):
        return resolved

    v3_package = _package_name_under(path, Path("results") / "v3_review")
    if v3_package in FROZEN_V3_REVIEW_PACKAGES or (
        v3_package is not None and v3_package != V3_6D_ALLOWED_PACKAGE
    ):
        raise ArtifactPathForbiddenError(
            f"Refusing to write into frozen or unauthorized V3 package "
            f"{v3_package!r} at {resolved}. V3.6D may write only under {allowed}."
        )

    v4_package = _package_name_under(path, Path("results") / "v4_review")
    if v4_package in {V4_0_ALLOWED_PACKAGE, V4_1_ALLOWED_PACKAGE}:
        raise ArtifactPathForbiddenError(
            f"Refusing to write into retained V4 package {v4_package!r} "
            f"at {resolved}. V3.6D may write only under {allowed}."
        )
    if v4_package is not None:
        raise ArtifactPathForbiddenError(
            f"Refusing to write into unauthorized V4 package {v4_package!r} "
            f"at {resolved}. V3.6D may write only under {allowed}."
        )

    if _is_under(resolved, canonical_v4_0_retained_root()) or _is_under(
        resolved, canonical_v4_1_retained_root()
    ):
        raise ArtifactPathForbiddenError(
            f"Refusing to overwrite retained V4 evidence at {resolved}."
        )

    raise ArtifactPathForbiddenError(
        f"V3.6D output path {resolved} is not under the allowed root {allowed}."
    )


def prepare_v3_6d_output_dir(path: Path) -> Path:
    """Assert ``path`` is the V3.6D corpus root and create the directory."""
    resolved = assert_v3_6d_output_allowed(path)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def allowed_v3_6e_output_root() -> Path:
    """Absolute allowed V3.6E wrench-core output root."""
    return (REPO_ROOT / "results" / "v3_review" / V3_6E_ALLOWED_PACKAGE).resolve()


def allowed_v3_6f_output_root() -> Path:
    """Absolute allowed V3.6F atlas output root."""
    return (REPO_ROOT / "results" / "v3_review" / V3_6F_ALLOWED_PACKAGE).resolve()


def _assert_package_output_allowed(
    path: Path,
    *,
    allowed: Path,
    package: str,
    writer: str,
) -> Path:
    resolved = Path(path).expanduser().resolve()
    if _is_under(resolved, allowed):
        return resolved
    v3_package = _package_name_under(path, Path("results") / "v3_review")
    if v3_package is not None and v3_package != package:
        raise ArtifactPathForbiddenError(
            f"Refusing to write into V3 package {v3_package!r} at {resolved}. "
            f"{writer} may write only under {allowed}."
        )
    v4_package = _package_name_under(path, Path("results") / "v4_review")
    if v4_package is not None:
        raise ArtifactPathForbiddenError(
            f"Refusing to write into V4 package {v4_package!r} at {resolved}. "
            f"{writer} may write only under {allowed}."
        )
    raise ArtifactPathForbiddenError(
        f"{writer} output path {resolved} is not under the allowed root {allowed}."
    )


def assert_v3_6e_output_allowed(path: Path) -> Path:
    """Resolve ``path`` and assert it is under the V3.6E core root."""
    return _assert_package_output_allowed(
        path,
        allowed=allowed_v3_6e_output_root(),
        package=V3_6E_ALLOWED_PACKAGE,
        writer="V3.6E",
    )


def prepare_v3_6e_output_dir(path: Path) -> Path:
    """Create the guarded V3.6E output directory."""
    resolved = assert_v3_6e_output_allowed(path)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def assert_v3_6f_output_allowed(path: Path) -> Path:
    """Resolve ``path`` and assert it is under the V3.6F atlas root."""
    return _assert_package_output_allowed(
        path,
        allowed=allowed_v3_6f_output_root(),
        package=V3_6F_ALLOWED_PACKAGE,
        writer="V3.6F",
    )


def prepare_v3_6f_output_dir(path: Path) -> Path:
    """Create the guarded V3.6F output directory."""
    resolved = assert_v3_6f_output_allowed(path)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


__all__ = [
    "CANONICAL_REPO_ROOT",
    "FROZEN_V3_REVIEW_PACKAGES",
    "REPO_ROOT",
    "V3_6D_ALLOWED_OUTPUT_REL",
    "V3_6D_ALLOWED_PACKAGE",
    "V3_6E_ALLOWED_PACKAGE",
    "V3_6F_ALLOWED_PACKAGE",
    "ArtifactPathForbiddenError",
    "allowed_v3_6d_output_root",
    "allowed_v3_6e_output_root",
    "allowed_v3_6f_output_root",
    "assert_v3_6d_output_allowed",
    "assert_v3_6e_output_allowed",
    "assert_v3_6f_output_allowed",
    "canonical_v4_1_retained_root",
    "prepare_v3_6d_output_dir",
    "prepare_v3_6e_output_dir",
    "prepare_v3_6f_output_dir",
]
