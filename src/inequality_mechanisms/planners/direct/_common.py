"""Shared helpers for Version 3 direct planners."""

from __future__ import annotations

import time
from typing import Any

import numpy as np

from inequality_mechanisms.benchmarks.classification import (
    classify_direct_attempt,
)
from inequality_mechanisms.core.goal_residuals import (
    GoalResidualReport,
    build_goal_residual_report,
)
from inequality_mechanisms.core.goals import GoalSamplingRequest, GoalStateGenerator
from inequality_mechanisms.core.local_motion import LocalMotion, LocalMotionModel
from inequality_mechanisms.core.objectives import (
    ActuatorTravelObjective,
    IncrementalPlanningObjective,
)
from inequality_mechanisms.core.problem import PlanningProblem
from inequality_mechanisms.core.results import (
    PlanningResult,
    PlanningStatus,
    ResultProvenance,
    Trajectory,
)
from inequality_mechanisms.core.state import PhysicalState, StateCandidate
from inequality_mechanisms.core.trajectory_metrics import path_metrics_from_motion_samples


def path_lengths_from_motion(
    motion: LocalMotion,
    *,
    robot: Any,
) -> tuple[float, float, float | None]:
    """Return ``(length_u, length_q, length_x)`` from connector samples."""
    metrics = path_metrics_from_motion_samples(
        sample_u=np.asarray(motion.parameters["sample_u"], dtype=np.float64),
        sample_q=np.asarray(motion.parameters["sample_q"], dtype=np.float64),
        actuator_path_length=float(motion.parameters["actuator_path_length"]),
        robot=robot,
        assembly_state=motion.start.assembly_state,
    )
    return metrics.length_u, metrics.length_q, metrics.length_x


def _goal_usable(problem: PlanningProblem) -> bool:
    try:
        _ = problem.goal.residual(problem.start)
        return True
    except (NotImplementedError, ValueError, TypeError):
        return False


