"""V4.2D Phase 1: writable root, predecessor freeze, and fail-closed paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from inequality_mechanisms.audits.v4_artifact_guard import (
    FROZEN_V3_REVIEW_PACKAGES,
    REPO_ROOT,
    V4_2C_R_ALLOWED_PACKAGE,
    V4_2D_ALLOWED_OUTPUT_REL,
    V4_2D_ALLOWED_PACKAGE,
    ArtifactPathForbiddenError,
    canonical_v4_0_retained_root,
    canonical_v4_1_retained_root,
    canonical_v4_2_retained_root,
    canonical_v4_2a_retained_root,
    canonical_v4_2b_retained_root,
    canonical_v4_2c_r_retained_root,
    canonical_v4_2c_retained_root,
)

V4_2D_OUTPUT_REL = Path("results") / "v4_review" / V4_2D_ALLOWED_PACKAGE


def test_v4_2d_allowed_root_and_nested_paths() -> None:
    from inequality_mechanisms.audits.v4_artifact_guard import (
        assert_v4_2d_output_allowed,
    )

    root = (REPO_ROOT / V4_2D_ALLOWED_OUTPUT_REL).resolve()
    assert V4_2D_ALLOWED_OUTPUT_REL == V4_2D_OUTPUT_REL
    assert assert_v4_2d_output_allowed(root) == root
    child = root / "data" / "v4_2c_center_reference_rows.jsonl.gz"
    assert assert_v4_2d_output_allowed(child) == child.resolve()


@pytest.mark.parametrize(
    "path_fn, match",
    [
        (canonical_v4_0_retained_root, "frozen V4.0"),
        (canonical_v4_1_retained_root, "frozen V4.1"),
        (canonical_v4_2_retained_root, "frozen V4.2"),
        (canonical_v4_2a_retained_root, "frozen V4.2A"),
        (canonical_v4_2b_retained_root, "frozen V4.2B"),
        (canonical_v4_2c_retained_root, "frozen V4.2C"),
        (canonical_v4_2c_r_retained_root, "frozen V4.2C-R"),
    ],
)
def test_v4_2d_refuses_historical_v4_packages(path_fn, match: str) -> None:
    from inequality_mechanisms.audits.v4_artifact_guard import (
        assert_v4_2d_output_allowed,
    )

    path = path_fn()
    with pytest.raises(ArtifactPathForbiddenError, match=match):
        assert_v4_2d_output_allowed(path)
    with pytest.raises(ArtifactPathForbiddenError, match=match):
        assert_v4_2d_output_allowed(path / "manifest.json")


@pytest.mark.parametrize("package", sorted(FROZEN_V3_REVIEW_PACKAGES))
def test_v4_2d_refuses_frozen_v3(package: str) -> None:
    from inequality_mechanisms.audits.v4_artifact_guard import (
        assert_v4_2d_output_allowed,
    )

    path = (REPO_ROOT / "results" / "v3_review" / package).resolve()
    with pytest.raises(ArtifactPathForbiddenError, match="frozen V3"):
        assert_v4_2d_output_allowed(path)


def test_v4_2d_refuses_sibling_v4_packages() -> None:
    from inequality_mechanisms.audits.v4_artifact_guard import (
        assert_v4_2d_output_allowed,
    )

    path = (
        REPO_ROOT / "results" / "v4_review" / "v4_3_intrinsic_static_wrench"
    ).resolve()
    with pytest.raises(ArtifactPathForbiddenError, match="unauthorized V4 package"):
        assert_v4_2d_output_allowed(path)


def test_v4_2c_r_refuses_v4_2d_package() -> None:
    from inequality_mechanisms.audits.v4_artifact_guard import (
        assert_v4_2c_r_output_allowed,
    )

    path = (REPO_ROOT / V4_2D_ALLOWED_OUTPUT_REL).resolve()
    with pytest.raises(ArtifactPathForbiddenError, match="unauthorized V4 package"):
        assert_v4_2c_r_output_allowed(path)
    with pytest.raises(ArtifactPathForbiddenError, match="unauthorized V4 package"):
        assert_v4_2c_r_output_allowed(path / "manifest.json")


def test_v4_2d_refuses_arbitrary_path(tmp_path: Path) -> None:
    from inequality_mechanisms.audits.v4_artifact_guard import (
        assert_v4_2d_output_allowed,
    )

    with pytest.raises(ArtifactPathForbiddenError, match="not under the allowed root"):
        assert_v4_2d_output_allowed(tmp_path / "elsewhere")


def test_tmp_v4_2d_prepare_leaves_predecessor_paths_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from inequality_mechanisms.audits import v4_artifact_guard as guard

    monkeypatch.setattr(guard, "REPO_ROOT", tmp_path)
    output = tmp_path / "results" / "v4_review" / V4_2D_ALLOWED_PACKAGE
    frozen_c = tmp_path / "results" / "v4_review" / guard.V4_2C_ALLOWED_PACKAGE
    frozen_r = tmp_path / "results" / "v4_review" / V4_2C_R_ALLOWED_PACKAGE
    frozen_c.mkdir(parents=True)
    frozen_r.mkdir(parents=True)
    (frozen_c / "manifest.json").write_text("keep-c\n", encoding="utf-8")
    (frozen_r / "manifest.json").write_text("keep-r\n", encoding="utf-8")
    prepared = guard.prepare_v4_2d_output_dir(output)
    assert prepared == output.resolve()
    assert prepared.is_dir()
    assert (frozen_c / "manifest.json").read_text(encoding="utf-8") == "keep-c\n"
    assert (frozen_r / "manifest.json").read_text(encoding="utf-8") == "keep-r\n"
