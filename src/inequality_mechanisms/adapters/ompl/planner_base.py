"""Shared OMPL planner solve path returning a Version 3 PlanningResult (V3-504).

V4-232 keeps this module as the compatibility orchestrator. PRM and RRTConnect
continue to call :func:`solve_with_ompl_planner` with one ``planner.solve``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from inequality_mechanisms.adapters.ompl.planner_geometry import primary_ompl_geometry
from inequality_mechanisms.adapters.ompl.session import (
    OmplAdapterConfig,
    _canonicalize_exact_start,
    _solution_flags,
    build_ompl_session,
    configure_goal,
    configure_objective,
    extract_path_states,
    finalize_ompl_result,
    run_single_shot,
)
from inequality_mechanisms.core.goals import GoalStateGenerator
from inequality_mechanisms.core.problem import PlanningProblem
from inequality_mechanisms.core.results import PlanningResult

__all__ = [
    "_canonicalize_exact_start",
    "_solution_flags",
    "extract_path_states",
    "solve_with_ompl_planner",
]


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
    trace_sink: Any | None = None,
) -> PlanningResult:
    """Classify, set up OMPL, solve once, and return a Version 3 ``PlanningResult``.

    Parameters
    ----------
    make_planner
        Callable ``si -> OMPL planner`` (e.g. ``lambda si: og.PRM(si)``).
    trace_sink
        Optional audit sink. Only a final ``PlannerData`` snapshot is emitted;
        stepwise OMPL history is marked unavailable.
    """
    config = OmplAdapterConfig(
        planner_id=planner_id,
        seed=seed,
        repetition_index=repetition_index,
        code_revision=code_revision,
        goal_generator=goal_generator,
        max_goal_candidates=max_goal_candidates,
        solve_time_s=solve_time_s,
        extras_base=extras_base,
        trace_sink=trace_sink,
        geometry=primary_ompl_geometry(),
    )
    session = build_ompl_session(problem, config)
    if session.early_result is not None:
        return session.early_result
    configure_goal(session, frozen_candidates=None)
    if session.early_result is not None:
        return session.early_result
    configure_objective(session)
    planner = make_planner(session.si)
    planner.setProblemDefinition(session.pdef)
    planner.setup()
    path = run_single_shot(session, planner)
    return finalize_ompl_result(session, planner, path)
