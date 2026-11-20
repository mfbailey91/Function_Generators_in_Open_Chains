"""Intrinsic planar velocity sets and explicitly selected differential IK.

The finite normalized actuator-rate box is a scientific comparison convention,
not a motor specification.  Its forward image always uses the stored V4.0
Jacobian.  Physical rank reports are inherited without reclassification.

At inherited rank loss, ray speeds describe an explicitly recorded truncated
rank model.  Raw corner images and support values remain available separately;
a numerically discarded singular value never disappears from those raw data.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from enum import Enum, StrEnum
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from inequality_mechanisms.metrics.wrench_directions import named_task_directions
from inequality_mechanisms.transmission_geometry.differential import (
    RankReport,
    composite_jacobian,
)
from inequality_mechanisms.transmission_geometry.errors import (
    DifferentialShapeError,
    DifferentialSingularityError,
)
from inequality_mechanisms.transmission_geometry.metrics import (
    validate_positive_definite,
)
from inequality_mechanisms.transmission_geometry.snapshot import (
    KinematicGeometrySnapshot,
)

VELOCITY_SCHEMA_VERSION = "v4.4.velocity_capability.v1"
DIFFERENTIAL_IK_SCHEMA_VERSION = "v4.4.differential_ik.v1"
DEFAULT_RATE_LIMITS = (1.0, 1.0)
NEAR_SINGULAR_CONDITION = 1e6
RANGE_DIRECTION_TOLERANCE = float(64.0 * np.finfo(np.float64).eps)
RATE_UTILIZATION_TOLERANCE = float(32.0 * np.finfo(np.float64).eps)


class VelocityStateStatus(StrEnum):
    """Conditioning of the source map, never unbounded velocity capability."""

    REGULAR = "regular"
    NEAR_SINGULAR = "near_singular"
    BOUNDED_RANK_DEFICIENT = "bounded_rank_deficient"
    BOUNDED_ZERO_RANK = "bounded_zero_rank"


class DifferentialIKPolicy(StrEnum):
    EXACT = "exact"
    MINIMUM_NORM = "minimum_norm"
    DAMPED_LEAST_SQUARES = "damped_least_squares"


class RatePolicy(StrEnum):
    REPORT_ONLY = "report_only"
    UNIFORM_SCALE = "uniform_scale"


class VelocityNumericalError(ValueError):
    """A finite input produced an unrepresentable numerical calculation."""

    failure_code = "nonfinite_velocity_calculation"


def _array(value: ArrayLike, shape: tuple[int, ...], name: str) -> NDArray[np.float64]:
    try:
        array = np.array(value, dtype=np.float64, copy=True)
    except (TypeError, ValueError) as exc:
        raise DifferentialShapeError(f"{name} must be a finite array") from exc
    if array.shape != shape or not np.all(np.isfinite(array)):
        raise DifferentialShapeError(
            f"{name} must be finite with shape {shape}, got {array.shape}"
        )
    return array


def _finite(value: NDArray[np.float64] | float, name: str) -> None:
    if not np.all(np.isfinite(value)):
        raise VelocityNumericalError(f"{name} is not finite")


def _vector(values: NDArray[np.float64]) -> tuple[float, ...]:
    return tuple(float(value) for value in values)


def _matrix(values: NDArray[np.float64]) -> tuple[tuple[float, ...], ...]:
    return tuple(_vector(row) for row in values)


def _strict_copy(value: Any) -> Any:
    """Copy transport records while refusing NaN/Infinity and opaque objects."""
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise DifferentialShapeError("record keys must be strings")
        return {key: _strict_copy(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_strict_copy(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (float, np.floating)):
        number = float(value)
        _finite(number, "serialized value")
        return number
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if value is None or isinstance(value, str):
        return value
    raise DifferentialShapeError(f"unsupported record value {type(value).__name__}")


def _rank_record(report: RankReport, name: str) -> dict[str, Any]:
    if (
        report.shape != (2, 2)
        or report.required_full_rank != 2
        or report.rank not in (0, 1, 2)
        or report.full_rank != (report.rank == 2)
        or len(report.singular_values) != 2
        or not np.isfinite(report.tolerance)
        or report.tolerance < 0.0
    ):
        raise DifferentialShapeError(f"{name} is not a valid planar rank report")
    singulars = np.asarray(report.singular_values, dtype=np.float64)
    if (
        not np.all(np.isfinite(singulars))
        or np.any(singulars < 0.0)
        or singulars[0] < singulars[1]
        or int(np.count_nonzero(singulars > report.tolerance)) != report.rank
    ):
        raise DifferentialShapeError(f"{name} has inconsistent inherited rank data")
    condition = report.condition_number
    if report.full_rank:
        with np.errstate(over="ignore", divide="ignore"):
            expected_condition = float(singulars[0] / singulars[-1])
        if (
            condition is None
            or not np.isfinite(condition)
            or not np.isfinite(expected_condition)
            or not np.isclose(
                condition,
                expected_condition,
                rtol=16.0 * np.finfo(np.float64).eps,
                atol=0.0,
            )
        ):
            raise DifferentialShapeError(
                f"{name} condition number disagrees with inherited singular values"
            )
    elif condition is not None:
        raise DifferentialShapeError(
            f"{name} condition number must be unavailable at inherited rank loss"
        )
    return _strict_copy(report.to_dict())  # type: ignore[no-any-return]


def _source(snapshot: KinematicGeometrySnapshot) -> dict[str, Any]:
    if not isinstance(snapshot, KinematicGeometrySnapshot):
        raise TypeError("snapshot must be a KinematicGeometrySnapshot")
    j_g = _array(snapshot.j_u_to_q, (2, 2), "snapshot.j_u_to_q")
    j_f = _array(snapshot.j_q_to_x, (2, 2), "snapshot.j_q_to_x")
    j_xu = _array(snapshot.j_u_to_x, (2, 2), "snapshot.j_u_to_x")
    if not np.allclose(j_xu, composite_jacobian(j_f, j_g), rtol=1e-12, atol=1e-12):
        raise DifferentialShapeError("stored J_xu disagrees with J_f @ J_g")
    return {
        "u": _vector(_array(snapshot.u, (2,), "snapshot.u")),
        "q": _vector(_array(snapshot.q, (2,), "snapshot.q")),
        "x": _vector(_array(snapshot.x, (2,), "snapshot.x")),
        "j_g": _matrix(j_g),
        "j_f": _matrix(j_f),
        "j_xu": _matrix(j_xu),
        "rank_reports": {
            "u_to_q": _rank_record(snapshot.rank_u_to_q, "rank_u_to_q"),
            "q_to_x": _rank_record(snapshot.rank_q_to_x, "rank_q_to_x"),
            "u_to_x": _rank_record(snapshot.rank_u_to_x, "rank_u_to_x"),
        },
        "provenance": {
            "source_snapshot": _strict_copy(deepcopy(snapshot.provenance)),
            "rank_policy": "inherited_from_geometry_snapshot",
            "rate_box_convention": "normalized_actuator_coordinate_rates",
            "physical_motor_limits": False,
            "near_singular_condition_threshold": NEAR_SINGULAR_CONDITION,
        },
    }


def _limits(value: ArrayLike) -> NDArray[np.float64]:
    limits = _array(value, (2,), "rate_limits")
    if np.any(limits <= 0.0):
        raise DifferentialShapeError("rate_limits must be strictly positive")
    return limits


def _status(report: RankReport) -> VelocityStateStatus:
    if report.rank == 0:
        return VelocityStateStatus.BOUNDED_ZERO_RANK
    if report.rank == 1:
        return VelocityStateStatus.BOUNDED_RANK_DEFICIENT
    if (
        report.condition_number is not None
        and report.condition_number >= NEAR_SINGULAR_CONDITION
    ):
        return VelocityStateStatus.NEAR_SINGULAR
    return VelocityStateStatus.REGULAR


def _unit_direction(value: ArrayLike | None, name: str) -> NDArray[np.float64] | None:
    if value is None:
        return None
    direction = _array(value, (2,), f"direction {name!r}")
    scale = float(np.max(np.abs(direction)))
    if scale == 0.0:
        return None
    scaled = direction / scale
    return scaled / float(np.linalg.norm(scaled))


def _inherited_svd(
    jacobian: NDArray[np.float64], rank: int
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Get vectors for the already selected rank; never select another cutoff."""
    left, singulars, right_t = np.linalg.svd(jacobian, full_matrices=False)
    if np.any(singulars[:rank] <= 0.0):
        raise VelocityNumericalError(
            "inherited rank cannot be represented by the stored map"
        )
    return left[:, :rank], singulars[:rank], right_t[:rank, :]


