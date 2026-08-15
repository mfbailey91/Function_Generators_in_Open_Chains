"""V4-003 metric and mobility algebra tests."""

from __future__ import annotations

import numpy as np
import pytest
from tests.graphs_v2._fixtures import fourbar_2d_branch

from inequality_mechanisms.transmission_geometry.errors import (
    DifferentialShapeError,
    DifferentialSingularityError,
)
from inequality_mechanisms.transmission_geometry.metrics import (
    actuator_metric_on_q,
    mobility_on_q,
    mobility_on_x,
    pullback_metric,
    validate_positive_definite,
)


def test_identity_gearbox_metric_equals_actuator_weight() -> None:
    j_g = np.eye(2, dtype=np.float64)
    weight = np.diag([2.0, 0.5])
    metric = actuator_metric_on_q(j_g, weight)
    np.testing.assert_allclose(metric, weight)
    mobility = mobility_on_q(j_g, weight)
    expected_mobility = np.diag([0.5, 2.0])
    np.testing.assert_allclose(mobility, expected_mobility)


def test_diagonal_gearbox_inverse_ratio_squares() -> None:
    ratios = np.array([2.0, 0.5], dtype=np.float64)
    j_g = np.diag(ratios)
    metric = actuator_metric_on_q(j_g)
    mobility = mobility_on_q(j_g)
    np.testing.assert_allclose(metric, np.diag(1.0 / ratios**2))
    np.testing.assert_allclose(mobility, np.diag(ratios**2))


def test_fourbar_metric_matches_audit_inverse_formula() -> None:
    branch = fourbar_2d_branch()
    u = 0.5 * (
        np.asarray(branch.certificate.input_lower, dtype=np.float64)
        + np.asarray(branch.certificate.input_upper, dtype=np.float64)
    )
    j_g = np.asarray(branch.jacobian(u), dtype=np.float64)
    metric = actuator_metric_on_q(j_g)
    j_inv = np.linalg.inv(j_g)
    expected = j_inv.T @ j_inv
    expected = 0.5 * (expected + expected.T)
    np.testing.assert_allclose(metric, expected, atol=1e-12, rtol=1e-12)


def test_metric_and_mobility_are_symmetric_and_inverse() -> None:
    rng = np.random.default_rng(1)
    j_g = rng.normal(size=(2, 2))
    j_g[0, 0] += 2.0
    weight = np.diag([1.5, 0.8])
    metric = actuator_metric_on_q(j_g, weight)
    mobility = mobility_on_q(j_g, weight)
    np.testing.assert_allclose(metric, metric.T)
    np.testing.assert_allclose(mobility, mobility.T)
    identity = np.eye(2, dtype=np.float64)
    np.testing.assert_allclose(metric @ mobility, identity, atol=1e-10, rtol=1e-10)
    np.testing.assert_allclose(mobility @ metric, identity, atol=1e-10, rtol=1e-10)


def test_singular_inverse_metric_raises_without_pinv() -> None:
    j_g = np.asarray([[1.0, 0.0], [0.0, 0.0]], dtype=np.float64)
    with pytest.raises(DifferentialSingularityError) as info:
        actuator_metric_on_q(j_g)
    assert info.value.operation == "actuator_metric_on_q"
    assert info.value.rank == 1
    assert info.value.required_rank == 2
    mobility = mobility_on_q(j_g)
    np.testing.assert_allclose(mobility, np.asarray([[1.0, 0.0], [0.0, 0.0]]))
    evals = np.linalg.eigvalsh(mobility)
    assert float(evals[0]) == pytest.approx(0.0, abs=1e-12)
    assert float(evals[1]) == pytest.approx(1.0, abs=1e-12)


def test_nonsquare_jacobian_raises_for_inverse_metric() -> None:
    j_g = np.ones((2, 3), dtype=np.float64)
    with pytest.raises(DifferentialSingularityError) as info:
        actuator_metric_on_q(j_g)
    assert info.value.operation == "actuator_metric_on_q"
    assert info.value.shape == (2, 3)


def test_validate_positive_definite_rejects_indefinite_and_nonsquare() -> None:
    report = validate_positive_definite(np.diag([2.0, 0.5]))
    assert report.full_rank is True
    with pytest.raises(DifferentialSingularityError) as info:
        validate_positive_definite(np.diag([1.0, -1.0]))
    assert info.value.operation == "validate_positive_definite"
    with pytest.raises(DifferentialShapeError, match="square"):
        validate_positive_definite(np.ones((2, 3)))
    with pytest.raises(DifferentialShapeError, match="symmetric"):
        validate_positive_definite(np.asarray([[1.0, 2.0], [0.0, 1.0]]))


def test_pullback_metric_identity_and_rank_deficient() -> None:
    j_arr = np.asarray([[1.0, 0.0], [0.0, 0.0]], dtype=np.float64)
    pulled = pullback_metric(j_arr)
    np.testing.assert_allclose(pulled, np.asarray([[1.0, 0.0], [0.0, 0.0]]))
    target = np.diag([4.0, 1.0])
    pulled_weighted = pullback_metric(np.eye(2), target)
    np.testing.assert_allclose(pulled_weighted, target)


def test_mobility_on_x_matches_formula() -> None:
    j_xu = np.asarray([[1.0, 2.0], [0.0, 1.0]], dtype=np.float64)
    weight = np.diag([4.0, 1.0])
    mobility = mobility_on_x(j_xu, weight)
    expected = j_xu @ np.linalg.inv(weight) @ j_xu.T
    expected = 0.5 * (expected + expected.T)
    np.testing.assert_allclose(mobility, expected)