def solve_with_direct_connector(
    problem: PlanningProblem,
    *,
    connector: LocalMotionModel,
    connector_policy: str,
    goal_generator: GoalStateGenerator,
    planner_id: str,
    max_candidates: int = 8,
    code_revision: str | None = None,
) -> PlanningResult:
    """Classify then attempt ``connector`` to generated goal candidates."""
    t0 = time.perf_counter()
    start_valid = problem.scene.state_is_valid(problem.start)
    goal_usable = _goal_usable(problem)
    already = bool(goal_usable and problem.goal.satisfied(problem.start))

    def _finish(
        *,
        status: PlanningStatus,
        task_class: str,
        trajectory: Trajectory | None,
        selected: PhysicalState | None,
        cost: float | None,
        length_u: float | None,
        length_q: float | None,
        length_x: float | None,
        metrics: dict[str, Any],
        state_checks: int | None = None,
        motion_checks: int | None = None,
        candidate: StateCandidate | None = None,
        residual_state: PhysicalState | None = None,
    ) -> PlanningResult:
        elapsed = time.perf_counter() - t0
        report: GoalResidualReport | None = None
        residual = None
        state_for_residual = residual_state if residual_state is not None else selected
        if state_for_residual is not None and goal_usable:
            report = build_goal_residual_report(
                problem.goal,
                state_for_residual,
                candidate=candidate,
            )
            residual = report.physical
        return PlanningResult(
            status=status,
            trajectory=trajectory,
            selected_goal_state=selected,
            selected_goal_candidate=candidate,
            total_wall_time_s=elapsed,
            query_time_s=elapsed,
            objective_cost=cost,
            path_length_u=length_u,
            path_length_q=length_q,
            path_length_x=length_x,
            task_class=task_class,
            final_goal_residual=residual,
            goal_residuals=report,
            planner_metrics=metrics,
            provenance=ResultProvenance(
                architecture_version=3,
                code_revision=code_revision,
                planner_id=planner_id,
            ),
            state_validity_checks=state_checks,
            motion_validity_checks=motion_checks,
        )

    base_metrics: dict[str, Any] = {
        "direct": {
            "direct_connector_policy": connector_policy,
            "candidate_count": 0,
            "ik_families": [],
        }
    }

    if not start_valid or not goal_usable:
        task_class = classify_direct_attempt(
            start_valid=start_valid,
            goal_usable=goal_usable,
            already_satisfied=False,
            candidates_representable=False,
            connector_succeeded=False,
        )
        return _finish(
            status=PlanningStatus.INVALID,
            task_class=task_class,
            trajectory=None,
            selected=None,
            cost=None,
            length_u=None,
            length_q=None,
            length_x=None,
            residual_state=problem.start if goal_usable else None,
            metrics=base_metrics,
            state_checks=1,
        )

    if already:
        task_class = classify_direct_attempt(
            start_valid=True,
            goal_usable=True,
            already_satisfied=True,
            candidates_representable=True,
            connector_succeeded=False,
        )
        return _finish(
            status=PlanningStatus.SUCCESS,
            task_class=task_class,
            trajectory=Trajectory(states=()),
            selected=problem.start,
            cost=0.0,
            length_u=0.0,
            length_q=0.0,
            length_x=0.0,
            metrics=base_metrics,
            state_checks=1,
        )

    request = GoalSamplingRequest(max_candidates=max_candidates)
    candidates = list(
        goal_generator.generate(problem.robot, problem.goal, request)
    )
    # Keep only scene-valid candidates.
    valid_candidates = [
        c for c in candidates if problem.scene.state_is_valid(c.state)
    ]
    ik_families = [
        str(c.provenance.get("ik_family", "unknown")) for c in valid_candidates
    ]
    base_metrics["direct"]["candidate_count"] = len(valid_candidates)
    base_metrics["direct"]["ik_families"] = ik_families

    if not valid_candidates:
        task_class = classify_direct_attempt(
            start_valid=True,
            goal_usable=True,
            already_satisfied=False,
            candidates_representable=False,
            connector_succeeded=False,
        )
        return _finish(
            status=PlanningStatus.INVALID,
            task_class=task_class,
            trajectory=None,
            selected=None,
            cost=None,
            length_u=None,
            length_q=None,
            length_x=None,
            residual_state=problem.start,
            metrics=base_metrics,
            state_checks=1 + len(candidates),
        )

    if not isinstance(problem.objective, ActuatorTravelObjective):
        if not isinstance(problem.objective, IncrementalPlanningObjective):
            raise ValueError(
                "direct planners require ActuatorTravelObjective "
                f"(or IncrementalPlanningObjective), got "
                f"{type(problem.objective).__name__}"
            )

    objective = problem.objective
    best: tuple[float, LocalMotion, StateCandidate] | None = None
    motion_checks = 0
    state_checks = 1 + len(candidates)

    for cand in valid_candidates:
        motion = connector.connect(problem.start, cand.state)
        if motion is None:
            continue
        motion_checks += 1
        if not problem.scene.motion_is_valid(motion):
            continue
        if not problem.goal.satisfied(cand.state):
            continue
        cost = float(objective.motion_cost(motion))  # type: ignore[attr-defined]
        if best is None or cost < best[0]:
            best = (cost, motion, cand)

    if best is None:
        task_class = classify_direct_attempt(
            start_valid=True,
            goal_usable=True,
            already_satisfied=False,
            candidates_representable=True,
            connector_succeeded=False,
        )
        return _finish(
            status=PlanningStatus.UNSOLVED,
            task_class=task_class,
            trajectory=None,
            selected=None,
            cost=None,
            length_u=None,
            length_q=None,
            length_x=None,
            residual_state=problem.start,
            metrics=base_metrics,
            state_checks=state_checks,
            motion_checks=motion_checks,
        )

    cost, motion, selected_cand = best
    selected = selected_cand.state
    length_u, length_q, length_x = path_lengths_from_motion(
        motion, robot=problem.robot
    )
    task_class = classify_direct_attempt(
        start_valid=True,
        goal_usable=True,
        already_satisfied=False,
        candidates_representable=True,
        connector_succeeded=True,
    )
    return _finish(
        status=PlanningStatus.SUCCESS,
        task_class=task_class,
        trajectory=Trajectory(states=(problem.start, selected)),
        selected=selected,
        candidate=selected_cand,
        cost=cost,
        length_u=length_u,
        length_q=length_q,
        length_x=length_x,
        metrics=base_metrics,
        state_checks=state_checks,
        motion_checks=motion_checks,
    )