@dataclass(frozen=True, slots=True)
class VelocityCapability2D:
    """Raw finite velocity image plus explicitly identified ray-speed model."""

    u: tuple[float, ...]
    q: tuple[float, ...]
    x: tuple[float, ...]
    j_g: tuple[tuple[float, ...], ...]
    j_f: tuple[tuple[float, ...], ...]
    j_xu: tuple[tuple[float, ...], ...]
    rate_limits: tuple[float, ...]
    actuator_corners: tuple[tuple[float, ...], ...]
    velocity_corners: tuple[tuple[float, ...], ...]
    directions: Mapping[str, tuple[float, ...] | None]
    directional_support: Mapping[str, float | None]
    directional_ray_speed: Mapping[str, float | None]
    direction_status: Mapping[str, str]
    isotropic_speed: float
    rank: int
    status: VelocityStateStatus
    ray_model: str
    ray_jacobian: tuple[tuple[float, ...], ...]
    ray_velocity_corners: tuple[tuple[float, ...], ...]
    rank_reports: Mapping[str, Any]
    provenance: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        record = {field: getattr(self, field) for field in self.__dataclass_fields__}
        record["schema_version"] = VELOCITY_SCHEMA_VERSION
        record["support_model"] = "raw_stored_jacobian_rate_box_image"
        record["isotropic_speed_model"] = self.ray_model
        return _strict_copy(record)  # type: ignore[no-any-return]


