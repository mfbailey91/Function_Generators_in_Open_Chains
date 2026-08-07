"""Shared OMPL planner solve path returning Version 3 PlanningResult (V3-504)."""

from __future__ import annotations

import time
from typing import Any, Callable

import numpy as np

from inequality_mechanisms.adapters.ompl._availability import (
    ompl_version_string,
    require_ompl,
)
from inequality_mechanisms.adapters.ompl.goals import select_and_build_goal
from inequality_mechanisms.adapters.ompl.metrics import planner_data_metrics
from inequality_mechanisms.adapters.ompl.objective import build_ompl_objective
from inequality_mechanisms.adapters.ompl.state_space import (
    ROUND_TRIP_TOL,
    build_actuator_state_space,
    physical_state_from_ompl,
    write_u_to_ompl_state,
)
from inequality_mechanisms.adapters.ompl.validity import (
    OmplValidityCounters,
    make_motion_validator,
    make_state_validity_checker,
)
from inequality_mechanisms.benchmarks.classification import (
    TASK_ALREADY_SATISFIED,
    TASK_INVALID_UNREPRESENTABLE,
    classify_direct_attempt,
)
from inequality_mechanisms.core.goals import GoalStateGenerator
from inequality_mechanisms.core.local_motion import InputLinearMotion
from inequality_mechanisms.core.objectives import ActuatorTravelObjective
from inequality_mechanisms.core.problem import PlanningProblem
from inequality_mechanisms.core.results import (
    PlanningResult,
    PlanningStatus,
    ResultProvenance,
    Trajectory,
)
from inequality_mechanisms.core.state import PhysicalState
from inequality_mechanisms.planners.sampling_rng import (
    SeededRun,
    make_generator,
    seed_provenance_extras,
)
from inequality_mechanisms.planners.sampling_space import (
    actuator_bounds,
    direct_connector_available,
    path_length_q,
)


def _goal_usable(problem: PlanningProblem) -> bool:
    try:
        _ = problem.goal.residual(problem.start)
        return True
    except (NotImplementedError, ValueError, TypeError):
        return False


def _apply_ompl_seed(seed: int) -> bool:
    """Best-effort process-global OMPL RNG seed request."""
    try:
        import ompl.util as ou  # type: ignore[attr-defined]

        if hasattr(ou, "RNG") and hasattr(ou.RNG, "setSeed"):
            ou.RNG.setSeed(int(seed) % (2**32))
            return True
    except Exception:
        pass
    return False


def _solution_flags(pdef: Any) -> tuple[bool, bool, float | None]:
    """Return ``(has_any, has_exact, difference)`` without conflating approximate paths."""
    has_any = bool(pdef.hasSolution())
    # Fail closed when a binding cannot prove exactness.
    has_exact = (
        bool(pdef.hasExactSolution()) if hasattr(pdef, "hasExactSolution") else False
    )
    difference: float | None = None
    if has_any and hasattr(pdef, "getSolutionDifference"):
        try:
            difference = float(pdef.getSolutionDifference())
        except Exception:
            difference = None
    return has_any, has_exact, difference


def extract_path_states(
    robot: Any,
    space: Any,
    path: Any,
    *,
    assembly_state: dict[str, Any] | None,
) -> tuple[PhysicalState, ...]:
    """Convert an OMPL ``PathGeometric`` into authoritative physical states."""
    states: list[PhysicalState] = []
    n = int(path.getStateCount())
    for i in range(n):
        states.append(
            physical_state_from_ompl(
                robot,
                space,
                path.getState(i),
                assembly_state=assembly_state,
            )
        )
    return tuple(states)


def _canonicalize_exact_start(
    states: tuple[PhysicalState, ...],
    exact_start: PhysicalState,
    *,
    planner_id: str,
) -> tuple[tuple[PhysicalState, ...], float]:
    """Verify the OMPL first waypoint and replace only numerically equivalent state."""
    if not states:
        return states, 0.0
    residual = float(np.linalg.norm(states[0].u - exact_start.u))
    if residual > ROUND_TRIP_TOL:
        raise RuntimeError(
            f"{planner_id} violated exact-start round trip: residual={residual}"
        )
    return (exact_start,) + tuple(states[1:]), residual


