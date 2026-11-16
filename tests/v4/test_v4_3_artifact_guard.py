"""V4-300: V4.3 writable root, predecessor freeze, and fail-closed paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from inequality_mechanisms.audits.v4_artifact_guard import (
    FROZEN_V3_REVIEW_PACKAGES,
    REPO_ROOT,
    V4_2D_ALLOWED_PACKAGE,
    V4_3_ALLOWED_OUTPUT_REL,
    V4_3_ALLOWED_PACKAGE,
    ArtifactPathForbiddenError,
    canonical_v4_0_retained_root,
    canonical_v4_1_retained_root,
    canonical_v4_2_retained_root,
    canonical_v4_2a_retained_root,
    canonical_v4_2b_retained_root,
    canonical_v4_2c_r_retained_root,
    canonical_v4_2c_retained_root,
    canonical_v4_2d_retained_root,
)

V4_3_OUTPUT_REL = Path("results") / "v4_review" / V4_3_ALLOWED_PACKAGE


def test_v4_3_allowed_root_and_nested_paths() -> None:
    from inequality_mechanisms.audits.v4_artifact_guard import (
        assert_v4_3_output_allowed,
    )

    root = (REPO_ROOT / V4_3_ALLOWED_OUTPUT_REL).resolve()
    assert V4_3_ALLOWED_OUTPUT_REL == V4_3_OUTPUT_REL
    assert assert_v4_3_output_allowed(root) == root
    child = root / "cases" / "span_j1_145_j2_145" / "summary.json"
    assert assert_v4_3_output_allowed(child) == child.resolve()


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
        (canonical_v4_2d_retained_root, "frozen V4.2D"),
    ],
)
def test_v4_3_refuses_historical_v4_packages(path_fn, match: str) -> None:
    from inequality_mechanisms.audits.v4_artifact_guard import (
        assert_v4_3_output_allowed,
    )

    path = path_fn()
    with pytest.raises(ArtifactPathForbiddenError, match=match):
        assert_v4_3_output_allowed(path)
    with pytest.raises(ArtifactPathForbiddenError, match=match):
        assert_v4_3_output_allowed(path / "manifest.json")


@pytest.mark.parametrize("package", sorted(FROZEN_V3_REVIEW_PACKAGES))
def test_v4_3_refuses_frozen_v3(package: str) -> None:
    from inequality_mechanisms.audits.v4_artifact_guard import (
        assert_v4_3_output_allowed,
    )

    path = (REPO_ROOT / "results" / "v3_review" / package).resolve()
    with pytest.raises(ArtifactPathForbiddenError, match="frozen V3"):
        assert_v4_3_output_allowed(path)


def test_v4_3_refuses_sibling_prefix_lookalike() -> None:
    from inequality_mechanisms.audits.v4_artifact_guard import (
        assert_v4_3_output_allowed,
    )

    path = (
        REPO_ROOT / "results" / "v4_review" / f"{V4_3_ALLOWED_PACKAGE}_backup"
    ).resolve()
    with pytest.raises(ArtifactPathForbiddenError, match="unauthorized V4 package"):
        assert_v4_3_output_allowed(path)


def test_v4_3_refuses_arbitrary_path(tmp_path: Path) -> None:
    from inequality_mechanisms.audits.v4_artifact_guard import (
        assert_v4_3_output_allowed,
    )

    with pytest.raises(ArtifactPathForbiddenError, match="not under the allowed root"):
        assert_v4_3_output_allowed(tmp_path / "elsewhere")


def test_v4_3_refuses_traversal_into_predecessor() -> None:
    from inequality_mechanisms.audits.v4_artifact_guard import (
        assert_v4_3_output_allowed,
    )

    traversal = (
        REPO_ROOT
        / "results"
        / "v4_review"
        / V4_3_ALLOWED_PACKAGE
        / ".."
        / V4_2D_ALLOWED_PACKAGE
        / "manifest.json"
    )
    with pytest.raises(ArtifactPathForbiddenError, match="frozen V4.2D"):
        assert_v4_3_output_allowed(traversal)


def test_v4_3_refuses_symlink_escape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from inequality_mechanisms.audits import v4_artifact_guard as guard

    monkeypatch.setattr(guard, "REPO_ROOT", tmp_path)
    allowed = tmp_path / "results" / "v4_review" / V4_3_ALLOWED_PACKAGE
    frozen = tmp_path / "results" / "v4_review" / guard.V4_2B_ALLOWED_PACKAGE
    allowed.mkdir(parents=True)
    frozen.mkdir(parents=True)
    (frozen / "manifest.json").write_text("keep\n", encoding="utf-8")
    link = allowed / "escape"
    link.symlink_to(frozen / "manifest.json")
    with pytest.raises(ArtifactPathForbiddenError, match="frozen V4.2B"):
        guard.assert_v4_3_output_allowed(link)


def test_v4_3_refuses_occupied_output_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from inequality_mechanisms.audits import v4_artifact_guard as guard

    monkeypatch.setattr(guard, "REPO_ROOT", tmp_path)
    output = tmp_path / "results" / "v4_review" / V4_3_ALLOWED_PACKAGE
    output.mkdir(parents=True)
    (output / "manifest.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(ArtifactPathForbiddenError, match="non-empty V4.3"):
        guard.assert_v4_3_output_root_empty(output)


def test_tmp_v4_3_prepare_leaves_predecessors_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from inequality_mechanisms.audits import v4_artifact_guard as guard

    monkeypatch.setattr(guard, "REPO_ROOT", tmp_path)
    output = tmp_path / "results" / "v4_review" / V4_3_ALLOWED_PACKAGE
    frozen_b = tmp_path / "results" / "v4_review" / guard.V4_2B_ALLOWED_PACKAGE
    frozen_d = tmp_path / "results" / "v4_review" / V4_2D_ALLOWED_PACKAGE
    frozen_b.mkdir(parents=True)
    frozen_d.mkdir(parents=True)
    (frozen_b / "manifest.json").write_text("keep-b\n", encoding="utf-8")
    (frozen_d / "manifest.json").write_text("keep-d\n", encoding="utf-8")
    prepared = guard.prepare_v4_3_output_dir(output)
    assert prepared == output.resolve()
    assert prepared.is_dir()
    assert (frozen_b / "manifest.json").read_text(encoding="utf-8") == "keep-b\n"
    assert (frozen_d / "manifest.json").read_text(encoding="utf-8") == "keep-d\n"
