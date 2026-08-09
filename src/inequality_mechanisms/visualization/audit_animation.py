"""Animations and print contact sheets for V3.6B (V3-626)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from inequality_mechanisms.audits.planar2r_visual import PlannerRunRecord
from inequality_mechanisms.graphs.embedded import EmbeddedPlanningGraph


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


def write_roadmap_tree_growth_animation(
    *,
    task_id: str,
    mechanism: str,
    planner: str,
    run: PlannerRunRecord,
    out_dir: Path,
    fractions: Sequence[float] = (0.0, 0.25, 0.5, 0.75, 1.0),
    n_frames: int = 11,
) -> dict[str, Path]:
    """Write roadmap/tree growth GIF + contact sheet for designated trials."""
    plt = _require_matplotlib()
    from matplotlib import animation

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    events = list(run.trace_events)
    if planner == "prm":
        growth = [e for e in events if e.get("event_type") in ("sample_accept", "edge_accept")]
    else:
        growth = [e for e in events if e.get("event_type") == "vertex_insert"]

    fig, ax = plt.subplots(figsize=(5.5, 5.0), constrained_layout=True)

    def _render(upto: int) -> None:
        ax.clear()
        subset = growth[:upto]
        if planner == "prm":
            pts = [e["payload"]["u"] for e in subset if e.get("event_type") == "sample_accept"]
            if pts:
                arr = np.asarray(pts, dtype=np.float64)
                ax.scatter(arr[:, 0], arr[:, 1], s=10, color="C0")
        else:
            by_tree: dict[str, list] = {}
            for e in subset:
                tree = str(e["payload"].get("tree", "start"))
                by_tree.setdefault(tree, []).append(e["payload"]["u"])
            for tree, pts in by_tree.items():
                arr = np.asarray(pts, dtype=np.float64)
                ax.scatter(arr[:, 0], arr[:, 1], s=10, label=tree)
            if by_tree:
                ax.legend(fontsize=8)
        ax.set_title(f"{task_id}/{mechanism}/{planner}: growth {upto}/{len(growth)}")
        ax.set_aspect("equal", adjustable="datalim")

    def _update(frame_i: int) -> Any:
        frac = frame_i / max(n_frames - 1, 1)
        _render(_fraction_index(len(growth), frac))
        return (ax,)

    anim = animation.FuncAnimation(fig, _update, frames=n_frames, interval=120)
    gif_path = out_dir / f"{task_id}__{mechanism}__{planner}__growth__anim.gif"
    try:
        anim.save(gif_path, writer="pillow", fps=8)
    finally:
        plt.close(fig)

    fig, axes = plt.subplots(1, len(fractions), figsize=(2.6 * len(fractions), 2.8), constrained_layout=True)
    if len(fractions) == 1:
        axes = [axes]
    for ax_i, frac in zip(axes, fractions):
        # temporarily swap
        global_ax = ax_i
        pts_upto = _fraction_index(len(growth), frac)
        subset = growth[:pts_upto]
        if planner == "prm":
            pts = [e["payload"]["u"] for e in subset if e.get("event_type") == "sample_accept"]
            if pts:
                arr = np.asarray(pts, dtype=np.float64)
                global_ax.scatter(arr[:, 0], arr[:, 1], s=8, color="C0")
        else:
            by_tree = {}
            for e in subset:
                tree = str(e["payload"].get("tree", "start"))
                by_tree.setdefault(tree, []).append(e["payload"]["u"])
            for tree, pts in by_tree.items():
                arr = np.asarray(pts, dtype=np.float64)
                global_ax.scatter(arr[:, 0], arr[:, 1], s=8, label=tree)
        global_ax.set_title(f"{frac*100:.0f}%", fontsize=9)
        global_ax.set_aspect("equal", adjustable="datalim")
        global_ax.set_xticks([])
        global_ax.set_yticks([])
    sheet = out_dir / f"{task_id}__{mechanism}__{planner}__growth__contact.png"
    fig.savefig(sheet, dpi=110)
    plt.close(fig)
    return {"anim": gif_path, "contact": sheet}


__all__ = [
    "write_lattice_combined_animation",
    "write_roadmap_tree_growth_animation",
]
