"""Shared OMPL solve session extracted from the V3.5 one-shot path (V4-232).

Importing this module must not import ``ompl``. Session construction calls
``require_ompl()`` only when building space information.
"""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from inequality_mechanisms.adapters.ompl._availability import (
    ompl_version_string,
    require_ompl,
)
from inequality_mechanisms.adapters.ompl.binding import checkpoint_costs_nonincreasing
from inequality_mechanisms.adapters.ompl.goals import (
    _goal_descriptor,
    select_and_build_goal,
)
from inequality_mechanisms.adapters.ompl.metrics import (
    attach_checkpoint_summaries,
    namespace_family_metrics,
    planner_data_metrics,
)
from inequality_mechanisms.adapters.ompl.objective import build_ompl_objective
from inequality_mechanisms.adapters.ompl.planner_geometry import (
    PlannerGeometryRecord,
    primary_ompl_geometry,
)
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
from inequality_mechanisms.core.goal_residuals import (
    GoalResidualReport,
    build_goal_residual_report,
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
from inequality_mechanisms.core.state import PhysicalState, StateCandidate
from inequality_mechanisms.planners.sampling_rng import (
    SeededRun,
    make_generator,
    seed_provenance_extras,
)
from inequality_mechanisms.planners.sampling_space import (
    actuator_bounds,
    direct_connector_available,
    match_selected_candidate,
    path_length_q,
    path_length_x,
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
        import ompl.util as ou  # type: ignore[import-not-found, unused-ignore]

        if hasattr(ou, "RNG") and hasattr(ou.RNG, "setSeed"):
            ou.RNG.setSeed(int(seed) % (2**32))
            return True
    except Exception:
        pass
    return False


def _solution_flags(pdef: Any) -> tuple[bool, bool, float | None]:
    """Return ``(has_any, has_exact, difference)`` without mixing approximate paths."""
    has_any = bool(pdef.hasSolution())
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


def assert_ompl_problem_supported(problem: PlanningProblem, *, planner_id: str) -> None:
    """Fail closed on unsupported objective, local motion, or missing bounds.

    These gates run before planner construction and before ``require_ompl``.
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
    try:
        actuator_bounds(problem.robot)
    except ValueError as exc:
        raise ValueError(
            f"{planner_id} requires a robot with certified actuator bounds"
        ) from exc


def _best_path_cost(pdef: Any) -> float | None:
    if pdef is None or not hasattr(pdef, "getSolutionPath"):
        return None
    try:
        path = pdef.getSolutionPath()
    except Exception:
        return None
    if path is None or not hasattr(path, "length"):
        return None
    try:
        return float(path.length())
    except Exception:
        return None


@dataclass
class OmplAdapterConfig:
    """Constructor-side inputs for an OMPL solve session."""

    planner_id: str
    seed: int
    repetition_index: int
    code_revision: str | None
    goal_generator: GoalStateGenerator | None
    max_goal_candidates: int
    solve_time_s: float
    extras_base: Mapping[str, Any] | None = None
    trace_sink: Any | None = None
    geometry: PlannerGeometryRecord | None = None


@dataclass
class OmplSolveSession:
    """Live OMPL query session (not frozen while OMPL objects are held)."""

    problem: PlanningProblem
    planner_id: str
    geometry: PlannerGeometryRecord
    seed: int
    repetition_index: int
    code_revision: str | None
    goal_generator: GoalStateGenerator | None
    max_goal_candidates: int
    solve_time_s: float
    extras: dict[str, Any]
    ompl_metrics: dict[str, Any]
    t0: float
    rng: Any
    start_valid: bool
    goal_usable: bool
    already_satisfied: bool
    trace_sink: Any | None = None
    space: Any | None = None
    si: Any | None = None
    counters: OmplValidityCounters | None = None
    assembly: dict[str, Any] | None = None
    owned_ompl_states: list[Any] = field(default_factory=list)
    start_ompl: Any | None = None
    pdef: Any | None = None
    candidates: list[StateCandidate] = field(default_factory=list)
    goal_ompl: Any | None = None
    goal_metadata: dict[str, Any] = field(default_factory=dict)
    task_class: str | None = None
    presearch_state_checks: int = 1
    direct_checks: int = 0
    query_s: float | None = None
    seed_applied: bool = False
    early_result: PlanningResult | None = None
    checkpoint_records: list[dict[str, Any]] = field(default_factory=list)

    def finish(
        self,
        *,
        status: PlanningStatus,
        task_class: str,
        trajectory: Trajectory | None,
        selected: PhysicalState | None,
        cost: float | None,
        length_u: float | None,
        length_q: float | None,
        length_x: float | None = None,
        residual_state: PhysicalState | None = None,
        candidate: StateCandidate | None = None,
        query_s: float | None = None,
        state_checks: int | None = None,
        motion_checks: int | None = None,
    ) -> PlanningResult:
        """Assemble a Version 3 ``PlanningResult`` from the live session."""
        total = time.perf_counter() - self.t0
        report: GoalResidualReport | None = None
        residual = None
        state_for_residual = residual_state if residual_state is not None else selected
        if state_for_residual is not None and self.goal_usable:
            report = build_goal_residual_report(
                self.problem.goal,
                state_for_residual,
                candidate=candidate,
            )
            residual = report.physical
        return PlanningResult(
            status=status,
            trajectory=trajectory,
            selected_goal_state=selected,
            selected_goal_candidate=candidate,
            total_wall_time_s=total,
            query_time_s=query_s if query_s is not None else total,
            objective_cost=cost,
            path_length_u=length_u,
            path_length_q=length_q,
            path_length_x=length_x,
            task_class=task_class,
            final_goal_residual=residual,
            goal_residuals=report,
            planner_metrics={"ompl": dict(self.ompl_metrics)},
            provenance=ResultProvenance(
                architecture_version=3,
                code_revision=self.code_revision,
                planner_id=self.planner_id,
                extras=self.extras,
            ),
            state_validity_checks=state_checks,
            motion_validity_checks=motion_checks,
        )


def _record_solution_flags(
    session: OmplSolveSession,
) -> tuple[bool, bool, float | None]:
    has_solution, has_exact_solution, solution_difference = _solution_flags(
        session.pdef
    )
    session.ompl_metrics["ompl_solved"] = has_solution
    session.ompl_metrics["ompl_exact_solution"] = has_exact_solution
    session.ompl_metrics["ompl_approximate_solution"] = bool(
        has_solution and not has_exact_solution
    )
    session.ompl_metrics["ompl_solution_difference"] = solution_difference
    return has_solution, has_exact_solution, solution_difference


def _emit_planner_data_snapshot(
    session: OmplSolveSession, planner: Any
) -> dict[str, Any]:
    snapshot = (
        planner_data_metrics(session.si, planner) if session.si is not None else {}
    )
    session.ompl_metrics["planner_data"] = snapshot
    session.ompl_metrics["stepwise_history"] = "unavailable"
    if session.trace_sink is not None:
        session.trace_sink.record(
            family="ompl",
            phase="snapshot",
            event_type="planner_data_final",
            payload={
                "planner_id": session.planner_id,
                "planner_data": dict(snapshot),
                "stepwise_history": "unavailable",
            },
        )
    return snapshot


def build_ompl_session(
    problem: PlanningProblem,
    adapter_config: OmplAdapterConfig,
) -> OmplSolveSession:
    """Classify the query, seed extras, and build space information when needed."""
    planner_id = adapter_config.planner_id
    assert_ompl_problem_supported(problem, planner_id=planner_id)
    geometry = adapter_config.geometry or primary_ompl_geometry()
    require_ompl()
    t0 = time.perf_counter()
    run = SeededRun(
        seed=adapter_config.seed, repetition_index=adapter_config.repetition_index
    )
    rng = make_generator(run.seed, repetition_index=run.repetition_index)
    extras = seed_provenance_extras(run, planner_id=planner_id)
    extras["seed_protocol"] = "v3_5_ompl_process_global_best_effort"
    extras["ompl_version"] = ompl_version_string()
    extras["nn_distance"] = "euclidean_u"
    extras["ompl_seed_requested"] = int(run.seed)
    extras["ompl_seed_scope"] = "process_global_best_effort"
    extras["reproducibility_contract"] = "not_claimed_in_process"
    if adapter_config.extras_base:
        extras.update(dict(adapter_config.extras_base))
    namespace_family_metrics(extras)
    extras["planner_geometry"] = geometry.to_dict()

    seed_applied = _apply_ompl_seed(run.seed)
    extras["ompl_seed_applied"] = seed_applied

    start_valid = problem.scene.state_is_valid(problem.start)
    goal_usable = _goal_usable(problem)
    already = bool(goal_usable and problem.goal.satisfied(problem.start))

    ompl_metrics: dict[str, Any] = {
        "nn_distance": "euclidean_u",
        "ompl_version": ompl_version_string(),
        "ompl_seed_applied": seed_applied,
        "ompl_seed_requested": int(adapter_config.seed),
        "ompl_seed_scope": "process_global_best_effort",
        "reproducibility_contract": "not_claimed_in_process",
        "seed": int(adapter_config.seed),
        "seed_protocol": "v3_5_ompl_process_global_best_effort",
        "repetition_index": int(adapter_config.repetition_index),
        "solve_time_budget_s": float(adapter_config.solve_time_s),
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

    session = OmplSolveSession(
        problem=problem,
        planner_id=planner_id,
        geometry=geometry,
        seed=adapter_config.seed,
        repetition_index=adapter_config.repetition_index,
        code_revision=adapter_config.code_revision,
        goal_generator=adapter_config.goal_generator,
        max_goal_candidates=adapter_config.max_goal_candidates,
        solve_time_s=adapter_config.solve_time_s,
        extras=extras,
        ompl_metrics=ompl_metrics,
        t0=t0,
        rng=rng,
        start_valid=start_valid,
        goal_usable=goal_usable,
        already_satisfied=already,
        trace_sink=adapter_config.trace_sink,
        seed_applied=seed_applied,
    )

    if not start_valid or not goal_usable:
        session.early_result = session.finish(
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
            residual_state=problem.start if goal_usable else None,
            state_checks=1,
        )
        return session

    if already:
        session.early_result = session.finish(
            status=PlanningStatus.SUCCESS,
            task_class=TASK_ALREADY_SATISFIED,
            trajectory=Trajectory(states=()),
            selected=problem.start,
            cost=0.0,
            length_u=0.0,
            length_q=0.0,
            query_s=0.0,
            state_checks=1,
        )
        return session

    ob, _og = require_ompl()
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

    start_state = space.allocState()
    write_u_to_ompl_state(space, start_state, problem.start.u)
    pdef = ob.ProblemDefinition(si)
    pdef.addStartState(start_state)

    session.space = space
    session.si = si
    session.counters = counters
    session.assembly = assembly
    session.owned_ompl_states = [start_state]
    session.start_ompl = start_state
    session.pdef = pdef
    return session


def configure_goal(
    session: OmplSolveSession,
    frozen_candidates: Sequence[StateCandidate] | None = None,
) -> OmplSolveSession:
    """Attach finite OMPL goal states from generated or frozen candidates."""
    if session.early_result is not None:
        return session
    space = session.space
    pdef = session.pdef
    if space is None or pdef is None:
        raise RuntimeError("configure_goal requires an initialized OMPL space")
    problem = session.problem
    ob, _og = require_ompl()
    if frozen_candidates is not None:
        candidates = list(frozen_candidates)
        ik_families = sorted(
            {str(cand.provenance.get("ik_family", "unknown")) for cand in candidates}
        )
        metadata = {
            "goal_representation": "finite_goal_states",
            "goal_region_descriptor": _goal_descriptor(problem),
            "goal_samples_generated": len(candidates),
            "goal_samples_accepted": len(candidates),
            "discrete_goal_state_count": len(candidates),
            "ik_families": ik_families,
        }
        goal_ompl = ob.GoalStates(session.si)
        owned_goal_states: list[Any] = []
        for cand in candidates:
            st = space.allocState()
            write_u_to_ompl_state(space, st, cand.state.u)
            goal_ompl.addState(st)
            owned_goal_states.append(st)
    else:
        try:
            goal_ompl, candidates, metadata, owned_goal_states = select_and_build_goal(
                session.si,
                session.space,
                problem,
                goal_generator=session.goal_generator,
                max_candidates=session.max_goal_candidates,
                rng=session.rng,
            )
        except ValueError:
            session.early_result = session.finish(
                status=PlanningStatus.INVALID,
                task_class=TASK_INVALID_UNREPRESENTABLE,
                trajectory=None,
                selected=None,
                cost=None,
                length_u=None,
                length_q=None,
                residual_state=problem.start,
                state_checks=1,
            )
            return session

    session.owned_ompl_states.extend(owned_goal_states)
    session.ompl_metrics.update(metadata)
    session.candidates = list(candidates)
    session.goal_ompl = goal_ompl
    session.goal_metadata = dict(metadata)
    generated = metadata["goal_samples_generated"]
    if not isinstance(generated, int):
        raise TypeError("goal_samples_generated must be int")
    session.presearch_state_checks = 1 + generated

    if not candidates:
        session.early_result = session.finish(
            status=PlanningStatus.INVALID,
            task_class=TASK_INVALID_UNREPRESENTABLE,
            trajectory=None,
            selected=None,
            cost=None,
            length_u=None,
            length_q=None,
            residual_state=problem.start,
            state_checks=session.presearch_state_checks,
        )
        return session

    goal_states = [c.state for c in candidates]
    direct_succeeded, direct_checks = direct_connector_available(problem, goal_states)
    session.direct_checks = int(direct_checks)
    session.ompl_metrics["direct_connector_available"] = direct_succeeded
    session.task_class = classify_direct_attempt(
        start_valid=True,
        goal_usable=True,
        already_satisfied=False,
        candidates_representable=True,
        connector_succeeded=direct_succeeded,
    )
    pdef.setGoal(goal_ompl)
    return session


def configure_objective(session: OmplSolveSession) -> OmplSolveSession:
    """Attach the actuator-travel path-length objective to the problem definition."""
    if session.early_result is not None:
        return session
    pdef = session.pdef
    if pdef is None:
        raise RuntimeError("configure_objective requires a problem definition")
    ompl_objective, objective_metadata = build_ompl_objective(
        session.si, session.problem
    )
    pdef.setOptimizationObjective(ompl_objective)
    session.ompl_metrics.update(objective_metadata)
    session.extras.update(objective_metadata)
    return session


def run_single_shot(session: OmplSolveSession, planner: Any) -> Any:
    """Run one ``planner.solve`` call and record the final PlannerData snapshot."""
    t_query = time.perf_counter()
    status = planner.solve(float(session.solve_time_s))
    session.query_s = time.perf_counter() - t_query
    session.ompl_metrics["ompl_status"] = str(status)
    _emit_planner_data_snapshot(session, planner)
    _has_solution, has_exact_solution, _difference = _record_solution_flags(session)
    if not has_exact_solution:
        return None
    pdef = session.pdef
    if pdef is None:
        return None
    return pdef.getSolutionPath()


def run_checkpointed(
    session: OmplSolveSession,
    planner: Any,
    checkpoints: Sequence[float],
) -> Any:
    """Loop remaining-time slices and record exactness / cost / PlannerData.

    Existing PRM / RRTConnect rows keep one ``planner.solve`` via
    :func:`run_single_shot`. This helper is for later optimizing wrappers.
    """
    times = [float(t) for t in checkpoints]
    if not times:
        raise ValueError("checkpoints must be a nonempty strictly increasing sequence")
    if any(t < 0.0 for t in times):
        raise ValueError("checkpoints must be nonnegative")
    if any(times[i] <= times[i - 1] for i in range(1, len(times))):
        raise ValueError("checkpoints must be strictly increasing")

    query_s = 0.0
    prev = 0.0
    records: list[dict[str, Any]] = []
    last_path: Any = None
    for t in times:
        slice_s = t - prev
        prev = t
        t_query = time.perf_counter()
        status = planner.solve(float(slice_s)) if slice_s > 0.0 else None
        query_s += time.perf_counter() - t_query
        has_solution, has_exact_solution, solution_difference = _solution_flags(
            session.pdef
        )
        snapshot = (
            planner_data_metrics(session.si, planner) if session.si is not None else {}
        )
        best_cost = _best_path_cost(session.pdef) if has_exact_solution else None
        if has_exact_solution:
            try:
                pdef = session.pdef
                last_path = None if pdef is None else pdef.getSolutionPath()
            except Exception:
                last_path = None
        records.append(
            {
                "checkpoint_s": t,
                "remaining_s": slice_s,
                "ompl_status": str(status),
                "ompl_solved": has_solution,
                "ompl_exact_solution": has_exact_solution,
                "ompl_solution_difference": solution_difference,
                "best_cost": best_cost,
                "planner_data": dict(snapshot),
            }
        )

    session.query_s = query_s
    session.checkpoint_records = records
    session.ompl_metrics["checkpoints"] = list(records)
    last_snapshot = records[-1]["planner_data"] if records else {}
    session.ompl_metrics["planner_data"] = dict(last_snapshot)
    session.ompl_metrics["stepwise_history"] = "unavailable"
    if session.trace_sink is not None:
        session.trace_sink.record(
            family="ompl",
            phase="snapshot",
            event_type="planner_data_final",
            payload={
                "planner_id": session.planner_id,
                "planner_data": dict(last_snapshot),
                "stepwise_history": "unavailable",
            },
        )
    _record_solution_flags(session)
    session.ompl_metrics["ompl_status"] = str(records[-1]["ompl_status"])
    session.ompl_metrics["checkpoint_cost_nonincreasing"] = (
        checkpoint_costs_nonincreasing(records)
    )
    attach_checkpoint_summaries(session, planner)
    has_exact = bool(session.ompl_metrics.get("ompl_exact_solution"))
    if not has_exact:
        return None
    return last_path


def finalize_ompl_result(
    session: OmplSolveSession,
    planner: Any,
    path: Any,
) -> PlanningResult:
    """Convert an exact OMPL path into a Version 3 ``PlanningResult``."""
    attach_checkpoint_summaries(session, planner)
    problem = session.problem
    task_class = session.task_class
    if task_class is None:
        task_class = classify_direct_attempt(
            start_valid=session.start_valid,
            goal_usable=session.goal_usable,
            already_satisfied=False,
            candidates_representable=bool(session.candidates),
            connector_succeeded=bool(
                session.ompl_metrics.get("direct_connector_available")
            ),
        )
    counters = session.counters or OmplValidityCounters()
    state_checks = session.presearch_state_checks + counters.state_checks
    motion_checks = session.direct_checks + counters.motion_checks

    if path is None:
        return session.finish(
            status=PlanningStatus.UNSOLVED,
            task_class=task_class,
            trajectory=None,
            selected=None,
            cost=None,
            length_u=None,
            length_q=None,
            residual_state=problem.start,
            query_s=session.query_s,
            state_checks=state_checks,
            motion_checks=motion_checks,
        )

    if hasattr(path, "interpolate"):
        try:
            path.interpolate()
        except Exception:
            pass

    states = extract_path_states(
        problem.robot, session.space, path, assembly_state=session.assembly
    )
    if not states:
        return session.finish(
            status=PlanningStatus.UNSOLVED,
            task_class=task_class,
            trajectory=None,
            selected=None,
            cost=None,
            length_u=None,
            length_q=None,
            residual_state=problem.start,
            query_s=session.query_s,
            state_checks=state_checks,
            motion_checks=motion_checks,
        )

    states, start_residual_u = _canonicalize_exact_start(
        states, problem.start, planner_id=session.planner_id
    )
    session.ompl_metrics["exact_start_residual_u"] = start_residual_u

    selected = states[-1]
    selected_goal_satisfied = bool(problem.goal.satisfied(selected))
    session.ompl_metrics["selected_goal_satisfied"] = selected_goal_satisfied
    if not selected_goal_satisfied:
        return session.finish(
            status=PlanningStatus.UNSOLVED,
            task_class=task_class,
            trajectory=None,
            selected=None,
            cost=None,
            length_u=None,
            length_q=None,
            residual_state=selected,
            query_s=session.query_s,
            state_checks=state_checks,
            motion_checks=motion_checks,
        )

    selected_cand = match_selected_candidate(
        session.candidates, selected, atol=float(ROUND_TRIP_TOL)
    )
    cost = float(problem.objective.trajectory_cost(states))
    session.ompl_metrics["objective_cost"] = cost
    session.ompl_metrics["objective_cost_units"] = "actuator_travel_polyline"
    last_exact = session.ompl_metrics.get("final_exact_cost")
    if last_exact is not None:
        session.ompl_metrics["last_exact_checkpoint_best_cost"] = last_exact
        # Checkpoint best_cost is OMPL path.length() on the session-owned
        # solution; objective_cost is ActuatorTravelObjective on the
        # extracted polyline. Compare only the session-owned best_cost chain.
    return session.finish(
        status=PlanningStatus.SUCCESS,
        task_class=task_class,
        trajectory=Trajectory(states=states),
        selected=selected,
        candidate=selected_cand,
        cost=cost,
        length_u=cost,
        length_q=path_length_q(states),
        length_x=path_length_x(states, robot=problem.robot),
        query_s=session.query_s,
        state_checks=state_checks,
        motion_checks=motion_checks,
    )
