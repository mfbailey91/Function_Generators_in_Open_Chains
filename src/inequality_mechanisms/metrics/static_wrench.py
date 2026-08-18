"""Gravity-free planar static wrench capability from V4.0 snapshots.

This module does not rederive Jacobians. It consumes ``geometry_snapshot``
/ ``composite_jacobian`` / ``rank_report`` and forms the exact torque-box
force set

``W = {w : |J_xu.T @ w| <= tau_bar}``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

import numpy as np
from numpy.typing import ArrayLike, NDArray

from inequality_mechanisms.core.state import PhysicalState
from inequality_mechanisms.experiments.span_wrench_config import FORBIDDEN_GRAVITY_KEYS
from inequality_mechanisms.metrics.wrench_directions import (
    DIRECTION_EPS,
    named_task_directions,
)
from inequality_mechanisms.transmission_geometry import (
    KinematicGeometrySnapshot,
    KinematicTransmissionRobotModel,
    composite_jacobian,
    geometry_snapshot,
    rank_report,
)
from inequality_mechanisms.transmission_geometry.errors import TransmissionGeometryError

SCHEMA_VERSION = "v3.6e.static_wrench.v1"
NEAR_SINGULAR_CONDITION = 1e6
DEFAULT_TORQUE_LIMITS = (1.0, 1.0)
_GRID_CACHE: dict[str, tuple["StaticWrenchCapability2D", ...]] = {}


class WrenchStateStatus(str, Enum):
    """Typed ideal-model wrench status. Values are never visually clipped."""

    REGULAR = "regular"
    NEAR_SINGULAR = "near_singular"
    RANK_DEFICIENT = "rank_deficient"
    UNBOUNDED_IDEAL_DIRECTION = "unbounded_ideal_direction"
    INVALID_MECHANISM_STATE = "invalid_mechanism_state"
    UNDEFINED_TASK_DIRECTION = "undefined_task_direction"


class StaticWrenchPhysicsError(ValueError):
    """Raised when gravity or payload fields are offered to this solver."""

    failure_code = "unsupported_physics"


def reject_unsupported_physics(payload: Mapping[str, Any] | None) -> None:
    """Refuse gravity/payload keys rather than silently ignoring them."""
    if payload is None:
        return
    for key in payload:
        if str(key) in FORBIDDEN_GRAVITY_KEYS:
            raise StaticWrenchPhysicsError(
                f"field {key!r} is outside the gravity-free static-wrench model"
            )


def jacobians_from_snapshot(
    snapshot: KinematicGeometrySnapshot,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Return ``(J_g, J_f, J_xu)`` arrays from a V4.0 snapshot.

    ``J_xu`` is the stored composite map; it is checked against
    ``composite_jacobian(J_f, J_g)`` rather than recomputed as a second kernel.
    """
    j_g = np.asarray(snapshot.j_u_to_q, dtype=np.float64)
    j_f = np.asarray(snapshot.j_q_to_x, dtype=np.float64)
    j_xu = np.asarray(snapshot.j_u_to_x, dtype=np.float64)
    composed = composite_jacobian(j_f, j_g)
    if j_xu.shape != composed.shape or not np.allclose(j_xu, composed, atol=1e-12, rtol=1e-12):
        raise ValueError("snapshot J_xu disagrees with V4.0 composite_jacobian(J_f, J_g)")
    return j_g, j_f, j_xu


