"""Mechanism and graph descriptors for Sprint Four attribution (S4-09)."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from inequality_mechanisms.diagnostics.plots import basin_metrics
from inequality_mechanisms.graphs.costs import build_edge_cost
from inequality_mechanisms.graphs.validation import ConstrainedInputGraph
from inequality_mechanisms.mechanisms.base import Mechanism
from inequality_mechanisms.mechanisms.fourbar import IndependentFourBars, PlanarFourBar
from inequality_mechanisms.mechanisms.population import follower_range
from inequality_mechanisms.search.cost_to_go import reverse_dijkstra


def _gain_stats(
    gains: np.ndarray,
    *,
    eps: float,
    high_threshold: float,
    reversal_eps: float,
) -> dict[str, float]:
    g = np.asarray(gains, dtype=np.float64)
    g = g[np.isfinite(g)]
    if g.size == 0:
        return {
            "gain_min": float("nan"),
            "gain_max": float("nan"),
            "gain_mean": float("nan"),
            "gain_var": float("nan"),
            "rho_epsilon": float("nan"),
            "high_gain_fraction": float("nan"),
            "near_reversal_fraction": float("nan"),
        }
    abs_g = np.abs(g)
    return {
        "gain_min": float(np.min(abs_g)),
        "gain_max": float(np.max(abs_g)),
        "gain_mean": float(np.mean(abs_g)),
        "gain_var": float(np.var(abs_g)),
        "rho_epsilon": float(np.mean(abs_g < float(eps))),
        "high_gain_fraction": float(np.mean(abs_g > float(high_threshold))),
        "near_reversal_fraction": float(np.mean(abs_g < float(reversal_eps))),
    }


def mechanism_descriptors(
    mechanism: Mechanism,
    *,
    n_samples: int = 181,
    eps: float = 0.05,
    high_threshold: float = 2.0,
    reversal_eps: float = 0.02,
) -> dict[str, Any]:
    """Compute Jacobian / follower-range descriptors for a mechanism."""
    u = np.linspace(0.0, 2.0 * np.pi, int(n_samples), endpoint=False)
    gains: list[float] = []
    dets: list[float] = []
    conds: list[float] = []
    follower_ranges: list[float] = []

    if isinstance(mechanism, IndependentFourBars):
        for bar in mechanism.bars:
            lo, hi = follower_range(bar, n_samples=n_samples)
            follower_ranges.append(float(hi - lo))
            for uu in u:
                try:
                    j = bar.output_jacobian([float(uu)])
                    gains.append(float(j[0, 0]))
                    dets.append(float(abs(j[0, 0])))
                    conds.append(float(abs(j[0, 0])) if abs(j[0, 0]) > 0 else math.inf)
                except Exception:
                    continue
    elif isinstance(mechanism, PlanarFourBar):
        lo, hi = follower_range(mechanism, n_samples=n_samples)
        follower_ranges.append(float(hi - lo))
        for uu in u:
            try:
                j = mechanism.output_jacobian([float(uu)])
                gains.append(float(j[0, 0]))
                dets.append(float(abs(j[0, 0])))
                conds.append(float(abs(j[0, 0])) if abs(j[0, 0]) > 0 else math.inf)
            except Exception:
                continue
    else:
        # Gearbox / general: sample a 1-D slice and full Jacobian norms.
        follower_ranges.append(2.0 * math.pi)  # unit map span on each axis
        grid_u = np.stack([u, np.zeros_like(u)], axis=1)
        for row in grid_u:
            try:
                j = np.asarray(mechanism.output_jacobian(row), dtype=np.float64)
                # Frobenius gain proxy and metric M = J^T J stats.
                gains.append(float(np.linalg.norm(j, ord="fro")))
                m = j.T @ j
                dets.append(float(np.linalg.det(m)))
                singular = np.linalg.svd(m, compute_uv=False)
                if singular.size and singular[-1] > 0:
                    conds.append(float(singular[0] / singular[-1]))
                else:
                    conds.append(float("inf"))
            except Exception:
                continue

    stats = _gain_stats(
        np.asarray(gains, dtype=np.float64),
        eps=eps,
        high_threshold=high_threshold,
        reversal_eps=reversal_eps,
    )
    det_arr = np.asarray(dets, dtype=np.float64)
    det_arr = det_arr[np.isfinite(det_arr)]
    cond_arr = np.asarray(conds, dtype=np.float64)
    cond_arr = cond_arr[np.isfinite(cond_arr)]
    return {
        "mechanism_type": getattr(mechanism, "type_key", type(mechanism).__name__),
        "follower_range_mean": float(np.mean(follower_ranges)) if follower_ranges else float("nan"),
        "follower_ranges": follower_ranges,
        **stats,
        "metric_det_mean": float(np.mean(det_arr)) if det_arr.size else float("nan"),
        "metric_det_var": float(np.var(det_arr)) if det_arr.size else float("nan"),
        "metric_cond_mean": float(np.mean(cond_arr)) if cond_arr.size else float("nan"),
        "metric_cond_max": float(np.max(cond_arr)) if cond_arr.size else float("nan"),
        "n_jacobian_samples": int(len(gains)),
    }


def graph_descriptors(
    graph: ConstrainedInputGraph,
    *,
    cost_type: str = "output_euclidean",
    start: int | None = None,
    goal: int | None = None,
    c_star: float | None = None,
    n_expanded: int | None = None,
    low_cost_quantile: float = 0.25,
) -> dict[str, Any]:
    """Compute connectivity and cost-field descriptors on a fixed graph."""
    n_nodes = int(graph.grid.node_count)
    n_valid = int(graph.valid_node_count)
    edge_cost = build_edge_cost(graph, cost_type)
    edge_costs = [float(edge_cost(a, b)) for a, b in graph.iter_edges()]
    ec = np.asarray(edge_costs, dtype=np.float64)
    ec = ec[np.isfinite(ec)]

    n_reachable = 0
    beta = float("nan")
    eta = float("nan")
    unweighted_path_len: int | None = None
    if start is not None:
        ctg = reverse_dijkstra(graph, int(start), edge_cost=edge_cost)
        reachable = [c for c in ctg.costs.values() if math.isfinite(float(c))]
        n_reachable = len(reachable)
        if c_star is not None and n_expanded is not None and math.isfinite(float(c_star)):
            eta, beta = basin_metrics(
                ctg.costs, c_star=float(c_star), n_expanded=int(n_expanded)
            )
        # Unweighted hop length via uniform reverse Dijkstra from goal if given.
        if goal is not None:
            from inequality_mechanisms.graphs.costs import uniform_edge_cost

            hops = reverse_dijkstra(graph, int(goal), edge_cost=uniform_edge_cost)
            h = hops.costs.get(int(start))
            if h is not None and math.isfinite(float(h)):
                unweighted_path_len = int(round(float(h)))

    low_frac = float("nan")
    if ec.size:
        thr = float(np.quantile(ec, float(low_cost_quantile)))
        low_frac = float(np.mean(ec <= thr))

    # Preimage richness proxy: unique rounded chart outputs among valid nodes.
    q_keys: set[tuple[float, ...]] = set()
    for node in graph.iter_valid_nodes():
        q = np.asarray(graph.output(node.coordinates), dtype=np.float64)
        q_keys.add(tuple(np.round(q, decimals=6).tolist()))

    return {
        "n_grid_nodes": n_nodes,
        "n_valid_nodes": n_valid,
        "valid_node_fraction": float(n_valid / n_nodes) if n_nodes else float("nan"),
        "n_reachable_nodes": n_reachable,
        "reachable_node_fraction": (
            float(n_reachable / n_valid) if n_valid else float("nan")
        ),
        "n_connected_components": int(graph.connected_component_count()),
        "n_discrete_output_preimages": int(len(q_keys)),
        "edge_cost_mean": float(np.mean(ec)) if ec.size else float("nan"),
        "edge_cost_variance": float(np.var(ec)) if ec.size else float("nan"),
        "low_cost_edge_fraction": low_frac,
        "beta": beta,
        "eta_reachable": eta,
        "shortest_unweighted_path_length": unweighted_path_len,
        "cost_type": cost_type,
    }


def correlate_descriptors(
    rows: Sequence[Mapping[str, Any]],
    *,
    x_fields: Sequence[str],
    y_field: str,
) -> dict[str, float | None]:
    """Pearson correlations of descriptor columns against ``y_field``."""
    y_vals = []
    x_cols: dict[str, list[float]] = {f: [] for f in x_fields}
    for row in rows:
        y = row.get(y_field)
        if y is None or not np.isfinite(float(y)):
            continue
        ok = True
        xs = []
        for f in x_fields:
            v = row.get(f)
            if v is None or not np.isfinite(float(v)):
                ok = False
                break
            xs.append(float(v))
        if not ok:
            continue
        y_vals.append(float(y))
        for f, v in zip(x_fields, xs, strict=True):
            x_cols[f].append(v)
    out: dict[str, float | None] = {}
    y_arr = np.asarray(y_vals, dtype=np.float64)
    if y_arr.size < 2:
        return {f: None for f in x_fields}
    for f, xs in x_cols.items():
        x_arr = np.asarray(xs, dtype=np.float64)
        if x_arr.size != y_arr.size or np.std(x_arr) == 0 or np.std(y_arr) == 0:
            out[f] = None
        else:
            out[f] = float(np.corrcoef(x_arr, y_arr)[0, 1])
    return out
