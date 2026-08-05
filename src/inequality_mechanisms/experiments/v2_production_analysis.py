"""Hierarchical analysis and sequential precision for production shards."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from inequality_mechanisms.metrics.hierarchical_bootstrap import (
    assert_not_task_level_iid,
    hierarchical_bootstrap_ci,
    mechanism_level_effects,
    sequential_precision_report,
)


def within_between_variance(
    mechanism_summaries: Sequence[Mapping[str, Any]],
) -> dict[str, float]:
    """Estimate within- and between-mechanism variance of task effects."""
    within_vars: list[float] = []
    means: list[float] = []
    for summary in mechanism_summaries:
        effects = [float(x) for x in summary.get("task_effects", [])]
        if not effects:
            continue
        means.append(float(np.mean(effects)))
        if len(effects) > 1:
            within_vars.append(float(np.var(effects, ddof=1)))
    between = float(np.var(means, ddof=1)) if len(means) > 1 else 0.0
    within = float(np.mean(within_vars)) if within_vars else 0.0
    return {
        "n_mechanisms": float(len(means)),
        "between_mechanism_variance": between,
        "within_mechanism_variance": within,
        "variance_ratio_between_over_within": (
            between / within if within > 0.0 else float("inf") if between > 0.0 else 0.0
        ),
    }


def sequential_precision_with_stability(
    mechanism_summaries: Sequence[Mapping[str, Any]],
    *,
    batch_size: int,
    target_ci_half_width: float,
    n_bootstrap: int,
    seed: int,
    confidence: float,
    max_relative_estimate_change: float,
    min_mechanisms: int,
    stable_batches_required: int,
    maximum_mechanisms: int,
) -> dict[str, Any]:
    """Extend sequential precision with consecutive stable-batch counting."""
    base = sequential_precision_report(
        mechanism_summaries,
        batch_size=batch_size,
        target_ci_half_width=target_ci_half_width,
        n_bootstrap=n_bootstrap,
        seed=seed,
        confidence=confidence,
        max_relative_estimate_change=max_relative_estimate_change,
        min_mechanisms=min_mechanisms,
    )
    batches = list(base.get("batches", []))
    stable_run = 0
    stop = False
    stop_reason = None
    for batch in batches:
        half = batch.get("ci_half_width")
        rel = batch.get("relative_change")
        n_mech = int(batch["n_mechanisms"])
        sign_stable = bool(batch.get("sign_stable", True))
        half_ok = (
            isinstance(half, (int, float))
            and np.isfinite(half)
            and half <= target_ci_half_width
        )
        rel_ok = (
            (not isinstance(rel, (int, float)))
            or (not np.isfinite(rel))
            or float(rel) <= float(max_relative_estimate_change)
        )
        if n_mech >= int(min_mechanisms) and half_ok and sign_stable and rel_ok:
            stable_run += 1
        else:
            stable_run = 0
        batch["stable_run"] = stable_run
        if stable_run >= int(stable_batches_required):
            stop = True
            stop_reason = "precision_and_stability"
            break
    if (
        not stop
        and batches
        and int(batches[-1]["n_mechanisms"]) >= int(maximum_mechanisms)
    ):
        stop = True
        stop_reason = "maximum_mechanisms"
    report = {
        **base,
        "batches": batches,
        "stop": stop,
        "stop_reason": stop_reason,
        "stable_batches_required": int(stable_batches_required),
        "maximum_mechanisms": int(maximum_mechanisms),
        "treats_tasks_as_iid": False,
        "cluster_definition": "mechanism_pair",
        "interval_scope": "mechanism",
    }
    assert_not_task_level_iid(report)
    return report


def analyze_production_trials(
    trials: Sequence[Mapping[str, Any]],
    *,
    batch_size: int,
    target_ci_half_width: float,
    n_bootstrap: int,
    seed: int,
    confidence: float,
    max_relative_estimate_change: float,
    min_mechanisms: int,
    stable_batches_required: int,
    maximum_mechanisms: int,
    min_accepted_tasks: int = 1,
) -> dict[str, Any]:
    """Aggregate trial rows into mechanism summaries and precision reports."""
    analysis_rows: list[dict[str, Any]] = []
    for row in trials:
        if not row.get("found"):
            continue
        analysis_rows.append(
            {
                "mechanism_id": row.get("mechanism_pair_id"),
                "task_id": row.get("task_id"),
                "mechanism": row.get("mechanism"),
                "algorithm": row.get("algorithm", "dijkstra"),
                "cost_type": row.get("cost_type", "actuator_travel"),
                "found": True,
                "n_expanded": row.get("n_expanded"),
                "optimal_cost": row.get("optimal_cost"),
                "path_length_u": row.get("path_length_u"),
                "path_length_q": row.get("path_length_q"),
                "path_length_x": row.get("path_length_x"),
            }
        )
    summaries, exclusions = mechanism_level_effects(
        analysis_rows,
        metric="log_expansion_ratio",
        algorithm="dijkstra",
        cost_type="actuator_travel",
        min_accepted_tasks=min_accepted_tasks,
    )
    cost_summaries, _ = mechanism_level_effects(
        analysis_rows,
        metric="optimal_cost_diff",
        algorithm="dijkstra",
        cost_type="actuator_travel",
        min_accepted_tasks=min_accepted_tasks,
    )
    path_u_summaries, _ = mechanism_level_effects(
        analysis_rows,
        metric="path_length_u_diff",
        algorithm="dijkstra",
        cost_type="actuator_travel",
        min_accepted_tasks=min_accepted_tasks,
    )
    hci = hierarchical_bootstrap_ci(
        summaries,
        n_bootstrap=n_bootstrap,
        seed=seed,
        confidence=confidence,
        metric="log_expansion_ratio",
    )
    precision = sequential_precision_with_stability(
        summaries,
        batch_size=batch_size,
        target_ci_half_width=target_ci_half_width,
        n_bootstrap=n_bootstrap,
        seed=seed,
        confidence=confidence,
        max_relative_estimate_change=max_relative_estimate_change,
        min_mechanisms=min_mechanisms,
        stable_batches_required=stable_batches_required,
        maximum_mechanisms=maximum_mechanisms,
    )
    task_category_effects: dict[str, list[float]] = defaultdict(list)
    by_pair_task: dict[tuple[Any, Any], dict[str, float]] = {}
    categories: dict[tuple[Any, Any], str] = {}
    for row in trials:
        if not row.get("found"):
            continue
        key = (row.get("mechanism_pair_id"), row.get("task_id"))
        side = str(row.get("mechanism"))
        bucket = by_pair_task.setdefault(key, {})
        if row.get("n_expanded") is not None:
            bucket[side] = float(row["n_expanded"])
        categories[key] = str(row.get("task_category") or "uncategorized")
    for key, sides in by_pair_task.items():
        if "fourbar" in sides and "gearbox" in sides:
            d = float(np.log((sides["fourbar"] + 1.0) / (sides["gearbox"] + 1.0)))
            task_category_effects[categories[key]].append(d)
    category_summary = {
        name: {
            "n": len(vals),
            "mean": float(np.mean(vals)) if vals else float("nan"),
        }
        for name, vals in sorted(task_category_effects.items())
    }
    return {
        "primary_metric": "log_expansion_ratio",
        "mechanism_summaries": summaries,
        "cost_summaries": cost_summaries,
        "path_length_u_summaries": path_u_summaries,
        "exclusions": exclusions,
        "hierarchical_bootstrap": hci.to_dict(),
        "variance": within_between_variance(summaries),
        "precision": precision,
        "task_category_effects": category_summary,
        "n_trial_rows": len(trials),
        "n_analysis_rows": len(analysis_rows),
    }
