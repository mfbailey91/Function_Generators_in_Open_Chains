"""Tests for Experiment B Cartesian calibration (V2B-005)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from inequality_mechanisms.experiments.v2_cartesian_calibration import (
    CartesianCalibrationError,
    CartesianCalibrationSettings,
    assert_cartesian_calibration_decisions_present,
    domain_for_radius,
    load_cartesian_calibration_decisions,
    run_cartesian_calibration_sweep,
    select_cartesian_radius,
    select_cartesian_resolution,
    separation_for_radius,
    write_cartesian_calibration_decisions,
)
from inequality_mechanisms.experiments.v2_cartesian_goal_region import (
    load_cartesian_goal_region_config,
    run_cartesian_goal_region,
)
from inequality_mechanisms.experiments.v2_cartesian_tasks import (
    START_ATTACHMENT_POLICY_ID,
    default_experiment_b_domain,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_SMOKE_CONFIG = _REPO_ROOT / "configs/v2/cartesian_goal_region_smoke.yaml"
_CALIBRATION_CONFIG = (
    _REPO_ROOT / "configs/v2/cartesian_goal_region_calibration.yaml"
)


def test_separation_auto_lifts_when_twice_radius_exceeds_floor() -> None:
    assert separation_for_radius(0.06) == 0.30
    assert separation_for_radius(0.20) == pytest.approx(0.40)
    domain = domain_for_radius(default_experiment_b_domain(), 0.20)
    assert domain.start_tolerance == pytest.approx(0.20)
    assert domain.goal_radius == pytest.approx(0.20)
    assert domain.min_start_goal_separation == pytest.approx(0.40)


def test_select_cartesian_radius_prefers_smallest_meeting_floor() -> None:
    rows = [
        {
            "goal_radius": 0.08,
            "start_tolerance": 0.08,
            "min_start_goal_separation": 0.30,
            "attachment_rate": 0.70,
            "shape_n": 128,
        },
        {
            "goal_radius": 0.06,
            "start_tolerance": 0.06,
            "min_start_goal_separation": 0.30,
            "attachment_rate": 0.55,
            "shape_n": 128,
        },
        {
            "goal_radius": 0.04,
            "start_tolerance": 0.04,
            "min_start_goal_separation": 0.30,
            "attachment_rate": 0.20,
            "shape_n": 128,
        },
    ]
    decision = select_cartesian_radius(rows, min_attachment_rate=0.50)
    assert decision["goal_radius"] == pytest.approx(0.06)
    assert decision["reason"] == "smallest_radius_meeting_attachment_floor"


def test_select_cartesian_radius_falls_back_below_floor() -> None:
    rows = [
        {
            "goal_radius": 0.04,
            "start_tolerance": 0.04,
            "min_start_goal_separation": 0.30,
            "attachment_rate": 0.10,
            "shape_n": 64,
        },
        {
            "goal_radius": 0.08,
            "start_tolerance": 0.08,
            "min_start_goal_separation": 0.30,
            "attachment_rate": 0.30,
            "shape_n": 64,
        },
    ]
    decision = select_cartesian_radius(rows, min_attachment_rate=0.50)
    assert decision["goal_radius"] == pytest.approx(0.08)
    assert decision["reason"] == "best_available_below_floor"


def test_select_cartesian_resolution_coarsest_stable() -> None:
    rows = [
        {
            "shape_n": 32,
            "mean_paired_delta_expansions": 10.0,
            "task_acceptance_rate": 0.50,
        },
        {
            "shape_n": 64,
            "mean_paired_delta_expansions": 10.2,
            "task_acceptance_rate": 0.52,
        },
        {
            "shape_n": 128,
            "mean_paired_delta_expansions": 10.3,
            "task_acceptance_rate": 0.53,
        },
    ]
    decision = select_cartesian_resolution(rows, max_relative_effect_change=0.05)
    assert decision["production_shape_n"] == 32
    assert decision["reason"] == "coarsest_stable"


def test_tiny_deterministic_sweep_writes_decision_files(tmp_path: Path) -> None:
    smoke = load_cartesian_goal_region_config(_SMOKE_CONFIG)
    settings = CartesianCalibrationSettings(
        candidate_resolutions=(16, 24),
        candidate_goal_radii=(0.08, 0.12),
        min_attachment_rate=0.10,
        run_search=False,
    )
    sweep = run_cartesian_calibration_sweep(
        base_experiment=smoke.base_experiment,
        domain=smoke.domain,
        settings=settings,
        task_count=4,
        seed=7,
    )
    write_cartesian_calibration_decisions(
        tmp_path,
        radius_decision=sweep["cartesian_radius_decision"],
        resolution_decision=sweep["cartesian_resolution_decision"],
        start_attachment_decision=sweep["cartesian_start_attachment_decision"],
    )
    loaded = load_cartesian_calibration_decisions(tmp_path)
    assert "goal_radius" in loaded["cartesian_radius_decision"]
    assert "production_shape_n" in loaded["cartesian_resolution_decision"]
    attachment = loaded["cartesian_start_attachment_decision"]
    assert attachment["policy_id"] == START_ATTACHMENT_POLICY_ID
    assert attachment["decision"] == "retain_nearest_node_v1"
    assert (tmp_path / "cartesian_radius_decision.json").is_file()
    assert (tmp_path / "cartesian_resolution_decision.json").is_file()
    assert (tmp_path / "cartesian_start_attachment_decision.json").is_file()


def test_production_stage_refuses_missing_decisions(tmp_path: Path) -> None:
    raw = yaml.safe_load(_SMOKE_CONFIG.read_text(encoding="utf-8"))
    raw["stage"] = "production"
    raw["solver_policy"] = "production_single_solver_v1"
    raw["algorithms"] = ["dijkstra"]
    raw["task_count"] = 2
    path = tmp_path / "production.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    config = load_cartesian_goal_region_config(path)
    assert config.stage == "production"
    with pytest.raises(CartesianCalibrationError, match="requires recorded"):
        run_cartesian_goal_region(config, results_root=tmp_path / "out")


def test_production_stage_applies_decisions_and_runs(tmp_path: Path) -> None:
    smoke = load_cartesian_goal_region_config(_SMOKE_CONFIG)
    settings = CartesianCalibrationSettings(
        candidate_resolutions=(16,),
        candidate_goal_radii=(0.12,),
        min_attachment_rate=0.01,
        run_search=False,
    )
    sweep = run_cartesian_calibration_sweep(
        base_experiment=smoke.base_experiment,
        domain=smoke.domain,
        settings=settings,
        task_count=4,
        seed=11,
    )
    decisions_dir = tmp_path / "decisions"
    write_cartesian_calibration_decisions(
        decisions_dir,
        radius_decision=sweep["cartesian_radius_decision"],
        resolution_decision=sweep["cartesian_resolution_decision"],
        start_attachment_decision=sweep["cartesian_start_attachment_decision"],
    )

    raw = yaml.safe_load(_SMOKE_CONFIG.read_text(encoding="utf-8"))
    raw["stage"] = "production"
    raw["solver_policy"] = "production_single_solver_v1"
    raw["algorithms"] = ["dijkstra"]
    raw["task_count"] = 2
    raw["seed"] = 11
    raw["base_experiment"]["sampling"]["shape"] = [64, 64]
    path = tmp_path / "production.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    config = load_cartesian_goal_region_config(path)
    result = run_cartesian_goal_region(
        config,
        results_root=tmp_path / "runs",
        apply_decisions=decisions_dir,
        run_id="prod_apply_test",
    )
    assert result.stage == "production"
    assert result.n_tasks == 2
    emitted = json.loads((result.path / "config.json").read_text(encoding="utf-8"))
    assert emitted["cartesian_domain"]["goal_radius"] == pytest.approx(0.12)
    assert emitted["base_experiment"]["sampling"]["shape"] == [16, 16]


def test_assert_decisions_present_for_production_only() -> None:
    assert_cartesian_calibration_decisions_present("smoke", decisions=None)
    assert_cartesian_calibration_decisions_present("calibration", decisions=None)
    with pytest.raises(CartesianCalibrationError):
        assert_cartesian_calibration_decisions_present("production", decisions=None)


def test_repository_calibration_yaml_loads() -> None:
    config = load_cartesian_goal_region_config(_CALIBRATION_CONFIG)
    assert config.stage == "calibration"
    assert config.solver_policy == "calibration_dijkstra_v1"
    assert config.algorithms == ("dijkstra",)
    assert config.calibration is not None
    assert config.calibration.candidate_resolutions == (32, 64, 96, 128)
    assert config.task_count == 64


def test_calibration_stage_writes_package(tmp_path: Path) -> None:
    raw = yaml.safe_load(_CALIBRATION_CONFIG.read_text(encoding="utf-8"))
    raw["task_count"] = 3
    raw["calibration"] = {
        "candidate_resolutions": [16, 24],
        "candidate_goal_radii": [0.10, 0.12],
        "min_attachment_rate": 0.05,
        "run_search": False,
    }
    path = tmp_path / "calib.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    config = load_cartesian_goal_region_config(path)
    result = run_cartesian_goal_region(
        config, results_root=tmp_path / "runs", run_id="calib_pkg"
    )
    assert result.stage == "calibration"
    assert (result.path / "cartesian_radius_decision.json").is_file()
    assert (result.path / "cartesian_resolution_decision.json").is_file()
    assert (result.path / "cartesian_start_attachment_decision.json").is_file()
    assert (result.path / "candidate_rows.jsonl").is_file()
    manifest = json.loads((result.path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["stage"] == "calibration"
    assert manifest["n_candidate_rows"] == 4
