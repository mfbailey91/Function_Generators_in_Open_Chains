"""Sprint Six runner — equivalence, resolution calibration, hierarchical MC."""

from __future__ import annotations

import csv
import io
import time
from pathlib import Path
from typing import Any

import numpy as np
from numpy.random import Generator

from inequality_mechanisms.experiments.config import ExperimentConfig
from inequality_mechanisms.experiments.pilot import (
    _finite_cost,
    _run_search,
    _write_path_sample,
    _write_plots,
    _write_table_artifact,
)
from inequality_mechanisms.experiments.registry import (
    ExperimentRun,
    create_run,
    default_results_root,
)
from inequality_mechanisms.experiments.resolution import (
    GRID_ANISOTROPY_LIMITATION,
    select_production_resolution,
)
from inequality_mechanisms.experiments.sample_bank import (
    build_sample_bank_from_config,
)
from inequality_mechanisms.experiments.schema import SPRINT6_RESULT_SCHEMA_VERSION
from inequality_mechanisms.experiments.setup import (
    PairedGraphs,
    build_paired_graphs,
    build_paired_graphs_from_parts,
)
from inequality_mechanisms.experiments.sprint6_canvas import write_sprint6_canvas
from inequality_mechanisms.experiments.tasks import (
    PairedTask,
    SelectedPreimages,
    default_snap_tol,
    discrete_preimage_candidates,
    select_preimage,
)
from inequality_mechanisms.graphs.grid import PeriodicGrid2D
from inequality_mechanisms.graphs.validation import ConstrainedInputGraph
from inequality_mechanisms.mechanisms.base import Mechanism
from inequality_mechanisms.mechanisms.equivalence import (
    equivalence_summary_rows,
    verify_matched_graphs,
    verify_rms_match,
    verify_span_match,
    verify_tv_match,
)
from inequality_mechanisms.mechanisms.gearbox import EquivalentGearbox
from inequality_mechanisms.metrics.expansions import summarize_trials
from inequality_mechanisms.metrics.hierarchical_bootstrap import (
    assert_not_task_level_iid,
    hierarchical_bootstrap_ci,
    mechanism_level_effects,
    required_mechanism_count,
    sequential_precision_report,
)
from inequality_mechanisms.metrics.path_metrics import compute_path_metrics
from inequality_mechanisms.search.objectives import resolve_planning_objective
from inequality_mechanisms.spaces.limits import OutputJointLimits


def _materialize_preimages(
    graph: ConstrainedInputGraph,
    q_start: np.ndarray,
    q_goal: np.ndarray,
    *,
    policy: str,
    rng: Generator,
    snap_tol: float,
) -> SelectedPreimages | None:
    start_cands, n_start_cont = discrete_preimage_candidates(
        graph, q_start, snap_tol=snap_tol
    )
    goal_cands, n_goal_cont = discrete_preimage_candidates(
        graph, q_goal, snap_tol=snap_tol
    )
    if not start_cands or not goal_cands:
        return None
    start_id = select_preimage(start_cands, policy=policy, rng=rng)  # type: ignore[arg-type]
    goal_id = select_preimage(goal_cands, policy=policy, rng=rng)  # type: ignore[arg-type]
    i0, i1 = graph.grid.indices_from_id(start_id)
    j0, j1 = graph.grid.indices_from_id(goal_id)
    return SelectedPreimages(
        mechanism_name=str(graph.mechanism.name),
        start_node_id=int(start_id),
        goal_node_id=int(goal_id),
        start_u=tuple(float(x) for x in graph.grid.coordinates(i0, i1)),
        goal_u=tuple(float(x) for x in graph.grid.coordinates(j0, j1)),
        n_start_candidates=len(start_cands),
        n_goal_candidates=len(goal_cands),
    )