def velocity_capability_from_snapshot(
    snapshot: KinematicGeometrySnapshot,
    rate_limits: ArrayLike = DEFAULT_RATE_LIMITS,
    directions: Mapping[str, ArrayLike | None] | None = None,
) -> VelocityCapability2D:
    """Map a finite rate box through a frozen 2-by-2 geometry snapshot.

    ``directional_support[d]`` is the maximum projection onto unit ``d``.
    ``directional_ray_speed[d]`` is the furthest point *on* the ray ``s*d``.
    These differ in general. At inherited rank loss the latter uses the
    explicitly stored inherited-rank model; raw corner images/support are
    never truncated. Undefined directions are represented by ``None``.
    """
    source = _source(snapshot)
    limits = _limits(rate_limits)
    jacobian = np.asarray(source["j_xu"], dtype=np.float64)
    rank = snapshot.rank_u_to_x.rank
    actuator_corners = (
        np.asarray([[-1.0, -1.0], [1.0, -1.0], [1.0, 1.0], [-1.0, 1.0]]) * limits
    )
    with np.errstate(over="ignore", invalid="ignore"):
        corners = actuator_corners @ jacobian.T
    _finite(corners, "velocity corner images")
    if rank == 2:
        ray_jacobian = jacobian.copy()
        ray_model = "raw_stored_jacobian"
        inverse = np.asarray(np.linalg.solve(jacobian, np.eye(2)), dtype=np.float64)
        _finite(inverse, "full-rank inverse")
        row_lengths = np.hypot(inverse[:, 0], inverse[:, 1])
        isotropic_speed = float(np.min(limits / row_lengths))
        range_axis = None
    else:
        left, singulars, right_t = _inherited_svd(jacobian, rank)
        ray_jacobian = (left * singulars) @ right_t
        ray_model = "explicit_inherited_rank_svd_truncation"
        inverse = None
        isotropic_speed = 0.0
        range_axis = left[:, 0] if rank == 1 else None
    direction_inputs = (
        named_task_directions(source["x"]) if directions is None else directions
    )
    normalized: dict[str, tuple[float, ...] | None] = {}
    supports: dict[str, float | None] = {}
    rays: dict[str, float | None] = {}
    statuses: dict[str, str] = {}
    for name, values in direction_inputs.items():
        if not isinstance(name, str) or not name:
            raise DifferentialShapeError("direction names must be nonempty strings")
        direction = _unit_direction(values, name)
        normalized[name] = None if direction is None else _vector(direction)
        if direction is None:
            supports[name] = None
            rays[name] = None
            statuses[name] = "undefined_direction"
            continue
        with np.errstate(over="ignore", invalid="ignore"):
            support = float(np.sum(limits * np.abs(jacobian.T @ direction)))
        _finite(support, f"support in {name}")
        supports[name] = support
        if inverse is not None:
            with np.errstate(over="ignore", invalid="ignore"):
                # A matrix inverse followed by multiplication introduces an
                # avoidable cancellation error on nearly dependent rows.
                # Solve the actual normalized target, exactly as the inverse
                # command policy does, so ray capacity and rate demand agree.
                demand = np.linalg.solve(jacobian, direction) / limits
            _finite(demand, f"unit-direction demand in {name}")
            rays[name] = 1.0 / float(np.max(np.abs(demand)))
            statuses[name] = "defined"
        elif range_axis is not None:
            orthogonal = direction - float(range_axis @ direction) * range_axis
            if float(np.linalg.norm(orthogonal)) > RANGE_DIRECTION_TOLERANCE:
                rays[name] = 0.0
                statuses[name] = "outside_inherited_range"
            else:
                rays[name] = float(np.sum(limits * np.abs(ray_jacobian.T @ direction)))
                statuses[name] = "defined_in_inherited_range"
        else:
            rays[name] = 0.0
            statuses[name] = "zero_inherited_range"
    source["provenance"]["ray_range_direction_tolerance"] = RANGE_DIRECTION_TOLERANCE
    result = VelocityCapability2D(
        **source,
        rate_limits=_vector(limits),
        actuator_corners=_matrix(actuator_corners),
        velocity_corners=_matrix(corners),
        directions=normalized,
        directional_support=supports,
        directional_ray_speed=rays,
        direction_status=statuses,
        isotropic_speed=isotropic_speed,
        rank=rank,
        status=_status(snapshot.rank_u_to_x),
        ray_model=ray_model,
        ray_jacobian=_matrix(ray_jacobian),
        ray_velocity_corners=_matrix(actuator_corners @ ray_jacobian.T),
    )
    result.to_dict()
    return result


