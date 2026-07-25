"""Tests for experiment configuration schema (IM-014)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from inequality_mechanisms.experiments import (
    ExperimentConfig,
    FourBarPopulationSource,
    experiment_config_to_yaml,
    load_experiment_config,
)
from inequality_mechanisms.mechanisms import IndependentFourBars, UnitGearbox

_REPO = Path(__file__).resolve().parents[2]
_PILOT = _REPO / "configs" / "pilot.v1.yaml"
_CR = (1.0, 2.5, 2.0, 2.0)


def _minimal_dict(**overrides: object) -> dict:
    data: dict = {
        "seed": 1,
        "mechanisms": {
            "gearbox": UnitGearbox(dim=2).to_dict(),
            "fourbar": IndependentFourBars.from_lengths([_CR, _CR]).to_dict(),
        },
        "graph": {"shape": [8, 8], "wrap": [True, True]},
        "limits": {"lower": [1.0, 1.0], "upper": [2.0, 2.0]},
        "cost": {"type": "output_euclidean"},
        "algorithms": {"names": ["dijkstra", "astar"]},
        "trials": {"n_trials": 4, "preimage_policy": "lex_min_node_id"},
    }
    data.update(overrides)
    return data


def _population_dict(**overrides: object) -> dict:
    data: dict = {
        "seed": 2,
        "mechanisms": {
            "gearbox": UnitGearbox(dim=2).to_dict(),
            "fourbar": {
                "mode": "population",
                "n_bars": 2,
                "d": 1.0,
                "length_low": 0.2,
                "length_high": 2.0,
            },
        },
        "graph": {"shape": [8, 8], "wrap": [True, True]},
        "cost": {"type": "output_euclidean"},
        "algorithms": {"names": ["dijkstra"]},
        "trials": {"n_trials": 2, "preimage_policy": "lex_min_node_id"},
    }
    data.update(overrides)
    return data


class TestExperimentConfig:
    def test_pilot_yaml_loads(self) -> None:
        cfg = load_experiment_config(_PILOT)
        assert cfg.seed == 0
        assert cfg.trials.n_trials == 250
        assert cfg.graph.shape == (16, 16)
        assert cfg.trials.require_reachable is True
        assert cfg.cost.type == "output_euclidean"
        assert cfg.limits is None
        assert cfg.mechanisms.fourbar_mode == "population"
        assert isinstance(cfg.mechanisms.fourbar, FourBarPopulationSource)
        gb = cfg.mechanisms.build_gearbox()
        assert gb.input_dim == 2
        with pytest.raises(TypeError, match="fixed"):
            cfg.mechanisms.build_fourbar()

    def test_population_mode_forbids_limits(self) -> None:
        with pytest.raises(ValidationError, match="limits must be omitted"):
            ExperimentConfig.model_validate(
                _population_dict(limits={"lower": [1.0, 1.0], "upper": [2.0, 2.0]})
            )

    def test_fixed_mode_requires_limits(self) -> None:
        data = _minimal_dict()
        data.pop("limits")
        with pytest.raises(ValidationError, match="limits are required"):
            ExperimentConfig.model_validate(data)

    def test_legacy_bare_fourbar_dict_is_fixed(self) -> None:
        cfg = ExperimentConfig.model_validate(_minimal_dict())
        assert cfg.mechanisms.fourbar_mode == "fixed"
        fb = cfg.mechanisms.build_fourbar()
        assert fb.input_dim == 2

    def test_round_trip_yaml(self) -> None:
        cfg = ExperimentConfig.model_validate(_minimal_dict())
        text = experiment_config_to_yaml(cfg)
        restored = ExperimentConfig.model_validate(__import__("yaml").safe_load(text))
        assert restored.seed == cfg.seed
        assert restored.graph.shape == cfg.graph.shape
        assert restored.mechanisms.gearbox["type"] == "unit_gearbox"

    def test_population_round_trip_yaml(self) -> None:
        cfg = ExperimentConfig.model_validate(_population_dict())
        text = experiment_config_to_yaml(cfg)
        restored = ExperimentConfig.model_validate(__import__("yaml").safe_load(text))
        assert restored.mechanisms.fourbar_mode == "population"
        assert restored.limits is None

    def test_rejects_unknown_top_level_key(self) -> None:
        with pytest.raises(ValidationError):
            ExperimentConfig.model_validate(_minimal_dict(extra_field=True))

    def test_rejects_bad_shape(self) -> None:
        data = _minimal_dict()
        data["graph"] = {"shape": [1, 8]}
        with pytest.raises(ValidationError):
            ExperimentConfig.model_validate(data)

    def test_rejects_limit_dim_mismatch(self) -> None:
        data = _minimal_dict()
        data["limits"] = {"lower": [0.0], "upper": [1.0]}
        with pytest.raises(ValidationError):
            ExperimentConfig.model_validate(data)

    def test_rejects_empty_algorithms(self) -> None:
        data = _minimal_dict()
        data["algorithms"] = {"names": []}
        with pytest.raises(ValidationError):
            ExperimentConfig.model_validate(data)

    def test_rejects_mechanism_without_type(self) -> None:
        data = _minimal_dict()
        data["mechanisms"]["gearbox"] = {"dim": 2}
        with pytest.raises(ValidationError):
            ExperimentConfig.model_validate(data)

    def test_limits_to_limits(self) -> None:
        cfg = ExperimentConfig.model_validate(_minimal_dict())
        assert cfg.limits is not None
        limits = cfg.limits.to_limits()
        assert limits.dim == 2
        assert limits.contains([1.5, 1.5]) is True

    def test_non_mapping_yaml_root(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.yaml"
        path.write_text("- just\n- a\n- list\n", encoding="utf-8")
        with pytest.raises(ValueError, match="mapping"):
            load_experiment_config(path)
