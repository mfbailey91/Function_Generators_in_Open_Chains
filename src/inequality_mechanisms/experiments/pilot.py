"""Pilot Monte Carlo runner (IM-017).

Loads a validated experiment config, registers a run, executes paired
gearbox / four-bar searches, and writes trial records, a summary table, and
expansion plots under ``results/<run_id>/``.

Population four-bar mode (ADR-009) samples two crank-rockers per trial,
derives shared Q limits from those follower ranges, and rebuilds graphs
before sampling matched start/goal poses.
"""

from __future__ import annotations

import math
import shutil
from pathlib import Path
from typing import Any

import numpy as np
from numpy.random import Generator

from inequality_mechanisms.experiments.config import (
    ExperimentConfig,
    FourBarPopulationSource,
)
from inequality_mechanisms.experiments.canvas import write_monte_carlo_canvas
from inequality_mechanisms.experiments.equal_nodes import (
    match_gearbox_to_fourbar_valid_count,
)
from inequality_mechanisms.experiments.registry import (
    ExperimentRun,
    create_run,
    default_results_root,
)
from inequality_mechanisms.experiments.schema import RESULT_SCHEMA_VERSION
from inequality_mechanisms.experiments.setup import (
    PairedGraphs,
    build_paired_graphs,
    build_paired_graphs_from_parts,
)
from inequality_mechanisms.experiments.tasks import (
    PairedTask,
    SelectedPreimages,
    generate_paired_tasks,
)
from inequality_mechanisms.graphs.grid import PeriodicGrid2D
from inequality_mechanisms.graphs.validation import ConstrainedInputGraph
from inequality_mechanisms.kinematics import Planar2R
from inequality_mechanisms.mechanisms.fourbar import IndependentFourBars
from inequality_mechanisms.mechanisms.population import (
    limits_from_fourbar_follower_ranges,
    sample_independent_crank_rockers,
)
from inequality_mechanisms.metrics.expansions import (
    normalized_expansion,
    summarize_trials,
    summary_table_csv,
)
from inequality_mechanisms.metrics.path_metrics import compute_path_metrics
from inequality_mechanisms.search.astar import astar
from inequality_mechanisms.search.core import best_first_search
from inequality_mechanisms.search.dijkstra import dijkstra
from inequality_mechanisms.search.heuristic_quality import (
    heuristic_quality_report,
    validate_heuristic_admissible,
)
from inequality_mechanisms.search.objectives import (
    PlanningObjective,
    resolve_planning_objective,
)
from inequality_mechanisms.search.result import SearchResult
from inequality_mechanisms.visualization.expansions import (
    plot_normalized_expansions,
    plot_paired_log_ratios,
    plot_raw_expansions,
)
from inequality_mechanisms.visualization.paths import (
    cost_from_start,
    path_outputs,
    plot_cartesian_path,
    plot_input_path,
    plot_output_path,
)


def _write_table_artifact(run: ExperimentRun, name: str, text: str) -> Path:
    """Write a tabular artifact as ``.csv``, falling back to ``.txt``.

    Some agent/sandbox environments block ``*.csv`` writes via ignore rules
    even when the run directory itself is writable. Prefer CSV when possible;
    otherwise preserve the same CSV-formatted text under ``.txt`` so the run
    can still complete without discarding trial results.
    """
    try:
        return run.write_text(name, text, suffix=".csv")
    except PermissionError:
        return run.write_text(name, text, suffix=".txt")


def _residual_summary_csv(rows: list[dict[str, Any]]) -> str:
    """Build a CSV of matched-task residual norms from trial JSONL rows."""
    lines = [
        "trial_index,mechanism,endpoint,residual_norm,"
        "n_continuous,n_discrete,tol"
    ]
    seen: set[tuple[int, str]] = set()
    for row in rows:
        key = (int(row["trial_index"]), str(row["mechanism"]))
        if key in seen:
            continue
        seen.add(key)
        pre = row.get("preimages") or {}
        tol = row.get("output_residual_tol")
        for endpoint, field in (("start", "start_residual"), ("goal", "goal_residual")):
            res = pre.get(field)
            if not isinstance(res, dict):
                continue
            lines.append(
                f"{row['trial_index']},{row['mechanism']},{endpoint},"
                f"{res.get('residual_norm')},"
                f"{res.get('n_continuous_candidates')},"
                f"{res.get('n_discrete_candidates')},"
                f"{tol}"
            )
    return "\n".join(lines) + "\n"