@dataclass(frozen=True, slots=True)
class DifferentialIKResult:
    """One instantaneous inverse command and separately assessed rate demand."""

    u: tuple[float, ...]
    q: tuple[float, ...]
    x: tuple[float, ...]
    j_g: tuple[tuple[float, ...], ...]
    j_f: tuple[tuple[float, ...], ...]
    j_xu: tuple[tuple[float, ...], ...]
    target_velocity: tuple[float, ...]
    requested_rates: tuple[float, ...]
    commanded_rates: tuple[float, ...]
    requested_achieved_velocity: tuple[float, ...]
    achieved_velocity: tuple[float, ...]
    requested_residual: tuple[float, ...]
    residual: tuple[float, ...]
    requested_residual_norm: float
    residual_norm: float
    requested_weighted_rate_norm: float
    commanded_weighted_rate_norm: float
    rate_limits: tuple[float, ...]
    utilization_requested: tuple[float, ...]
    utilization_commanded: tuple[float, ...]
    requested_peak_utilization: float
    commanded_peak_utilization: float
    requested_feasible: bool
    commanded_feasible: bool
    requested_saturated_channels: tuple[int, ...]
    commanded_saturated_channels: tuple[int, ...]
    requested_exceeding_channels: tuple[int, ...]
    commanded_exceeding_channels: tuple[int, ...]
    applied_scale: float
    policy: DifferentialIKPolicy
    rate_policy: RatePolicy
    damping: float | None
    actuator_weight: tuple[tuple[float, ...], ...]
    solver_status: str
    command_status: str
    physical_status: VelocityStateStatus
    solver_rank_policy: str
    solver_jacobian: tuple[tuple[float, ...], ...]
    rank_reports: Mapping[str, Any]
    provenance: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        record = {field: getattr(self, field) for field in self.__dataclass_fields__}
        record["schema_version"] = DIFFERENTIAL_IK_SCHEMA_VERSION
        record["residual_convention"] = "target_minus_raw_stored_jacobian_command"
        return _strict_copy(record)  # type: ignore[no-any-return]


