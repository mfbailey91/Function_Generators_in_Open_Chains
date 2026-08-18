"""V4-101 frozen atlas configuration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from inequality_mechanisms.audits.v4_artifact_guard import (
    REPO_ROOT,
    V4_1_ALLOWED_OUTPUT_REL,
)
from inequality_mechanisms.experiments.v4.atlas_config import (
    DEFAULT_CONFIG_REL,
    NO_INFERENCE_STATEMENT,
    V4AtlasConfigError,
    load_atlas_config,
)

CONFIG_PATH = REPO_ROOT / DEFAULT_CONFIG_REL


def test_frozen_config_loads_and_forbids_ranking() -> None:
    config = load_atlas_config(CONFIG_PATH)
    assert config.output_dir == V4_1_ALLOWED_OUTPUT_REL.as_posix()
    assert config.grid.shape == (33, 33)
    assert config.matching_rule == "span"
    assert config.actuator_weight == "identity"
    assert config.no_inference_statement == NO_INFERENCE_STATEMENT
    assert config.fourbar.a == 1.0
    assert config.planar2r.L1 == 1.0
    digest = config.digest()
    assert len(digest) == 64
    assert config.digest() == digest


def test_config_rejects_missing_and_extra_fields(tmp_path: Path) -> None:
    raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    raw.pop("matching_rule")
    bad = tmp_path / "missing.json"
    bad.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(V4AtlasConfigError):
        load_atlas_config(bad)
    raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    raw["ranking"] = "better"
    extra = tmp_path / "extra.json"
    extra.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(V4AtlasConfigError):
        load_atlas_config(extra)


def test_config_rejects_wrong_output_dir(tmp_path: Path) -> None:
    raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    raw["output_dir"] = "results/v4_review/v4_0_kinematic_geometry_core"
    path = tmp_path / "wrong_out.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(V4AtlasConfigError, match="output_dir"):
        load_atlas_config(path)
