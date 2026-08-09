"""Planar 3R goal-state generators (Sprint V3.6A / V3-614)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from inequality_mechanisms.core.goals import (
    CartesianDiskGoal,
    GoalConstraint,
    GoalSamplingRequest,
    PlanarPoseRegionGoal,
)
from inequality_mechanisms.core.robot import RobotModel
from inequality_mechanisms.core.state import StateCandidate
from inequality_mechanisms.kinematics.planar_3r import (
    Planar3R,
    planar_3r_elbow_family,
)


@dataclass(frozen=True, slots=True)
class Planar3RPoseGoalGenerator:
    """Generate physical candidates for an SE(2) pose-region goal via 3R IK."""

    planar_fk: Planar3R
    limit_tolerance: float = 1e-9

    def generate(
        self,
        robot: RobotModel,
        goal: GoalConstraint,
        request: GoalSamplingRequest,
    ) -> Sequence[StateCandidate]:
        """Return representable IK lifts of the pose-region center/heading."""
        if not isinstance(goal, PlanarPoseRegionGoal):
            raise TypeError(
                "Planar3RPoseGoalGenerator requires PlanarPoseRegionGoal, "
                f"got {type(goal).__name__}"
            )
        out: list[StateCandidate] = []
        seen: set[tuple[float, float, float]] = set()
        for q in self.planar_fk.inverse_pose(goal.center, goal.phi_goal):
            q_arr = np.asarray(q, dtype=np.float64)
            key = tuple(np.round(q_arr, decimals=12).tolist())
            if key in seen:
                continue
            family = planar_3r_elbow_family(q_arr)
            for cand in robot.states_from_output(q_arr):
                if not robot.state_within_limits(cand.state):
                    continue
                if not goal.satisfied(cand.state):
                    continue
                seen.add(key)
                provenance = {
                    **dict(cand.provenance),
                    "ik_family": family,
                    "goal_region": "planar_pose_region_center",
                    "goal_sample_id": "se2_center",
                    "goal_phi": float(goal.phi_goal),
                }
                out.append(
                    StateCandidate(
                        state=cand.state,
                        residual=max(
                            float(cand.residual),
                            float(goal.residual(cand.state).primary),
                        ),
                        provenance=provenance,
                    )
                )
                if len(out) >= request.max_candidates:
                    return tuple(out)
        return tuple(out)


@dataclass(frozen=True, slots=True)
class FrozenPlanar3RPositionGoalGenerator:
    """Deterministic redundant position goal set: disk samples × frozen φ."""

    planar_fk: Planar3R
    goal_points: tuple[NDArray[np.float64], ...]
    goal_point_ids: tuple[str, ...]
    phi_samples: tuple[float, ...]
    numerical_tolerance: float = 1e-9

    def generate(
        self,
        robot: RobotModel,
        goal: GoalConstraint,
        request: GoalSamplingRequest,
    ) -> Sequence[StateCandidate]:
        """Return finite IK candidates for the frozen position representation."""
        if not isinstance(goal, CartesianDiskGoal):
            raise TypeError(
                "FrozenPlanar3RPositionGoalGenerator requires CartesianDiskGoal"
            )
        if len(self.goal_points) != len(self.goal_point_ids):
            raise ValueError("goal point ids must match goal points")

        out: list[StateCandidate] = []
        seen: set[tuple[float, float, float]] = set()
        for point_index, (point_id, point) in enumerate(
            zip(self.goal_point_ids, self.goal_points)
        ):
            for phi_index, phi in enumerate(self.phi_samples):
                for q in self.planar_fk.inverse_position_at_heading(point, phi):
                    q_arr = np.asarray(q, dtype=np.float64)
                    key = tuple(np.round(q_arr, decimals=12).tolist())
                    if key in seen:
                        continue
                    for cand in robot.states_from_output(q_arr):
                        if not robot.state_within_limits(cand.state):
                            continue
                        tip = np.asarray(
                            robot.forward_kinematics(cand.state).position,
                            dtype=np.float64,
                        )
                        cart_dist = float(np.linalg.norm(tip - goal.center))
                        if cart_dist > float(goal.radius) + self.numerical_tolerance:
                            continue
                        seen.add(key)
                        provenance = {
                            **dict(cand.provenance),
                            "ik_family": planar_3r_elbow_family(q_arr),
                            "goal_representation": (
                                "frozen_disk_points_times_phi_grid_v1"
                            ),
                            "goal_sample_id": f"{point_id}__phi_{phi_index}",
                            "goal_sample_index": int(point_index),
                            "goal_phi_index": int(phi_index),
                            "goal_sample_point": point.tolist(),
                            "goal_phi": float(phi),
                        }
                        out.append(
                            StateCandidate(
                                state=cand.state,
                                residual=max(float(cand.residual), cart_dist),
                                provenance=provenance,
                            )
                        )
                        if len(out) >= request.max_candidates:
                            return tuple(out)
        return tuple(out)
