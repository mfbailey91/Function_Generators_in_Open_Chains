"""Metric and mobility algebra for kinematic transmission geometry.

These operations are independent of ``PhysicalState`` and robot classes.
Inverse-defined actuator metrics raise rather than using a pseudoinverse.
Mobility remains defined when a Jacobian loses rank.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

from inequality_mechanisms.transmission_geometry.differential import (
    RankReport,
    _as_finite_matrix,
    rank_report,
)
from inequality_mechanisms.transmission_geometry.errors import (
    DifferentialShapeError,
    DifferentialSingularityError,
)


def _symmetry_tolerance(matrix: NDArray[np.float64]) -> float:
    scale = max(float(np.linalg.norm(matrix, ord="fro")), 1.0)
    return float(np.finfo(np.float64).eps * max(matrix.shape) * scale)


def _symmetrize(matrix: NDArray[np.float64]) -> NDArray[np.float64]:
    return 0.5 * (matrix + matrix.T)


def _raise_singularity(
    *,
    message: str,
    operation: str,
    report: RankReport,
    required_rank: int | None = None,
) -> None:
    raise DifferentialSingularityError(
        message,
        operation=operation,
        shape=report.shape,
        rank=report.rank,
        required_rank=int(
            report.required_full_rank if required_rank is None else required_rank
        ),
        singular_values=report.singular_values,
        tolerance=report.tolerance,
    )


def validate_positive_definite(
    weight: ArrayLike,
    *,
    tolerance: float | None = None,
) -> RankReport:
    """Return a rank report for a symmetric positive-definite weight.

    Parameters
    ----------
    weight :
        Candidate metric matrix.
    tolerance :
        Optional absolute cutoff used by :func:`rank_report` and the
        eigenvalue positivity check. When omitted, use the default
        scale-aware rank policy.

    Returns
    -------
    RankReport
        Rank report of the accepted weight.

    Raises
    ------
    DifferentialShapeError
        If ``weight`` is not a finite square symmetric matrix.
    DifferentialSingularityError
        If ``weight`` is not positive definite at the declared tolerance.
    """
    matrix = _as_finite_matrix(weight, name="weight")
    if matrix.shape[0] != matrix.shape[1]:
        raise DifferentialShapeError(
            f"weight must be square, got shape {matrix.shape}"
        )
    if not np.allclose(
        matrix,
        matrix.T,
        rtol=0.0,
        atol=_symmetry_tolerance(matrix),
    ):
        raise DifferentialShapeError("weight must be symmetric")
    report = rank_report(matrix, tolerance=tolerance)
    evals = np.linalg.eigvalsh(_symmetrize(matrix))
    if (not report.full_rank) or float(evals[0]) <= report.tolerance:
        _raise_singularity(
            message="weight must be positive definite",
            operation="validate_positive_definite",
            report=report,
            required_rank=int(matrix.shape[0]),
        )
    return report


def _resolved_actuator_weight(
    input_dim: int,
    actuator_weight: ArrayLike | None,
    *,
    rank_tolerance: float | None = None,
) -> NDArray[np.float64]:
    if actuator_weight is None:
        weight = np.eye(input_dim, dtype=np.float64)
    else:
        weight = _as_finite_matrix(actuator_weight, name="actuator_weight")
        if weight.shape != (input_dim, input_dim):
            raise DifferentialShapeError(
                "actuator_weight must have shape "
                f"({input_dim}, {input_dim}), got {weight.shape}"
            )
    validate_positive_definite(weight, tolerance=rank_tolerance)
    return weight


def pullback_metric(
    jacobian: ArrayLike,
    target_metric: ArrayLike | None = None,
) -> NDArray[np.float64]:
    """Return the pullback metric ``J.T @ M @ J``.

    Parameters
    ----------
    jacobian :
        Finite map differential, shape ``(m, n)``.
    target_metric :
        Metric on the target space, shape ``(m, m)``. When omitted, use
        the identity of dimension ``m``.

    Returns
    -------
    ndarray
        New symmetric ``float64`` matrix, shape ``(n, n)``.
    """
    j_arr = _as_finite_matrix(jacobian, name="jacobian")
    if target_metric is None:
        metric = np.eye(j_arr.shape[0], dtype=np.float64)
    else:
        metric = _as_finite_matrix(target_metric, name="target_metric")
        expected = (j_arr.shape[0], j_arr.shape[0])
        if metric.shape != expected:
            raise DifferentialShapeError(
                "target_metric must have shape "
                f"{expected}, got {metric.shape}"
            )
    pulled = j_arr.T @ metric @ j_arr
    return _symmetrize(pulled)


def actuator_metric_on_q(
    j_u_to_q: ArrayLike,
    actuator_weight: ArrayLike | None = None,
    *,
    rank_tolerance: float | None = None,
) -> NDArray[np.float64]:
    """Return the actuator-travel metric expressed on Q.

    For square full-rank ``J_g``,

    .. math::

        M_Q^{(U)} = J_g^{-T} W_u J_g^{-1}.

    Parameters
    ----------
    j_u_to_q :
        Transmission Jacobian ``J_g``, shape ``(n_q, n_u)``.
    actuator_weight :
        Positive-definite actuator metric ``W_u``. Defaults to identity.
    rank_tolerance :
        Optional absolute rank cutoff for ``J_g`` and ``W_u``.

    Returns
    -------
    ndarray
        New symmetric ``float64`` matrix, shape ``(n_q, n_q)``.

    Raises
    ------
    DifferentialSingularityError
        If ``J_g`` is nonsquare or rank-deficient.
    """
    j_g = _as_finite_matrix(j_u_to_q, name="j_u_to_q")
    report = rank_report(j_g, tolerance=rank_tolerance)
    n_q, n_u = j_g.shape
    if n_q != n_u or not report.full_rank:
        _raise_singularity(
            message="actuator_metric_on_q requires square full-rank J_g",
            operation="actuator_metric_on_q",
            report=report,
            required_rank=n_u if n_q == n_u else max(n_q, n_u),
        )
    weight = _resolved_actuator_weight(
        n_u,
        actuator_weight,
        rank_tolerance=rank_tolerance,
    )
    identity = np.eye(n_u, dtype=np.float64)
    j_inv = np.linalg.solve(j_g, identity)
    metric = j_inv.T @ weight @ j_inv
    return _symmetrize(metric)


def _mobility(
    jacobian: ArrayLike,
    actuator_weight: ArrayLike | None,
    *,
    jacobian_name: str,
) -> NDArray[np.float64]:
    j_arr = _as_finite_matrix(jacobian, name=jacobian_name)
    weight = _resolved_actuator_weight(j_arr.shape[1], actuator_weight)
    w_inv_jt = np.linalg.solve(weight, j_arr.T)
    mobility = j_arr @ w_inv_jt
    return _symmetrize(mobility)


def mobility_on_q(
    j_u_to_q: ArrayLike,
    actuator_weight: ArrayLike | None = None,
) -> NDArray[np.float64]:
    """Return actuator mobility on Q, ``B_Q = J_g W_u^{-1} J_g.T``.

    The result may be positive semidefinite when ``J_g`` loses rank.

    Parameters
    ----------
    j_u_to_q :
        Transmission Jacobian ``J_g``.
    actuator_weight :
        Positive-definite actuator metric ``W_u``. Defaults to identity.

    Returns
    -------
    ndarray
        New symmetric ``float64`` matrix, shape ``(n_q, n_q)``.
    """
    return _mobility(j_u_to_q, actuator_weight, jacobian_name="j_u_to_q")


def mobility_on_x(
    j_u_to_x: ArrayLike,
    actuator_weight: ArrayLike | None = None,
) -> NDArray[np.float64]:
    """Return actuator mobility on X, ``B_X = J_xu W_u^{-1} J_xu.T``.

    The result may be positive semidefinite when ``J_xu`` loses rank.

    Parameters
    ----------
    j_u_to_x :
        Composite Jacobian ``J_xu``.
    actuator_weight :
        Positive-definite actuator metric ``W_u``. Defaults to identity.

    Returns
    -------
    ndarray
        New symmetric ``float64`` matrix, shape ``(n_x, n_x)``.
    """
    return _mobility(j_u_to_x, actuator_weight, jacobian_name="j_u_to_x")


__all__ = [
    "actuator_metric_on_q",
    "mobility_on_q",
    "mobility_on_x",
    "pullback_metric",
    "validate_positive_definite",
]