def _finite_cost(cost: float) -> float | None:
    if math.isfinite(cost):
        return float(cost)
    return None


def _fourbar_lengths_payload(fourbar: IndependentFourBars) -> list[list[float]]:
    return [list(bar.lengths) for bar in fourbar.bars]


def _limits_payload(paired: PairedGraphs) -> dict[str, list[float]]:
    return {
        "lower": paired.limits.lower.tolist(),
        "upper": paired.limits.upper.tolist(),
    }


def _annotate_trial_meta(
    rows: list[dict[str, Any]],
    *,
    paired: PairedGraphs,
    fourbar_mode: str,
) -> None:
    """Attach per-trial mechanism / limit identity to search records."""
    limits = _limits_payload(paired)
    lengths: list[list[float]] | None = None
    if isinstance(paired.fourbar_mechanism, IndependentFourBars):
        lengths = _fourbar_lengths_payload(paired.fourbar_mechanism)
    gb_shape = list(paired.gearbox.grid.shape)
    fb_shape = list(paired.fourbar.grid.shape)
    for record in rows:
        record["fourbar_mode"] = fourbar_mode
        record["limits"] = limits
        record["gearbox_grid_shape"] = gb_shape
        record["fourbar_grid_shape"] = fb_shape
        if lengths is not None:
            record["fourbar_lengths"] = lengths
        if paired.match_meta is not None:
            record["match_meta"] = paired.match_meta


def _run_search(
    graph: ConstrainedInputGraph,
    start: int,
    goal: int,
    algorithm: str,
    objective: PlanningObjective,
    *,
    record_expanded: bool = False,
) -> SearchResult:
    """Run Dijkstra or A* under a resolved planning objective."""
    if algorithm == "dijkstra":
        return dijkstra(
            graph,
            start,
            goal,
            edge_cost=objective.edge_cost,
            record_expanded=record_expanded,
        )
    if algorithm == "astar":
        # Preserve IM-035: never call astar() with a custom edge_cost.
        if (
            objective.cost_name == "output_euclidean"
            and objective.heuristic_name == "output_euclidean"
            and not record_expanded
        ):
            return astar(graph, start, goal)
        return best_first_search(
            graph,
            start,
            goal,
            objective.heuristic,
            edge_cost=objective.edge_cost,
            record_expanded=record_expanded,
        )
    raise ValueError(f"unknown algorithm: {algorithm!r}")


def _write_path_sample(
    run: ExperimentRun,
    *,
    trial_index: int,
    paired: PairedGraphs,
    task: PairedTask,
    algorithm: str = "astar",
    cost_type: str = "output_euclidean",
) -> None:
    """Write U / Q / Cartesian PNGs for one kept trial."""
    gb_obj = resolve_planning_objective(
        paired.gearbox, task.gearbox.goal_node_id, cost_type
    )
    fb_obj = resolve_planning_objective(
        paired.fourbar, task.fourbar.goal_node_id, cost_type
    )
    gb_res = _run_search(
        paired.gearbox,
        task.gearbox.start_node_id,
        task.gearbox.goal_node_id,
        algorithm,
        gb_obj,
    )
    fb_res = _run_search(
        paired.fourbar,
        task.fourbar.start_node_id,
        task.fourbar.goal_node_id,
        algorithm,
        fb_obj,
    )
    if not (gb_res.found and fb_res.found):
        return

    out = run.outputs_dir / "paths" / f"trial_{trial_index:04d}"
    out.mkdir(parents=True, exist_ok=True)
    plant = Planar2R()
    gb_costs = cost_from_start(paired.gearbox, task.gearbox.start_node_id)
    fb_costs = cost_from_start(paired.fourbar, task.fourbar.start_node_id)

    figures = {
        "gearbox_input": plot_input_path(
            paired.gearbox,
            gb_res.path,
            out / "gearbox_input.png",
            costs=gb_costs,
            start=task.gearbox.start_node_id,
            goal=task.gearbox.goal_node_id,
            title=f"Trial {trial_index} gearbox U",
        ),
        "gearbox_output": plot_output_path(
            paired.gearbox,
            gb_res.path,
            out / "gearbox_output.png",
            costs=gb_costs,
            start=task.gearbox.start_node_id,
            goal=task.gearbox.goal_node_id,
            title=f"Trial {trial_index} gearbox Q",
        ),
        "gearbox_cartesian": plot_cartesian_path(
            path_outputs(paired.gearbox, gb_res.path),
            out / "gearbox_cartesian.png",
            plant=plant,
            title=f"Trial {trial_index} gearbox Cartesian",
        ),
        "fourbar_input": plot_input_path(
            paired.fourbar,
            fb_res.path,
            out / "fourbar_input.png",
            costs=fb_costs,
            start=task.fourbar.start_node_id,
            goal=task.fourbar.goal_node_id,
            title=f"Trial {trial_index} four-bar U",
        ),
        "fourbar_output": plot_output_path(
            paired.fourbar,
            fb_res.path,
            out / "fourbar_output.png",
            costs=fb_costs,
            start=task.fourbar.start_node_id,
            goal=task.fourbar.goal_node_id,
            title=f"Trial {trial_index} four-bar Q",
        ),
        "fourbar_cartesian": plot_cartesian_path(
            path_outputs(paired.fourbar, fb_res.path),
            out / "fourbar_cartesian.png",
            plant=plant,
            title=f"Trial {trial_index} four-bar Cartesian",
        ),
    }
    for name, path in figures.items():
        rel = path.relative_to(run.path).as_posix()
        run.register_output(f"path_t{trial_index:04d}_{name}", rel)


