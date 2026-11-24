"""Frozen V4-405 Cartesian tracking task/integration contract (no runner)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from inequality_mechanisms.audits.v4_4_artifact import (
    POLICIES,
    RATE_POLICIES,
    V4_4ArtifactError,
    read_json_text,
    strict_json,
)
from inequality_mechanisms.experiments.v4.intrinsic_static_wrench_config import (
    FROZEN_MECHANISM_IDS,
    SourceLock,
)

CANONICAL_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CONTRACT_REL = Path("configs/v4/velocity_tracking_contract_v1.json")
CONTRACT_SCHEMA = "v4.4.velocity.tracking.contract.v1"
RESERVED_PACKAGE = "v4_4_velocity_tracking_smoke"
RESERVED_OUTPUT_REL = Path("results/v4_review") / RESERVED_PACKAGE

PATH_IDS = ("axis_x", "axis_y", "diagonal", "circle_ccw")
FAILURE_CODES = (
    "ok",
    "start_unavailable",
    "snapshot_invalid",
    "path_undefined",
    "integration_nonfinite",
    "domain_boundary_exit",
    "exact_unavailable",
    "transmission_rank_deficient",
    "rate_infeasible_report_only",
    "task_ineligible",
    "refinement_diverged",
)
DECLARED_METRICS = (
    "rms_cartesian_error",
    "peak_cartesian_error",
    "peak_rate_utilization",
    "residual_norm_before_scale",
    "residual_norm_after_scale",
    "command_continuity_max_delta_u_dot",
    "failure_code",
)
DAMPING_SWEEP = (0.01, 0.05, 0.2)
TASK_DURATION = 1.0
BASE_DT = 0.01
REFINEMENT_DT = (0.005, 0.0025)
FEEDBACK_GAIN = 5.0
INITIAL_ACTUATOR_RATE = (0.0, 0.0)


def default_tracking_contract() -> dict[str, Any]:
    """Return the frozen V4-405 contract payload."""
    return {
        "schema_version": CONTRACT_SCHEMA,
        "package": RESERVED_PACKAGE,
        "output_dir": RESERVED_OUTPUT_REL.as_posix(),
        "adr": "ADR-034",
        "source": SourceLock().model_dump(mode="json"),
        "mechanisms": list(FROZEN_MECHANISM_IDS),
        "paths": {
            "ids": list(PATH_IDS),
            "coordinate_frame": "mounted_x",
            "scale_rule": "isotropic_speed_times_duration",
            "duration": TASK_DURATION,
            "definitions": {
                "axis_x": {"kind": "segment", "direction": [1.0, 0.0]},
                "axis_y": {"kind": "segment", "direction": [0.0, 1.0]},
                "diagonal": {
                    "kind": "segment",
                    "direction": [0.7071067811865476, 0.7071067811865476],
                },
                "circle_ccw": {"kind": "circle", "orientation": "ccw"},
            },
        },
        "start": {
            "match": "exact_retained_identity",
            "require_shared_physical_qx": True,
            "initial_actuator_rate": list(INITIAL_ACTUATOR_RATE),
        },
        "timing": {
            "duration": TASK_DURATION,
            "dt": BASE_DT,
            "refinement_dt": list(REFINEMENT_DT),
            "integrator": "explicit_euler_actuator_rate",
            "achieved_velocity_map": "raw_stored_j_xu",
        },
        "control": {
            "feedforward": "path_derivative",
            "feedback": "proportional_cartesian",
            "kp": FEEDBACK_GAIN,
            "request": "v_ff_plus_v_fb",
        },
        "inverse": {
            "ik_policies": list(POLICIES),
            "rate_policies": list(RATE_POLICIES),
            "actuator_weight": [[1.0, 0.0], [0.0, 1.0]],
            "damping_sweep": list(DAMPING_SWEEP),
            "rate_limits": [1.0, 1.0],
            "rate_units": "normalized_actuator_coordinate_rate",
            "velocity_units": "length_per_normalized_time",
        },
        "domain_boundary": {
            "policy": "typed_terminal_failure",
            "silent_clipping": False,
            "certified_box": "mounted_q",
        },
        "failure_codes": list(FAILURE_CODES),
        "declared_metrics": list(DECLARED_METRICS),
        "sweep": {
            "mode": "documented_factorial",
            "ik_policies": list(POLICIES),
            "rate_policies": list(RATE_POLICIES),
            "damping_sweep": list(DAMPING_SWEEP),
            "damping_applies_to": ["damped_least_squares"],
            "first_smoke_may_subset_with_selection_record": True,
        },
        "v4_405_forbids_writing_output_dir": True,
        "no_inference_statement": (
            "V4-405 freezes the Cartesian tracking task/integration contract only. "
            "No runner, tracking evidence, motor rating, or temporal claim is made "
            "from instantaneous smoke or atlas cells."
        ),
    }


def contract_path(path: Path | None = None) -> Path:
    if path is None:
        return CANONICAL_REPO_ROOT / DEFAULT_CONTRACT_REL
    return Path(path)


def load_tracking_contract(path: Path | None = None) -> dict[str, Any]:
    """Require an exact match to the frozen tracking contract."""
    source = contract_path(path)
    payload = read_json_text(source.read_text(encoding="utf-8"))
    expected = default_tracking_contract()
    if strict_json(payload) != strict_json(expected):
        raise V4_4ArtifactError(
            "V4.4 tracking contract must match the frozen ADR-034 contract"
        )
    validate_tracking_contract(expected)
    return expected


def validate_tracking_contract(contract: Mapping[str, Any]) -> None:
    """Fail closed on structural contract violations."""
    if contract.get("schema_version") != CONTRACT_SCHEMA:
        raise V4_4ArtifactError("tracking contract schema mismatch")
    if contract.get("package") != RESERVED_PACKAGE:
        raise V4_4ArtifactError("tracking package id mismatch")
    if contract.get("output_dir") != RESERVED_OUTPUT_REL.as_posix():
        raise V4_4ArtifactError("reserved tracking output_dir mismatch")
    if contract.get("v4_405_forbids_writing_output_dir") is not True:
        raise V4_4ArtifactError("V4-405 must forbid writing the reserved root")
    paths = contract.get("paths")
    if not isinstance(paths, Mapping):
        raise V4_4ArtifactError("paths block required")
    ids = tuple(paths.get("ids") or ())
    if ids != PATH_IDS:
        raise V4_4ArtifactError("path ids must match the frozen task bank")
    definitions = paths.get("definitions")
    if not isinstance(definitions, Mapping) or set(definitions) != set(PATH_IDS):
        raise V4_4ArtifactError("path definitions must cover every path id")
    duration = paths.get("duration")
    if not isinstance(duration, (int, float)) or float(duration) != TASK_DURATION:
        raise V4_4ArtifactError("path duration mismatch")
    timing = contract.get("timing")
    if not isinstance(timing, Mapping):
        raise V4_4ArtifactError("timing block required")
    dt = timing.get("dt")
    if not isinstance(dt, (int, float)) or float(dt) != BASE_DT:
        raise V4_4ArtifactError("base dt mismatch")
    if tuple(timing.get("refinement_dt") or ()) != REFINEMENT_DT:
        raise V4_4ArtifactError("refinement dt mismatch")
    if timing.get("integrator") != "explicit_euler_actuator_rate":
        raise V4_4ArtifactError("integrator must be explicit Euler on actuator rates")
    control = contract.get("control")
    if not isinstance(control, Mapping):
        raise V4_4ArtifactError("control block required")
    kp = control.get("kp")
    if not isinstance(kp, (int, float)) or float(kp) != FEEDBACK_GAIN:
        raise V4_4ArtifactError("feedback gain mismatch")
    inverse = contract.get("inverse")
    if not isinstance(inverse, Mapping):
        raise V4_4ArtifactError("inverse block required")
    if tuple(inverse.get("ik_policies") or ()) != POLICIES:
        raise V4_4ArtifactError("ik_policies mismatch")
    if tuple(inverse.get("rate_policies") or ()) != RATE_POLICIES:
        raise V4_4ArtifactError("rate_policies mismatch")
    if tuple(inverse.get("damping_sweep") or ()) != DAMPING_SWEEP:
        raise V4_4ArtifactError("damping_sweep mismatch")
    if tuple(contract.get("failure_codes") or ()) != FAILURE_CODES:
        raise V4_4ArtifactError("failure_codes catalog mismatch")
    if tuple(contract.get("declared_metrics") or ()) != DECLARED_METRICS:
        raise V4_4ArtifactError("declared_metrics mismatch")
    if list(contract.get("mechanisms") or []) != list(FROZEN_MECHANISM_IDS):
        raise V4_4ArtifactError("mechanisms mismatch")
    SourceLock(**contract["source"])


def documented_factorial_size(contract: Mapping[str, Any] | None = None) -> int:
    """Count documented sweep combinations (DLS × damping; others × one null)."""
    payload = default_tracking_contract() if contract is None else contract
    inverse = payload["inverse"]
    n = 0
    for policy in inverse["ik_policies"]:
        dampings: Sequence[float | None]
        if policy == "damped_least_squares":
            dampings = list(inverse["damping_sweep"])
        else:
            dampings = [None]
        for _damping in dampings:
            for _rate in inverse["rate_policies"]:
                n += 1
    return n


def assert_no_tracking_generator_entrypoint(repo_root: Path | None = None) -> None:
    """V4-405 forbids a production tracking generate script."""
    root = CANONICAL_REPO_ROOT if repo_root is None else Path(repo_root)
    forbidden = (
        root / "scripts" / "generate_v4_4_velocity_tracking.py",
        root / "scripts" / "generate_v4_4_tracking_smoke.py",
    )
    existing = [path for path in forbidden if path.exists()]
    if existing:
        raise V4_4ArtifactError(
            "V4-405 forbids tracking generator entrypoints: "
            + ", ".join(path.name for path in existing)
        )


__all__ = [
    "BASE_DT",
    "CANONICAL_REPO_ROOT",
    "CONTRACT_SCHEMA",
    "DAMPING_SWEEP",
    "DECLARED_METRICS",
    "DEFAULT_CONTRACT_REL",
    "FAILURE_CODES",
    "FEEDBACK_GAIN",
    "PATH_IDS",
    "REFINEMENT_DT",
    "RESERVED_OUTPUT_REL",
    "RESERVED_PACKAGE",
    "TASK_DURATION",
    "assert_no_tracking_generator_entrypoint",
    "contract_path",
    "default_tracking_contract",
    "documented_factorial_size",
    "load_tracking_contract",
    "validate_tracking_contract",
]
