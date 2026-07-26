"""Diagnostic figure helpers paired with numerical assertions.

Plots consume shared traces / graph APIs only — no plot-specific mapping.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray

from inequality_mechanisms.diagnostics.mapping import mapping_curve
from inequality_mechanisms.graphs.edge_trace import EdgeTrace, build_edge_trace
from inequality_mechanisms.graphs.grid import PeriodicGrid2D
from inequality_mechanisms.graphs.validation import ConstrainedInputGraph
from inequality_mechanisms.spaces.output_space import OutputSpace


def _require_matplotlib() -> Any:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "matplotlib is required for diagnostic plots; "
            "install with pip install matplotlib"
        ) from exc
    return plt


def _save(fig: Any, path_out: Path | str, plt: Any) -> Path:
    out = Path(path_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_mapping_atlas(
    curve: Mapping[str, NDArray[np.floating]],
    path_out: Path | str,
    *,
    title: str | None = None,
    degrees: bool = True,
) -> Path:
    """Plot raw / canonical / winding / dq/du vs actuator angle."""
    plt = _require_matplotlib()
    u = np.asarray(curve["u"], dtype=np.float64)
    scale = 180.0 / np.pi if degrees else 1.0
    unit = "deg" if degrees else "rad"
    fig, axes = plt.subplots(4, 1, figsize=(8, 9), sharex=True)
    axes[0].plot(u * scale, np.asarray(curve["raw"]) * scale, color="#1f4e79", lw=1.5)
    axes[0].set_ylabel(f"raw ({unit})")
    axes[0].set_title(title or "Mechanism mapping atlas")
    axes[1].plot(u * scale, np.asarray(curve["canonical"]) * scale, color="#2e7d32", lw=1.5)
    axes[1].axhline(float(curve["q_min"][0]) * scale, color="#c62828", ls="--", lw=1)
    axes[1].axhline(float(curve["q_max"][0]) * scale, color="#c62828", ls="--", lw=1)
    axes[1].set_ylabel(f"canonical ({unit})")
    axes[2].step(u * scale, np.asarray(curve["winding"]), where="mid", color="#6a1b9a")
    axes[2].set_ylabel("winding")
    axes[3].plot(u * scale, np.asarray(curve["dq_du"]), color="#ef6c00", lw=1.2)
    axes[3].set_ylabel("dq/du")
    axes[3].set_xlabel(f"u ({unit})")
    fig.tight_layout()
    return _save(fig, path_out, plt)


def plot_topology_panels(
    u: ArrayLike,
    q_raw: ArrayLike,
    q_can: ArrayLike,
    path_out: Path | str,
    *,
    q_min: float,
    q_max: float,
    title: str | None = None,
) -> Path:
    """Three-panel U / raw / Q topology view for one actuator sweep."""
    plt = _require_matplotlib()
    uu = np.asarray(u, dtype=np.float64)
    raw = np.asarray(q_raw, dtype=np.float64)
    can = np.asarray(q_can, dtype=np.float64)
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.4))
    # U as angle on a circle.
    th = uu
    axes[0].plot(np.cos(th), np.sin(th), color="#1f4e79", lw=1.5)
    axes[0].scatter([np.cos(th[0])], [np.sin(th[0])], c="#2e7d32", s=40, zorder=3)
    axes[0].scatter([np.cos(th[-1])], [np.sin(th[-1])], c="#c62828", s=40, zorder=3)
    axes[0].set_aspect("equal")
    axes[0].set_title("Actuator U")
    axes[0].set_xlim(-1.3, 1.3)
    axes[0].set_ylim(-1.3, 1.3)
    axes[1].plot(uu, raw, color="#6a1b9a", lw=1.4)
    axes[1].set_title("Raw solver angle")
    axes[1].set_xlabel("u")
    axes[2].plot(uu, can, color="#2e7d32", lw=1.4)
    axes[2].axhline(q_min, color="#c62828", ls="--", lw=1)
    axes[2].axhline(q_max, color="#c62828", ls="--", lw=1)
    axes[2].set_title("Canonical Q")
    axes[2].set_xlabel("u")
    fig.suptitle(title or "Topology: U → raw → Q", y=1.02)
    fig.tight_layout()
    return _save(fig, path_out, plt)


def plot_edge_microscope(
    trace: EdgeTrace,
    path_out: Path | str,
    *,
    axis: int = 0,
    title: str | None = None,
) -> Path:
    """Stack aligned edge-sample tracks from a shared EdgeTrace."""
    plt = _require_matplotlib()
    s = np.array([p.s for p in trace.samples], dtype=np.float64)
    u_axis = np.array(
        [p.u[min(axis, len(p.u) - 1)] for p in trace.samples], dtype=np.float64
    )
    q_raw = np.array(
        [
            np.nan if p.q_raw is None else p.q_raw[min(axis, len(p.q_raw) - 1)]
            for p in trace.samples
        ],
        dtype=np.float64,
    )
    q_can = np.array(
        [
            np.nan
            if p.q_canonical is None
            else p.q_canonical[min(axis, len(p.q_canonical) - 1)]
            for p in trace.samples
        ],
        dtype=np.float64,
    )
    wind = np.array(
        [
            np.nan
            if p.windings is None
            else p.windings[min(axis, len(p.windings) - 1)]
            for p in trace.samples
        ],
        dtype=np.float64,
    )
    assembly = np.array([1.0 if p.assembly_valid else 0.0 for p in trace.samples])
    limits = np.array([1.0 if p.limits_valid else 0.0 for p in trace.samples])
    seg = np.array(
        [
            np.nan if p.segment_cost_from_prev is None else p.segment_cost_from_prev
            for p in trace.samples
        ],
        dtype=np.float64,
    )

    fig, axes = plt.subplots(7, 1, figsize=(8, 11), sharex=True)
    tracks = (
        (u_axis, "u(s)", "#1f4e79"),
        (q_raw, "q_raw(s)", "#6a1b9a"),
        (q_can, "q_canonical(s)", "#2e7d32"),
        (wind, "winding", "#4527a0"),
        (assembly, "assembly", "#00838f"),
        (limits, "limits", "#ef6c00"),
        (seg, "segment cost", "#c62828"),
    )
    for ax, (y, lab, color) in zip(axes, tracks, strict=True):
        ax.plot(s, y, color=color, lw=1.4, marker="o", ms=3)
        ax.set_ylabel(lab)
    if trace.first_invalid_index is not None:
        s_fail = float(trace.samples[trace.first_invalid_index].s)
        for ax in axes:
            ax.axvline(s_fail, color="#b71c1c", ls="--", lw=1)
    axes[0].set_title(
        title
        or (
            f"Edge microscope — valid={trace.is_valid}"
            + (
                f", fail@{trace.first_invalid_index}:{trace.first_invalid_reason}"
                if not trace.is_valid
                else ""
            )
        )
    )
    axes[-1].set_xlabel("s")
    fig.tight_layout()
    return _save(fig, path_out, plt)


EdgeKind = Literal["interior", "seam0", "seam1", "path"]


def classify_lattice_edge(
    grid: PeriodicGrid2D,
    a: int,
    b: int,
) -> EdgeKind:
    """Classify an undirected lattice edge as interior or wrap-seam."""
    i0, i1 = grid.indices_from_id(a)
    j0, j1 = grid.indices_from_id(b)
    di = abs(i0 - j0)
    dj = abs(i1 - j1)
    n0, n1 = grid.shape
    wrap0 = bool(grid.wrap[0]) and di == n0 - 1 and dj == 0
    wrap1 = bool(grid.wrap[1]) and dj == n1 - 1 and di == 0
    if wrap0:
        return "seam0"
    if wrap1:
        return "seam1"
    return "interior"


def plot_edge_density_differences(
    graphs_by_samples: Mapping[int, ConstrainedInputGraph],
    path_out: Path | str,
    *,
    path_edges: set[tuple[int, int]] | None = None,
    title: str | None = None,
) -> Path:
    """Highlight edges removed as validation density increases."""
    plt = _require_matplotlib()
    levels = sorted(graphs_by_samples.keys(), reverse=True)
    if len(levels) < 2:
        raise ValueError("need at least two edge_samples levels")
    fig, axes = plt.subplots(1, len(levels) - 1, figsize=(3.2 * (len(levels) - 1), 3.4))
    if len(levels) == 2:
        axes = [axes]
    colors = {
        "interior": "#c62828",
        "seam0": "#1565c0",
        "seam1": "#2e7d32",
        "path": "#f9a825",
    }
    for ax, dense, sparse in zip(axes, levels[:-1], levels[1:], strict=False):
        g_dense = graphs_by_samples[dense]
        g_sparse = graphs_by_samples[sparse]
        removed = set(g_sparse.iter_edges()) - set(g_dense.iter_edges())
        # Background: denser graph edges faintly.
        for a, b in g_dense.iter_edges():
            _draw_edge(ax, g_dense.grid, a, b, color="#bdbdbd", lw=0.4, alpha=0.5)
        for a, b in removed:
            kind = classify_lattice_edge(g_dense.grid, a, b)
            if path_edges is not None and ((a, b) in path_edges or (b, a) in path_edges):
                kind = "path"
            _draw_edge(ax, g_dense.grid, a, b, color=colors[kind], lw=1.6, alpha=1.0)
        ax.set_title(f"removed {sparse}→{dense}")
        ax.set_aspect("equal")
        ax.set_xlim(0, 2 * np.pi)
        ax.set_ylim(0, 2 * np.pi)
    fig.suptitle(title or "Edge-density removals", y=1.02)
    fig.tight_layout()
    return _save(fig, path_out, plt)


def _draw_edge(ax: Any, grid: PeriodicGrid2D, a: int, b: int, **kwargs: Any) -> None:
    ua = grid.coordinates(*grid.indices_from_id(a))
    ub = grid.coordinates(*grid.indices_from_id(b))
    # Short visual segment without wrapping through the chart (seam edges jump).
    ax.plot([ua[0], ub[0]], [ua[1], ub[1]], **kwargs)


def plot_search_basin(
    graph: ConstrainedInputGraph,
    costs: Mapping[int, float],
    path: Sequence[int],
    expanded: Sequence[int],
    path_out: Path | str,
    *,
    c_star: float,
    eta: float,
    beta: float,
    title: str | None = None,
) -> Path:
    """Heatmap of Dijkstra distance with expansions, path, and cost contour."""
    plt = _require_matplotlib()
    n0, n1 = graph.grid.shape
    field = np.full((n0, n1), np.nan, dtype=np.float64)
    for node_id, cost in costs.items():
        i0, i1 = graph.grid.indices_from_id(int(node_id))
        field[i0, i1] = float(cost)
    # Mark invalid nodes.
    for i0 in range(n0):
        for i1 in range(n1):
            if not graph.node_is_valid(i0, i1):
                field[i0, i1] = np.nan

    u0 = np.array(
        [graph.grid.coordinates(i, 0)[0] for i in range(n0)], dtype=np.float64
    )
    u1 = np.array(
        [graph.grid.coordinates(0, j)[1] for j in range(n1)], dtype=np.float64
    )
    uu0, uu1 = np.meshgrid(u0, u1, indexing="ij")
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    pcm = ax.pcolormesh(uu0, uu1, field, shading="auto", cmap="viridis")
    fig.colorbar(pcm, ax=ax, label="d(s, u)")
    if np.isfinite(c_star):
        ax.contour(uu0, uu1, field, levels=[c_star], colors="white", linewidths=1.2)
    exp_u = []
    for nid in expanded:
        i0, i1 = graph.grid.indices_from_id(int(nid))
        exp_u.append(graph.grid.coordinates(i0, i1))
    if exp_u:
        arr = np.asarray(exp_u)
        ax.scatter(arr[:, 0], arr[:, 1], s=8, c="#ffab00", alpha=0.55, label="expanded")
    if len(path) >= 2:
        pts = []
        for nid in path:
            i0, i1 = graph.grid.indices_from_id(int(nid))
            pts.append(graph.grid.coordinates(i0, i1))
        pts_a = np.asarray(pts)
        ax.plot(pts_a[:, 0], pts_a[:, 1], color="white", lw=2.0, label="path")
    ax.set_xlabel("u0")
    ax.set_ylabel("u1")
    ax.set_title(
        (title or "Search basin") + f"\nη={eta:.3f}, β={beta:.3f}, C*={c_star:.4g}"
    )
    ax.set_aspect("equal")
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    return _save(fig, path_out, plt)


def plot_task_preimages(
    graph: ConstrainedInputGraph,
    q_target: ArrayLike,
    continuous_preimages: Sequence[ArrayLike],
    candidate_node_ids: Sequence[int],
    selected_node_id: int | None,
    residuals: Mapping[int, float],
    path_out: Path | str,
    *,
    title: str | None = None,
) -> Path:
    """Show continuous preimages, snapped candidates, and residuals in U."""
    plt = _require_matplotlib()
    fig, ax = plt.subplots(figsize=(6, 5.5))
    # Valid lattice background.
    for node in graph.iter_valid_nodes():
        ax.scatter(
            node.coordinates[0],
            node.coordinates[1],
            s=6,
            c="#eceff1",
            zorder=1,
        )
    cont = np.asarray([np.asarray(p, dtype=np.float64) for p in continuous_preimages])
    if cont.size:
        ax.scatter(cont[:, 0], cont[:, 1], s=60, c="#6a1b9a", marker="*", label="continuous", zorder=3)
    for nid in candidate_node_ids:
        i0, i1 = graph.grid.indices_from_id(int(nid))
        u = graph.grid.coordinates(i0, i1)
        r = residuals.get(int(nid), np.nan)
        ax.scatter(u[0], u[1], s=40, c="#1565c0", zorder=4)
        if np.isfinite(r):
            ax.annotate(f"{r:.2g}", (u[0], u[1]), fontsize=7, color="#1565c0")
    if selected_node_id is not None:
        i0, i1 = graph.grid.indices_from_id(int(selected_node_id))
        u = graph.grid.coordinates(i0, i1)
        ax.scatter(u[0], u[1], s=90, facecolors="none", edgecolors="#c62828", lw=2, label="selected", zorder=5)
    ax.set_title(title or f"Preimages for q={np.asarray(q_target)}")
    ax.set_xlabel("u0")
    ax.set_ylabel("u1")
    ax.set_aspect("equal")
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    return _save(fig, path_out, plt)


def uniform_edge_cost(_u: int, _v: int) -> float:
    """Unit edge weight for ablation basins."""
    return 1.0


def input_euclidean_cost(graph: ConstrainedInputGraph) -> Callable[[int, int], float]:
    """Build lattice edge cost from short input displacement."""

    def cost(u_id: int, v_id: int) -> float:
        ua = np.asarray(
            graph.grid.coordinates(*graph.grid.indices_from_id(u_id)),
            dtype=np.float64,
        )
        ub = np.asarray(
            graph.grid.coordinates(*graph.grid.indices_from_id(v_id)),
            dtype=np.float64,
        )
        # Short periodic displacement on wrap axes.
        delta = ub - ua
        for i, wrap in enumerate(graph.mechanism.periodic_axes()):
            if wrap:
                delta[i] = (delta[i] + np.pi) % (2 * np.pi) - np.pi
        return float(np.linalg.norm(delta))

    return cost


def basin_metrics(
    costs: Mapping[int, float],
    *,
    c_star: float,
    n_expanded: int,
) -> tuple[float, float]:
    """Return ``(eta, beta)`` from a distance field and expansion count."""
    reachable = [c for c in costs.values() if np.isfinite(c)]
    n_reach = len(reachable)
    if n_reach == 0 or not np.isfinite(c_star):
        return 0.0, 0.0
    eta = float(n_expanded) / float(n_reach)
    beta = float(sum(1 for c in reachable if c <= c_star + 1e-12)) / float(n_reach)
    return eta, beta


def build_mapping_atlas_curve(
    raw_fn: Callable[[float], float],
    output_space: OutputSpace,
    *,
    axis: int = 0,
    n: int = 361,
) -> dict[str, NDArray[np.floating]]:
    """Convenience wrapper around :func:`mapping_curve` on ``[0, 2pi)``."""
    u = np.linspace(0.0, 2.0 * np.pi, n, endpoint=False)
    return mapping_curve(raw_fn, output_space, u, axis=axis)


# Re-export for callers that only import plots.
__all__ = [
    "basin_metrics",
    "build_edge_trace",
    "build_mapping_atlas_curve",
    "classify_lattice_edge",
    "input_euclidean_cost",
    "plot_edge_density_differences",
    "plot_edge_microscope",
    "plot_mapping_atlas",
    "plot_search_basin",
    "plot_task_preimages",
    "plot_topology_panels",
    "uniform_edge_cost",
]
