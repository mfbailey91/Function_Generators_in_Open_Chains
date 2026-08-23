"""V4.2C Phase 1: writable root, predecessor freeze, and fail-closed paths."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from inequality_mechanisms.audits.v4_artifact_guard import (
    FROZEN_V3_REVIEW_PACKAGES,
    REPO_ROOT,
    V4_0_ALLOWED_PACKAGE,
    V4_1_ALLOWED_PACKAGE,
    V4_2_ALLOWED_PACKAGE,
    V4_2A_ALLOWED_PACKAGE,
    V4_2B_ALLOWED_PACKAGE,
    V4_2C_ALLOWED_OUTPUT_REL,
    V4_2C_ALLOWED_PACKAGE,
    ArtifactPathForbiddenError,
    canonical_v4_0_retained_root,
    canonical_v4_1_retained_root,
    canonical_v4_2_retained_root,
    canonical_v4_2a_retained_root,
    canonical_v4_2b_retained_root,
    digest_git_tracked_paths,
    git_ls_files,
    v4_2b_git_tracked_package_digest,
)

DIGEST_LOCK = (
    Path(__file__).resolve().parent / "data" / "frozen_v4_2b_closeout_digests.json"
)
V4_2C_OUTPUT_REL = Path("results") / "v4_review" / V4_2C_ALLOWED_PACKAGE


def _assert_lock(
    path: Path,
    *,
    schema_version: str,
    package: str,
    digest_fn: Callable[[], tuple[str, int]],
    digest_kind: str | None = None,
) -> None:
    lock = json.loads(path.read_text(encoding="utf-8"))
    assert lock["schema_version"] == schema_version
    assert lock["package"] == package
    if digest_kind is not None:
        assert lock["digest_kind"] == digest_kind
    sha, n_files = digest_fn()
    assert n_files == lock["n_files"], path.name
    assert sha == lock["sha256"], path.name


def _v3_review_git_tracked_digest() -> tuple[str, int]:
    paths = git_ls_files("results/v3_review")
    return digest_git_tracked_paths(paths)


def test_v4_2c_allowed_root_and_nested_paths() -> None:
    from inequality_mechanisms.audits.v4_artifact_guard import (
        assert_v4_2c_output_allowed,
    )

    root = (REPO_ROOT / V4_2C_ALLOWED_OUTPUT_REL).resolve()
    assert V4_2C_ALLOWED_OUTPUT_REL == V4_2C_OUTPUT_REL
    assert assert_v4_2c_output_allowed(root) == root
    child = root / "stage_c" / "rows" / "bitstar.json"
    assert assert_v4_2c_output_allowed(child) == child.resolve()


@pytest.mark.parametrize(
    "path_fn, match",
    [
        (canonical_v4_0_retained_root, "frozen V4.0"),
        (canonical_v4_1_retained_root, "frozen V4.1"),
        (canonical_v4_2_retained_root, "frozen V4.2"),
        (canonical_v4_2a_retained_root, "frozen V4.2A"),
        (canonical_v4_2b_retained_root, "frozen V4.2B"),
    ],
)
def test_v4_2c_refuses_historical_v4_packages(path_fn, match: str) -> None:
    from inequality_mechanisms.audits.v4_artifact_guard import (
        assert_v4_2c_output_allowed,
    )

    path = path_fn()
    with pytest.raises(ArtifactPathForbiddenError, match=match):
        assert_v4_2c_output_allowed(path)
    with pytest.raises(ArtifactPathForbiddenError, match=match):
        assert_v4_2c_output_allowed(path / "manifest.json")


@pytest.mark.parametrize("package", sorted(FROZEN_V3_REVIEW_PACKAGES))
def test_v4_2c_refuses_frozen_v3(package: str) -> None:
    from inequality_mechanisms.audits.v4_artifact_guard import (
        assert_v4_2c_output_allowed,
    )

    path = (REPO_ROOT / "results" / "v3_review" / package).resolve()
    with pytest.raises(ArtifactPathForbiddenError, match="frozen V3"):
        assert_v4_2c_output_allowed(path)


def test_v4_2c_refuses_sibling_v4_packages() -> None:
    from inequality_mechanisms.audits.v4_artifact_guard import (
        assert_v4_2c_output_allowed,
    )

    path = (
        REPO_ROOT / "results" / "v4_review" / "v4_3_intrinsic_static_wrench"
    ).resolve()
    with pytest.raises(ArtifactPathForbiddenError, match="unauthorized V4 package"):
        assert_v4_2c_output_allowed(path)


def test_v4_2b_refuses_v4_2c_package() -> None:
    from inequality_mechanisms.audits.v4_artifact_guard import (
        assert_v4_2b_output_allowed,
    )

    path = (REPO_ROOT / V4_2C_ALLOWED_OUTPUT_REL).resolve()
    with pytest.raises(ArtifactPathForbiddenError, match="unauthorized V4 package"):
        assert_v4_2b_output_allowed(path)
    with pytest.raises(ArtifactPathForbiddenError, match="unauthorized V4 package"):
        assert_v4_2b_output_allowed(path / "manifest.json")


def test_v4_2c_refuses_arbitrary_path(tmp_path: Path) -> None:
    from inequality_mechanisms.audits.v4_artifact_guard import (
        assert_v4_2c_output_allowed,
    )

    with pytest.raises(ArtifactPathForbiddenError, match="not under the allowed root"):
        assert_v4_2c_output_allowed(tmp_path / "elsewhere")


def test_tmp_v4_2c_prepare_leaves_predecessor_git_tracked_digests_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from inequality_mechanisms.audits import v4_artifact_guard
    from inequality_mechanisms.audits.v4_artifact_guard import prepare_v4_2c_output_dir

    sha_2b, n_2b = v4_2b_git_tracked_package_digest()
    sha_v3, n_v3 = _v3_review_git_tracked_digest()
    monkeypatch.setattr(v4_artifact_guard, "REPO_ROOT", tmp_path)
    output = tmp_path / "results" / "v4_review" / V4_2C_ALLOWED_PACKAGE
    prepared = prepare_v4_2c_output_dir(output)
    (prepared / "placeholder.txt").write_text("tmp", encoding="utf-8")
    sha_2b_after, n_2b_after = v4_2b_git_tracked_package_digest()
    sha_v3_after, n_v3_after = _v3_review_git_tracked_digest()
    assert (sha_2b_after, n_2b_after) == (sha_2b, n_2b)
    assert (sha_v3_after, n_v3_after) == (sha_v3, n_v3)
    assert V4_0_ALLOWED_PACKAGE != V4_2C_ALLOWED_PACKAGE
    assert V4_1_ALLOWED_PACKAGE != V4_2C_ALLOWED_PACKAGE
    assert V4_2_ALLOWED_PACKAGE != V4_2C_ALLOWED_PACKAGE
    assert V4_2A_ALLOWED_PACKAGE != V4_2C_ALLOWED_PACKAGE
    assert V4_2B_ALLOWED_PACKAGE != V4_2C_ALLOWED_PACKAGE


def test_v4_2b_closeout_digest_lock_matches_committed_package() -> None:
    _assert_lock(
        DIGEST_LOCK,
        schema_version="v4.2c.frozen_v4_2b_git_tracked_digests.v1",
        package=V4_2B_ALLOWED_PACKAGE,
        digest_fn=v4_2b_git_tracked_package_digest,
        digest_kind="git_tracked",
    )
