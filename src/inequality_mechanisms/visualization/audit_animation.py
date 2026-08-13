"""Animations and print contact sheets for V3.6B / V3.6C (V3-626, V3-635)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from inequality_mechanisms.audits.planar2r_visual import PlannerRunRecord
from inequality_mechanisms.core.local_motion import LocalMotionModel
from inequality_mechanisms.core.state import PhysicalState
from inequality_mechanisms.graphs.embedded import EmbeddedPlanningGraph
from inequality_mechanisms.visualization.audit_trace_geometry import (
    extract_prm_geometry,
    extract_rrt_geometry,
    growth_events,
    reconstruct_edge_samples,
)


def _require_matplotlib() -> Any:
    import matplotlib.pyplot as plt

    return plt


def _fraction_index(n: int, frac: float) -> int:
    if n <= 0:
        return 0
    return min(n, max(0, int(round(frac * n))))


def _draw_expansion_panel(
    ax: Any,
    graph: EmbeddedPlanningGraph,
    expanded: Sequence[int],
    upto: int,
    *,
    title: str,
) -> None:
    q = np.asarray(graph.q_nodes, dtype=np.float64)
    valid = graph.valid_nodes
    ax.scatter(q[valid, 0], q[valid, 1], s=3, color="0.85", zorder=1)
    exp = np.asarray(list(expanded)[:upto], dtype=int)
    exp = exp[(exp >= 0) & (exp < graph.node_count)]
    if exp.size:
        ax.scatter(q[exp, 0], q[exp, 1], s=8, c=np.arange(exp.size), cmap="plasma", zorder=3)
    ax.set_title(title, fontsize=9)
    ax.set_aspect("equal", adjustable="datalim")
    ax.set_xticks([])
    ax.set_yticks([])


def write_lattice_combined_animation(
    *,
    task_id: str,
    graphs: Mapping[str, EmbeddedPlanningGraph],
    runs: Mapping[tuple[str, str], PlannerRunRecord],
    out_dir: Path,
    fractions: Sequence[float] = (0.0, 0.25, 0.5, 0.75, 1.0),
    n_frames: int = 11,
) -> dict[str, Path]:
    """Write combined 4-panel lattice expansion GIF + contact sheet."""
    plt = _require_matplotlib()
    from matplotlib import animation

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    panels = [
        ("fourbar", "lattice_dijkstra"),
        ("gearbox", "lattice_dijkstra"),
        ("fourbar", "lattice_astar"),
        ("gearbox", "lattice_astar"),
    ]
    expansions = {
        key: list(runs[key].expanded_node_ids) if key in runs else []
        for key in panels
    }
    max_n = max((len(v) for v in expansions.values()), default=0)
    fig, axes = plt.subplots(2, 2, figsize=(8.0, 7.5), constrained_layout=True)
    axes_flat = axes.ravel()

    def _update(frame_i: int) -> Any:
        frac = frame_i / max(n_frames - 1, 1)
        for ax, key in zip(axes_flat, panels):
            ax.clear()
            mech, planner = key
            exp = expansions[key]
            upto = _fraction_index(len(exp), frac) if max_n == 0 else _fraction_index(max_n, frac)
            # Use each panel's own length when shorter.
            upto = min(upto, len(exp))
            _draw_expansion_panel(
                ax,
                graphs[mech],
                exp,
                upto,
                title=f"{mech}/{planner} ({upto}/{len(exp)})",
            )
        fig.suptitle(f"{task_id}: lattice expansion {frac*100:.0f}%")
        return axes_flat

    anim = animation.FuncAnimation(fig, _update, frames=n_frames, interval=120)
    gif_path = out_dir / f"{task_id}__lattice_combined__anim.gif"
    try:
        anim.save(gif_path, writer="pillow", fps=8)
    finally:
        plt.close(fig)

    # Contact sheet.
    fig, axes = plt.subplots(len(fractions), 4, figsize=(10.0, 2.2 * len(fractions)), constrained_layout=True)
    if len(fractions) == 1:
        axes = np.asarray([axes])
    for row, frac in enumerate(fractions):
        for col, key in enumerate(panels):
            ax = axes[row, col]
            mech, planner = key
            exp = expansions[key]
            upto = min(_fraction_index(len(exp), frac), len(exp))
            _draw_expansion_panel(
                ax,
                graphs[mech],
                exp,
                upto,
                title=f"{mech[0]}/{planner.split('_')[1]} @{frac*100:.0f}%",
            )
    sheet = out_dir / f"{task_id}__lattice_combined__contact.png"
    fig.savefig(sheet, dpi=110)
    plt.close(fig)
    return {"anim": gif_path, "contact": sheet}


def _vertex_xy(robot: Any, geom: Any) -> dict[str, list[np.ndarray]]:
    out: dict[str, list[np.ndarray]] = {"U": [], "Q": [], "X": []}
    for v in geom.vertices:
        out["U"].append(v.u[:2])
        out["Q"].append(v.q[:2])
        tip = np.asarray(
            robot.forward_kinematics(
                PhysicalState(u=v.u, q=v.q, assembly_state={})
            ).position,
            dtype=np.float64,
        )[:2]
        out["X"].append(tip)
    return out


def _render_growth_space(
    ax: Any,
    *,
    space: str,
    verts: Sequence[np.ndarray],
    reconstructed: Sequence[Any],
    title: str,
) -> None:
    if verts:
        arr = np.asarray(verts, dtype=np.float64)
        ax.scatter(arr[:, 0], arr[:, 1], s=8, color="C0", zorder=2)
    for rec in reconstructed:
        if not rec.drawn:
            continue
        samples = (
            rec.sample_u if space == "U" else rec.sample_q if space == "Q" else rec.sample_x
        )
        if samples is None or samples.shape[0] < 2:
            continue
        ax.plot(
            samples[:, 0],
            samples[:, 1],
            color="0.5",
            linewidth=0.8,
            alpha=0.85,
            zorder=1,
        )
    ax.set_title(title, fontsize=9)
    ax.set_aspect("equal", adjustable="datalim")
    ax.set_xticks([])
    ax.set_yticks([])


def write_roadmap_tree_growth_animation(
    *,
    task_id: str,
    mechanism: str,
    planner: str,
    run: PlannerRunRecord,
    out_dir: Path,
    fractions: Sequence[float] = (0.0, 0.25, 0.5, 0.75, 1.0),
    n_frames: int = 11,
    connector: LocalMotionModel | None = None,
    robot: Any | None = None,
) -> dict[str, Path]:
    """Write roadmap/tree growth GIF + U/Q/X contact sheets for designated trials."""
    plt = _require_matplotlib()
    from matplotlib import animation

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    events = list(run.trace_events)
    growth = growth_events(events, planner=planner)
    robot_obj = robot
    if robot_obj is None:
        raise ValueError("robot is required for native U/Q/X growth animations")
    if connector is None:
        raise ValueError("connector is required for native U/Q/X growth animations")

    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.6), constrained_layout=True)
    spaces = ("U", "Q", "X")

    def _render(upto: int) -> None:
        # Rebuild from the prefix of the full event stream so attach/path
        # indices remain consistent with construction order.
        prefix_events = events[: max(1, _event_prefix_for_growth(events, growth, upto))]
        geom = (
            extract_prm_geometry(prefix_events)
            if planner == "prm"
            else extract_rrt_geometry(prefix_events)
        )
        reconstructed = reconstruct_edge_samples(
            geom.edges, connector=connector, robot=robot_obj
        )
        verts = _vertex_xy(robot_obj, geom)
        for ax, space in zip(axes, spaces):
            ax.clear()
            _render_growth_space(
                ax,
                space=space,
                verts=verts[space],
                reconstructed=reconstructed,
                title=f"{space} {upto}/{len(growth)}",
            )
        fig.suptitle(f"{task_id}/{mechanism}/{planner}: growth")

    def _update(frame_i: int) -> Any:
        frac = frame_i / max(n_frames - 1, 1)
        _render(_fraction_index(len(growth), frac))
        return axes

    anim = animation.FuncAnimation(fig, _update, frames=n_frames, interval=120)
    gif_path = out_dir / f"{task_id}__{mechanism}__{planner}__growth__anim.gif"
    try:
        anim.save(gif_path, writer="pillow", fps=8)
    finally:
        plt.close(fig)

    # Contact sheet: rows = fractions, columns = U/Q/X.
    fig, axes = plt.subplots(
        len(fractions),
        3,
        figsize=(9.0, 2.4 * len(fractions)),
        constrained_layout=True,
    )
    if len(fractions) == 1:
        axes = np.asarray([axes])
    for row, frac in enumerate(fractions):
        upto = _fraction_index(len(growth), frac)
        prefix_events = events[: max(1, _event_prefix_for_growth(events, growth, upto))]
        geom = (
            extract_prm_geometry(prefix_events)
            if planner == "prm"
            else extract_rrt_geometry(prefix_events)
        )
        reconstructed = reconstruct_edge_samples(
            geom.edges, connector=connector, robot=robot_obj
        )
        verts = _vertex_xy(robot_obj, geom)
        for col, space in enumerate(spaces):
            ax = axes[row, col]
            _render_growth_space(
                ax,
                space=space,
                verts=verts[space],
                reconstructed=reconstructed,
                title=f"{space} @{frac*100:.0f}%",
            )
    sheet = out_dir / f"{task_id}__{mechanism}__{planner}__growth__contact.png"
    fig.savefig(sheet, dpi=110)
    plt.close(fig)

    # Per-space contact sheets for asset-key clarity.
    per_space: dict[str, Path] = {"anim": gif_path, "contact": sheet}
    for space in spaces:
        fig, axes = plt.subplots(
            1,
            len(fractions),
            figsize=(2.6 * len(fractions), 2.8),
            constrained_layout=True,
        )
        if len(fractions) == 1:
            axes = [axes]
        for ax_i, frac in zip(axes, fractions):
            upto = _fraction_index(len(growth), frac)
            prefix_events = events[
                : max(1, _event_prefix_for_growth(events, growth, upto))
            ]
            geom = (
                extract_prm_geometry(prefix_events)
                if planner == "prm"
                else extract_rrt_geometry(prefix_events)
            )
            reconstructed = reconstruct_edge_samples(
                geom.edges, connector=connector, robot=robot_obj
            )
            verts = _vertex_xy(robot_obj, geom)
            _render_growth_space(
                ax_i,
                space=space,
                verts=verts[space],
                reconstructed=reconstructed,
                title=f"{frac*100:.0f}%",
            )
        space_sheet = (
            out_dir
            / f"{task_id}__{mechanism}__{planner}__growth_{space.lower()}__contact.png"
        )
        fig.savefig(space_sheet, dpi=110)
        plt.close(fig)
        per_space[f"contact_{space.lower()}"] = space_sheet
    return per_space


def _event_prefix_for_growth(
    events: Sequence[Mapping[str, Any]],
    growth: Sequence[Mapping[str, Any]],
    upto: int,
) -> int:
    """Map a growth-event count to a prefix length in the full event stream."""
    if upto <= 0 or not growth:
        return 0
    target = growth[min(upto, len(growth)) - 1]
    # Identity match on step when present; else fall back to object identity.
    target_step = target.get("step")
    for i, ev in enumerate(events):
        if target_step is not None and ev.get("step") == target_step:
            return i + 1
        if ev is target:
            return i + 1
        if (
            ev.get("event_type") == target.get("event_type")
            and ev.get("payload") == target.get("payload")
        ):
            return i + 1
    return min(len(events), upto)


__all__ = [
    "write_lattice_combined_animation",
    "write_roadmap_tree_growth_animation",
]
