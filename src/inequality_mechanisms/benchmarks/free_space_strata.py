"""Pre-search size and paired strata for free-space evidence (Sprint V3.6 / V3-602)."""

from __future__ import annotations

from typing import Any, Literal

import numpy as np

from inequality_mechanisms.benchmarks.classification import (
    TASK_DIRECT_LOCAL_FEASIBLE,
    classify_direct_attempt,
)
from inequality_mechanisms.benchmarks.free_space_bank import (
    FreeSpaceBankTask,
    FreeSpaceTaskBank,
    state_from_u_frac,
)
from inequality_mechanisms.benchmarks.smoke_sampling_2r import SamplingSmokeArm
from inequality_mechanisms.core.goals import CartesianDiskGoalGenerator
from inequality_mechanisms.core.problem import PlanningProblem
from inequality_mechanisms.core.state import PhysicalState
from inequality_mechanisms.planners.sampling_space import (
    direct_connector_available,
    select_goal_states,
)

PairedStratum = Literal[
    "both_direct",
    "fourbar_only_direct",
    "gearbox_only_direct",
    "neither_direct",
    "paired_invalid",
]


def tip_position(arm: SamplingSmokeArm, state: PhysicalState) -> np.ndarray:
    """Return Cartesian tip coordinates for ``state``."""
    return np.asarray(arm.robot.forward_kinematics(state).position, dtype=np.float64)


def tip_separation(
    arm: SamplingSmokeArm,
    task: FreeSpaceBankTask,
) -> float:
    """Euclidean tip distance from exact start tip to the external goal center."""
    start = state_from_u_frac(arm, task.start_u_frac)
    tip = tip_position(arm, start)
    return float(np.linalg.norm(tip - np.asarray(task.goal_center, dtype=np.float64)))


def assign_size_stratum(
    tip_distance: float,
    bins: dict[str, tuple[float, float | None]],
) -> str:
    """Assign ``short`` / ``medium`` / ``long`` from tip-distance bins."""
    for name in ("short", "medium", "long"):
        if name not in bins:
            continue
        lo, hi = bins[name]
        if tip_distance < lo:
            continue
        if hi is None or tip_distance < hi:
            return name
    # Fallback: open upper bin.
    return "long"


def classify_problem_presearch(
    problem: PlanningProblem,
    *,
    goal_generator: CartesianDiskGoalGenerator | None,
    max_goal_candidates: int = 8,
) -> tuple[str, dict[str, Any], list[PhysicalState]]:
    """Classify one mechanism-task before planner search (ADR-026)."""
    start_valid = bool(problem.scene.state_is_valid(problem.start))
    try:
        _ = problem.goal.residual(problem.start)
        goal_usable = True
    except (NotImplementedError, ValueError, TypeError):
        goal_usable = False
    already = bool(goal_usable and problem.goal.satisfied(problem.start))
    candidates: list[PhysicalState] = []
    if goal_usable and not already:
        try:
            candidates = select_goal_states(
                problem,
                goal_generator=goal_generator,
                max_candidates=max_goal_candidates,
                rng=None,
            )
        except ValueError:
            candidates = []
    connector_ok = False
    if candidates:
        connector_ok, _ = direct_connector_available(problem, candidates)
    task_class = classify_direct_attempt(
        start_valid=start_valid,
        goal_usable=goal_usable,
        already_satisfied=already,
        candidates_representable=bool(candidates) or already,
        connector_succeeded=connector_ok or already,
    )
    extras = {
        "start_valid": start_valid,
        "goal_usable": goal_usable,
        "already_satisfied": already,
        "goal_candidates": len(candidates),
        "direct_connector_available": bool(connector_ok or already),
        "direct_connector_policy": str(
            getattr(
                problem.local_motion,
                "model_id",
                type(problem.local_motion).__name__,
            )
        ),
    }
    return task_class, extras, candidates


def paired_stratum_from_classes(
    fourbar_class: str,
    gearbox_class: str,
) -> PairedStratum:
    """Map per-arm ADR-026 classes to an ADR-026 paired feasibility stratum."""
    invalid_tokens = ("invalid/unrepresentable", "certifiably unreachable")
    if fourbar_class in invalid_tokens or gearbox_class in invalid_tokens:
        return "paired_invalid"
    fb_direct = fourbar_class in (
        TASK_DIRECT_LOCAL_FEASIBLE,
        "already satisfied",
    )
    gb_direct = gearbox_class in (
        TASK_DIRECT_LOCAL_FEASIBLE,
        "already satisfied",
    )
    if fb_direct and gb_direct:
        return "both_direct"
    if fb_direct and not gb_direct:
        return "fourbar_only_direct"
    if gb_direct and not fb_direct:
        return "gearbox_only_direct"
    return "neither_direct"


def presearch_descriptors(
    arm: SamplingSmokeArm,
    task: FreeSpaceBankTask,
    bank: FreeSpaceTaskBank,
    problem: PlanningProblem,
    *,
    task_class: str,
    class_extras: dict[str, Any],
    goal_candidates: list[PhysicalState],
) -> dict[str, Any]:
    """Build the pre-search descriptor record for one mechanism-task."""
    start = problem.start
    tip = tip_position(arm, start)
    tip_dist = float(np.linalg.norm(tip - task.goal_center))
    size = assign_size_stratum(tip_dist, bank.size_bins)
    direct_u = None
    direct_q = None
    if goal_candidates:
        g0 = goal_candidates[0]
        direct_u = float(np.linalg.norm(g0.u - start.u))
        direct_q = float(np.linalg.norm(g0.q - start.q))
    return {
        "task_id": task.task_id,
        "mechanism": arm.name,
        "task_class": task_class,
        "size_stratum": size,
        "tip_distance": tip_dist,
        "goal_radius": float(task.goal_radius),
        "goal_center": task.goal_center.tolist(),
        "start_tip": tip.tolist(),
        "direct_u_distance": direct_u,
        "direct_q_distance": direct_q,
        "goal_region_descriptor": {
            "type": "cartesian_disk",
            "center": task.goal_center.tolist(),
            "radius": float(task.goal_radius),
        },
        **class_extras,
    }


__all__ = [
    "PairedStratum",
    "assign_size_stratum",
    "classify_problem_presearch",
    "paired_stratum_from_classes",
    "presearch_descriptors",
    "tip_position",
    "tip_separation",
]
