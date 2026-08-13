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
    PlanarPoseRegionGoal,
)
from inequality_mechanisms.core.problem import PlanningProblem
from inequality_mechanisms.core.state import StateCandidate


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
    if isinstance(goal, PlanarPoseRegionGoal):
        return {
            "type": "planar_pose_region",
            "center": goal.center.tolist(),
            "radius": float(goal.radius),
            "phi_goal": float(goal.phi_goal),
            "orientation_tol": float(goal.orientation_tol),
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
) -> tuple[Any, list[StateCandidate], dict[str, Any], list[Any]]:
    """Realize a Version 3 goal predicate as finite OMPL ``GoalStates``.

    The fourth return value holds allocated OMPL states that must remain alive
    for the lifetime of the returned ``GoalStates`` object (Nanobind does not
    allow attaching Python attributes to the C++ wrapper).

    Accepted ``StateCandidate`` objects retain generator provenance for result
    assembly after solve.
    """
    ob, _og = require_ompl()
    raw: list[StateCandidate]
    if isinstance(problem.goal, ExactOutputGoal):
        raw = list(problem.robot.states_from_output(problem.goal.q_goal))
        accepted: list[StateCandidate] = []
        for cand in raw:
            if not problem.scene.state_is_valid(cand.state):
                continue
            provenance = {
                **dict(cand.provenance),
                "candidate_generator_id": "exact_output_ik",
            }
            if "goal_sample_id" not in provenance:
                provenance["goal_sample_id"] = "exact_output"
            accepted.append(
                StateCandidate(
                    state=cand.state,
                    residual=float(cand.residual),
                    provenance=provenance,
                )
            )
            if len(accepted) >= max_candidates:
                break
    else:
        if goal_generator is None:
            raise ValueError("goal_generator required for non-exact OMPL goals")
        seed = None if rng is None else int(rng.integers(0, 2**31 - 1))
        request = GoalSamplingRequest(max_candidates=max_candidates, seed=seed)
        raw = list(goal_generator.generate(problem.robot, problem.goal, request))
        accepted = [cand for cand in raw if problem.scene.state_is_valid(cand.state)]
        accepted = accepted[:max_candidates]

    ik_families = sorted(
        {str(cand.provenance.get("ik_family", "unknown")) for cand in accepted}
    )
    metadata = {
        "goal_representation": "finite_goal_states",
        "goal_region_descriptor": _goal_descriptor(problem),
        "goal_samples_generated": len(raw),
        "goal_samples_accepted": len(accepted),
        "discrete_goal_state_count": len(accepted),
        "ik_families": ik_families,
    }

    goal = ob.GoalStates(si)
    owned_states: list[Any] = []
    for cand in accepted:
        st = space.allocState()
        write_u_to_ompl_state(space, st, cand.state.u)
        goal.addState(st)
        owned_states.append(st)
    return goal, accepted, metadata, owned_states
