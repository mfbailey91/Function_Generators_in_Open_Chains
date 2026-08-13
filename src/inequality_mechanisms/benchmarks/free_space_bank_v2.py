"""Corrected Version 3.6 free-space bank contract.

The v1 JSON task list is immutable pilot provenance.  V2 layers a corrected
execution contract over it:

- v1 ``start_u_frac`` is interpreted only on one reference mechanism;
- that reference state is resolved to one shared ``q`` / Cartesian start;
- every paired mechanism realizes that same ``q`` through its own inverse map;
- the physical Cartesian disk remains the task predicate;
- all planners consume one frozen finite Cartesian sample set for that disk.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from inequality_mechanisms.benchmarks.free_space_bank import (
    FreeSpaceBankTask,
    FreeSpaceTaskBank,
    MechanismName,
    build_bank_arms,
    build_cartesian_problem,
    load_free_space_bank,
)
from inequality_mechanisms.benchmarks.smoke_sampling_2r import SamplingSmokeArm
from inequality_mechanisms.core.goals import (
    CartesianDiskGoal,
    GoalConstraint,
    GoalSamplingRequest,
)
from inequality_mechanisms.core.state import PhysicalState, StateCandidate
from inequality_mechanisms.kinematics.planar_2r import Planar2R
from inequality_mechanisms.kinematics.planar_2r_goals import planar_2r_ik_family

DEFAULT_BANK_V2_PATH = (
    Path(__file__).resolve().parents[3]
    / "configs"
    / "v3"
    / "free_space_planar2r_v2.json"
)


@dataclass(frozen=True, slots=True)
class GoalRepresentationV2:
    kind: str
    include_center: bool
    boundary_angles_deg: tuple[float, ...]
    boundary_radius_fraction: float
    max_candidates: int


@dataclass(frozen=True, slots=True)
class FreeSpaceEvidenceContractV2:
    bank_id: str
    schema_version: int
    description: str
    base_bank: FreeSpaceTaskBank
    reference_mechanism: MechanismName
    start_tip_tolerance: float
    goal_representation: GoalRepresentationV2
    stochastic_seeds: tuple[int, ...]
    ompl_process_isolation: bool
    source_path: Path


@dataclass(frozen=True, slots=True)
class ResolvedFreeSpaceTaskV2:
    task_id: str
    start_q: NDArray[np.float64]
    start_tip: NDArray[np.float64]
    goal_center: NDArray[np.float64]
    goal_radius: float
    goal_points: tuple[NDArray[np.float64], ...]
    goal_point_ids: tuple[str, ...]
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


@dataclass(frozen=True, slots=True)
class FrozenCartesianDiskGoalGenerator:
    """Deterministic finite realization of one Cartesian disk predicate."""

    planar_fk: Planar2R
    goal_points: tuple[NDArray[np.float64], ...]
    goal_point_ids: tuple[str, ...]
    numerical_tolerance: float = 1e-9

    def generate(
        self,
        robot: Any,
        goal: GoalConstraint,
        request: GoalSamplingRequest,
    ) -> tuple[StateCandidate, ...]:
        if not isinstance(goal, CartesianDiskGoal):
            raise TypeError(
                "FrozenCartesianDiskGoalGenerator requires CartesianDiskGoal"
            )
        if len(self.goal_points) != len(self.goal_point_ids):
            raise ValueError("goal point ids must match goal points")

        out: list[StateCandidate] = []
        seen: set[tuple[float, ...]] = set()
        for point_index, (point_id, point) in enumerate(
            zip(self.goal_point_ids, self.goal_points)
        ):
            for q in self.planar_fk.inverse(point):
                q_arr = np.asarray(q, dtype=np.float64)
                key = tuple(np.round(q_arr, decimals=12).tolist())
                if key in seen:
                    continue
                for cand in robot.states_from_output(q_arr):
                    if not robot.state_within_limits(cand.state):
                        continue
                    tip = np.asarray(
                        robot.forward_kinematics(cand.state).position,
                        dtype=np.float64,
                    )
                    cart_dist = float(np.linalg.norm(tip - goal.center))
                    if cart_dist > float(goal.radius) + self.numerical_tolerance:
                        continue
                    seen.add(key)
                    provenance = {
                        **dict(cand.provenance),
                        "ik_family": planar_2r_ik_family(q_arr),
                        "goal_representation": "frozen_cartesian_disk_points_v1",
                        "candidate_generator_id": "frozen_cartesian_disk_points_v1",
                        "goal_sample_id": point_id,
                        "goal_sample_index": int(point_index),
                        "goal_sample_point": point.tolist(),
                    }
                    out.append(
                        StateCandidate(
                            state=cand.state,
                            residual=max(float(cand.residual), cart_dist),
                            provenance=provenance,
                        )
                    )
                    if len(out) >= request.max_candidates:
                        return tuple(out)
        return tuple(out)


def load_free_space_bank_v2(
    path: Path | None = None,
) -> FreeSpaceEvidenceContractV2:
    source = Path(path) if path is not None else DEFAULT_BANK_V2_PATH
    raw = json.loads(source.read_text(encoding="utf-8"))
    if int(raw.get("schema_version", -1)) != 2:
        raise ValueError(f"unsupported V3.6 corrective schema in {source}")

    base_path = source.parent / str(raw["base_bank_path"])
    base_bank = load_free_space_bank(base_path)
    if base_bank.bank_id != str(raw["base_bank_id"]):
        raise ValueError("base bank id does not match corrective contract")

    start = dict(raw["start_contract"])
    goal = dict(raw["goal_representation"])
    reps = dict(raw["stochastic_repetitions"])
    reference = str(start["authoring_reference_mechanism"])
    if reference not in base_bank.mechanisms:
        raise ValueError(f"unknown reference mechanism {reference!r}")

    radius_fraction = float(goal["boundary_radius_fraction"])
    if not (0.0 < radius_fraction < 1.0):
        raise ValueError("boundary_radius_fraction must lie in (0, 1)")
    seeds = tuple(int(s) for s in reps["seeds"])
    if not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("stochastic seeds must be nonempty and unique")

    return FreeSpaceEvidenceContractV2(
        bank_id=str(raw["bank_id"]),
        schema_version=2,
        description=str(raw.get("description", "")),
        base_bank=base_bank,
        reference_mechanism=reference,  # type: ignore[arg-type]
        start_tip_tolerance=float(start["cartesian_tip_tolerance"]),
        goal_representation=GoalRepresentationV2(
            kind=str(goal["kind"]),
            include_center=bool(goal["include_center"]),
            boundary_angles_deg=tuple(float(v) for v in goal["boundary_angles_deg"]),
            boundary_radius_fraction=radius_fraction,
            max_candidates=int(goal["max_candidates"]),
        ),
        stochastic_seeds=seeds,
        ompl_process_isolation=bool(reps["ompl_process_isolation"]),
        source_path=source.resolve(),
    )


def _goal_points(
    task: FreeSpaceBankTask,
    spec: GoalRepresentationV2,
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


def state_from_shared_q(
    arm: SamplingSmokeArm,
    start_q: NDArray[np.float64],
) -> PhysicalState:
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


def resolve_free_space_tasks_v2(
    contract: FreeSpaceEvidenceContractV2,
    *,
    arms: dict[MechanismName, SamplingSmokeArm] | None = None,
) -> tuple[ResolvedFreeSpaceTaskV2, ...]:
    arms = arms if arms is not None else build_bank_arms(contract.base_bank)
    ref_arm = arms[contract.reference_mechanism]
    cert = ref_arm.branch.certificate
    u_lo = np.asarray(cert.input_lower, dtype=np.float64)
    u_hi = np.asarray(cert.input_upper, dtype=np.float64)

    resolved: list[ResolvedFreeSpaceTaskV2] = []
    for task in contract.base_bank.tasks:
        frac = np.asarray(task.start_u_frac, dtype=np.float64)
        u_ref = u_lo + frac * (u_hi - u_lo)
        ref_state = ref_arm.robot.state_from_input(u_ref)
        start_q = np.asarray(ref_state.q, dtype=np.float64).copy()
        start_tip = np.asarray(
            ref_arm.robot.forward_kinematics(ref_state).position,
            dtype=np.float64,
        )
        for mech in contract.base_bank.mechanisms:
            state = state_from_shared_q(arms[mech], start_q)
            tip = np.asarray(
                arms[mech].robot.forward_kinematics(state).position,
                dtype=np.float64,
            )
            residual = float(np.linalg.norm(tip - start_tip))
            if residual > contract.start_tip_tolerance:
                raise ValueError(
                    f"{task.task_id}: paired start-tip mismatch for {mech}: "
                    f"{residual}"
                )
        points, point_ids = _goal_points(task, contract.goal_representation)
        resolved.append(
            ResolvedFreeSpaceTaskV2(
                task_id=task.task_id,
                start_q=start_q,
                start_tip=start_tip,
                goal_center=np.asarray(task.goal_center, dtype=np.float64),
                goal_radius=float(task.goal_radius),
                goal_points=points,
                goal_point_ids=point_ids,
                notes=task.notes,
            )
        )
    return tuple(resolved)


def build_problem_v2(
    arm: SamplingSmokeArm,
    task: ResolvedFreeSpaceTaskV2,
) -> Any:
    """Build the common input-linear V3.6 benchmark problem."""
    base_task = FreeSpaceBankTask(
        task_id=task.task_id,
        start_u_frac=(0.0, 0.0),  # ignored below; retained for V1 container reuse
        goal_center=task.goal_center,
        goal_radius=task.goal_radius,
        notes=task.notes,
    )
    problem = build_cartesian_problem(arm, base_task)
    start = state_from_shared_q(arm, task.start_q)
    return type(problem)(
        robot=problem.robot,
        scene=problem.scene,
        start=start,
        goal=problem.goal,
        path_constraints=problem.path_constraints,
        local_motion=problem.local_motion,
        objective=problem.objective,
    )


def goal_generator_v2(
    arm: SamplingSmokeArm,
    task: ResolvedFreeSpaceTaskV2,
) -> FrozenCartesianDiskGoalGenerator:
    fk = arm.robot.planar_fk
    if fk is None:
        raise ValueError("planar FK is required for the V3.6 corrected goal set")
    return FrozenCartesianDiskGoalGenerator(
        planar_fk=fk,
        goal_points=task.goal_points,
        goal_point_ids=task.goal_point_ids,
    )


def resolved_bank_to_dict(
    contract: FreeSpaceEvidenceContractV2,
    tasks: tuple[ResolvedFreeSpaceTaskV2, ...],
) -> dict[str, Any]:
    return {
        "bank_id": contract.bank_id,
        "schema_version": contract.schema_version,
        "base_bank_id": contract.base_bank.bank_id,
        "reference_mechanism": contract.reference_mechanism,
        "start_contract": "shared_q_resolved_from_reference_arm",
        "goal_representation": {
            "kind": contract.goal_representation.kind,
            "boundary_radius_fraction": (
                contract.goal_representation.boundary_radius_fraction
            ),
            "max_candidates": contract.goal_representation.max_candidates,
        },
        "stochastic_seeds": list(contract.stochastic_seeds),
        "tasks": [
            {
                "task_id": task.task_id,
                "start_q": task.start_q.tolist(),
                "start_tip": task.start_tip.tolist(),
                "goal_center": task.goal_center.tolist(),
                "goal_radius": task.goal_radius,
                "goal_point_ids": list(task.goal_point_ids),
                "goal_points": [x.tolist() for x in task.goal_points],
                "notes": task.notes,
            }
            for task in tasks
        ],
    }


__all__ = [
    "DEFAULT_BANK_V2_PATH",
    "FreeSpaceEvidenceContractV2",
    "FrozenCartesianDiskGoalGenerator",
    "GoalRepresentationV2",
    "ResolvedFreeSpaceTaskV2",
    "build_problem_v2",
    "goal_generator_v2",
    "load_free_space_bank_v2",
    "resolve_free_space_tasks_v2",
    "resolved_bank_to_dict",
    "state_from_shared_q",
]
