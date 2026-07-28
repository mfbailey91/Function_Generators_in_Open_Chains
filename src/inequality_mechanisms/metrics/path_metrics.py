"""Path length metrics in U, Q, and Cartesian X (S4-03)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass

import numpy as np

from inequality_mechanisms.graphs.costs import (
    wrapped_input_displacement,
)
from inequality_mechanisms.graphs.validation import ConstrainedInputGraph
from inequality_mechanisms.kinematics.planar_2r import Planar2R
from inequality_mechanisms.visualization.paths import path_inputs, path_outputs

# Default absolute tolerance for C* vs path-length invariants.
PATH_METRIC_ATOL = 1e-9


@dataclass(frozen=True, slots=True)
class PathMetrics:
    """Scalar path quality measures for a solved discrete path.

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
    length_u = 0.0
    length_q = 0.0
    for i in range(n_edges):
        length_u += wrapped_input_displacement(u_path[i], u_path[i + 1], wrap=wrap)
        length_q += float(np.linalg.norm(q_path[i + 1] - q_path[i]))

    fk = plant if plant is not None else Planar2R()
    x_path = np.vstack([fk.forward(q) for q in q_path])
    length_x = float(np.sum(np.linalg.norm(np.diff(x_path, axis=0), axis=1)))

    return PathMetrics(
        n_path_edges=n_edges,
        path_length_u=float(length_u),
        path_length_q=float(length_q),
        path_length_x=float(length_x),
        optimal_cost=float(optimal_cost),
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
