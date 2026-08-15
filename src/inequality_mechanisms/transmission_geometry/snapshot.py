"""Geometry snapshots and serialization for kinematic transmission geometry."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from inequality_mechanisms.core.state import PhysicalState
from inequality_mechanisms.transmission_geometry.differential import (
    DEFAULT_RANK_TOLERANCE_FACTOR,
    RankReport,
    composite_jacobian,
    rank_report,
)
from inequality_mechanisms.transmission_geometry.errors import (
    DifferentialShapeError,
    DifferentialSingularityError,
)
from inequality_mechanisms.transmission_geometry.metrics import (
    actuator_metric_on_q,
    mobility_on_q,
    mobility_on_x,
    validate_positive_definite,
)
from inequality_mechanisms.transmission_geometry.protocols import (
    DEFAULT_STATE_TOLERANCE,
    KinematicTransmissionRobotModel,
)

GEOMETRY_SNAPSHOT_SCHEMA_VERSION = "v4.0.geometry_snapshot.v1"
METRIC_STATUS_AVAILABLE = "inverse_metric_available"
METRIC_STATUS_RANK_DEFICIENT = "inverse_metric_unavailable_rank_deficient"
METRIC_STATUS_NONSQUARE = "inverse_metric_unavailable_nonsquare"

_UNAVAILABLE_REASON = {
    METRIC_STATUS_AVAILABLE: None,
    METRIC_STATUS_RANK_DEFICIENT: "J_g is rank-deficient",
    METRIC_STATUS_NONSQUARE: "J_g is nonsquare",
}

_SNAPSHOT_TOP_LEVEL_KEYS = (
    "schema_version",
    "u",
    "q",
    "x",
    "jacobians",
    "rank_reports",
    "metrics",
    "provenance",
)


def _vector_to_tuple(values: ArrayLike, *, name: str) -> tuple[float, ...]:
    arr = np.asarray(values, dtype=np.float64)
    if arr.ndim != 1 or arr.size == 0:
        raise DifferentialShapeError(
            f"{name} must be a nonempty 1-D vector, got shape {arr.shape}"
        )
    if not np.all(np.isfinite(arr)):
        raise DifferentialShapeError(
            f"{name} must contain only finite values",
            failure_code="nonfinite_differential",
        )
    return tuple(float(value) for value in arr)


def _matrix_to_tuples(
    values: ArrayLike,
    *,
    name: str,
) -> tuple[tuple[float, ...], ...]:
    arr = np.asarray(values, dtype=np.float64)
    if arr.ndim != 2 or arr.shape[0] == 0 or arr.shape[1] == 0:
        raise DifferentialShapeError(
            f"{name} must be a nonempty rank-2 matrix, got shape {arr.shape}"
        )
    if not np.all(np.isfinite(arr)):
        raise DifferentialShapeError(
            f"{name} must contain only finite values",
            failure_code="nonfinite_differential",
        )
    return tuple(tuple(float(value) for value in row) for row in arr)


def _matrix_to_lists(
    rows: tuple[tuple[float, ...], ...] | None,
) -> list[list[float]] | None:
    if rows is None:
        return None
    return [list(row) for row in rows]


def _resolved_weight(
    input_dim: int,
    actuator_weight: ArrayLike | None,
) -> tuple[NDArray[np.float64], str]:
    if actuator_weight is None:
        weight = np.eye(input_dim, dtype=np.float64)
        source = "identity_default"
    else:
        weight = np.asarray(actuator_weight, dtype=np.float64)
        source = "caller"
        if weight.shape != (input_dim, input_dim):
            raise DifferentialShapeError(
                "actuator_weight must have shape "
                f"({input_dim}, {input_dim}), got {weight.shape}"
            )
    validate_positive_definite(weight)
    return weight, source


def _metric_status_from_error(exc: DifferentialSingularityError) -> str:
    if exc.shape[0] != exc.shape[1]:
        return METRIC_STATUS_NONSQUARE
    return METRIC_STATUS_RANK_DEFICIENT


def _provenance(
    robot: KinematicTransmissionRobotModel,
    *,
    state_tolerance: float,
    rank_tolerance: float | None,
    rank_u_to_q: RankReport,
    rank_q_to_x: RankReport,
    rank_u_to_x: RankReport,
    weight_source: str,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "package": "inequality_mechanisms.transmission_geometry",
        "kernel": "v4.0",
        "robot_type": type(robot).__name__,
        "state_tolerance": float(state_tolerance),
        "rank_tolerance_policy": (
            {"mode": "absolute", "value": float(rank_tolerance)}
            if rank_tolerance is not None
            else {
                "mode": "default_scale_aware",
                "factor": float(DEFAULT_RANK_TOLERANCE_FACTOR),
            }
        ),
        "rank_tolerances": {
            "u_to_q": float(rank_u_to_q.tolerance),
            "q_to_x": float(rank_q_to_x.tolerance),
            "u_to_x": float(rank_u_to_x.tolerance),
        },
        "actuator_weight_source": weight_source,
    }
    branch = getattr(robot, "branch", None)
    if branch is not None:
        mechanism = getattr(branch, "mechanism", None)
        if mechanism is not None:
            record["mechanism_name"] = str(
                getattr(mechanism, "name", type(mechanism).__name__)
            )
            type_key = getattr(mechanism, "type_key", None)
            record["mechanism_type"] = (
                str(type_key)
                if type_key is not None
                else type(mechanism).__name__
            )
        branch_id = getattr(branch, "branch_id", None)
        if branch_id is not None:
            record["branch_id"] = str(branch_id)
    kinematic_model = getattr(robot, "kinematic_model", None)
    if kinematic_model is not None:
        record["kinematic_model_type"] = type(kinematic_model).__name__
        params: dict[str, float] = {}
        if hasattr(kinematic_model, "L1"):
            params["L1"] = float(kinematic_model.L1)
        if hasattr(kinematic_model, "L2"):
            params["L2"] = float(kinematic_model.L2)
        if params:
            record["kinematic_model_params"] = params
    return record


@dataclass(frozen=True, slots=True)
class KinematicGeometrySnapshot:
    """Certified state, Jacobians, rank reports, metric, and mobility."""

    u: tuple[float, ...]
    q: tuple[float, ...]
    x: tuple[float, ...]
    j_u_to_q: tuple[tuple[float, ...], ...]
    j_q_to_x: tuple[tuple[float, ...], ...]
    j_u_to_x: tuple[tuple[float, ...], ...]
    rank_u_to_q: RankReport
    rank_q_to_x: RankReport
    rank_u_to_x: RankReport
    actuator_weight: tuple[tuple[float, ...], ...]
    actuator_metric_on_q: tuple[tuple[float, ...], ...] | None
    mobility_on_q: tuple[tuple[float, ...], ...]
    mobility_on_x: tuple[tuple[float, ...], ...]
    metric_status: str
    provenance: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "provenance", dict(self.provenance))
        if self.metric_status not in _UNAVAILABLE_REASON:
            raise ValueError(f"unknown metric_status {self.metric_status!r}")
        available = self.actuator_metric_on_q is not None
        if available != (self.metric_status == METRIC_STATUS_AVAILABLE):
            raise ValueError(
                "actuator_metric_on_q presence must match metric_status"
            )

    def to_dict(self) -> dict[str, Any]:
        """Return the Version 4 geometry-snapshot schema record."""
        available = self.actuator_metric_on_q is not None
        return {
            "schema_version": GEOMETRY_SNAPSHOT_SCHEMA_VERSION,
            "u": list(self.u),
            "q": list(self.q),
            "x": list(self.x),
            "jacobians": {
                "j_u_to_q": _matrix_to_lists(self.j_u_to_q),
                "j_q_to_x": _matrix_to_lists(self.j_q_to_x),
                "j_u_to_x": _matrix_to_lists(self.j_u_to_x),
            },
            "rank_reports": {
                "u_to_q": self.rank_u_to_q.to_dict(),
                "q_to_x": self.rank_q_to_x.to_dict(),
                "u_to_x": self.rank_u_to_x.to_dict(),
            },
            "metrics": {
                "actuator_weight": _matrix_to_lists(self.actuator_weight),
                "actuator_metric_on_q": _matrix_to_lists(
                    self.actuator_metric_on_q
                ),
                "actuator_metric_on_q_available": bool(available),
                "actuator_metric_unavailable_reason": _UNAVAILABLE_REASON[
                    self.metric_status
                ],
                "mobility_on_q": _matrix_to_lists(self.mobility_on_q),
                "mobility_on_x": _matrix_to_lists(self.mobility_on_x),
                "metric_status": str(self.metric_status),
            },
            "provenance": dict(self.provenance),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> KinematicGeometrySnapshot:
        """Restore a snapshot from :meth:`to_dict` output."""
        schema = data.get("schema_version")
        if schema != GEOMETRY_SNAPSHOT_SCHEMA_VERSION:
            raise ValueError(
                "unsupported geometry snapshot schema_version: "
                f"{schema!r}"
            )
        missing = [key for key in _SNAPSHOT_TOP_LEVEL_KEYS if key not in data]
        if missing:
            raise ValueError(f"geometry snapshot missing keys: {missing}")
        jacobians = data["jacobians"]
        ranks = data["rank_reports"]
        metrics = data["metrics"]
        return cls(
            u=_vector_to_tuple(data["u"], name="u"),
            q=_vector_to_tuple(data["q"], name="q"),
            x=_vector_to_tuple(data["x"], name="x"),
            j_u_to_q=_matrix_to_tuples(
                jacobians["j_u_to_q"], name="j_u_to_q"
            ),
            j_q_to_x=_matrix_to_tuples(
                jacobians["j_q_to_x"], name="j_q_to_x"
            ),
            j_u_to_x=_matrix_to_tuples(
                jacobians["j_u_to_x"], name="j_u_to_x"
            ),
            rank_u_to_q=RankReport.from_dict(ranks["u_to_q"]),
            rank_q_to_x=RankReport.from_dict(ranks["q_to_x"]),
            rank_u_to_x=RankReport.from_dict(ranks["u_to_x"]),
            actuator_weight=_matrix_to_tuples(
                metrics["actuator_weight"], name="actuator_weight"
            ),
            actuator_metric_on_q=(
                None
                if metrics["actuator_metric_on_q"] is None
                else _matrix_to_tuples(
                    metrics["actuator_metric_on_q"],
                    name="actuator_metric_on_q",
                )
            ),
            mobility_on_q=_matrix_to_tuples(
                metrics["mobility_on_q"], name="mobility_on_q"
            ),
            mobility_on_x=_matrix_to_tuples(
                metrics["mobility_on_x"], name="mobility_on_x"
            ),
            metric_status=str(metrics["metric_status"]),
            provenance=dict(data["provenance"]),
        )


def geometry_snapshot(
    robot: KinematicTransmissionRobotModel,
    state: PhysicalState,
    *,
    actuator_weight: ArrayLike | None = None,
    rank_tolerance: float | None = None,
    state_tolerance: float = DEFAULT_STATE_TOLERANCE,
) -> KinematicGeometrySnapshot:
    """Build a geometry snapshot at a certified physical state.

    Parameters
    ----------
    robot :
        Version 4-capable robot exposing ``jacobian_u_to_q``.
    state :
        Physical state to evaluate.
    actuator_weight :
        Optional positive-definite actuator metric. Defaults to identity.
    rank_tolerance :
        Optional absolute SVD cutoff forwarded to rank reports and the
        inverse metric.
    state_tolerance :
        Declared ``||q - g(u)||`` cutoff used before evaluating maps.

    Returns
    -------
    KinematicGeometrySnapshot
        Frozen record of coordinates, Jacobians, rank, metric, and mobility.
    """
    if not isinstance(robot, KinematicTransmissionRobotModel):
        raise TypeError(
            "robot must implement KinematicTransmissionRobotModel, "
            f"got {type(robot).__name__}"
        )
    used_state_tolerance = float(state_tolerance)
    if not np.isfinite(used_state_tolerance) or used_state_tolerance < 0.0:
        raise ValueError(
            "state_tolerance must be finite and nonnegative, "
            f"got {state_tolerance}"
        )
    if not robot.validate_state(state, used_state_tolerance):
        raise ValueError("state is inconsistent with the transmission map g(u)")
    if not robot.state_within_limits(state):
        raise ValueError("state is outside the certified operating branch")

    j_g = np.asarray(robot.jacobian_u_to_q(state), dtype=np.float64)
    j_f = np.asarray(robot.jacobian_q_to_x(state), dtype=np.float64)
    pose = robot.forward_kinematics(state)
    x = np.asarray(pose.position, dtype=np.float64)
    j_xu = composite_jacobian(j_f, j_g)

    rank_u_to_q = rank_report(j_g, tolerance=rank_tolerance)
    rank_q_to_x = rank_report(j_f, tolerance=rank_tolerance)
    rank_u_to_x = rank_report(j_xu, tolerance=rank_tolerance)

    weight, weight_source = _resolved_weight(int(j_g.shape[1]), actuator_weight)
    b_q = mobility_on_q(j_g, weight)
    b_x = mobility_on_x(j_xu, weight)
    try:
        metric = actuator_metric_on_q(
            j_g,
            weight,
            rank_tolerance=rank_tolerance,
        )
        metric_status = METRIC_STATUS_AVAILABLE
        metric_tuples: tuple[tuple[float, ...], ...] | None = _matrix_to_tuples(
            metric,
            name="actuator_metric_on_q",
        )
    except DifferentialSingularityError as exc:
        metric_tuples = None
        metric_status = _metric_status_from_error(exc)

    return KinematicGeometrySnapshot(
        u=_vector_to_tuple(state.u, name="u"),
        q=_vector_to_tuple(state.q, name="q"),
        x=_vector_to_tuple(x, name="x"),
        j_u_to_q=_matrix_to_tuples(j_g, name="j_u_to_q"),
        j_q_to_x=_matrix_to_tuples(j_f, name="j_q_to_x"),
        j_u_to_x=_matrix_to_tuples(j_xu, name="j_u_to_x"),
        rank_u_to_q=rank_u_to_q,
        rank_q_to_x=rank_q_to_x,
        rank_u_to_x=rank_u_to_x,
        actuator_weight=_matrix_to_tuples(weight, name="actuator_weight"),
        actuator_metric_on_q=metric_tuples,
        mobility_on_q=_matrix_to_tuples(b_q, name="mobility_on_q"),
        mobility_on_x=_matrix_to_tuples(b_x, name="mobility_on_x"),
        metric_status=metric_status,
        provenance=_provenance(
            robot,
            state_tolerance=used_state_tolerance,
            rank_tolerance=rank_tolerance,
            rank_u_to_q=rank_u_to_q,
            rank_q_to_x=rank_q_to_x,
            rank_u_to_x=rank_u_to_x,
            weight_source=weight_source,
        ),
    )


__all__ = [
    "GEOMETRY_SNAPSHOT_SCHEMA_VERSION",
    "METRIC_STATUS_AVAILABLE",
    "METRIC_STATUS_NONSQUARE",
    "METRIC_STATUS_RANK_DEFICIENT",
    "KinematicGeometrySnapshot",
    "geometry_snapshot",
]
