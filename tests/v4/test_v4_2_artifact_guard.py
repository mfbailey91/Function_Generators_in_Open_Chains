"""V4-200: V4.2 writers may write only the span-atlas root."""

from __future__ import annotations

from pathlib import Path

import pytest

from inequality_mechanisms.audits import v4_artifact_guard
from inequality_mechanisms.audits.v4_artifact_guard import (
    FROZEN_V3_REVIEW_PACKAGES,
    REPO_ROOT,
    V4_0_ALLOWED_PACKAGE,
    V4_1_ALLOWED_PACKAGE,
    V4_2_ALLOWED_OUTPUT_REL,
    V4_2_ALLOWED_PACKAGE,
    ArtifactPathForbiddenError,
    assert_v4_1_output_allowed,
    assert_v4_2_output_allowed,
    canonical_v4_0_retained_root,
    canonical_v4_1_retained_root,
    prepare_v4_2_output_dir,
)


def test_v4_2_allowed_root_and_nested_paths() -> None:
    root = (REPO_ROOT / V4_2_ALLOWED_OUTPUT_REL).resolve()
    assert assert_v4_2_output_allowed(root) == root
    child = root / "cases" / "span_j1_145_j2_145" / "index.html"
    assert assert_v4_2_output_allowed(child) == child.resolve()
    assert assert_v4_2_output_allowed(V4_2_ALLOWED_OUTPUT_REL) == root


def test_v4_2_refuses_retained_v4_0() -> None:
    path = canonical_v4_0_retained_root()
    with pytest.raises(ArtifactPathForbiddenError, match="frozen V4.0"):
        assert_v4_2_output_allowed(path)
    with pytest.raises(ArtifactPathForbiddenError, match="frozen V4.0"):
        assert_v4_2_output_allowed(path / "manifest.json")


def test_v4_2_refuses_retained_v4_1() -> None:
    path = canonical_v4_1_retained_root()
    with pytest.raises(ArtifactPathForbiddenError, match="frozen V4.1"):
        assert_v4_2_output_allowed(path)
    with pytest.raises(ArtifactPathForbiddenError, match="frozen V4.1"):
        assert_v4_2_output_allowed(path / "index.html")
    with pytest.raises(ArtifactPathForbiddenError, match="unauthorized V4"):
        assert_v4_1_output_allowed(REPO_ROOT / V4_2_ALLOWED_OUTPUT_REL)


@pytest.mark.parametrize("package", sorted(FROZEN_V3_REVIEW_PACKAGES))
def test_v4_2_refuses_frozen_v3(package: str) -> None:
    path = (REPO_ROOT / "results" / "v3_review" / package).resolve()
    with pytest.raises(ArtifactPathForbiddenError, match="frozen V3"):
        assert_v4_2_output_allowed(path)


@pytest.mark.parametrize(
    "package",
    ["v3_6d_span_corpus", "v3_6e_static_wrench_core", "v3_6f_static_wrench_atlas"],
)
def test_v4_2_refuses_v3_6d_through_f(package: str) -> None:
    path = (REPO_ROOT / "results" / "v3_review" / package).resolve()
    with pytest.raises(ArtifactPathForbiddenError, match="frozen V3"):
        assert_v4_2_output_allowed(path)


@pytest.mark.parametrize(
    "package",
    ["v4_3_intrinsic_static_wrench", "v4_7_closeout", V4_0_ALLOWED_PACKAGE],
)
def test_v4_2_refuses_sibling_v4_packages(package: str) -> None:
    path = (REPO_ROOT / "results" / "v4_review" / package).resolve()
    with pytest.raises(ArtifactPathForbiddenError):
        assert_v4_2_output_allowed(path)


def test_v4_2_refuses_arbitrary_path(tmp_path: Path) -> None:
    with pytest.raises(ArtifactPathForbiddenError, match="not under the allowed root"):
        assert_v4_2_output_allowed(tmp_path / "elsewhere")


def test_prepare_v4_2_output_dir_creates_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(v4_artifact_guard, "REPO_ROOT", tmp_path)
    allowed = tmp_path / "results" / "v4_review" / V4_2_ALLOWED_PACKAGE
    created = prepare_v4_2_output_dir(allowed)
    assert created == allowed.resolve()
    assert created.is_dir()
    frozen = tmp_path / "results" / "v4_review" / V4_1_ALLOWED_PACKAGE
    frozen.mkdir(parents=True)
    with pytest.raises(ArtifactPathForbiddenError, match="frozen V4.1"):
        prepare_v4_2_output_dir(frozen)
