"""Sprint Four factorial attribution runner (S4-06–S4-10).

Runs ``{gearbox, fourbar} × cost.types × {dijkstra, astar}`` on matched
paired tasks with a fixed physical U-graph per trial, then writes savings
plots, landscape bundles, descriptors, and paired bootstrap CIs.
"""

from __future__ import annotations

import csv
import io
import math
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from numpy.random import Generator

from inequality_mechanisms.diagnostics.plots import basin_metrics
from inequality_mechanisms.experiments.canvas import write_monte_carlo_canvas
from inequality_mechanisms.experiments.config import (
    ExperimentConfig,
)
from inequality_mechanisms.experiments.pilot import (
    _annotate_trial_meta,
    _build_population_trial_graphs,
    _finite_cost,
    _pair_found,
    _residual_summary_csv,
    _run_search,
    _shared_grid,
    _try_one_paired_task,
    _write_path_sample,
    _write_plots,
    _write_table_artifact,
)
from inequality_mechanisms.experiments.registry import (
    ExperimentRun,
    create_run,
    default_results_root,
)
from inequality_mechanisms.experiments.schema import RESULT_SCHEMA_VERSION
from inequality_mechanisms.experiments.setup import PairedGraphs, build_paired_graphs
from inequality_mechanisms.experiments.tasks import PairedTask, SelectedPreimages
from inequality_mechanisms.graphs.costs import build_edge_cost
from inequality_mechanisms.graphs.validation import ConstrainedInputGraph
from inequality_mechanisms.metrics.bootstrap import bootstrap_primary_metrics
from inequality_mechanisms.metrics.descriptors import (
    correlate_descriptors,
    graph_descriptors,
    mechanism_descriptors,
)
from inequality_mechanisms.metrics.expansions import (
    normalized_expansion,
    summarize_trials,
    summary_table_csv,
)
from inequality_mechanisms.metrics.path_metrics import compute_path_metrics
from inequality_mechanisms.metrics.savings import (
    compute_savings_rows,
    summarize_savings,
)
from inequality_mechanisms.search.cost_to_go import reverse_dijkstra
from inequality_mechanisms.search.heuristic_quality import (
    heuristic_quality_report,
    validate_heuristic_admissible,
)
from inequality_mechanisms.search.objectives import resolve_planning_objective
from inequality_mechanisms.visualization.landscape import write_landscape_bundle
from inequality_mechanisms.visualization.savings import (
    plot_astar_vs_dijkstra_expansions,
    plot_edge_cost_variance_vs_savings,
    plot_heuristic_strength_vs_savings,
    plot_path_length_vs_savings,
    plot_savings_by_mechanism_cost,
)


def _edge_cost_variance(graph: ConstrainedInputGraph, cost_type: str) -> float:
    edge_cost = build_edge_cost(graph, cost_type)
    vals = [float(edge_cost(a, b)) for a, b in graph.iter_edges()]
    if len(vals) < 2:
        return 0.0
    return float(np.var(np.asarray(vals, dtype=np.float64)))