def _search_record(
    *,
    mechanism_id: str,
    task_id: str,
    trial_index: int,
    mechanism: str,
    algorithm: str,
    cost_type: str,
    graph: ConstrainedInputGraph,
    preimages: SelectedPreimages,
    q_start: list[float],
    q_goal: list[float],
    baseline_label: str,
    shape_n: int,
) -> dict[str, Any]:
    objective = resolve_planning_objective(
        graph,
        preimages.goal_node_id,
        cost_type,
        heuristic_name="zero" if algorithm == "dijkstra" else None,
    )
    t0 = time.perf_counter()
    result = _run_search(
        graph,
        preimages.start_node_id,
        preimages.goal_node_id,
        algorithm,
        objective,
    )
    runtime = float(time.perf_counter() - t0)
    n_valid = int(graph.valid_node_count)
    record: dict[str, Any] = {
        "result_schema_version": SPRINT6_RESULT_SCHEMA_VERSION,
        "mechanism_id": mechanism_id,
        "task_id": task_id,
        "trial_index": trial_index,
        "mechanism": mechanism,
        "baseline_label": baseline_label,
        "algorithm": algorithm,
        "cost_type": cost_type,
        "shape_n": int(shape_n),
        "q_start": list(q_start),
        "q_goal": list(q_goal),
        "preimages": preimages.to_dict(),
        "n_valid_nodes": n_valid,
        "n_components": int(graph.connected_component_count()),
        "found": False,
        "n_expanded": int(result.n_expanded),
        "n_generated": int(result.n_generated),
        "n_stale": int(result.n_stale),
        "n_path_edges": int(result.n_path_edges),
        "path_length_u": None,
        "path_length_q": None,
        "path_length_x": None,
        "optimal_cost": _finite_cost(result.cost),
        "rho_expanded": None,
        "runtime_s": runtime,
        "failure_reason": None,
    }
    if result.found:
        record["found"] = True
        metrics = compute_path_metrics(
            graph, result.path, optimal_cost=float(result.cost)
        )
        record["n_path_edges"] = int(metrics.n_path_edges)
        record["path_length_u"] = float(metrics.path_length_u)
        record["path_length_q"] = float(metrics.path_length_q)
        record["path_length_x"] = float(metrics.path_length_x)
        if n_valid > 0:
            record["rho_expanded"] = float(result.n_expanded) / float(n_valid)
    else:
        record["failure_reason"] = "unreachable"
    return record


def _graphs_at_shape(
    config: ExperimentConfig,
    *,
    shape_n: int,
    fourbar: Mechanism,
    gearbox: Mechanism,
    limits: OutputJointLimits,
) -> PairedGraphs:
    graph_cfg = config.graph
    ranges = None if graph_cfg.ranges is None else graph_cfg.ranges
    grid = PeriodicGrid2D(
        (int(shape_n), int(shape_n)),
        ranges=ranges,
        wrap=graph_cfg.wrap,
    )
    return build_paired_graphs_from_parts(
        grid=grid,
        limits=limits,
        gearbox_mechanism=gearbox,
        fourbar_mechanism=fourbar,
        edge_samples=int(graph_cfg.edge_samples),
    )


def _equivalence_checks(paired: PairedGraphs) -> dict[str, Any]:
    gb = paired.gearbox_mechanism
    fb = paired.fourbar_mechanism
    report: dict[str, Any] = {
        "graph_match": verify_matched_graphs(paired.gearbox, paired.fourbar),
    }
    if isinstance(gb, EquivalentGearbox):
        if gb.matching_rule == "span":
            report["span"] = verify_span_match(gb, fb)
        elif gb.matching_rule == "total_variation":
            report["total_variation"] = verify_tv_match(gb, fb)
        elif gb.matching_rule == "rms_gain":
            report["rms_gain"] = verify_rms_match(gb, fb)
        report["matching_rule"] = gb.matching_rule
        report["baseline_label"] = gb.name
        report["ratios"] = gb.ratios.tolist()
        report["provenance"] = gb.provenance
    else:
        report["matching_rule"] = None
        report["baseline_label"] = "unit_gearbox"
    return report


