"""Frozen common-physical span task bank (V4.2B / V4-226 bank freeze).

Author starts and witness goals in the exact intersection of all 17 mounted
usable Q boxes, then map them through identity planar-2R FK to X-space disks.
The bank is preflighted on every mounted four-bar/gearbox pair before its
digest is frozen. Planner outcomes are not computed here.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from numpy.typing import NDArray

from inequality_mechanisms.adapters.planar_2r_robot import (
    planar_2r_operating_branch_robot,
)
from inequality_mechanisms.audits.v4_artifact_guard import CANONICAL_REPO_ROOT
from inequality_mechanisms.benchmarks.smoke_sampling_2r import SamplingSmokeArm
from inequality_mechanisms.experiments.span_cases import (
    RealizedSpanCase,
    generate_span_cases,
    realize_mounted_span_case,
)
from inequality_mechanisms.experiments.v4.span_controlled_atlas_config import (
    FROZEN_V3_6D_DIGEST,
    FROZEN_V3_6D_REGISTRY_REL,
)
from inequality_mechanisms.kinematics.planar_2r import Planar2R
from inequality_mechanisms.mechanisms.span_registry import SpanRegistry, load_span_registry

BANK_ID = "common_physical_span_bank_v1"
SCHEMA_VERSION = "v4.2b.common_physical_span_bank.v1"
GENERATOR_VERSION = "v4.2b.common_physical_span_bank.v1"
DEFAULT_BANK_REL = Path("configs") / "v4" / "span_common_physical_planar2r_v1.json"
FROZEN_TASK_IDS = (
    "near_0",
    "near_1",
    "near_2",
    "near_3",
    "near_4",
    "far_0",
    "far_1",
    "far_2",
    "far_3",
    "far_4",
)
FROZEN_SEED = 7
INSET_FRACTION = 0.10
NEAR_OFFSET_FRACTION = 0.35
NEAR_STEP_FRACTION = 0.10
FAR_OFFSET_FRACTION = 0.70
# The common-box midpoint has q2=0 (fully stretched). Disk octants around
# that pose leave the reachable workspace, so authoring uses a strictly
# interior positive-elbow rectangle inside the inset box.
WORKING_Q2_LOWER_FRACTION = 0.70
WORKING_Q2_UPPER_FRACTION = 0.95
GOAL_RADIUS = 0.05
PLANAR_L1 = 1.0
PLANAR_L2 = 1.0
FK_ATOL = 1e-9
BOUNDARY_ANGLES_DEG = (0.0, 45.0, 90.0, 135.0, 180.0, 225.0, 270.0, 315.0)
BOUNDARY_RADIUS_FRACTION = 0.98
GOAL_REPRESENTATION_KIND = "center_plus_near_boundary_octants_v1"
RESIDUAL_POLICY = "cartesian_disk"
ARMS = ("fourbar", "gearbox")


class CommonPhysicalBankError(ValueError):
    """Raised when the common-physical bank cannot be frozen."""

    failure_code = "common_physical_bank_failed"


def _as_q2(values: Any) -> NDArray[np.float64]:
    arr = np.asarray(values, dtype=np.float64)
    if arr.shape != (2,) or not np.all(np.isfinite(arr)):
        raise CommonPhysicalBankError(f"expected finite q/x of shape (2,), got {arr}")
    return arr.copy()


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def bank_digest(payload: Mapping[str, Any]) -> str:
    """SHA-256 of the bank body, excluding the digest field itself."""
    body = {key: value for key, value in payload.items() if key != "sha256"}
    return hashlib.sha256(_canonical_json(body).encode("utf-8")).hexdigest()


def load_frozen_v3_6d_registry(*, repo_root: Path | None = None) -> SpanRegistry:
    """Load the committed V3.6D registry without calling synthesis."""
    root = CANONICAL_REPO_ROOT if repo_root is None else Path(repo_root)
    path = root / FROZEN_V3_6D_REGISTRY_REL
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CommonPhysicalBankError(f"missing frozen V3.6D registry at {path}") from exc
    except json.JSONDecodeError as exc:
        raise CommonPhysicalBankError(f"invalid V3.6D registry JSON at {path}: {exc}") from exc
    registry = load_span_registry(payload)
    if registry.sha256 != FROZEN_V3_6D_DIGEST:
        raise CommonPhysicalBankError(
            "V3.6D registry digest mismatch: "
            f"file={registry.sha256} lock={FROZEN_V3_6D_DIGEST}"
        )
    return registry


def _sampling_arms(realized: RealizedSpanCase, *, fk: Planar2R) -> dict[str, SamplingSmokeArm]:
    return {
        "fourbar": SamplingSmokeArm(
            name="fourbar",
            branch=realized.fourbar,
            robot=planar_2r_operating_branch_robot(realized.fourbar, planar_fk=fk),
        ),
        "gearbox": SamplingSmokeArm(
            name="gearbox",
            branch=realized.gearbox,
            robot=planar_2r_operating_branch_robot(realized.gearbox, planar_fk=fk),
        ),
    }


def common_mounted_q_box(
    realized_cases: tuple[RealizedSpanCase, ...],
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return the axis-wise intersection of mounted usable Q boxes."""
    if not realized_cases:
        raise CommonPhysicalBankError("need at least one mounted span case")
    lower = np.full(2, -np.inf, dtype=np.float64)
    upper = np.full(2, np.inf, dtype=np.float64)
    for realized in realized_cases:
        cert = realized.fourbar.certificate
        gb = realized.gearbox.certificate
        for branch_cert in (cert, gb):
            lo = np.asarray(branch_cert.output_lower, dtype=np.float64)
            hi = np.asarray(branch_cert.output_upper, dtype=np.float64)
            if lo.shape != (2,) or hi.shape != (2,):
                raise CommonPhysicalBankError("mounted output bounds must have shape (2,)")
            lower = np.maximum(lower, lo)
            upper = np.minimum(upper, hi)
        for axis, (label, row) in enumerate(
            (("J1", realized.j1), ("J2", realized.j2))
        ):
            if row.range_definition is None:
                raise CommonPhysicalBankError(
                    f"{label} span {row.target_span_deg} must record a range definition"
                )
            usable = row.range_definition.usable_interval_rad
            if abs(float(cert.output_lower[axis]) - float(usable[0])) > FK_ATOL:
                raise CommonPhysicalBankError(
                    f"{realized.case.case_id} {label} mounted lower disagrees with registry"
                )
            if abs(float(cert.output_upper[axis]) - float(usable[1])) > FK_ATOL:
                raise CommonPhysicalBankError(
                    f"{realized.case.case_id} {label} mounted upper disagrees with registry"
                )
    if not np.all(np.isfinite(lower)) or not np.all(np.isfinite(upper)):
        raise CommonPhysicalBankError("common mounted Q box is not finite")
    if np.any(upper <= lower):
        raise CommonPhysicalBankError("common mounted Q box is empty")
    return lower, upper


