"""Shared V3 trajectory path metrics (Sprint V3.6A / V3-615).

Endpoint polyline formulas for reporting. Declared integrated local-motion
costs remain authoritative when present on a ``LocalMotion``; this utility
does not replace them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np

from inequality_mechanisms.core.robot import RobotModel
from inequality_mechanisms.core.state import PhysicalState


@dataclass(frozen=True, slots=True)
class TrajectoryPathMetrics:
    """Waypoint polyline lengths in U, Q, and Cartesian tip space."""

    length_u: float
    length_q: float
    length_x: float | None
    n_waypoints: int


def _polyline_length(samples: np.ndarray) -> float:
    if samples.shape[0] < 2:
        return 0.0
    return float(np.sum(np.linalg.norm(np.diff(samples, axis=0), axis=1)))


def path_metrics_from_states(
    states: Sequence[PhysicalState],
    *,
    robot: RobotModel | None = None,
) -> TrajectoryPathMetrics:
    """Return endpoint polyline metrics for an ordered physical-state path."""
    n = len(states)
    if n == 0:
        return TrajectoryPathMetrics(
            length_u=0.0, length_q=0.0, length_x=None, n_waypoints=0
        )
    if n == 1:
        return TrajectoryPathMetrics(
            length_u=0.0, length_q=0.0, length_x=0.0, n_waypoints=1
        )

    length_u = 0.0
    length_q = 0.0
    for a, b in zip(states[:-1], states[1:]):
        length_u += float(np.linalg.norm(b.u - a.u))
        length_q += float(np.linalg.norm(b.q - a.q))

    length_x: float | None = None
    if robot is not None:
        try:
            tips = [
                np.asarray(robot.forward_kinematics(s).position, dtype=np.float64)
                for s in states
            ]
            length_x = _polyline_length(np.asarray(tips, dtype=np.float64))
        except (NotImplementedError, ValueError, AttributeError, TypeError):
            length_x = None

    return TrajectoryPathMetrics(
        length_u=float(length_u),
        length_q=float(length_q),
        length_x=length_x,
        n_waypoints=n,
    )


def path_metrics_from_motion_samples(
    *,
    sample_u: np.ndarray,
    sample_q: np.ndarray,
    actuator_path_length: float,
    robot: Any,
    assembly_state: Any,
) -> TrajectoryPathMetrics:
    """Return metrics from connector sample arrays (direct planners)."""
    length_q = _polyline_length(np.asarray(sample_q, dtype=np.float64))
    length_x: float | None
    try:
        tips = []
        for u_row, q_row in zip(sample_u, sample_q):
            state = PhysicalState(u=u_row, q=q_row, assembly_state=assembly_state)
            tips.append(np.asarray(robot.forward_kinematics(state).position))
        length_x = _polyline_length(np.asarray(tips, dtype=np.float64))
    except (NotImplementedError, ValueError, AttributeError, TypeError):
        length_x = None
    return TrajectoryPathMetrics(
        length_u=float(actuator_path_length),
        length_q=float(length_q),
        length_x=length_x,
        n_waypoints=int(np.asarray(sample_u).shape[0]),
    )
