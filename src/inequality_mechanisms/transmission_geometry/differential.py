"""Pure differential algebra for kinematic transmission geometry.

These operations are independent of ``PhysicalState`` and robot classes.
Rank-deficient inputs are reported, not inverted or silently regularized.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from inequality_mechanisms.transmission_geometry.errors import DifferentialShapeError

DEFAULT_RANK_TOLERANCE_FACTOR = 1.0


@dataclass(frozen=True, slots=True)
class RankReport:
    """Numerical rank, singular values, and full-rank status of a matrix."""

    shape: tuple[int, int]
    rank: int
    required_full_rank: int
    singular_values: tuple[float, ...]
    tolerance: float
    full_rank: bool
    condition_number: float | None


def default_rank_tolerance(
    shape: tuple[int, int],
    singular_values: ArrayLike,
    *,
    factor: float = DEFAULT_RANK_TOLERANCE_FACTOR,
) -> float:
    """Return the scale-aware SVD rank cutoff.

    The default policy is

    .. math::

        \\epsilon_{\\mathrm{rank}}
        =
        \\textit{factor}\\cdot\\varepsilon_{\\mathrm{machine}}
        \\max(m,n)\\sigma_{\\max}

    Parameters
    ----------
    shape :
        Matrix shape ``(m, n)``.
    singular_values :
        Singular values in nonincreasing order.
    factor :
        Serialized policy factor. Default is ``1.0``.

    Returns
    -------
    float
        Nonnegative rank tolerance.
    """
    if factor <= 0.0 or not np.isfinite(factor):
        raise DifferentialShapeError(
            f"rank-tolerance factor must be finite and positive, got {factor}"
        )
    m, n = shape
    sigmas = np.asarray(singular_values, dtype=np.float64)
    sigma_max = float(sigmas[0]) if sigmas.size else 0.0
    return float(factor * np.finfo(np.float64).eps * max(m, n) * sigma_max)


def _as_finite_matrix(value: ArrayLike, *, name: str) -> NDArray[np.float64]:
    arr = np.asarray(value, dtype=np.float64)
    if arr.ndim != 2:
        raise DifferentialShapeError(
            f"{name} must be a rank-2 matrix, got shape {arr.shape}"
        )
    if arr.shape[0] == 0 or arr.shape[1] == 0:
        raise DifferentialShapeError(
            f"{name} must have positive dimensions, got shape {arr.shape}"
        )
    if not np.all(np.isfinite(arr)):
        raise DifferentialShapeError(
            f"{name} must contain only finite values",
            failure_code="nonfinite_differential",
        )
    return np.array(arr, dtype=np.float64, copy=True)


def _as_finite_vector(value: ArrayLike, *, name: str) -> NDArray[np.float64]:
    arr = np.asarray(value, dtype=np.float64)
    if arr.ndim != 1:
        raise DifferentialShapeError(
            f"{name} must be a rank-1 vector, got shape {arr.shape}"
        )
    if arr.shape[0] == 0:
        raise DifferentialShapeError(
            f"{name} must have positive length, got shape {arr.shape}"
        )
    if not np.all(np.isfinite(arr)):
        raise DifferentialShapeError(
            f"{name} must contain only finite values",
            failure_code="nonfinite_differential",
        )
    return np.array(arr, dtype=np.float64, copy=True)


def rank_report(
    matrix: ArrayLike,
    *,
    tolerance: float | None = None,
    tolerance_factor: float = DEFAULT_RANK_TOLERANCE_FACTOR,
) -> RankReport:
    """Return an explicit SVD rank report for ``matrix``.

    Parameters
    ----------
    matrix :
        Finite rank-2 array.
    tolerance :
        Optional absolute cutoff. When omitted, use
        :func:`default_rank_tolerance`.
    tolerance_factor :
        Policy factor for the default cutoff.

    Returns
    -------
    RankReport
        Rank, singular values, and full-rank status. Rank deficiency is
        reported rather than treated as an error.
    """
    arr = _as_finite_matrix(matrix, name="matrix")
    singular_values = np.linalg.svd(arr, compute_uv=False)
    sigmas = tuple(float(s) for s in singular_values)
    if tolerance is None:
        used_tolerance = default_rank_tolerance(
            (int(arr.shape[0]), int(arr.shape[1])),
            singular_values,
            factor=tolerance_factor,
        )
    else:
        if not np.isfinite(tolerance) or tolerance < 0.0:
            raise DifferentialShapeError(
                f"rank tolerance must be finite and nonnegative, got {tolerance}"
            )
        used_tolerance = float(tolerance)
    rank = int(np.count_nonzero(singular_values > used_tolerance))
    required = int(min(arr.shape[0], arr.shape[1]))
    sigma_min = float(singular_values[-1]) if singular_values.size else 0.0
    if singular_values.size == 0 or sigma_min <= used_tolerance:
        condition: float | None = None
    else:
        condition = float(singular_values[0] / sigma_min)
    return RankReport(
        shape=(int(arr.shape[0]), int(arr.shape[1])),
        rank=rank,
        required_full_rank=required,
        singular_values=sigmas,
        tolerance=used_tolerance,
        full_rank=rank == required,
        condition_number=condition,
    )


def composite_jacobian(
    j_q_to_x: ArrayLike,
    j_u_to_q: ArrayLike,
) -> NDArray[np.float64]:
    """Return ``J_{xu} = J_q_to_x @ J_u_to_q``.

    Parameters
    ----------
    j_q_to_x :
        Forward-kinematics Jacobian, shape ``(n_x, n_q)``.
    j_u_to_q :
        Transmission Jacobian, shape ``(n_q, n_u)``.

    Returns
    -------
    ndarray
        New ``float64`` composite Jacobian, shape ``(n_x, n_u)``.
    """
    j_f = _as_finite_matrix(j_q_to_x, name="j_q_to_x")
    j_g = _as_finite_matrix(j_u_to_q, name="j_u_to_q")
    if j_f.shape[1] != j_g.shape[0]:
        raise DifferentialShapeError(
            "inner dimensions must agree for J_q_to_x @ J_u_to_q, "
            f"got {j_f.shape} and {j_g.shape}"
        )
    return j_f @ j_g


def pushforward_vector(
    jacobian: ArrayLike,
    vector: ArrayLike,
) -> NDArray[np.float64]:
    """Return the tangent pushforward ``J @ v``.

    Parameters
    ----------
    jacobian :
        Finite matrix, shape ``(m, n)``.
    vector :
        Finite vector, shape ``(n,)``.

    Returns
    -------
    ndarray
        New ``float64`` vector, shape ``(m,)``.
    """
    j_arr = _as_finite_matrix(jacobian, name="jacobian")
    v_arr = _as_finite_vector(vector, name="vector")
    if j_arr.shape[1] != v_arr.shape[0]:
        raise DifferentialShapeError(
            "vector length must match jacobian columns, "
            f"got jacobian {j_arr.shape} and vector {v_arr.shape}"
        )
    return j_arr @ v_arr


def pullback_covector(
    jacobian: ArrayLike,
    covector: ArrayLike,
) -> NDArray[np.float64]:
    """Return the covector pullback ``J.T @ covector``.

    Parameters
    ----------
    jacobian :
        Finite matrix, shape ``(m, n)``.
    covector :
        Finite covector, shape ``(m,)``.

    Returns
    -------
    ndarray
        New ``float64`` covector, shape ``(n,)``.
    """
    j_arr = _as_finite_matrix(jacobian, name="jacobian")
    c_arr = _as_finite_vector(covector, name="covector")
    if j_arr.shape[0] != c_arr.shape[0]:
        raise DifferentialShapeError(
            "covector length must match jacobian rows, "
            f"got jacobian {j_arr.shape} and covector {c_arr.shape}"
        )
    return j_arr.T @ c_arr


__all__ = [
    "DEFAULT_RANK_TOLERANCE_FACTOR",
    "RankReport",
    "composite_jacobian",
    "default_rank_tolerance",
    "pullback_covector",
    "pushforward_vector",
    "rank_report",
]
