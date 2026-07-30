"""Path length metrics in U, Q, and Cartesian X (S4-03 / S5-01).

Coordinate conventions (stored in run metadata via
:data:`PATH_LENGTH_CONVENTIONS`):

- ``U``: wrapped input displacement in radians (periodic axes use short arc).
- ``Q``: Euclidean distance in the canonicalized bounded output chart.
- ``X``: Euclidean end-effector displacement from planar 2R forward kinematics.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from inequality_mechanisms.graphs.costs import (
    wrapped_input_displacement,
)
from inequality_mechanisms.graphs.validation import ConstrainedInputGraph
from inequality_mechanisms.kinematics.planar_2r import Planar2R
from inequality_mechanisms.spaces.output_space import OutputSpace
from inequality_mechanisms.visualization.paths import path_inputs, path_outputs

# Default absolute tolerance for C* vs path-length invariants.
PATH_METRIC_ATOL = 1e-9

PATH_LENGTH_CONVENTIONS: dict[str, Any] = {
    "n_path_edges": "discrete edge count along the node path",
    "path_length_u": {
        "symbol": "L_U",
        "space": "U",
        "units": "rad",
        "metric": "wrapped_input_displacement (short arc on 2*pi for wrapped axes)",
    },
    "path_length_q": {
        "symbol": "L_Q",
        "space": "Q",
        "units": "rad (canonicalized chart coordinates)",
        "metric": "OutputSpace.distance on already-canonicalized samples",
    },
    "path_length_x": {
        "symbol": "L_X",
        "space": "X",
        "units": "length (planar 2R EE frame)",
        "metric": "Euclidean ||x_{k+1} - x_k||_2",
    },
}


@dataclass(frozen=True, slots=True)
class PathMetrics:
    """Scalar path length measures for a solved discrete path.

    Attributes
    ----------
    n_path_edges :
        Number of edges on the path.
    path_length_u :
        Sum of wrapped input displacements along the path.
    path_length_q :
        Sum of output-chart displacements along the path.
    path_length_x :
        Sum of Cartesian end-effector displacements along the path.
    optimal_cost :
        ``C*`` under the selected search metric (may be ``inf`` if unsolved).
    """

    n_path_edges: int
    path_length_u: float
    path_length_q: float
    path_length_x: float
    optimal_cost: float

    def to_dict(self) -> dict[str, int | float]:
        """JSON-serializable field dict."""
        return asdict(self)


def _q_segment_length(
    q_a: np.ndarray,
    q_b: np.ndarray,
    *,
    output_space: OutputSpace | None,
) -> float:
    """Return one-step ``d_Q`` using shared OutputSpace when available."""
    if output_space is not None:
        return float(output_space.distance(q_a, q_b))
    return float(np.linalg.norm(q_b - q_a))


def compute_path_metrics_from_trajectories(
    u_path: np.ndarray,
    q_path: np.ndarray,
    *,
    optimal_cost: float,
    wrap_u: tuple[bool, ...] | list[bool] = (False, False),
    plant: Planar2R | None = None,
    output_space: OutputSpace | None = None,
) -> PathMetrics:
    """Compute path metrics from explicit ``U`` and ``Q`` sample sequences.

    Used by the Sprint Four monotonic Q-grid control, where lattice identity
    may be ``q`` while ``L_U`` still needs the attached crank trajectory.

    Parameters
    ----------
    u_path, q_path :
        Sample sequences, shape ``(N+1, dim)``. ``q_path`` should already be
        chart-canonicalized when ``output_space`` is omitted.
    optimal_cost :
        Search-reported ``C*`` (stored verbatim).
    wrap_u :
        Per-axis wrap flags for input displacement.
    plant :
        Planar 2R map for Cartesian length; default unit lengths.
    output_space :
        Optional shared output space; when provided, ``L_Q`` uses
        :meth:`OutputSpace.distance`.
    """
    u_arr = np.asarray(u_path, dtype=np.float64)
    q_arr = np.asarray(q_path, dtype=np.float64)
    if u_arr.ndim != 2 or q_arr.ndim != 2:
        raise ValueError("u_path and q_path must be 2-D arrays")
    if u_arr.shape[0] != q_arr.shape[0]:
        raise ValueError("u_path and q_path must have the same length")
    n_edges = max(0, int(u_arr.shape[0]) - 1)
    if n_edges == 0:
        return PathMetrics(
            n_path_edges=0,
            path_length_u=0.0,
            path_length_q=0.0,
            path_length_x=0.0,
            optimal_cost=float(optimal_cost),
        )

    length_u = 0.0
    length_q = 0.0
    for i in range(n_edges):
        length_u += wrapped_input_displacement(u_arr[i], u_arr[i + 1], wrap=wrap_u)
        length_q += _q_segment_length(
            q_arr[i], q_arr[i + 1], output_space=output_space
        )

    fk = plant if plant is not None else Planar2R()
    x_path = np.vstack([fk.forward(q) for q in q_arr])
    length_x = float(np.sum(np.linalg.norm(np.diff(x_path, axis=0), axis=1)))

    return PathMetrics(
        n_path_edges=n_edges,
        path_length_u=float(length_u),
        path_length_q=float(length_q),
        path_length_x=float(length_x),
        optimal_cost=float(optimal_cost),
    )


def compute_path_metrics(
    graph: ConstrainedInputGraph,
    path: Sequence[int],
    *,
    optimal_cost: float,
    plant: Planar2R | None = None,
) -> PathMetrics:
    """Compute ``N_edges``, ``L_U``, ``L_Q``, and ``L_X`` for a node path.

    Parameters
    ----------
    graph :
        Constrained input graph providing U/Q geometry.
    path :
        Ordered flat node ids (inclusive start/goal).
    optimal_cost :
        Search-reported ``C*`` (stored verbatim).
    plant :
        Optional planar 2R map for Cartesian length; default unit lengths.

    Returns
    -------
    PathMetrics
    """
    nodes = [int(n) for n in path]
    n_edges = max(0, len(nodes) - 1)
    if n_edges == 0:
        return PathMetrics(
            n_path_edges=0,
            path_length_u=0.0,
            path_length_q=0.0,
            path_length_x=0.0,
            optimal_cost=float(optimal_cost),
        )

    wrap = graph.grid.wrap
    u_path = path_inputs(graph, nodes)
    q_path = path_outputs(graph, nodes)
    return compute_path_metrics_from_trajectories(
        u_path,
        q_path,
        optimal_cost=optimal_cost,
        wrap_u=wrap,
        plant=plant,
        output_space=graph.output_space,
    )


def assert_cost_path_invariant(
    cost_name: str,
    metrics: PathMetrics,
    *,
    atol: float = PATH_METRIC_ATOL,
) -> None:
    """Raise ``AssertionError`` if ``C*`` disagrees with the matching length.

    Under uniform cost ``C* = N_edges``; under input Euclidean ``C* = L_U``;
    under output Euclidean ``C* = L_Q``.
    """
    c_star = float(metrics.optimal_cost)
    if not np.isfinite(c_star):
        raise AssertionError("optimal_cost must be finite for invariant check")
    if cost_name == "uniform":
        expected = float(metrics.n_path_edges)
        label = "n_path_edges"
    elif cost_name == "input_euclidean":
        expected = float(metrics.path_length_u)
        label = "path_length_u"
    elif cost_name == "output_euclidean":
        expected = float(metrics.path_length_q)
        label = "path_length_q"
    else:
        raise ValueError(f"no path invariant defined for cost {cost_name!r}")
    if abs(c_star - expected) > atol:
        raise AssertionError(
            f"cost {cost_name!r}: C*={c_star} disagrees with {label}={expected} "
            f"(atol={atol})"
        )
