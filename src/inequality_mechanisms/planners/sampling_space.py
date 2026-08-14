"""Shared sampling-space helpers for roadmap and tree planners."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
from numpy.random import Generator
from numpy.typing import NDArray

from inequality_mechanisms.core.goals import (
    ExactOutputGoal,
    GoalSamplingRequest,
    GoalStateGenerator,
)
from inequality_mechanisms.core.local_motion import (
    InputLinearMotion,
    LocalMotionModel,
)
from inequality_mechanisms.core.problem import PlanningProblem
from inequality_mechanisms.core.robot import RobotModel
from inequality_mechanisms.core.state import PhysicalState, StateCandidate


def actuator_bounds(robot: RobotModel) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return robot-owned input lower/upper bounds."""
    domain = getattr(robot, "input_domain", None)
    if domain is None:
        raise ValueError("sampling planners require a robot with input_domain")
    lo = np.asarray(domain.lower, dtype=np.float64)
    hi = np.asarray(domain.upper, dtype=np.float64)
    return lo, hi


def sample_state_uniform(
    robot: RobotModel,
    rng: Generator,
    *,
    assembly_state: dict[str, Any] | None = None,
) -> PhysicalState:
    """Draw one uniform sample in the robot input domain."""
    lo, hi = actuator_bounds(robot)
    u = rng.uniform(lo, hi)
    return robot.state_from_input(u, assembly_state=assembly_state)


def resolve_connector(problem: PlanningProblem, *, n_samples: int = 16) -> LocalMotionModel:
    """Prefer problem connector when input-linear; else build InputLinearMotion."""
    motion = problem.local_motion
    if isinstance(motion, InputLinearMotion):
        return motion
    model_id = getattr(motion, "model_id", "")
    if str(model_id).startswith("input_linear"):
        return motion  # type: ignore[return-value]
    return InputLinearMotion(robot=problem.robot, n_samples=n_samples)


def try_connect(
    connector: LocalMotionModel,
    problem: PlanningProblem,
    a: PhysicalState,
    b: PhysicalState,
) -> bool:
    """Return True when a local motion between ``a`` and ``b`` is scene-valid."""
    motion = connector.connect(a, b)
    if motion is None:
        return False
    return bool(problem.scene.motion_is_valid(motion))


def direct_connector_available(
    problem: PlanningProblem,
    goal_states: list[PhysicalState],
) -> tuple[bool, int]:
    """Evaluate the declared direct connector before nonlocal planning.

    ADR-026 task classification is independent of the planner selected for the
    query.  Sampling planners therefore test ``problem.local_motion`` directly
    against the represented goal candidates before building a roadmap or tree.
    The returned count is the number of continuous motions submitted to the
    scene validity checker.
    """
    motion_checks = 0
    for goal_state in goal_states:
        motion = problem.local_motion.connect(problem.start, goal_state)
        if motion is None:
            continue
        motion_checks += 1
        if problem.scene.motion_is_valid(motion) and problem.goal.satisfied(goal_state):
            return True, motion_checks
    return False, motion_checks


def select_goal_candidates(
    problem: PlanningProblem,
    *,
    goal_generator: GoalStateGenerator | None,
    max_candidates: int,
    rng: Generator | None = None,
) -> list[StateCandidate]:
    """Return scene-valid goal candidates preserving generator provenance."""
    goal = problem.goal
    if isinstance(goal, ExactOutputGoal):
        cands = list(problem.robot.states_from_output(goal.q_goal))
        out: list[StateCandidate] = []
        for cand in cands:
            if not problem.scene.state_is_valid(cand.state):
                continue
            provenance = {
                **dict(cand.provenance),
                "candidate_generator_id": "exact_output_ik",
            }
            if "goal_sample_id" not in provenance:
                provenance["goal_sample_id"] = "exact_output"
            out.append(
                StateCandidate(
                    state=cand.state,
                    residual=float(cand.residual),
                    provenance=provenance,
                )
            )
            if len(out) >= max_candidates:
                break
        return out
    if goal_generator is None:
        raise ValueError("goal_generator required for non-exact goals")
    seed = None if rng is None else int(rng.integers(0, 2**31 - 1))
    request = GoalSamplingRequest(max_candidates=max_candidates, seed=seed)
    cands = list(goal_generator.generate(problem.robot, goal, request))
    return [c for c in cands if problem.scene.state_is_valid(c.state)]


def select_goal_states(
    problem: PlanningProblem,
    *,
    goal_generator: GoalStateGenerator | None,
    max_candidates: int,
    rng: Generator | None = None,
) -> list[PhysicalState]:
    """Return physical goal states (shim over ``select_goal_candidates``)."""
    return [
        c.state
        for c in select_goal_candidates(
            problem,
            goal_generator=goal_generator,
            max_candidates=max_candidates,
            rng=rng,
        )
    ]


def match_selected_candidate(
    candidates: Sequence[StateCandidate],
    selected: PhysicalState,
    *,
    atol: float = 1e-9,
) -> StateCandidate | None:
    """Return the candidate whose state matches ``selected`` in U (then Q)."""
    for cand in candidates:
        if np.allclose(cand.state.u, selected.u, rtol=0.0, atol=atol):
            if np.allclose(cand.state.q, selected.q, rtol=0.0, atol=atol):
                return cand
    for cand in candidates:
        if np.allclose(cand.state.u, selected.u, rtol=0.0, atol=atol):
            return cand
    return None


def path_cost_u(states: tuple[PhysicalState, ...]) -> float:
    """Sum endpoint Euclidean actuator displacements along ``states``."""
    from inequality_mechanisms.core.trajectory_metrics import path_metrics_from_states

    return path_metrics_from_states(states).length_u


def path_length_q(states: tuple[PhysicalState, ...]) -> float:
    """Sum endpoint Euclidean output displacements along ``states``."""
    from inequality_mechanisms.core.trajectory_metrics import path_metrics_from_states

    return path_metrics_from_states(states).length_q


def path_length_x(
    states: tuple[PhysicalState, ...],
    *,
    robot: RobotModel | None = None,
) -> float | None:
    """Sum tip displacements when ``robot`` FK is available."""
    from inequality_mechanisms.core.trajectory_metrics import path_metrics_from_states

    return path_metrics_from_states(states, robot=robot).length_x
