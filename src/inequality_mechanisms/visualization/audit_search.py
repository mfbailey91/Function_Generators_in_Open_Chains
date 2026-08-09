"""Planner path and exploration panels for V3.6B (V3-625)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from inequality_mechanisms.audits.planar2r_visual import PlannerRunRecord
from inequality_mechanisms.graphs.embedded import EmbeddedPlanningGraph


def _require_matplotlib() -> Any:
    import matplotlib.pyplot as plt

    return plt


def _path_arrays(run: PlannerRunRecord) -> tuple[np.ndarray | None, np.ndarray | None, np.ndarray | None]:
    if not run.trajectory_states:
        return None, None, None
    u = np.asarray([s["u"] for s in run.trajectory_states], dtype=np.float64)
    q = np.asarray([s["q"] for s in run.trajectory_states], dtype=np.float64)
    return u, q, None


def write_search_panels(
    *,
    graph: EmbeddedPlanningGraph,
    robot: Any,
    run: PlannerRunRecord,
    out_dir: Path,
    task_id: str,
    goal_center: Sequence[float] | None = None,
    goal_radius: float | None = None,
) -> dict[str, Path]:
    """Write path overlays and lattice expansion masks for one planner run."""
    plt = _require_matplotlib()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    assets: dict[str, Path] = {}
    mech = run.mechanism
    planner = run.planner
    prefix = f"{task_id}__{mech}__{planner}"
    u_path, q_path, _ = _path_arrays(run)
    q_nodes = np.asarray(graph.q_nodes, dtype=np.float64)
    u_nodes = np.asarray(graph.u_nodes, dtype=np.float64)
    valid = graph.valid_nodes

    # U/Q path panels.
    for kind, nodes, path, xlabel, ylabel in (
        ("Q", q_nodes, q_path, "q1", "q2"),
        ("U", u_nodes, u_path, "u1", "u2"),
    ):
        fig, ax = plt.subplots(figsize=(5.2, 4.8), constrained_layout=True)
        ax.scatter(nodes[valid, 0], nodes[valid, 1], s=4, color="0.75", zorder=1)
        if path is not None and path.size:
            ax.plot(path[:, 0], path[:, 1], color="C0", linewidth=2.0, zorder=3)
            ax.scatter(path[0, 0], path[0, 1], color="green", s=28, zorder=4)
            ax.scatter(path[-1, 0], path[-1, 1], color="red", s=28, zorder=4)
        ax.set_title(f"{task_id}/{mech}/{planner}: {kind} path")
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_aspect("equal", adjustable="datalim")
        path_out = out_dir / f"{prefix}__path_{kind.lower()}.png"
        fig.savefig(path_out, dpi=110)
        plt.close(fig)
        assets[f"path_{kind.lower()}"] = path_out

    # Cartesian tip trail + pose samples.
    if u_path is not None and q_path is not None and q_path.size:
        from inequality_mechanisms.core.state import PhysicalState

        tips = []
        for u_row, q_row in zip(u_path, q_path):
            st = PhysicalState(u=u_row, q=q_row, assembly_state={})
            tips.append(np.asarray(robot.forward_kinematics(st).position, dtype=np.float64)[:2])
        tips_a = np.asarray(tips, dtype=np.float64)
        fig, ax = plt.subplots(figsize=(5.2, 4.8), constrained_layout=True)
        ax.plot(tips_a[:, 0], tips_a[:, 1], color="C0", linewidth=2.0)
        ax.scatter(tips_a[0, 0], tips_a[0, 1], color="green", s=28)
        ax.scatter(tips_a[-1, 0], tips_a[-1, 1], color="red", s=28)
        if goal_center is not None and goal_radius is not None:
            circ = plt.Circle((goal_center[0], goal_center[1]), goal_radius, fill=False, color="C3", linestyle="--")
            ax.add_patch(circ)
        # Sparse pose polylines when planar FK exposes link polyline.
        fk = getattr(robot, "planar_fk", None) or getattr(robot, "kinematic_model", None)
        if fk is not None and hasattr(fk, "link_polyline"):
            idxs = np.linspace(0, len(q_path) - 1, num=min(8, len(q_path)), dtype=int)
            for i in idxs:
                poly = np.asarray(fk.link_polyline(q_path[i]), dtype=np.float64)
                ax.plot(poly[:, 0], poly[:, 1], color="0.4", linewidth=0.8, alpha=0.7)
        ax.set_title(f"{task_id}/{mech}/{planner}: X path + poses")
        ax.set_aspect("equal", adjustable="datalim")
        path_out = out_dir / f"{prefix}__path_x.png"
        fig.savefig(path_out, dpi=110)
        plt.close(fig)
        assets["path_x"] = path_out

    # Expansion mask for lattice planners.
    if run.expanded_node_ids:
        fig, ax = plt.subplots(figsize=(5.2, 4.8), constrained_layout=True)
        ax.scatter(q_nodes[valid, 0], q_nodes[valid, 1], s=4, color="0.85", zorder=1)
        exp = np.asarray(run.expanded_node_ids, dtype=int)
        exp = exp[(exp >= 0) & (exp < graph.node_count)]
        if exp.size:
            order = np.arange(exp.size)
            sc = ax.scatter(
                q_nodes[exp, 0], q_nodes[exp, 1], c=order, s=10, cmap="plasma", zorder=3
            )
            fig.colorbar(sc, ax=ax, fraction=0.046, pad=0.04, label="expansion order")
        if q_path is not None and q_path.size:
            ax.plot(q_path[:, 0], q_path[:, 1], color="cyan", linewidth=1.5, zorder=4)
        ax.set_title(f"{task_id}/{mech}/{planner}: expansion mask")
        ax.set_aspect("equal", adjustable="datalim")
        path_out = out_dir / f"{prefix}__expansion.png"
        fig.savefig(path_out, dpi=110)
        plt.close(fig)
        assets["expansion"] = path_out

    # Roadmap / tree final static trace from events.
    if run.trace_events and planner in ("prm", "rrt_connect"):
        fig, ax = plt.subplots(figsize=(5.2, 4.8), constrained_layout=True)
        ax.scatter(u_nodes[valid, 0], u_nodes[valid, 1], s=3, color="0.9", zorder=0)
        if planner == "prm":
            samples = [
                e["payload"]["u"]
                for e in run.trace_events
                if e.get("event_type") == "sample_accept"
            ]
            if samples:
                s = np.asarray(samples, dtype=np.float64)
                ax.scatter(s[:, 0], s[:, 1], s=8, color="C0", zorder=2, label="samples")
            for e in run.trace_events:
                if e.get("event_type") == "edge_accept":
                    # endpoints not stored as coords; skip edge draw here
                    pass
        else:
            inserts = [
                e for e in run.trace_events if e.get("event_type") == "vertex_insert"
            ]
            by_tree: dict[str, list[np.ndarray]] = {"start": [], "goal": []}
            for e in inserts:
                tree = str(e["payload"].get("tree", "start"))
                by_tree.setdefault(tree, []).append(np.asarray(e["payload"]["u"], dtype=np.float64))
            for tree, pts in by_tree.items():
                if not pts:
                    continue
                arr = np.asarray(pts, dtype=np.float64)
                ax.scatter(arr[:, 0], arr[:, 1], s=8, label=tree, zorder=2)
        if u_path is not None and u_path.size:
            ax.plot(u_path[:, 0], u_path[:, 1], color="k", linewidth=1.8, zorder=4)
        ax.legend(fontsize=8)
        ax.set_title(f"{task_id}/{mech}/{planner}: final trace (U)")
        ax.set_aspect("equal", adjustable="datalim")
        path_out = out_dir / f"{prefix}__final_trace.png"
        fig.savefig(path_out, dpi=110)
        plt.close(fig)
        assets["final_trace"] = path_out

    # Unavailable marker panel for OMPL when skipped.
    if run.skipped == "ompl_unavailable":
        fig, ax = plt.subplots(figsize=(5.2, 2.2), constrained_layout=True)
        ax.axis("off")
        ax.text(0.5, 0.5, "OMPL unavailable", ha="center", va="center", fontsize=14)
        path_out = out_dir / f"{prefix}__unavailable.png"
        fig.savefig(path_out, dpi=110)
        plt.close(fig)
        assets["unavailable"] = path_out
    return assets


def write_direct_comparison(
    *,
    runs: Mapping[str, PlannerRunRecord],
    out_dir: Path,
    task_id: str,
) -> Path:
    """Write a compact direct-planner U/Q/X length bar chart for one trial."""
    plt = _require_matplotlib()
    out_dir = Path(out_dir)
    fig, ax = plt.subplots(figsize=(6.5, 3.8), constrained_layout=True)
    labels = []
    lu, lq, lx = [], [], []
    for key, run in runs.items():
        labels.append(key)
        lu.append(run.path_length_u if run.path_length_u is not None else 0.0)
        lq.append(run.path_length_q if run.path_length_q is not None else 0.0)
        lx.append(run.path_length_x if run.path_length_x is not None else 0.0)
    x = np.arange(len(labels))
    w = 0.25
    ax.bar(x - w, lu, width=w, label="L_U")
    ax.bar(x, lq, width=w, label="L_Q")
    ax.bar(x + w, lx, width=w, label="L_X")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right", fontsize=8)
    ax.legend(fontsize=8)
    ax.set_title(f"{task_id}: path length components")
    path = out_dir / f"{task_id}__shared__path_lengths.png"
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path


__all__ = ["write_direct_comparison", "write_search_panels"]