@dataclass(frozen=True, slots=True)
class StaticWrenchCapability2D:
    """Exact 2D force set at one physical state."""

    q: NDArray[np.float64]
    u: NDArray[np.float64]
    x: NDArray[np.float64]
    j_g: NDArray[np.float64]
    j_f: NDArray[np.float64]
    j_xu: NDArray[np.float64]
    torque_limits: NDArray[np.float64]
    hrep_a: NDArray[np.float64]
    hrep_b: NDArray[np.float64]
    vertices: NDArray[np.float64] | None
    isotropic_radius: float
    directional_capacity: Mapping[str, float]
    undefined_directions: tuple[str, ...]
    rank: int
    singular_values: tuple[float, ...]
    status: WrenchStateStatus
    rank_attribution: Mapping[str, str]
    joint_torque_amplification: tuple[float, ...]

    def to_dict(self) -> dict[str, Any]:
        """JSON-friendly wrench record."""
        return {
            "schema_version": SCHEMA_VERSION,
            "q": [float(v) for v in np.asarray(self.q).reshape(-1)],
            "u": [float(v) for v in np.asarray(self.u).reshape(-1)],
            "x": [float(v) for v in np.asarray(self.x).reshape(-1)],
            "j_g": np.asarray(self.j_g).tolist(),
            "j_f": np.asarray(self.j_f).tolist(),
            "j_xu": np.asarray(self.j_xu).tolist(),
            "torque_limits": [float(v) for v in np.asarray(self.torque_limits)],
            "hrep_a": np.asarray(self.hrep_a).tolist(),
            "hrep_b": [float(v) for v in np.asarray(self.hrep_b)],
            "vertices": None if self.vertices is None else np.asarray(self.vertices).tolist(),
            "isotropic_radius": float(self.isotropic_radius),
            "directional_capacity": {k: float(v) for k, v in self.directional_capacity.items()},
            "undefined_directions": list(self.undefined_directions),
            "rank": int(self.rank),
            "singular_values": [float(v) for v in self.singular_values],
            "status": self.status.value,
            "rank_attribution": dict(self.rank_attribution),
            "joint_torque_amplification": [float(v) for v in self.joint_torque_amplification],
        }


def _as_limits(torque_limits: ArrayLike) -> NDArray[np.float64]:
    tau = np.asarray(torque_limits, dtype=np.float64).reshape(-1)
    if tau.size != 2 or np.any(tau <= 0.0) or not np.all(np.isfinite(tau)):
        raise ValueError("torque_limits must be two positive finite values")
    return tau


