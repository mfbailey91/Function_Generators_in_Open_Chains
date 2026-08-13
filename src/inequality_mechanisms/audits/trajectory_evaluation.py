"""Continuous trajectory evaluation for fresh V3.6C reporting (V3-634).

A planned path is an ordered sequence of declared local motions. This module
rebuilds each edge through the planner's connector and integrates U/Q/X arc
lengths from the same sample arrays used for later plots.

Planner ``objective_cost`` remains authoritative and is never replaced here.
Waypoint endpoint chords are retained only as named diagnostics.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray

from inequality_mechanisms.core.goals import GoalConstraint
from inequality_mechanisms.core.local_motion import LocalMotion, LocalMotionModel
from inequality_mechanisms.core.results import Trajectory
from inequality_mechanisms.core.robot import RobotModel
from inequality_mechanisms.core.scene import PlanningScene
from inequality_mechanisms.core.state import PhysicalState
from inequality_mechanisms.core.trajectory_metrics import (
    _polyline_length,
    path_metrics_from_motion_samples,
    path_metrics_from_states,
)

SCHEMA_VERSION = "v3_6c_cte_v1"


@dataclass(frozen=True, slots=True)
class TrajectorySegmentEvaluation:
    """Connector-reconstructed evaluation of one consecutive state pair."""

    start: PhysicalState
    end: PhysicalState
    model_id: str
    sample_u: NDArray[np.float64] | None
    sample_q: NDArray[np.float64] | None
    sample_x: NDArray[np.float64] | None
    length_u: float | None
    length_q: float | None
    length_x: float | None
    n_samples: int
    valid: bool
    failure_reason: str | None = None

    def to_jsonable(self) -> dict[str, Any]:
        """Serialize segment fields for audit JSON records."""
        return {
            "model_id": self.model_id,
            "sample_u": None if self.sample_u is None else self.sample_u.tolist(),
            "sample_q": None if self.sample_q is None else self.sample_q.tolist(),
            "sample_x": None if self.sample_x is None else self.sample_x.tolist(),
            "length_u": self.length_u,
            "length_q": self.length_q,
            "length_x": self.length_x,
            "n_samples": int(self.n_samples),
            "valid": bool(self.valid),
            "failure_reason": self.failure_reason,
            "start_u": np.asarray(self.start.u, dtype=np.float64).tolist(),
            "start_q": np.asarray(self.start.q, dtype=np.float64).tolist(),
            "end_u": np.asarray(self.end.u, dtype=np.float64).tolist(),
            "end_q": np.asarray(self.end.q, dtype=np.float64).tolist(),
        }


@dataclass(frozen=True, slots=True)
class ContinuousTrajectoryEvaluation:
    """Versioned continuous-path metrics reconstructed via local motions."""

    schema_version: str
    connector_id: str
    sampling_policy: Mapping[str, Any]
    segments: tuple[TrajectorySegmentEvaluation, ...]
    length_u: float | None
    length_q: float | None
    length_x: float | None
    n_waypoints: int
    n_samples_total: int
    start_physical_residual: float | None
    end_physical_residual: float | None
    waypoint_chord_u: float
    waypoint_chord_q: float
    waypoint_chord_x: float | None
    all_segments_valid: bool
    extras: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "sampling_policy", dict(self.sampling_policy))
        object.__setattr__(self, "extras", dict(self.extras))

    def to_jsonable(self) -> dict[str, Any]:
        """Serialize the evaluation record for planner_metrics / exporters."""
        return {
            "schema_version": self.schema_version,
            "connector_id": self.connector_id,
            "sampling_policy": dict(self.sampling_policy),
            "segments": [seg.to_jsonable() for seg in self.segments],
            "length_u": self.length_u,
            "length_q": self.length_q,
            "length_x": self.length_x,
            "n_waypoints": int(self.n_waypoints),
            "n_samples_total": int(self.n_samples_total),
            "start_physical_residual": self.start_physical_residual,
            "end_physical_residual": self.end_physical_residual,
            "waypoint_chord_u": self.waypoint_chord_u,
            "waypoint_chord_q": self.waypoint_chord_q,
            "waypoint_chord_x": self.waypoint_chord_x,
            "all_segments_valid": bool(self.all_segments_valid),
            "extras": dict(self.extras),
        }


def _as_states(
    states: Sequence[PhysicalState] | Trajectory,
) -> tuple[PhysicalState, ...]:
    if isinstance(states, Trajectory):
        return tuple(states.states)
    return tuple(states)


def _connector_id(connector: LocalMotionModel) -> str:
    mid = getattr(connector, "model_id", None)
    if mid is not None and str(mid):
        return str(mid)
    return type(connector).__name__


def _sampling_policy(connector: LocalMotionModel) -> dict[str, Any]:
    policy: dict[str, Any] = {
        "connector_id": _connector_id(connector),
        "connector_type": type(connector).__name__,
    }
    n_samples = getattr(connector, "n_samples", None)
    if n_samples is not None:
        policy["n_samples"] = int(n_samples)
    endpoint_tol = getattr(connector, "endpoint_tolerance", None)
    if endpoint_tol is not None:
        policy["endpoint_tolerance"] = float(endpoint_tol)
    return policy


def _physical_residual(
    goal: GoalConstraint | None,
    state: PhysicalState | None,
) -> float | None:
    if goal is None or state is None:
        return None
    try:
        return float(goal.residual(state).primary)
    except (NotImplementedError, ValueError, TypeError, AttributeError):
        return None


def _sample_x_array(
    *,
    sample_u: NDArray[np.float64],
    sample_q: NDArray[np.float64],
    robot: RobotModel,
    assembly_state: Mapping[str, Any],
) -> NDArray[np.float64] | None:
    try:
        tips = []
        for u_row, q_row in zip(sample_u, sample_q):
            state = PhysicalState(
                u=u_row,
                q=q_row,
                assembly_state=dict(assembly_state),
            )
            tips.append(
                np.asarray(robot.forward_kinematics(state).position, dtype=np.float64)
            )
        return np.asarray(tips, dtype=np.float64)
    except (NotImplementedError, ValueError, AttributeError, TypeError):
        return None


def _failed_segment(
    start: PhysicalState,
    end: PhysicalState,
    *,
    model_id: str,
    reason: str,
) -> TrajectorySegmentEvaluation:
    return TrajectorySegmentEvaluation(
        start=start,
        end=end,
        model_id=model_id,
        sample_u=None,
        sample_q=None,
        sample_x=None,
        length_u=None,
        length_q=None,
        length_x=None,
        n_samples=0,
        valid=False,
        failure_reason=reason,
    )


def _evaluate_segment(
    start: PhysicalState,
    end: PhysicalState,
    *,
    connector: LocalMotionModel,
    robot: RobotModel,
    scene: PlanningScene | None,
    assembly_override: Mapping[str, Any] | None,
) -> TrajectorySegmentEvaluation:
    connector_mid = _connector_id(connector)
    motion: LocalMotion | None
    try:
        motion = connector.connect(start, end)
    except (ValueError, TypeError, AttributeError) as exc:
        return _failed_segment(
            start, end, model_id=connector_mid, reason=f"connect_raised:{type(exc).__name__}"
        )
    if motion is None:
        return _failed_segment(
            start, end, model_id=connector_mid, reason="connect_rejected"
        )
    model_id = str(motion.model_id or connector_mid)
    if scene is not None and not scene.motion_is_valid(motion):
        return _failed_segment(
            start, end, model_id=model_id, reason="scene_invalid"
        )

    sample_u_raw = motion.parameters.get("sample_u")
    sample_q_raw = motion.parameters.get("sample_q")
    actuator_len = motion.parameters.get("actuator_path_length")
    if sample_u_raw is None or sample_q_raw is None or actuator_len is None:
        # Fail closed: never substitute endpoint chords into reporting lengths.
        return _failed_segment(
            start,
            end,
            model_id=model_id,
            reason="missing_connector_samples",
        )

    sample_u = np.asarray(sample_u_raw, dtype=np.float64)
    sample_q = np.asarray(sample_q_raw, dtype=np.float64)
    if (
        sample_u.ndim != 2
        or sample_q.ndim != 2
        or sample_u.shape[0] != sample_q.shape[0]
        or sample_u.shape[0] < 2
    ):
        return _failed_segment(
            start, end, model_id=model_id, reason="malformed_connector_samples"
        )

    assembly = dict(
        assembly_override
        if assembly_override is not None
        else motion.start.assembly_state
    )
    metrics = path_metrics_from_motion_samples(
        sample_u=sample_u,
        sample_q=sample_q,
        actuator_path_length=float(actuator_len),
        robot=robot,
        assembly_state=assembly,
    )
    sample_x = _sample_x_array(
        sample_u=sample_u,
        sample_q=sample_q,
        robot=robot,
        assembly_state=assembly,
    )
    length_x = metrics.length_x
    if length_x is None and sample_x is not None:
        length_x = _polyline_length(sample_x)

    return TrajectorySegmentEvaluation(
        start=start,
        end=end,
        model_id=model_id,
        sample_u=sample_u,
        sample_q=sample_q,
        sample_x=sample_x,
        length_u=float(metrics.length_u),
        length_q=float(metrics.length_q),
        length_x=None if length_x is None else float(length_x),
        n_samples=int(sample_u.shape[0]),
        valid=True,
        failure_reason=None,
    )


def evaluate_continuous_trajectory(
    states: Sequence[PhysicalState] | Trajectory,
    *,
    connector: LocalMotionModel,
    robot: RobotModel,
    goal: GoalConstraint | None = None,
    scene: PlanningScene | None = None,
    assembly_state: Mapping[str, Any] | None = None,
) -> ContinuousTrajectoryEvaluation:
    """Rebuild local motions along ``states`` and integrate continuous lengths.

    Parameters
    ----------
    states :
        Ordered physical waypoints or a ``Trajectory``.
    connector :
        Planner-declared local-motion model used to reconstruct each edge.
    robot :
        Robot model for FK tip samples and chord diagnostics.
    goal :
        Optional task predicate for start/end physical residuals.
    scene :
        Optional scene validity filter applied to each reconstructed motion.
    assembly_state :
        Optional assembly override for tip reconstruction.

    Returns
    -------
    ContinuousTrajectoryEvaluation
        Versioned record with per-segment samples, integrated totals, and
        separately named waypoint-chord diagnostics.
    """
    waypoints = _as_states(states)
    n_waypoints = len(waypoints)
    chords = path_metrics_from_states(waypoints, robot=robot)
    connector_mid = _connector_id(connector)
    policy = _sampling_policy(connector)

    if n_waypoints == 0:
        return ContinuousTrajectoryEvaluation(
            schema_version=SCHEMA_VERSION,
            connector_id=connector_mid,
            sampling_policy=policy,
            segments=(),
            length_u=0.0,
            length_q=0.0,
            length_x=0.0,
            n_waypoints=0,
            n_samples_total=0,
            start_physical_residual=None,
            end_physical_residual=None,
            waypoint_chord_u=0.0,
            waypoint_chord_q=0.0,
            waypoint_chord_x=chords.length_x,
            all_segments_valid=True,
        )

    start_res = _physical_residual(goal, waypoints[0])
    end_res = _physical_residual(goal, waypoints[-1])

    if n_waypoints == 1:
        return ContinuousTrajectoryEvaluation(
            schema_version=SCHEMA_VERSION,
            connector_id=connector_mid,
            sampling_policy=policy,
            segments=(),
            length_u=0.0,
            length_q=0.0,
            length_x=0.0,
            n_waypoints=1,
            n_samples_total=0,
            start_physical_residual=start_res,
            end_physical_residual=end_res,
            waypoint_chord_u=0.0,
            waypoint_chord_q=0.0,
            waypoint_chord_x=chords.length_x if chords.length_x is not None else 0.0,
            all_segments_valid=True,
        )

    segments: list[TrajectorySegmentEvaluation] = []
    for a, b in zip(waypoints[:-1], waypoints[1:]):
        segments.append(
            _evaluate_segment(
                a,
                b,
                connector=connector,
                robot=robot,
                scene=scene,
                assembly_override=assembly_state,
            )
        )

    all_valid = all(seg.valid for seg in segments)
    n_samples_total = int(sum(seg.n_samples for seg in segments))

    if all_valid:
        length_u = float(sum(float(seg.length_u or 0.0) for seg in segments))
        length_q = float(sum(float(seg.length_q or 0.0) for seg in segments))
        if any(seg.length_x is None for seg in segments):
            length_x: float | None = None
        else:
            length_x = float(sum(float(seg.length_x or 0.0) for seg in segments))
    else:
        # Fail closed: do not fill reporting lengths from waypoint chords.
        length_u = None
        length_q = None
        length_x = None

    return ContinuousTrajectoryEvaluation(
        schema_version=SCHEMA_VERSION,
        connector_id=connector_mid,
        sampling_policy=policy,
        segments=tuple(segments),
        length_u=length_u,
        length_q=length_q,
        length_x=length_x,
        n_waypoints=n_waypoints,
        n_samples_total=n_samples_total,
        start_physical_residual=start_res,
        end_physical_residual=end_res,
        waypoint_chord_u=float(chords.length_u),
        waypoint_chord_q=float(chords.length_q),
        waypoint_chord_x=None if chords.length_x is None else float(chords.length_x),
        all_segments_valid=all_valid,
    )
