"""Tests for equal valid-node matching (IM-018 / ADR-010)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from inequality_mechanisms.experiments import (
    ExperimentConfig,
    build_paired_graphs_from_parts,
    load_experiment_config,
    run_pilot,
)
from inequality_mechanisms.experiments.equal_nodes import (
    gearbox_grid_over_limits,
    match_gearbox_to_fourbar_valid_count,
)
from inequality_mechanisms.graphs.grid import PeriodicGrid2D
from inequality_mechanisms.graphs.validation import ConstrainedInputGraph
from inequality_mechanisms.mechanisms import IndependentFourBars, UnitGearbox
from inequality_mechanisms.mechanisms.population import (
    limits_from_fourbar_follower_ranges,
    sample_independent_crank_rockers,
)

_REPO = Path(__file__).resolve().parents[2]
_EQUAL = _REPO / "configs" / "pilot.equal_nodes.v1.yaml"
_CR_D1 = (0.5, 1.25, 1.0, 1.0)


class TestEqualNodesHelpers:
    def test_match_within_tolerance(self) -> None:
        fb = IndependentFourBars.from_lengths([_CR_D1, _CR_D1], branch=1)
        limits = limits_from_fourbar_follower_ranges(fb, n_samples=91)
        fb_grid = PeriodicGrid2D((12, 12), wrap=(True, True))
        fb_graph = ConstrainedInputGraph(fb_grid, fb, limits, edge_samples=5)
        gb = UnitGearbox(dim=2)
        grid, graph, meta = match_gearbox_to_fourbar_valid_count(
            gearbox_mechanism=gb,
            fourbar_graph=fb_graph,
            limits=limits,
            edge_samples=5,
            relative_tol=0.15,
            shape_hi=48,
        )
        target = fb_graph.valid_node_count
        assert abs(graph.valid_node_count - target) / target <= 0.15
        assert meta["match_mode"] == "equal_valid_nodes"
        assert grid.wrap == (False, False)
        assert grid.ranges[0][0] == pytest.approx(float(limits.lower[0]))

    def test_gearbox_grid_over_limits_ranges(self) -> None:
        fb = IndependentFourBars.from_lengths([_CR_D1, _CR_D1], branch=1)
        limits = limits_from_fourbar_follower_ranges(fb, n_samples=91)
        grid = gearbox_grid_over_limits(limits, (8, 8))
        assert grid.shape == (8, 8)
        assert grid.wrap == (False, False)


class TestEqualNodesPilot:
    def test_equal_nodes_config_loads(self) -> None:
        cfg = load_experiment_config(_EQUAL)
        assert cfg.graph.match_valid_nodes is True
        assert cfg.trials.n_trials == 30
        assert cfg.trials.n_path_samples == 2

    def test_small_equal_node_pilot_with_paths(self, tmp_path: Path) -> None:
        cfg = ExperimentConfig.model_validate(
            {
                "seed": 1,
                "mechanisms": {
                    "gearbox": UnitGearbox(dim=2).to_dict(),
                    "fourbar": {
                        "mode": "population",
                        "n_bars": 2,
                        "d": 1.0,
                        "n_crank_samples": 91,
                    },
                },
                "graph": {
                    "shape": [12, 12],
                    "wrap": [True, True],
                    "edge_samples": 5,
                    "match_valid_nodes": True,
                    "match_relative_tol": 0.15,
                    "match_shape_hi": 48,
                },
                "cost": {"type": "output_euclidean"},
                "algorithms": {"names": ["dijkstra", "astar"]},
                "trials": {
                    "n_trials": 3,
                    "min_output_separation": 0.05,
                    "preimage_policy": "lex_min_node_id",
                    "max_sample_attempts": 2000,
                    "require_reachable": True,
                    "n_path_samples": 1,
                },
            }
        )
        run = run_pilot(cfg, results_root=tmp_path, run_id="eq_smoke")
        assert run.status == "completed"
        rows = run.read_jsonl("trials")
        assert len(rows) == 12
        for row in rows:
            assert "match_meta" in row
            mm = row["match_meta"]
            assert mm["gearbox_valid_nodes"] > 0
            assert mm["fourbar_valid_nodes"] > 0
            rel = abs(mm["gearbox_valid_nodes"] - mm["fourbar_valid_nodes"]) / mm[
                "fourbar_valid_nodes"
            ]
            assert rel <= 0.15 + 1e-9
            assert row["match_meta"]["gearbox_grid_shape"] != row["match_meta"][
                "fourbar_grid_shape"
            ] or row["match_meta"]["gearbox_valid_nodes"] == row["match_meta"][
                "fourbar_valid_nodes"
            ]
        path_png = run.path / "outputs" / "paths" / "trial_0000" / "gearbox_input.png"
        assert path_png.is_file()
        assert (run.path / "outputs" / "expansions_raw.png").is_file()


class TestDualGridNativeStillShares:
    def test_shared_grid_object_when_no_match(self) -> None:
        fb_mech = sample_independent_crank_rockers(np.random.default_rng(0), n_bars=2)
        limits = limits_from_fourbar_follower_ranges(fb_mech, n_samples=91)
        grid = PeriodicGrid2D((8, 8))
        paired = build_paired_graphs_from_parts(
            grid=grid,
            limits=limits,
            gearbox_mechanism=UnitGearbox(dim=2),
            fourbar_mechanism=fb_mech,
            edge_samples=5,
        )
        assert paired.gearbox.grid is paired.fourbar.grid
        assert paired.match_meta is None
