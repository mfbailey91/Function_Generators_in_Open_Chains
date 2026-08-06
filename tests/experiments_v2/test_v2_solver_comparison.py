from __future__ import annotations

import json
from pathlib import Path

import pytest

from inequality_mechanisms.experiments.v2_solver_comparison import (
    compare_exact_solver_runs,
)


def _write_run(root: Path, solver: str, expanded: int, cost: float) -> None:
    (root / "merged").mkdir(parents=True)
    (root / "manifest.json").write_text(
        json.dumps({"solver_id": solver, "sample_bank_digest": "bank"})
    )
    row = {
        "mechanism_pair_id": "m000000",
        "mechanism_id": "fourbar",
        "task_id": "t0",
        "graph_shape": [64, 64],
        "objective_id": "actuator_travel",
        "found": True,
        "optimal_cost": cost,
        "n_expanded": expanded,
    }
    (root / "merged" / "trials.jsonl").write_text(json.dumps(row) + "\n")


def test_exact_solver_comparison_checks_cost_and_reports_savings(tmp_path: Path) -> None:
    dijkstra = tmp_path / "dijkstra"
    astar = tmp_path / "astar"
    _write_run(dijkstra, "dijkstra", expanded=100, cost=2.0)
    _write_run(astar, "astar", expanded=40, cost=2.0)
    result = compare_exact_solver_runs(dijkstra, astar)
    assert result["n_paired_trials"] == 1
    assert result["max_optimal_cost_delta"] == 0.0
    assert result["mean_heuristic_savings"] == pytest.approx(
        1.0 - 41.0 / 101.0
    )


def test_exact_solver_comparison_rejects_cost_disagreement(tmp_path: Path) -> None:
    dijkstra = tmp_path / "dijkstra"
    astar = tmp_path / "astar"
    _write_run(dijkstra, "dijkstra", expanded=100, cost=2.0)
    _write_run(astar, "astar", expanded=40, cost=2.1)
    with pytest.raises(ValueError, match="optimal-cost disagreement"):
        compare_exact_solver_runs(dijkstra, astar)
