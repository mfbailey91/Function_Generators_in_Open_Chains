"""OMPL goal bridges for ExactOutputGoal and Cartesian disk goals (V3-503)."""

from __future__ import annotations

from typing import Any

from numpy.random import Generator

from inequality_mechanisms.adapters.ompl._availability import require_ompl
from inequality_mechanisms.adapters.ompl.state_space import write_u_to_ompl_state
from inequality_mechanisms.core.goals import GoalStateGenerator
from inequality_mechanisms.core.problem import PlanningProblem
from inequality_mechanisms.core.state import PhysicalState
from inequality_mechanisms.planners.sampling_space import select_goal_states


def select_and_build_goal(
    si: Any,
    space: Any,
    problem: PlanningProblem,
    *,
    goal_generator: GoalStateGenerator | None,
    max_candidates: int,
    rng: Generator | None,
) -> tuple[Any, list[PhysicalState]]:
    """Build an OMPL ``GoalStates`` from Version 3 goal candidates.

    Returns
    -------
    goal, candidates
        OMPL goal object and the physical candidates used to populate it.
    """
    ob, _og = require_ompl()
    candidates = select_goal_states(
        problem,
        goal_generator=goal_generator,
        max_candidates=max_candidates,
        rng=rng,
    )
    goal = ob.GoalStates(si)
    for cand in candidates:
        st = ob.State(space)
        write_u_to_ompl_state(space, st(), cand.u)
        goal.addState(st)
    return goal, candidates