def inset_q_box(
    lower: NDArray[np.float64],
    upper: NDArray[np.float64],
    *,
    inset_fraction: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Shrink a closed Q box by ``inset_fraction`` of each axis width."""
    if not (0.0 < float(inset_fraction) < 0.5):
        raise CommonPhysicalBankError("inset_fraction must lie in (0, 0.5)")
    width = upper - lower
    pad = float(inset_fraction) * width
    inset_lo = lower + pad
    inset_hi = upper - pad
    if np.any(inset_hi <= inset_lo):
        raise CommonPhysicalBankError("inset Q box is empty")
    return inset_lo, inset_hi


def strictly_inside(
    q: NDArray[np.float64],
    lower: NDArray[np.float64],
    upper: NDArray[np.float64],
) -> bool:
    """Return True when ``q`` is in the open box ``(lower, upper)``."""
    q_arr = _as_q2(q)
    return bool(np.all(q_arr > lower) and np.all(q_arr < upper))


def _goal_points(
    center: NDArray[np.float64],
    radius: float,
) -> tuple[tuple[NDArray[np.float64], ...], tuple[str, ...]]:
    points = [_as_q2(center)]
    ids = ["center"]
    radial = float(radius) * BOUNDARY_RADIUS_FRACTION
    for angle_deg in BOUNDARY_ANGLES_DEG:
        theta = math.radians(float(angle_deg))
        offset = radial * np.asarray([math.cos(theta), math.sin(theta)], dtype=np.float64)
        points.append(_as_q2(center) + offset)
        ids.append(f"boundary_{angle_deg:g}deg")
    return tuple(points), tuple(ids)


def _working_q_box(
    inset_lo: NDArray[np.float64],
    inset_hi: NDArray[np.float64],
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return a strictly interior positive-elbow rectangle inside the inset."""
    q2_lo = float(WORKING_Q2_LOWER_FRACTION) * float(inset_hi[1])
    q2_hi = float(WORKING_Q2_UPPER_FRACTION) * float(inset_hi[1])
    if not (0.0 < q2_lo < q2_hi < float(inset_hi[1]) + 1e-15):
        raise CommonPhysicalBankError("working q2 band must lie in the open positive inset")
    work_lo = np.asarray([float(inset_lo[0]), q2_lo], dtype=np.float64)
    work_hi = np.asarray([float(inset_hi[0]), q2_hi], dtype=np.float64)
    if not strictly_inside(work_lo + 1e-12, inset_lo, inset_hi):
        raise CommonPhysicalBankError("working lower corner must lie inside the inset box")
    if not strictly_inside(work_hi - 1e-12, inset_lo, inset_hi):
        raise CommonPhysicalBankError("working upper corner must lie inside the inset box")
    return work_lo, work_hi


def _place_tasks(
    *,
    inset_lo: NDArray[np.float64],
    inset_hi: NDArray[np.float64],
    fk: Planar2R,
    goal_radius: float,
) -> tuple[dict[str, Any], ...]:
    work_lo, work_hi = _working_q_box(inset_lo, inset_hi)
    center = 0.5 * (work_lo + work_hi)
    half = 0.5 * (work_hi - work_lo)
    width = work_hi - work_lo
    near_offset = NEAR_OFFSET_FRACTION * half
    near_step = NEAR_STEP_FRACTION * width
    far_offset = FAR_OFFSET_FRACTION * half

    near_starts = (
        center,
        center + np.asarray([near_offset[0], 0.0]),
        center + np.asarray([-near_offset[0], 0.0]),
        center + np.asarray([0.0, near_offset[1]]),
        center + np.asarray([0.0, -near_offset[1]]),
    )
    near_witnesses = (
        near_starts[0] + np.asarray([near_step[0], 0.0]),
        near_starts[1] + np.asarray([0.0, near_step[1]]),
        near_starts[2] + np.asarray([0.0, near_step[1]]),
        near_starts[3] + np.asarray([near_step[0], 0.0]),
        near_starts[4] + np.asarray([near_step[0], 0.0]),
    )
    far_starts = (
        center + np.asarray([-far_offset[0], -far_offset[1]]),
        center + np.asarray([far_offset[0], -far_offset[1]]),
        center + np.asarray([-far_offset[0], far_offset[1]]),
        center + np.asarray([far_offset[0], far_offset[1]]),
        center + np.asarray([-far_offset[0], 0.0]),
    )
    far_witnesses = (
        center + np.asarray([far_offset[0], far_offset[1]]),
        center + np.asarray([-far_offset[0], far_offset[1]]),
        center + np.asarray([far_offset[0], -far_offset[1]]),
        center + np.asarray([-far_offset[0], -far_offset[1]]),
        center + np.asarray([far_offset[0], 0.0]),
    )

    tasks: list[dict[str, Any]] = []
    pairs = list(zip(FROZEN_TASK_IDS[:5], near_starts, near_witnesses, strict=True))
    pairs.extend(zip(FROZEN_TASK_IDS[5:], far_starts, far_witnesses, strict=True))
    for task_id, start_q, witness_q in pairs:
        start = _as_q2(start_q)
        witness = _as_q2(witness_q)
        if not strictly_inside(start, work_lo, work_hi):
            raise CommonPhysicalBankError(f"{task_id} start_q is not strictly inside the working box")
        if not strictly_inside(witness, work_lo, work_hi):
            raise CommonPhysicalBankError(
                f"{task_id} witness_q is not strictly inside the working box"
            )
        if not strictly_inside(start, inset_lo, inset_hi):
            raise CommonPhysicalBankError(f"{task_id} start_q is not strictly inside the inset box")
        if not strictly_inside(witness, inset_lo, inset_hi):
            raise CommonPhysicalBankError(
                f"{task_id} witness_q is not strictly inside the inset box"
            )
        start_x = _as_q2(fk.forward(start))
        goal_center = _as_q2(fk.forward(witness))
        goal_points, goal_ids = _goal_points(goal_center, goal_radius)
        for point_id, point in zip(goal_ids, goal_points, strict=True):
            if not fk.inverse(point):
                raise CommonPhysicalBankError(
                    f"{task_id} disk sample {point_id} is unreachable for identity planar 2R"
                )
        tasks.append(
            {
                "task_id": task_id,
                "start_q": start.tolist(),
                "start_x": start_x.tolist(),
                "witness_q": witness.tolist(),
                "goal_center": goal_center.tolist(),
                "goal_radius": float(goal_radius),
                "goal_point_ids": list(goal_ids),
                "goal_points": [point.tolist() for point in goal_points],
            }
        )
    return tuple(tasks)


def _unique_state(arm: SamplingSmokeArm, q: NDArray[np.float64], *, label: str) -> Any:
    candidates = list(arm.robot.states_from_output(q))
    if len(candidates) != 1:
        raise CommonPhysicalBankError(
            f"{arm.name} {label}: expected one certified inverse, got {len(candidates)}"
        )
    state = candidates[0].state
    if not arm.robot.validate_state(state, FK_ATOL):
        raise CommonPhysicalBankError(f"{arm.name} {label}: inverse failed round-trip")
    if not arm.robot.state_within_limits(state):
        raise CommonPhysicalBankError(f"{arm.name} {label}: realization is outside limits")
    return state


def _disk_sample_realizable(arm: SamplingSmokeArm, point: NDArray[np.float64], fk: Planar2R) -> bool:
    for q in fk.inverse(point):
        q_arr = _as_q2(q)
        for candidate in arm.robot.states_from_output(q_arr):
            if arm.robot.state_within_limits(candidate.state):
                return True
    return False


def preflight_bank(
    *,
    tasks: tuple[dict[str, Any], ...],
    realized_cases: tuple[RealizedSpanCase, ...],
    fk: Planar2R,
) -> dict[str, Any]:
    """Require start, witness, and disk samples on every mounted arm."""
    matrix: dict[str, dict[str, dict[str, str]]] = {}
    for realized in realized_cases:
        case_id = realized.case.case_id
        arms = _sampling_arms(realized, fk=fk)
        matrix[case_id] = {}
        for task in tasks:
            task_id = str(task["task_id"])
            start_q = _as_q2(task["start_q"])
            witness_q = _as_q2(task["witness_q"])
            start_x = _as_q2(task["start_x"])
            goal_center = _as_q2(task["goal_center"])
            row: dict[str, str] = {}
            for arm_name in ARMS:
                arm = arms[arm_name]
                start_state = _unique_state(arm, start_q, label=f"{task_id} start")
                witness_state = _unique_state(arm, witness_q, label=f"{task_id} witness")
                start_tip = np.asarray(
                    arm.robot.forward_kinematics(start_state).position, dtype=np.float64
                )
                witness_tip = np.asarray(
                    arm.robot.forward_kinematics(witness_state).position, dtype=np.float64
                )
                identity_start = _as_q2(fk.forward(start_q))
                identity_goal = _as_q2(fk.forward(witness_q))
                if float(np.linalg.norm(identity_start - start_x)) > FK_ATOL:
                    raise CommonPhysicalBankError(
                        f"{task_id}: identity start X disagrees with frozen start_x"
                    )
                if float(np.linalg.norm(identity_goal - goal_center)) > FK_ATOL:
                    raise CommonPhysicalBankError(
                        f"{task_id}: identity goal X disagrees with frozen goal_center"
                    )
                if float(np.linalg.norm(start_tip - start_x)) > FK_ATOL:
                    raise CommonPhysicalBankError(
                        f"{case_id}/{task_id}/{arm_name}: branch start FK disagrees with start_x"
                    )
                if float(np.linalg.norm(witness_tip - goal_center)) > FK_ATOL:
                    raise CommonPhysicalBankError(
                        f"{case_id}/{task_id}/{arm_name}: branch witness FK disagrees with goal_center"
                    )
                for point_id, point in zip(task["goal_point_ids"], task["goal_points"], strict=True):
                    if not _disk_sample_realizable(arm, _as_q2(point), fk):
                        raise CommonPhysicalBankError(
                            f"{case_id}/{task_id}/{arm_name}: disk sample {point_id} has no in-limits IK"
                        )
                row[arm_name] = "ok"
            matrix[case_id][task_id] = row
    return {
        "n_cases": len(realized_cases),
        "n_tasks": len(tasks),
        "n_arms": len(ARMS),
        "all_passed": True,
        "matrix": matrix,
    }


def realize_mounted_cases(registry: SpanRegistry) -> tuple[RealizedSpanCase, ...]:
    """Realize every generated span case on the mounted-Q owner."""
    cases = generate_span_cases()
    if len(cases) != 17:
        raise CommonPhysicalBankError(f"expected 17 span cases, got {len(cases)}")
    return tuple(realize_mounted_span_case(case, registry) for case in cases)


def build_common_physical_bank(
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Build, preflight, and digest the common-physical bank."""
    registry = load_frozen_v3_6d_registry(repo_root=repo_root)
    realized = realize_mounted_cases(registry)
    common_lo, common_hi = common_mounted_q_box(realized)
    inset_lo, inset_hi = inset_q_box(common_lo, common_hi, inset_fraction=INSET_FRACTION)
    work_lo, work_hi = _working_q_box(inset_lo, inset_hi)
    fk = Planar2R(L1=PLANAR_L1, L2=PLANAR_L2)
    tasks = _place_tasks(
        inset_lo=inset_lo,
        inset_hi=inset_hi,
        fk=fk,
        goal_radius=GOAL_RADIUS,
    )
    for task in tasks:
        if not strictly_inside(_as_q2(task["start_q"]), common_lo, common_hi):
            raise CommonPhysicalBankError(f"{task['task_id']} start_q is not strictly inside the common box")
        if not strictly_inside(_as_q2(task["witness_q"]), common_lo, common_hi):
            raise CommonPhysicalBankError(
                f"{task['task_id']} witness_q is not strictly inside the common box"
            )
    preflight = preflight_bank(tasks=tasks, realized_cases=realized, fk=fk)
    payload: dict[str, Any] = {
        "bank_id": BANK_ID,
        "schema_version": SCHEMA_VERSION,
        "generator_version": GENERATOR_VERSION,
        "seed": FROZEN_SEED,
        "v3_6d_digest_lock": FROZEN_V3_6D_DIGEST,
        "planar2r": {"L1": PLANAR_L1, "L2": PLANAR_L2},
        "inset_fraction": INSET_FRACTION,
        "working_q2_lower_fraction": WORKING_Q2_LOWER_FRACTION,
        "working_q2_upper_fraction": WORKING_Q2_UPPER_FRACTION,
        "near_offset_fraction": NEAR_OFFSET_FRACTION,
        "near_step_fraction": NEAR_STEP_FRACTION,
        "far_offset_fraction": FAR_OFFSET_FRACTION,
        "goal_radius": GOAL_RADIUS,
        "goal_representation": {
            "kind": GOAL_REPRESENTATION_KIND,
            "include_center": True,
            "boundary_angles_deg": list(BOUNDARY_ANGLES_DEG),
            "boundary_radius_fraction": BOUNDARY_RADIUS_FRACTION,
            "max_candidates": 32,
        },
        "residual_policy": RESIDUAL_POLICY,
        "common_q_box": {
            "lower": common_lo.tolist(),
            "upper": common_hi.tolist(),
        },
        "inset_q_box": {
            "lower": inset_lo.tolist(),
            "upper": inset_hi.tolist(),
        },
        "working_q_box": {
            "lower": work_lo.tolist(),
            "upper": work_hi.tolist(),
        },
        "task_ids": list(FROZEN_TASK_IDS),
        "tasks": list(tasks),
        "preflight": preflight,
    }
    payload["sha256"] = bank_digest(payload)
    return payload


def load_common_physical_bank(path: Path | str | None = None) -> dict[str, Any]:
    """Load the frozen bank JSON and verify its digest."""
    bank_path = (
        Path(path)
        if path is not None
        else CANONICAL_REPO_ROOT / DEFAULT_BANK_REL
    )
    try:
        payload = json.loads(bank_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CommonPhysicalBankError(f"missing common-physical bank at {bank_path}") from exc
    except json.JSONDecodeError as exc:
        raise CommonPhysicalBankError(f"invalid common-physical bank JSON at {bank_path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise CommonPhysicalBankError("common-physical bank must be a JSON object")
    digest = bank_digest(payload)
    recorded = str(payload.get("sha256", ""))
    if digest != recorded:
        raise CommonPhysicalBankError(
            f"common-physical bank digest mismatch: file={recorded} recomputed={digest}"
        )
    if payload.get("bank_id") != BANK_ID:
        raise CommonPhysicalBankError(
            f"bank_id must be {BANK_ID!r}, got {payload.get('bank_id')!r}"
        )
    return payload


def write_common_physical_bank(
    path: Path | str | None = None,
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Build the bank and write the frozen JSON."""
    payload = build_common_physical_bank(repo_root=repo_root)
    bank_path = (
        Path(path)
        if path is not None
        else CANONICAL_REPO_ROOT / DEFAULT_BANK_REL
    )
    bank_path.parent.mkdir(parents=True, exist_ok=True)
    bank_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload
