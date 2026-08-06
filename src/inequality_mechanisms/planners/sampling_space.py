"""Shared sampling-space helpers for roadmap and tree planners."""

from __future__ import annotations

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
from inequality_mechanisms.core.state import PhysicalState


def actuator_bounds(robot: RobotModel) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return certified input lower/upper bounds when available."""
    branch = getattr(robot, "branch", None)
    if branch is None:
        raise ValueError("sampling planners require a robot with a certified branch")
    cert = branch.certificate
    lo = np.asarray(cert.input_lower, dtype=np.float64)
    hi = np.asarray(cert.input_upper, dtype=np.float64)
    return lo, hi


def sample_state_uniform(
    robot: RobotModel,
    rng: Generator,
    *,
    assembly_state: dict[str, Any] | None = None,
) -> PhysicalState:
    """Draw one uniform sample in the certified actuator box."""
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


def select_goal_states(
    problem: PlanningProblem,
    *,
    goal_generator: GoalStateGenerator | None,
    max_candidates: int,
    rng: Generator | None = None,
) -> list[PhysicalState]:
    """Return physical goal candidates for ExactOutputGoal or CartesianDiskGoal."""
    goal = problem.goal
    if isinstance(goal, ExactOutputGoal):
        cands = list(problem.robot.states_from_output(goal.q_goal))
        out = [c.state for c in cands if problem.scene.state_is_valid(c.state)]
        return out[:max_candidates]
    if goal_generator is None:
        raise ValueError("goal_generator required for non-exact goals")
    seed = None if rng is None else int(rng.integers(0, 2**31 - 1))
    request = GoalSamplingRequest(max_candidates=max_candidates, seed=seed)
    cands = list(goal_generator.generate(problem.robot, goal, request))
    return [c.state for c in cands if problem.scene.state_is_valid(c.state)]


def path_cost_u(states: tuple[PhysicalState, ...]) -> float:
    """Sum endpoint Euclidean actuator displacements along ``states``."""
    if len(states) < 2:
        return 0.0
    total = 0.0
    for a, b in zip(states[:-1], states[1:]):
        total += float(np.linalg.norm(b.u - a.u))
    return float(total)


def path_length_q(states: tuple[PhysicalState, ...]) -> float:
    """Sum endpoint Euclidean output displacements along ``states``."""
    if len(states) < 2:
        return 0.0
    total = 0.0
    for a, b in zip(states[:-1], states[1:]):
        total += float(np.linalg.norm(b.q - a.q))
    return float(total)
