"""Path and lattice figure helpers for input / output / Cartesian views.

Search remains on input-space nodes. These plots only visualize an already
computed path and cost field for verification against the paper figures.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from inequality_mechanisms.graphs.validation import ConstrainedInputGraph
from inequality_mechanisms.kinematics.planar_2r import Planar2R
from inequality_mechanisms.search.cost_to_go import reverse_dijkstra


def _require_matplotlib() -> Any:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "matplotlib is required for path plots; "
            "install with pip install matplotlib"
        ) from exc
    return plt


def cost_from_start(
    graph: ConstrainedInputGraph,
    start: int,
) -> Mapping[int, float]:
    """Return optimal cost from ``start`` to every reachable node.

    Uses reverse Dijkstra with Version 1 symmetric output Euclidean costs so
    ``C*(n, start) = C*(start, n)``.
    """
    return reverse_dijkstra(graph, start).costs


def path_inputs(
    graph: ConstrainedInputGraph,
    path: Sequence[int],
) -> NDArray[np.floating]:
    """Stack input coordinates along a flat-id path, shape ``(len(path), 2)``."""
    coords = np.empty((len(path), 2), dtype=np.float64)
    for i, node_id in enumerate(path):
        i0, i1 = graph.grid.indices_from_id(int(node_id))
        coords[i] = graph.grid.coordinates(i0, i1)
    return coords


def path_outputs(
    graph: ConstrainedInputGraph,
    path: Sequence[int],
) -> NDArray[np.floating]:
    """Stack canonicalized output coordinates along a path, shape ``(L, 2)``."""
    out = np.empty((len(path), 2), dtype=np.float64)
    for i, node_id in enumerate(path):
        i0, i1 = graph.grid.indices_from_id(int(node_id))
        u = graph.grid.coordinates(i0, i1)
        out[i] = graph.output(u)
    return out


def _cost_grid(
    graph: ConstrainedInputGraph,
    costs: Mapping[int, float],
) -> NDArray[np.floating]:
    """Reshape cost-from-start into a ``(n0, n1)`` array (NaN if unknown)."""
    n0, n1 = graph.grid.shape
    field = np.full((n0, n1), np.nan, dtype=np.float64)
    for node_id, cost in costs.items():
        if not np.isfinite(cost):
            continue
        i0, i1 = graph.grid.indices_from_id(int(node_id))
        field[i0, i1] = float(cost)
    return field


def _axis_edges(lo: float, hi: float, n: int) -> NDArray[np.floating]:
    """Cell edges for ``n`` samples on ``[lo, hi)`` with spacing ``(hi-lo)/n``."""
    step = (hi - lo) / n
    return lo + np.arange(n + 1, dtype=np.float64) * step


def plot_input_path(
    graph: ConstrainedInputGraph,
    path: Sequence[int],
    path_out: Path | str,
    *,
    costs: Mapping[int, float] | None = None,
    start: int | None = None,
    goal: int | None = None,
    title: str | None = None,
) -> Path:
    """Write a heatmap of cost-from-start in input space with the path overlaid.

    At fine lattices (e.g. 64×64) per-cell numeric labels are omitted.
    """
    plt = _require_matplotlib()
    out = Path(path_out)
    out.parent.mkdir(parents=True, exist_ok=True)

    if start is None:
        if not path:
            raise ValueError("path is empty and start was not provided")
        start = int(path[0])
    if goal is None and path:
        goal = int(path[-1])
    if costs is None:
        costs = cost_from_start(graph, start)

    field = _cost_grid(graph, costs)
    (u0_lo, u0_hi), (u1_lo, u1_hi) = graph.grid.ranges
    n0, n1 = graph.grid.shape
    u0_edges = _axis_edges(u0_lo, u0_hi, n0)
    u1_edges = _axis_edges(u1_lo, u1_hi, n1)

    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    mesh = ax.pcolormesh(
        u0_edges,
        u1_edges,
        field.T,
        shading="flat",
        cmap="viridis",
    )
    cbar = fig.colorbar(mesh, ax=ax)
    cbar.set_label("4-connected cost from start")

    if path:
        u_path = path_inputs(graph, path)
        ax.plot(u_path[:, 0], u_path[:, 1], color="C0", linewidth=2.0, label="A* path")
    i0_s, i1_s = graph.grid.indices_from_id(start)
    u_start = graph.grid.coordinates(i0_s, i1_s)
    ax.scatter([u_start[0]], [u_start[1]], color="C0", s=60, zorder=5, label="start")
    if goal is not None:
        i0_g, i1_g = graph.grid.indices_from_id(goal)
        u_goal = graph.grid.coordinates(i0_g, i1_g)
        ax.scatter(
            [u_goal[0]], [u_goal[1]], color="C1", s=60, zorder=5, label="goal"
        )

    ax.set_xlabel(r"$u_1$")
    ax.set_ylabel(r"$u_2$")
    # Pin to the full shared lattice so gearbox / four-bar panels share
    # the same U extent (valid subsets differ under shared Q limits).
    ax.set_xlim(u0_lo, u0_hi)
    ax.set_ylim(u1_lo, u1_hi)
    ax.set_aspect("equal", adjustable="box")
    ax.set_title(title or "Input-space path")
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def plot_output_path(
    graph: ConstrainedInputGraph,
    path: Sequence[int],
    path_out: Path | str,
    *,
    costs: Mapping[int, float] | None = None,
    start: int | None = None,
    goal: int | None = None,
    title: str | None = None,
) -> Path:
    """Write cost-from-start carried into output joint space ``Q``.

    Valid reachable nodes are drawn as a scatter colored by input-space path
    cost; the discrete path is overlaid in ``q``.
    """
    plt = _require_matplotlib()
    out = Path(path_out)
    out.parent.mkdir(parents=True, exist_ok=True)

    if start is None:
        if not path:
            raise ValueError("path is empty and start was not provided")
        start = int(path[0])
    if goal is None and path:
        goal = int(path[-1])
    if costs is None:
        costs = cost_from_start(graph, start)

    mech = graph.mechanism
    qs: list[list[float]] = []
    cs: list[float] = []
    for node_id, cost in costs.items():
        if not np.isfinite(cost):
            continue
        i0, i1 = graph.grid.indices_from_id(int(node_id))
        u = graph.grid.coordinates(i0, i1)
        q = graph.output(u)
        qs.append([float(q[0]), float(q[1])])
        cs.append(float(cost))
    q_arr = np.asarray(qs, dtype=np.float64) if qs else np.empty((0, 2))
    c_arr = np.asarray(cs, dtype=np.float64)

    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    if len(q_arr):
        sc = ax.scatter(
            q_arr[:, 0],
            q_arr[:, 1],
            c=c_arr,
            cmap="viridis",
            s=12,
            linewidths=0,
        )
        cbar = fig.colorbar(sc, ax=ax)
        cbar.set_label("input-space cost carried to output")

    if path:
        q_path = path_outputs(graph, path)
        ax.plot(q_path[:, 0], q_path[:, 1], color="C0", linewidth=2.0, label="A* path")
    i0_s, i1_s = graph.grid.indices_from_id(start)
    q_start = graph.output(graph.grid.coordinates(i0_s, i1_s))
    ax.scatter([q_start[0]], [q_start[1]], color="C0", s=60, zorder=5, label="start")
    if goal is not None:
        i0_g, i1_g = graph.grid.indices_from_id(goal)
        q_goal = graph.output(graph.grid.coordinates(i0_g, i1_g))
        ax.scatter(
            [q_goal[0]], [q_goal[1]], color="C1", s=60, zorder=5, label="goal"
        )

    ax.set_xlabel(r"$q_1$ [rad]")
    ax.set_ylabel(r"$q_2$ [rad]")
    ax.set_aspect("equal", adjustable="box")
    ax.set_title(title or "Mapped path in Q")
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def _node_u_q(
    graph: ConstrainedInputGraph, node_id: int
) -> tuple[NDArray[np.floating], NDArray[np.floating]]:
    """Return ``(u, q)`` coordinates for a flat node id."""
    i0, i1 = graph.grid.indices_from_id(int(node_id))
    u = np.asarray(graph.grid.coordinates(i0, i1), dtype=np.float64)
    q = np.asarray(graph.output(u), dtype=np.float64)
    return u, q


def lattice_edge_weights(
    graph: ConstrainedInputGraph,
) -> tuple[list[tuple[int, int]], NDArray[np.floating], NDArray[np.floating]]:
    """Return undirected edges with U and induced Q Euclidean weights.

    Parameters
    ----------
    graph :
        Validated Version 1 input-space planning graph.

    Returns
    -------
    edges :
        Undirected pairs ``(a, b)`` with ``a < b``.
    u_weights :
        ``‖u_b - u_a‖₂`` for each edge.
    q_weights :
        ``‖q(u_b) - q(u_a)‖₂`` for each edge (mechanism-induced on the
        shared adjacency).
    """
    edges: list[tuple[int, int]] = []
    u_vals: list[float] = []
    q_vals: list[float] = []
    for a, b in graph.iter_edges():
        u_a, q_a = _node_u_q(graph, a)
        u_b, q_b = _node_u_q(graph, b)
        edges.append((int(a), int(b)))
        u_vals.append(float(np.linalg.norm(u_b - u_a)))
        q_vals.append(float(np.linalg.norm(q_b - q_a)))
    return (
        edges,
        np.asarray(u_vals, dtype=np.float64),
        np.asarray(q_vals, dtype=np.float64),
    )


def _draw_weighted_edges(
    ax: Any,
    segments: NDArray[np.floating],
    weights: NDArray[np.floating],
    *,
    cmap: str = "viridis",
    linewidth: float = 1.4,
) -> Any:
    """Draw a ``LineCollection`` colored by ``weights``; return the collection."""
    from matplotlib.collections import LineCollection

    if segments.size == 0:
        return None
    lc = LineCollection(
        segments,
        array=weights,
        cmap=cmap,
        linewidths=linewidth,
        zorder=2,
    )
    ax.add_collection(lc)
    return lc


def _overlay_path_markers(
    ax: Any,
    coords: NDArray[np.floating],
    *,
    start: NDArray[np.floating] | None,
    goal: NDArray[np.floating] | None,
) -> None:
    """Overlay a polyline path plus start/goal markers."""
    if coords.shape[0] >= 2:
        ax.plot(
            coords[:, 0],
            coords[:, 1],
            color="C3",
            linewidth=2.2,
            zorder=5,
            label="path",
        )
    elif coords.shape[0] == 1:
        ax.scatter(
            [coords[0, 0]],
            [coords[0, 1]],
            color="C3",
            s=40,
            zorder=5,
            label="path",
        )
    if start is not None:
        ax.scatter(
            [start[0]], [start[1]], color="C0", s=70, zorder=6, label="start"
        )
    if goal is not None:
        ax.scatter(
            [goal[0]], [goal[1]], color="C1", s=70, zorder=6, label="goal"
        )


def plot_input_graph_weights(
    graph: ConstrainedInputGraph,
    path: Sequence[int],
    path_out: Path | str,
    *,
    start: int | None = None,
    goal: int | None = None,
    title: str | None = None,
) -> Path:
    """Write U as a 4-connected lattice with edges colored by U weight.

    Edge weight is input Euclidean distance ``‖Δu‖₂``. The selected path and
    start/goal markers are overlaid.
    """
    plt = _require_matplotlib()
    out = Path(path_out)
    out.parent.mkdir(parents=True, exist_ok=True)

    if start is None and path:
        start = int(path[0])
    if goal is None and path:
        goal = int(path[-1])

    edges, u_weights, _q_weights = lattice_edge_weights(graph)
    segments: list[list[list[float]]] = []
    for a, b in edges:
        u_a, _ = _node_u_q(graph, a)
        u_b, _ = _node_u_q(graph, b)
        segments.append([[float(u_a[0]), float(u_a[1])], [float(u_b[0]), float(u_b[1])]])
    seg_arr = np.asarray(segments, dtype=np.float64) if segments else np.empty((0, 2, 2))

    valid_u = []
    for node in graph.iter_valid_nodes():
        valid_u.append(node.coordinates)
    valid_u_arr = (
        np.asarray(valid_u, dtype=np.float64) if valid_u else np.empty((0, 2))
    )

    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    if valid_u_arr.size:
        ax.scatter(
            valid_u_arr[:, 0],
            valid_u_arr[:, 1],
            s=10,
            color="0.55",
            linewidths=0,
            zorder=3,
            label="valid nodes",
        )
    lc = _draw_weighted_edges(ax, seg_arr, u_weights)
    if lc is not None:
        cbar = fig.colorbar(lc, ax=ax)
        cbar.set_label(r"U edge weight $\|\Delta u\|_2$")

    path_coords = path_inputs(graph, path) if path else np.empty((0, 2))
    start_xy = None
    goal_xy = None
    if start is not None:
        start_xy, _ = _node_u_q(graph, start)
    if goal is not None:
        goal_xy, _ = _node_u_q(graph, goal)
    _overlay_path_markers(ax, path_coords, start=start_xy, goal=goal_xy)

    (u0_lo, u0_hi), (u1_lo, u1_hi) = graph.grid.ranges
    ax.set_xlabel(r"$u_1$")
    ax.set_ylabel(r"$u_2$")
    ax.set_xlim(u0_lo, u0_hi)
    ax.set_ylim(u1_lo, u1_hi)
    ax.set_aspect("equal", adjustable="box")
    ax.set_title(title or "U connected graph (edge weights)")
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def plot_output_graph_weights(
    graph: ConstrainedInputGraph,
    path: Sequence[int],
    path_out: Path | str,
    *,
    start: int | None = None,
    goal: int | None = None,
    title: str | None = None,
) -> Path:
    r"""Write a 1×2 Q lattice: left edges by \(w_Q\), right by induced \(w_U\).

    Both panels share mapped Q coordinates and the same adjacency as the
    input graph. Left color encodes output Euclidean edge weight; right
    color encodes the induced actuator (U) weight on that edge.
    """
    plt = _require_matplotlib()
    out = Path(path_out)
    out.parent.mkdir(parents=True, exist_ok=True)

    if start is None and path:
        start = int(path[0])
    if goal is None and path:
        goal = int(path[-1])

    edges, u_weights, q_weights = lattice_edge_weights(graph)
    segments: list[list[list[float]]] = []
    for a, b in edges:
        _, q_a = _node_u_q(graph, a)
        _, q_b = _node_u_q(graph, b)
        segments.append([[float(q_a[0]), float(q_a[1])], [float(q_b[0]), float(q_b[1])]])
    seg_arr = np.asarray(segments, dtype=np.float64) if segments else np.empty((0, 2, 2))

    valid_q = []
    for node in graph.iter_valid_nodes():
        valid_q.append(graph.output(node.coordinates))
    valid_q_arr = (
        np.asarray(valid_q, dtype=np.float64) if valid_q else np.empty((0, 2))
    )

    path_coords = path_outputs(graph, path) if path else np.empty((0, 2))
    start_xy = None
    goal_xy = None
    if start is not None:
        _, start_xy = _node_u_q(graph, start)
    if goal is not None:
        _, goal_xy = _node_u_q(graph, goal)

    fig, axes = plt.subplots(1, 2, figsize=(11.0, 5.2), sharex=True, sharey=True)
    panels = (
        (axes[0], q_weights, r"$w_Q=\|\Delta q\|_2$", "Q edge weights"),
        (axes[1], u_weights, r"induced $w_U=\|\Delta u\|_2$", "Induced U edge weights"),
    )
    for ax, weights, cbar_label, panel_title in panels:
        if valid_q_arr.size:
            ax.scatter(
                valid_q_arr[:, 0],
                valid_q_arr[:, 1],
                s=10,
                color="0.55",
                linewidths=0,
                zorder=3,
            )
        lc = _draw_weighted_edges(ax, seg_arr, weights)
        if lc is not None:
            cbar = fig.colorbar(lc, ax=ax, fraction=0.046, pad=0.04)
            cbar.set_label(cbar_label)
        _overlay_path_markers(ax, path_coords, start=start_xy, goal=goal_xy)
        ax.set_xlabel(r"$q_1$ [rad]")
        ax.set_ylabel(r"$q_2$ [rad]")
        ax.set_aspect("equal", adjustable="box")
        ax.set_title(panel_title)
        ax.legend(loc="best", fontsize=7)

    fig.suptitle(title or "Q connected graph with Q and induced U weights", fontsize=11)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def axis_transmission_curve(
    graph: ConstrainedInputGraph,
    axis: int,
    *,
    n_samples: int = 201,
) -> tuple[NDArray[np.floating], NDArray[np.floating], NDArray[np.bool_]]:
    """Sweep one input axis and return ``(u_i, q_i, valid_mask)``.

    Other axes are held at the midpoint of their grid ranges. ``q_i`` is
    taken from ``graph.output(u)`` so the curve matches the mapping search
    consumes. ``valid_mask`` is ``True`` where the mechanism assembles and
    the canonicalized output lies in the shared chart.
    """
    dim = len(graph.grid.ranges)
    if axis < 0 or axis >= dim:
        raise ValueError(f"axis {axis} out of range for dim {dim}")
    if n_samples < 2:
        raise ValueError(f"n_samples must be >= 2, got {n_samples}")

    mid = np.asarray(
        [0.5 * (lo + hi) for lo, hi in graph.grid.ranges], dtype=np.float64
    )
    lo_i, hi_i = graph.grid.ranges[axis]
    u_axis = np.linspace(float(lo_i), float(hi_i), int(n_samples), dtype=np.float64)
    q_axis = np.full(u_axis.shape[0], np.nan, dtype=np.float64)
    valid = np.zeros(u_axis.shape[0], dtype=np.bool_)
    for k, u_i in enumerate(u_axis):
        u = mid.copy()
        u[axis] = float(u_i)
        try:
            if not graph.mechanism.valid_input(u):
                continue
            q = np.asarray(graph.output(u), dtype=np.float64)
            if not np.all(np.isfinite(q)):
                continue
            q_axis[k] = float(q[axis])
            valid[k] = True
        except Exception:  # pragma: no cover — defensive for singular maps
            continue
    return u_axis, q_axis, valid


def plot_axis_transmission(
    labeled_graphs: Mapping[str, ConstrainedInputGraph],
    path_out: Path | str,
    *,
    title: str | None = None,
    n_samples: int = 201,
) -> Path:
    """Write per-axis ``q_i(u_i)`` curves for one or more mechanisms.

    Parameters
    ----------
    labeled_graphs :
        Ordered mapping of legend label to ``ConstrainedInputGraph``. All
        graphs must share the same input dimension.
    path_out :
        Destination PNG path.
    title :
        Optional figure super-title.
    n_samples :
        Sweep samples per axis.
    """
    plt = _require_matplotlib()
    out = Path(path_out)
    out.parent.mkdir(parents=True, exist_ok=True)

    if not labeled_graphs:
        raise ValueError("labeled_graphs must be non-empty")
    items = list(labeled_graphs.items())
    dims = []
    for _label, graph in items:
        dim = len(graph.grid.ranges)
        dims.append(dim)
    if len(set(dims)) != 1:
        raise ValueError(f"all graphs must share input dim, got {dims}")
    dim = dims[0]

    fig, axes = plt.subplots(1, dim, figsize=(5.0 * dim, 4.2), squeeze=False)
    for axis in range(dim):
        ax = axes[0, axis]
        for idx, (label, graph) in enumerate(items):
            u_axis, q_axis, valid = axis_transmission_curve(
                graph, axis, n_samples=n_samples
            )
            color = f"C{idx % 10}"
            if np.any(valid):
                ax.plot(
                    u_axis[valid],
                    q_axis[valid],
                    color=color,
                    linewidth=2.0,
                    label=label,
                )
                if idx == 0:
                    u_valid = u_axis[valid]
                    ax.axvspan(
                        float(u_valid.min()),
                        float(u_valid.max()),
                        color="0.85",
                        alpha=0.35,
                        zorder=0,
                        label="valid u extent",
                    )
        ax.set_xlabel(rf"$u_{{{axis + 1}}}$")
        ax.set_ylabel(rf"$q_{{{axis + 1}}}$")
        ax.set_title(rf"axis {axis + 1}: $q(u)$")
        ax.grid(True, alpha=0.35)
        ax.legend(loc="best", fontsize=8)

    fig.suptitle(title or "Axis transmission maps $q(u)$", fontsize=11)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def plot_cartesian_path(
    q_path: ArrayLike,
    path_out: Path | str,
    *,
    plant: Planar2R | None = None,
    title: str | None = None,
    n_pose_samples: int = 12,
) -> Path:
    """Write planar 2R poses and end-effector path for a joint trajectory.

    Parameters
    ----------
    q_path :
        Joint samples along the path, shape ``(T, 2)``.
    path_out :
        Destination PNG path.
    plant :
        Planar 2R kinematics; defaults to unit link lengths.
    title :
        Optional figure title.
    n_pose_samples :
        Maximum number of intermediate link polylines to draw (start and
        goal are always included when ``T >= 2``).
    """
    plt = _require_matplotlib()
    out = Path(path_out)
    out.parent.mkdir(parents=True, exist_ok=True)

    q = np.asarray(q_path, dtype=np.float64)
    if q.ndim != 2 or q.shape[1] != 2:
        raise ValueError(f"q_path must have shape (T, 2), got {q.shape}")
    if q.shape[0] < 1:
        raise ValueError("q_path must contain at least one sample")
    if not np.all(np.isfinite(q)):
        raise ValueError("q_path must contain only finite values")
    if n_pose_samples < 2:
        raise ValueError(f"n_pose_samples must be >= 2, got {n_pose_samples}")

    arm = plant if plant is not None else Planar2R()
    tips = np.asarray([arm.forward(qi) for qi in q], dtype=np.float64)

    fig, ax = plt.subplots(figsize=(6.0, 6.0))
    ax.plot(
        tips[:, 0],
        tips[:, 1],
        color="C0",
        linewidth=2.0,
        label="end-effector path",
    )

    t = q.shape[0]
    if t == 1:
        indices = [0]
    else:
        n_draw = min(n_pose_samples, t)
        indices = sorted(set(np.linspace(0, t - 1, n_draw, dtype=int).tolist()))

    for idx in indices:
        poly = arm.link_polyline(q[idx])
        if idx == 0:
            ax.plot(
                poly[:, 0],
                poly[:, 1],
                "-o",
                color="C0",
                linewidth=2.5,
                markersize=5,
                label="start pose",
                zorder=4,
            )
        elif idx == t - 1:
            ax.plot(
                poly[:, 0],
                poly[:, 1],
                "-o",
                color="C1",
                linewidth=2.5,
                markersize=5,
                label="goal pose",
                zorder=4,
            )
        else:
            ax.plot(
                poly[:, 0],
                poly[:, 1],
                "-",
                color="0.55",
                alpha=0.45,
                linewidth=1.0,
                zorder=2,
            )

    reach = arm.L1 + arm.L2
    ax.set_xlim(-reach * 1.15, reach * 1.15)
    ax.set_ylim(-reach * 1.15, reach * 1.15)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.35)
    ax.set_xlabel(r"$x$")
    ax.set_ylabel(r"$y$")
    ax.set_title(title or "Cartesian poses")
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out
