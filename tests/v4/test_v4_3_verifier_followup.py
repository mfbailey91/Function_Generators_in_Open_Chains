"""V4.3B adversarial verifier probes from the post-V4.3A review."""

from __future__ import annotations

import copy
import gzip
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from inequality_mechanisms.audits import v4_3_artifact as artifact
from inequality_mechanisms.audits.v4_artifact_guard import (
    V4_3_CORRECTIVE_OUTPUT_REL,
    canonical_v4_3_corrective_root,
    canonical_v4_3_followup_root,
)
from inequality_mechanisms.experiments.v4.intrinsic_static_wrench_config import (
    IntrinsicStaticWrenchConfig,
)
from inequality_mechanisms.metrics.static_wrench import directional_capacity


def _load_case_rows(case_id: str = "span_j1_095_j2_095") -> list[dict[str, Any]]:
    path = canonical_v4_3_corrective_root() / artifact.case_wrench_rel(case_id)
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream]


@pytest.fixture(scope="module")
def near_singular_row() -> dict[str, Any]:
    return next(row for row in _load_case_rows() if row["status"] == "near_singular")


@pytest.fixture(scope="module")
def regular_row() -> dict[str, Any]:
    return next(row for row in _load_case_rows() if row["status"] == "regular")


def test_committed_corrective_rows_still_pass_tightened_rules(
    near_singular_row: dict[str, Any], regular_row: dict[str, Any]
) -> None:
    artifact._validate_row(near_singular_row)
    artifact._validate_row(regular_row)


def test_collapsed_near_singular_polygon_is_rejected(
    near_singular_row: dict[str, Any],
) -> None:
    row = copy.deepcopy(near_singular_row)
    row["vertices"] = [[0.0, 0.0] for _ in range(4)]
    with pytest.raises(artifact.V4_3ArtifactError, match="distinct"):
        artifact._validate_row(row)


@pytest.mark.parametrize("scale", [0.5, 1.5])
def test_distinct_scaled_near_singular_polygon_is_rejected(
    near_singular_row: dict[str, Any], scale: float
) -> None:
    row = copy.deepcopy(near_singular_row)
    row["vertices"] = (np.asarray(row["vertices"]) * scale).tolist()
    with pytest.raises(artifact.V4_3ArtifactError, match="corner equality"):
        artifact._validate_row(row)


def test_rank_deficient_set_cannot_claim_closed_polygon(
    regular_row: dict[str, Any],
) -> None:
    row = next(
        row for row in _load_case_rows() if row["status"] == "unbounded_ideal_direction"
    )
    row["vertices"] = copy.deepcopy(regular_row["vertices"])
    row["vertex_feasibility"] = copy.deepcopy(regular_row["vertex_feasibility"])
    with pytest.raises(artifact.V4_3ArtifactError, match="rank-deficient.*polygon"):
        artifact._validate_row(row)


def test_tiny_nonbinding_projection_does_not_exempt_stable_ray() -> None:
    # A near-singular map can still have a well-constrained ray even when one
    # actuator has almost no projection onto it. The other actuator bounds it.
    a_map = np.array([[1e-12, 1e-12], [1.0, 0.0]])
    assert not artifact._ray_is_ill_conditioned(a_map, np.array([1.0, 0.0]))
    assert artifact._ray_is_ill_conditioned(a_map, np.array([0.0, 1.0]))


def test_well_conditioned_positive_x_unbounded_relabel_is_rejected(
    near_singular_row: dict[str, Any],
) -> None:
    row = copy.deepcopy(near_singular_row)
    assert row["directional_capacity"]["positive_x"] is not None
    row["directional_capacity"]["positive_x"] = None
    row["directional_fields"]["positive_x"].update(
        value=None, status="unbounded", reason="unbounded_ideal_direction"
    )
    with pytest.raises(artifact.V4_3ArtifactError, match="ray"):
        artifact._validate_row(row)


@pytest.mark.parametrize("claimed", [0.0, 1.0, 1e300])
def test_sensitive_radial_ray_rejects_arbitrary_finite_capacity(
    near_singular_row: dict[str, Any], claimed: float
) -> None:
    row = copy.deepcopy(near_singular_row)
    assert row["directional_capacity"]["radial"] > 1e10
    row["directional_capacity"]["radial"] = claimed
    row["directional_fields"]["radial"]["value"] = claimed
    with pytest.raises(artifact.V4_3ArtifactError, match="ray capacity"):
        artifact._validate_row(row)


@pytest.mark.parametrize("factor", [0.5, 2.0])
def test_sensitive_radial_ray_rejects_gross_factor_error(
    near_singular_row: dict[str, Any], factor: float
) -> None:
    row = copy.deepcopy(near_singular_row)
    claimed = factor * row["directional_capacity"]["radial"]
    row["directional_capacity"]["radial"] = claimed
    row["directional_fields"]["radial"]["value"] = claimed
    with pytest.raises(artifact.V4_3ArtifactError, match="projection interval"):
        artifact._validate_row(row)


