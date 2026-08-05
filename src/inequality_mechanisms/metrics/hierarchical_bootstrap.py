"""Hierarchical bootstrap and mechanism-level Monte Carlo summaries (S6-11–S6-16)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True, slots=True)
class HierarchicalBootstrapCI:
    """Mechanism-first hierarchical percentile bootstrap interval."""

    metric: str
    estimate: float
    ci_low: float
    ci_high: float
    n_mechanisms: int
    n_tasks: int
    n_excluded_mechanisms: int
    n_bootstrap_samples: int
    confidence_level: float
    interval_method: str
    bootstrap_seed: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def paired_log_expansion_ratio(n_fb: float, n_gb: float) -> float:
    """Return ``log((N_fb + 1) / (N_gb + 1))``."""
    return float(np.log((float(n_fb) + 1.0) / (float(n_gb) + 1.0)))


def mechanism_level_effects(
    rows: Sequence[Mapping[str, Any]],
    *,
    metric: str = "log_expansion_ratio",
    algorithm: str | None = "dijkstra",
    cost_type: str | None = None,
    min_accepted_tasks: int = 1,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Aggregate paired task metrics to one effect per mechanism.

    Parameters
    ----------
    rows :
        Trial rows with ``mechanism_id``, ``task_id``, ``mechanism`` in
        ``{gearbox, fourbar}``, and metric fields.
    metric :
        ``log_expansion_ratio``, ``expansion_diff``, ``optimal_cost_diff``,
        ``path_length_u_diff``, ``path_length_q_diff``, ``path_length_x_diff``,
        or ``rho_diff``.
    algorithm, cost_type :
        Optional filters.
    min_accepted_tasks :
        Mechanisms with fewer accepted paired tasks are excluded.

    Returns
    -------
    summaries, exclusions
        Mechanism-level summary dicts and exclusion records.
    """
    # key: (mechanism_id, task_id) -> side -> value
    by_pair: dict[tuple[Any, Any], dict[str, float]] = {}
    for row in rows:
        if not row.get("found"):
            continue
        if algorithm is not None and str(row.get("algorithm")) != algorithm:
            continue
        if cost_type is not None and str(row.get("cost_type")) != cost_type:
            continue
        mech_id = row.get("mechanism_id")
        task_id = row.get("task_id")
        if mech_id is None or task_id is None:
            continue
        side = str(row.get("mechanism"))
        key = (mech_id, task_id)
        bucket = by_pair.setdefault(key, {})
        if metric == "log_expansion_ratio" or metric == "expansion_diff":
            val = row.get("n_expanded")
        elif metric == "optimal_cost_diff":
            val = row.get("optimal_cost")
        elif metric == "path_length_u_diff":
            val = row.get("path_length_u")
        elif metric == "path_length_q_diff":
            val = row.get("path_length_q")
        elif metric == "path_length_x_diff":
            val = row.get("path_length_x")
        elif metric == "rho_diff":
            val = row.get("rho_expanded")
        else:
            raise ValueError(f"unknown metric {metric!r}")
        if val is None:
            continue
        bucket[side] = float(val)

    per_mech_tasks: dict[Any, list[float]] = defaultdict(list)
    for (mech_id, _task_id), sides in by_pair.items():
        if "fourbar" not in sides or "gearbox" not in sides:
            continue
        fb = sides["fourbar"]
        gb = sides["gearbox"]
        if metric == "log_expansion_ratio":
            d = paired_log_expansion_ratio(fb, gb)
        else:
            d = float(fb - gb)
        per_mech_tasks[mech_id].append(d)

    summaries: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    for mech_id, vals in sorted(per_mech_tasks.items(), key=lambda kv: str(kv[0])):
        if len(vals) < int(min_accepted_tasks):
            exclusions.append(
                {
                    "mechanism_id": mech_id,
                    "reason_code": "insufficient_tasks",
                    "n_accepted_tasks": len(vals),
                    "min_accepted_tasks": int(min_accepted_tasks),
                }
            )
            continue
        summaries.append(
            {
                "mechanism_id": mech_id,
                "metric": metric,
                "n_accepted_tasks": len(vals),
                "effect": float(np.mean(vals)),
                "effect_std": float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0,
                "task_effects": [float(v) for v in vals],
            }
        )
    return summaries, exclusions


