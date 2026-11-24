"""V4-404 atlas guards, one-case package path, verifier, and presentation checks."""

from __future__ import annotations

import gzip
import inspect
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from inequality_mechanisms.audits import v4_4_artifact as smoke_audit
from inequality_mechanisms.audits import v4_4_atlas_artifact as atlas
from inequality_mechanisms.experiments.v4 import intrinsic_velocity_atlas as consumer
from inequality_mechanisms.experiments.v4.intrinsic_static_wrench_config import (
    FROZEN_MECHANISM_IDS,
)
from inequality_mechanisms.visualization.v4 import intrinsic_velocity_atlas as viz

ONE_CASE = ("span_j1_095_j2_095",)
ONE_CASE_ROWS = 33 * 33 * 3
ONE_CASE_PER_ARM = 33 * 33


@pytest.fixture(scope="module")
def atlas_package(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, dict[str, Any]]:
    isolated = tmp_path_factory.mktemp("v44_atlas")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(atlas, "REPO_ROOT", isolated)
        patch.setattr(atlas, "ATLAS_CASE_IDS", ONE_CASE)
        patch.setattr(consumer, "ATLAS_CASE_IDS", ONE_CASE)
        patch.setattr(atlas, "FROZEN_V4_2B_N_GEOMETRY_ROWS", ONE_CASE_ROWS)
        patch.setattr(atlas, "FROZEN_V4_2B_N_ROWS_PER_ARM", ONE_CASE_PER_ARM)
        patch.setattr(consumer, "FROZEN_V4_2B_N_GEOMETRY_ROWS", ONE_CASE_ROWS)
        patch.setattr(atlas, "git_status_porcelain", lambda: "")
        patch.setattr(atlas, "git_rev_parse_head", lambda: "c" * 40)

        def forbid_wrench(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("V4.4 atlas must not evaluate the wrench solver")

        from inequality_mechanisms.experiments.v4 import intrinsic_static_wrench

        patch.setattr(
            intrinsic_static_wrench, "static_wrench_from_snapshot", forbid_wrench
        )
        result = consumer.generate_velocity_atlas()
    return Path(result["output"]), result


def test_config_matches_frozen_contract() -> None:
    loaded = atlas.load_velocity_atlas_config()
    assert loaded == atlas.default_velocity_atlas_config()
    assert loaded["package"] == atlas.ATLAS_PACKAGE
    assert loaded["selection"]["mode"] == "full_corpus"
    assert loaded["selection"]["grid"] == [33, 33]
    assert loaded["output_dir"] == atlas.ATLAS_OUTPUT_REL.as_posix()
    assert loaded["output_dir"] != smoke_audit.OUTPUT_REL.as_posix()


def test_preflight_refuses_dirty_nonempty_and_smoke_roots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(atlas, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(atlas, "git_status_porcelain", lambda: " M dirty.py")
    with pytest.raises(smoke_audit.V4_4DirtySourceError):
        atlas.preflight_velocity_atlas()
    monkeypatch.setattr(atlas, "git_status_porcelain", lambda: "")
    monkeypatch.setattr(atlas, "git_rev_parse_head", lambda: "d" * 40)
    smoke = tmp_path / atlas.SMOKE_OUTPUT_REL
    smoke.mkdir(parents=True)
    with pytest.raises(smoke_audit.V4_4ArtifactError, match="smoke"):
        atlas.preflight_velocity_atlas(smoke)
    with pytest.raises(smoke_audit.V4_4ArtifactError, match="smoke"):
        atlas.preflight_velocity_atlas(atlas.canonical_v4_4_smoke_root())
    target = tmp_path / atlas.ATLAS_OUTPUT_REL
    target.mkdir(parents=True)
    (target / "keep.txt").write_text("frozen")
    with pytest.raises(smoke_audit.V4_4ArtifactError, match="nonempty"):
        atlas.preflight_velocity_atlas()
    assert (target / "keep.txt").read_text() == "frozen"


def test_preflight_refuses_symlink_and_nonexact_roots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(atlas, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(atlas, "git_status_porcelain", lambda: "")
    monkeypatch.setattr(atlas, "git_rev_parse_head", lambda: "e" * 40)
    with pytest.raises(smoke_audit.V4_4ArtifactError):
        atlas.preflight_velocity_atlas(tmp_path / atlas.ATLAS_OUTPUT_REL / "child")
    (tmp_path / "results").symlink_to(
        atlas.CANONICAL_REPO_ROOT / "results", target_is_directory=True
    )
    with pytest.raises(smoke_audit.V4_4ArtifactError):
        atlas.preflight_velocity_atlas()


def test_one_case_package_verifies_and_has_paired_views(
    atlas_package: tuple[Path, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, generated = atlas_package
    monkeypatch.setattr(atlas, "ATLAS_CASE_IDS", ONE_CASE)
    monkeypatch.setattr(atlas, "FROZEN_V4_2B_N_GEOMETRY_ROWS", ONE_CASE_ROWS)
    monkeypatch.setattr(atlas, "FROZEN_V4_2B_N_ROWS_PER_ARM", ONE_CASE_PER_ARM)
    verified = atlas.verify_v4_4_atlas_artifact(root)
    assert verified["files_digest"] == generated["files_digest"]
    assert verified["n_rows"] == ONE_CASE_ROWS
    assert verified["n_pairs"] == ONE_CASE_PER_ARM
    assert verified["n_ik_requests"] == ONE_CASE_ROWS * 24
    assert verified["n_typed_failures"] == verified["n_silent_drops"] == 0
    assert verified["n_rows_per_arm"] == {
        mech: ONE_CASE_PER_ARM for mech in FROZEN_MECHANISM_IDS
    }
    case_dir = root / "cases" / ONE_CASE[0]
    for name in atlas.ATLAS_FIGURES:
        assert (case_dir / "figures" / f"{name}.png").is_file()
    page = (case_dir / "index.html").read_text(encoding="utf-8")
    assert 'id="sample-select"' in page
    assert 'id="atlas-data" type="application/json"' in page
    assert "assets/atlas.js" in page
    inspector = json.loads((case_dir / "inspector.json").read_text(encoding="utf-8"))
    assert len(inspector["rows"]) == ONE_CASE_ROWS
    assert "directional_support" in inspector["rows"][0]["capability"]
    assert "ik_positive_x" in inspector["rows"][0]
    summary = json.loads((case_dir / "summary.json").read_text(encoding="utf-8"))
    assert "isotropic_speed" in summary["color_limits"]
    assert set(summary["assets"]) == set(atlas.ATLAS_FIGURES)
    index = (root / "index.html").read_text(encoding="utf-8")
    assert ONE_CASE[0] in index
    assert "Unit actuator rates" in index


def _rewrite_manifest(root: Path) -> None:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    inventory = atlas.inventory_atlas_files(root, ONE_CASE)
    manifest["files"] = inventory
    manifest["n_files"] = len(inventory)
    manifest["files_digest"] = smoke_audit.inventory_digest(inventory)
    (root / "manifest.json").write_text(
        smoke_audit.strict_json(manifest) + "\n", encoding="utf-8"
    )


def test_verifier_rejects_silent_drop_and_schema_tamper(
    atlas_package: tuple[Path, dict[str, Any]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _ = atlas_package
    monkeypatch.setattr(atlas, "ATLAS_CASE_IDS", ONE_CASE)
    monkeypatch.setattr(atlas, "FROZEN_V4_2B_N_GEOMETRY_ROWS", ONE_CASE_ROWS)
    monkeypatch.setattr(atlas, "FROZEN_V4_2B_N_ROWS_PER_ARM", ONE_CASE_PER_ARM)
    damaged = tmp_path / "damaged"
    damaged.mkdir()
    for path in root.rglob("*"):
        if path.is_file():
            dest = damaged / path.relative_to(root)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(path.read_bytes())
    rows_path = damaged / atlas.case_velocity_rel(ONE_CASE[0])
    lines = list(atlas.iter_case_rows(rows_path))
    with gzip.open(rows_path, "wt", encoding="utf-8") as stream:
        for row in lines[1:]:
            stream.write(smoke_audit.strict_json(row, indent=None) + "\n")
    _rewrite_manifest(damaged)
    with pytest.raises(
        smoke_audit.V4_4ArtifactError, match="silent drop|identity|grid"
    ):
        atlas.verify_v4_4_atlas_artifact(damaged)

    schema_pkg = tmp_path / "schema_damage"
    schema_pkg.mkdir()
    for path in root.rglob("*"):
        if path.is_file():
            dest = schema_pkg / path.relative_to(root)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(path.read_bytes())
    schema = json.loads((schema_pkg / "schema.json").read_text(encoding="utf-8"))
    schema["schemas"]["package"] = "tampered"
    (schema_pkg / "schema.json").write_text(smoke_audit.strict_json(schema) + "\n")
    _rewrite_manifest(schema_pkg)
    with pytest.raises(smoke_audit.V4_4ArtifactError, match="schema"):
        atlas.verify_v4_4_atlas_artifact(schema_pkg)


def test_primary_scale_excludes_near_singular_extremes() -> None:
    records = []
    for i, (mech, status, speed) in enumerate(
        (
            ("fourbar", "regular", 1.0),
            ("span_matched_gearbox", "regular", 2.0),
            ("fourbar", "near_singular", 100.0),
            ("span_matched_gearbox", "near_singular", 200.0),
            ("identity_on_shared_q", "regular", 3.0),
        )
    ):
        records.append(
            {
                "mechanism_id": mech,
                "grid_index": [i, 0],
                "primary_eligible": status == "regular",
                "capability": {
                    "status": status,
                    "isotropic_speed": speed,
                    "directional_ray_speed": {"positive_x": speed},
                    "direction_status": {"positive_x": "defined"},
                    "velocity_corners": [
                        [speed, 0.0],
                        [0.0, speed],
                        [-speed, 0.0],
                        [0.0, -speed],
                    ],
                },
            }
        )
    primary = viz._field_grid(
        records, mechanism_id="fourbar", key="isotropic_speed", primary_only=True
    )
    full = viz._field_grid(
        records, mechanism_id="fourbar", key="isotropic_speed", primary_only=False
    )
    assert primary[0, 0] == 1.0
    assert not (primary == 100.0).any()
    assert full[2, 0] == 100.0


def test_cli_exposes_verify_without_overwrite_escape() -> None:
    assert set(inspect.signature(consumer.generate_velocity_atlas).parameters) == {
        "config_path"
    }
    completed = subprocess.run(
        [
            sys.executable,
            str(atlas.CANONICAL_REPO_ROOT / "scripts/generate_v4_4_velocity_atlas.py"),
            "--help",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "--verify" in completed.stdout
    assert "--overwrite" not in completed.stdout
    assert "--allow-dirty" not in completed.stdout


def test_occupied_canonical_smoke_is_refused_for_atlas_writes() -> None:
    smoke = atlas.canonical_v4_4_smoke_root()
    assert smoke.is_dir() and any(smoke.iterdir())
    with pytest.raises(smoke_audit.V4_4ArtifactError, match="smoke"):
        atlas.preflight_velocity_atlas(smoke)
