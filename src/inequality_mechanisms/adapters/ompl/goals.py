"""OMPL finite goal-state bridge (V3-503)."""

from __future__ import annotations

from typing import Any

from numpy.random import Generator

from inequality_mechanisms.adapters.ompl._availability import require_ompl
from inequality_mechanisms.adapters.ompl.state_space import write_u_to_ompl_state
from inequality_mechanisms.core.goals import (
    CartesianDiskGoal,
    ExactOutputGoal,
    GoalSamplingRequest,
    GoalStateGenerator,
)
from inequality_mechanisms.core.problem import PlanningProblem
from inequality_mechanisms.core.state import PhysicalState, StateCandidate


def _goal_descriptor(problem: PlanningProblem) -> dict[str, Any]:
    goal = problem.goal
    if isinstance(goal, ExactOutputGoal):
        return {"type": "exact_output", "tolerance": float(goal.tolerance)}
    if isinstance(goal, CartesianDiskGoal):
        return {
            "type": "cartesian_disk",
            "center": goal.center.tolist(),
            "radius": float(goal.radius),
        }
    return {"type": type(goal).__name__}


def select_and_build_goal(
    si: Any,
    space: Any,
    problem: PlanningProblem,
    *,
    goal_generator: GoalStateGenerator | None,
    max_candidates: int,
    rng: Generator | None,
) -> tuple[Any, list[PhysicalState], dict[str, Any]]:
    """Realize a Version 3 goal predicate as finite OMPL ``GoalStates``."""
    ob, _og = require_ompl()
    raw: list[StateCandidate]
    if isinstance(problem.goal, ExactOutputGoal):
        raw = list(problem.robot.states_from_output(problem.goal.q_goal))
    else:
        if goal_generator is None:
            raise ValueError("goal_generator required for non-exact OMPL goals")
        seed = None if rng is None else int(rng.integers(0, 2**31 - 1))
        request = GoalSamplingRequest(max_candidates=max_candidates, seed=seed)
        raw = list(goal_generator.generate(problem.robot, problem.goal, request))

    accepted = [cand for cand in raw if problem.scene.state_is_valid(cand.state)]
    accepted = accepted[:max_candidates]
    candidates = [cand.state for cand in accepted]
    ik_families = sorted(
        {str(cand.provenance.get("ik_family", "unknown")) for cand in accepted}
    )
    metadata = {
        "goal_representation": "finite_goal_states",
        "goal_region_descriptor": _goal_descriptor(problem),
        "goal_samples_generated": len(raw),
        "goal_samples_accepted": len(accepted),
        "discrete_goal_state_count": len(candidates),
        "ik_families": ik_families,
    }

    goal = ob.GoalStates(si)
    for cand in candidates:
        st = ob.State(space)
        write_u_to_ompl_state(space, st(), cand.u)
        goal.addState(st)
    return goal, candidates, metadata
