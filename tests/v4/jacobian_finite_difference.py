"""Test-only independent finite-difference Jacobians (V4-107 / deferred V4-006)."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from numpy.typing import NDArray


def central_difference_jacobian(
    forward: Callable[[NDArray[np.float64]], NDArray[np.float64]],
    u: NDArray[np.float64],
    *,
    h: float,
) -> NDArray[np.float64]:
    """Return the central-difference Jacobian of ``forward`` at ``u``.

    This helper is for tests only. It is not a production Jacobian API.
    """
    u_arr = np.asarray(u, dtype=np.float64)
    y0 = np.asarray(forward(u_arr), dtype=np.float64)
    columns: list[NDArray[np.float64]] = []
    for i in range(u_arr.size):
        e = np.zeros_like(u_arr)
        e[i] = 1.0
        plus = np.asarray(forward(u_arr + h * e), dtype=np.float64)
        minus = np.asarray(forward(u_arr - h * e), dtype=np.float64)
        if plus.shape != y0.shape or minus.shape != y0.shape:
            raise ValueError(
                f"finite-difference column {i} changed output shape: "
                f"h={h}, plus={plus.shape}, minus={minus.shape}, y0={y0.shape}"
            )
        columns.append((plus - minus) / (2.0 * h))
    return np.column_stack(columns)


def step_size_sensitivity(
    forward: Callable[[NDArray[np.float64]], NDArray[np.float64]],
    analytic: NDArray[np.float64],
    u: NDArray[np.float64],
    steps: tuple[float, ...] = (1e-4, 1e-5, 1e-6, 1e-7),
) -> dict[float, float]:
    """Return max-abs residuals vs ``analytic`` at several step sizes."""
    residuals: dict[float, float] = {}
    for h in steps:
        fd = central_difference_jacobian(forward, u, h=h)
        residuals[float(h)] = float(np.max(np.abs(fd - analytic)))
    return residuals
