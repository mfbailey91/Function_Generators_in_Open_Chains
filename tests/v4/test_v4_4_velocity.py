"""V4-400–403 analytic controls for intrinsic velocity and differential IK."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

import numpy as np
import pytest

from inequality_mechanisms.adapters import planar_2r_operating_branch_robot
from inequality_mechanisms.kinematics.planar_2r import Planar2R
from inequality_mechanisms.mechanisms import unit_gearbox_branch
from inequality_mechanisms.metrics.velocity import (
    DifferentialIKPolicy,
    VelocityNumericalError,
    VelocityStateStatus,
    differential_ik_from_snapshot,
    velocity_capability_from_snapshot,
)
from inequality_mechanisms.transmission_geometry.differential import rank_report
from inequality_mechanisms.transmission_geometry.errors import (
    DifferentialShapeError,
    DifferentialSingularityError,
)
from inequality_mechanisms.transmission_geometry.snapshot import (
    METRIC_STATUS_AVAILABLE,
    METRIC_STATUS_RANK_DEFICIENT,
    KinematicGeometrySnapshot,
    geometry_snapshot,
)


def _rows(values: Any) -> tuple[tuple[float, ...], ...]:
    return tuple(tuple(float(value) for value in row) for row in values)


def _snapshot(
    jacobian: Any,
    *,
    j_g: Any | None = None,
    j_f: Any | None = None,
    tolerance: float | None = None,
    weight: Any | None = None,
    x: tuple[float, float] = (1.0, 1.0),
) -> KinematicGeometrySnapshot:
    """Explicit synthetic fixture; no capability implementation used here."""
    composite = np.asarray(jacobian, dtype=np.float64)
    j_g = composite if j_g is None else np.asarray(j_g, dtype=np.float64)
    j_f = np.eye(2) if j_f is None else np.asarray(j_f, dtype=np.float64)
    weight = np.eye(2) if weight is None else np.asarray(weight, dtype=np.float64)
    report_g = rank_report(j_g, tolerance=tolerance)
    inverse = np.linalg.inv(j_g) if report_g.full_rank else None
    return KinematicGeometrySnapshot(
        u=(0.1, -0.2),
        q=(0.2, -0.1),
        x=x,
        j_u_to_q=_rows(j_g),
        j_q_to_x=_rows(j_f),
        j_u_to_x=_rows(composite),
        rank_u_to_q=report_g,
        rank_q_to_x=rank_report(j_f, tolerance=tolerance),
        rank_u_to_x=rank_report(composite, tolerance=tolerance),
        actuator_weight=_rows(weight),
        actuator_metric_on_q=(
            None if inverse is None else _rows(inverse.T @ weight @ inverse)
        ),
        mobility_on_q=_rows(j_g @ np.linalg.solve(weight, j_g.T)),
        mobility_on_x=_rows(composite @ np.linalg.solve(weight, composite.T)),
        metric_status=(
            METRIC_STATUS_AVAILABLE
            if report_g.full_rank
            else METRIC_STATUS_RANK_DEFICIENT
        ),
        provenance={"fixture": "analytic", "nested": {"revision": "source-v1"}},
    )


def test_identity_box_axis_and_diagonal_rays() -> None:
    snapshot = _snapshot(np.eye(2))
    result = velocity_capability_from_snapshot(
        snapshot, directions={"x": [1.0, 0.0], "diagonal": [1.0, 1.0]}
    )
    np.testing.assert_array_equal(result.velocity_corners, result.actuator_corners)
    assert result.rate_limits == (1.0, 1.0)
    assert result.directional_ray_speed["x"] == pytest.approx(1.0)
    assert result.directional_ray_speed["diagonal"] == pytest.approx(np.sqrt(2.0))
    assert result.isotropic_speed == pytest.approx(1.0)
    assert result.status == VelocityStateStatus.REGULAR
    inverse = differential_ik_from_snapshot(snapshot, [0.2, -0.4], policy="exact")
    np.testing.assert_array_equal(inverse.requested_rates, [0.2, -0.4])
    np.testing.assert_array_equal(inverse.achieved_velocity, [0.2, -0.4])
    assert inverse.requested_feasible and inverse.commanded_feasible
    assert inverse.residual_norm == 0.0


@pytest.mark.parametrize("first_ratio", [2.0, -2.0])
def test_anisotropic_signed_gear_has_distinct_support_and_ray(
    first_ratio: float,
) -> None:
    jacobian = np.diag([first_ratio, 0.5])
    snapshot = _snapshot(jacobian)
    result = velocity_capability_from_snapshot(
        snapshot,
        directions={"x": [1.0, 0.0], "y": [0.0, 1.0], "diagonal": [1.0, 1.0]},
    )
    np.testing.assert_allclose(
        result.velocity_corners, np.asarray(result.actuator_corners) @ jacobian.T
    )
    assert result.directional_ray_speed["x"] == pytest.approx(2.0)
    assert result.directional_ray_speed["y"] == pytest.approx(0.5)
    assert result.directional_support["diagonal"] == pytest.approx(2.5 / np.sqrt(2.0))
    assert result.directional_ray_speed["diagonal"] == pytest.approx(0.5 * np.sqrt(2.0))
    assert result.isotropic_speed == pytest.approx(0.5)
    command = differential_ik_from_snapshot(snapshot, [1.0, 1.0], policy="exact")
    np.testing.assert_allclose(command.requested_rates, [1.0 / first_ratio, 2.0])
    assert not command.requested_feasible
    assert command.command_status == "outside_rate_box"


def test_analytic_regular_planar_fixture_has_correct_endpoint() -> None:
    branch = unit_gearbox_branch(
        2, input_lower=[-np.pi, -np.pi], input_upper=[np.pi, np.pi]
    )
    robot = planar_2r_operating_branch_robot(branch, planar_fk=Planar2R(L1=1.0, L2=1.0))
    snapshot = geometry_snapshot(robot, robot.state_from_input([0.0, np.pi / 2.0]))
    np.testing.assert_allclose(snapshot.x, [1.0, 1.0], atol=1e-15)
    np.testing.assert_allclose(
        snapshot.j_u_to_x, [[-1.0, -1.0], [1.0, 0.0]], atol=1e-15
    )
    result = velocity_capability_from_snapshot(snapshot)
    command = differential_ik_from_snapshot(snapshot, [-0.5, 0.25], policy="exact")
    np.testing.assert_allclose(command.requested_rates, [0.25, 0.25], atol=1e-15)
    assert result.directional_ray_speed["positive_x"] == pytest.approx(1.0)
    assert result.directional_ray_speed["positive_y"] == pytest.approx(1.0)


def test_corner_pushforward_and_virtual_power_duality() -> None:
    j_g = np.diag([-2.0, 0.5])
    j_f = np.array([[-1.0, -1.0], [1.0, 0.0]])
    snapshot = _snapshot(j_f @ j_g, j_g=j_g, j_f=j_f)
    result = velocity_capability_from_snapshot(snapshot, rate_limits=[0.7, 1.3])
    force = np.array([0.3, -0.8])
    actuator_covector = j_g.T @ j_f.T @ force
    for rates, velocity in zip(
        result.actuator_corners, result.velocity_corners, strict=True
    ):
        np.testing.assert_allclose(velocity, j_f @ (j_g @ rates))
        assert force @ velocity == pytest.approx(actuator_covector @ rates)
        np.testing.assert_allclose(np.abs(rates) / result.rate_limits, [1.0, 1.0])


def test_rotating_task_coordinates_rotates_corner_set_and_preserves_ray_speed() -> None:
    jacobian = np.array([[2.0, 0.3], [-0.2, 0.5]])
    theta = 0.6
    rotation = np.array(
        [[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]]
    )
    direction = np.array([0.4, 0.7])
    base = velocity_capability_from_snapshot(
        _snapshot(jacobian), directions={"d": direction}
    )
    rotated = velocity_capability_from_snapshot(
        _snapshot(rotation @ jacobian, j_g=jacobian, j_f=rotation),
        directions={"d": rotation @ direction},
    )
    np.testing.assert_allclose(
        rotated.velocity_corners, np.asarray(base.velocity_corners) @ rotation.T
    )
    assert rotated.directional_ray_speed["d"] == pytest.approx(
        base.directional_ray_speed["d"]
    )
    assert rotated.directional_support["d"] == pytest.approx(
        base.directional_support["d"]
    )
    assert rotated.isotropic_speed == pytest.approx(base.isotropic_speed)


@pytest.mark.parametrize("rank", [0, 1])
def test_rank_loss_is_bounded_and_exact_inverse_refuses(rank: int) -> None:
    snapshot = _snapshot(np.diag([float(rank), 0.0]))
    result = velocity_capability_from_snapshot(snapshot)
    assert result.rank == rank
    assert result.isotropic_speed == 0.0
    assert result.directional_ray_speed["positive_x"] == float(rank)
    assert result.directional_ray_speed["positive_y"] == 0.0
    assert result.status.value.startswith("bounded_")
    assert result.ray_model == "explicit_inherited_rank_svd_truncation"
    with pytest.raises(DifferentialSingularityError) as info:
        differential_ik_from_snapshot(snapshot, [0.3, 0.4], policy="exact")
    assert info.value.rank == rank
    projected = differential_ik_from_snapshot(
        snapshot, [0.3, 0.4], policy="minimum_norm"
    )
    np.testing.assert_allclose(projected.requested_rates, [0.3 * rank, 0.0])
    np.testing.assert_allclose(projected.residual, [0.3 * (1 - rank), 0.4])
    assert projected.solver_status == "projected"
    damped = differential_ik_from_snapshot(
        snapshot, [0.3, 0.4], policy="damped_least_squares", damping=0.2
    )
    assert damped.physical_status == result.status
    assert damped.solver_rank_policy == "positive_damping_no_rank_truncation"
    json.dumps(damped.to_dict(), allow_nan=False)


def test_inherited_rank_truncation_is_explicit_and_raw_geometry_is_preserved() -> None:
    jacobian = np.diag([1.0, 1e-8])
    snapshot = _snapshot(jacobian, tolerance=1e-6)
    result = velocity_capability_from_snapshot(snapshot)
    assert result.rank == 1
    assert result.directional_support["positive_y"] == pytest.approx(1e-8)
    assert result.directional_ray_speed["positive_y"] == 0.0
    np.testing.assert_array_equal(
        np.abs(np.asarray(result.velocity_corners)[:, 1]), 1e-8
    )
    np.testing.assert_array_equal(np.asarray(result.ray_velocity_corners)[:, 1], 0.0)
    projected = differential_ik_from_snapshot(
        snapshot, [0.0, 1.0], policy="minimum_norm"
    )
    np.testing.assert_array_equal(projected.requested_rates, [0.0, 0.0])
    damped = differential_ik_from_snapshot(
        snapshot, [0.0, 1.0], policy="damped_least_squares", damping=1e-8
    )
    assert damped.requested_rates[1] == pytest.approx(5e7)
    assert damped.achieved_velocity[1] == pytest.approx(0.5)
    assert damped.rank_reports["u_to_x"] == snapshot.rank_u_to_x.to_dict()
    assert damped.physical_status == VelocityStateStatus.BOUNDED_RANK_DEFICIENT


def test_weighted_rank_one_minimum_norm_matches_constrained_analytic_solution() -> None:
    jacobian = np.array([[1.0, 1.0], [0.0, 0.0]])
    weight = np.array([[2.0, 0.4], [0.4, 1.0]])
    snapshot = _snapshot(jacobian, weight=weight)
    target = np.array([3.0, 4.0])
    result = differential_ik_from_snapshot(snapshot, target, policy="minimum_norm")
    row = np.array([1.0, 1.0])
    weighted_row = np.linalg.solve(weight, row)
    expected = weighted_row * target[0] / (row @ weighted_row)
    np.testing.assert_allclose(result.requested_rates, expected, atol=1e-14)
    np.testing.assert_allclose(result.achieved_velocity, [3.0, 0.0], atol=1e-14)
    np.testing.assert_allclose(result.residual, [0.0, 4.0], atol=1e-14)
    # W*u must be orthogonal to the feasible null direction.
    assert np.array([1.0, -1.0]) @ weight @ result.requested_rates == pytest.approx(
        0.0, abs=1e-14
    )
    np.testing.assert_allclose(result.actuator_weight, weight)
    assert result.provenance["actuator_weight_source"] == "snapshot"


def test_full_rank_weight_does_not_change_unique_exact_inverse() -> None:
    snapshot = _snapshot([[2.0, 0.3], [0.2, 0.5]])
    target = [0.4, -0.5]
    exact = differential_ik_from_snapshot(snapshot, target, policy="exact")
    weighted = differential_ik_from_snapshot(
        snapshot,
        target,
        policy="minimum_norm",
        actuator_weight=[[3.0, 0.4], [0.4, 0.8]],
    )
    np.testing.assert_allclose(weighted.requested_rates, exact.requested_rates)


@pytest.mark.parametrize("damping", [0.01, 0.7, 100.0])
def test_weighted_dls_satisfies_objective_stationarity(damping: float) -> None:
    jacobian = np.array([[2.0, 0.3], [-0.2, 0.5]])
    weight = np.array([[2.0, 0.4], [0.4, 1.0]])
    target = np.array([0.3, -0.4])
    snapshot = _snapshot(jacobian)
    result = differential_ik_from_snapshot(
        snapshot,
        target,
        policy="damped_least_squares",
        damping=damping,
        actuator_weight=weight,
    )
    rates = np.asarray(result.requested_rates)
    stationarity = (
        jacobian.T @ (jacobian @ rates - target) + damping**2 * weight @ rates
    )
    np.testing.assert_allclose(stationarity, [0.0, 0.0], atol=3e-15)
    expected = np.linalg.solve(
        jacobian.T @ jacobian + damping**2 * weight, jacobian.T @ target
    )
    np.testing.assert_allclose(rates, expected, atol=3e-15)
    assert result.solver_status == "regularized"
    assert result.physical_status == VelocityStateStatus.REGULAR
    assert result.provenance["actuator_weight_source"] == "caller"


def test_near_singular_exact_demand_and_dls_tradeoff_are_both_retained() -> None:
    snapshot = _snapshot(np.diag([1.0, 1e-8]))
    exact = differential_ik_from_snapshot(snapshot, [0.0, 1.0], policy="exact")
    damped = differential_ik_from_snapshot(
        snapshot, [0.0, 1.0], policy="damped_least_squares", damping=1e-4
    )
    assert exact.physical_status == VelocityStateStatus.NEAR_SINGULAR
    assert exact.requested_rates[1] == 1e8
    assert not exact.requested_feasible
    assert damped.requested_rates[1] == pytest.approx(1e-8 / (1e-16 + 1e-8))
    assert damped.residual_norm > 0.999
    assert damped.rank_reports == exact.rank_reports


def test_near_singular_ray_speed_agrees_with_actual_target_rate_demand() -> None:
    # Representative retained full-rank, nearly dependent map. Multiplying
    # an explicit inverse by this tangential target loses several ppm through
    # cancellation even though a direct target solve remains consistent.
    snapshot = _snapshot(
        [
            [1.4694415274668244, 0.7570488823445098],
            [0.5024236984414052, 0.2588461617894391],
        ]
    )
    capability = velocity_capability_from_snapshot(
        snapshot, directions={"tangent": [0.9462191868318749, 0.3235262747772199]}
    )
    retained_direction = capability.directions["tangent"]
    assert retained_direction is not None
    command = differential_ik_from_snapshot(
        snapshot, retained_direction, policy="exact"
    )
    assert capability.status == VelocityStateStatus.NEAR_SINGULAR
    assert capability.directional_ray_speed["tangent"] == pytest.approx(
        1.0 / command.requested_peak_utilization, rel=2e-15
    )


def test_uniform_scaling_is_explicit_and_preserves_achieved_direction() -> None:
    snapshot = _snapshot(np.diag([2.0, 0.5]))
    report = differential_ik_from_snapshot(snapshot, [6.0, 1.0], policy="exact")
    scaled = differential_ik_from_snapshot(
        snapshot, [6.0, 1.0], policy="exact", rate_policy="uniform_scale"
    )
    np.testing.assert_array_equal(report.requested_rates, [3.0, 2.0])
    np.testing.assert_array_equal(report.commanded_rates, report.requested_rates)
    assert report.command_status == "outside_rate_box"
    assert report.requested_exceeding_channels == (0, 1)
    assert report.requested_saturated_channels == ()
    assert scaled.applied_scale == pytest.approx(1.0 / 3.0)
    np.testing.assert_allclose(scaled.commanded_rates, [1.0, 2.0 / 3.0])
    np.testing.assert_allclose(
        scaled.achieved_velocity, np.asarray(report.achieved_velocity) / 3.0
    )
    assert not scaled.requested_feasible and scaled.commanded_feasible
    assert scaled.commanded_saturated_channels == (0,)
    assert scaled.commanded_exceeding_channels == ()
    assert scaled.command_status == "uniformly_scaled_to_rate_box"
    assert scaled.residual_norm > 0.0


@pytest.mark.parametrize("policy", list(DifferentialIKPolicy))
def test_zero_target_gives_zero_rates(policy: DifferentialIKPolicy) -> None:
    result = differential_ik_from_snapshot(
        _snapshot(np.diag([2.0, 0.5])),
        [0.0, 0.0],
        policy=policy,
        damping=0.1 if policy == DifferentialIKPolicy.DAMPED_LEAST_SQUARES else None,
        rate_policy="uniform_scale",
    )
    np.testing.assert_array_equal(result.requested_rates, [0.0, 0.0])
    assert result.applied_scale == 1.0
    assert result.residual_norm == 0.0
    assert result.commanded_saturated_channels == ()


def test_undefined_radial_direction_serializes_as_null() -> None:
    result = velocity_capability_from_snapshot(_snapshot(np.eye(2), x=(0.0, 0.0)))
    assert result.directional_support["radial"] is None
    assert result.directional_ray_speed["radial"] is None
    assert result.direction_status["radial"] == "undefined_direction"
    assert result.directional_ray_speed["tangential"] is None
    json.dumps(result.to_dict(), allow_nan=False)


def test_serialization_and_result_source_records_are_deep_copies() -> None:
    snapshot = _snapshot(np.eye(2))
    capability = velocity_capability_from_snapshot(snapshot)
    command = differential_ik_from_snapshot(snapshot, [0.1, 0.2], policy="exact")
    record = capability.to_dict()
    record["rank_reports"]["u_to_x"]["singular_values"][0] = 777.0
    record["provenance"]["source_snapshot"]["nested"]["revision"] = "modified"
    assert capability.rank_reports["u_to_x"]["singular_values"][0] == 1.0
    assert snapshot.provenance["nested"]["revision"] == "source-v1"
    snapshot.provenance["nested"]["revision"] = "later-source-edit"
    assert capability.provenance["source_snapshot"]["nested"]["revision"] == "source-v1"
    assert command.provenance["source_snapshot"]["nested"]["revision"] == "source-v1"
    for result in (capability, command):
        serialized = result.to_dict()
        assert json.loads(json.dumps(serialized, allow_nan=False)) == serialized


def test_restored_snapshot_uses_inherited_reports_without_default_rank_cutoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = KinematicGeometrySnapshot.from_dict(
        _snapshot(np.diag([1.0, 1e-8]), tolerance=1e-6).to_dict()
    )

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("implicit rank recomputation or inversion")

    # Weight validation has its own legitimate SPD rank check, so forbid
    # replacement rank selection on Jacobians and implicit pinv/lstsq only.
    monkeypatch.setattr(np.linalg, "pinv", forbidden)
    monkeypatch.setattr(np.linalg, "lstsq", forbidden)
    monkeypatch.setattr(np.linalg, "matrix_rank", forbidden)
    capability = velocity_capability_from_snapshot(snapshot)
    result = differential_ik_from_snapshot(snapshot, [0.3, 0.4], policy="minimum_norm")
    assert capability.rank == 1
    assert result.rank_reports["u_to_x"]["tolerance"] == 1e-6
    assert result.rank_reports["u_to_x"]["rank"] == 1


@pytest.mark.parametrize(
    "bad_target", [[1.0], [[1.0, 2.0]], [np.nan, 0.0], [0.0, np.inf]]
)
def test_reject_invalid_target_velocity(bad_target: Any) -> None:
    with pytest.raises(DifferentialShapeError):
        differential_ik_from_snapshot(_snapshot(np.eye(2)), bad_target, policy="exact")


@pytest.mark.parametrize("bad_limits", [[0.0, 1.0], [-1.0, 1.0], [1.0], [1.0, np.inf]])
def test_reject_invalid_rate_box(bad_limits: Any) -> None:
    with pytest.raises(DifferentialShapeError):
        velocity_capability_from_snapshot(_snapshot(np.eye(2)), rate_limits=bad_limits)


@pytest.mark.parametrize("damping", [None, 0.0, -1.0, np.nan, np.inf])
def test_reject_nonpositive_or_nonfinite_dls_damping(damping: Any) -> None:
    with pytest.raises(DifferentialShapeError):
        differential_ik_from_snapshot(
            _snapshot(np.eye(2)),
            [0.0, 0.0],
            policy="damped_least_squares",
            damping=damping,
        )


@pytest.mark.parametrize(
    "weight",
    [[[1.0, 2.0], [0.0, 1.0]], [[1.0, 0.0], [0.0, -1.0]], [[1.0, 0.0], [0.0, 0.0]]],
)
def test_reject_invalid_actuator_weights(weight: Any) -> None:
    with pytest.raises((DifferentialShapeError, DifferentialSingularityError)):
        differential_ik_from_snapshot(
            _snapshot(np.eye(2)),
            [0.1, 0.2],
            policy="minimum_norm",
            actuator_weight=weight,
        )


def test_reject_unrequested_policy_and_inconsistent_source() -> None:
    snapshot = _snapshot(np.eye(2))
    with pytest.raises(DifferentialShapeError, match="only defined"):
        differential_ik_from_snapshot(snapshot, [1.0, 0.0], policy="exact", damping=0.1)
    with pytest.raises(ValueError):
        differential_ik_from_snapshot(snapshot, [1.0, 0.0], policy="automatic")
    with pytest.raises(ValueError):
        differential_ik_from_snapshot(
            snapshot, [1.0, 0.0], policy="exact", rate_policy="clip"
        )
    corrupted = replace(snapshot, j_u_to_x=((2.0, 0.0), (0.0, 1.0)))
    with pytest.raises(DifferentialShapeError, match="disagrees"):
        velocity_capability_from_snapshot(corrupted)
    with pytest.raises(DifferentialShapeError):
        velocity_capability_from_snapshot(snapshot, directions={"bad": [np.nan, 0.0]})


def test_nonfinite_source_metadata_is_rejected_instead_of_serialized() -> None:
    snapshot = replace(_snapshot(np.eye(2)), provenance={"bad": np.inf})
    with pytest.raises(VelocityNumericalError):
        velocity_capability_from_snapshot(snapshot)


@pytest.mark.parametrize("condition", [None, 1.0, -1.0, np.nan, np.inf])
def test_condition_metadata_cannot_relabel_near_singular_source(condition: Any) -> None:
    snapshot = _snapshot(np.diag([1.0, 1e-8]))
    corrupted = replace(
        snapshot,
        rank_u_to_x=replace(snapshot.rank_u_to_x, condition_number=condition),
    )
    with pytest.raises(DifferentialShapeError, match="condition number"):
        velocity_capability_from_snapshot(corrupted)
    with pytest.raises(DifferentialShapeError, match="condition number"):
        differential_ik_from_snapshot(corrupted, [0.0, 1.0], policy="exact")


def test_rank_deficient_condition_metadata_must_stay_unavailable() -> None:
    snapshot = _snapshot(np.diag([1.0, 1e-8]), tolerance=1e-6)
    corrupted = replace(
        snapshot,
        rank_u_to_x=replace(snapshot.rank_u_to_x, condition_number=1e8),
    )
    with pytest.raises(DifferentialShapeError, match="unavailable at inherited rank"):
        velocity_capability_from_snapshot(corrupted)
