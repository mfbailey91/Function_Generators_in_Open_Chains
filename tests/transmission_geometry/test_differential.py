"""V4-002 robot-independent differential algebra tests."""

from __future__ import annotations

import numpy as np
import pytest

from inequality_mechanisms.kinematics import Planar2R
from inequality_mechanisms.transmission_geometry import (
    DEFAULT_RANK_TOLERANCE_FACTOR,
    DifferentialShapeError,
    DifferentialSingularityError,
    RankReport,
    composite_jacobian,
    default_rank_tolerance,
    pullback_covector,
    pushforward_vector,
    rank_report,
)


def test_rectangular_hand_worked_product() -> None:
    j_f = np.asarray([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]], dtype=np.float64)
    j_g = np.asarray(
        [[1.0, 0.0, 1.0, 0.0], [0.0, 1.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    expected = np.asarray(
        [[1.0, 2.0, 1.0, 2.0], [3.0, 4.0, 3.0, 4.0], [5.0, 6.0, 5.0, 6.0]],
        dtype=np.float64,
    )
    out = composite_jacobian(j_f, j_g)
    assert out.shape == (3, 4)
    assert out.dtype == np.float64
    np.testing.assert_allclose(out, expected)
    assert out is not j_f
    assert out is not j_g


def test_inner_dimension_mismatch_raises() -> None:
    j_f = np.eye(2, dtype=np.float64)
    j_g = np.ones((3, 2), dtype=np.float64)
    with pytest.raises(DifferentialShapeError, match="inner dimensions") as info:
        composite_jacobian(j_f, j_g)
    assert info.value.failure_code == "differential_shape_error"


def test_non_matrix_and_non_vector_shapes_raise() -> None:
    with pytest.raises(DifferentialShapeError, match="rank-2"):
        composite_jacobian(np.arange(4, dtype=np.float64), np.eye(2))
    with pytest.raises(DifferentialShapeError, match="rank-1"):
        pushforward_vector(np.eye(2), np.eye(2))
    with pytest.raises(DifferentialShapeError, match="rank-1"):
        pullback_covector(np.eye(2), np.ones((2, 1)))


def test_vector_length_mismatch_raises() -> None:
    j_arr = np.ones((3, 2), dtype=np.float64)
    with pytest.raises(DifferentialShapeError, match="vector length"):
        pushforward_vector(j_arr, np.ones(3, dtype=np.float64))
    with pytest.raises(DifferentialShapeError, match="covector length"):
        pullback_covector(j_arr, np.ones(2, dtype=np.float64))


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_nonfinite_matrix_and_vector_raise(bad: float) -> None:
    finite = np.eye(2, dtype=np.float64)
    dirty = np.array([[1.0, bad], [0.0, 1.0]], dtype=np.float64)
    with pytest.raises(DifferentialShapeError) as info:
        composite_jacobian(dirty, finite)
    assert info.value.failure_code == "nonfinite_differential"
    with pytest.raises(DifferentialShapeError) as info:
        pushforward_vector(finite, np.array([1.0, bad], dtype=np.float64))
    assert info.value.failure_code == "nonfinite_differential"
    with pytest.raises(DifferentialShapeError) as info:
        pullback_covector(finite, np.array([bad, 0.0], dtype=np.float64))
    assert info.value.failure_code == "nonfinite_differential"


def test_composition_associativity() -> None:
    rng = np.random.default_rng(0)
    a = rng.normal(size=(2, 3))
    b = rng.normal(size=(3, 4))
    c = rng.normal(size=(4, 5))
    left = composite_jacobian(a, composite_jacobian(b, c))
    right = composite_jacobian(composite_jacobian(a, b), c)
    np.testing.assert_allclose(left, right)


def test_planar2r_analytic_composite_identity_and_diagonal() -> None:
    arm = Planar2R(L1=1.0, L2=1.0)
    q = np.asarray([0.4, 0.7], dtype=np.float64)
    j_f = np.asarray(arm.jacobian(q), dtype=np.float64)
    j_identity = np.eye(2, dtype=np.float64)
    j_diag = np.diag([2.0, 0.5])
    np.testing.assert_allclose(composite_jacobian(j_f, j_identity), j_f @ j_identity)
    np.testing.assert_allclose(composite_jacobian(j_f, j_diag), j_f @ j_diag)


def test_pushforward_and_pullback_hand_worked() -> None:
    jacobian = np.asarray([[1.0, 2.0], [3.0, 4.0]], dtype=np.float64)
    vector = np.asarray([1.0, -1.0], dtype=np.float64)
    covector = np.asarray([1.0, 0.0], dtype=np.float64)
    np.testing.assert_allclose(pushforward_vector(jacobian, vector), [-1.0, -1.0])
    np.testing.assert_allclose(pullback_covector(jacobian, covector), [1.0, 2.0])


def test_rank_report_identity_is_full_rank() -> None:
    report = rank_report(np.eye(2, dtype=np.float64))
    assert isinstance(report, RankReport)
    assert report.shape == (2, 2)
    assert report.rank == 2
    assert report.required_full_rank == 2
    assert report.full_rank is True
    assert report.condition_number == pytest.approx(1.0)
    expected_tol = default_rank_tolerance(
        (2, 2),
        report.singular_values,
        factor=DEFAULT_RANK_TOLERANCE_FACTOR,
    )
    assert report.tolerance == pytest.approx(expected_tol)


def test_rank_report_rank_one_matrix() -> None:
    matrix = np.asarray([[1.0, 2.0], [2.0, 4.0]], dtype=np.float64)
    report = rank_report(matrix)
    assert report.rank == 1
    assert report.required_full_rank == 2
    assert report.full_rank is False
    assert report.singular_values[1] <= report.tolerance or report.singular_values[
        1
    ] == pytest.approx(0.0, abs=1e-12)
    assert report.condition_number is None


def test_rank_tolerance_policy_is_explicit() -> None:
    sigmas = (4.0, 1.0)
    tol = default_rank_tolerance((3, 2), sigmas, factor=2.0)
    assert tol == pytest.approx(2.0 * np.finfo(np.float64).eps * 3 * 4.0)
    with pytest.raises(DifferentialShapeError, match="factor"):
        default_rank_tolerance((2, 2), (1.0,), factor=0.0)


def test_outputs_are_new_float64_arrays() -> None:
    j_f = np.eye(2, dtype=np.float32)
    j_g = np.diag([3.0, 4.0]).astype(np.float32)
    out = composite_jacobian(j_f, j_g)
    assert out.dtype == np.float64
    j_f[0, 0] = 99.0
    assert out[0, 0] == pytest.approx(3.0)


def test_singularity_error_carries_rank_fields() -> None:
    err = DifferentialSingularityError(
        "inverse metric unavailable",
        operation="actuator_metric_on_q",
        shape=(2, 2),
        rank=1,
        required_rank=2,
        singular_values=(1.0, 0.0),
        tolerance=1e-15,
    )
    assert err.operation == "actuator_metric_on_q"
    assert err.shape == (2, 2)
    assert err.rank == 1
    assert err.required_rank == 2
    assert err.singular_values == (1.0, 0.0)
    assert err.tolerance == 1e-15
    assert err.failure_code == "transmission_rank_deficient"
