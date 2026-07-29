"""Tests for equal-cost Dijkstra / A* path comparison (S5-07)."""

from __future__ import annotations

from inequality_mechanisms.metrics.equal_cost_paths import (
    compare_equal_cost_pair,
    compare_equal_cost_rows,
)


def test_same_cost_same_path() -> None:
    d = {
        "trial_index": 0,
        "mechanism": "gearbox",
        "cost_type": "uniform",
        "optimal_cost": 3.0,
        "_path": [1, 2, 3, 4],
        "n_path_edges": 3,
        "path_length_u": 3.0,
    }
    a = {
        **d,
        "algorithm": "astar",
    }
    d = {**d, "algorithm": "dijkstra"}
    cmp = compare_equal_cost_pair(d, a)
    assert cmp["same_optimal_cost"]
    assert cmp["same_node_path"]
    assert cmp["secondary_deltas"] == {}


def test_same_cost_different_path_records_deltas() -> None:
    d = {
        "trial_index": 0,
        "mechanism": "gearbox",
        "cost_type": "uniform",
        "algorithm": "dijkstra",
        "optimal_cost": 4.0,
        "_path": [1, 2, 3, 4, 5],
        "n_path_edges": 4,
        "path_length_u": 4.0,
        "path_length_q": 2.0,
        "path_length_x": 2.5,
        "directness_ratio_q": 1.2,
        "directness_ratio_x": 1.3,
        "cumulative_turning_q": 1.0,
        "cumulative_turning_x": 1.5,
        "self_intersections_q": 0,
        "self_intersections_x": 1,
        "near_revisit_distance_q": 0.2,
        "near_revisit_distance_x": 0.1,
    }
    a = {
        **d,
        "algorithm": "astar",
        "_path": [1, 6, 7, 5],
        "n_path_edges": 3,
        "path_length_u": 3.0,
        "path_length_q": 2.5,
        "cumulative_turning_x": 2.0,
        "self_intersections_x": 0,
    }
    cmp = compare_equal_cost_pair(d, a)
    assert cmp["same_optimal_cost"]
    assert not cmp["same_node_path"]
    assert cmp["secondary_deltas"]["n_path_edges"] == -1.0
    assert cmp["secondary_deltas"]["self_intersections_x"] == -1.0


def test_compare_rows_aggregates_by_cost() -> None:
    rows = [
        {
            "found": True,
            "trial_index": 0,
            "mechanism": "gearbox",
            "cost_type": "uniform",
            "algorithm": "dijkstra",
            "optimal_cost": 1.0,
            "_path": [0, 1],
        },
        {
            "found": True,
            "trial_index": 0,
            "mechanism": "gearbox",
            "cost_type": "uniform",
            "algorithm": "astar",
            "optimal_cost": 1.0,
            "_path": [0, 2, 1],
        },
    ]
    report = compare_equal_cost_rows(rows)
    assert report["n_matched_pairs"] == 1
    assert report["n_same_optimal_cost"] == 1
    assert report["n_diff_node_path_same_cost"] == 1
    assert report["by_cost_type"]["uniform"]["n_diff_node_path_same_cost"] == 1
