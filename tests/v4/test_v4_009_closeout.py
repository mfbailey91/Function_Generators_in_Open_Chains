"""V4-009 closeout: frozen V3 digests, kernel policy, and authorization reset."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from inequality_mechanisms.audits.v4_artifact_guard import (
    FROZEN_V3_REVIEW_PACKAGES,
    REPO_ROOT,
    V4_0_ALLOWED_OUTPUT_REL,
    ArtifactPathForbiddenError,
)
from inequality_mechanisms.core.robot import RobotModel
from inequality_mechanisms.transmission_geometry import (
    DifferentialSingularityError,
    KinematicTransmissionRobotModel,
    actuator_metric_on_q,
)
from inequality_mechanisms.transmission_geometry.errors import DifferentialShapeError

DIGEST_LOCK = Path(__file__).resolve().parent / "data" / "frozen_v3_review_digests.json"
KERNEL_DIR = REPO_ROOT / "src" / "inequality_mechanisms" / "transmission_geometry"
AUDIT_METRICS = REPO_ROOT / "src" / "inequality_mechanisms" / "audits" / "metrics.py"
ACTIVE_SPRINT = REPO_ROOT / "docs" / "software" / "planning" / "ACTIVE_SPRINT.md"
V4_README = REPO_ROOT / "docs" / "software" / "planning" / "sprints" / "v4" / "README.md"
SMOKE_ROOT = REPO_ROOT / V4_0_ALLOWED_OUTPUT_REL
PINV_PATHS = (
    *sorted(KERNEL_DIR.glob("*.py")),
    AUDIT_METRICS,
)
FROZEN_PACKAGE_KEYS = (
    "v3_5_closeout",
    "v3_6_free_space",
    "v3_6_free_space_v2",
    "v3_6b_planar2r_visual_audit",
    "v3_6c_planar2r_closeout",
    "v3_7_3r_free_space",
)


def _git_ls_files(*paths: str) -> list[str]:
    proc = subprocess.run(
        ["git", "ls-files", "-z", "--", *paths],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    if not proc.stdout:
        return []
    return [item.decode("utf-8") for item in proc.stdout.split(b"\0") if item]


def _digest_paths(rel_paths: list[str]) -> tuple[str, int]:
    digest = hashlib.sha256()
    for rel in sorted(rel_paths):
        payload = (REPO_ROOT / rel).read_bytes()
        file_hash = hashlib.sha256(payload).hexdigest()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest(), len(rel_paths)


def _package_digest(package: str) -> tuple[str, int]:
    prefix = f"results/v3_review/{package}/"
    paths = [rel for rel in _git_ls_files("results/v3_review") if rel.startswith(prefix)]
    return _digest_paths(paths)


def test_frozen_v3_review_digests_are_unchanged() -> None:
    lock = json.loads(DIGEST_LOCK.read_text(encoding="utf-8"))
    assert lock["schema_version"] == "v4.0.frozen_v3_review_digests.v1"
    expected = lock["packages"]
    for package in FROZEN_PACKAGE_KEYS:
        sha, n_files = _package_digest(package)
        record = expected[package]
        assert n_files == record["n_files"], package
        assert sha == record["sha256"], package
    root_paths = [
        rel
        for rel in _git_ls_files("results/v3_review")
        if rel.count("/") == 2
    ]
    sha, n_files = _digest_paths(root_paths)
    root = expected["_v3_review_root"]
    assert n_files == root["n_files"]
    assert sha == root["sha256"]
    assert FROZEN_V3_REVIEW_PACKAGES == frozenset(FROZEN_PACKAGE_KEYS)


def test_inverse_metric_sources_do_not_use_pinv() -> None:
    for path in PINV_PATHS:
        source = path.read_text(encoding="utf-8")
        assert "pinv" not in source, path


def test_singular_metric_raises_typed_singularity() -> None:
    j_g = [[1.0, 0.0], [0.0, 0.0]]
    with pytest.raises(DifferentialSingularityError) as info:
        actuator_metric_on_q(j_g)
    assert info.value.failure_code == "transmission_rank_deficient"
    assert info.value.operation == "actuator_metric_on_q"


def test_nonfinite_jacobian_uses_shape_failure_code() -> None:
    with pytest.raises(DifferentialShapeError) as info:
        actuator_metric_on_q([[float("nan"), 0.0], [0.0, 1.0]])
    assert info.value.failure_code == "nonfinite_differential"


def test_v4_protocol_extends_robot_model_without_widening_v3() -> None:
    assert RobotModel in KinematicTransmissionRobotModel.__bases__
    assert "jacobian_q_to_x" in RobotModel.__dict__
    assert "jacobian_u_to_q" not in RobotModel.__dict__
    assert "jacobian_u_to_q" in KinematicTransmissionRobotModel.__dict__


def test_v4_0_smoke_package_is_non_inferential() -> None:
    manifest = json.loads((SMOKE_ROOT / "manifest.json").read_text(encoding="utf-8"))
    html = (SMOKE_ROOT / "index.html").read_text(encoding="utf-8")
    statement = "geometry-core verification; no mechanism performance inference."
    assert manifest["no_inference_statement"] == statement
    assert statement in html
    assert (SMOKE_ROOT / "geometry_samples.jsonl").is_file()
    assert (SMOKE_ROOT / "identity_residuals.json").is_file()


def test_v4_0_closeout_did_not_auto_authorize_later_columns() -> None:
    closeout = (
        REPO_ROOT
        / "docs"
        / "software"
        / "architecture"
        / "notes"
        / "V4_0_KINEMATIC_GEOMETRY_CORE_CLOSEOUT.md"
    ).read_text(encoding="utf-8")
    active = ACTIVE_SPRINT.read_text(encoding="utf-8")
    v4_readme = V4_README.read_text(encoding="utf-8")
    assert "V4.0 completion does not authorize later sprints" in closeout
    assert "**Code authorization:** none" in active
    assert "V4.2" in active
    assert "no code authorization" in active.lower()
    assert "completed" in v4_readme.lower()
    assert "V4-200" not in active


def test_v4_1_output_remains_forbidden_to_v4_0_writer() -> None:
    path = (REPO_ROOT / "results" / "v4_review" / "v4_1_planar2r_geometry_atlas").resolve()
    with pytest.raises(ArtifactPathForbiddenError, match="unauthorized V4"):
        from inequality_mechanisms.audits.v4_artifact_guard import (
            assert_v4_0_output_allowed,
        )

        assert_v4_0_output_allowed(path)