def solve_with_ompl_planner(
    problem: PlanningProblem,
    *,
    planner_id: str,
    make_planner: Callable[[Any], Any],
    seed: int,
    repetition_index: int,
    code_revision: str | None,
    goal_generator: GoalStateGenerator | None,
    max_goal_candidates: int,
    solve_time_s: float,
    extras_base: dict[str, Any] | None = None,
) -> PlanningResult:
    """Classify, set up OMPL, solve, and return a Version 3 ``PlanningResult``.

    Parameters
    ----------
    make_planner
        Callable ``si -> OMPL planner`` (e.g. ``lambda si: og.PRM(si)``).
    """
    if not isinstance(problem.objective, ActuatorTravelObjective):
        raise ValueError(
            f"{planner_id} requires ActuatorTravelObjective; "
            f"got {type(problem.objective).__name__}"
        )
    if not isinstance(problem.local_motion, InputLinearMotion):
        raise ValueError(
            f"{planner_id} supports InputLinearMotion only in V3.5; "
            f"got {type(problem.local_motion).__name__}"
        )
    # Reject robots without certified branch bounds (no silent joint fallback).
    try:
        actuator_bounds(problem.robot)
    except ValueError as exc:
        raise ValueError(
            f"{planner_id} requires a robot with certified actuator bounds"
        ) from exc

    ob, _og = require_ompl()
    t0 = time.perf_counter()
    run = SeededRun(seed=seed, repetition_index=repetition_index)
    rng = make_generator(run.seed, repetition_index=run.repetition_index)
    extras = seed_provenance_extras(run, planner_id=planner_id)
    extras["seed_protocol"] = "v3_5_ompl_process_global_best_effort"
    extras["ompl_version"] = ompl_version_string()
    extras["nn_distance"] = "euclidean_u"
    extras["ompl_seed_requested"] = int(run.seed)
    extras["ompl_seed_scope"] = "process_global_best_effort"
    extras["reproducibility_contract"] = "not_claimed_in_process"
    if extras_base:
        extras.update(extras_base)

    seed_applied = _apply_ompl_seed(run.seed)
    extras["ompl_seed_applied"] = seed_applied

    start_valid = problem.scene.state_is_valid(problem.start)
    goal_usable = _goal_usable(problem)
    already = bool(goal_usable and problem.goal.satisfied(problem.start))

    ompl_metrics: dict[str, Any] = {
        "nn_distance": "euclidean_u",
        "ompl_version": ompl_version_string(),
        "ompl_seed_applied": seed_applied,
        "ompl_seed_requested": int(seed),
        "ompl_seed_scope": "process_global_best_effort",
        "reproducibility_contract": "not_claimed_in_process",
        "seed": int(seed),
        "seed_protocol": "v3_5_ompl_process_global_best_effort",
        "repetition_index": int(repetition_index),
        "solve_time_budget_s": float(solve_time_s),
        "direct_connector_policy": str(
            getattr(
                problem.local_motion,
                "model_id",
                type(problem.local_motion).__name__,
            )
        ),
        "direct_connector_available": None,
        "planner_data": {},
        "ompl_solved": False,
    }

    def _finish(
        *,
        status: PlanningStatus,
        task_class: str,
        trajectory: Trajectory | None,
        selected: PhysicalState | None,
        cost: float | None,
        length_u: float | None,
        length_q: float | None,
        residual: Any = None,
        query_s: float | None = None,
        state_checks: int | None = None,
        motion_checks: int | None = None,
    ) -> PlanningResult:
        total = time.perf_counter() - t0
        return PlanningResult(
            status=status,
            trajectory=trajectory,
            selected_goal_state=selected,
            total_wall_time_s=total,
            query_time_s=query_s if query_s is not None else total,
            objective_cost=cost,
            path_length_u=length_u,
            path_length_q=length_q,
            path_length_x=None,
            task_class=task_class,
            final_goal_residual=residual,
            planner_metrics={"ompl": dict(ompl_metrics)},
            provenance=ResultProvenance(
                architecture_version=3,
                code_revision=code_revision,
                planner_id=planner_id,
                extras=extras,
            ),
            state_validity_checks=state_checks,
            motion_validity_checks=motion_checks,
        )

    if not start_valid or not goal_usable:
        return _finish(
            status=PlanningStatus.INVALID,
            task_class=classify_direct_attempt(
                start_valid=start_valid,
                goal_usable=goal_usable,
                already_satisfied=False,
                candidates_representable=False,
                connector_succeeded=False,
            ),
            trajectory=None,
            selected=None,
            cost=None,
            length_u=None,
            length_q=None,
            residual=problem.goal.residual(problem.start) if goal_usable else None,
            state_checks=1,
        )

    if already:
        return _finish(
            status=PlanningStatus.SUCCESS,
            task_class=TASK_ALREADY_SATISFIED,
            trajectory=Trajectory(states=()),
            selected=problem.start,
            cost=0.0,
            length_u=0.0,
            length_q=0.0,
            residual=problem.goal.residual(problem.start),
            query_s=0.0,
            state_checks=1,
        )

    assembly = dict(problem.start.assembly_state)
    space = build_actuator_state_space(problem.robot)
    si = ob.SpaceInformation(space)
    counters = OmplValidityCounters()
    validity = make_state_validity_checker(
        si, problem, space, assembly_state=assembly, counters=counters
    )
    si.setStateValidityChecker(validity)
    connector = problem.local_motion
    si.setMotionValidator(
        make_motion_validator(
            si,
            problem,
            space,
            connector,
            assembly_state=assembly,
            counters=counters,
        )
    )
    si.setup()

    try:
        goal_ompl, candidates, goal_metadata = select_and_build_goal(
            si,
            space,
            problem,
            goal_generator=goal_generator,
            max_candidates=max_goal_candidates,
            rng=rng,
        )
    except ValueError:
        return _finish(
            status=PlanningStatus.INVALID,
            task_class=TASK_INVALID_UNREPRESENTABLE,
            trajectory=None,
            selected=None,
            cost=None,
            length_u=None,
            length_q=None,
            residual=problem.goal.residual(problem.start),
            state_checks=1,
        )

    ompl_metrics.update(goal_metadata)
    presearch_state_checks = 1 + int(goal_metadata["goal_samples_generated"])

    if not candidates:
        return _finish(
            status=PlanningStatus.INVALID,
            task_class=TASK_INVALID_UNREPRESENTABLE,
            trajectory=None,
            selected=None,
            cost=None,
            length_u=None,
            length_q=None,
            residual=problem.goal.residual(problem.start),
            state_checks=presearch_state_checks,
        )

    direct_succeeded, direct_checks = direct_connector_available(problem, candidates)
    ompl_metrics["direct_connector_available"] = direct_succeeded
    task_class = classify_direct_attempt(
        start_valid=True,
        goal_usable=True,
        already_satisfied=False,
        candidates_representable=True,
        connector_succeeded=direct_succeeded,
    )

    start_scoped = ob.State(space)
    write_u_to_ompl_state(space, start_scoped(), problem.start.u)

    pdef = ob.ProblemDefinition(si)
    pdef.addStartState(start_scoped)
    pdef.setGoal(goal_ompl)
    ompl_objective, objective_metadata = build_ompl_objective(si, problem)
    pdef.setOptimizationObjective(ompl_objective)
    ompl_metrics.update(objective_metadata)
    extras.update(objective_metadata)

    planner = make_planner(si)
    planner.setProblemDefinition(pdef)
    planner.setup()

    t_query = time.perf_counter()
    status = planner.solve(float(solve_time_s))
    query_s = time.perf_counter() - t_query
    ompl_metrics["planner_data"] = planner_data_metrics(si, planner)
    ompl_metrics["ompl_status"] = str(status)
    has_solution, has_exact_solution, solution_difference = _solution_flags(pdef)
    ompl_metrics["ompl_solved"] = has_solution
    ompl_metrics["ompl_exact_solution"] = has_exact_solution
    ompl_metrics["ompl_approximate_solution"] = bool(
        has_solution and not has_exact_solution
    )
    ompl_metrics["ompl_solution_difference"] = solution_difference

    if not has_exact_solution:
        return _finish(
            status=PlanningStatus.UNSOLVED,
            task_class=task_class,
            trajectory=None,
            selected=None,
            cost=None,
            length_u=None,
            length_q=None,
            residual=problem.goal.residual(problem.start),
            query_s=query_s,
            state_checks=presearch_state_checks + counters.state_checks,
            motion_checks=direct_checks + counters.motion_checks,
        )

    path = pdef.getSolutionPath()
    # Ensure PathGeometric interface (interpolate optional for denser polyline).
    if hasattr(path, "interpolate"):
        try:
            path.interpolate()
        except Exception:
            pass

    states = extract_path_states(
        problem.robot, space, path, assembly_state=assembly
    )
    if not states:
        return _finish(
            status=PlanningStatus.UNSOLVED,
            task_class=task_class,
            trajectory=None,
            selected=None,
            cost=None,
            length_u=None,
            length_q=None,
            residual=problem.goal.residual(problem.start),
            query_s=query_s,
            state_checks=presearch_state_checks + counters.state_checks,
            motion_checks=direct_checks + counters.motion_checks,
        )

    # Exact start is an adapter invariant; only canonicalize a numerically
    # equivalent first state. A real mismatch is an adapter failure.
    states, start_residual_u = _canonicalize_exact_start(
        states, problem.start, planner_id=planner_id
    )
    ompl_metrics["exact_start_residual_u"] = start_residual_u

    selected = states[-1]
    selected_goal_satisfied = bool(problem.goal.satisfied(selected))
    ompl_metrics["selected_goal_satisfied"] = selected_goal_satisfied
    if not selected_goal_satisfied:
        return _finish(
            status=PlanningStatus.UNSOLVED,
            task_class=task_class,
            trajectory=None,
            selected=None,
            cost=None,
            length_u=None,
            length_q=None,
            residual=problem.goal.residual(selected),
            query_s=query_s,
            state_checks=presearch_state_checks + counters.state_checks,
            motion_checks=direct_checks + counters.motion_checks,
        )

    cost = float(problem.objective.trajectory_cost(states))
    return _finish(
        status=PlanningStatus.SUCCESS,
        task_class=task_class,
        trajectory=Trajectory(states=states),
        selected=selected,
        cost=cost,
        length_u=cost,
        length_q=path_length_q(states),
        residual=problem.goal.residual(selected),
        query_s=query_s,
        state_checks=presearch_state_checks + counters.state_checks,
        motion_checks=direct_checks + counters.motion_checks,
    )