def _inverse_rates(
    jacobian: NDArray[np.float64],
    target: NDArray[np.float64],
    weight: NDArray[np.float64],
    report: RankReport,
    policy: DifferentialIKPolicy,
    damping: float | None,
) -> tuple[NDArray[np.float64], NDArray[np.float64], str, str]:
    if policy == DifferentialIKPolicy.EXACT:
        if not report.full_rank:
            raise DifferentialSingularityError(
                "exact differential IK requires inherited full rank",
                operation="differential_ik_exact",
                shape=report.shape,
                rank=report.rank,
                required_rank=2,
                singular_values=report.singular_values,
                tolerance=report.tolerance,
            )
        return (
            np.asarray(np.linalg.solve(jacobian, target), dtype=np.float64),
            jacobian.copy(),
            "exact",
            "raw_full_rank_exact_solve",
        )
    if policy == DifferentialIKPolicy.MINIMUM_NORM:
        if report.rank == 2:
            rates = np.linalg.solve(jacobian, target)
            model = jacobian.copy()
        else:
            left, singulars, right_t = _inherited_svd(jacobian, report.rank)
            model = (left * singulars) @ right_t
            if report.rank == 0:
                rates = np.zeros(2)
            else:
                # Minimize u.T W u subject to V_r.T u = S_r^-1 U_r.T v.
                # The inherited rank is selected before weighting. Whitening
                # must not silently establish a different physical cutoff.
                weighted_right = np.linalg.solve(weight, right_t.T)
                constraint = (left.T @ target) / singulars
                rates = weighted_right @ np.linalg.solve(
                    right_t @ weighted_right, constraint
                )
        return (
            np.asarray(rates, dtype=np.float64),
            model,
            "exact" if report.rank == 2 else "projected",
            "explicit_inherited_rank_weighted_minimum_norm",
        )
    assert damping is not None
    # W = R.T R; solve in z = R u. All singular modes enter the positive-
    # damping filter. This avoids squared conditioning in normal equations.
    upper = np.linalg.cholesky(weight).T
    whitened = np.linalg.solve(upper.T, jacobian.T).T
    left, singulars, right_t = np.linalg.svd(whitened, full_matrices=False)
    # Scaling avoids overflow in both s*s + damping*damping and its square
    # root, even when the final filter is representable for extreme inputs.
    scale = np.maximum(singulars, damping)
    scaled_singulars = singulars / scale
    scaled_damping = damping / scale
    filters = (scaled_singulars / (scaled_singulars**2 + scaled_damping**2)) / scale
    whitened_rates = right_t.T @ (filters * (left.T @ target))
    rates = np.linalg.solve(upper, whitened_rates)
    return (
        np.asarray(rates, dtype=np.float64),
        jacobian.copy(),
        "regularized",
        "positive_damping_no_rank_truncation",
    )


def _channels(utilization: NDArray[np.float64], *, exceeding: bool) -> tuple[int, ...]:
    mask = (
        utilization > 1.0 + RATE_UTILIZATION_TOLERANCE
        if exceeding
        else np.abs(utilization - 1.0) <= RATE_UTILIZATION_TOLERANCE
    )
    return tuple(int(index) for index in np.flatnonzero(mask))


