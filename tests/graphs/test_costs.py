"""Tests for configuration-driven edge-cost registry (S4-01)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from inequality_mechanisms.experiments import ExperimentConfig, load_experiment_config
from inequality_mechanisms.graphs import (
    KNOWN_COST_TYPES,
    ConstrainedInputGraph,
    PeriodicGrid2D,
    build_edge_cost,
    input_euclidean_cost,
    uniform_edge_cost,
)
from inequality_mechanisms.mechanisms import IndependentFourBars, UnitGearbox
from inequality_mechanisms.spaces import OutputJointLimits

_REPO = __import__("pathlib").Path(__file__).resolve().parents[2]
_CR = (1.0, 2.5, 2.0, 2.0)


def _graph() -> ConstrainedInputGraph:
    grid = PeriodicGrid2D((4, 4), wrap=(True, True))
    mech = UnitGearbox(dim=2)
    limits = OutputJointLimits.box(lower=[0.0, 0.0], upper=[2.0 * 3.1416, 2.0 * 3.1416])
    return ConstrainedInputGraph(grid, mech, limits, edge_samples=3)


class TestCostRegistry:
    def test_known_cost_types(self) -> None:
        assert KNOWN_COST_TYPES == {
            "uniform",
            "input_euclidean",
            "output_euclidean",
        }

    def test_build_edge_cost_rejects_unknown(self) -> None:
        with pytest.raises(ValueError, match="unknown cost"):
            build_edge_cost(_graph(), "torque")

    def test_uniform_is_one(self) -> None:
        g = _graph()
        c = build_edge_cost(g, "uniform")
        u = g.grid.node_id(0, 0)
        v = g.grid.node_id(0, 1)
        assert c(u, v) == pytest.approx(1.0)
        assert uniform_edge_cost(u, v) == pytest.approx(1.0)

    def test_input_matches_helper(self) -> None:
        g = _graph()
        via_registry = build_edge_cost(g, "input_euclidean")
        via_helper = input_euclidean_cost(g)
        u = g.grid.node_id(1, 1)
        v = g.grid.node_id(2, 1)
        assert via_registry(u, v) == pytest.approx(via_helper(u, v))

    def test_config_accepts_all_costs(self) -> None:
        for cost in sorted(KNOWN_COST_TYPES):
            cfg = ExperimentConfig.model_validate(
                {
                    "seed": 0,
                    "mechanisms": {
                        "gearbox": UnitGearbox(dim=2).to_dict(),
                        "fourbar": IndependentFourBars.from_lengths(
                            [_CR, _CR]
                        ).to_dict(),
                    },
                    "graph": {"shape": [4, 4]},
                    "limits": {"lower": [0.5, 0.5], "upper": [2.5, 2.5]},
                    "cost": {"type": cost},
                    "algorithms": {"names": ["dijkstra"]},
                    "trials": {"n_trials": 1},
                }
            )
            assert cfg.cost.type == cost

    def test_config_rejects_unknown_cost(self) -> None:
        with pytest.raises(ValidationError):
            ExperimentConfig.model_validate(
                {
                    "seed": 0,
                    "mechanisms": {
                        "gearbox": UnitGearbox(dim=2).to_dict(),
                        "fourbar": IndependentFourBars.from_lengths(
                            [_CR, _CR]
                        ).to_dict(),
                    },
                    "graph": {"shape": [4, 4]},
                    "limits": {"lower": [0.5, 0.5], "upper": [2.5, 2.5]},
                    "cost": {"type": "torque"},
                    "algorithms": {"names": ["dijkstra"]},
                    "trials": {"n_trials": 1},
                }
            )

    def test_example_yamls_load(self) -> None:
        for name in ("pilot.cost_uniform.v1.yaml", "pilot.cost_input.v1.yaml"):
            cfg = load_experiment_config(_REPO / "configs" / name)
            assert cfg.cost.type in KNOWN_COST_TYPES