def _search_record(
    *,
    trial: PairedTask,
    mechanism: str,
    algorithm: str,
    graph: ConstrainedInputGraph,
    preimages: SelectedPreimages,
    cost_type: str,
    validate_heuristic: bool,
) -> dict[str, Any]:
    """Run one search and return a tidy trial JSONL record."""
    if mechanism not in ("gearbox", "fourbar"):
        raise ValueError(f"unknown mechanism key: {mechanism!r}")
    if algorithm not in ("dijkstra", "astar"):
        raise ValueError(f"unknown algorithm: {algorithm!r}")

    n_valid = graph.valid_node_count
    objective = resolve_planning_objective(
        graph,
        preimages.goal_node_id,
        cost_type,
        heuristic_name="zero" if algorithm == "dijkstra" else None,
    )
    # Dijkstra always records zero heuristic; A* records the compatible default.
    recorded_heuristic = (
        "zero" if algorithm == "dijkstra" else objective.heuristic_name
    )

    record: dict[str, Any] = {
        "result_schema_version": RESULT_SCHEMA_VERSION,
        "trial_index": trial.trial_index,
        "mechanism": mechanism,
        "algorithm": algorithm,
        "cost_type": objective.cost_name,
        "heuristic_type": recorded_heuristic,
        "q_start": trial.q_start.tolist(),
        "q_goal": trial.q_goal.tolist(),
        "preimages": preimages.to_dict(),
        "n_valid_nodes": n_valid,
        "output_residual_tol": trial.output_residual_tol,
        "found": False,
        "n_expanded": None,
        "n_generated": None,
        "n_stale": None,
        "n_path_edges": None,
        "path_length_u": None,
        "path_length_q": None,
        "path_length_x": None,
        "optimal_cost": None,
        "cost": None,
        "rho_expanded": None,
        "failure_reason": None,
        "heuristic_validation": None,
        "heuristic_quality": None,
    }

    result = _run_search(
        graph,
        preimages.start_node_id,
        preimages.goal_node_id,
        algorithm,
        objective,
        record_expanded=bool(validate_heuristic and algorithm == "astar"),
    )

    if validate_heuristic and algorithm == "astar":
        reason = validate_heuristic_admissible(
            graph,
            preimages.goal_node_id,
            objective.heuristic,
            edge_cost=objective.edge_cost,
        )
        record["heuristic_validation"] = "ok" if reason is None else "failed"
        if reason is not None:
            record["failure_reason"] = reason
        else:
            hq = heuristic_quality_report(
                graph,
                preimages.goal_node_id,
                objective.heuristic,
                edge_cost=objective.edge_cost,
                cost_name=objective.cost_name,
                heuristic_name=objective.heuristic_name,
                path=result.path if result.found else None,
                expanded_nodes=result.expanded_nodes or None,
                max_sample_nodes=256,
                sample_seed=int(trial.trial_index),
            )
            record["heuristic_quality"] = hq.to_dict()

    record["n_expanded"] = int(result.n_expanded)
    record["n_generated"] = int(result.n_generated)
    record["n_stale"] = int(result.n_stale)
    record["n_path_edges"] = int(result.n_path_edges)
    opt = _finite_cost(result.cost)
    record["optimal_cost"] = opt
    record["cost"] = opt  # backward-compatible alias of optimal_cost

    if result.found:
        record["found"] = True
        metrics = compute_path_metrics(
            graph,
            result.path,
            optimal_cost=float(result.cost),
        )
        record["n_path_edges"] = int(metrics.n_path_edges)
        record["path_length_u"] = float(metrics.path_length_u)
        record["path_length_q"] = float(metrics.path_length_q)
        record["path_length_x"] = float(metrics.path_length_x)
        if n_valid > 0:
            record["rho_expanded"] = normalized_expansion(result.n_expanded, n_valid)
    else:
        record["found"] = False
        if record["failure_reason"] is None:
            record["failure_reason"] = "unreachable"

    return record