def differential_ik_from_snapshot(
    snapshot: KinematicGeometrySnapshot,
    target_velocity: ArrayLike,
    *,
    policy: DifferentialIKPolicy | str,
    damping: float | None = None,
    actuator_weight: ArrayLike | None = None,
    rate_limits: ArrayLike = DEFAULT_RATE_LIMITS,
    rate_policy: RatePolicy | str = RatePolicy.REPORT_ONLY,
) -> DifferentialIKResult:
    """Solve one explicit inverse policy and report normalized rate demand.

    ``minimum_norm`` projects onto the inherited-rank task range and minimizes
    ``u.T W u`` there. ``damped_least_squares`` minimizes
    ``||J u-v||^2 + damping^2*u.T W u`` with strictly positive damping.
    Every achieved velocity and residual is measured with the raw stored J.

    ``report_only`` retains an infeasible request unchanged and labels it.
    ``uniform_scale`` scales the whole rate vector into the box, preserving
    its achieved task direction. It is not box-constrained least squares.
    """
    source = _source(snapshot)
    target = _array(target_velocity, (2,), "target_velocity")
    limits = _limits(rate_limits)
    selected_policy = DifferentialIKPolicy(policy)
    selected_rate_policy = RatePolicy(rate_policy)
    if selected_policy == DifferentialIKPolicy.DAMPED_LEAST_SQUARES:
        if damping is None or not np.isfinite(damping) or damping <= 0.0:
            raise DifferentialShapeError(
                "damping must be explicitly finite and positive"
            )
        damping = float(damping)
    elif damping is not None:
        raise DifferentialShapeError("damping is only defined for damped_least_squares")
    weight = _array(
        snapshot.actuator_weight if actuator_weight is None else actuator_weight,
        (2, 2),
        "actuator_weight",
    )
    validate_positive_definite(weight)
    # The validator permits roundoff-sized asymmetry, so use its symmetric
    # interpretation consistently in Cholesky and the reported objective.
    weight = 0.5 * (weight + weight.T)
    jacobian = np.asarray(source["j_xu"], dtype=np.float64)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        requested, model, solver_status, rank_policy = _inverse_rates(
            jacobian,
            target,
            weight,
            snapshot.rank_u_to_x,
            selected_policy,
            damping,
        )
        utilization_requested = np.abs(requested) / limits
    _finite(requested, "requested actuator rates")
    _finite(utilization_requested, "requested normalized utilization")
    peak_requested = float(np.max(utilization_requested))
    scale = (
        1.0 / peak_requested
        if selected_rate_policy == RatePolicy.UNIFORM_SCALE and peak_requested > 1.0
        else 1.0
    )
    commanded = scale * requested
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        utilization_commanded = np.abs(commanded) / limits
        requested_achieved = jacobian @ requested
        achieved = jacobian @ commanded
        requested_residual = target - requested_achieved
        residual = target - achieved
    for name, value in (
        ("commanded utilization", utilization_commanded),
        ("requested achieved velocity", requested_achieved),
        ("achieved velocity", achieved),
        ("requested residual", requested_residual),
        ("residual", residual),
    ):
        _finite(value, name)
    peak_commanded = float(np.max(utilization_commanded))
    requested_feasible = peak_requested <= 1.0 + RATE_UTILIZATION_TOLERANCE
    commanded_feasible = peak_commanded <= 1.0 + RATE_UTILIZATION_TOLERANCE
    command_status = (
        "uniformly_scaled_to_rate_box"
        if scale < 1.0
        else "within_rate_box"
        if commanded_feasible
        else "outside_rate_box"
    )
    upper = np.linalg.cholesky(weight).T
    weighted_requested = upper @ requested
    weighted_commanded = upper @ commanded
    source["provenance"].update(
        {
            "actuator_weight_source": "snapshot"
            if actuator_weight is None
            else "caller",
            "rate_utilization_tolerance": RATE_UTILIZATION_TOLERANCE,
            "saturation_definition": "absolute_normalized_rate_equal_to_one",
            "residual_evaluation": "raw_stored_jacobian",
        }
    )
    result = DifferentialIKResult(
        **source,
        target_velocity=_vector(target),
        requested_rates=_vector(requested),
        commanded_rates=_vector(commanded),
        requested_achieved_velocity=_vector(requested_achieved),
        achieved_velocity=_vector(achieved),
        requested_residual=_vector(requested_residual),
        residual=_vector(residual),
        requested_residual_norm=float(np.hypot(*requested_residual)),
        residual_norm=float(np.hypot(*residual)),
        requested_weighted_rate_norm=float(np.hypot(*weighted_requested)),
        commanded_weighted_rate_norm=float(np.hypot(*weighted_commanded)),
        rate_limits=_vector(limits),
        utilization_requested=_vector(utilization_requested),
        utilization_commanded=_vector(utilization_commanded),
        requested_peak_utilization=peak_requested,
        commanded_peak_utilization=peak_commanded,
        requested_feasible=requested_feasible,
        commanded_feasible=commanded_feasible,
        requested_saturated_channels=_channels(utilization_requested, exceeding=False),
        commanded_saturated_channels=_channels(utilization_commanded, exceeding=False),
        requested_exceeding_channels=_channels(utilization_requested, exceeding=True),
        commanded_exceeding_channels=_channels(utilization_commanded, exceeding=True),
        applied_scale=scale,
        policy=selected_policy,
        rate_policy=selected_rate_policy,
        damping=damping,
        actuator_weight=_matrix(weight),
        solver_status=solver_status,
        command_status=command_status,
        physical_status=_status(snapshot.rank_u_to_x),
        solver_rank_policy=rank_policy,
        solver_jacobian=_matrix(model),
    )
    result.to_dict()
    return result


__all__ = [
    "DEFAULT_RATE_LIMITS",
    "DIFFERENTIAL_IK_SCHEMA_VERSION",
    "VELOCITY_SCHEMA_VERSION",
    "DifferentialIKPolicy",
    "DifferentialIKResult",
    "RatePolicy",
    "VelocityCapability2D",
    "VelocityNumericalError",
    "VelocityStateStatus",
    "differential_ik_from_snapshot",
    "velocity_capability_from_snapshot",
]
