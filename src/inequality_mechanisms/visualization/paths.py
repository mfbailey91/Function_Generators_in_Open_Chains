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