def _rows_to_csv(rows: list[dict[str, Any]], fieldnames: list[str]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()


def run_sprint6(
    config: ExperimentConfig,
    *,
    results_root: Path | str | None = None,
    run_id: str | None = None,
    mode: str = "full",
) -> ExperimentRun:
    """Execute Sprint Six equivalence / resolution / hierarchical study.

    Parameters
    ----------
    config :
        Validated experiment configuration (``sprint6`` block used).
    results_root :
        Parent directory for runs.
    run_id :
        Optional explicit run id.
    mode :
        ``full`` (default), ``equivalence``, ``resolution``, or ``monte_carlo``.
    """
    if not isinstance(config, ExperimentConfig):
        raise TypeError("config must be an ExperimentConfig")
    if mode not in {"full", "equivalence", "resolution", "monte_carlo"}:
        raise ValueError(f"unknown mode {mode!r}")

    root = Path(results_root) if results_root is not None else default_results_root()
    run = create_run(config, results_root=root, run_id=run_id)
    run.mark_running()

    try:
        s6 = config.sprint6
        rng = np.random.default_rng(config.seed)
        algorithms = list(config.algorithms.names)
        cost_types = config.cost.resolved_types()
        policy = config.trials.preimage_policy

        # --- Sample bank (S6-19) ---
        bank = build_sample_bank_from_config(config, rng=rng)
        run.write_json("sample_bank", bank.to_dict())

        paired_fixed: PairedGraphs | None = None
        if config.mechanisms.fourbar_mode == "fixed":
            paired_fixed = build_paired_graphs(config)

        equivalence_report: dict[str, Any] = {}
        if paired_fixed is not None and (
            mode in {"full", "equivalence"} or s6.verify_equivalence
        ):
            equivalence_report = _equivalence_checks(paired_fixed)
            if s6.verify_equivalence:
                for key in ("span", "total_variation", "rms_gain", "graph_match"):
                    sub = equivalence_report.get(key)
                    if isinstance(sub, dict) and sub.get("ok") is False:
                        raise ValueError(f"equivalence check failed: {key}={sub}")

        run.write_json("equivalence", equivalence_report)
        run.write_json(
            "equivalence_summary",
            {"rows": equivalence_summary_rows()},
        )

        shapes = (
            list(s6.resolution_shapes)
            if mode in {"full", "resolution"}
            else [int(config.graph.shape[0])]
        )
        if mode == "equivalence":
            shapes = [int(config.graph.shape[0])]
        if mode == "monte_carlo":
            shapes = [int(config.graph.shape[0])]

        all_rows: list[dict[str, Any]] = []
        resolution_rows: list[dict[str, Any]] = []
        trial_index = 0
        exclusions: list[dict[str, Any]] = []
        n_path_samples = int(config.trials.n_path_samples)
        path_samples_written = 0
        path_sample_shape = int(config.graph.shape[0])
        path_algo = "astar" if "astar" in algorithms else algorithms[0]
        path_cost = (
            "output_euclidean"
            if "output_euclidean" in cost_types
            else cost_types[0]
        )

        for shape_n in shapes:
            t_build0 = time.perf_counter()
            if paired_fixed is not None:
                limits = paired_fixed.limits
                fourbar = paired_fixed.fourbar_mechanism
                gearbox = paired_fixed.gearbox_mechanism
                baseline = equivalence_report.get("baseline_label", "unit_gearbox")
                paired = _graphs_at_shape(
                    config,
                    shape_n=shape_n,
                    fourbar=fourbar,
                    gearbox=gearbox,
                    limits=limits,
                )
                mech_entries = bank.mechanisms[:1]
            else:
                # Population: rebuild each mechanism at this shape.
                mech_entries = bank.mechanisms
                paired = None  # set per mechanism
                baseline = "unit_gearbox"
                limits = None
                fourbar = None
                gearbox = None

            build_s = float(time.perf_counter() - t_build0)
            accepted_tasks = 0
            requested_tasks = 0
            effect_pairs: list[float] = []
            n_components = 0
            n_valid = 0
            n_edges = 0
            runtime_sum = 0.0

            for mech_entry in mech_entries:
                if paired_fixed is None:
                    from inequality_mechanisms.mechanisms.base import Mechanism as Mech

                    fourbar = Mech.from_dict(mech_entry.fourbar)
                    gearbox = Mech.from_dict(mech_entry.gearbox)
                    assert mech_entry.limits is not None
                    limits = OutputJointLimits.box(
                        lower=mech_entry.limits["lower"],
                        upper=mech_entry.limits["upper"],
                    )
                    paired = _graphs_at_shape(
                        config,
                        shape_n=shape_n,
                        fourbar=fourbar,
                        gearbox=gearbox,
                        limits=limits,
                    )
                    baseline = mech_entry.baseline_label
                assert paired is not None

                n_components = int(paired.fourbar.connected_component_count())
                n_valid = int(paired.fourbar.valid_node_count)
                n_edges = sum(1 for _ in paired.fourbar.iter_edges())
                snap_tol = (
                    default_snap_tol(paired.grid)
                    if config.trials.snap_output_tol is None
                    else float(config.trials.snap_output_tol)
                )

                for task in mech_entry.tasks:
                    requested_tasks += 1
                    q_start = np.asarray(task.q_start, dtype=np.float64)
                    q_goal = np.asarray(task.q_goal, dtype=np.float64)
                    task_rng = np.random.default_rng(task.seed)
                    gb_pre = _materialize_preimages(
                        paired.gearbox,
                        q_start,
                        q_goal,
                        policy=policy,
                        rng=task_rng,
                        snap_tol=snap_tol,
                    )
                    fb_pre = _materialize_preimages(
                        paired.fourbar,
                        q_start,
                        q_goal,
                        policy=policy,
                        rng=task_rng,
                        snap_tol=snap_tol,
                    )
                    if gb_pre is None or fb_pre is None:
                        exclusions.append(
                            {
                                "mechanism_id": mech_entry.mechanism_id,
                                "task_id": task.task_id,
                                "reason_code": "preimage_snap_failed",
                                "shape_n": shape_n,
                            }
                        )
                        continue
                    accepted_tasks += 1
                    paired_task = PairedTask(
                        trial_index=trial_index,
                        q_start=q_start,
                        q_goal=q_goal,
                        gearbox=gb_pre,
                        fourbar=fb_pre,
                        output_residual_tol=snap_tol,
                    )
                    for cost_type in cost_types:
                        for algorithm in algorithms:
                            for side, graph, pre in (
                                ("gearbox", paired.gearbox, gb_pre),
                                ("fourbar", paired.fourbar, fb_pre),
                            ):
                                rec = _search_record(
                                    mechanism_id=mech_entry.mechanism_id,
                                    task_id=task.task_id,
                                    trial_index=trial_index,
                                    mechanism=side,
                                    algorithm=algorithm,
                                    cost_type=cost_type,
                                    graph=graph,
                                    preimages=pre,
                                    q_start=list(task.q_start),
                                    q_goal=list(task.q_goal),
                                    baseline_label=str(baseline),
                                    shape_n=shape_n,
                                )
                                runtime_sum += float(rec["runtime_s"] or 0.0)
                                all_rows.append(rec)
                    # Path samples (U / Q / Cartesian) at the config grid size.
                    if (
                        int(shape_n) == path_sample_shape
                        and path_samples_written < n_path_samples
                    ):
                        before = path_samples_written
                        _write_path_sample(
                            run,
                            trial_index=path_samples_written,
                            paired=paired,
                            task=paired_task,
                            algorithm=path_algo,
                            cost_type=path_cost,
                        )
                        # Count only if PNGs were written (both searches found).
                        sample_dir = (
                            run.outputs_dir
                            / "paths"
                            / f"trial_{path_samples_written:04d}"
                        )
                        if sample_dir.is_dir() and any(sample_dir.glob("*.png")):
                            path_samples_written += 1
                        _ = before
                    # Primary paired effect for resolution (dijkstra, first cost).
                    primary_cost = cost_types[0]
                    gb_exp = next(
                        (
                            r["n_expanded"]
                            for r in all_rows
                            if r["task_id"] == task.task_id
                            and r["shape_n"] == shape_n
                            and r["mechanism"] == "gearbox"
                            and r["algorithm"] == "dijkstra"
                            and r["cost_type"] == primary_cost
                            and r["found"]
                        ),
                        None,
                    )
                    fb_exp = next(
                        (
                            r["n_expanded"]
                            for r in all_rows
                            if r["task_id"] == task.task_id
                            and r["shape_n"] == shape_n
                            and r["mechanism"] == "fourbar"
                            and r["algorithm"] == "dijkstra"
                            and r["cost_type"] == primary_cost
                            and r["found"]
                        ),
                        None,
                    )
                    if gb_exp is not None and fb_exp is not None:
                        effect_pairs.append(
                            float(np.log((fb_exp + 1.0) / (gb_exp + 1.0)))
                        )
                    trial_index += 1

            acceptance = (
                float(accepted_tasks) / float(requested_tasks)
                if requested_tasks > 0
                else 0.0
            )
            primary_effect = (
                float(np.mean(effect_pairs)) if effect_pairs else float("nan")
            )
            resolution_rows.append(
                {
                    "shape_n": int(shape_n),
                    "total_nodes": int(shape_n) ** 2,
                    "valid_nodes": int(n_valid),
                    "valid_edges": int(n_edges),
                    "n_components": int(n_components),
                    "task_acceptance_rate": acceptance,
                    "primary_effect": primary_effect,
                    "graph_build_s": build_s,
                    "search_runtime_s": runtime_sum,
                    "n_accepted_tasks": int(accepted_tasks),
                    "n_requested_tasks": int(requested_tasks),
                }
            )

        run.append_jsonl("trials", all_rows)
        run.write_json("resolution_sweep", {"rows": resolution_rows})
        run.write_json("exclusions", {"rows": exclusions})

        production = select_production_resolution(
            resolution_rows,
            max_relative_effect_change=float(s6.max_relative_effect_change),
            require_sign_stability=bool(s6.require_sign_stability),
            require_component_stability=bool(s6.require_component_stability),
            require_task_feasibility_stability=bool(
                s6.require_task_feasibility_stability
            ),
        )
        run.write_json("production_resolution", production)

        # Hierarchical analysis on the production (or only) resolution rows.
        prod_n = int(production["production_shape_n"])
        analysis_rows = [r for r in all_rows if int(r["shape_n"]) == prod_n]
        if not analysis_rows:
            analysis_rows = all_rows

        summaries, mech_excl = mechanism_level_effects(
            analysis_rows,
            metric="log_expansion_ratio",
            algorithm="dijkstra",
            cost_type=cost_types[0],
            min_accepted_tasks=int(s6.min_accepted_tasks_per_mechanism),
        )
        exclusions.extend(mech_excl)
        run.write_json("mechanism_effects", {"rows": summaries})

        hci = hierarchical_bootstrap_ci(
            summaries,
            n_bootstrap=int(s6.hierarchical_bootstrap_samples),
            seed=int(s6.hierarchical_bootstrap_seed),
            confidence=float(s6.hierarchical_bootstrap_confidence),
            metric="log_expansion_ratio",
        )
        hci_payload = hci.to_dict()
        hci_payload["cluster_definition"] = "mechanism_pair"
        hci_payload["treats_tasks_as_iid"] = False
        assert_not_task_level_iid(hci_payload)
        run.write_json("hierarchical_bootstrap", hci_payload)

        effect_std = (
            float(np.std([s["effect"] for s in summaries], ddof=1))
            if len(summaries) > 1
            else 0.0
        )
        m_req = required_mechanism_count(
            effect_std, target_half_width=float(s6.target_ci_half_width)
        )
        sample_size = {
            "mechanism_effect_std": effect_std,
            "target_ci_half_width": float(s6.target_ci_half_width),
            "m_required": int(m_req),
            "n_mechanisms_observed": len(summaries),
        }
        run.write_json("sample_size_plan", sample_size)

        precision = sequential_precision_report(
            summaries,
            batch_size=int(s6.mechanism_batch_size),
            target_ci_half_width=float(s6.target_ci_half_width),
            n_bootstrap=int(s6.hierarchical_bootstrap_samples),
            seed=int(s6.hierarchical_bootstrap_seed),
            confidence=float(s6.hierarchical_bootstrap_confidence),
            max_relative_estimate_change=float(s6.max_relative_effect_change),
            min_mechanisms=int(s6.min_mechanisms),
        )
        run.write_json("sequential_precision", precision)

        # Confirmation subset at next higher resolution when available.
        confirmation: dict[str, Any] = {"ran": False}
        higher = [n for n in shapes if int(n) > prod_n]
        if higher and mode in {"full", "resolution"}:
            conf_n = int(min(higher))
            conf_rows = [r for r in all_rows if int(r["shape_n"]) == conf_n]
            conf_sum, _ = mechanism_level_effects(
                conf_rows,
                metric="log_expansion_ratio",
                algorithm="dijkstra",
                cost_type=cost_types[0],
                min_accepted_tasks=1,
            )
            conf_hci = hierarchical_bootstrap_ci(
                conf_sum,
                n_bootstrap=int(s6.hierarchical_bootstrap_samples),
                seed=int(s6.hierarchical_bootstrap_seed),
                confidence=float(s6.hierarchical_bootstrap_confidence),
            )
            sign_flip = (
                np.isfinite(hci.estimate)
                and np.isfinite(conf_hci.estimate)
                and np.sign(hci.estimate) != np.sign(conf_hci.estimate)
                and hci.estimate != 0.0
                and conf_hci.estimate != 0.0
            )
            confirmation = {
                "ran": True,
                "confirmation_shape_n": conf_n,
                "production_estimate": float(hci.estimate),
                "confirmation_estimate": float(conf_hci.estimate),
                "sign_reversed": bool(sign_flip),
                "n_mechanisms": len(conf_sum),
            }
        run.write_json("high_resolution_confirmation", confirmation)

        # Stability tables / plots metadata.
        _write_stability_artifacts(run, resolution_rows, precision)
        _write_plots(run, all_rows, figures_dir=None)
        if paired_fixed is not None:
            _write_gain_matching_figure(run, paired_fixed)

        summary_stats = summarize_trials(all_rows)
        summary = {
            "result_schema_version": SPRINT6_RESULT_SCHEMA_VERSION,
            "study": "sprint6",
            "mode": mode,
            "seed": int(config.seed),
            "n_trial_rows": len(all_rows),
            "n_mechanisms": len(bank.mechanisms),
            "n_exclusions": len(exclusions),
            "n_path_samples": int(path_samples_written),
            "n_path_samples_requested": int(n_path_samples),
            "production_shape_n": prod_n,
            "primary_effect": float(hci.estimate),
            "hierarchical_ci": [float(hci.ci_low), float(hci.ci_high)],
            "sample_size_plan": sample_size,
            "grid_anisotropy_limitation": GRID_ANISOTROPY_LIMITATION,
            "grid_anisotropy_acknowledged": bool(s6.grid_anisotropy_acknowledged),
            "confirmation": confirmation,
            "equivalence_baseline": equivalence_report.get("baseline_label"),
            "by_group": summary_stats.get("by_group"),
            "paired_log_ratios": summary_stats.get("paired_log_ratios"),
        }
        run.write_json("summary", summary)
        run.write_json("exclusions", {"rows": exclusions})

        fieldnames = [
            "mechanism_id",
            "task_id",
            "mechanism",
            "algorithm",
            "cost_type",
            "shape_n",
            "found",
            "n_expanded",
            "optimal_cost",
            "path_length_u",
            "path_length_q",
            "path_length_x",
            "runtime_s",
        ]
        _write_table_artifact(
            run, "trials_table", _rows_to_csv(all_rows, fieldnames)
        )
        _write_table_artifact(
            run,
            "resolution_table",
            _rows_to_csv(
                resolution_rows,
                [
                    "shape_n",
                    "total_nodes",
                    "valid_nodes",
                    "valid_edges",
                    "n_components",
                    "task_acceptance_rate",
                    "primary_effect",
                    "search_runtime_s",
                ],
            ),
        )

        run.mark_completed()
        # Derived viewer; regenerable via scripts/generate_sprint6_canvas.py.
        write_sprint6_canvas(run)
    except Exception as exc:
        run.mark_failed(str(exc))
        raise

    return run


def _write_stability_artifacts(
    run: ExperimentRun,
    resolution_rows: list[dict[str, Any]],
    precision: dict[str, Any],
) -> None:
    """Write Sprint Six stability plots when matplotlib is available."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return

    out_dir = run.outputs_dir / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)

    if resolution_rows:
        xs = [int(r["shape_n"]) for r in resolution_rows]
        fig, axes = plt.subplots(1, 3, figsize=(12, 3.5))
        axes[0].plot(xs, [r["valid_nodes"] for r in resolution_rows], marker="o")
        axes[0].set_xlabel("n")
        axes[0].set_ylabel("valid nodes")
        axes[0].set_title("Valid nodes vs resolution")
        axes[1].plot(
            xs, [r["search_runtime_s"] for r in resolution_rows], marker="o"
        )
        axes[1].set_xlabel("n")
        axes[1].set_ylabel("search runtime (s)")
        axes[1].set_title("Runtime vs resolution")
        axes[2].plot(
            xs, [r["primary_effect"] for r in resolution_rows], marker="o"
        )
        axes[2].set_xlabel("n")
        axes[2].set_ylabel("primary effect")
        axes[2].set_title("Effect vs resolution")
        fig.tight_layout()
        fig.savefig(out_dir / "resolution_stability.png", dpi=120)
        plt.close(fig)
        run.register_output(
            "resolution_stability", "outputs/figures/resolution_stability.png"
        )

    batches = list(precision.get("batches", []))
    if batches:
        ms = [int(b["n_mechanisms"]) for b in batches]
        fig, axes = plt.subplots(1, 2, figsize=(8, 3.5))
        axes[0].plot(ms, [b["estimate"] for b in batches], marker="o")
        axes[0].set_xlabel("M")
        axes[0].set_ylabel("effect")
        axes[0].set_title("Effect vs mechanism count")
        axes[1].plot(ms, [b["ci_half_width"] for b in batches], marker="o")
        axes[1].set_xlabel("M")
        axes[1].set_ylabel("CI half-width")
        axes[1].set_title("Precision vs mechanism count")
        fig.tight_layout()
        fig.savefig(out_dir / "monte_carlo_stability.png", dpi=120)
        plt.close(fig)
        run.register_output(
            "monte_carlo_stability", "outputs/figures/monte_carlo_stability.png"
        )


def _write_gain_matching_figure(run: ExperimentRun, paired: PairedGraphs) -> None:
    """Plot four-bar follower curves with matched linear gearbox overlays."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return

    from inequality_mechanisms.mechanisms.fourbar import IndependentFourBars
    from inequality_mechanisms.mechanisms.gearbox import EquivalentGearbox

    fb = paired.fourbar_mechanism
    gb = paired.gearbox_mechanism
    if not isinstance(fb, IndependentFourBars):
        return

    out = run.outputs_dir / "figures" / "gain_matching.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    n_axes = fb.input_dim
    fig, axes = plt.subplots(1, n_axes, figsize=(5.0 * n_axes, 3.6), squeeze=False)
    u = np.linspace(0.0, 2.0 * np.pi, 361, dtype=np.float64)
    for i, bar in enumerate(fb.bars):
        ax = axes[0, i]
        q_fb = bar.follower_curve(u, unwrap=True)
        ax.plot(u, q_fb, color="#c44e52", lw=1.8, label="four-bar")
        if isinstance(gb, EquivalentGearbox):
            q_gb = gb.q_ref[i] + gb.ratios[i] * (u - gb.u_ref[i])
            ax.plot(
                u,
                q_gb,
                color="#4c72b0",
                lw=1.6,
                ls="--",
                label=f"{gb.matching_rule} gearbox",
            )
            axes_meta = gb.provenance.get("axes") or []
            meta = axes_meta[i] if i < len(axes_meta) else {}
            interval = meta.get("u_interval") if isinstance(meta, dict) else None
            if isinstance(interval, list) and len(interval) == 2:
                ax.axvspan(
                    float(interval[0]), float(interval[1]), color="#4c72b0", alpha=0.08
                )
        ax.set_xlabel(f"u[{i}]")
        ax.set_ylabel(f"q[{i}]")
        ax.set_title(f"Axis {i} transmission")
        ax.legend(loc="best", fontsize=8)
    fig.suptitle("Four-bar gain vs matched linear baseline", y=1.02)
    fig.tight_layout()
    fig.savefig(out, dpi=140, bbox_inches="tight")
    plt.close(fig)
    run.register_output("gain_matching", "outputs/figures/gain_matching.png")
