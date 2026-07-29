"""Version 1 serialization and architecture-compatibility goldens."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from inequality_mechanisms.experiments.architecture import (
    ArchitectureCompatibilityError,
    classify_architecture_version,
)
from inequality_mechanisms.experiments.config import (
    ExperimentConfig,
    experiment_config_to_yaml,
    load_experiment_config,
)

_DATA = Path(__file__).resolve().parent / "data"
_REPO = Path(__file__).resolve().parents[2]


def test_v1_config_yaml_round_trip() -> None:
    path = _DATA / "fixture_v1_config.yaml"
    cfg = load_experiment_config(path)
    text = experiment_config_to_yaml(cfg)
    restored = ExperimentConfig.model_validate(yaml.safe_load(text))
    assert restored.seed == cfg.seed
    assert restored.graph.shape == cfg.graph.shape
    assert restored.cost.type == cfg.cost.type
    assert restored.trials.preimage_policy == cfg.trials.preimage_policy


def test_legacy_pilot_config_is_version_1() -> None:
    data = yaml.safe_load((_REPO / "configs" / "pilot.v1.yaml").read_text())
    assert classify_architecture_version(data) == 1


def test_missing_architecture_version_means_v1() -> None:
    data = yaml.safe_load((_DATA / "fixture_v1_config.yaml").read_text())
    assert "architecture_version" not in data
    assert classify_architecture_version(data) == 1


def test_rejects_output_planning_space_on_v1() -> None:
    data = yaml.safe_load((_DATA / "fixture_v1_config.yaml").read_text())
    data["planning_space"] = "output"
    with pytest.raises(ArchitectureCompatibilityError, match="architecture_version: 2"):
        classify_architecture_version(data)


def test_v2_requires_planning_space_output() -> None:
    data = {
        "architecture_version": 2,
        "planning_space": "input",
        "branch": {},
        "sampling": {"domain": "output", "shape": [8, 8]},
    }
    with pytest.raises(ArchitectureCompatibilityError, match="planning_space: output"):
        classify_architecture_version(data)


def test_v2_rejects_preimage_policy() -> None:
    data = {
        "architecture_version": 2,
        "planning_space": "output",
        "branch": {},
        "sampling": {"domain": "input", "shape": [8, 8]},
        "trials": {"preimage_policy": "lex_min_node_id"},
    }
    with pytest.raises(ArchitectureCompatibilityError, match="preimage_policy"):
        classify_architecture_version(data)


def test_v2_rejects_wrapped_topology() -> None:
    data = {
        "architecture_version": 2,
        "planning_space": "output",
        "branch": {},
        "sampling": {"domain": "input", "shape": [8, 8]},
        "graph": {"shape": [8, 8], "wrap": [True, False]},
    }
    with pytest.raises(ArchitectureCompatibilityError, match="nonperiodic"):
        classify_architecture_version(data)


def test_valid_v2_mapping_classifies() -> None:
    data = {
        "architecture_version": 2,
        "planning_space": "output",
        "branch": {"selection": "monotonic_interval"},
        "sampling": {"domain": "input", "shape": [8, 8]},
        "graph": {"shape": [8, 8], "wrap": [False, False]},
    }
    assert classify_architecture_version(data) == 2