def _write_plots(
    run: ExperimentRun,
    rows: list[dict[str, Any]],
    *,
    figures_dir: Path | None,
) -> dict[str, Path]:
    """Write expansion PNGs under the run outputs (and optional copy dir)."""
    outputs = run.outputs_dir
    raw_path = outputs / "expansions_raw.png"
    norm_path = outputs / "expansions_normalized.png"
    ratio_path = outputs / "expansions_ratio.png"

    plot_raw_expansions(rows, raw_path)
    plot_normalized_expansions(rows, norm_path)
    plot_paired_log_ratios(rows, ratio_path)

    run.register_output("expansions_raw", "outputs/expansions_raw.png")
    run.register_output("expansions_normalized", "outputs/expansions_normalized.png")
    run.register_output("expansions_ratio", "outputs/expansions_ratio.png")

    written = {
        "expansions_raw": raw_path,
        "expansions_normalized": norm_path,
        "expansions_ratio": ratio_path,
    }
    if figures_dir is not None:
        figures_dir = Path(figures_dir)
        figures_dir.mkdir(parents=True, exist_ok=True)
        for name, src in written.items():
            shutil.copy2(src, figures_dir / src.name)
    return written


def _records_for_task(
    task: PairedTask,
    paired: PairedGraphs,
    *,
    algorithms: list[str],
    cost_type: str,
    validate_h: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for mechanism, graph, preimages in (
        ("gearbox", paired.gearbox, task.gearbox),
        ("fourbar", paired.fourbar, task.fourbar),
    ):
        for algorithm in algorithms:
            rows.append(
                _search_record(
                    trial=task,
                    mechanism=mechanism,
                    algorithm=algorithm,
                    graph=graph,
                    preimages=preimages,
                    cost_type=cost_type,
                    validate_heuristic=validate_h,
                )
            )
    return rows


def _pair_found(rows: list[dict[str, Any]], *, algorithm: str = "dijkstra") -> bool:
    """Return True if both mechanisms found a path under ``algorithm``."""
    found = {
        str(r["mechanism"]): bool(r["found"])
        for r in rows
        if str(r["algorithm"]) == algorithm
    }
    return bool(found.get("gearbox")) and bool(found.get("fourbar"))


def _shared_grid(config: ExperimentConfig) -> PeriodicGrid2D:
    graph_cfg = config.graph
    ranges = None if graph_cfg.ranges is None else graph_cfg.ranges
    return PeriodicGrid2D(
        graph_cfg.shape,
        ranges=ranges,
        wrap=graph_cfg.wrap,
    )


def _build_population_trial_graphs(
    config: ExperimentConfig,
    rng: Generator,
    *,
    grid: PeriodicGrid2D,
) -> PairedGraphs:
    """Sample crank-rockers and build paired graphs under follower-range limits."""
    src = config.mechanisms.fourbar
    if not isinstance(src, FourBarPopulationSource):
        raise TypeError("population trial requires FourBarPopulationSource")
    spec = src.to_spec()
    fourbar = sample_independent_crank_rockers(
        rng,
        spec,
        n_bars=int(src.n_bars),
        name=str(src.name_prefix),
    )
    limits = limits_from_fourbar_follower_ranges(
        fourbar,
        n_samples=int(spec.n_crank_samples),
    )
    gearbox = config.mechanisms.build_gearbox()
    edge_samples = int(config.graph.edge_samples)

    if not config.graph.match_valid_nodes:
        return build_paired_graphs_from_parts(
            grid=grid,
            limits=limits,
            gearbox_mechanism=gearbox,
            fourbar_mechanism=fourbar,
            edge_samples=edge_samples,
        )

    fourbar_graph = ConstrainedInputGraph(
        grid,
        fourbar,
        limits,
        edge_samples=edge_samples,
    )
    gb_grid, _gb_graph, meta = match_gearbox_to_fourbar_valid_count(
        gearbox_mechanism=gearbox,
        fourbar_graph=fourbar_graph,
        limits=limits,
        edge_samples=edge_samples,
        relative_tol=float(config.graph.match_relative_tol),
        shape_hi=int(config.graph.match_shape_hi),
    )
    return build_paired_graphs_from_parts(
        grid=grid,
        limits=limits,
        gearbox_mechanism=gearbox,
        fourbar_mechanism=fourbar,
        edge_samples=edge_samples,
        gearbox_grid=gb_grid,
        match_meta=meta,
    )


def _try_one_paired_task(
    paired: PairedGraphs,
    rng: Generator,
    config: ExperimentConfig,
    *,
    remaining_attempts: int,
) -> PairedTask | None:
    """Sample one paired task or return None if sampling fails immediately."""
    try:
        batch = generate_paired_tasks(
            paired.gearbox,
            paired.fourbar,
            n_trials=1,
            rng=rng,
            min_output_separation=config.trials.min_output_separation,
            preimage_policy=config.trials.preimage_policy,
            max_sample_attempts=max(1, remaining_attempts),
            snap_tol=config.trials.snap_output_tol,
        )
    except ValueError:
        return None
    candidate = batch[0]
    return PairedTask(
        trial_index=0,
        q_start=candidate.q_start,
        q_goal=candidate.q_goal,
        gearbox=candidate.gearbox,
        fourbar=candidate.fourbar,
        output_residual_tol=candidate.output_residual_tol,
    )


def run_pilot(
    config: ExperimentConfig,
    *,
    results_root: Path | str | None = None,
    run_id: str | None = None,
    figures_dir: Path | str | None = None,
    graphs: PairedGraphs | None = None,
) -> ExperimentRun:
    """Execute the paired pilot Monte Carlo and persist artifacts.

    Parameters
    ----------
    config :
        Validated experiment configuration.
    results_root :
        Parent directory for runs (default: repo ``results/``).
    run_id :
        Optional explicit run id; otherwise generated.
    figures_dir :
        Optional directory to copy PNG figures into (does not mutate
        historical docs figures unless the caller points there).
    graphs :
        Optional pre-built graphs (fixed-mode tests only). Ignored when
        ``mechanisms.fourbar.mode == 'population'``.

    Returns
    -------
    ExperimentRun
        Completed (or failed) run handle.

    Raises
    ------
    FileExistsError
        If ``run_id`` already exists under ``results_root``.
    TypeError
        If ``config`` is not an ``ExperimentConfig``.
    ValueError
        If sampling exhausts ``max_sample_attempts`` before collecting
        ``n_trials`` kept pairs.
    """
    if not isinstance(config, ExperimentConfig):
        raise TypeError("config must be an ExperimentConfig")

    root = Path(results_root) if results_root is not None else default_results_root()
    run = create_run(config, results_root=root, run_id=run_id)
    run.mark_running()

    try:
        fourbar_mode = config.mechanisms.fourbar_mode
        rng = np.random.default_rng(config.seed)
        algorithms = list(config.algorithms.names)
        cost_type = str(config.cost.type)
        validate_h = bool(config.algorithms.validate_heuristic)
        require_reachable = bool(config.trials.require_reachable)
        n_target = int(config.trials.n_trials)
        max_attempts = int(config.trials.max_sample_attempts)
        reach_algo = "dijkstra" if "dijkstra" in algorithms else algorithms[0]

        fixed_paired: PairedGraphs | None = None
        grid: PeriodicGrid2D | None = None
        if fourbar_mode == "fixed":
            fixed_paired = graphs if graphs is not None else build_paired_graphs(config)
            graph_meta: dict[str, Any] = {
                "fourbar_mode": "fixed",
                "gearbox_valid_nodes": fixed_paired.gearbox.valid_node_count,
                "fourbar_valid_nodes": fixed_paired.fourbar.valid_node_count,
                "grid_shape": list(config.graph.shape),
                "require_reachable": require_reachable,
                "cost_type": cost_type,
            }
        else:
            if graphs is not None:
                raise ValueError(
                    "graphs= is only supported for mechanisms.fourbar.mode == 'fixed'"
                )
            grid = _shared_grid(config)
            graph_meta = {
                "fourbar_mode": "population",
                "grid_shape": list(config.graph.shape),
                "require_reachable": require_reachable,
                "match_valid_nodes": bool(config.graph.match_valid_nodes),
                "match_relative_tol": float(config.graph.match_relative_tol),
                "cost_type": cost_type,
            }
        run.write_json("graph_meta", graph_meta)

        rows: list[dict[str, Any]] = []
        n_discarded_unreachable = 0
        n_discarded_task_sample = 0
        sample_attempts = 0
        kept = 0
        n_path_samples = int(config.trials.n_path_samples)
        path_algo = "astar" if "astar" in algorithms else algorithms[0]

        while kept < n_target:
            sample_attempts += 1
            if sample_attempts > max_attempts:
                raise ValueError(
                    f"failed to collect {n_target} reachable paired trials "
                    f"after {max_attempts} sampling attempts "
                    f"({kept} kept, {n_discarded_unreachable} unreachable, "
                    f"{n_discarded_task_sample} task-sample failures)"
                )

            if fourbar_mode == "fixed":
                assert fixed_paired is not None
                paired = fixed_paired
            else:
                assert grid is not None
                paired = _build_population_trial_graphs(config, rng, grid=grid)

            remaining = max_attempts - sample_attempts + 1
            probe = _try_one_paired_task(
                paired,
                rng,
                config,
                remaining_attempts=remaining,
            )
            if probe is None:
                n_discarded_task_sample += 1
                continue

            trial_rows = _records_for_task(
                probe,
                paired,
                algorithms=algorithms,
                cost_type=cost_type,
                validate_h=validate_h,
            )
            if require_reachable and not _pair_found(trial_rows, algorithm=reach_algo):
                n_discarded_unreachable += 1
                continue

            for record in trial_rows:
                record["trial_index"] = kept
            _annotate_trial_meta(
                trial_rows,
                paired=paired,
                fourbar_mode=fourbar_mode,
            )
            rows.extend(trial_rows)
            if kept < n_path_samples:
                kept_task = PairedTask(
                    trial_index=kept,
                    q_start=probe.q_start,
                    q_goal=probe.q_goal,
                    gearbox=probe.gearbox,
                    fourbar=probe.fourbar,
                    output_residual_tol=probe.output_residual_tol,
                )
                _write_path_sample(
                    run,
                    trial_index=kept,
                    paired=paired,
                    task=kept_task,
                    algorithm=path_algo,
                    cost_type=cost_type,
                )
            kept += 1
            if kept % 50 == 0 or kept == n_target:
                print(
                    f"pilot progress: kept={kept}/{n_target} "
                    f"discarded={n_discarded_unreachable} "
                    f"task_fail={n_discarded_task_sample} "
                    f"attempts={sample_attempts}",
                    flush=True,
                )

        run.append_jsonl("trials", rows)

        hq_rows = [
            {
                "trial_index": r.get("trial_index"),
                "mechanism": r.get("mechanism"),
                "algorithm": r.get("algorithm"),
                "cost_type": r.get("cost_type"),
                "heuristic_type": r.get("heuristic_type"),
                "heuristic_quality": r.get("heuristic_quality"),
            }
            for r in rows
            if r.get("heuristic_quality") is not None
        ]
        if hq_rows:
            run.write_json("heuristic_quality", {"reports": hq_rows})

        summary = summarize_trials(rows)
        summary["graph_meta"] = graph_meta
        summary["seed"] = int(config.seed)
        summary["n_trials_config"] = n_target
        summary["n_discarded_unreachable"] = n_discarded_unreachable
        summary["n_discarded_task_sample"] = n_discarded_task_sample
        summary["n_sample_attempts"] = sample_attempts
        summary["result_schema_version"] = RESULT_SCHEMA_VERSION
        summary["cost_type"] = cost_type
        run.write_json("summary", summary)
        _write_table_artifact(run, "summary_table", summary_table_csv(summary))
        _write_table_artifact(run, "residual_summary", _residual_summary_csv(rows))

        _write_plots(
            run,
            rows,
            figures_dir=None if figures_dir is None else Path(figures_dir),
        )
        run.mark_completed()
        # Derived viewer; regenerable via scripts/generate_monte_carlo_canvas.py.
        write_monte_carlo_canvas(run)
    except Exception as exc:
        run.mark_failed(f"{type(exc).__name__}: {exc}")
        raise

    return run
