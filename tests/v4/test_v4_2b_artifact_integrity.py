"""V4.2B Phase 1: corrective package root and historical freeze (V4-220/V4-227)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from inequality_mechanisms.audits.v4_artifact_guard import (
    CANONICAL_REPO_ROOT,
    FROZEN_V3_REVIEW_PACKAGES,
    REPO_ROOT,
    V4_0_ALLOWED_PACKAGE,
    V4_1_ALLOWED_PACKAGE,
    V4_2_ALLOWED_PACKAGE,
    V4_2A_ALLOWED_PACKAGE,
    ArtifactPathForbiddenError,
    canonical_v4_0_retained_root,
    canonical_v4_1_retained_root,
    canonical_v4_2_retained_root,
    canonical_v4_2a_retained_root,
    v4_2_git_tracked_package_digest,
    v4_2a_git_tracked_package_digest,
)

V4_2B_PACKAGE = "v4_2b_span_controlled_corrective_closeout"
V4_2B_OUTPUT_REL = Path("results") / "v4_review" / V4_2B_PACKAGE
VERIFY_SCRIPT = CANONICAL_REPO_ROOT / "scripts" / "verify_v4_2b_artifact.py"


def test_v4_2b_allowed_root_and_nested_paths() -> None:
    from inequality_mechanisms.audits.v4_artifact_guard import (
        V4_2B_ALLOWED_OUTPUT_REL,
        assert_v4_2b_output_allowed,
    )

    root = (REPO_ROOT / V4_2B_ALLOWED_OUTPUT_REL).resolve()
    assert V4_2B_ALLOWED_OUTPUT_REL == V4_2B_OUTPUT_REL
    assert assert_v4_2b_output_allowed(root) == root
    child = root / "geometry_atlas" / "cases" / "span_j1_145_j2_145" / "index.html"
    assert assert_v4_2b_output_allowed(child) == child.resolve()


@pytest.mark.parametrize(
    "path_fn, match",
    [
        (canonical_v4_0_retained_root, "frozen V4.0"),
        (canonical_v4_1_retained_root, "frozen V4.1"),
        (canonical_v4_2_retained_root, "frozen V4.2"),
        (canonical_v4_2a_retained_root, "frozen V4.2A"),
    ],
)
def test_v4_2b_refuses_historical_v4_packages(path_fn, match: str) -> None:
    from inequality_mechanisms.audits.v4_artifact_guard import assert_v4_2b_output_allowed

    path = path_fn()
    with pytest.raises(ArtifactPathForbiddenError, match=match):
        assert_v4_2b_output_allowed(path)
    with pytest.raises(ArtifactPathForbiddenError, match=match):
        assert_v4_2b_output_allowed(path / "manifest.json")


@pytest.mark.parametrize("package", sorted(FROZEN_V3_REVIEW_PACKAGES))
def test_v4_2b_refuses_frozen_v3(package: str) -> None:
    from inequality_mechanisms.audits.v4_artifact_guard import assert_v4_2b_output_allowed

    path = (REPO_ROOT / "results" / "v3_review" / package).resolve()
    with pytest.raises(ArtifactPathForbiddenError, match="frozen V3"):
        assert_v4_2b_output_allowed(path)


def test_tmp_v4_2b_prepare_leaves_historical_git_tracked_digests_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from inequality_mechanisms.audits import v4_artifact_guard
    from inequality_mechanisms.audits.v4_artifact_guard import prepare_v4_2b_output_dir

    sha_2, n_2 = v4_2_git_tracked_package_digest()
    sha_2a, n_2a = v4_2a_git_tracked_package_digest()
    monkeypatch.setattr(v4_artifact_guard, "REPO_ROOT", tmp_path)
    output = tmp_path / "results" / "v4_review" / V4_2B_PACKAGE
    prepared = prepare_v4_2b_output_dir(output)
    (prepared / "placeholder.txt").write_text("tmp", encoding="utf-8")
    sha_2_after, n_2_after = v4_2_git_tracked_package_digest()
    sha_2a_after, n_2a_after = v4_2a_git_tracked_package_digest()
    assert (sha_2_after, n_2_after) == (sha_2, n_2)
    assert (sha_2a_after, n_2a_after) == (sha_2a, n_2a)
    assert V4_0_ALLOWED_PACKAGE != V4_2B_PACKAGE
    assert V4_1_ALLOWED_PACKAGE != V4_2B_PACKAGE
    assert V4_2_ALLOWED_PACKAGE != V4_2B_PACKAGE
    assert V4_2A_ALLOWED_PACKAGE != V4_2B_PACKAGE


def test_v4_2b_verifier_script_exists_and_loads() -> None:
    assert VERIFY_SCRIPT.is_file()
    spec = importlib.util.spec_from_file_location("verify_v4_2b_artifact", VERIFY_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert callable(getattr(module, "verify_v4_2b_artifact"))