def _factorial_search_record(
    *,
    trial: PairedTask,
    mechanism: str,
    algorithm: str,
    graph: ConstrainedInputGraph,
    preimages: SelectedPreimages,
    cost_type: str,
    validate_heuristic: bool,
    record_expanded: bool = False,
    path_quality: Any | None = None,
    result_schema_version: str | None = None,
) -> dict[str, Any]:
    """Run one factorial search cell with P1 instrumentation."""
    from inequality_mechanisms.metrics.path_quality import (
        attach_path_quality_fields,
        compute_path_quality,
        path_quality_null_fields,
    )

    n_valid = graph.valid_node_count
    objective = resolve_planning_objective(
        graph,
        preimages.goal_node_id,
        cost_type,
        heuristic_name="zero" if algorithm == "dijkstra" else None,
    )
    recorded_heuristic = (
        "zero" if algorithm == "dijkstra" else objective.heuristic_name
    )
    schema = (
        RESULT_SCHEMA_VERSION
        if result_schema_version is None
        else str(result_schema_version)
    )
    record: dict[str, Any] = {
        "result_schema_version": schema,
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
        "runtime_s": None,
        "n_reachable_nodes": None,
        "beta": None,
        "eta_reachable": None,
        "edge_cost_variance": None,
        "failure_reason": None,
        "heuristic_validation": None,
        "heuristic_quality": None,
        "mean_heuristic_strength": None,
    }
    if path_quality is not None:
        record.update(path_quality_null_fields())

    t0 = time.perf_counter()
    result = _run_search(
        graph,
        preimages.start_node_id,
        preimages.goal_node_id,
        algorithm,
        objective,
        record_expanded=record_expanded
        or bool(validate_heuristic and algorithm == "astar"),
    )
    record["runtime_s"] = float(time.perf_counter() - t0)

    # Distance field from start under this edge metric (symmetric costs).
    ctg_start = reverse_dijkstra(
        graph, preimages.start_node_id, edge_cost=objective.edge_cost
    )
    n_reach = sum(1 for c in ctg_start.costs.values() if math.isfinite(float(c)))
    record["n_reachable_nodes"] = int(n_reach)
    record["edge_cost_variance"] = _edge_cost_variance(graph, cost_type)

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
            record["mean_heuristic_strength"] = hq.mean_strength

    record["n_expanded"] = int(result.n_expanded)
    record["n_generated"] = int(result.n_generated)
    record["n_stale"] = int(result.n_stale)
    record["n_path_edges"] = int(result.n_path_edges)
    opt = _finite_cost(result.cost)
    record["optimal_cost"] = opt
    record["cost"] = opt

    if result.found:
        record["found"] = True
        metrics = compute_path_metrics(
            graph, result.path, optimal_cost=float(result.cost)
        )
        record["n_path_edges"] = int(metrics.n_path_edges)
        record["path_length_u"] = float(metrics.path_length_u)
        record["path_length_q"] = float(metrics.path_length_q)
        record["path_length_x"] = float(metrics.path_length_x)
        if path_quality is not None:
            quality = compute_path_quality(
                graph,
                result.path,
                optimal_cost=float(result.cost),
                revisit_exclusion_steps=int(path_quality.revisit_exclusion_steps),
                revisit_threshold_q=float(path_quality.revisit_threshold_q),
                revisit_threshold_x=float(path_quality.revisit_threshold_x),
            )
            attach_path_quality_fields(record, quality)
        if n_valid > 0:
            record["rho_expanded"] = normalized_expansion(result.n_expanded, n_valid)
        eta, beta = basin_metrics(
            ctg_start.costs,
            c_star=float(result.cost),
            n_expanded=int(result.n_expanded),
        )
        record["eta_reachable"] = float(eta)
        record["beta"] = float(beta)
        # Attach expanded path for landscape use (not serialized as huge lists
        # unless requested); store on a private key stripped before JSONL.
        record["_path"] = list(result.path)
        record["_expanded"] = list(result.expanded_nodes)
    else:
        if record["failure_reason"] is None:
            record["failure_reason"] = "unreachable"

    return record


def _records_for_factorial_task(
    task: PairedTask,
    paired: PairedGraphs,
    *,
    algorithms: list[str],
    cost_types: list[str],
    validate_h: bool,
    record_expanded_for_landscape: bool,
    path_quality: Any | None = None,
    result_schema_version: str | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for mechanism, graph, preimages in (
        ("gearbox", paired.gearbox, task.gearbox),
        ("fourbar", paired.fourbar, task.fourbar),
    ):
        for cost_type in cost_types:
            for algorithm in algorithms:
                rows.append(
                    _factorial_search_record(
                        trial=task,
                        mechanism=mechanism,
                        algorithm=algorithm,
                        graph=graph,
                        preimages=preimages,
                        cost_type=cost_type,
                        validate_heuristic=validate_h,
                        record_expanded=record_expanded_for_landscape
                        and algorithm == "dijkstra",
                        path_quality=path_quality,
                        result_schema_version=result_schema_version,
                    )
                )
    return rows


def _strip_private(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for row in rows:
        cleaned.append({k: v for k, v in row.items() if not str(k).startswith("_")})
    return cleaned


def _factorial_summary_table(rows: list[dict[str, Any]]) -> str:
    """CSV grouped by algorithm × mechanism × cost_type."""
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    expansions: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    rhos: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for row in rows:
        key = (
            str(row["algorithm"]),
            str(row["mechanism"]),
            str(row.get("cost_type", "")),
        )
        if key not in groups:
            groups[key] = {
                "algorithm": key[0],
                "mechanism": key[1],
                "cost_type": key[2],
                "n_trials": 0,
                "n_found": 0,
                "n_unreachable": 0,
            }
        g = groups[key]
        g["n_trials"] += 1
        if row.get("found"):
            g["n_found"] += 1
            expansions[key].append(int(row["n_expanded"]))
            if row.get("rho_expanded") is not None:
                rhos[key].append(float(row["rho_expanded"]))
        else:
            g["n_unreachable"] += 1

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "algorithm",
            "mechanism",
            "cost_type",
            "n_trials",
            "n_found",
            "n_unreachable",
            "median_n_expanded",
            "mean_rho_expanded",
        ]
    )
    for key in sorted(groups.keys()):
        g = groups[key]
        med = None
        if expansions[key]:
            med = float(np.median(np.asarray(expansions[key], dtype=np.float64)))
        mean_rho = None
        if rhos[key]:
            mean_rho = float(np.mean(np.asarray(rhos[key], dtype=np.float64)))
        writer.writerow(
            [
                g["algorithm"],
                g["mechanism"],
                g["cost_type"],
                g["n_trials"],
                g["n_found"],
                g["n_unreachable"],
                med,
                mean_rho,
            ]
        )
    return buf.getvalue()


