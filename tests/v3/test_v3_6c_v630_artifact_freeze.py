"""V3-630 artifact freeze guard and closeout scaffold invariants."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from inequality_mechanisms.audits import artifact_freeze
from inequality_mechanisms.audits.artifact_freeze import (
    REPO_ROOT,
    V3_6C_ALLOWED_OUTPUT_REL,
    V3_6C_ALLOWED_PACKAGE,
    assert_v3_6c_output_allowed,
    is_frozen_v3_review_package,
)

CLOSEOUT_CONFIG = REPO_ROOT / "configs" / "v3" / "planar2r_closeout_v1.json"
EXPORT_SCRIPT = REPO_ROOT / "scripts" / "export_v3_6c_planar2r_closeout.py"


def _load_exporter():
    spec = importlib.util.spec_from_file_location("export_v3_6c_v630", EXPORT_SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_allowed_closeout_path_succeeds():
    root = (REPO_ROOT / V3_6C_ALLOWED_OUTPUT_REL).resolve()
    assert assert_v3_6c_output_allowed(root) == root
    child = root / "trials" / "near_0"
    assert assert_v3_6c_output_allowed(child) == child.resolve()


@pytest.mark.parametrize(
    "package",
    [
        "v3_6_free_space",
        "v3_6_free_space_v2",
        "v3_6b_planar2r_visual_audit",
        "v3_7_3r_free_space",
        "v3_6_sibling_extra",
    ],
)
def test_forbidden_frozen_paths_raise(package: str):
    assert is_frozen_v3_review_package(package)
    path = (REPO_ROOT / "results" / "v3_review" / package).resolve()
    with pytest.raises(ValueError, match="frozen|not under the allowed"):
        assert_v3_6c_output_allowed(path)
    nested = path / "summary.json"
    with pytest.raises(ValueError, match="frozen"):
        assert_v3_6c_output_allowed(nested)


def test_closeout_package_name_is_not_frozen():
    assert not is_frozen_v3_review_package(V3_6C_ALLOWED_PACKAGE)


def test_config_stub_declares_allowed_output_dir():
    data = json.loads(CLOSEOUT_CONFIG.read_text(encoding="utf-8"))
    assert data["audit_id"] == "planar2r_closeout_v1"
    assert data["seed"] == 7
    assert data["lattice"]["shape"] == [32, 32]
    assert data["task_ids"][0] == "near_0"
    assert data["task_ids"][-1] == "far_4"
    assert data["source_bank"]["bank_id"] == "free_space_planar2r_v2"
    assert data["source_bank"]["reuse_only"] is True
    assert data["mechanisms"]["pair"] == ["fourbar", "gearbox"]
    out = data["artifact_contract"]["output_dir"]
    assert out == "results/v3_review/v3_6c_planar2r_closeout"
    assert assert_v3_6c_output_allowed(REPO_ROOT / out) == (
        REPO_ROOT / V3_6C_ALLOWED_OUTPUT_REL
    ).resolve()


def test_exporter_scaffold_on_temp_allowed_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(artifact_freeze, "REPO_ROOT", tmp_path)
    allowed = tmp_path / "results" / "v3_review" / V3_6C_ALLOWED_PACKAGE
    # Exporter uses its own ROOT for default config; pass config + output.
    mod = _load_exporter()
    # Guard uses monkeypatched REPO_ROOT from the imported freeze module.
    # Re-bind the exporter's assert to the same module so the patch applies.
    monkeypatch.setattr(mod, "assert_v3_6c_output_allowed", assert_v3_6c_output_allowed)

    rc = mod.main(["--config", str(CLOSEOUT_CONFIG), "--output", str(allowed)])
    assert rc == 0
    manifest_path = allowed / "manifest.json"
    assert manifest_path.is_file()
    man = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert man["status"] == "scaffold"
    assert "freeze_statement" in man
    assert "V3-638" in man["note"] or "V3-639" in man["note"]


def test_exporter_refuses_forbidden_path(tmp_path, monkeypatch):
    monkeypatch.setattr(artifact_freeze, "REPO_ROOT", tmp_path)
    forbidden = tmp_path / "results" / "v3_review" / "v3_6_free_space_v2"
    forbidden.mkdir(parents=True)
    mod = _load_exporter()
    monkeypatch.setattr(mod, "assert_v3_6c_output_allowed", assert_v3_6c_output_allowed)

    with pytest.raises(ValueError, match="frozen"):
        mod.main(["--config", str(CLOSEOUT_CONFIG), "--output", str(forbidden)])
    assert not (forbidden / "manifest.json").exists()