def test_sensitive_but_certainly_active_radial_ray_cannot_claim_unbounded(
    near_singular_row: dict[str, Any],
) -> None:
    row = copy.deepcopy(near_singular_row)
    row["directional_capacity"]["radial"] = None
    row["directional_fields"]["radial"].update(
        value=None, status="unbounded", reason="unbounded_ideal_direction"
    )
    with pytest.raises(
        artifact.V4_3ArtifactError, match="finite ray capacity required"
    ):
        artifact._validate_row(row)


def test_sensitive_ray_rejects_coherently_rotated_named_direction(
    near_singular_row: dict[str, Any],
) -> None:
    row = copy.deepcopy(near_singular_row)
    original = np.asarray(row["direction_vectors"]["radial"])
    angle = 1e-13
    rotation = np.array(
        [[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]]
    )
    rotated = rotation @ original
    rotated /= np.linalg.norm(rotated)
    # This previously passed the 1e-12 named-vector comparison while changing
    # a cancellation-sensitive ray materially. Matching recomputed capacity
    # must not turn an altered named target into valid retained evidence.
    assert np.allclose(rotated, original, rtol=1e-12, atol=1e-12)
    capacity = directional_capacity(
        np.asarray(row["j_xu"]).T,
        np.asarray(row["torque_limits"]),
        rotated,
    )
    assert np.isfinite(capacity)
    assert abs(capacity / row["directional_capacity"]["radial"] - 1.0) > 1e-3
    row["direction_vectors"]["radial"] = rotated.tolist()
    row["directional_capacity"]["radial"] = capacity
    row["directional_fields"]["radial"]["value"] = capacity
    with pytest.raises(artifact.V4_3ArtifactError, match="named direction vector"):
        artifact._validate_row(row)


def test_cutoff_straddling_interval_keeps_only_bounded_transport_ambiguity() -> None:
    cutoff = artifact.DIRECTION_EPS
    a_map = np.array([[cutoff, 0.0], [0.0, 0.0]])
    tau = np.ones(2)
    direction = np.array([1.0, 0.0])
    check = artifact._validate_ray_capacity_interval
    # Both outcomes are possible within rounding of the unchanged strict
    # active cutoff. Any finite value must nevertheless stay near its scale.
    check(a_map, tau, direction, None, "unbounded")
    just_active = float(np.nextafter(cutoff, np.inf))
    check(a_map, tau, direction, 1.0 / just_active, "finite")
    for invalid in (0.0, 1.0, 1e30):
        with pytest.raises(artifact.V4_3ArtifactError, match="ray capacity"):
            check(a_map, tau, direction, invalid, "finite")


def test_ray_interval_enforces_provably_finite_or_unbounded_status() -> None:
    tau = np.ones(2)
    direction = np.array([1.0, 0.0])
    check = artifact._validate_ray_capacity_interval
    active = np.array([[1e-10, 0.0], [0.0, 0.0]])
    check(active, tau, direction, 1e10, "finite")
    with pytest.raises(
        artifact.V4_3ArtifactError, match="finite ray capacity required"
    ):
        check(active, tau, direction, None, "unbounded")
    inactive = np.array([[0.5e-12, 0.0], [0.0, 0.0]])
    check(inactive, tau, direction, None, "unbounded")
    with pytest.raises(artifact.V4_3ArtifactError, match="unbounded ray capacity"):
        check(inactive, tau, direction, 1e12, "finite")


@pytest.mark.parametrize("package", ["corrective", "followup"])
def test_all_retained_near_singular_rows_pass_bounded_ray_audit(package: str) -> None:
    root = (
        canonical_v4_3_corrective_root()
        if package == "corrective"
        else canonical_v4_3_followup_root()
    )
    n_near = 0
    for case_id in artifact.expected_case_ids():
        with gzip.open(root / artifact.case_wrench_rel(case_id), "rt") as stream:
            for line in stream:
                row = json.loads(line)
                if row["status"] == "near_singular":
                    artifact._validate_row(row)
                    n_near += 1
    assert n_near == 561


def test_impossible_negative_hrep_residual_is_rejected(
    regular_row: dict[str, Any],
) -> None:
    row = copy.deepcopy(regular_row)
    row["vertex_feasibility"]["max_hrep_residual"] = -100.0
    row["vertex_feasibility"]["details"]["hrep_residual_max"] = -100.0
    with pytest.raises(artifact.V4_3ArtifactError, match="impossibly negative"):
        artifact._validate_row(row)


def test_plausible_but_false_hrep_residual_is_rejected(
    regular_row: dict[str, Any],
) -> None:
    row = copy.deepcopy(regular_row)
    row["vertex_feasibility"]["max_hrep_residual"] = -0.5
    row["vertex_feasibility"]["details"]["hrep_residual_max"] = -0.5
    with pytest.raises(artifact.V4_3ArtifactError, match="residual.*retained vertices"):
        artifact._validate_row(row)


