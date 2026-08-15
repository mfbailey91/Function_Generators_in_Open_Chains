"""V4-008 deterministic geometry-core smoke artifact tests."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from inequality_mechanisms.audits import v4_artifact_guard
from inequality_mechanisms.audits.v4_artifact_guard import (
    V4_0_ALLOWED_PACKAGE,
    ArtifactPathForbiddenError,
)
from inequality_mechanisms.audits.v4_geometry_core_smoke import (
    GRID_N,
    MECHANISM_IDS,
    NO_INFERENCE_STATEMENT,
    REQUIRED_FILES,
    generate_geometry_core_smoke,
)

_FORBIDDEN_LANGUAGE = (
    "winner",
    "outperform",
    "ranking",
    "estimand",
    "superior",
    "inferior",
)


@pytest.fixture(scope="module")
def smoke_package(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("v4_008_repo")
    original = v4_artifact_guard.REPO_ROOT
    v4_artifact_guard.REPO_ROOT = root
    try:
        output = root / "results" / "v4_review" / V4_0_ALLOWED_PACKAGE
        generate_geometry_core_smoke(output)
        yield output
    finally:
        v4_artifact_guard.REPO_ROOT = original


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_rows(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_frozen_v3_output_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(v4_artifact_guard, "REPO_ROOT", tmp_path)
    forbidden = tmp_path / "results" / "v3_review" / "v3_6_free_space_v2"
    forbidden.mkdir(parents=True)
    with pytest.raises(ArtifactPathForbiddenError, match="frozen V3"):
        generate_geometry_core_smoke(forbidden)
    assert not (forbidden / "manifest.json").exists()


def test_unauthorized_v4_package_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(v4_artifact_guard, "REPO_ROOT", tmp_path)
    forbidden = tmp_path / "results" / "v4_review" / "v4_1_planar2r_geometry_atlas"
    forbidden.mkdir(parents=True)
    with pytest.raises(ArtifactPathForbiddenError, match="unauthorized V4"):
        generate_geometry_core_smoke(forbidden)
    assert not (forbidden / "manifest.json").exists()


def test_required_files_and_sample_count(smoke_package: Path) -> None:
    for name in REQUIRED_FILES:
        assert (smoke_package / name).is_file(), name
    rows = _load_rows(smoke_package / "geometry_samples.jsonl")
    assert len(rows) == GRID_N * GRID_N * len(MECHANISM_IDS)
    assert {row["mechanism_id"] for row in rows} == set(MECHANISM_IDS)
    manifest = _load_json(smoke_package / "manifest.json")
    assert manifest["n_samples"] == len(rows)
    assert manifest["no_inference_statement"] == NO_INFERENCE_STATEMENT
    assert "figures" in manifest
    for rel in manifest["figures"].values():
        assert (smoke_package / rel).is_file()


def test_html_states_no_inference_and_avoids_ranking(smoke_package: Path) -> None:
    html = (smoke_package / "index.html").read_text(encoding="utf-8")
    manifest = (smoke_package / "manifest.json").read_text(encoding="utf-8")
    assert NO_INFERENCE_STATEMENT in html
    combined = f"{html}\n{manifest}".lower()
    for word in _FORBIDDEN_LANGUAGE:
        assert word not in combined, word


def test_gearbox_analytic_identity(smoke_package: Path) -> None:
    identity = _load_json(smoke_package / "identity_residuals.json")
    gearbox = identity["gearbox_analytic"]
    ratios = np.asarray(gearbox["ratios"], dtype=np.float64)
    assert ratios.shape == (2,)
    assert np.all(ratios > 0.0)
    assert gearbox["max_jacobian_residual"] < 1e-12
    assert gearbox["max_metric_residual"] < 1e-12


def test_fourbar_residuals_are_finite_and_tight(smoke_package: Path) -> None:
    identity = _load_json(smoke_package / "identity_residuals.json")
    fourbar = identity["maxima"]
    for key in (
        "metric_mobility",
        "finite_difference",
        "virtual_power",
        "potential_gradient",
    ):
        value = float(fourbar[key]["fourbar"])
        assert np.isfinite(value), key
        assert value >= 0.0, key
    assert fourbar["metric_mobility"]["fourbar"] < 1e-10
    assert fourbar["virtual_power"]["fourbar"] < 1e-10
    assert fourbar["finite_difference"]["fourbar"] < 1e-6
    assert fourbar["potential_gradient"]["fourbar"] < 1e-6
    assert fourbar["metric_mobility"]["all"] < 1e-10
    assert fourbar["virtual_power"]["all"] < 1e-10
    assert fourbar["finite_difference"]["all"] < 1e-6
    assert fourbar["potential_gradient"]["all"] < 1e-6
