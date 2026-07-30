"""Paired bootstrap confidence intervals (S4-10)."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True, slots=True)
class BootstrapCI:
    """One paired-bootstrap confidence interval.

    Attributes
    ----------
    metric :
        Metric name (e.g. ``expansion_diff``).
    estimate :
        Observed paired mean difference (four-bar − gearbox unless noted).
    ci_low, ci_high :
        Percentile interval bounds.
    n_pairs :
        Number of paired observations used.
    n_excluded :
        Pairs dropped for missing / failed values.
    """

    metric: str
    estimate: float
    ci_low: float
    ci_high: float
    n_pairs: int
    n_excluded: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def paired_bootstrap_ci(
    differences: Sequence[float],
    *,
    n_bootstrap: int = 1000,
    seed: int = 0,
    confidence: float = 0.95,
) -> tuple[float, float, float]:
    """Return ``(estimate, ci_low, ci_high)`` for the mean of paired diffs.

    Uses the percentile bootstrap of the mean.
    """
    arr = np.asarray(list(differences), dtype=np.float64)
    if arr.size == 0:
        return float("nan"), float("nan"), float("nan")
    estimate = float(np.mean(arr))
    if arr.size == 1 or n_bootstrap < 1:
        return estimate, estimate, estimate
    rng = np.random.default_rng(int(seed))
    idx = rng.integers(0, arr.size, size=(int(n_bootstrap), arr.size))
    means = np.mean(arr[idx], axis=1)
    alpha = 1.0 - float(confidence)
    low = float(np.quantile(means, alpha / 2.0))
    high = float(np.quantile(means, 1.0 - alpha / 2.0))
    return estimate, low, high


def _paired_diffs(
    rows: Sequence[Mapping[str, Any]],
    *,
    field: str,
    algorithm: str | None = None,
    cost_type: str | None = None,
    transform: Callable[[float, float], float] | None = None,
) -> tuple[list[float], int]:
    """Return (fourbar - gearbox) differences and exclusion count."""
    by_key: dict[tuple[Any, ...], dict[str, float]] = {}
    for row in rows:
        if not row.get("found"):
            continue
        if algorithm is not None and str(row.get("algorithm")) != algorithm:
            continue
        if cost_type is not None and str(row.get("cost_type")) != cost_type:
            continue
        val = row.get(field)
        if val is None:
            continue
        try:
            fval = float(val)
        except (TypeError, ValueError):
            continue
        if not np.isfinite(fval):
            continue
        key = (
            int(row["trial_index"]),
            str(row.get("cost_type", "")),
            str(row.get("algorithm", "")),
        )
        by_key.setdefault(key, {})[str(row["mechanism"])] = fval

    diffs: list[float] = []
    excluded = 0
    for pair in by_key.values():
        if "gearbox" not in pair or "fourbar" not in pair:
            excluded += 1
            continue
        g = pair["gearbox"]
        f = pair["fourbar"]
        if transform is not None:
            diffs.append(float(transform(f, g)))
        else:
            diffs.append(float(f - g))
    return diffs, excluded


def bootstrap_primary_metrics(
    rows: Sequence[Mapping[str, Any]],
    savings_rows: Sequence[Mapping[str, Any]],
    *,
    n_bootstrap: int = 1000,
    seed: int = 0,
    confidence: float = 0.95,
    algorithm: str = "dijkstra",
) -> dict[str, Any]:
    """Compute paired bootstrap CIs for Sprint Four primary metrics.

    Differences are four-bar minus gearbox unless the metric is already a
    paired savings quantity (then four-bar savings minus gearbox savings).
    """
    meta = {
        "bootstrap_seed": int(seed),
        "n_bootstrap_samples": int(n_bootstrap),
        "confidence_level": float(confidence),
        "interval_method": "percentile",
        "algorithm": algorithm,
    }
    results: list[dict[str, Any]] = []

    def _add(metric: str, diffs: list[float], excluded: int) -> None:
        est, lo, hi = paired_bootstrap_ci(
            diffs,
            n_bootstrap=n_bootstrap,
            seed=seed,
            confidence=confidence,
        )
        results.append(
            BootstrapCI(
                metric=metric,
                estimate=est,
                ci_low=lo,
                ci_high=hi,
                n_pairs=len(diffs),
                n_excluded=int(excluded),
            ).to_dict()
        )

    for field, name in (
        ("n_expanded", "expansion_diff"),
        ("rho_expanded", "normalized_expansion_diff"),
        ("optimal_cost", "optimal_cost_diff"),
        ("path_length_u", "path_length_u_diff"),
        ("path_length_q", "path_length_q_diff"),
        ("path_length_x", "path_length_x_diff"),
        ("runtime_s", "runtime_diff"),
        ("beta", "goal_cost_ball_diff"),
    ):
        diffs, excluded = _paired_diffs(
            rows, field=field, algorithm=algorithm
        )
        _add(name, diffs, excluded)

    # A* savings difference (four-bar S_A − gearbox S_A) per cost.
    sav_by: dict[tuple[int, str], dict[str, float]] = {}
    sav_excluded = 0
    for row in savings_rows:
        key = (int(row["trial_index"]), str(row["cost_type"]))
        sav_by.setdefault(key, {})[str(row["mechanism"])] = float(row["s_a"])
    sav_diffs: list[float] = []
    for pair in sav_by.values():
        if "gearbox" not in pair or "fourbar" not in pair:
            sav_excluded += 1
            continue
        sav_diffs.append(float(pair["fourbar"] - pair["gearbox"]))
    _add("astar_savings_diff", sav_diffs, sav_excluded)

    return {**meta, "intervals": results}


def _undefined_counts(
    rows: Sequence[Mapping[str, Any]],
    *,
    field: str,
    algorithm: str | None = None,
) -> dict[str, int]:
    """Count found rows with missing/undefined metric values."""
    n_found = 0
    n_undefined = 0
    for row in rows:
        if not row.get("found"):
            continue
        if algorithm is not None and str(row.get("algorithm")) != algorithm:
            continue
        n_found += 1
        val = row.get(field)
        if field.startswith("directness_ratio_"):
            space = field.rsplit("_", 1)[-1]
            defined_flag = row.get(f"directness_defined_{space}")
            if defined_flag is False or val is None:
                n_undefined += 1
                continue
        if val is None:
            n_undefined += 1
            continue
        try:
            if not np.isfinite(float(val)):
                n_undefined += 1
        except (TypeError, ValueError):
            n_undefined += 1
    return {"n_found": n_found, "n_undefined": n_undefined}


def bootstrap_path_quality_metrics(
    rows: Sequence[Mapping[str, Any]],
    *,
    n_bootstrap: int = 1000,
    seed: int = 0,
    confidence: float = 0.95,
    algorithm: str = "dijkstra",
) -> dict[str, Any]:
    """Paired bootstrap CIs for Sprint Five path-quality metrics (S5-09).

    Differences are four-bar minus gearbox. Sparse intersection counts also
    receive raw frequency summaries.
    """
    meta = {
        "bootstrap_seed": int(seed),
        "n_bootstrap_samples": int(n_bootstrap),
        "confidence_level": float(confidence),
        "interval_method": "percentile",
        "algorithm": algorithm,
    }
    results: list[dict[str, Any]] = []
    undefined: dict[str, Any] = {}

    def _add(metric: str, diffs: list[float], excluded: int) -> None:
        est, lo, hi = paired_bootstrap_ci(
            diffs,
            n_bootstrap=n_bootstrap,
            seed=seed,
            confidence=confidence,
        )
        results.append(
            BootstrapCI(
                metric=metric,
                estimate=est,
                ci_low=lo,
                ci_high=hi,
                n_pairs=len(diffs),
                n_excluded=int(excluded),
            ).to_dict()
        )

    for field, name in (
        ("path_length_u", "path_length_u_diff"),
        ("path_length_q", "path_length_q_diff"),
        ("path_length_x", "path_length_x_diff"),
        ("directness_ratio_q", "directness_ratio_q_diff"),
        ("directness_ratio_x", "directness_ratio_x_diff"),
        ("cumulative_turning_q", "cumulative_turning_q_diff"),
        ("cumulative_turning_x", "cumulative_turning_x_diff"),
        ("self_intersections_q", "self_intersections_q_diff"),
        ("self_intersections_x", "self_intersections_x_diff"),
        ("near_revisit_distance_q", "near_revisit_distance_q_diff"),
        ("near_revisit_distance_x", "near_revisit_distance_x_diff"),
    ):
        diffs, excluded = _paired_diffs(rows, field=field, algorithm=algorithm)
        _add(name, diffs, excluded)
        undefined[field] = _undefined_counts(
            rows, field=field, algorithm=algorithm
        )

    # Sparse intersection frequencies / proportions (not paired diffs).
    sparse: dict[str, Any] = {}
    for field in ("self_intersections_q", "self_intersections_x"):
        by_mech: dict[str, list[float]] = {"gearbox": [], "fourbar": []}
        for row in rows:
            if not row.get("found"):
                continue
            if str(row.get("algorithm")) != algorithm:
                continue
            mech = str(row.get("mechanism"))
            if mech not in by_mech:
                continue
            val = row.get(field)
            if val is None:
                continue
            by_mech[mech].append(float(val))
        sparse[field] = {
            mech: {
                "n": len(vals),
                "mean": float(np.mean(vals)) if vals else float("nan"),
                "fraction_positive": (
                    float(np.mean(np.asarray(vals) > 0.0)) if vals else float("nan")
                ),
            }
            for mech, vals in by_mech.items()
        }

    return {
        **meta,
        "intervals": results,
        "undefined_counts": undefined,
        "sparse_intersection_frequencies": sparse,
    }