def _hrep(
    j_xu: NDArray[np.float64], tau: NDArray[np.float64]
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    a_map = np.asarray(j_xu, dtype=np.float64).T
    hrep_a = np.vstack([a_map, -a_map])
    hrep_b = np.concatenate([tau, tau])
    return a_map, hrep_a, hrep_b


def _sort_vertices(vertices: NDArray[np.float64]) -> NDArray[np.float64]:
    center = np.mean(vertices, axis=0)
    angles = np.arctan2(vertices[:, 1] - center[1], vertices[:, 0] - center[0])
    return vertices[np.argsort(angles)]


def _regular_vertices(a_map: NDArray[np.float64], tau: NDArray[np.float64]) -> NDArray[np.float64]:
    corners = np.array(
        [
            [tau[0], tau[1]],
            [tau[0], -tau[1]],
            [-tau[0], tau[1]],
            [-tau[0], -tau[1]],
        ],
        dtype=np.float64,
    )
    vertices = np.linalg.solve(a_map, corners.T).T
    return _sort_vertices(vertices)


def isotropic_radius(a_map: NDArray[np.float64], tau: NDArray[np.float64]) -> float:
    """Largest origin-centered Euclidean disk inside the force set."""
    radii: list[float] = []
    for i, row in enumerate(a_map):
        norm = float(np.linalg.norm(row))
        if norm <= DIRECTION_EPS:
            continue
        radii.append(float(tau[i]) / norm)
    if not radii:
        return float("inf")
    return float(min(radii))


def directional_capacity(
    a_map: NDArray[np.float64],
    tau: NDArray[np.float64],
    direction: ArrayLike,
) -> float:
    """Support of the force set along a unit direction."""
    d = np.asarray(direction, dtype=np.float64).reshape(-1)
    nrm = float(np.linalg.norm(d))
    if nrm <= DIRECTION_EPS or not np.all(np.isfinite(d)):
        return float("nan")
    d = d / nrm
    values: list[float] = []
    for i, row in enumerate(a_map):
        den = abs(float(np.dot(row, d)))
        if den <= DIRECTION_EPS:
            continue
        values.append(float(tau[i]) / den)
    if not values:
        return float("inf")
    return float(min(values))


def joint_torque_amplification(j_g: NDArray[np.float64]) -> tuple[float, ...]:
    """Return ``|tau_q_i / tau_u_i|`` for a diagonal square ``J_g``.

    Ideal virtual work gives ``tau_u = J_g.T @ tau_q``. On a certified
    separable branch this is axis-wise ``tau_u_i = (dq_i/du_i) tau_q_i``,
    so joint-torque amplification is ``1 / |dq/du|``.
    """
    jg = np.asarray(j_g, dtype=np.float64)
    if jg.shape != (2, 2):
        return (float("nan"), float("nan"))
    off = float(np.max(np.abs(jg - np.diag(np.diag(jg)))))
    if off > 1e-8:
        sv = np.linalg.svd(jg, compute_uv=False)
        if float(sv[-1]) <= DIRECTION_EPS:
            return (float("inf"), float("inf"))
        return tuple(float(1.0 / s) for s in sv)
    gains: list[float] = []
    for diag in np.diag(jg):
        mag = abs(float(diag))
        gains.append(float("inf") if mag <= DIRECTION_EPS else float(1.0 / mag))
    return tuple(gains)


def _attribution(
    *,
    rank_u_to_q,
    rank_q_to_x,
    rank_u_to_x,
    j_g: NDArray[np.float64],
) -> dict[str, str]:
    jg_full = bool(rank_u_to_q.full_rank)
    jf_full = bool(rank_q_to_x.full_rank)
    jxu_full = bool(rank_u_to_x.full_rank)
    min_gain = float(np.min(np.abs(np.diag(j_g)))) if j_g.shape == (2, 2) else float("nan")
    if not jf_full:
        cause = "arm_jacobian_rank_loss"
    elif not jg_full:
        cause = "mechanism_rank_loss"
    elif not jxu_full:
        cause = "composite_rank_loss"
    elif np.isfinite(min_gain) and min_gain < 0.05:
        cause = "four_bar_low_gain"
    else:
        cause = "none"
    return {
        "j_g": "full_rank" if jg_full else "rank_deficient",
        "j_f": "full_rank" if jf_full else "rank_deficient",
        "j_xu": "full_rank" if jxu_full else "rank_deficient",
        "primary_cause": cause,
    }


def _invalid_record(
    *,
    q: ArrayLike,
    u: ArrayLike | None = None,
    x: ArrayLike | None = None,
) -> StaticWrenchCapability2D:
    q_arr = np.asarray(q, dtype=np.float64).reshape(-1)
    u_arr = (
        np.full(q_arr.shape, np.nan, dtype=np.float64)
        if u is None
        else np.asarray(u, dtype=np.float64).reshape(-1)
    )
    x_arr = (
        np.array([np.nan, np.nan], dtype=np.float64)
        if x is None
        else np.asarray(x, dtype=np.float64).reshape(-1)
    )
    empty = np.full((2, 2), np.nan, dtype=np.float64)
    return StaticWrenchCapability2D(
        q=q_arr,
        u=u_arr,
        x=x_arr,
        j_g=empty,
        j_f=empty,
        j_xu=empty,
        torque_limits=np.asarray(DEFAULT_TORQUE_LIMITS, dtype=np.float64),
        hrep_a=np.full((4, 2), np.nan, dtype=np.float64),
        hrep_b=np.full(4, np.nan, dtype=np.float64),
        vertices=None,
        isotropic_radius=float("nan"),
        directional_capacity={},
        undefined_directions=(),
        rank=0,
        singular_values=(),
        status=WrenchStateStatus.INVALID_MECHANISM_STATE,
        rank_attribution={
            "j_g": "invalid",
            "j_f": "invalid",
            "j_xu": "invalid",
            "primary_cause": "invalid_mechanism_state",
        },
        joint_torque_amplification=(float("nan"), float("nan")),
    )


def static_wrench_from_maps(
    *,
    q: ArrayLike,
    u: ArrayLike,
    x: ArrayLike,
    j_g: ArrayLike,
    j_f: ArrayLike,
    j_xu: ArrayLike,
    torque_limits: ArrayLike = DEFAULT_TORQUE_LIMITS,
    named_directions: Mapping[str, ArrayLike | None] | None = None,
    rank_u_to_q=None,
    rank_q_to_x=None,
    rank_u_to_x=None,
    extra_physics: Mapping[str, Any] | None = None,
) -> StaticWrenchCapability2D:
    """Build the force set from already-computed maps (tests and snapshots)."""
    reject_unsupported_physics(extra_physics)
    tau = _as_limits(torque_limits)
    jg = np.asarray(j_g, dtype=np.float64)
    jf = np.asarray(j_f, dtype=np.float64)
    jxu = np.asarray(j_xu, dtype=np.float64)
    if jxu.shape != (2, 2):
        raise ValueError(f"planar 2D wrench requires J_xu shape (2, 2), got {jxu.shape}")
    a_map, hrep_a, hrep_b = _hrep(jxu, tau)
    report_xu = rank_u_to_x if rank_u_to_x is not None else rank_report(jxu)
    report_g = rank_u_to_q if rank_u_to_q is not None else rank_report(jg)
    report_f = rank_q_to_x if rank_q_to_x is not None else rank_report(jf)
    rank = int(report_xu.rank)
    sigmas = tuple(float(v) for v in report_xu.singular_values)
    directions = dict(named_directions or {})
    capacities: dict[str, float] = {}
    undefined: list[str] = []
    for name, vec in directions.items():
        if vec is None:
            capacities[name] = float("nan")
            undefined.append(str(name))
            continue
        capacities[name] = directional_capacity(a_map, tau, vec)
    attribution = _attribution(
        rank_u_to_q=report_g,
        rank_q_to_x=report_f,
        rank_u_to_x=report_xu,
        j_g=jg,
    )
    amp = joint_torque_amplification(jg)
    if rank < 2:
        r_iso = isotropic_radius(a_map, tau)
        unbounded = any(np.isinf(v) for v in capacities.values()) or r_iso == float("inf")
        if not unbounded:
            # Rank < 2 in 2D always leaves a left-null force direction.
            unbounded = True
        status = (
            WrenchStateStatus.UNBOUNDED_IDEAL_DIRECTION
            if unbounded
            else WrenchStateStatus.RANK_DEFICIENT
        )
        return StaticWrenchCapability2D(
            q=np.asarray(q, dtype=np.float64).reshape(-1),
            u=np.asarray(u, dtype=np.float64).reshape(-1),
            x=np.asarray(x, dtype=np.float64).reshape(-1),
            j_g=jg,
            j_f=jf,
            j_xu=jxu,
            torque_limits=tau,
            hrep_a=hrep_a,
            hrep_b=hrep_b,
            vertices=None,
            isotropic_radius=r_iso,
            directional_capacity=capacities,
            undefined_directions=tuple(undefined),
            rank=rank,
            singular_values=sigmas,
            status=status,
            rank_attribution=attribution,
            joint_torque_amplification=amp,
        )
    cond = report_xu.condition_number
    status = WrenchStateStatus.REGULAR
    if cond is not None and cond >= NEAR_SINGULAR_CONDITION:
        status = WrenchStateStatus.NEAR_SINGULAR
    vertices = _regular_vertices(a_map, tau)
    r_iso = isotropic_radius(a_map, tau)
    return StaticWrenchCapability2D(
        q=np.asarray(q, dtype=np.float64).reshape(-1),
        u=np.asarray(u, dtype=np.float64).reshape(-1),
        x=np.asarray(x, dtype=np.float64).reshape(-1),
        j_g=jg,
        j_f=jf,
        j_xu=jxu,
        torque_limits=tau,
        hrep_a=hrep_a,
        hrep_b=hrep_b,
        vertices=vertices,
        isotropic_radius=r_iso,
        directional_capacity=capacities,
        undefined_directions=tuple(undefined),
        rank=rank,
        singular_values=sigmas,
        status=status,
        rank_attribution=attribution,
        joint_torque_amplification=amp,
    )


def static_wrench_from_snapshot(
    snapshot: KinematicGeometrySnapshot,
    *,
    torque_limits: ArrayLike = DEFAULT_TORQUE_LIMITS,
    named_directions: Mapping[str, ArrayLike | None] | None = None,
    extra_physics: Mapping[str, Any] | None = None,
) -> StaticWrenchCapability2D:
    """Build the gravity-free 2D force set from a V4.0 geometry snapshot."""
    j_g, j_f, j_xu = jacobians_from_snapshot(snapshot)
    directions = named_directions
    if directions is None:
        directions = named_task_directions(snapshot.x)
    return static_wrench_from_maps(
        q=snapshot.q,
        u=snapshot.u,
        x=snapshot.x,
        j_g=j_g,
        j_f=j_f,
        j_xu=j_xu,
        torque_limits=torque_limits,
        named_directions=directions,
        rank_u_to_q=snapshot.rank_u_to_q,
        rank_q_to_x=snapshot.rank_q_to_x,
        rank_u_to_x=snapshot.rank_u_to_x,
        extra_physics=extra_physics,
    )


def static_wrench_at_state(
    robot: KinematicTransmissionRobotModel,
    state: PhysicalState,
    *,
    torque_limits: ArrayLike = DEFAULT_TORQUE_LIMITS,
) -> StaticWrenchCapability2D:
    """Thin V4.0 snapshot wrapper from a certified physical state."""
    try:
        snapshot = geometry_snapshot(robot, state)
    except (TransmissionGeometryError, ValueError, NotImplementedError):
        return _invalid_record(q=state.q, u=state.u)
    return static_wrench_from_snapshot(snapshot, torque_limits=torque_limits)


def static_wrench_at_q(
    robot: KinematicTransmissionRobotModel,
    q: ArrayLike,
    *,
    torque_limits: ArrayLike = DEFAULT_TORQUE_LIMITS,
) -> StaticWrenchCapability2D:
    """Evaluate the force set at an output coordinate, or mark it invalid."""
    q_arr = np.asarray(q, dtype=np.float64).reshape(-1)
    try:
        candidates = robot.states_from_output(q_arr)
    except (ValueError, NotImplementedError):
        return _invalid_record(q=q_arr)
    if not candidates:
        return _invalid_record(q=q_arr)
    return static_wrench_at_state(robot, candidates[0].state, torque_limits=torque_limits)


def evaluate_static_wrench_grid(
    robot: KinematicTransmissionRobotModel,
    q_samples: ArrayLike,
    *,
    torque_limits: ArrayLike = DEFAULT_TORQUE_LIMITS,
    cache_key: str | None = None,
) -> tuple[StaticWrenchCapability2D, ...]:
    """Evaluate a Q grid. Cached results match scalar evaluation byte-for-byte."""
    qs = np.asarray(q_samples, dtype=np.float64)
    if qs.ndim != 2 or qs.shape[1] != 2:
        raise ValueError(f"q_samples must have shape (N, 2), got {qs.shape}")
    tau = _as_limits(torque_limits)
    key = cache_key
    if key is not None:
        cached = _GRID_CACHE.get(key)
        if cached is not None:
            return cached
    rows = tuple(static_wrench_at_q(robot, q, torque_limits=tau) for q in qs)
    if key is not None:
        _GRID_CACHE[key] = rows
    return rows


def grid_cache_key(
    *,
    registry_hash: str,
    case_id: str,
    mechanism_id: str,
    q_samples: ArrayLike,
    torque_limits: ArrayLike,
) -> str:
    """Deterministic cache key for a span-case grid evaluation."""
    qs = np.asarray(q_samples, dtype=np.float64)
    tau = _as_limits(torque_limits)
    digest = np.array2string(qs, precision=16, separator=",", suppress_small=False)
    return "|".join(
        [
            SCHEMA_VERSION,
            registry_hash,
            case_id,
            mechanism_id,
            digest,
            ",".join(f"{v:.16g}" for v in tau),
        ]
    )
