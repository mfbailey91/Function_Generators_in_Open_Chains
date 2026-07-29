"""Version 1 commands/configs must keep resolving through the V1 path only.

Sprint V2.4, V2-408: adding the Version 2 pipeline must not change how any
existing Version 1 config loads, and Version 1 files must never be routed
through the Version 2 loader or runner.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from inequality_mechanisms.experiments.architecture import classify_architecture_version
from inequality_mechanisms.experiments.config import (
    ExperimentConfig,
    load_experiment_config,
)
from inequality_mechanisms.experiments.v2_config import (
    V2ConfigError,
    validate_v2_config_mapping,
)

_REPO = Path(__file__).resolve().parents[2]
_V1_CONFIGS = (
    "configs/pilot.v1.yaml",
    "configs/pilot.cost_uniform.v1.yaml",
    "configs/pilot.cost_input.v1.yaml",
    "configs/sprint4.smoke.v1.yaml",
)


@pytest.mark.parametrize("relative_path", _V1_CONFIGS)
def test_v1_config_still_loads_via_v1_loader(relative_path: str) -> None:
    cfg = load_experiment_config(_REPO / relative_path)
    assert isinstance(cfg, ExperimentConfig)


@pytest.mark.parametrize("relative_path", _V1_CONFIGS)
def test_v1_config_classifies_as_version_1(relative_path: str) -> None:
    raw = yaml.safe_load((_REPO / relative_path).read_text())
    assert classify_architecture_version(raw) == 1


@pytest.mark.parametrize("relative_path", _V1_CONFIGS)
def test_v1_config_rejected_by_v2_loader(relative_path: str) -> None:
    raw = yaml.safe_load((_REPO / relative_path).read_text())
    with pytest.raises(V2ConfigError):
        validate_v2_config_mapping(raw)


def test_v2_smoke_config_rejected_by_v1_loader() -> None:
    """The V2 smoke config must not silently satisfy the V1 schema either."""
    raw = yaml.safe_load((_REPO / "configs" / "v2" / "smoke.yaml").read_text())
    with pytest.raises(Exception):
        ExperimentConfig.model_validate(raw)


def test_v2_smoke_config_classifies_as_version_2() -> None:
    raw = yaml.safe_load((_REPO / "configs" / "v2" / "smoke.yaml").read_text())
    assert classify_architecture_version(raw) == 2