def _savings_table_csv(savings_rows: list[dict[str, Any]]) -> str:
    if not savings_rows:
        return "trial_index,mechanism,cost_type,s_a,delta_n_a\n"
    keys = list(savings_rows[0].keys())
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=keys)
    writer.writeheader()
    for row in savings_rows:
        writer.writerow(row)
    return buf.getvalue()


def _write_savings_plots(run: ExperimentRun, savings_rows: list[dict[str, Any]]) -> None:
    out = run.outputs_dir
    plots = {
        "astar_vs_dijkstra": plot_astar_vs_dijkstra_expansions(
            savings_rows, out / "astar_vs_dijkstra.png"
        ),
        "savings_by_mechanism_cost": plot_savings_by_mechanism_cost(
            savings_rows, out / "savings_by_mechanism_cost.png"
        ),
        "heuristic_strength_vs_savings": plot_heuristic_strength_vs_savings(
            savings_rows, out / "heuristic_strength_vs_savings.png"
        ),
        "edge_cost_variance_vs_savings": plot_edge_cost_variance_vs_savings(
            savings_rows, out / "edge_cost_variance_vs_savings.png"
        ),
        "path_length_vs_savings": plot_path_length_vs_savings(
            savings_rows, out / "path_length_vs_savings.png"
        ),
    }
    for name, path in plots.items():
        run.register_output(name, path.relative_to(run.path).as_posix())


def _write_landscapes(
    run: ExperimentRun,
    *,
    kept_payloads: list[tuple[PairedTask, PairedGraphs, list[dict[str, Any]]]],
    landscape_costs: list[str],
    n_landscape_trials: int,
) -> list[dict[str, Any]]:
    metrics_list: list[dict[str, Any]] = []
    for task, paired, rows in kept_payloads[: int(n_landscape_trials)]:
        for mechanism, graph, preimages in (
            ("gearbox", paired.gearbox, task.gearbox),
            ("fourbar", paired.fourbar, task.fourbar),
        ):
            for cost_type in landscape_costs:
                # Prefer Dijkstra row with recorded expansions / path.
                candidates = [
                    r
                    for r in rows
                    if r.get("mechanism") == mechanism
                    and r.get("cost_type") == cost_type
                    and r.get("algorithm") == "dijkstra"
                    and r.get("found")
                ]
                if not candidates:
                    continue
                row = candidates[0]
                path = row.get("_path") or []
                expanded = row.get("_expanded") or []
                if not path:
                    continue
                # Re-run with record_expanded if missing.
                if not expanded:
                    obj = resolve_planning_objective(
                        graph, preimages.goal_node_id, cost_type
                    )
                    res = _run_search(
                        graph,
                        preimages.start_node_id,
                        preimages.goal_node_id,
                        "dijkstra",
                        obj,
                        record_expanded=True,
                    )
                    path = list(res.path)
                    expanded = list(res.expanded_nodes)
                dest = (
                    run.path
                    / "landscape"
                    / f"trial_{int(task.trial_index):04d}"
                    / mechanism
                    / cost_type
                )
                metrics = write_landscape_bundle(
                    graph,
                    start=preimages.start_node_id,
                    goal=preimages.goal_node_id,
                    path=path,
                    expanded=expanded,
                    cost_type=cost_type,
                    out_dir=dest,
                    c_star=float(row["optimal_cost"])
                    if row.get("optimal_cost") is not None
                    else None,
                )
                metrics["trial_index"] = int(task.trial_index)
                metrics["mechanism"] = mechanism
                metrics_list.append(metrics)
                metrics_rel = (
                    dest / "landscape_metrics.json"
                ).relative_to(run.path).as_posix()
                run.register_output(
                    f"landscape_t{int(task.trial_index):04d}_{mechanism}_{cost_type}",
                    metrics_rel,
                )
    return metrics_list


