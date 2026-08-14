"""Planner path and exploration panels for V3.6B / V3.6C (V3-625, V3-635)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from inequality_mechanisms.audits.planar2r_visual import PlannerRunRecord
from inequality_mechanisms.core.local_motion import LocalMotionModel
from inequality_mechanisms.core.state import PhysicalState
from inequality_mechanisms.graphs.embedded import EmbeddedPlanningGraph
from inequality_mechanisms.visualization.audit_trace_geometry import (
    extract_trace_geometry,
    final_path_samples_from_cte,
    reconstruct_edge_samples,
)


def _require_matplotlib() -> Any:
    import matplotlib.pyplot as plt

    return plt


def _path_arrays(run: PlannerRunRecord) -> tuple[np.ndarray | None, np.ndarray | None, np.ndarray | None]:
    if not run.trajectory_states:
        return None, None, None
    u = np.asarray([s["u"] for s in run.trajectory_states], dtype=np.float64)
    q = np.asarray([s["q"] for s in run.trajectory_states], dtype=np.float64)
    return u, q, None


def _draw_polyline(ax: Any, samples: np.ndarray | None, *, color: str, lw: float, z: int, alpha: float = 1.0) -> None:
    if samples is None or samples.size == 0 or samples.shape[0] < 2:
        return
    ax.plot(
        samples[:, 0],
        samples[:, 1],
        color=color,
        linewidth=lw,
        alpha=alpha,
        zorder=z,
    )


def _draw_native_trace_panel(
    ax: Any,
    *,
    space: str,
    vertices_xy: list[np.ndarray],
    reconstructed: Sequence[Any],
    path_xy: np.ndarray | None,
    expand_xy: list[np.ndarray],
    title: str,
    xlabel: str,
    ylabel: str,
    goal_center: Sequence[float] | None = None,
    goal_radius: float | None = None,
) -> None:
    if vertices_xy:
        arr = np.asarray(vertices_xy, dtype=np.float64)
        ax.scatter(arr[:, 0], arr[:, 1], s=8, color="C0", zorder=2, label="vertices")
    edge_color = "0.55" if space != "X" else "0.45"
    for rec in reconstructed:
        if not rec.drawn:
            continue
        if space == "U":
            samples = rec.sample_u
        elif space == "Q":
            samples = rec.sample_q
        else:
            samples = rec.sample_x
        _draw_polyline(ax, samples, color=edge_color, lw=0.9, z=1, alpha=0.85)
    if expand_xy:
        earr = np.asarray(expand_xy, dtype=np.float64)
        ax.scatter(
            earr[:, 0],
            earr[:, 1],
            s=12,
            c=np.arange(earr.shape[0]),
            cmap="plasma",
            zorder=3,
            label="expand",
        )
    if path_xy is not None and path_xy.size:
        ax.plot(path_xy[:, 0], path_xy[:, 1], color="k", linewidth=1.8, zorder=4, label="path")
        ax.scatter(path_xy[0, 0], path_xy[0, 1], color="green", s=28, zorder=5)
        ax.scatter(path_xy[-1, 0], path_xy[-1, 1], color="red", s=28, zorder=5)
    if space == "X" and goal_center is not None and goal_radius is not None:
        import matplotlib.pyplot as plt

        circ = plt.Circle(
            (goal_center[0], goal_center[1]),
            goal_radius,
            fill=False,
            color="C3",
            linestyle="--",
        )
        ax.add_patch(circ)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_aspect("equal", adjustable="datalim")
    ax.legend(fontsize=7, loc="best")


def write_search_panels(
    *,
    graph: EmbeddedPlanningGraph,
    robot: Any,
    run: PlannerRunRecord,
    out_dir: Path,
    task_id: str,
    goal_center: Sequence[float] | None = None,
    goal_radius: float | None = None,
    connector: LocalMotionModel | None = None,
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

    # Native PRM/RRT synchronized U/Q/X traces (connector-reconstructed edges).
    if run.trace_events and planner in ("prm", "rrt_connect") and connector is not None:
        geom = extract_trace_geometry(run.trace_events, planner=planner)
        reconstructed = reconstruct_edge_samples(
            geom.edges, connector=connector, robot=robot
        )
        by_key = {v.key: v for v in geom.vertices}
        cte_u, cte_q, cte_x = final_path_samples_from_cte(run.planner_metrics)
        path_by_space = {
            "U": cte_u,
            "Q": cte_q,
            "X": cte_x,
        }
        # Prefer CTE; otherwise omit path polyline (no silent waypoint chords).
        expand_by_space: dict[str, list[np.ndarray]] = {"U": [], "Q": [], "X": []}
        for key in geom.expansion_keys:
            v = by_key.get(key)
            if v is None:
                continue
            expand_by_space["U"].append(v.u[:2])
            expand_by_space["Q"].append(v.q[:2])
            tip = np.asarray(
                robot.forward_kinematics(
                    PhysicalState(u=v.u, q=v.q, assembly_state={})
                ).position,
                dtype=np.float64,
            )[:2]
            expand_by_space["X"].append(tip)

        verts_u = [v.u[:2] for v in geom.vertices]
        verts_q = [v.q[:2] for v in geom.vertices]
        verts_x = [
            np.asarray(
                robot.forward_kinematics(
                    PhysicalState(u=v.u, q=v.q, assembly_state={})
                ).position,
                dtype=np.float64,
            )[:2]
            for v in geom.vertices
        ]
        verts_by_space = {"U": verts_u, "Q": verts_q, "X": verts_x}
        labels = {
            "U": ("u1", "u2"),
            "Q": ("q1", "q2"),
            "X": ("x", "y"),
        }
        for space in ("U", "Q", "X"):
            fig, ax = plt.subplots(figsize=(5.2, 4.8), constrained_layout=True)
            xlabel, ylabel = labels[space]
            path_xy = path_by_space[space]
            if path_xy is not None and path_xy.shape[1] > 2:
                path_xy = path_xy[:, :2]
            _draw_native_trace_panel(
                ax,
                space=space,
                vertices_xy=verts_by_space[space],
                reconstructed=reconstructed,
                path_xy=path_xy,
                expand_xy=expand_by_space[space],
                title=f"{task_id}/{mech}/{planner}: final trace ({space})",
                xlabel=xlabel,
                ylabel=ylabel,
                goal_center=goal_center if space == "X" else None,
                goal_radius=goal_radius if space == "X" else None,
            )
            path_out = out_dir / f"{prefix}__final_trace_{space.lower()}.png"
            fig.savefig(path_out, dpi=110)
            plt.close(fig)
            assets[f"final_trace_{space.lower()}"] = path_out
        # Backward-compatible key used by V3.6B HTML templates.
        assets["final_trace"] = assets["final_trace_u"]
    elif run.trace_events and planner in ("prm", "rrt_connect"):
        # No connector: fail closed on edges; still emit empty-ish U panel for diagnostics.
        fig, ax = plt.subplots(figsize=(5.2, 4.8), constrained_layout=True)
        ax.text(
            0.5,
            0.5,
            "connector required for native U/Q/X edges",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
        ax.set_title(f"{task_id}/{mech}/{planner}: final trace (unavailable)")
        path_out = out_dir / f"{prefix}__final_trace_u.png"
        fig.savefig(path_out, dpi=110)
        plt.close(fig)
        assets["final_trace_u"] = path_out
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
