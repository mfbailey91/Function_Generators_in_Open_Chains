#!/usr/bin/env python3
"""Render four-bar vs gearbox example trials for the V2.11 HTML dashboard."""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np

_REPO = Path(__file__).resolve().parents[1]
_SRC = _REPO / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import animation
from matplotlib.collections import LineCollection

from inequality_mechanisms.experiments.v2_production_config import (
    load_v2_production_config,
)
from inequality_mechanisms.experiments.v2_production_sample_bank import (
    load_v2_sample_bank,
)
from inequality_mechanisms.experiments.v2_production_work_unit import (
    _pair_experiment_config,
)
from inequality_mechanisms.experiments.v2_runner import (
    FOURBAR_MECHANISM_ID,
    SPAN_MATCHED_GEARBOX_MECHANISM_ID,
    build_graphs,
    build_mechanism_branches,
)
from inequality_mechanisms.experiments.v2_shared_q_fixtures import fractions_to_q
from inequality_mechanisms.experiments.v2_tasks import OutputTask
from inequality_mechanisms.graphs.pair_invariants import (
    assert_identical_query_overlays,
    assert_shared_q_pair_invariants,
)
from inequality_mechanisms.graphs.query_overlay import QueryOverlayGraph
from inequality_mechanisms.kinematics.planar_2r import Planar2R
from inequality_mechanisms.search.graph_solver import production_graph_solver
from inequality_mechanisms.search.v2_objectives import resolve_v2_objective
from inequality_mechanisms.visualization.branches import plot_branch_axis_transmission
from inequality_mechanisms.visualization.embedded_graphs import (
    plot_embedded_q_path,
    plot_embedded_u_path,
)
from inequality_mechanisms.visualization.paths import plot_cartesian_path

OUT_DIR = (
    _REPO
    / "docs"
    / "software"
    / "experiments"
    / "reports"
    / "figures"
    / "v2_11"
    / "examples"
)
PAIR_ID = "m000160"
TASK_IDS = ("reverse_diagonal", "joint1_dominant")
LABELS = {
    FOURBAR_MECHANISM_ID: "four-bar",
    SPAN_MATCHED_GEARBOX_MECHANISM_ID: "gearbox",
}


def _coords(graph: Any, node_ids: list[int], space: str) -> np.ndarray:
    rows = []
    for node_id in node_ids:
        state = graph.q_state(node_id) if space == "q" else graph.u_state(node_id)
        rows.append(np.asarray(state, dtype=np.float64))
    return np.vstack(rows) if rows else np.empty((0, 2), dtype=np.float64)


def _subsample(values: list[int], n_frames: int) -> list[list[int]]:
    if not values:
        return [[]]
    n_frames = max(2, int(n_frames))
    frames: list[list[int]] = []
    for i in range(n_frames):
        end = max(1, int(round((i + 1) * len(values) / n_frames)))
        frames.append(values[:end])
    return frames


def write_heatmap(
    graph: Any,
    path_ids: list[int],
    out: Path,
    *,
    title: str,
    edge_cost,
) -> None:
    base = graph._base
    q = np.asarray(base.q_nodes, dtype=np.float64)
    valid = np.asarray(base.valid_nodes, dtype=bool)
    segments = []
    weights = []
    for a, b in base.topology.iter_edges():
        if not (valid[a] and valid[b]):
            continue
        segments.append([q[a], q[b]])
        weights.append(float(edge_cost(int(a), int(b))))
    fig, ax = plt.subplots(figsize=(5.4, 5.2))
    coll = LineCollection(
        np.asarray(segments),
        array=np.asarray(weights),
        cmap="magma",
        linewidths=1.1,
        zorder=1,
    )
    ax.add_collection(coll)
    fig.colorbar(coll, ax=ax, shrink=0.82, label=r"edge weight $\|\Delta u\|_2$")
    if path_ids:
        coords = _coords(graph, path_ids, "q")
        ax.plot(coords[:, 0], coords[:, 1], color="cyan", lw=2.2, zorder=3, label="path")
        ax.scatter(coords[0, 0], coords[0, 1], c="white", s=40, zorder=4, edgecolors="k")
        ax.scatter(coords[-1, 0], coords[-1, 1], c="lime", s=40, zorder=4, edgecolors="k")
    ax.set_xlabel("$q_0$")
    ax.set_ylabel("$q_1$")
    ax.set_title(title)
    ax.set_aspect("equal", adjustable="box")
    ax.legend(fontsize=8, loc="best")
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)


