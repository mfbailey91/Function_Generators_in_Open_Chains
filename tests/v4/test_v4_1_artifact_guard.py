"""V4-100: V4.1 writers may write only the atlas root; V4.0 smoke is frozen."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from inequality_mechanisms.audits import v4_artifact_guard
from inequality_mechanisms.audits.v4_artifact_guard import (
    FROZEN_V3_REVIEW_PACKAGES,
    REPO_ROOT,
    V4_0_ALLOWED_PACKAGE,
    V4_1_ALLOWED_OUTPUT_REL,
    V4_1_ALLOWED_PACKAGE,
    ArtifactPathForbiddenError,
    assert_not_overwriting_retained_v4_0,
    assert_v4_0_output_allowed,
    assert_v4_1_output_allowed,
    canonical_v4_0_retained_root,
    prepare_v4_0_output_dir,
    prepare_v4_1_output_dir,
    v4_0_smoke_package_digest,
)
from inequality_mechanisms.audits.v4_geometry_core_smoke import generate_geometry_core_smoke

DIGEST_LOCK = Path(__file__).resolve().parent / "data" / "frozen_v4_0_smoke_digests.json"


def test_v4_0_smoke_digest_lock_matches_committed_package() -> None:
    lock = json.loads(DIGEST_LOCK.read_text(encoding="utf-8"))
    assert lock["schema_version"] == "v4.0.frozen_v4_0_smoke_digests.v1"
    assert lock["package"] == V4_0_ALLOWED_PACKAGE
    sha, n_files = v4_0_smoke_package_digest()
    assert n_files == lock["n_files"]
    assert sha == lock["sha256"]


def test_canonical_v4_0_overwrite_is_refused() -> None:
    retained = canonical_v4_0_retained_root()
    with pytest.raises(ArtifactPathForbiddenError, match="frozen V4.0"):
        assert_not_overwriting_retained_v4_0(retained)
    with pytest.raises(ArtifactPathForbiddenError, match="frozen V4.0"):
        assert_not_overwriting_retained_v4_0(retained / "manifest.json")
    with pytest.raises(ArtifactPathForbiddenError, match="frozen V4.0"):
        prepare_v4_0_output_dir(retained)
    with pytest.raises(ArtifactPathForbiddenError, match="frozen V4.0"):
        generate_geometry_core_smoke(retained)


def test_v4_1_allowed_root_and_nested_paths() -> None:
    root = (REPO_ROOT / V4_1_ALLOWED_OUTPUT_REL).resolve()
    assert assert_v4_1_output_allowed(root) == root
    child = root / "geometry_samples.jsonl"
    assert assert_v4_1_output_allowed(child) == child.resolve()
    relative = V4_1_ALLOWED_OUTPUT_REL
    assert assert_v4_1_output_allowed(relative) == root


def test_v4_1_refuses_retained_v4_0() -> None:
    path = canonical_v4_0_retained_root()
    with pytest.raises(ArtifactPathForbiddenError, match="frozen V4.0"):
        assert_v4_1_output_allowed(path)
    with pytest.raises(ArtifactPathForbiddenError, match="frozen V4.0"):
        assert_v4_1_output_allowed(path / "index.html")


@pytest.mark.parametrize("package", sorted(FROZEN_V3_REVIEW_PACKAGES))
def test_v4_1_refuses_frozen_v3(package: str) -> None:
    path = (REPO_ROOT / "results" / "v3_review" / package).resolve()
    with pytest.raises(ArtifactPathForbiddenError, match="frozen V3"):
        assert_v4_1_output_allowed(path)


@pytest.mark.parametrize(
    "package",
    ["v4_2_differential_ik_velocity", "v4_7_closeout"],
)
def test_v4_1_refuses_sibling_v4_packages(package: str) -> None:
    path = (REPO_ROOT / "results" / "v4_review" / package).resolve()
    with pytest.raises(ArtifactPathForbiddenError, match="unauthorized V4"):
        assert_v4_1_output_allowed(path)


def test_v4_1_refuses_arbitrary_path(tmp_path: Path) -> None:
    with pytest.raises(ArtifactPathForbiddenError, match="not under the allowed root"):
        assert_v4_1_output_allowed(tmp_path / "elsewhere")


def test_prepare_v4_1_output_dir_creates_clean_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(v4_artifact_guard, "REPO_ROOT", tmp_path)
    allowed = tmp_path / "results" / "v4_review" / V4_1_ALLOWED_PACKAGE
    created = prepare_v4_1_output_dir(allowed)
    assert created == allowed.resolve()
    assert created.is_dir()


def test_v4_1_tmp_runner_refuses_v4_0_and_writes_atlas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(v4_artifact_guard, "REPO_ROOT", tmp_path)
    frozen = tmp_path / "results" / "v4_review" / V4_0_ALLOWED_PACKAGE
    frozen.mkdir(parents=True)
    with pytest.raises(ArtifactPathForbiddenError, match="frozen V4.0"):
        prepare_v4_1_output_dir(frozen)
    allowed = tmp_path / "results" / "v4_review" / V4_1_ALLOWED_PACKAGE
    created = prepare_v4_1_output_dir(allowed)
    (created / "manifest.json").write_text("{}", encoding="utf-8")
    assert (created / "manifest.json").is_file()


def test_v4_0_writer_still_refuses_v4_1_root() -> None:
    path = (REPO_ROOT / V4_1_ALLOWED_OUTPUT_REL).resolve()
    with pytest.raises(ArtifactPathForbiddenError, match="unauthorized V4"):
        assert_v4_0_output_allowed(path)
