"""V4-201 frozen V4.2 span-atlas configuration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from inequality_mechanisms.audits.v4_artifact_guard import (
    CANONICAL_REPO_ROOT,
    V4_2_ALLOWED_OUTPUT_REL,
)
from inequality_mechanisms.experiments.v4.atlas_config import NO_INFERENCE_STATEMENT
from inequality_mechanisms.experiments.v4.span_controlled_atlas_config import (
    DEFAULT_CONFIG_REL,
    FROZEN_V3_6D_DIGEST,
    FROZEN_V3_6D_REGISTRY_REL,
    SPAN_175_STATUS,
    V4SpanAtlasConfigError,
    load_span_atlas_config,
)

CONFIG_PATH = CANONICAL_REPO_ROOT / DEFAULT_CONFIG_REL


def test_frozen_config_loads_and_locks_digest() -> None:
    config = load_span_atlas_config(CONFIG_PATH)
    assert config.output_dir == V4_2_ALLOWED_OUTPUT_REL.as_posix()
    assert config.v3_6d_digest_lock == FROZEN_V3_6D_DIGEST
    assert Path(config.v3_6d_registry) == FROZEN_V3_6D_REGISTRY_REL
    assert config.grid.shape == (33, 33)
    assert config.grid.inset_fraction == 0.01
    assert config.matching_rule == "span"
    assert config.span_175_status == SPAN_175_STATUS
    assert config.no_inference_statement == NO_INFERENCE_STATEMENT
    assert config.planar2r.L1 == 1.0
    digest = config.digest()
    assert len(digest) == 64
    assert config.digest() == digest


def test_config_rejects_missing_and_extra_fields(tmp_path: Path) -> None:
    raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    raw.pop("matching_rule")
    bad = tmp_path / "missing.json"
    bad.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(V4SpanAtlasConfigError):
        load_span_atlas_config(bad)
    raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    raw["ranking"] = "better"
    extra = tmp_path / "extra.json"
    extra.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(V4SpanAtlasConfigError):
        load_span_atlas_config(extra)


@pytest.mark.parametrize("key", ["gravity", "payload", "gravity_scale"])
def test_config_rejects_gravity_and_payload_keys(tmp_path: Path, key: str) -> None:
    raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    raw[key] = 1.0
    path = tmp_path / f"{key}.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(V4SpanAtlasConfigError, match="forbidden config key"):
        load_span_atlas_config(path)


def test_config_rejects_wrong_digest_and_output(tmp_path: Path) -> None:
    raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    raw["v3_6d_digest_lock"] = "0" * 64
    path = tmp_path / "wrong_digest.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(V4SpanAtlasConfigError, match="v3_6d_digest_lock"):
        load_span_atlas_config(path)
    raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    raw["output_dir"] = "results/v4_review/v4_1_planar2r_geometry_atlas"
    path = tmp_path / "wrong_out.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(V4SpanAtlasConfigError, match="output_dir"):
        load_span_atlas_config(path)
