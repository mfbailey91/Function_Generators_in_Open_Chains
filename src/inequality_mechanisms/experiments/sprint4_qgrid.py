"""Sprint Four monotonic uniform-U vs uniform-Q control (S4-11).

Builds matched open-box graphs for a one-to-one four-bar sector:

* ``uniform_u`` — regular crank lattice (ADR-001 identity)
* ``uniform_q`` — regular follower lattice with unique attached ``u``

Both use ``output_euclidean`` cost, matched ``q`` start/goal, and no
periodic wrapping. This does not change ADR-001.
"""

from __future__ import annotations

import csv
import io
import math
from pathlib import Path
from typing import Any

import numpy as np
from numpy.random import Generator

from inequality_mechanisms.experiments.config import ExperimentConfig
from inequality_mechanisms.experiments.pilot import (
    _finite_cost,
    _run_search,
    _write_table_artifact,
)
from inequality_mechanisms.experiments.registry import (
    ExperimentRun,
    create_run,
    default_results_root,
)
from inequality_mechanisms.graphs.grid import PeriodicGrid2D
from inequality_mechanisms.graphs.output_grid import MonotonicOutputGraph
from inequality_mechanisms.graphs.validation import ConstrainedInputGraph
from inequality_mechanisms.mechanisms.fourbar import IndependentFourBars
from inequality_mechanisms.mechanisms.monotonic import (
    MonotonicBox2D,
    monotonic_box_for_independent_fourbars,
    open_axis_independent_fourbars,
)
from inequality_mechanisms.metrics.expansions import normalized_expansion
from inequality_mechanisms.metrics.path_metrics import (
    compute_path_metrics,
    compute_path_metrics_from_trajectories,
)
from inequality_mechanisms.search.objectives import resolve_planning_objective
from inequality_mechanisms.spaces.limits import OutputJointLimits
from inequality_mechanisms.spaces.output_space import OutputSpace
from inequality_mechanisms.visualization.paths import path_inputs

QGRID_RESULT_SCHEMA_VERSION = "4.2.0"
_COST_TYPE = "output_euclidean"


