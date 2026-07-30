"""Search-landscape diagnostic panels over U (S4-08)."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from inequality_mechanisms.diagnostics.plots import basin_metrics
from inequality_mechanisms.graphs.costs import build_edge_cost
from inequality_mechanisms.graphs.validation import ConstrainedInputGraph
from inequality_mechanisms.search.cost_to_go import reverse_dijkstra
from inequality_mechanisms.visualization.paths import path_inputs


def _require_matplotlib() -> Any:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "matplotlib is required for landscape plots; "
            "install with pip install matplotlib"
        ) from exc
    return plt


def _field_from_nodes(
    graph: ConstrainedInputGraph,
    values: Mapping[int, float],
    *,
    fill: float = np.nan,
) -> np.ndarray:
    n0, n1 = graph.grid.shape
    field = np.full((n0, n1), fill, dtype=np.float64)
    for nid, val in values.items():
        i0, i1 = graph.grid.indices_from_id(int(nid))
        field[i0, i1] = float(val)
    return field


def _valid_mask(graph: ConstrainedInputGraph) -> np.ndarray:
    n0, n1 = graph.grid.shape
    mask = np.zeros((n0, n1), dtype=np.float64)
    for node in graph.iter_valid_nodes():
        i0, i1 = node.indices
        mask[i0, i1] = 1.0
    return mask


def _coords(graph: ConstrainedInputGraph) -> tuple[np.ndarray, np.ndarray]:
    n0, n1 = graph.grid.shape
    u0 = np.array(
        [graph.grid.coordinates(i, 0)[0] for i in range(n0)], dtype=np.float64
    )
    u1 = np.array(
        [graph.grid.coordinates(0, j)[1] for j in range(n1)], dtype=np.float64
    )
    return np.meshgrid(u0, u1, indexing="ij")


def _save_heatmap(
    field: np.ndarray,
    graph: ConstrainedInputGraph,
    path_out: Path,
    *,
    title: str,
    cmap: str = "viridis",
    path: Sequence[int] | None = None,
    contour_level: float | None = None,
    binary: bool = False,
) -> Path:
    plt = _require_matplotlib()
    uu0, uu1 = _coords(graph)
    fig, ax = plt.subplots(figsize=(5.5, 5.0))
    plot_field = field.copy()
    if binary:
        pcm = ax.pcolormesh(
            uu0, uu1, plot_field, shading="auto", cmap="gray_r", vmin=0, vmax=1
        )
    else:
        pcm = ax.pcolormesh(uu0, uu1, plot_field, shading="auto", cmap=cmap)
        fig.colorbar(pcm, ax=ax, fraction=0.046, pad=0.04)
    if contour_level is not None and np.isfinite(contour_level):
        ax.contour(
            uu0,
            uu1,
            plot_field,
            levels=[float(contour_level)],
            colors="white",
            linewidths=1.2,
        )
    if path:
        pts = path_inputs(graph, path)
        ax.plot(pts[:, 0], pts[:, 1], color="C1", lw=2.0)
    # Seam markers for wrap axes.
    (u0_lo, u0_hi), (u1_lo, u1_hi) = graph.grid.ranges
    if graph.grid.wrap[0]:
        ax.axvline(u0_lo, color="0.7", ls=":", lw=0.8)
        ax.axvline(u0_hi, color="0.7", ls=":", lw=0.8)
    if graph.grid.wrap[1]:
        ax.axhline(u1_lo, color="0.7", ls=":", lw=0.8)
        ax.axhline(u1_hi, color="0.7", ls=":", lw=0.8)
    ax.set_xlabel("u0")
    ax.set_ylabel("u1")
    ax.set_title(title)
    ax.set_aspect("equal")
    fig.tight_layout()
    path_out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path_out, dpi=140, bbox_inches="tight")
    plt.close(fig)
    return path_out


def _mean_outgoing_edge_cost(
    graph: ConstrainedInputGraph,
    edge_cost,
) -> dict[int, float]:
    acc: dict[int, list[float]] = {}
    for a, b in graph.iter_edges():
        c = float(edge_cost(a, b))
        acc.setdefault(a, []).append(c)
        acc.setdefault(b, []).append(c)
    return {nid: float(sum(vals) / len(vals)) for nid, vals in acc.items()}


def _gain_field(graph: ConstrainedInputGraph) -> dict[int, float]:
    out: dict[int, float] = {}
    for node in graph.iter_valid_nodes():
        try:
            j = np.asarray(
                graph.mechanism.output_jacobian(node.coordinates), dtype=np.float64
            )
            out[node.node_id] = float(np.linalg.norm(j, ord="fro"))
        except Exception:
            out[node.node_id] = float("nan")
    return out


def write_landscape_bundle(
    graph: ConstrainedInputGraph,
    *,
    start: int,
    goal: int,
    path: Sequence[int],
    expanded: Sequence[int],
    cost_type: str,
    out_dir: Path | str,
    c_star: float | None = None,
) -> dict[str, Any]:
    """Write the S4-08 landscape PNG bundle and metrics JSON.

    Parameters
    ----------
    graph :
        Constrained input lattice.
    start, goal :
        Flat node ids.
    path :
        Optimal path node ids.
    expanded :
        Expanded-node ids from a recorded search.
    cost_type :
        Edge-cost registry name.
    out_dir :
        Destination directory (created if needed).
    c_star :
        Optimal path cost; defaults to distance-to-goal at start.

    Returns
    -------
    dict
        Landscape metrics including ``beta`` and ``eta_reachable``.
    """
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    edge_cost = build_edge_cost(graph, cost_type)

    valid = _valid_mask(graph)
    from_start = reverse_dijkstra(graph, int(start), edge_cost=edge_cost).costs
    to_goal = reverse_dijkstra(graph, int(goal), edge_cost=edge_cost).costs
    if c_star is None:
        c_star = float(to_goal.get(int(start), math.inf))
    eta, beta = basin_metrics(
        from_start, c_star=float(c_star), n_expanded=len(list(expanded))
    )

    reachable_mask = np.full(graph.grid.shape, np.nan, dtype=np.float64)
    for nid, c in from_start.items():
        if math.isfinite(float(c)):
            i0, i1 = graph.grid.indices_from_id(int(nid))
            reachable_mask[i0, i1] = 1.0

    expanded_mask = np.zeros(graph.grid.shape, dtype=np.float64)
    for nid in expanded:
        i0, i1 = graph.grid.indices_from_id(int(nid))
        expanded_mask[i0, i1] = 1.0

    edge_field = _field_from_nodes(graph, _mean_outgoing_edge_cost(graph, edge_cost))
    gain_field = _field_from_nodes(graph, _gain_field(graph))
    d_start = _field_from_nodes(graph, from_start)
    d_goal = _field_from_nodes(graph, to_goal)

    files = {
        "valid_nodes.png": lambda: _save_heatmap(
            valid, graph, root / "valid_nodes.png", title="Valid nodes", binary=True
        ),
        "reachable_nodes.png": lambda: _save_heatmap(
            reachable_mask,
            graph,
            root / "reachable_nodes.png",
            title="Reachable from start",
            binary=True,
        ),
        "edge_cost_field.png": lambda: _save_heatmap(
            edge_field,
            graph,
            root / "edge_cost_field.png",
            title=f"Local edge cost ({cost_type})",
        ),
        "mechanism_gain_field.png": lambda: _save_heatmap(
            gain_field,
            graph,
            root / "mechanism_gain_field.png",
            title=r"Mechanism gain $\|J_g\|_F$",
            cmap="magma",
        ),
        "distance_from_start.png": lambda: _save_heatmap(
            d_start,
            graph,
            root / "distance_from_start.png",
            title="Distance from start",
            path=path,
        ),
        "distance_to_goal.png": lambda: _save_heatmap(
            d_goal,
            graph,
            root / "distance_to_goal.png",
            title="Distance to goal",
            path=path,
        ),
        "expanded_mask.png": lambda: _save_heatmap(
            expanded_mask,
            graph,
            root / "expanded_mask.png",
            title="Expanded nodes",
            binary=True,
            path=path,
        ),
        "goal_cost_basin.png": lambda: _save_heatmap(
            d_start,
            graph,
            root / "goal_cost_basin.png",
            title=f"Goal-cost basin (β={beta:.3f})",
            path=path,
            contour_level=float(c_star) if math.isfinite(float(c_star)) else None,
        ),
        "optimal_path.png": lambda: _save_heatmap(
            d_start,
            graph,
            root / "optimal_path.png",
            title="Optimal path overlay",
            path=path,
        ),
    }
    written: dict[str, str] = {}
    for name, fn in files.items():
        written[name] = fn().name

    metrics = {
        "cost_type": cost_type,
        "start": int(start),
        "goal": int(goal),
        "c_star": float(c_star) if c_star is not None else None,
        "n_expanded": int(len(list(expanded))),
        "n_path_edges": max(0, len(list(path)) - 1),
        "beta": float(beta),
        "eta_reachable": float(eta),
        "n_valid_nodes": int(graph.valid_node_count),
        "n_reachable_nodes": int(
            sum(1 for c in from_start.values() if math.isfinite(float(c)))
        ),
        "files": written,
    }
    (root / "landscape_metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return metrics
