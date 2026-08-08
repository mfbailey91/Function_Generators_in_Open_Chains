"""Frozen planar 3R free-space bank loader (Sprint V3.7 / V3-704)."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray

from inequality_mechanisms.benchmarks.planar_3r_arms import (
    MechanismName,
    Planar3RArm,
    build_paired_3r_arms,
)
from inequality_mechanisms.core.constraints import ConstraintSet
from inequality_mechanisms.core.goals import (
    CartesianDiskGoal,
    FrozenPlanar3RPositionGoalGenerator,
    GoalConstraint,
    GoalStateGenerator,
    Planar3RPoseGoalGenerator,
    PlanarPoseRegionGoal,
)
from inequality_mechanisms.core.local_motion import InputLinearMotion
from inequality_mechanisms.core.objectives import ActuatorTravelObjective
from inequality_mechanisms.core.problem import PlanningProblem
from inequality_mechanisms.core.scene import FreeSpaceScene
from inequality_mechanisms.core.state import PhysicalState
from inequality_mechanisms.kinematics.planar_3r import angular_distance

TaskFamily = Literal["position_only", "full_pose"]

DEFAULT_BANK_3R_PATH = (
    Path(__file__).resolve().parents[3]
    / "configs"
    / "v3"
    / "free_space_planar3r_v1.json"
)


@dataclass(frozen=True, slots=True)
class PositionOnlyRepresentation3R:
    kind: str
    include_center: bool
    boundary_angles_deg: tuple[float, ...]
    boundary_radius_fraction: float
    phi_samples: tuple[float, ...]
    max_candidates: int


@dataclass(frozen=True, slots=True)
class FullPoseRepresentation3R:
    kind: str
    max_candidates: int


@dataclass(frozen=True, slots=True)
class FreeSpaceBankTask3R:
    task_id: str
    task_family: TaskFamily
    start_u_frac: tuple[float, float, float]
    goal_center: NDArray[np.float64]
    goal_radius: float
    goal_phi: float | None = None
    orientation_tol: float | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "goal_center",
            np.asarray(self.goal_center, dtype=np.float64).copy(),
        )


@dataclass(frozen=True, slots=True)
class FreeSpaceEvidenceContract3R:
    bank_id: str
    schema_version: int
    description: str
    L1: float
    L2: float
    L3: float
    mechanisms: tuple[MechanismName, ...]
    size_bins: dict[str, tuple[float, float | None]]
    reference_mechanism: MechanismName
    start_tip_tolerance: float
    start_heading_tolerance: float
    position_only_representation: PositionOnlyRepresentation3R
    full_pose_representation: FullPoseRepresentation3R
    stochastic_seeds: tuple[int, ...]
    ompl_process_isolation: bool
    tasks: tuple[FreeSpaceBankTask3R, ...]
    source_path: Path


@dataclass(frozen=True, slots=True)
class ResolvedFreeSpaceTask3R:
    task_id: str
    task_family: TaskFamily
    start_q: NDArray[np.float64]
    start_tip: NDArray[np.float64]
    start_phi: float
    goal_center: NDArray[np.float64]
    goal_radius: float
    goal_phi: float | None
    orientation_tol: float | None
    goal_points: tuple[NDArray[np.float64], ...]
    goal_point_ids: tuple[str, ...]
    phi_samples: tuple[float, ...]
    notes: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "start_q", np.asarray(self.start_q, dtype=np.float64).copy()
        )
        object.__setattr__(
            self, "start_tip", np.asarray(self.start_tip, dtype=np.float64).copy()
        )
        object.__setattr__(
            self,
            "goal_center",
            np.asarray(self.goal_center, dtype=np.float64).copy(),
        )
        object.__setattr__(
            self,
            "goal_points",
            tuple(np.asarray(x, dtype=np.float64).copy() for x in self.goal_points),
        )


def default_bank_3r_path() -> Path:
    """Return the repository path to ``free_space_planar3r_v1.json``."""
    return DEFAULT_BANK_3R_PATH


def load_free_space_bank_3r(
    path: Path | None = None,
) -> FreeSpaceEvidenceContract3R:
    """Load and validate the frozen planar 3R free-space bank."""
    source = Path(path) if path is not None else default_bank_3r_path()
    raw = json.loads(source.read_text(encoding="utf-8"))
    if int(raw.get("schema_version", -1)) != 1:
        raise ValueError(f"unsupported 3R bank schema_version in {source}")

    bins_raw = dict(raw["size_strata_bins_tip_distance"])
    size_bins: dict[str, tuple[float, float | None]] = {}
    for name, pair in bins_raw.items():
        lo = float(pair[0])
        hi = None if pair[1] is None else float(pair[1])
        size_bins[str(name)] = (lo, hi)

    start = dict(raw["start_contract"])
    pos = dict(raw["position_only_representation"])
    pose = dict(raw["full_pose_representation"])
    reps = dict(raw["stochastic_repetitions"])
    reference = str(start["authoring_reference_mechanism"])
    mechanisms = tuple(str(m) for m in raw["mechanisms"])
    if reference not in mechanisms:
        raise ValueError(f"unknown reference mechanism {reference!r}")

    radius_fraction = float(pos["boundary_radius_fraction"])
    if not (0.0 < radius_fraction < 1.0):
        raise ValueError("boundary_radius_fraction must lie in (0, 1)")
    seeds = tuple(int(s) for s in reps["seeds"])
    if not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("stochastic seeds must be nonempty and unique")

    tasks: list[FreeSpaceBankTask3R] = []
    for item in raw["tasks"]:
        family = str(item["task_family"])
        if family not in ("position_only", "full_pose"):
            raise ValueError(f"unsupported task_family {family!r}")
        frac = item["start_u_frac"]
        if len(frac) != 3:
            raise ValueError(f"{item['task_id']}: start_u_frac must have length 3")
        goal_phi = item.get("goal_phi")
        ori_tol = item.get("orientation_tol")
        if family == "full_pose":
            if goal_phi is None or ori_tol is None:
                raise ValueError(
                    f"{item['task_id']}: full_pose requires goal_phi and orientation_tol"
                )
        tasks.append(
            FreeSpaceBankTask3R(
                task_id=str(item["task_id"]),
                task_family=family,  # type: ignore[arg-type]
                start_u_frac=(float(frac[0]), float(frac[1]), float(frac[2])),
                goal_center=np.asarray(item["goal_center"], dtype=np.float64),
                goal_radius=float(item["goal_radius"]),
                goal_phi=None if goal_phi is None else float(goal_phi),
                orientation_tol=None if ori_tol is None else float(ori_tol),
                notes=str(item.get("notes", "")),
            )
        )

    return FreeSpaceEvidenceContract3R(
        bank_id=str(raw["bank_id"]),
        schema_version=int(raw["schema_version"]),
        description=str(raw.get("description", "")),
        L1=float(raw["robot"]["L1"]),
        L2=float(raw["robot"]["L2"]),
        L3=float(raw["robot"]["L3"]),
        mechanisms=mechanisms,  # type: ignore[arg-type]
        size_bins=size_bins,
        reference_mechanism=reference,  # type: ignore[arg-type]
        start_tip_tolerance=float(start["cartesian_tip_tolerance"]),
        start_heading_tolerance=float(start.get("pose_heading_tolerance", 1e-9)),
        position_only_representation=PositionOnlyRepresentation3R(
            kind=str(pos["kind"]),
            include_center=bool(pos["include_center"]),
            boundary_angles_deg=tuple(float(v) for v in pos["boundary_angles_deg"]),
            boundary_radius_fraction=radius_fraction,
            phi_samples=tuple(float(v) for v in pos["phi_samples_rad"]),
            max_candidates=int(pos["max_candidates"]),
        ),
        full_pose_representation=FullPoseRepresentation3R(
            kind=str(pose["kind"]),
            max_candidates=int(pose["max_candidates"]),
        ),
        stochastic_seeds=seeds,
        ompl_process_isolation=bool(reps["ompl_process_isolation"]),
        tasks=tuple(tasks),
        source_path=source.resolve(),
    )


def build_bank_arms_3r(
    contract: FreeSpaceEvidenceContract3R,
) -> dict[MechanismName, Planar3RArm]:
    """Build paired 3R arms matching the bank FK lengths."""
    return build_paired_3r_arms(L1=contract.L1, L2=contract.L2, L3=contract.L3)


def state_from_shared_q_3r(
    arm: Planar3RArm,
    start_q: NDArray[np.float64],
) -> PhysicalState:
    """Realize a shared output configuration on ``arm``."""
    candidates = list(arm.robot.states_from_output(start_q))
    if len(candidates) != 1:
        raise ValueError(
            f"{arm.name} expected exactly one certified start realization, "
            f"got {len(candidates)}"
        )
    state = candidates[0].state
    if not arm.robot.validate_state(state, 1e-9):
        raise ValueError(f"{arm.name} produced inconsistent shared start")
    if not arm.robot.state_within_limits(state):
        raise ValueError(f"{arm.name} shared start is outside certified limits")
    return state


def _goal_points(
    task: FreeSpaceBankTask3R,
    spec: PositionOnlyRepresentation3R,
) -> tuple[tuple[NDArray[np.float64], ...], tuple[str, ...]]:
    points: list[NDArray[np.float64]] = []
    ids: list[str] = []
    if spec.include_center:
        points.append(np.asarray(task.goal_center, dtype=np.float64).copy())
        ids.append("center")
    radial = float(task.goal_radius) * spec.boundary_radius_fraction
    for angle_deg in spec.boundary_angles_deg:
        theta = math.radians(float(angle_deg))
        offset = radial * np.asarray([math.cos(theta), math.sin(theta)])
        points.append(np.asarray(task.goal_center, dtype=np.float64) + offset)
        ids.append(f"boundary_{angle_deg:g}deg")
    return tuple(points), tuple(ids)


def resolve_free_space_tasks_3r(
    contract: FreeSpaceEvidenceContract3R,
    *,
    arms: dict[MechanismName, Planar3RArm] | None = None,
) -> tuple[ResolvedFreeSpaceTask3R, ...]:
    """Resolve shared starts and frozen goal representations for all tasks."""
    arms = arms if arms is not None else build_bank_arms_3r(contract)
    ref_arm = arms[contract.reference_mechanism]
    cert = ref_arm.branch.certificate
    u_lo = np.asarray(cert.input_lower, dtype=np.float64)
    u_hi = np.asarray(cert.input_upper, dtype=np.float64)

    resolved: list[ResolvedFreeSpaceTask3R] = []
    for task in contract.tasks:
        frac = np.asarray(task.start_u_frac, dtype=np.float64)
        u_ref = u_lo + frac * (u_hi - u_lo)
        ref_state = ref_arm.robot.state_from_input(u_ref)
        start_q = np.asarray(ref_state.q, dtype=np.float64).copy()
        pose = ref_arm.robot.forward_kinematics(ref_state)
        start_tip = np.asarray(pose.position, dtype=np.float64)
        if pose.orientation is None:
            raise ValueError("3R FK must provide orientation")
        start_phi = float(pose.orientation[0])
        for mech in contract.mechanisms:
            state = state_from_shared_q_3r(arms[mech], start_q)
            tip_pose = arms[mech].robot.forward_kinematics(state)
            tip = np.asarray(tip_pose.position, dtype=np.float64)
            residual = float(np.linalg.norm(tip - start_tip))
            if residual > contract.start_tip_tolerance:
                raise ValueError(
                    f"{task.task_id}: paired start-tip mismatch for {mech}: {residual}"
                )
            if tip_pose.orientation is None:
                raise ValueError(f"{mech} missing start orientation")
            heading_err = angular_distance(float(tip_pose.orientation[0]), start_phi)
            if heading_err > contract.start_heading_tolerance:
                raise ValueError(
                    f"{task.task_id}: paired start-heading mismatch for {mech}: "
                    f"{heading_err}"
                )

        if task.task_family == "position_only":
            points, point_ids = _goal_points(
                task, contract.position_only_representation
            )
            phi_samples = contract.position_only_representation.phi_samples
        else:
            points = (np.asarray(task.goal_center, dtype=np.float64).copy(),)
            point_ids = ("se2_center",)
            phi_samples = (
                () if task.goal_phi is None else (float(task.goal_phi),)
            )

        resolved.append(
            ResolvedFreeSpaceTask3R(
                task_id=task.task_id,
                task_family=task.task_family,
                start_q=start_q,
                start_tip=start_tip,
                start_phi=start_phi,
                goal_center=np.asarray(task.goal_center, dtype=np.float64),
                goal_radius=float(task.goal_radius),
                goal_phi=task.goal_phi,
                orientation_tol=task.orientation_tol,
                goal_points=points,
                goal_point_ids=point_ids,
                phi_samples=phi_samples,
                notes=task.notes,
            )
        )
    return tuple(resolved)


def build_goal_3r(
    arm: Planar3RArm,
    task: ResolvedFreeSpaceTask3R,
) -> GoalConstraint:
    """Build the physical goal predicate for a resolved 3R task."""
    if task.task_family == "position_only":
        return CartesianDiskGoal(
            center=task.goal_center.copy(),
            radius=task.goal_radius,
            robot=arm.robot,
        )
    assert task.goal_phi is not None and task.orientation_tol is not None
    return PlanarPoseRegionGoal(
        center=task.goal_center.copy(),
        radius=task.goal_radius,
        phi_goal=float(task.goal_phi),
        orientation_tol=float(task.orientation_tol),
        robot=arm.robot,
    )


def build_problem_3r(
    arm: Planar3RArm,
    task: ResolvedFreeSpaceTask3R,
) -> PlanningProblem:
    """Build an exact-start PlanningProblem for a resolved 3R task."""
    start = state_from_shared_q_3r(arm, task.start_q)
    return PlanningProblem(
        robot=arm.robot,
        scene=FreeSpaceScene(robot=arm.robot),
        start=start,
        goal=build_goal_3r(arm, task),
        path_constraints=ConstraintSet.empty(),
        local_motion=InputLinearMotion(robot=arm.robot, n_samples=12),
        objective=ActuatorTravelObjective(),
    )


def goal_generator_3r(
    arm: Planar3RArm,
    task: ResolvedFreeSpaceTask3R,
    contract: FreeSpaceEvidenceContract3R,
) -> GoalStateGenerator:
    """Return the frozen represented-goal generator for ``task``."""
    fk = arm.planar_fk
    if task.task_family == "position_only":
        return FrozenPlanar3RPositionGoalGenerator(
            planar_fk=fk,
            goal_points=task.goal_points,
            goal_point_ids=task.goal_point_ids,
            phi_samples=task.phi_samples,
        )
    return Planar3RPoseGoalGenerator(planar_fk=fk)


def max_candidates_3r(
    task: ResolvedFreeSpaceTask3R,
    contract: FreeSpaceEvidenceContract3R,
) -> int:
    """Return the frozen max-candidate budget for ``task``."""
    if task.task_family == "position_only":
        return contract.position_only_representation.max_candidates
    return contract.full_pose_representation.max_candidates


def resolved_bank_3r_to_dict(
    contract: FreeSpaceEvidenceContract3R,
    tasks: tuple[ResolvedFreeSpaceTask3R, ...],
) -> dict[str, Any]:
    """Serialize resolved bank provenance for review artifacts."""
    return {
        "bank_id": contract.bank_id,
        "schema_version": contract.schema_version,
        "reference_mechanism": contract.reference_mechanism,
        "start_contract": "shared_q_resolved_from_reference_arm",
        "position_only_representation": {
            "kind": contract.position_only_representation.kind,
            "phi_samples_rad": list(
                contract.position_only_representation.phi_samples
            ),
            "max_candidates": contract.position_only_representation.max_candidates,
        },
        "full_pose_representation": {
            "kind": contract.full_pose_representation.kind,
            "max_candidates": contract.full_pose_representation.max_candidates,
        },
        "stochastic_seeds": list(contract.stochastic_seeds),
        "tasks": [
            {
                "task_id": task.task_id,
                "task_family": task.task_family,
                "start_q": task.start_q.tolist(),
                "start_tip": task.start_tip.tolist(),
                "start_phi": task.start_phi,
                "goal_center": task.goal_center.tolist(),
                "goal_radius": task.goal_radius,
                "goal_phi": task.goal_phi,
                "orientation_tol": task.orientation_tol,
                "goal_point_ids": list(task.goal_point_ids),
                "goal_points": [x.tolist() for x in task.goal_points],
                "phi_samples": list(task.phi_samples),
                "notes": task.notes,
            }
            for task in tasks
        ],
    }


__all__ = [
    "DEFAULT_BANK_3R_PATH",
    "FreeSpaceBankTask3R",
    "FreeSpaceEvidenceContract3R",
    "FullPoseRepresentation3R",
    "PositionOnlyRepresentation3R",
    "ResolvedFreeSpaceTask3R",
    "TaskFamily",
    "build_bank_arms_3r",
    "build_goal_3r",
    "build_problem_3r",
    "default_bank_3r_path",
    "goal_generator_3r",
    "load_free_space_bank_3r",
    "max_candidates_3r",
    "resolve_free_space_tasks_3r",
    "resolved_bank_3r_to_dict",
    "state_from_shared_q_3r",
]
