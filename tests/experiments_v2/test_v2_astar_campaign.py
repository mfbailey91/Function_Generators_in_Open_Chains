from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import yaml

from inequality_mechanisms.experiments.v2_production_config import (
    V2ProductionConfigError,
    load_v2_production_config,
    validate_v2_production_config_mapping,
)
from inequality_mechanisms.experiments.v2_production_sample_bank import (
    build_v2_sample_bank,
)
from inequality_mechanisms.experiments.v2_production_work_unit import (
    run_mechanism_pair_work_unit,
)

REPO = Path(__file__).resolve().parents[2]
DIJKSTRA = REPO / "configs" / "v2" / "production_dijkstra_smoke.yaml"
ASTAR = REPO / "configs" / "v2" / "production_astar_smoke.yaml"


def test_astar_config_is_single_solver_with_frozen_heuristic() -> None:
    config = load_v2_production_config(ASTAR)
    assert config.study.name == "production_monte_carlo_astar"
    assert config.search.algorithm == "astar"
    assert config.search.resolved_heuristic == "input_euclidean"


def test_astar_zero_heuristic_is_rejected() -> None:
    raw = yaml.safe_load(ASTAR.read_text())
    raw["search"]["heuristic"] = "zero"
    with pytest.raises(V2ProductionConfigError, match="input_euclidean"):
        validate_v2_production_config_mapping(raw)


def test_dijkstra_nonzero_heuristic_is_rejected() -> None:
    raw = yaml.safe_load(DIJKSTRA.read_text())
    raw["search"]["heuristic"] = "input_euclidean"
    with pytest.raises(V2ProductionConfigError, match="Dijkstra"):
        validate_v2_production_config_mapping(raw)


def test_astar_and_dijkstra_return_identical_optimal_costs() -> None:
    dijkstra = load_v2_production_config(DIJKSTRA)
    astar = load_v2_production_config(ASTAR)
    bank = build_v2_sample_bank(dijkstra, n_mechanisms=1, n_tasks=2)
    mechanism = bank.mechanisms[0]
    d_result = run_mechanism_pair_work_unit(
        dijkstra, bank, mechanism, run_id="dijkstra", shape=(8, 8)
    )
    a_result = run_mechanism_pair_work_unit(
        astar, bank, mechanism, run_id="astar", shape=(8, 8)
    )
    assert d_result.status == a_result.status == "completed"
    d_rows = {(r["mechanism_id"], r["task_id"]): r for r in d_result.trials}
    a_rows = {(r["mechanism_id"], r["task_id"]): r for r in a_result.trials}
    assert d_rows.keys() == a_rows.keys()
    for key in d_rows:
        assert d_rows[key]["found"] == a_rows[key]["found"]
        assert np.isclose(
            float(d_rows[key]["optimal_cost"]),
            float(a_rows[key]["optimal_cost"]),
            rtol=0.0,
            atol=1.0e-10,
        )
        assert a_rows[key]["solver_id"] == "astar"
        assert a_rows[key]["heuristic_id"] == "input_euclidean"
        assert int(a_rows[key]["n_heuristic_calls"]) >= 1


def test_production_and_confirmation_reuse_v2_10_artifacts() -> None:
    production = load_v2_production_config(
        REPO / "configs" / "v2" / "production_astar.yaml"
    )
    confirmation = load_v2_production_config(
        REPO / "configs" / "v2" / "production_astar_confirmation.yaml"
    )
    assert production.study.reference_run == "results/v2_10_production"
    assert confirmation.study.reference_run == "results/v2_10_confirmation"
    assert confirmation.study.confirmation_subset == (
        "results/v2_10_confirmation/confirmation_subset.json"
    )
    assert production.study.sample_bank == confirmation.study.sample_bank
    assert production.population.production_shape_n == 64
    assert confirmation.population.production_shape_n == 64
    assert production.population.tasks_per_mechanism == 8
    assert confirmation.population.tasks_per_mechanism == 8
