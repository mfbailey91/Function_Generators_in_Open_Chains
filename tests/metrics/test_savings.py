"""Unit tests for A* savings metrics (S4-07)."""

from __future__ import annotations

import pytest

from inequality_mechanisms.metrics.savings import (
    astar_expansion_delta,
    astar_savings,
    compute_savings_rows,
    summarize_savings,
)


def test_astar_savings_formula() -> None:
    assert astar_savings(100, 40) == pytest.approx(0.6)
    assert astar_expansion_delta(100, 40) == 60
    with pytest.raises(ValueError):
        astar_savings(0, 1)


def test_compute_savings_rows_pairs() -> None:
    rows = [
        {
            "trial_index": 0,
            "mechanism": "gearbox",
            "cost_type": "uniform",
            "algorithm": "dijkstra",
            "found": True,
            "n_expanded": 10,
            "path_length_q": 1.0,
            "edge_cost_variance": 0.5,
            "beta": 0.2,
        },
        {
            "trial_index": 0,
            "mechanism": "gearbox",
            "cost_type": "uniform",
            "algorithm": "astar",
            "found": True,
            "n_expanded": 4,
            "path_length_q": 1.0,
            "mean_heuristic_strength": 0.8,
        },
    ]
    savings = compute_savings_rows(rows)
    assert len(savings) == 1
    assert savings[0]["s_a"] == pytest.approx(0.6)
    assert savings[0]["delta_n_a"] == 6
    summary = summarize_savings(savings)
    assert summary["n_pairs"] == 1
    assert "gearbox|uniform" in summary["by_group"]
