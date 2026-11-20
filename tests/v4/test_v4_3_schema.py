"""V4-300: strict config, schema catalog, and numeric transport."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from inequality_mechanisms.audits.v4_3_artifact import (
    encode_numeric_field,
    schema_documentation,
    strict_json_dumps,
    to_strict_jsonable,
)
from inequality_mechanisms.audits.v4_artifact_guard import (
    V4_3_ALLOWED_OUTPUT_REL,
    V4_3_FOLLOWUP_OUTPUT_REL,
)
from inequality_mechanisms.experiments.v4.intrinsic_static_wrench_config import (
    CONFIG_SCHEMA_VERSION,
    DEFAULT_CONFIG_REL,
    FIELD_STATUS_SCHEMA_VERSION,
    LEGACY_MANIFEST_SCHEMA_VERSION,
    LEGACY_PACKAGE_SCHEMA_VERSION,
    LEGACY_ROW_SCHEMA_VERSION,
    MANIFEST_SCHEMA_VERSION,
    PACKAGE_SCHEMA_VERSION,
    ROW_SCHEMA_VERSION,
    SOURCE_LOCK_SCHEMA_VERSION,
    V4_3ConfigError,
    load_intrinsic_static_wrench_config,
    schema_catalog,
    walk_forbidden_keys,
)


def test_default_config_loads_and_matches_schema_ids() -> None:
    config = load_intrinsic_static_wrench_config(DEFAULT_CONFIG_REL)
    assert config.schema_version == CONFIG_SCHEMA_VERSION
    assert config.source.schema_version == SOURCE_LOCK_SCHEMA_VERSION
    assert config.package == "v4_3_intrinsic_static_wrench"
    assert config.torque.limits == (1.0, 1.0)
    assert config.output_dir == V4_3_FOLLOWUP_OUTPUT_REL.as_posix()
    catalog = schema_catalog()
    assert catalog["config"] == CONFIG_SCHEMA_VERSION
    assert catalog["package"] == PACKAGE_SCHEMA_VERSION
    docs = schema_documentation()
    assert docs["schemas"] == catalog


def test_corrective_scientific_contract_is_distinct_from_frozen_v1() -> None:
    assert ROW_SCHEMA_VERSION.endswith(".v2")
    assert MANIFEST_SCHEMA_VERSION.endswith(".v2")
    assert PACKAGE_SCHEMA_VERSION.endswith(".v2")
    assert LEGACY_ROW_SCHEMA_VERSION.endswith(".v1")
    assert LEGACY_MANIFEST_SCHEMA_VERSION.endswith(".v1")
    assert LEGACY_PACKAGE_SCHEMA_VERSION.endswith(".v1")


def test_historical_config_remains_readable_without_changing_default_destination(
    tmp_path: Path,
) -> None:
    payload = json.loads(Path(DEFAULT_CONFIG_REL).read_text(encoding="utf-8"))
    payload["output_dir"] = V4_3_ALLOWED_OUTPUT_REL.as_posix()
    path = tmp_path / "historical_config.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    historical = load_intrinsic_static_wrench_config(path)
    assert historical.output_dir == V4_3_ALLOWED_OUTPUT_REL.as_posix()
    assert load_intrinsic_static_wrench_config().output_dir == (
        V4_3_FOLLOWUP_OUTPUT_REL.as_posix()
    )


def test_config_rejects_gravity_nested_key(tmp_path: Path) -> None:
    payload = json.loads(Path(DEFAULT_CONFIG_REL).read_text(encoding="utf-8"))
    payload["torque"]["gravity"] = 9.81
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(V4_3ConfigError, match="forbidden config key"):
        load_intrinsic_static_wrench_config(path)


def test_config_rejects_unknown_top_level_key(tmp_path: Path) -> None:
    payload = json.loads(Path(DEFAULT_CONFIG_REL).read_text(encoding="utf-8"))
    payload["unexpected"] = True
    path = tmp_path / "unknown.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(V4_3ConfigError, match="invalid V4.3 config"):
        load_intrinsic_static_wrench_config(path)


def test_config_rejects_wrong_output_dir(tmp_path: Path) -> None:
    payload = json.loads(Path(DEFAULT_CONFIG_REL).read_text(encoding="utf-8"))
    payload["output_dir"] = (
        "results/v4_review/v4_2b_span_controlled_corrective_closeout"
    )
    path = tmp_path / "wrong_out.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(V4_3ConfigError, match="output_dir"):
        load_intrinsic_static_wrench_config(path)


def test_walk_forbidden_keys_detects_payload_alias() -> None:
    with pytest.raises(V4_3ConfigError, match="payload"):
        walk_forbidden_keys({"physics": {"payload_mass": 1.0}})


def test_encode_numeric_field_finite_and_nonfinite() -> None:
    finite = encode_numeric_field(1.5, status="finite")
    assert finite["schema_version"] == FIELD_STATUS_SCHEMA_VERSION
    assert finite["value"] == 1.5
    unbounded = encode_numeric_field(float("inf"), status="unbounded")
    assert unbounded["value"] is None
    assert unbounded["status"] == "unbounded"
    undefined = encode_numeric_field(None, status="undefined", reason="origin")
    assert undefined["value"] is None
    assert undefined["reason"] == "origin"
    with pytest.raises(ValueError, match="nonfinite value"):
        encode_numeric_field(float("nan"), status="finite")


def test_strict_json_rejects_bare_nan_after_conversion() -> None:
    payload = {"a": float("nan"), "b": float("inf"), "c": 2.0}
    converted = to_strict_jsonable(payload)
    assert converted == {"a": None, "b": None, "c": 2.0}
    text = strict_json_dumps(payload)
    assert "NaN" not in text
    assert "Infinity" not in text
    assert json.loads(text)["c"] == 2.0
    with pytest.raises(ValueError):
        json.dumps({"x": float("nan")}, allow_nan=False)
    assert not math.isfinite(float("nan"))