def write_traversal_gif(
    graph: Any,
    *,
    space: str,
    expanded: list[int],
    path_ids: list[int],
    out: Path,
    title: str,
    n_frames: int = 36,
) -> None:
    base = graph._base
    values = base.q_nodes if space == "q" else base.u_nodes
    valid = np.asarray(base.valid_nodes, dtype=bool)
    fig, ax = plt.subplots(figsize=(5.0, 5.0))
    for a, b in base.topology.iter_edges():
        if valid[a] and valid[b]:
            ax.plot(
                [values[a, 0], values[b, 0]],
                [values[a, 1], values[b, 1]],
                color="0.85",
                lw=0.4,
                zorder=1,
            )
    exp_scat = ax.scatter([], [], s=10, c="#c0392b", alpha=0.55, zorder=3, label="expanded")
    (path_line,) = ax.plot([], [], color="#1f4e79", lw=2.0, zorder=4, label="path")
    ax.set_xlabel("$q_0$" if space == "q" else "$u_0$")
    ax.set_ylabel("$q_1$" if space == "q" else "$u_1$")
    ax.set_title(title)
    ax.set_aspect("equal", adjustable="box")
    ax.legend(fontsize=8)
    frames = _subsample(expanded, n_frames)
    path_coords = _coords(graph, path_ids, space)

    def update(frame_idx: int):
        ids = frames[frame_idx]
        coords = _coords(graph, ids, space) if ids else np.empty((0, 2))
        exp_scat.set_offsets(coords if coords.size else np.empty((0, 2)))
        show_path = frame_idx >= len(frames) - 4
        if show_path and path_coords.size:
            path_line.set_data(path_coords[:, 0], path_coords[:, 1])
        else:
            path_line.set_data([], [])
        return exp_scat, path_line

    anim = animation.FuncAnimation(fig, update, frames=len(frames), interval=80, blit=True)
    anim.save(out, writer=animation.PillowWriter(fps=12))
    plt.close(fig)