def run_sprint4(
    config: ExperimentConfig,
    *,
    results_root: Path | str | None = None,
    run_id: str | None = None,
    figures_dir: Path | str | None = None,
    graphs: PairedGraphs | None = None,
) -> ExperimentRun:
    """Execute the Sprint Four mech × cost × algorithm factorial study.

    Parameters
    ----------
    config :
        Validated experiment configuration. Uses ``cost.types`` when set;
        otherwise all three registered costs.
    results_root, run_id, figures_dir, graphs :
        Same semantics as ``run_pilot``.

    Returns
    -------
    ExperimentRun
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
        if config.cost.types is not None:
            cost_types = list(config.cost.resolved_types())
        else:
            cost_types = ["uniform", "input_euclidean", "output_euclidean"]
        validate_h = bool(config.algorithms.validate_heuristic)
        require_reachable = bool(config.trials.require_reachable)
        n_target = int(config.trials.n_trials)
        max_attempts = int(config.trials.max_sample_attempts)
        reach_algo = "dijkstra" if "dijkstra" in algorithms else algorithms[0]
        s4 = config.sprint4
        n_landscape = int(s4.n_landscape_trials)
        landscape_costs = list(s4.landscape_costs) or ["output_euclidean"]

        fixed_paired: PairedGraphs | None = None
        grid = None
        if fourbar_mode == "fixed":
            fixed_paired = graphs if graphs is not None else build_paired_graphs(config)
            graph_meta: dict[str, Any] = {
                "fourbar_mode": "fixed",
                "gearbox_valid_nodes": fixed_paired.gearbox.valid_node_count,
                "fourbar_valid_nodes": fixed_paired.fourbar.valid_node_count,
                "grid_shape": list(config.graph.shape),
                "require_reachable": require_reachable,
                "cost_types": cost_types,
                "study": "sprint4_factorial",
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
                "cost_types": cost_types,
                "study": "sprint4_factorial",
            }
        run.write_json("graph_meta", graph_meta)

        rows: list[dict[str, Any]] = []
        kept_payloads: list[
            tuple[PairedTask, PairedGraphs, list[dict[str, Any]]]
        ] = []
        n_discarded_unreachable = 0
        n_discarded_task_sample = 0
        sample_attempts = 0
        kept = 0
        n_path_samples = int(config.trials.n_path_samples)
        path_algo = "astar" if "astar" in algorithms else algorithms[0]
        descriptor_rows: list[dict[str, Any]] = []

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
                paired, rng, config, remaining_attempts=remaining
            )
            if probe is None:
                n_discarded_task_sample += 1
                continue

            need_expanded = kept < n_landscape
            trial_rows = _records_for_factorial_task(
                probe,
                paired,
                algorithms=algorithms,
                cost_types=cost_types,
                validate_h=validate_h,
                record_expanded_for_landscape=need_expanded,
            )
            # Reachability gate uses output_euclidean Dijkstra when available.
            gate_rows = [
                r
                for r in trial_rows
                if r.get("cost_type") == "output_euclidean"
            ] or trial_rows
            if require_reachable and not _pair_found(
                gate_rows, algorithm=reach_algo
            ):
                n_discarded_unreachable += 1
                continue

            for record in trial_rows:
                record["trial_index"] = kept
            _annotate_trial_meta(
                trial_rows, paired=paired, fourbar_mode=fourbar_mode
            )

            # Mechanism / graph descriptors once per mechanism for this trial.
            for mechanism, graph, preimages in (
                ("gearbox", paired.gearbox, probe.gearbox),
                ("fourbar", paired.fourbar, probe.fourbar),
            ):
                mech = (
                    paired.gearbox_mechanism
                    if mechanism == "gearbox"
                    else paired.fourbar_mechanism
                )
                mdesc = mechanism_descriptors(
                    mech,
                    eps=float(s4.gain_epsilon),
                    high_threshold=float(s4.high_gain_threshold),
                    reversal_eps=float(s4.near_reversal_epsilon),
                )
                # Use Dijkstra / output_euclidean row for graph descriptors when present.
                ref = next(
                    (
                        r
                        for r in trial_rows
                        if r.get("mechanism") == mechanism
                        and r.get("algorithm") == "dijkstra"
                        and r.get("cost_type") == "output_euclidean"
                        and r.get("found")
                    ),
                    None,
                )
                gdesc = graph_descriptors(
                    graph,
                    cost_type="output_euclidean",
                    start=preimages.start_node_id,
                    goal=preimages.goal_node_id,
                    c_star=None if ref is None else ref.get("optimal_cost"),
                    n_expanded=None if ref is None else ref.get("n_expanded"),
                )
                descriptor_rows.append(
                    {
                        "trial_index": kept,
                        "mechanism": mechanism,
                        **mdesc,
                        **{f"graph_{k}": v for k, v in gdesc.items()},
                    }
                )

            kept_task = PairedTask(
                trial_index=kept,
                q_start=probe.q_start,
                q_goal=probe.q_goal,
                gearbox=probe.gearbox,
                fourbar=probe.fourbar,
                output_residual_tol=probe.output_residual_tol,
            )
            kept_payloads.append((kept_task, paired, trial_rows))
            rows.extend(trial_rows)

            if kept < n_path_samples:
                _write_path_sample(
                    run,
                    trial_index=kept,
                    paired=paired,
                    task=kept_task,
                    algorithm=path_algo,
                    cost_type="output_euclidean",
                )
            kept += 1
            if kept % 25 == 0 or kept == n_target:
                print(
                    f"sprint4 progress: kept={kept}/{n_target} "
                    f"discarded={n_discarded_unreachable} "
                    f"attempts={sample_attempts}",
                    flush=True,
                )

        public_rows = _strip_private(rows)
        run.append_jsonl("trials", public_rows)

        savings_rows = compute_savings_rows(public_rows)
        savings_summary = summarize_savings(savings_rows)
        run.write_json("savings", {"rows": savings_rows, "summary": savings_summary})
        _write_table_artifact(run, "savings_table", _savings_table_csv(savings_rows))
        _write_savings_plots(run, savings_rows)

        landscape_metrics = _write_landscapes(
            run,
            kept_payloads=kept_payloads,
            landscape_costs=landscape_costs,
            n_landscape_trials=n_landscape,
        )
        run.write_json("landscape_metrics", {"bundles": landscape_metrics})

        # Correlations (S4-09).
        corr_expansions = correlate_descriptors(
            [
                {
                    "n_expanded": r.get("n_expanded"),
                    "beta": r.get("beta"),
                    "edge_cost_variance": r.get("edge_cost_variance"),
                    "rho_epsilon": next(
                        (
                            d.get("rho_epsilon")
                            for d in descriptor_rows
                            if d.get("trial_index") == r.get("trial_index")
                            and d.get("mechanism") == r.get("mechanism")
                        ),
                        None,
                    ),
                    "preimage_count": next(
                        (
                            d.get("graph_n_discrete_output_preimages")
                            for d in descriptor_rows
                            if d.get("trial_index") == r.get("trial_index")
                            and d.get("mechanism") == r.get("mechanism")
                        ),
                        None,
                    ),
                }
                for r in public_rows
                if r.get("found") and r.get("algorithm") == "dijkstra"
            ],
            x_fields=("beta", "rho_epsilon", "preimage_count", "edge_cost_variance"),
            y_field="n_expanded",
        )
        corr_savings = correlate_descriptors(
            savings_rows,
            x_fields=("mean_heuristic_strength", "edge_cost_variance", "beta"),
            y_field="s_a",
        )
        run.write_json(
            "descriptors",
            {
                "rows": descriptor_rows,
                "correlations": {
                    "n_expanded": corr_expansions,
                    "s_a": corr_savings,
                },
            },
        )

        boot = bootstrap_primary_metrics(
            public_rows,
            savings_rows,
            n_bootstrap=int(s4.bootstrap_n_samples),
            seed=int(s4.bootstrap_seed),
            confidence=float(s4.bootstrap_confidence),
            algorithm="dijkstra",
        )
        run.write_json("bootstrap_cis", boot)

        summary = summarize_trials(public_rows)
        summary["graph_meta"] = graph_meta
        summary["seed"] = int(config.seed)
        summary["n_trials_config"] = n_target
        summary["n_discarded_unreachable"] = n_discarded_unreachable
        summary["n_discarded_task_sample"] = n_discarded_task_sample
        summary["n_sample_attempts"] = sample_attempts
        summary["result_schema_version"] = RESULT_SCHEMA_VERSION
        summary["cost_types"] = cost_types
        summary["study"] = "sprint4_factorial"
        summary["savings"] = savings_summary
        run.write_json("summary", summary)
        _write_table_artifact(run, "summary_table", summary_table_csv(summary))
        _write_table_artifact(
            run, "factorial_summary_table", _factorial_summary_table(public_rows)
        )
        _write_table_artifact(
            run, "residual_summary", _residual_summary_csv(public_rows)
        )

        _write_plots(
            run,
            public_rows,
            figures_dir=None if figures_dir is None else Path(figures_dir),
        )
        run.mark_completed()
        write_monte_carlo_canvas(run)
    except Exception as exc:
        run.mark_failed(f"{type(exc).__name__}: {exc}")
        raise

    return run
