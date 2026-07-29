"""Tests for Sprint Four factorial runner and landscape (S4-06–S4-08)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from inequality_mechanisms.experiments import (
    ExperimentConfig,
    load_experiment_config,
    run_sprint4,
)
from inequality_mechanisms.graphs import ConstrainedInputGraph, PeriodicGrid2D
from inequality_mechanisms.mechanisms import UnitGearbox
from inequality_mechanisms.search import dijkstra, resolve_planning_objective
from inequality_mechanisms.spaces import OutputJointLimits
from inequality_mechanisms.visualization.landscape import write_landscape_bundle

_REPO = Path(__file__).resolve().parents[2]
_SMOKE = _REPO / "configs" / "sprint4.smoke.v1.yaml"


class TestSprint4Config:
    def test_smoke_yaml_loads(self) -> None:
        cfg = load_experiment_config(_SMOKE)
        assert cfg.cost.types == [
            "uniform",
            "input_euclidean",
            "output_euclidean",
        ]
        assert cfg.sprint4.bootstrap_n_samples == 50
        assert cfg.trials.n_trials == 2

    def test_cost_types_reject_duplicates(self) -> None:
        with pytest.raises(ValidationError):
            ExperimentConfig.model_validate(
                {
                    "seed": 0,
                    "mechanisms": {
                        "gearbox": {
                            "type": "unit_gearbox",
                            "dim": 2,
                            "periodic": [True, True],
                        },
                        "fourbar": {
                            "mode": "fixed",
                            "mechanism": {
                                "type": "independent_fourbars",
                                "bars": [
                                    {
                                        "type": "planar_fourbar",
                                        "a": 1.0,
                                        "b": 2.5,
                                        "c": 2.0,
                                        "d": 2.0,
                                    },
                                    {
                                        "type": "planar_fourbar",
                                        "a": 1.0,
                                        "b": 2.5,
                                        "c": 2.0,
                                        "d": 2.0,
                                    },
                                ],
                            },
                        },
                    },
                    "graph": {"shape": [4, 4]},
                    "limits": {"lower": [0.5, 0.5], "upper": [2.5, 2.5]},
                    "cost": {"types": ["uniform", "uniform"]},
                    "algorithms": {"names": ["dijkstra"]},
                    "trials": {"n_trials": 1},
                }
            )


class TestLandscapeBundle:
    def test_writes_required_files(self, tmp_path: Path) -> None:
        grid = PeriodicGrid2D(
            (5, 5), ranges=((0.0, 5.0), (0.0, 5.0)), wrap=(False, False)
        )
        mech = UnitGearbox(dim=2)
        limits = OutputJointLimits.box(lower=[0.0, 0.0], upper=[5.0, 5.0])
        graph = ConstrainedInputGraph(grid, mech, limits)
        start = graph.grid.node_id(0, 0)
        goal = graph.grid.node_id(3, 2)
        obj = resolve_planning_objective(graph, goal, "uniform")
        result = dijkstra(
            graph, start, goal, edge_cost=obj.edge_cost, record_expanded=True
        )
        assert result.found
        out = tmp_path / "landscape"
        metrics = write_landscape_bundle(
            graph,
            start=start,
            goal=goal,
            path=result.path,
            expanded=result.expanded_nodes,
            cost_type="uniform",
            out_dir=out,
            c_star=float(result.cost),
        )
        required = [
            "valid_nodes.png",
            "reachable_nodes.png",
            "edge_cost_field.png",
            "mechanism_gain_field.png",
            "distance_from_start.png",
            "distance_to_goal.png",
            "expanded_mask.png",
            "goal_cost_basin.png",
            "optimal_path.png",
            "landscape_metrics.json",
        ]
        for name in required:
            assert (out / name).is_file(), name
        assert "beta" in metrics
        assert "eta_reachable" in metrics


class TestRunSprint4:
    def test_smoke_factorial(self, tmp_path: Path) -> None:
        cfg = load_experiment_config(_SMOKE)
        run = run_sprint4(cfg, results_root=tmp_path, run_id="sprint4_smoke")
        assert run.status == "completed"
        rows = run.read_jsonl("trials")
        # 2 trials × 2 mechanisms × 3 costs × 2 algorithms
        assert len(rows) == 24
        summary = run.read_json("summary")
        assert summary["result_schema_version"] == "4.1.0"
        assert summary["cost_types"] == [
            "uniform",
            "input_euclidean",
            "output_euclidean",
        ]
        assert "savings" in run.outputs
        assert "bootstrap_cis" in run.outputs
        assert "descriptors" in run.outputs
        assert (run.path / "index.html").is_file()
        assert (run.outputs_dir / "astar_vs_dijkstra.png").is_file()
        assert (run.outputs_dir / "savings_by_mechanism_cost.png").is_file()

        for row in rows:
            assert row["result_schema_version"] == "4.1.0"
            assert "runtime_s" in row
            assert "edge_cost_variance" in row
            if row["found"]:
                assert row["beta"] is not None
                assert row["n_reachable_nodes"] is not None

        # Dijkstra and A* agree on C* within each (trial, mech, cost).
        by_key: dict[tuple, dict] = {}
        for row in rows:
            key = (row["trial_index"], row["mechanism"], row["cost_type"])
            by_key.setdefault(key, {})[row["algorithm"]] = row
        for pair in by_key.values():
            d = pair.get("dijkstra")
            a = pair.get("astar")
            if d and a and d["found"] and a["found"]:
                assert a["optimal_cost"] == pytest.approx(
                    d["optimal_cost"], abs=1e-9
                )

        boot = run.read_json("bootstrap_cis")
        assert boot["n_bootstrap_samples"] == 50
        assert boot["intervals"]
