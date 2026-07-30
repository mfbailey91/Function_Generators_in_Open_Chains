"""Unit tests for paired bootstrap CIs (S4-10)."""

from __future__ import annotations

from inequality_mechanisms.metrics.bootstrap import (
    bootstrap_primary_metrics,
    paired_bootstrap_ci,
)


def test_paired_bootstrap_reproducible() -> None:
    diffs = [1.0, 2.0, 1.5, 0.5, 3.0]
    a = paired_bootstrap_ci(diffs, n_bootstrap=200, seed=7, confidence=0.9)
    b = paired_bootstrap_ci(diffs, n_bootstrap=200, seed=7, confidence=0.9)
    assert a == b
    est, lo, hi = a
    assert lo <= est <= hi


def test_bootstrap_primary_metrics_shape() -> None:
    rows = []
    for trial in range(3):
        for mech, base in (("gearbox", 10), ("fourbar", 20)):
            rows.append(
                {
                    "trial_index": trial,
                    "mechanism": mech,
                    "algorithm": "dijkstra",
                    "cost_type": "output_euclidean",
                    "found": True,
                    "n_expanded": base + trial,
                    "rho_expanded": 0.1 * (base + trial),
                    "optimal_cost": float(base),
                    "path_length_u": 1.0,
                    "path_length_q": 1.0,
                    "path_length_x": 1.0,
                    "runtime_s": 0.01,
                    "beta": 0.2,
                }
            )
    savings = [
        {
            "trial_index": t,
            "mechanism": mech,
            "cost_type": "output_euclidean",
            "s_a": 0.1 if mech == "gearbox" else 0.3,
        }
        for t in range(3)
        for mech in ("gearbox", "fourbar")
    ]
    out = bootstrap_primary_metrics(
        rows, savings, n_bootstrap=50, seed=0, confidence=0.95
    )
    assert out["n_bootstrap_samples"] == 50
    assert out["interval_method"] == "percentile"
    names = {item["metric"] for item in out["intervals"]}
    assert "expansion_diff" in names
    assert "astar_savings_diff" in names
