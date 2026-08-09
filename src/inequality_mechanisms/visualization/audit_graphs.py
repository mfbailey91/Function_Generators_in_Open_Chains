"""Q/U/X embeddings and edge-weight fields for V3.6B (V3-624)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from inequality_mechanisms.audits.metrics import LatticeMetricBundle
from inequality_mechanisms.graphs.embedded import EmbeddedPlanningGraph


def _require_matplotlib() -> Any:
    import matplotlib.pyplot as plt

    return plt


def _draw_edges_colored(
    ax: Any,
    xy: np.ndarray,
    edges: Sequence[tuple[int, int, float]],
    *,
    cmap: str = "viridis",
) -> Any:
    import matplotlib.pyplot as plt

    vals = np.asarray([w for _, _, w in edges if np.isfinite(w)], dtype=np.float64)
    norm = None
    if vals.size:
        vmin, vmax = float(np.min(vals)), float(np.max(vals))
        if vmax <= vmin:
            vmax = vmin + 1e-12
        norm = plt.Normalize(vmin=vmin, vmax=vmax)
    sm = None
    for a, b, w in edges:
        color = "0.75"
        if np.isfinite(w) and norm is not None:
            color = plt.get_cmap(cmap)(norm(w))
        ax.plot([xy[a, 0], xy[b, 0]], [xy[a, 1], xy[b, 1]], color=color, linewidth=0.8, zorder=1)
    if norm is not None:
        sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
        sm.set_array([])
    return sm


def write_graph_panels(
    *,
    graph: EmbeddedPlanningGraph,
    robot: Any,
    bundle: LatticeMetricBundle,
    out_dir: Path,
    task_id: str,
    mechanism: str,
    start_q: Sequence[float] | None = None,
    goal_center: Sequence[float] | None = None,
    goal_radius: float | None = None,
    goal_points: Sequence[Sequence[float]] | None = None,
    path_q: Sequence[Sequence[float]] | None = None,
) -> dict[str, Path]:
    """Write Q/U/X embeddings and weight-colored Q panels."""
    plt = _require_matplotlib()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    assets: dict[str, Path] = {}
    q = np.asarray(graph.q_nodes, dtype=np.float64)
    u = np.asarray(graph.u_nodes, dtype=np.float64)
    valid = graph.valid_nodes

    # X embedding via FK.
    tips = np.full((graph.node_count, 2), np.nan, dtype=np.float64)
    for nid in range(graph.node_count):
        if not valid[nid]:
            continue
        from inequality_mechanisms.core.state import PhysicalState

        st = PhysicalState(u=u[nid], q=q[nid], assembly_state={})
        tips[nid] = np.asarray(robot.forward_kinematics(st).position, dtype=np.float64)[:2]

    def _scatter_path(ax: Any, pts: np.ndarray, path: Sequence[Sequence[float]] | None, color: str) -> None:
        ax.scatter(pts[valid, 0], pts[valid, 1], s=6, color="0.6", zorder=2)
        if path:
            arr = np.asarray(path, dtype=np.float64)
            ax.plot(arr[:, 0], arr[:, 1], color=color, linewidth=2.0, zorder=4)
            ax.scatter(arr[0, 0], arr[0, 1], color="green", s=30, zorder=5)
            ax.scatter(arr[-1, 0], arr[-1, 1], color="red", s=30, zorder=5)

    # Embeddings.
    for kind, pts, xlabel, ylabel in (
        ("Q", q, "q1", "q2"),
        ("U", u, "u1", "u2"),
        ("X", tips, "x", "y"),
    ):
        fig, ax = plt.subplots(figsize=(5.5, 5.0), constrained_layout=True)
        for a, b in graph.topology.iter_edges():
            if not (valid[a] and valid[b]):
                continue
            if not (np.isfinite(pts[a]).all() and np.isfinite(pts[b]).all()):
                continue
            ax.plot([pts[a, 0], pts[b, 0]], [pts[a, 1], pts[b, 1]], color="0.8", linewidth=0.5, zorder=1)
        _scatter_path(ax, pts, path_q if kind == "Q" else None, "C0")
        if kind == "Q" and start_q is not None:
            ax.scatter([start_q[0]], [start_q[1]], marker="*", s=80, color="green", zorder=6, label="start")
        if kind == "X" and goal_center is not None and goal_radius is not None:
            circ = plt.Circle((goal_center[0], goal_center[1]), goal_radius, fill=False, color="C3", linestyle="--")
            ax.add_patch(circ)
            if goal_points:
                gp = np.asarray(goal_points, dtype=np.float64)
                ax.scatter(gp[:, 0], gp[:, 1], s=18, color="C3", marker="x", zorder=5, label="candidates")
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_title(f"{task_id}/{mechanism}: {kind} embedding")
        ax.set_aspect("equal", adjustable="datalim")
        path = out_dir / f"{task_id}__{mechanism}__embed_{kind.lower()}.png"
        fig.savefig(path, dpi=120)
        plt.close(fig)
        assets[f"embed_{kind.lower()}"] = path

    # Weight panels on Q layout.
    for key, attr, title in (
        ("w_u", "w_u", "w_U"),
        ("w_q", "w_q", "w_Q"),
        ("w_x", "w_x", "w_X"),
        ("stretch_q_over_u", "stretch_q_over_u", "s_Q/U"),
        ("stretch_u_over_q", "stretch_u_over_q", "s_U/Q"),
    ):
        fig, ax = plt.subplots(figsize=(5.5, 5.0), constrained_layout=True)
        edges = [(e.a, e.b, getattr(e, attr)) for e in bundle.edges]
        sm = _draw_edges_colored(ax, q, edges)
        ax.scatter(q[valid, 0], q[valid, 1], s=6, color="0.5", zorder=2)
        if sm is not None:
            fig.colorbar(sm, ax=ax, fraction=0.046, pad=0.04)
        ax.set_title(f"{task_id}/{mechanism}: {title}")
        ax.set_xlabel("q1")
        ax.set_ylabel("q2")
        ax.set_aspect("equal", adjustable="datalim")
        path = out_dir / f"{task_id}__{mechanism}__{key}.png"
        fig.savefig(path, dpi=120)
        plt.close(fig)
        assets[key] = path

    # Metric field: M_Q condition.
    if bundle.fields:
        fig, ax = plt.subplots(figsize=(5.5, 5.0), constrained_layout=True)
        xs = [f.q[0] for f in bundle.fields]
        ys = [f.q[1] for f in bundle.fields]
        cs = [f.m_q_cond for f in bundle.fields]
        sc = ax.scatter(xs, ys, c=cs, s=12, cmap="magma", zorder=3)
        fig.colorbar(sc, ax=ax, fraction=0.046, pad=0.04)
        ax.set_title(f"{task_id}/{mechanism}: cond(M_Q)")
        ax.set_xlabel("q1")
        ax.set_ylabel("q2")
        ax.set_aspect("equal", adjustable="datalim")
        path = out_dir / f"{task_id}__{mechanism}__field_mq_cond.png"
        fig.savefig(path, dpi=120)
        plt.close(fig)
        assets["field_mq_cond"] = path
    return assets


__all__ = ["write_graph_panels"]
