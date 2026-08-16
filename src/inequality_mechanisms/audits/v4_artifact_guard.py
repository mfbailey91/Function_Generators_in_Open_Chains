"""Fail-closed output path guards for Version 4 artifacts.

V4.0 historically wrote only under ``results/v4_review/v4_0_kinematic_geometry_core/``.
That package is now retained evidence: canonical-path overwrites are forbidden.
V4.1 writers may write only under ``results/v4_review/v4_1_planar2r_geometry_atlas/``.

Every package under ``results/v3_review/`` remains frozen. Other
``results/v4_review/`` packages stay unauthorized.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from inequality_mechanisms.audits.artifact_freeze import FROZEN_EXPLICIT_PACKAGES

# Repo root: src/inequality_mechanisms/audits/v4_artifact_guard.py -> parents[3]
# Canonical root is never monkeypatched; REPO_ROOT may be patched in tests.
CANONICAL_REPO_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = CANONICAL_REPO_ROOT

V4_0_ALLOWED_PACKAGE = "v4_0_kinematic_geometry_core"
V4_0_ALLOWED_OUTPUT_REL = Path("results") / "v4_review" / V4_0_ALLOWED_PACKAGE
V4_1_ALLOWED_PACKAGE = "v4_1_planar2r_geometry_atlas"
V4_1_ALLOWED_OUTPUT_REL = Path("results") / "v4_review" / V4_1_ALLOWED_PACKAGE

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
    """Absolute allowed V4.0 geometry-core output root (may be monkeypatched)."""
    return (REPO_ROOT / V4_0_ALLOWED_OUTPUT_REL).resolve()


def allowed_v4_1_output_root() -> Path:
    """Absolute allowed V4.1 atlas output root (may be monkeypatched)."""
    return (REPO_ROOT / V4_1_ALLOWED_OUTPUT_REL).resolve()


def canonical_v4_0_retained_root() -> Path:
    """Committed V4.0 smoke package in this repository (never monkeypatched)."""
    return (CANONICAL_REPO_ROOT / V4_0_ALLOWED_OUTPUT_REL).resolve()


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


def _refuse_v3(resolved: Path, *, writer: str, allowed: Path) -> None:
    v3_review = (REPO_ROOT / "results" / "v3_review").resolve()
    if _is_under(resolved, v3_review):
        v3_package = _v3_review_package_name(resolved) or "v3_review"
        raise ArtifactPathForbiddenError(
            f"Refusing to write into frozen V3 evidence package {v3_package!r} "
            f"at {resolved}. {writer} may write only under {allowed}."
        )


def assert_not_overwriting_retained_v4_0(path: Path) -> Path:
    """Refuse writes that would mutate the committed V4.0 smoke package.

    Parameters
    ----------
    path :
        Candidate output path.

    Returns
    -------
    pathlib.Path
        Resolved path when it is not the retained V4.0 package.

    Raises
    ------
    ArtifactPathForbiddenError
        If ``path`` is under the canonical retained V4.0 smoke root.
    """
    resolved = Path(path).expanduser().resolve()
    retained = canonical_v4_0_retained_root()
    if _is_under(resolved, retained):
        raise ArtifactPathForbiddenError(
            "Refusing to overwrite frozen V4.0 retained evidence "
            f"at {resolved}."
        )
    return resolved


def assert_v4_0_output_allowed(path: Path) -> Path:
    """Resolve ``path`` and assert it is under the V4.0 output root.

    This is the historical V4.0 writer contract. Canonical retained-package
    overwrite is refused separately by
    :func:`assert_not_overwriting_retained_v4_0`.
    """
    resolved = Path(path).expanduser().resolve()
    allowed = allowed_v4_0_output_root()
    if _is_under(resolved, allowed):
        return resolved

    _refuse_v3(resolved, writer="V4.0", allowed=allowed)

    v4_package = _v4_review_package_name(resolved)
    if v4_package is not None and v4_package != V4_0_ALLOWED_PACKAGE:
        raise ArtifactPathForbiddenError(
            f"Refusing to write into unauthorized V4 package {v4_package!r} "
            f"at {resolved}. V4.0 may write only under {allowed}."
        )

    raise ArtifactPathForbiddenError(
        f"V4.0 output path {resolved} is not under the allowed root {allowed}."
    )


def assert_v4_1_output_allowed(path: Path) -> Path:
    """Resolve ``path`` and assert it is under the V4.1 atlas output root.

    V4.1 writers must reject the retained V4.0 smoke package, every V3
    review package, sibling V4 packages, and arbitrary paths.
    """
    resolved = Path(path).expanduser().resolve()
    allowed = allowed_v4_1_output_root()
    if _is_under(resolved, allowed):
        return resolved

    _refuse_v3(resolved, writer="V4.1", allowed=allowed)

    v4_package = _v4_review_package_name(resolved)
    if v4_package == V4_0_ALLOWED_PACKAGE:
        raise ArtifactPathForbiddenError(
            "Refusing to write into frozen V4.0 retained evidence "
            f"at {resolved}. V4.1 may write only under {allowed}."
        )
    if v4_package is not None and v4_package != V4_1_ALLOWED_PACKAGE:
        raise ArtifactPathForbiddenError(
            f"Refusing to write into unauthorized V4 package {v4_package!r} "
            f"at {resolved}. V4.1 may write only under {allowed}."
        )

    raise ArtifactPathForbiddenError(
        f"V4.1 output path {resolved} is not under the allowed root {allowed}."
    )


def prepare_v4_0_output_dir(path: Path) -> Path:
    """Assert ``path`` is allowed and create the directory from a clean tree.

    Canonical retained V4.0 evidence cannot be created or overwritten.
    Monkeypatched tmp roots remain writable for V4-008 tests.
    """
    resolved = assert_v4_0_output_allowed(path)
    assert_not_overwriting_retained_v4_0(resolved)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def prepare_v4_1_output_dir(path: Path) -> Path:
    """Assert ``path`` is the V4.1 atlas root and create the directory."""
    resolved = assert_v4_1_output_allowed(path)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def git_ls_files(*paths: str, cwd: Path | None = None) -> list[str]:
    """Return git-tracked paths under ``paths`` relative to ``cwd``."""
    root = CANONICAL_REPO_ROOT if cwd is None else Path(cwd)
    proc = subprocess.run(
        ["git", "ls-files", "-z", "--", *paths],
        cwd=root,
        check=True,
        capture_output=True,
    )
    if not proc.stdout:
        return []
    return [item.decode("utf-8") for item in proc.stdout.split(b"\0") if item]


def digest_git_tracked_paths(rel_paths: list[str], *, cwd: Path | None = None) -> tuple[str, int]:
    """Return SHA-256 of sorted relative paths and per-file hashes."""
    root = CANONICAL_REPO_ROOT if cwd is None else Path(cwd)
    digest = hashlib.sha256()
    for rel in sorted(rel_paths):
        payload = (root / rel).read_bytes()
        file_hash = hashlib.sha256(payload).hexdigest()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest(), len(rel_paths)


def v4_0_smoke_package_digest() -> tuple[str, int]:
    """Digest git-tracked files of the retained V4.0 smoke package."""
    prefix = f"{V4_0_ALLOWED_OUTPUT_REL.as_posix()}/"
    paths = [
        rel
        for rel in git_ls_files(V4_0_ALLOWED_OUTPUT_REL.as_posix())
        if rel.startswith(prefix) or rel == V4_0_ALLOWED_OUTPUT_REL.as_posix()
    ]
    return digest_git_tracked_paths(paths)


__all__ = [
    "CANONICAL_REPO_ROOT",
    "FROZEN_V3_CLOSEOUT_PACKAGES",
    "FROZEN_V3_REVIEW_PACKAGES",
    "REPO_ROOT",
    "V4_0_ALLOWED_OUTPUT_REL",
    "V4_0_ALLOWED_PACKAGE",
    "V4_1_ALLOWED_OUTPUT_REL",
    "V4_1_ALLOWED_PACKAGE",
    "ArtifactPathForbiddenError",
    "allowed_v4_0_output_root",
    "allowed_v4_1_output_root",
    "assert_not_overwriting_retained_v4_0",
    "assert_v4_0_output_allowed",
    "assert_v4_1_output_allowed",
    "canonical_v4_0_retained_root",
    "digest_git_tracked_paths",
    "git_ls_files",
    "prepare_v4_0_output_dir",
    "prepare_v4_1_output_dir",
    "v4_0_smoke_package_digest",
]
