"""Smoke tests for the Sprint Five path-quality runner."""

from __future__ import annotations

from pathlib import Path

import pytest

from inequality_mechanisms.experiments import (
    SPRINT5_RESULT_SCHEMA_VERSION,
    load_experiment_config,
    run_sprint5,
)


@pytest.fixture
def smoke_config():
    root = Path(__file__).resolve().parents[2]
    return load_experiment_config(root / "configs" / "sprint5.smoke.v1.yaml")


def test_sprint5_smoke(smoke_config, tmp_path: Path) -> None:
    run = run_sprint5(smoke_config, results_root=tmp_path, run_id="sprint5_smoke")
    assert run.status == "completed"
    summary = run.read_json("summary")
    assert summary["result_schema_version"] == SPRINT5_RESULT_SCHEMA_VERSION
    assert summary["study"] == "sprint5_path_quality"

    trials = run.read_jsonl("trials")
    assert trials
    found = [r for r in trials if r.get("found")]
    assert found
    row = found[0]
    for key in (
        "path_length_u",
        "path_length_q",
        "path_length_x",
        "directness_ratio_q",
        "cumulative_turning_x",
        "self_intersections_q",
        "near_revisit_distance_x",
        "directness_defined_u",
    ):
        assert key in row

    assert (run.path / "path_quality" / "representative_trials.json").is_file()
    assert "equal_cost_path_degeneracy" in run.outputs
    assert "bootstrap_cis" in run.outputs
    boot = run.read_json("bootstrap_cis")
    assert "path_quality" in boot
    assert "undefined_counts" in boot["path_quality"]

    # Standard figures / tables present.
    for name in (
        "paired_path_length_x",
        "paired_directness_x",
        "expansions_vs_directness_x",
        "path_length_summary",
        "directness_summary",
    ):
        assert name in run.outputs

    canvas = run.path / "index.html"
    assert canvas.is_file()
    html = canvas.read_text(encoding="utf-8")
    assert "Sprint Five" in html
    assert "Path Quality" in html
    assert "5.0.0" in html
    assert "Path samples" in html
    path_root = run.path / "outputs" / "paths"
    assert path_root.is_dir()
    trial_dirs = sorted(p for p in path_root.iterdir() if p.is_dir())
    assert len(trial_dirs) == 5
    assert any(trial_dirs[0].glob("*.png"))
