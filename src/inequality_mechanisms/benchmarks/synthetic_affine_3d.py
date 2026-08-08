"""Synthetic 3-DOF affine architecture fixture (Sprint V3.6A / V3-616).

Identity transmission ``q = u`` with identity tip map ``x = q``. This module
exercises dimension-agnostic robot, sampling, planner, and optional OMPL
paths. It is not a planar-3R scientific robot and carries no V3.7 evidence.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from inequality_mechanisms.adapters.operating_branch_robot import (
    OperatingBranchRobotModel,
)
from inequality_mechanisms.core.constraints import ConstraintSet
from inequality_mechanisms.core.goals import ExactOutputGoal
from inequality_mechanisms.core.local_motion import InputLinearMotion
from inequality_mechanisms.core.objectives import ActuatorTravelObjective
from inequality_mechanisms.core.problem import PlanningProblem
from inequality_mechanisms.core.scene import FreeSpaceScene
from inequality_mechanisms.mechanisms import unit_gearbox_branch
from inequality_mechanisms.mechanisms.operating_branch import OperatingBranch


@dataclass(frozen=True, slots=True)
class AffineIdentityKinematics3D:
    """Identity tip kinematics ``x = q`` in ``R^3`` (architecture fixture)."""

    @property
    def dof(self) -> int:
        """Joint / tip dimension."""
        return 3

    def forward(self, q: ArrayLike) -> NDArray[np.float64]:
        """Return tip position equal to ``q``."""
        q_arr = np.asarray(q, dtype=np.float64)
        if q_arr.shape != (3,):
            raise ValueError(f"q must have shape (3,), got {q_arr.shape}")
        if not np.all(np.isfinite(q_arr)):
            raise ValueError("q must be finite")
        return q_arr.copy()

    def jacobian(self, q: ArrayLike) -> NDArray[np.float64]:
        """Return the identity Jacobian."""
        self.forward(q)
        return np.eye(3, dtype=np.float64)


DEFAULT_INPUT_LOWER = (-1.0, -1.0, -1.0)
DEFAULT_INPUT_UPPER = (1.0, 1.0, 1.0)


def synthetic_affine_3d_branch(
    *,
    input_lower: ArrayLike = DEFAULT_INPUT_LOWER,
    input_upper: ArrayLike = DEFAULT_INPUT_UPPER,
) -> OperatingBranch:
    """Return a certified 3-DOF unit-gearbox operating branch ``q = u``."""
    return unit_gearbox_branch(
        3,
        input_lower=input_lower,
        input_upper=input_upper,
        name="synthetic_affine_3d",
    )


def synthetic_affine_3d_robot(
    *,
    branch: OperatingBranch | None = None,
    kinematic_model: AffineIdentityKinematics3D | None = None,
) -> OperatingBranchRobotModel:
    """Wrap the synthetic 3-DOF branch with identity tip kinematics."""
    return OperatingBranchRobotModel(
        branch=branch if branch is not None else synthetic_affine_3d_branch(),
        kinematic_model=(
            kinematic_model
            if kinematic_model is not None
            else AffineIdentityKinematics3D()
        ),
    )


def synthetic_affine_3d_exact_problem(
    *,
    start_u: ArrayLike = (-0.6, -0.4, -0.2),
    goal_u: ArrayLike = (0.5, 0.3, 0.7),
    n_samples: int = 12,
) -> tuple[OperatingBranchRobotModel, PlanningProblem]:
    """Build an ExactOutputGoal free-space problem on the synthetic 3-DOF robot."""
    robot = synthetic_affine_3d_robot()
    start = robot.state_from_input(start_u)
    goal_state = robot.state_from_input(goal_u)
    problem = PlanningProblem(
        robot=robot,
        scene=FreeSpaceScene(robot=robot),
        start=start,
        goal=ExactOutputGoal(q_goal=goal_state.q.copy()),
        path_constraints=ConstraintSet.empty(),
        local_motion=InputLinearMotion(robot=robot, n_samples=n_samples),
        objective=ActuatorTravelObjective(),
    )
    return robot, problem
