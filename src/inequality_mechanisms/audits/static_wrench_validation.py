"""V3.6E gravity-free static-wrench validation artifact (math fixtures)."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from inequality_mechanisms.adapters import planar_2r_operating_branch_robot
from inequality_mechanisms.audits.v3_span_wrench_guard import (
    V3_6E_ALLOWED_PACKAGE,
    assert_v3_6e_output_allowed,
    prepare_v3_6e_output_dir,
)
from inequality_mechanisms.experiments.span_cases import realize_supported_cases
from inequality_mechanisms.experiments.span_wrench_config import DEFAULT_CONFIG_REL
from inequality_mechanisms.kinematics.planar_2r import Planar2R
from inequality_mechanisms.mechanisms import (
    fixed_ratio_gearbox_branch,
    unit_gearbox_branch,
)
from inequality_mechanisms.mechanisms.span_registry import load_span_registry
from inequality_mechanisms.metrics.static_wrench import (
    DEFAULT_TORQUE_LIMITS,
    NEAR_SINGULAR_CONDITION,
    SCHEMA_VERSION,
    WrenchStateStatus,
    directional_capacity,
    isotropic_radius,
    reject_unsupported_physics,
    static_wrench_at_state,
    static_wrench_from_maps,
    static_wrench_from_snapshot,
)
from inequality_mechanisms.transmission_geometry import geometry_snapshot, pullback_covector

D_REGISTRY = Path("results") / "v3_review" / "v3_6d_span_corpus" / "registry.json"
PLANAR = Planar2R(L1=1.0, L2=1.0)
RNG_SEED = 669
N_RANDOM = 32


def _git_revision() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def _write_json(path: Path, payload: Any) -> str:
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    data = text.encode("utf-8")
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _identity_robot():
    branch = unit_gearbox_branch(2, input_lower=[-2.0, -2.0], input_upper=[2.0, 2.0])
    return planar_2r_operating_branch_robot(branch, planar_fk=PLANAR)


def _ratio_robot():
    branch = fixed_ratio_gearbox_branch(
        [2.0, 0.5],
        input_lower=[-2.0, -2.0],
        input_upper=[2.0, 2.0],
    )
    return planar_2r_operating_branch_robot(branch, planar_fk=PLANAR)


def _analytic_identity() -> dict[str, Any]:
    robot = _identity_robot()
    state = robot.state_from_input([0.0, np.pi / 2])
    cap = static_wrench_at_state(robot, state)
    a_map = np.asarray(cap.j_xu).T
    return {
        "mechanism": "identity_gearbox",
        "q": cap.to_dict()["q"],
        "x": cap.to_dict()["x"],
        "status": cap.status.value,
        "rank": cap.rank,
        "isotropic_radius": cap.isotropic_radius,
        "vertices": None if cap.vertices is None else cap.vertices.tolist(),
        "analytic_r_iso": isotropic_radius(a_map, cap.torque_limits),
        "joint_torque_amplification": list(cap.joint_torque_amplification),
    }


def _analytic_constant_gear() -> dict[str, Any]:
    robot = _ratio_robot()
    state = robot.state_from_input([0.0, np.pi / 2])
    cap = static_wrench_at_state(robot, state)
    return {
        "mechanism": "constant_gear_2_0p5",
        "q": cap.to_dict()["q"],
        "status": cap.status.value,
        "rank": cap.rank,
        "isotropic_radius": cap.isotropic_radius,
        "vertices": None if cap.vertices is None else cap.vertices.tolist(),
        "joint_torque_amplification": list(cap.joint_torque_amplification),
    }


def _random_summary() -> dict[str, Any]:
    rng = np.random.default_rng(RNG_SEED)
    robot = _identity_robot()
    residuals = []
    saturations = []
    for _ in range(N_RANDOM):
        u = rng.uniform(-0.8, 0.8, size=2)
        u[1] = float(np.clip(u[1], 0.25, 0.8))  # keep J_f regular
        state = robot.state_from_input(u)
        snap = geometry_snapshot(robot, state)
        cap = static_wrench_from_snapshot(snap)
        force = rng.normal(size=2)
        tau = pullback_covector(cap.j_xu, force)
        residuals.append(float(np.max(np.abs(tau - cap.j_xu.T @ force))))
        if cap.vertices is None:
            continue
        a_map = cap.j_xu.T
        sat = np.abs(a_map @ cap.vertices.T)
        saturations.append(float(np.max(np.abs(sat - cap.torque_limits[:, None]))))
    return {
        "n_random": N_RANDOM,
        "seed": RNG_SEED,
        "max_virtual_work_residual": max(residuals) if residuals else None,
        "max_vertex_torque_residual": max(saturations) if saturations else None,
    }


def _singularity_fixtures() -> dict[str, Any]:
    robot = _identity_robot()
    stretched = static_wrench_at_state(robot, robot.state_from_input([0.3, 0.0]))
    folded_q = np.array([0.0, 0.0], dtype=np.float64)
    invalid = static_wrench_from_maps(
        q=folded_q,
        u=folded_q,
        x=np.array([2.0, 0.0]),
        j_g=np.eye(2),
        j_f=np.array([[0.0, 0.0], [0.0, 0.0]]),
        j_xu=np.zeros((2, 2)),
        named_directions={"positive_x": np.array([1.0, 0.0]), "positive_y": np.array([0.0, 1.0])},
    )
    origin = static_wrench_from_maps(
        q=np.array([0.0, np.pi]),
        u=np.array([0.0, np.pi]),
        x=np.array([0.0, 0.0]),
        j_g=np.eye(2),
        j_f=np.array([[0.0, 0.0], [1.0, 1.0]]),
        j_xu=np.array([[0.0, 0.0], [1.0, 1.0]]),
    )
    return {
        "manipulator_stretched": stretched.to_dict(),
        "zero_composite": invalid.to_dict(),
        "rank1_unbounded": origin.to_dict(),
        "near_singular_threshold": NEAR_SINGULAR_CONDITION,
        "statuses": {
            "stretched": stretched.status.value,
            "zero": invalid.status.value,
            "rank1": origin.status.value,
        },
    }


def _span_family_interior() -> dict[str, Any]:
    payload = json.loads(D_REGISTRY.read_text(encoding="utf-8"))
    registry = load_span_registry(payload)
    realized = realize_supported_cases(registry)
    rows: list[dict[str, Any]] = []
    for case in realized:
        for name, branch in (("fourbar", case.fourbar), ("gearbox", case.gearbox)):
            robot = planar_2r_operating_branch_robot(branch, planar_fk=PLANAR)
            lo = np.asarray(branch.certificate.input_lower, dtype=np.float64)
            hi = np.asarray(branch.certificate.input_upper, dtype=np.float64)
            u = 0.5 * (lo + hi)
            cap = static_wrench_at_state(robot, robot.state_from_input(u))
            rows.append(
                {
                    "case_id": case.case.case_id,
                    "mechanism": name,
                    "j1_status": case.j1.status,
                    "j2_status": case.j2.status,
                    "status": cap.status.value,
                    "rank": cap.rank,
                    "isotropic_radius": cap.isotropic_radius,
                    "rank_attribution": dict(cap.rank_attribution),
                }
            )
    return {
        "n_realized_cases": len(realized),
        "n_interior_evaluations": len(rows),
        "rows": rows,
    }


def export_static_wrench_core(*, output: Path | None = None) -> Path:
    """Write analytic fixtures, random summaries, and span-family checks."""
    reject_unsupported_physics(None)
    target = output
    if target is None:
        target = Path("results") / "v3_review" / V3_6E_ALLOWED_PACKAGE
    root = prepare_v3_6e_output_dir(assert_v3_6e_output_allowed(target))
    files: dict[str, str] = {}
    files["analytic_fixtures.json"] = _write_json(
        root / "analytic_fixtures.json",
        {
            "schema_version": SCHEMA_VERSION,
            "torque_limits": list(DEFAULT_TORQUE_LIMITS),
            "identity": _analytic_identity(),
            "constant_gear": _analytic_constant_gear(),
        },
    )
    files["random_test_summary.json"] = _write_json(
        root / "random_test_summary.json",
        _random_summary(),
    )
    files["singularity_fixtures.json"] = _write_json(
        root / "singularity_fixtures.json",
        _singularity_fixtures(),
    )
    files["span_family_interior.json"] = _write_json(
        root / "span_family_interior.json",
        _span_family_interior(),
    )
    files["tolerances.json"] = _write_json(
        root / "tolerances.json",
        {
            "schema_version": SCHEMA_VERSION,
            "near_singular_condition": NEAR_SINGULAR_CONDITION,
            "direction_eps": 1e-12,
            "vertex_hrep_atol": 1e-9,
            "virtual_work_atol": 1e-12,
            "finite_difference_step": 1e-6,
            "angular_sample_count": 720,
        },
    )
    gravity_rejected = False
    try:
        reject_unsupported_physics({"gravity_vector": [0.0, -9.81]})
    except Exception as exc:  # noqa: BLE001
        gravity_rejected = "gravity" in str(exc).lower()
    files["schema.json"] = _write_json(
        root / "schema.json",
        {
            "schema_version": SCHEMA_VERSION,
            "config": str(DEFAULT_CONFIG_REL),
            "gravity_fields_rejected": gravity_rejected,
            "kernel": "v4.0.transmission_geometry",
            "html": False,
        },
    )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_revision": _git_revision(),
        "package": V3_6E_ALLOWED_PACKAGE,
        "files": files,
        "no_inference": "gravity-free static wrench math fixtures; no mechanism ranking.",
    }
    files["manifest.json"] = _write_json(root / "manifest.json", manifest)
    manifest["files"] = files
    _write_json(root / "manifest.json", manifest)
    (root / "README.md").write_text(
        "# V3.6E gravity-free static wrench core\n\n"
        "Math fixtures only. No HTML atlas. Consumes V4.0 snapshots. "
        "Not Sprint V4.3.\n",
        encoding="utf-8",
    )
    return root
