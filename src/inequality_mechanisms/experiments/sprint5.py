"""Sprint Five path-quality paired study runner (S5-06 … S5-09).

Reuses the Sprint Four factorial harness with path-quality metrics,
equal-cost Dijkstra/A* comparison, diagnostic cards, and bootstrap CIs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from numpy.random import Generator

from inequality_mechanisms.experiments.config import ExperimentConfig
from inequality_mechanisms.experiments.pilot import (
    _annotate_trial_meta,
    _build_population_trial_graphs,
    _pair_found,
    _residual_summary_csv,
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
from inequality_mechanisms.experiments.schema import SPRINT5_RESULT_SCHEMA_VERSION
from inequality_mechanisms.experiments.setup import PairedGraphs, build_paired_graphs
from inequality_mechanisms.experiments.sprint4 import (
    _factorial_summary_table,
    _records_for_factorial_task,
    _savings_table_csv,
    _strip_private,
    _write_landscapes,
    _write_savings_plots,
)
from inequality_mechanisms.experiments.tasks import PairedTask
from inequality_mechanisms.metrics.bootstrap import (
    bootstrap_path_quality_metrics,
    bootstrap_primary_metrics,
)
from inequality_mechanisms.metrics.descriptors import (
    correlate_descriptors,
    graph_descriptors,
    mechanism_descriptors,
)
from inequality_mechanisms.metrics.equal_cost_paths import (
    compare_equal_cost_rows,
    equal_cost_summary_csv,
)
from inequality_mechanisms.metrics.expansions import (
    summarize_trials,
    summary_table_csv,
)
from inequality_mechanisms.metrics.path_metrics import PATH_LENGTH_CONVENTIONS
from inequality_mechanisms.metrics.path_quality import quality_config_metadata
from inequality_mechanisms.metrics.savings import (
    compute_savings_rows,
    summarize_savings,
)
from inequality_mechanisms.visualization.path_quality import (
    path_quality_summary_tables,
    plot_expansions_vs_quality,
    plot_metric_histogram,
    plot_paired_metric_scatter,
    select_representative_trials,
    write_path_quality_bundle,
)
from inequality_mechanisms.experiments.sprint5_canvas import write_sprint5_canvas


def run_sprint5(
    config: ExperimentConfig,
    *,
    results_root: Path | str | None = None,
    run_id: str | None = None,
    figures_dir: Path | str | None = None,
    graphs: PairedGraphs | None = None,
    rng: Generator | None = None,
) -> ExperimentRun:
    """Run the Sprint Five paired path-quality study.

    Parameters
    ----------
    config :
        Validated experiment configuration (includes ``path_quality``).
    results_root :
        Optional results directory override.
    run_id :
        Optional explicit run id.
    figures_dir :
        Optional directory to copy expansion PNGs into.
    graphs :
        Optional prebuilt fixed paired graphs.
    rng :
        Optional NumPy Generator; defaults to ``default_rng(config.seed)``.
    """
    import numpy as np

    root = default_results_root() if results_root is None else Path(results_root)
    run = create_run(
        config,
        results_root=root,
        run_id=run_id,
    )
    run.mark_running()
    if rng is None:
        rng = np.random.default_rng(int(config.seed))

    try:
        fourbar_mode = config.mechanisms.fourbar_mode
        algorithms = list(config.algorithms.names)
        cost_types = list(config.cost.resolved_types())
        validate_h = bool(config.algorithms.validate_heuristic)
        require_reachable = bool(config.trials.require_reachable)
        n_target = int(config.trials.n_trials)
        max_attempts = int(config.trials.max_sample_attempts)
        reach_algo = "dijkstra" if "dijkstra" in algorithms else algorithms[0]
        s4 = config.sprint4
        pq = config.path_quality
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
                "study": "sprint5_path_quality",
                "result_schema_version": SPRINT5_RESULT_SCHEMA_VERSION,
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
                "study": "sprint5_path_quality",
                "result_schema_version": SPRINT5_RESULT_SCHEMA_VERSION,
            }
        graph_meta.update(
            quality_config_metadata(pq.model_dump())
        )
        graph_meta["path_length_conventions"] = PATH_LENGTH_CONVENTIONS
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
        graphs_by_key: dict[tuple[Any, ...], Any] = {}

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
                path_quality=pq,
                result_schema_version=SPRINT5_RESULT_SCHEMA_VERSION,
            )
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

            graphs_by_key[(kept, "gearbox")] = paired.gearbox
            graphs_by_key[(kept, "fourbar")] = paired.fourbar

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
                    f"sprint5 progress: kept={kept}/{n_target} "
                    f"discarded={n_discarded_unreachable} "
                    f"attempts={sample_attempts}",
                    flush=True,
                )

        # Equal-cost comparison while private paths remain available.
        equal_cost = compare_equal_cost_rows(rows, graphs_by_key=graphs_by_key)
        run.write_json("equal_cost_path_degeneracy", equal_cost)
        _write_table_artifact(
            run, "equal_cost_path_degeneracy_table", equal_cost_summary_csv(equal_cost)
        )

        # Path-quality cards before stripping private paths.
        selections = select_representative_trials(
            rows,
            max_cards=int(pq.n_representative_cards),
        )
        pq_dir = run.path / "path_quality"
        card_meta = write_path_quality_bundle(
            pq_dir,
            selections=selections,
            graphs_by_key=graphs_by_key,
            revisit_exclusion_steps=int(pq.revisit_exclusion_steps),
        )
        run.register_output(
            "path_quality_cards",
            "path_quality/representative_trials.json",
        )
        run.write_json("path_quality_selection", card_meta)

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

        corr_expansions = correlate_descriptors(
            [
                {
                    "n_expanded": r.get("n_expanded"),
                    "beta": r.get("beta"),
                    "directness_ratio_x": r.get("directness_ratio_x"),
                    "cumulative_turning_x": r.get("cumulative_turning_x"),
                    "edge_cost_variance": r.get("edge_cost_variance"),
                }
                for r in public_rows
                if r.get("found") and r.get("algorithm") == "dijkstra"
            ],
            x_fields=(
                "beta",
                "directness_ratio_x",
                "cumulative_turning_x",
                "edge_cost_variance",
            ),
            y_field="n_expanded",
        )
        run.write_json(
            "descriptors",
            {
                "rows": descriptor_rows,
                "correlations": {"n_expanded": corr_expansions},
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
        boot_pq = bootstrap_path_quality_metrics(
            public_rows,
            n_bootstrap=int(s4.bootstrap_n_samples),
            seed=int(s4.bootstrap_seed),
            confidence=float(s4.bootstrap_confidence),
            algorithm="dijkstra",
        )
        run.write_json(
            "bootstrap_cis",
            {"sprint4_primary": boot, "path_quality": boot_pq},
        )

        # Standard Sprint Five figures.
        out = run.path / "outputs"
        out.mkdir(parents=True, exist_ok=True)
        figure_paths = {
            "paired_path_length_u": plot_paired_metric_scatter(
                public_rows, "path_length_u", out / "paired_path_length_u.png"
            ),
            "paired_path_length_q": plot_paired_metric_scatter(
                public_rows, "path_length_q", out / "paired_path_length_q.png"
            ),
            "paired_path_length_x": plot_paired_metric_scatter(
                public_rows, "path_length_x", out / "paired_path_length_x.png"
            ),
            "paired_directness_q": plot_paired_metric_scatter(
                public_rows, "directness_ratio_q", out / "paired_directness_q.png"
            ),
            "paired_directness_x": plot_paired_metric_scatter(
                public_rows, "directness_ratio_x", out / "paired_directness_x.png"
            ),
            "paired_turning_q": plot_paired_metric_scatter(
                public_rows, "cumulative_turning_q", out / "paired_turning_q.png"
            ),
            "paired_turning_x": plot_paired_metric_scatter(
                public_rows, "cumulative_turning_x", out / "paired_turning_x.png"
            ),
            "self_intersections_x_hist": plot_metric_histogram(
                public_rows,
                "self_intersections_x",
                out / "self_intersections_x_hist.png",
            ),
            "near_revisit_x_hist": plot_metric_histogram(
                public_rows,
                "near_revisit_distance_x",
                out / "near_revisit_x_hist.png",
            ),
            "expansions_vs_directness_x": plot_expansions_vs_quality(
                public_rows,
                "directness_ratio_x",
                out / "expansions_vs_directness_x.png",
            ),
            "expansions_vs_turning_x": plot_expansions_vs_quality(
                public_rows,
                "cumulative_turning_x",
                out / "expansions_vs_turning_x.png",
            ),
        }
        for name, path in figure_paths.items():
            run.register_output(name, path.relative_to(run.path).as_posix())

        tables = path_quality_summary_tables(public_rows)
        for name, csv_text in tables.items():
            _write_table_artifact(run, name, csv_text)

        # Metric / tolerance summary table.
        metric_cfg = {
            "result_schema_version": SPRINT5_RESULT_SCHEMA_VERSION,
            "path_quality": pq.model_dump(),
            "path_length_conventions": PATH_LENGTH_CONVENTIONS,
            "undefined_counts": boot_pq.get("undefined_counts", {}),
        }
        run.write_json("metric_configuration", metric_cfg)

        summary = summarize_trials(public_rows)
        summary["graph_meta"] = graph_meta
        summary["seed"] = int(config.seed)
        summary["n_trials_config"] = n_target
        summary["n_discarded_unreachable"] = n_discarded_unreachable
        summary["n_discarded_task_sample"] = n_discarded_task_sample
        summary["n_sample_attempts"] = sample_attempts
        summary["result_schema_version"] = SPRINT5_RESULT_SCHEMA_VERSION
        summary["cost_types"] = cost_types
        summary["study"] = "sprint5_path_quality"
        summary["savings"] = savings_summary
        summary["equal_cost"] = {
            "n_matched_pairs": equal_cost["n_matched_pairs"],
            "n_same_optimal_cost": equal_cost["n_same_optimal_cost"],
            "n_diff_node_path_same_cost": equal_cost["n_diff_node_path_same_cost"],
        }
        summary["path_quality_cards"] = card_meta
        run.write_json("summary", summary)
        _write_table_artifact(run, "summary_table", summary_table_csv(summary))
        _write_table_artifact(
            run, "factorial_summary_table", _factorial_summary_table(public_rows)
        )
        _write_table_artifact(
            run, "residual_summary", _residual_summary_csv(public_rows)
        )
        _write_table_artifact(
            run,
            "run_summary",
            _run_summary_csv(summary),
        )

        _write_plots(
            run,
            public_rows,
            figures_dir=None if figures_dir is None else Path(figures_dir),
        )
        run.mark_completed()
        # Derived viewer; regenerable via scripts/generate_sprint5_canvas.py.
        write_sprint5_canvas(run)
    except Exception as exc:
        run.mark_failed(f"{type(exc).__name__}: {exc}")
        raise

    return run


def _run_summary_csv(summary: dict[str, Any]) -> str:
    import csv
    import io

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["key", "value"])
    for key in (
        "study",
        "result_schema_version",
        "seed",
        "n_trials_config",
        "n_discarded_unreachable",
        "n_sample_attempts",
    ):
        writer.writerow([key, summary.get(key)])
    return buf.getvalue()
