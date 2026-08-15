"""V4-000 artifact guard and planning-contract invariants."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from inequality_mechanisms.audits.artifact_freeze import FROZEN_EXPLICIT_PACKAGES
from inequality_mechanisms.audits import v4_artifact_guard
from inequality_mechanisms.audits.v4_artifact_guard import (
    FROZEN_V3_CLOSEOUT_PACKAGES,
    FROZEN_V3_REVIEW_PACKAGES,
    REPO_ROOT,
    V4_0_ALLOWED_OUTPUT_REL,
    V4_0_ALLOWED_PACKAGE,
    ArtifactPathForbiddenError,
    assert_v4_0_output_allowed,
    prepare_v4_0_output_dir,
)

PLANNING_CONTRACTS = (
    REPO_ROOT / "docs" / "software" / "architecture" / "adr" / "ADR-027-v4-kinematic-transmission-geometry.md",
    REPO_ROOT / "docs" / "software" / "V4_PROJECT_PLAN.md",
    REPO_ROOT
    / "docs"
    / "software"
    / "planning"
    / "sprints"
    / "v4"
    / "SPRINT_V4_0_KINEMATIC_GEOMETRY_CORE.md",
)


def _fake_runner_write_manifest(output: Path) -> Path:
    resolved = prepare_v4_0_output_dir(output)
    manifest = resolved / "manifest.json"
    manifest.write_text(json.dumps({"status": "generated"}), encoding="utf-8")
    return manifest


def test_allowed_v4_0_path_succeeds():
    root = (REPO_ROOT / V4_0_ALLOWED_OUTPUT_REL).resolve()
    assert assert_v4_0_output_allowed(root) == root
    child = root / "geometry_samples.jsonl"
    assert assert_v4_0_output_allowed(child) == child.resolve()


def test_failure_code_is_artifact_path_forbidden():
    assert ArtifactPathForbiddenError.failure_code == "artifact_path_forbidden"


@pytest.mark.parametrize(
    "package",
    sorted(FROZEN_V3_REVIEW_PACKAGES),
)
def test_frozen_v3_packages_raise(package: str):
    assert package in FROZEN_EXPLICIT_PACKAGES or package in FROZEN_V3_CLOSEOUT_PACKAGES
    path = (REPO_ROOT / "results" / "v3_review" / package).resolve()
    with pytest.raises(ArtifactPathForbiddenError, match="frozen V3"):
        assert_v4_0_output_allowed(path)
    nested = path / "summary.json"
    with pytest.raises(ArtifactPathForbiddenError, match="frozen V3"):
        assert_v4_0_output_allowed(nested)


def test_v3_review_root_is_forbidden():
    path = (REPO_ROOT / "results" / "v3_review").resolve()
    with pytest.raises(ArtifactPathForbiddenError, match="frozen V3"):
        assert_v4_0_output_allowed(path)


@pytest.mark.parametrize(
    "package",
    [
        "v4_1_planar2r_geometry_atlas",
        "v4_2_differential_ik_velocity",
        "v4_7_closeout",
    ],
)
def test_unauthorized_v4_packages_raise(package: str):
    path = (REPO_ROOT / "results" / "v4_review" / package).resolve()
    with pytest.raises(ArtifactPathForbiddenError, match="unauthorized V4"):
        assert_v4_0_output_allowed(path)


def test_prepare_v4_0_output_dir_creates_clean_tree(tmp_path, monkeypatch):
    monkeypatch.setattr(v4_artifact_guard, "REPO_ROOT", tmp_path)
    allowed = tmp_path / "results" / "v4_review" / V4_0_ALLOWED_PACKAGE
    assert not allowed.exists()
    created = v4_artifact_guard.prepare_v4_0_output_dir(allowed)
    assert created == allowed.resolve()
    assert created.is_dir()
    assert created.exists()


def test_future_runner_refuses_frozen_v3_and_writes_no_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(v4_artifact_guard, "REPO_ROOT", tmp_path)
    forbidden = tmp_path / "results" / "v3_review" / "v3_6_free_space_v2"
    forbidden.mkdir(parents=True)
    with pytest.raises(ArtifactPathForbiddenError, match="frozen V3"):
        _fake_runner_write_manifest(forbidden)
    assert not (forbidden / "manifest.json").exists()


def test_future_runner_writes_manifest_on_allowed_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(v4_artifact_guard, "REPO_ROOT", tmp_path)
    allowed = tmp_path / "results" / "v4_review" / V4_0_ALLOWED_PACKAGE
    manifest = _fake_runner_write_manifest(allowed)
    assert manifest.is_file()
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["status"] == "generated"


def test_planning_contracts_exist():
    missing = [str(path) for path in PLANNING_CONTRACTS if not path.is_file()]
    assert missing == []
    sprint = PLANNING_CONTRACTS[-1].read_text(encoding="utf-8")
    assert "V4-000" in sprint
    assert "results/v4_review/v4_0_kinematic_geometry_core/" in sprint