def test_plausible_but_false_corner_residual_is_rejected(
    near_singular_row: dict[str, Any],
) -> None:
    row = copy.deepcopy(near_singular_row)
    row["vertex_feasibility"]["max_corner_saturation_residual"] = 0.25
    row["vertex_feasibility"]["details"]["corner_saturation_residual_max"] = 0.25
    with pytest.raises(artifact.V4_3ArtifactError, match="residual.*retained vertices"):
        artifact._validate_row(row)


def test_near_roundoff_failure_remains_a_diagnostic(
    near_singular_row: dict[str, Any],
) -> None:
    assert not near_singular_row["vertex_feasibility"]["ok"]
    assert near_singular_row["vertex_feasibility"]["max_hrep_residual"] > 1e-9
    artifact._validate_row(near_singular_row)


def test_bow_tie_vertex_reorder_is_rejected(regular_row: dict[str, Any]) -> None:
    row = copy.deepcopy(regular_row)
    verts = np.asarray(row["vertices"], dtype=float)
    # Swap the last two vertices to create a self-intersecting order.
    bow_tie = verts[[0, 1, 3, 2]].tolist()
    row["vertices"] = bow_tie
    with pytest.raises(
        artifact.V4_3ArtifactError, match="inconsistent|self-intersecting|effort"
    ):
        artifact._validate_row(row)


def test_aggregate_vertex_diagnostics_separates_near_singular_failures() -> None:
    rows = _load_case_rows()
    summary = artifact.aggregate_vertex_diagnostics(rows)
    assert summary["vertex_diagnostic_failures_by_status"].get("regular", 0) == 0
    assert summary["vertex_diagnostic_failures_by_status"].get("near_singular", 0) > 0
    assert "max_corner_residual" in summary
    assert "max_hrep_residual" in summary


@pytest.fixture(scope="module")
def relocated_followup_packet(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("followup-verifier") / "downloaded-packet"
    shutil.copytree(canonical_v4_3_followup_root(), root)
    return root


def test_complete_followup_packet_keeps_profile_when_relocated(
    relocated_followup_packet: Path,
) -> None:
    summary = artifact.verify_v4_3_artifact(relocated_followup_packet)
    assert summary["verification_profile"] == "followup_v3"
    assert summary["n_rows"] == 55539
    assert summary["n_files"] == 325
    assert summary["files_digest"] == (
        "124d6c7b5701129d2f91a25dae2b6beabd546ba2498d11577b9d424a2b6cb7d6"
    )


def test_relocated_followup_still_requires_diagnostic_views(
    relocated_followup_packet: Path,
) -> None:
    root = relocated_followup_packet
    image_path = root / "cases/span_j1_095_j2_095/figures/positive_x_diagnostic.png"
    manifest_path = root / "manifest.json"
    original_image, original_manifest = (
        image_path.read_bytes(),
        manifest_path.read_bytes(),
    )
    try:
        image_path.unlink()
        manifest = json.loads(original_manifest)
        rel = image_path.relative_to(root).as_posix()
        manifest["files"] = [item for item in manifest["files"] if item["path"] != rel]
        manifest["files_digest"] = artifact.files_digest(manifest["files"])
        manifest_path.write_text(artifact.strict_json_dumps(manifest) + "\n")
        with pytest.raises(artifact.V4_3ArtifactError, match="missing required files"):
            artifact.verify_v4_3_artifact(root)
    finally:
        image_path.write_bytes(original_image)
        manifest_path.write_bytes(original_manifest)


def test_rehashed_followup_cannot_claim_historical_corrective_profile(
    relocated_followup_packet: Path,
) -> None:
    root = relocated_followup_packet
    config_path, manifest_path = root / "config_resolved.json", root / "manifest.json"
    original_config, original_manifest = (
        config_path.read_bytes(),
        manifest_path.read_bytes(),
    )
    try:
        resolved = json.loads(original_config)
        resolved["config"]["output_dir"] = V4_3_CORRECTIVE_OUTPUT_REL.as_posix()
        config = IntrinsicStaticWrenchConfig.model_validate(resolved["config"])
        resolved["config_digest"] = config.digest()
        config_path.write_text(artifact.strict_json_dumps(resolved) + "\n")
        manifest = json.loads(original_manifest)
        manifest["config_digest"] = config.digest()
        manifest["files"] = [
            artifact.inventory_file(root, "config_resolved.json")
            if item["path"] == "config_resolved.json"
            else item
            for item in manifest["files"]
        ]
        manifest["files_digest"] = artifact.files_digest(manifest["files"])
        manifest_path.write_text(artifact.strict_json_dumps(manifest) + "\n")
        with pytest.raises(artifact.V4_3ArtifactError, match="corrective_v2.*pinned"):
            artifact.verify_v4_3_artifact(root)
    finally:
        config_path.write_bytes(original_config)
        manifest_path.write_bytes(original_manifest)
