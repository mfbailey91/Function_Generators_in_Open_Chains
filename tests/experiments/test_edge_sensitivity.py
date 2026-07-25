"""Tests for IM-037 edge-validation sensitivity helpers."""

from __future__ import annotations

from inequality_mechanisms.experiments.edge_sensitivity import (
    edge_sensitivity_stable,
    rows_to_csv,
    run_edge_sensitivity,
)


class TestEdgeSensitivity:
    def test_sweep_runs_and_reports_stability(self) -> None:
        rows = run_edge_sensitivity(
            shape=(10, 10),
            seed=0,
            edge_samples_grid=(5, 9, 17, 33),
        )
        assert [r.edge_samples for r in rows] == [5, 9, 17, 33]
        assert all(r.n_valid_nodes_fourbar >= 1 for r in rows)
        csv = rows_to_csv(rows)
        assert "edge_samples" in csv.splitlines()[0]
        # Stability helper should return a bool without raising.
        assert isinstance(edge_sensitivity_stable(rows), bool)
