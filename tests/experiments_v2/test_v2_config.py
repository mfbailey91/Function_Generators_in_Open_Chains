"""Strict Version 2 config rejection tests (Sprint V2.4, V2-401)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from tests.experiments_v2._config_fixtures import base_v2_config_mapping

from inequality_mechanisms.experiments.v2_config import (
    V2ConfigError,
    V2ExperimentConfig,
    load_v2_experiment_config,
    v2_experiment_config_to_yaml,
    validate_v2_config_mapping,
)

_REPO = Path(__file__).resolve().parents[2]


class TestValidConfigAccepted:
    def test_base_mapping_is_valid(self) -> None:
        cfg = validate_v2_config_mapping(base_v2_config_mapping())
        assert isinstance(cfg, V2ExperimentConfig)
        assert cfg.architecture_version == 2
        assert cfg.result_schema_version == 2
        assert cfg.mechanisms.dim == 2
        assert cfg.objective.resolved_heuristic() == "output_euclidean"

    def test_smoke_config_loads(self) -> None:
        cfg = load_v2_experiment_config(_REPO / "configs" / "v2" / "smoke.yaml")
        assert cfg.architecture_version == 2
        assert cfg.mechanisms.comparison == "fourbar_vs_equivalent_affine_gearbox"

    def test_round_trip_yaml(self) -> None:
        cfg = validate_v2_config_mapping(base_v2_config_mapping())
        text = v2_experiment_config_to_yaml(cfg)
        restored = validate_v2_config_mapping(yaml.safe_load(text))
        assert restored.seed == cfg.seed
        assert restored.sampling.shape == cfg.sampling.shape

    def test_default_heuristic_resolved_when_omitted(self) -> None:
        data = base_v2_config_mapping()
        data["objective"] = {"cost": "uniform"}
        cfg = validate_v2_config_mapping(data)
        assert cfg.objective.resolved_heuristic() == "uniform_step"

    def test_explicit_pairs_accepted(self) -> None:
        data = base_v2_config_mapping()
        data["tasks"]["pairs"] = [{"start_q": [1.0, 1.0], "goal_q": [2.0, 2.0]}]
        cfg = validate_v2_config_mapping(data)
        assert cfg.tasks.pairs is not None
        assert len(cfg.tasks.pairs) == 1


class TestMissingOrUnsupportedArchitectureVersion:
    def test_missing_architecture_version_rejected(self) -> None:
        data = base_v2_config_mapping()
        del data["architecture_version"]
        with pytest.raises(V2ConfigError):
            validate_v2_config_mapping(data)

    def test_architecture_version_1_rejected(self) -> None:
        data = base_v2_config_mapping()
        data["architecture_version"] = 1
        with pytest.raises(V2ConfigError, match="not a Version 2 config"):
            validate_v2_config_mapping(data)

    def test_unsupported_architecture_version_rejected(self) -> None:
        data = base_v2_config_mapping()
        data["architecture_version"] = 3
        with pytest.raises(V2ConfigError):
            validate_v2_config_mapping(data)


class TestPlanningSpace:
    def test_missing_planning_space_rejected(self) -> None:
        data = base_v2_config_mapping()
        del data["planning_space"]
        with pytest.raises(V2ConfigError):
            validate_v2_config_mapping(data)

    def test_non_output_planning_space_rejected(self) -> None:
        data = base_v2_config_mapping()
        data["planning_space"] = "input"
        with pytest.raises(V2ConfigError, match="planning_space"):
            validate_v2_config_mapping(data)


class TestWrappedTopologyRejected:
    def test_wrapped_graph_block_rejected(self) -> None:
        data = base_v2_config_mapping()
        data["graph"] = {"shape": [8, 8], "wrap": [True, False]}
        with pytest.raises(V2ConfigError, match="nonperiodic"):
            validate_v2_config_mapping(data)

    def test_unwrapped_graph_block_still_forbidden_extra(self) -> None:
        data = base_v2_config_mapping()
        data["graph"] = {"shape": [8, 8], "wrap": [False, False]}
        with pytest.raises(Exception):
            validate_v2_config_mapping(data)


class TestFullCycleBranchRejected:
    def test_full_cycle_selection_rejected(self) -> None:
        data = base_v2_config_mapping()
        data["branch"]["selection"] = "full_cycle"
        with pytest.raises(V2ConfigError, match="full_cycle"):
            validate_v2_config_mapping(data)

    def test_unknown_selection_rejected(self) -> None:
        data = base_v2_config_mapping()
        data["branch"]["selection"] = "not_a_real_method"
        with pytest.raises(Exception):
            validate_v2_config_mapping(data)


class TestCostHeuristicCombinations:
    def test_incompatible_pair_rejected(self) -> None:
        data = base_v2_config_mapping()
        data["objective"] = {"cost": "uniform", "heuristic": "output_euclidean"}
        with pytest.raises(Exception):
            validate_v2_config_mapping(data)

    def test_input_euclidean_heuristic_rejected_for_output_cost(self) -> None:
        data = base_v2_config_mapping()
        data["objective"] = {"cost": "output_euclidean", "heuristic": "input_euclidean"}
        with pytest.raises(Exception):
            validate_v2_config_mapping(data)

    def test_zero_heuristic_always_compatible(self) -> None:
        for cost in ("uniform", "output_euclidean", "input_euclidean"):
            data = base_v2_config_mapping()
            data["objective"] = {"cost": cost, "heuristic": "zero"}
            cfg = validate_v2_config_mapping(data)
            assert cfg.objective.resolved_heuristic() == "zero"

    def test_unknown_cost_rejected(self) -> None:
        data = base_v2_config_mapping()
        data["objective"] = {"cost": "capability_energy"}
        with pytest.raises(Exception):
            validate_v2_config_mapping(data)


class TestDimensionAndSampleCounts:
    def test_nonpositive_dim_rejected(self) -> None:
        data = base_v2_config_mapping()
        data["mechanisms"]["dim"] = 0
        with pytest.raises(Exception):
            validate_v2_config_mapping(data)

    def test_shape_entry_below_two_rejected(self) -> None:
        data = base_v2_config_mapping()
        data["sampling"]["shape"] = [1, 8]
        with pytest.raises(Exception):
            validate_v2_config_mapping(data)

    def test_certification_samples_below_three_rejected(self) -> None:
        data = base_v2_config_mapping()
        data["branch"]["certification_samples_per_axis"] = 2
        with pytest.raises(Exception):
            validate_v2_config_mapping(data)

    def test_nonpositive_minimum_abs_gain_rejected(self) -> None:
        data = base_v2_config_mapping()
        data["branch"]["minimum_abs_gain"] = 0.0
        with pytest.raises(Exception):
            validate_v2_config_mapping(data)

    def test_shape_dim_mismatch_rejected(self) -> None:
        data = base_v2_config_mapping()
        data["sampling"]["shape"] = [8, 8, 8]
        with pytest.raises(Exception):
            validate_v2_config_mapping(data)

    def test_include_endpoints_false_rejected(self) -> None:
        data = base_v2_config_mapping()
        data["sampling"]["include_endpoints"] = False
        with pytest.raises(Exception):
            validate_v2_config_mapping(data)


class TestV1OnlyFieldsRejected:
    def test_preimage_policy_rejected(self) -> None:
        data = base_v2_config_mapping()
        data["tasks"]["preimage_policy"] = "lex_min_node_id"
        with pytest.raises(V2ConfigError, match="preimage_policy"):
            validate_v2_config_mapping(data)

    def test_root_must_be_mapping(self) -> None:
        with pytest.raises(V2ConfigError, match="mapping"):
            validate_v2_config_mapping([1, 2, 3])  # type: ignore[arg-type]

    def test_legacy_v1_pilot_config_rejected(self) -> None:
        raw = yaml.safe_load((_REPO / "configs" / "pilot.v1.yaml").read_text())
        with pytest.raises(V2ConfigError):
            validate_v2_config_mapping(raw)