def _shrink_ranges(
    ranges: tuple[tuple[float, float], tuple[float, float]],
    *,
    fraction: float = 0.05,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Inset each axis interval to avoid rocker-extrema / gain fold."""
    out: list[tuple[float, float]] = []
    for lo, hi in ranges:
        width = float(hi - lo)
        pad = float(fraction) * width
        if width - 2.0 * pad <= 1e-9:
            out.append((float(lo), float(hi)))
        else:
            out.append((float(lo + pad), float(hi - pad)))
    return out[0], out[1]


def _nearest_valid_node(
    graph: ConstrainedInputGraph,
    u_target: np.ndarray,
) -> tuple[int, float]:
    """Return ``(node_id, ||u_node - u_target||)`` for the nearest valid node."""
    best_id = -1
    best_d = math.inf
    target = np.asarray(u_target, dtype=np.float64).reshape(2)
    for node in graph.iter_valid_nodes():
        coords = np.asarray(node.coordinates, dtype=np.float64)
        d = float(np.linalg.norm(coords - target))
        if d < best_d:
            best_d = d
            best_id = int(node.node_id)
    if best_id < 0:
        raise ValueError("U-graph has no valid nodes")
    return best_id, best_d


def build_monotonic_control_graphs(
    mech: IndependentFourBars,
    *,
    shape: tuple[int, int],
    edge_samples: int,
    box: MonotonicBox2D | None = None,
    range_inset: float = 0.05,
) -> dict[str, Any]:
    """Materialize matched open U-grid and Q-grid graphs for one mechanism."""
    if not isinstance(mech, IndependentFourBars):
        raise TypeError("mech must be IndependentFourBars")
    mono = box if box is not None else monotonic_box_for_independent_fourbars(mech)
    u_ranges = _shrink_ranges(mono.u_ranges, fraction=range_inset)
    q_ranges = _shrink_ranges(mono.q_ranges, fraction=range_inset)
    limits = OutputJointLimits.box(
        lower=[q_ranges[0][0], q_ranges[1][0]],
        upper=[q_ranges[0][1], q_ranges[1][1]],
    )
    space = OutputSpace.from_limits(limits)
    open_mech = open_axis_independent_fourbars(mech)

    u_grid = PeriodicGrid2D(shape=shape, ranges=u_ranges, wrap=(False, False))
    q_grid = PeriodicGrid2D(shape=shape, ranges=q_ranges, wrap=(False, False))

    u_graph = ConstrainedInputGraph(
        u_grid,
        open_mech,
        limits,
        edge_samples=edge_samples,
        output_space=space,
    )
    q_graph = MonotonicOutputGraph(
        q_grid,
        open_mech,
        limits,
        u_ranges=u_ranges,
        edge_samples=edge_samples,
        output_space=space,
    )
    return {
        "mechanism": open_mech,
        "box": mono,
        "u_ranges": u_ranges,
        "q_ranges": q_ranges,
        "limits": limits,
        "output_space": space,
        "u_graph": u_graph,
        "q_graph": q_graph,
    }


def _sample_matched_task(
    *,
    u_graph: ConstrainedInputGraph,
    q_graph: MonotonicOutputGraph,
    rng: Generator,
    min_output_separation: float,
    max_attempts: int,
    require_reachable: bool,
) -> dict[str, Any] | None:
    """Sample matched ``q`` start/goal with U snaps and optional reachability."""
    valid_q = list(q_graph.iter_valid_nodes())
    if len(valid_q) < 2:
        return None

    for _ in range(int(max_attempts)):
        i, j = (int(x) for x in rng.choice(len(valid_q), size=2, replace=False))
        qs = valid_q[i]
        qg = valid_q[j]
        q_start = np.asarray(qs.coordinates, dtype=np.float64)
        q_goal = np.asarray(qg.coordinates, dtype=np.float64)
        if float(np.linalg.norm(q_goal - q_start)) < float(min_output_separation):
            continue

        u_start_exact = q_graph.attached_u(qs.node_id)
        u_goal_exact = q_graph.attached_u(qg.node_id)
        u_start_id, d_s = _nearest_valid_node(u_graph, u_start_exact)
        u_goal_id, d_g = _nearest_valid_node(u_graph, u_goal_exact)
        if u_start_id == u_goal_id:
            continue

        q_start_u = u_graph.output(
            u_graph.grid.coordinates(*u_graph.grid.indices_from_id(u_start_id))
        )
        q_goal_u = u_graph.output(
            u_graph.grid.coordinates(*u_graph.grid.indices_from_id(u_goal_id))
        )
        start_residual = float(np.linalg.norm(q_start_u - q_start))
        goal_residual = float(np.linalg.norm(q_goal_u - q_goal))

        task = {
            "q_start": q_start,
            "q_goal": q_goal,
            "q_start_id": int(qs.node_id),
            "q_goal_id": int(qg.node_id),
            "u_start_id": int(u_start_id),
            "u_goal_id": int(u_goal_id),
            "u_snap_distance_start": float(d_s),
            "u_snap_distance_goal": float(d_g),
            "start_residual": start_residual,
            "goal_residual": goal_residual,
        }

        if not require_reachable:
            return task

        # Cheap reachability screen with Dijkstra on both graphs.
        ok = True
        for graph, start, goal in (
            (u_graph, task["u_start_id"], task["u_goal_id"]),
            (q_graph, task["q_start_id"], task["q_goal_id"]),
        ):
            objective = resolve_planning_objective(graph, goal, _COST_TYPE)  # type: ignore[arg-type]
            result = _run_search(graph, start, goal, "dijkstra", objective)  # type: ignore[arg-type]
            if not result.found:
                ok = False
                break
        if ok:
            return task
    return None


def _path_metrics_for_representation(
    *,
    representation: str,
    graph: ConstrainedInputGraph | MonotonicOutputGraph,
    path: tuple[int, ...],
    optimal_cost: float,
) -> dict[str, float | int]:
    if representation == "uniform_u":
        assert isinstance(graph, ConstrainedInputGraph)
        metrics = compute_path_metrics(graph, path, optimal_cost=optimal_cost)
        return metrics.to_dict()

    assert isinstance(graph, MonotonicOutputGraph)
    nodes = [int(n) for n in path]
    if not nodes:
        metrics = compute_path_metrics_from_trajectories(
            np.zeros((0, 2)),
            np.zeros((0, 2)),
            optimal_cost=optimal_cost,
            wrap_u=(False, False),
        )
        return metrics.to_dict()
    u_path = np.vstack([graph.attached_u(n) for n in nodes])
    q_path = path_inputs(graph, nodes)  # lattice coords are q
    metrics = compute_path_metrics_from_trajectories(
        u_path,
        q_path,
        optimal_cost=optimal_cost,
        wrap_u=(False, False),
    )
    return metrics.to_dict()


def _search_record(
    *,
    trial_index: int,
    representation: str,
    algorithm: str,
    graph: ConstrainedInputGraph | MonotonicOutputGraph,
    start: int,
    goal: int,
    task: dict[str, Any],
    graph_meta: dict[str, Any],
) -> dict[str, Any]:
    objective = resolve_planning_objective(graph, goal, _COST_TYPE)  # type: ignore[arg-type]
    result = _run_search(graph, start, goal, algorithm, objective)  # type: ignore[arg-type]
    n_valid = int(graph.valid_node_count)
    rho = (
        normalized_expansion(result.n_expanded, n_valid)
        if result.found and n_valid > 0
        else float("nan")
    )
    path_metrics = _path_metrics_for_representation(
        representation=representation,
        graph=graph,
        path=result.path if result.found else (),
        optimal_cost=float(result.cost),
    )
    q_stats = (
        graph.q_resolution_stats()
        if isinstance(graph, MonotonicOutputGraph)
        else {
            "delta_q0": float("nan"),
            "delta_q1": float("nan"),
            "delta_q_mean": float("nan"),
            "n_nodes": float(graph.grid.node_count),
            "n_valid_nodes": float(n_valid),
            "valid_fraction": float(n_valid / max(1, graph.grid.node_count)),
        }
    )
    if representation == "uniform_u":
        # Approximate output resolution from image of U spacing via local gain.
        du0, du1 = graph.grid.steps
        q_stats = {
            "delta_u0": float(du0),
            "delta_u1": float(du1),
            "delta_u_mean": float(0.5 * (du0 + du1)),
            "n_nodes": float(graph.grid.node_count),
            "n_valid_nodes": float(n_valid),
            "valid_fraction": float(n_valid / max(1, graph.grid.node_count)),
        }

    return {
        "result_schema_version": QGRID_RESULT_SCHEMA_VERSION,
        "trial_index": int(trial_index),
        "mechanism": "fourbar",
        "representation": representation,
        "algorithm": algorithm,
        "cost_type": _COST_TYPE,
        "heuristic_type": objective.heuristic_name,
        "found": bool(result.found),
        "failure_reason": None if result.found else "unreachable",
        "n_expanded": int(result.n_expanded),
        "n_generated": int(result.n_generated),
        "n_stale": int(result.n_stale),
        "n_valid_nodes": n_valid,
        "normalized_expansion": rho,
        "cost": _finite_cost(float(result.cost)),
        "optimal_cost": _finite_cost(float(result.cost)),
        "start_node": int(start),
        "goal_node": int(goal),
        "q_start": [float(x) for x in task["q_start"]],
        "q_goal": [float(x) for x in task["q_goal"]],
        "start_residual": float(task["start_residual"])
        if representation == "uniform_u"
        else 0.0,
        "goal_residual": float(task["goal_residual"])
        if representation == "uniform_u"
        else 0.0,
        "u_snap_distance_start": float(task["u_snap_distance_start"]),
        "u_snap_distance_goal": float(task["u_snap_distance_goal"]),
        "path_metrics": path_metrics,
        "n_path_edges": path_metrics["n_path_edges"],
        "path_length_u": path_metrics["path_length_u"],
        "path_length_q": path_metrics["path_length_q"],
        "path_length_x": path_metrics["path_length_x"],
        "resolution": q_stats,
        "u_ranges": [list(r) for r in graph_meta["u_ranges"]],
        "q_ranges": [list(r) for r in graph_meta["q_ranges"]],
        "limits": {
            "lower": graph_meta["limits"].lower.tolist(),
            "upper": graph_meta["limits"].upper.tolist(),
        },
        "grid_shape": list(graph.grid.shape),
        "wrap": list(graph.grid.wrap),
        "control": "monotonic_uniform_q_vs_u",
        "adr001_unchanged": True,
    }


def _comparison_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pair uniform_u / uniform_q rows sharing trial and algorithm."""
    by_key: dict[tuple[int, str], dict[str, dict[str, Any]]] = {}
    for row in rows:
        key = (int(row["trial_index"]), str(row["algorithm"]))
        by_key.setdefault(key, {})[str(row["representation"])] = row

    out: list[dict[str, Any]] = []
    for (trial_index, algorithm), parts in sorted(by_key.items()):
        u_row = parts.get("uniform_u")
        q_row = parts.get("uniform_q")
        if u_row is None or q_row is None:
            continue
        out.append(
            {
                "trial_index": trial_index,
                "algorithm": algorithm,
                "both_found": bool(u_row["found"] and q_row["found"]),
                "n_expanded_u": u_row["n_expanded"],
                "n_expanded_q": q_row["n_expanded"],
                "rho_u": u_row["normalized_expansion"],
                "rho_q": q_row["normalized_expansion"],
                "n_valid_u": u_row["n_valid_nodes"],
                "n_valid_q": q_row["n_valid_nodes"],
                "path_length_u_on_u": u_row["path_length_u"],
                "path_length_u_on_q": q_row["path_length_u"],
                "path_length_q_on_u": u_row["path_length_q"],
                "path_length_q_on_q": q_row["path_length_q"],
                "path_length_x_on_u": u_row["path_length_x"],
                "path_length_x_on_q": q_row["path_length_x"],
                "expansion_delta_q_minus_u": (
                    float(q_row["n_expanded"]) - float(u_row["n_expanded"])
                    if u_row["found"] and q_row["found"]
                    else float("nan")
                ),
            }
        )
    return out


def _comparison_csv(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "trial_index,algorithm\n"
    fieldnames = list(rows[0].keys())
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def _plot_comparison(rows: list[dict[str, Any]], path: Path) -> None:
    import matplotlib.pyplot as plt

    found = [r for r in rows if r["both_found"]]
    fig, axes = plt.subplots(1, 2, figsize=(8.5, 3.5), constrained_layout=True)
    if not found:
        for ax in axes:
            ax.set_title("no paired solves")
        fig.savefig(path, dpi=120)
        plt.close(fig)
        return

    labels = [f"t{r['trial_index']}/{r['algorithm'][:1]}" for r in found]
    x = np.arange(len(found))
    width = 0.35
    axes[0].bar(x - width / 2, [r["n_expanded_u"] for r in found], width, label="uniform_U")
    axes[0].bar(x + width / 2, [r["n_expanded_q"] for r in found], width, label="uniform_Q")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    axes[0].set_ylabel("expansions")
    axes[0].set_title("Expansions: uniform U vs Q")
    axes[0].legend(fontsize=8)

    axes[1].bar(x - width / 2, [r["rho_u"] for r in found], width, label="uniform_U")
    axes[1].bar(x + width / 2, [r["rho_q"] for r in found], width, label="uniform_Q")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    axes[1].set_ylabel(r"$\rho = N_{exp}/N_{valid}$")
    axes[1].set_title("Normalized expansions")
    axes[1].legend(fontsize=8)

    fig.savefig(path, dpi=120)
    plt.close(fig)


def run_sprint4_qgrid(
    config: ExperimentConfig,
    *,
    results_root: Path | None = None,
    run_id: str | None = None,
    figures_dir: Path | None = None,
) -> ExperimentRun:
    """Run the monotonic uniform-U vs uniform-Q control study."""
    fourbar = config.mechanisms.build_fourbar()
    if not isinstance(fourbar, IndependentFourBars):
        raise TypeError("sprint4_qgrid requires IndependentFourBars")

    root = default_results_root() if results_root is None else Path(results_root)
    run = create_run(config, results_root=root, run_id=run_id)
    run.mark_running()

    try:
        graph_pack = build_monotonic_control_graphs(
            fourbar,
            shape=tuple(config.graph.shape),  # type: ignore[arg-type]
            edge_samples=int(config.graph.edge_samples),
        )
        u_graph: ConstrainedInputGraph = graph_pack["u_graph"]
        q_graph: MonotonicOutputGraph = graph_pack["q_graph"]

        if u_graph.valid_node_count < 2 or q_graph.valid_node_count < 2:
            raise RuntimeError(
                "monotonic control graphs have too few valid nodes: "
                f"U={u_graph.valid_node_count}, Q={q_graph.valid_node_count}"
            )

        rng = np.random.default_rng(int(config.seed))
        rows: list[dict[str, Any]] = []
        n_accepted = 0
        n_excluded = 0
        attempts = 0
        max_total = int(config.trials.n_trials) * int(config.trials.max_sample_attempts)

        while n_accepted < int(config.trials.n_trials) and attempts < max_total:
            attempts += 1
            task = _sample_matched_task(
                u_graph=u_graph,
                q_graph=q_graph,
                rng=rng,
                min_output_separation=float(config.trials.min_output_separation),
                max_attempts=1,
                require_reachable=bool(config.trials.require_reachable),
            )
            if task is None:
                n_excluded += 1
                continue

            for algorithm in config.algorithms.names:
                rows.append(
                    _search_record(
                        trial_index=n_accepted,
                        representation="uniform_u",
                        algorithm=algorithm,
                        graph=u_graph,
                        start=task["u_start_id"],
                        goal=task["u_goal_id"],
                        task=task,
                        graph_meta=graph_pack,
                    )
                )
                rows.append(
                    _search_record(
                        trial_index=n_accepted,
                        representation="uniform_q",
                        algorithm=algorithm,
                        graph=q_graph,
                        start=task["q_start_id"],
                        goal=task["q_goal_id"],
                        task=task,
                        graph_meta=graph_pack,
                    )
                )
            n_accepted += 1

        run.append_jsonl("trials", rows)

        comparison = _comparison_rows(rows)
        _write_table_artifact(run, "qgrid_comparison", _comparison_csv(comparison))

        plot_path = run.path / "outputs" / "qgrid_u_vs_q_expansions.png"
        plot_path.parent.mkdir(parents=True, exist_ok=True)
        _plot_comparison(comparison, plot_path)
        run.register_output(
            "qgrid_u_vs_q_expansions",
            plot_path.relative_to(run.path).as_posix(),
        )

        if figures_dir is not None:
            dest = Path(figures_dir)
            dest.mkdir(parents=True, exist_ok=True)
            target = dest / plot_path.name
            target.write_bytes(plot_path.read_bytes())

        summary = {
            "experiment": "sprint4_qgrid",
            "result_schema_version": QGRID_RESULT_SCHEMA_VERSION,
            "seed": int(config.seed),
            "n_trials_requested": int(config.trials.n_trials),
            "n_trials_accepted": n_accepted,
            "n_sample_exclusions": n_excluded,
            "n_sample_attempts": attempts,
            "n_rows": len(rows),
            "cost_type": _COST_TYPE,
            "algorithms": list(config.algorithms.names),
            "grid_shape": list(config.graph.shape),
            "u_valid_nodes": int(u_graph.valid_node_count),
            "q_valid_nodes": int(q_graph.valid_node_count),
            "u_ranges": [list(r) for r in graph_pack["u_ranges"]],
            "q_ranges": [list(r) for r in graph_pack["q_ranges"]],
            "q_resolution": q_graph.q_resolution_stats(),
            "control_note": (
                "Experimental monotonic uniform-Q control; ADR-001 unchanged."
            ),
        }
        run.write_json("summary", summary)
        run.mark_completed()
    except Exception as exc:
        run.mark_failed(f"{type(exc).__name__}: {exc}")
        raise

    return run