def hierarchical_bootstrap_ci(
    mechanism_summaries: Sequence[Mapping[str, Any]],
    *,
    n_bootstrap: int = 1000,
    seed: int = 0,
    confidence: float = 0.95,
    metric: str = "log_expansion_ratio",
) -> HierarchicalBootstrapCI:
    """Resample mechanisms, then tasks within mechanisms, then overall mean.

    Each summary must include ``task_effects`` (per-task paired differences)
    and ``effect`` (mechanism mean).
    """
    usable = [s for s in mechanism_summaries if s.get("task_effects")]
    n_mech = len(usable)
    n_tasks = int(sum(len(s["task_effects"]) for s in usable))
    if n_mech == 0:
        return HierarchicalBootstrapCI(
            metric=metric,
            estimate=float("nan"),
            ci_low=float("nan"),
            ci_high=float("nan"),
            n_mechanisms=0,
            n_tasks=0,
            n_excluded_mechanisms=len(mechanism_summaries),
            n_bootstrap_samples=int(n_bootstrap),
            confidence_level=float(confidence),
            interval_method="percentile",
            bootstrap_seed=int(seed),
        )

    observed = float(np.mean([float(s["effect"]) for s in usable]))
    if n_mech == 1 or int(n_bootstrap) < 1:
        return HierarchicalBootstrapCI(
            metric=metric,
            estimate=observed,
            ci_low=observed,
            ci_high=observed,
            n_mechanisms=n_mech,
            n_tasks=n_tasks,
            n_excluded_mechanisms=max(0, len(mechanism_summaries) - n_mech),
            n_bootstrap_samples=int(n_bootstrap),
            confidence_level=float(confidence),
            interval_method="percentile",
            bootstrap_seed=int(seed),
        )

    rng = np.random.default_rng(int(seed))
    task_lists = [np.asarray(s["task_effects"], dtype=np.float64) for s in usable]
    means = np.empty(int(n_bootstrap), dtype=np.float64)
    for b in range(int(n_bootstrap)):
        mech_idx = rng.integers(0, n_mech, size=n_mech)
        mech_means = np.empty(n_mech, dtype=np.float64)
        for j, mi in enumerate(mech_idx):
            tasks = task_lists[int(mi)]
            t_idx = rng.integers(0, tasks.size, size=tasks.size)
            mech_means[j] = float(np.mean(tasks[t_idx]))
        means[b] = float(np.mean(mech_means))

    alpha = 1.0 - float(confidence)
    low = float(np.quantile(means, alpha / 2.0))
    high = float(np.quantile(means, 1.0 - alpha / 2.0))
    return HierarchicalBootstrapCI(
        metric=metric,
        estimate=observed,
        ci_low=low,
        ci_high=high,
        n_mechanisms=n_mech,
        n_tasks=n_tasks,
        n_excluded_mechanisms=max(0, len(mechanism_summaries) - n_mech),
        n_bootstrap_samples=int(n_bootstrap),
        confidence_level=float(confidence),
        interval_method="percentile",
        bootstrap_seed=int(seed),
    )


def required_mechanism_count(
    mechanism_effect_std: float,
    *,
    target_half_width: float = 0.10,
    z: float = 1.96,
) -> int:
    """Planning estimate ``M ≈ (z * s_d / h)^2`` from pilot variance."""
    s = float(mechanism_effect_std)
    h = float(target_half_width)
    if h <= 0.0:
        raise ValueError("target_half_width must be positive")
    if not np.isfinite(s) or s < 0.0:
        raise ValueError("mechanism_effect_std must be finite and non-negative")
    if s == 0.0:
        return 1
    m = (float(z) * s / h) ** 2
    return max(1, int(np.ceil(m)))


def sequential_precision_report(
    mechanism_summaries: Sequence[Mapping[str, Any]],
    *,
    batch_size: int,
    target_ci_half_width: float,
    n_bootstrap: int = 200,
    seed: int = 0,
    confidence: float = 0.95,
    max_relative_estimate_change: float = 0.05,
    min_mechanisms: int = 1,
) -> dict[str, Any]:
    """Compute cumulative precision after each mechanism batch."""
    ordered = list(mechanism_summaries)
    batches: list[dict[str, Any]] = []
    prev_estimate: float | None = None
    stop = False
    stop_reason: str | None = None

    for end in range(int(batch_size), len(ordered) + 1, int(batch_size)):
        subset = ordered[:end]
        ci = hierarchical_bootstrap_ci(
            subset,
            n_bootstrap=n_bootstrap,
            seed=seed,
            confidence=confidence,
        )
        half = (
            float("nan")
            if not np.isfinite(ci.ci_high)
            else 0.5 * (float(ci.ci_high) - float(ci.ci_low))
        )
        est = float(ci.estimate)
        delta = (
            float("nan")
            if prev_estimate is None or not np.isfinite(prev_estimate)
            else abs(est - prev_estimate)
        )
        sign_stable = (
            True
            if prev_estimate is None
            else (np.sign(est) == np.sign(prev_estimate) or est == 0.0)
        )
        relative_change = (
            float("nan")
            if prev_estimate is None or abs(prev_estimate) < 1e-12
            else abs(est - prev_estimate) / abs(prev_estimate)
        )
        batch_rec = {
            "n_mechanisms": end,
            "estimate": est,
            "ci_low": float(ci.ci_low),
            "ci_high": float(ci.ci_high),
            "ci_half_width": half,
            "delta_from_previous": delta,
            "relative_change": relative_change,
            "sign_stable": bool(sign_stable),
        }
        batches.append(batch_rec)
        prev_estimate = est

        if (
            end >= int(min_mechanisms)
            and np.isfinite(half)
            and half <= float(target_ci_half_width)
            and sign_stable
            and (
                not np.isfinite(relative_change)
                or relative_change <= float(max_relative_estimate_change)
            )
        ):
            stop = True
            stop_reason = "precision_and_stability"

    return {
        "cluster_definition": "mechanism_pair",
        "batches": batches,
        "stop": stop,
        "stop_reason": stop_reason,
        "target_ci_half_width": float(target_ci_half_width),
        "min_mechanisms": int(min_mechanisms),
        "final_n_mechanisms": int(batches[-1]["n_mechanisms"]) if batches else 0,
    }


def assert_not_task_level_iid(report: Mapping[str, Any]) -> None:
    """Raise if a report claims task-level iid CI without mechanism clustering."""
    if report.get("treats_tasks_as_iid") is True:
        raise AssertionError(
            "task-level iid confidence intervals are forbidden when tasks are "
            "nested in mechanisms (S6-20); use hierarchical bootstrap"
        )
    if (
        report.get("interval_scope") == "task"
        and report.get("cluster_definition") != "mechanism_pair"
    ):
        raise AssertionError(
            "task-scoped intervals require cluster_definition == 'mechanism_pair'"
        )