def write_cartesian_gif(q_path: np.ndarray, out: Path, title: str, n_frames: int = 32) -> None:
    arm = Planar2R()
    tips = np.asarray([arm.forward(q) for q in q_path], dtype=np.float64)
    fig, ax = plt.subplots(figsize=(5.0, 5.0))
    ax.plot(tips[:, 0], tips[:, 1], color="0.75", lw=1.5, zorder=1)
    (arm_line,) = ax.plot([], [], "-o", color="#1f4e79", lw=2.4, ms=5, zorder=3)
    tip_scat = ax.scatter([], [], c="#c0392b", s=30, zorder=4)
    ax.set_title(title)
    ax.set_xlabel("$x$")
    ax.set_ylabel("$y$")
    ax.set_aspect("equal", adjustable="box")
    pad = 0.15
    ax.set_xlim(tips[:, 0].min() - pad, tips[:, 0].max() + pad)
    ax.set_ylim(tips[:, 1].min() - pad, tips[:, 1].max() + pad)
    indices = np.unique(np.linspace(0, len(q_path) - 1, n_frames, dtype=int))

    def update(frame_idx: int):
        idx = int(indices[frame_idx])
        poly = arm.link_polyline(q_path[idx])
        arm_line.set_data(poly[:, 0], poly[:, 1])
        tip_scat.set_offsets(tips[idx : idx + 1])
        return arm_line, tip_scat

    anim = animation.FuncAnimation(fig, update, frames=len(indices), interval=90, blit=True)
    anim.save(out, writer=animation.PillowWriter(fps=10))
    plt.close(fig)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    config = load_v2_production_config(_REPO / "configs" / "v2" / "production_astar.yaml")
    bank = load_v2_sample_bank(_REPO / "configs" / "v2" / "sample_banks" / "production_v1.json")
    mechanism = next(m for m in bank.mechanisms if m.mechanism_id == PAIR_ID)
    tasks = {t.task_id: t for t in bank.tasks}
    exp_cfg = _pair_experiment_config(config, mechanism, shape=(64, 64))
    branches = build_mechanism_branches(exp_cfg)
    graphs = build_graphs(exp_cfg, branches)
    shared_valid = np.asarray(
        np.logical_and.reduce([g.valid_nodes for g in graphs.values()]),
        dtype=np.bool_,
    )
    graphs = {mid: replace(g, valid_nodes=shared_valid.copy()) for mid, g in graphs.items()}
    assert_shared_q_pair_invariants(
        graphs[FOURBAR_MECHANISM_ID],
        graphs[SPAN_MATCHED_GEARBOX_MECHANISM_ID],
        residual_tol=config.branch.inverse_tolerance,
        edge_n_samples=config.edge_validation.samples,
        raise_on_failure=True,
    )
    plot_branch_axis_transmission(
        {
            "four-bar": branches[FOURBAR_MECHANISM_ID],
            "gearbox": branches[SPAN_MATCHED_GEARBOX_MECHANISM_ID],
        },
        OUT_DIR / f"{PAIR_ID}_transmission.png",
        title=f"{PAIR_ID} axis maps $q(u)$",
    )
    solver = production_graph_solver("astar")
    cert = branches[FOURBAR_MECHANISM_ID].certificate
    gb_mech = branches[SPAN_MATCHED_GEARBOX_MECHANISM_ID].mechanism
    manifest: dict[str, Any] = {
        "pair_id": PAIR_ID,
        "fourbars": mechanism.fourbars,
        "descriptors": mechanism.descriptors,
        "branch_summary": mechanism.branch_summary,
        "gearbox_ratios": [float(x) for x in np.asarray(gb_mech.ratios)],
        "gearbox_provenance_axes": gb_mech.provenance.get("axes", []),
        "tasks": [],
    }
    for task_id in TASK_IDS:
        task = tasks[task_id]
        start_q = fractions_to_q(cert.output_lower, cert.output_upper, task.start_fraction)
        goal_q = fractions_to_q(cert.output_lower, cert.output_upper, task.goal_fraction)
        requested = OutputTask(
            np.asarray(start_q, dtype=np.float64),
            np.asarray(goal_q, dtype=np.float64),
        )
        overlays = {
            mid: QueryOverlayGraph(
                base=base_graph,
                start_q=requested.requested_start_q,
                goal_q=requested.requested_goal_q,
                edge_n_samples=config.edge_validation.samples,
            )
            for mid, base_graph in graphs.items()
        }
        assert_identical_query_overlays(
            overlays[FOURBAR_MECHANISM_ID],
            overlays[SPAN_MATCHED_GEARBOX_MECHANISM_ID],
            raise_on_failure=True,
        )
        task_payload: dict[str, Any] = {
            "task_id": task_id,
            "category": task.category,
            "start_q": requested.requested_start_q.tolist(),
            "goal_q": requested.requested_goal_q.tolist(),
            "sides": {},
        }
        stem = OUT_DIR / f"{PAIR_ID}_{task_id}"
        for mid, overlay in overlays.items():
            label = LABELS[mid]
            objective = resolve_v2_objective(
                overlay,  # type: ignore[arg-type]
                overlay.goal_node_id,
                "actuator_travel",
                "input_euclidean",
            )
            result = solver.solve(
                overlay,
                overlay.start_node_id,
                overlay.goal_node_id,
                objective,
                record_expanded=True,
            )
            if not result.found:
                raise RuntimeError(f"example search failed: {PAIR_ID} {task_id} {mid}")
            path_ids = [int(n) for n in result.path]
            expanded = [int(n) for n in result.expanded_nodes]
            q_path = _coords(overlay, path_ids, "q")
            u_path = _coords(overlay, path_ids, "u")
            plot_embedded_q_path(
                overlay,
                f"{stem}_{label}_q.png",
                path_node_ids=path_ids,
                expanded_node_ids=expanded,
                title=f"{label} Q path · {task_id}",
            )
            plot_embedded_u_path(
                overlay,
                f"{stem}_{label}_u.png",
                path_node_ids=path_ids,
                expanded_node_ids=expanded,
                title=f"{label} U path · {task_id}",
            )
            plot_cartesian_path(
                q_path,
                f"{stem}_{label}_cartesian.png",
                title=f"{label} Cartesian · {task_id}",
                n_pose_samples=10,
            )
            write_heatmap(
                overlay,
                path_ids,
                Path(f"{stem}_{label}_heatmap.png"),
                title=f"{label} Q grid · actuator-travel weights",
                edge_cost=objective.edge_cost,
            )
            write_traversal_gif(
                overlay,
                space="q",
                expanded=expanded,
                path_ids=path_ids,
                out=Path(f"{stem}_{label}_q_traversal.gif"),
                title=f"{label} Q traversal · {task_id}",
            )
            write_traversal_gif(
                overlay,
                space="u",
                expanded=expanded,
                path_ids=path_ids,
                out=Path(f"{stem}_{label}_u_traversal.gif"),
                title=f"{label} U traversal · {task_id}",
            )
            write_cartesian_gif(
                q_path,
                Path(f"{stem}_{label}_cartesian.gif"),
                title=f"{label} Cartesian traversal · {task_id}",
            )
            task_payload["sides"][label] = {
                "n_expanded": int(result.n_expanded),
                "n_generated": int(result.n_generated),
                "optimal_cost": float(result.cost),
                "path_length_q": float(np.sum(np.linalg.norm(np.diff(q_path, axis=0), axis=1)))
                if len(q_path) > 1
                else 0.0,
                "path_length_u": float(np.sum(np.linalg.norm(np.diff(u_path, axis=0), axis=1)))
                if len(u_path) > 1
                else 0.0,
                "n_path_nodes": len(path_ids),
            }
        manifest["tasks"].append(task_payload)

    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(OUT_DIR / "manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
