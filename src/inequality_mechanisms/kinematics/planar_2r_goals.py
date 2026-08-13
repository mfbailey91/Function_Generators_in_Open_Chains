"""Planar 2R goal-state generators (Sprint V3.6A / V3-614)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from inequality_mechanisms.core.goals import (
    CartesianDiskGoal,
    GoalConstraint,
    GoalSamplingRequest,
)
from inequality_mechanisms.core.robot import RobotModel
from inequality_mechanisms.core.state import StateCandidate
from inequality_mechanisms.kinematics.planar_2r import Planar2R


def planar_2r_ik_family(q: ArrayLike, *, tolerance: float = 1e-9) -> str:
    """Return ``elbow_up`` / ``elbow_down`` / ``singular`` for planar 2R ``q``."""
    q_arr = np.asarray(q, dtype=np.float64)
    if q_arr.shape != (2,):
        raise ValueError("q must have shape (2,)")
    s = float(np.sin(q_arr[1]))
    if abs(s) <= tolerance:
        return "singular"
    return "elbow_up" if s > 0.0 else "elbow_down"


@dataclass(frozen=True, slots=True)
class CartesianDiskGoalGenerator:
    """Generate physical candidates at the disk center via planar 2R IK."""

    planar_fk: Planar2R
    limit_tolerance: float = 1e-9

    def generate(
        self,
        robot: RobotModel,
        goal: GoalConstraint,
        request: GoalSamplingRequest,
    ) -> Sequence[StateCandidate]:
        """Return representable IK lifts of the disk center."""
        if not isinstance(goal, CartesianDiskGoal):
            raise TypeError(
                "CartesianDiskGoalGenerator requires CartesianDiskGoal, "
                f"got {type(goal).__name__}"
            )
        qs = self.planar_fk.inverse(goal.center)
        out: list[StateCandidate] = []
        for q in qs:
            q_arr = np.asarray(q, dtype=np.float64)
            family = planar_2r_ik_family(q_arr)
            for cand in robot.states_from_output(q_arr):
                if not robot.state_within_limits(cand.state):
                    continue
                tip = np.asarray(
                    robot.forward_kinematics(cand.state).position, dtype=np.float64
                )
                cart_res = float(np.linalg.norm(tip - goal.center))
                provenance = {
                    **dict(cand.provenance),
                    "ik_family": family,
                    "goal_region": "cartesian_disk_center",
                    "candidate_generator_id": "cartesian_disk_center_ik",
                    "goal_sample_id": "disk_center",
                    "goal_sample_index": 0,
                    "goal_sample_point": goal.center.tolist(),
                }
                out.append(
                    StateCandidate(
                        state=cand.state,
                        residual=max(float(cand.residual), cart_res),
                        provenance=provenance,
                    )
                )
                if len(out) >= request.max_candidates:
                    return tuple(out)
        return tuple(out)
