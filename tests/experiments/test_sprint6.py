"""Tests for Sprint Six resolution selection and runner smoke."""

from __future__ import annotations

from pathlib import Path

import pytest

from inequality_mechanisms.experiments.config import load_experiment_config
from inequality_mechanisms.experiments.resolution import (
    GRID_ANISOTROPY_LIMITATION,
    select_production_resolution,
)
from inequality_mechanisms.experiments.setup import build_paired_graphs
from inequality_mechanisms.experiments.sprint6 import run_sprint6
from inequality_mechanisms.mechanisms.equivalence import verify_matched_graphs
from inequality_mechanisms.mechanisms.gearbox import EquivalentGearbox


REPO = Path(__file__).resolve().parents[2]


def test_select_production_resolution_coarsest_stable() -> None:
    rows = [
        {
            "shape_n": 32,
            "primary_effect": 0.50,
            "n_components": 1,
            "task_acceptance_rate": 0.9,
        },
        {
            "shape_n": 48,
            "primary_effect": 0.51,
            "n_components": 1,
            "task_acceptance_rate": 0.91,
        },
        {
            "shape_n": 64,
            "primary_effect": 0.80,
            "n_components": 1,
            "task_acceptance_rate": 0.92,
        },
    ]
    decision = select_production_resolution(
        rows,
        max_relative_effect_change=0.05,
        require_sign_stability=True,
        require_component_stability=True,
        require_task_feasibility_stability=True,
    )
    assert decision["production_shape_n"] == 32
    assert decision["reason"] == "coarsest_stable"
    assert "isotropic" in GRID_ANISOTROPY_LIMITATION


def test_equivalence_smoke_config_loads_and_matches() -> None:
    cfg = load_experiment_config(
        REPO / "configs" / "sprint6.equivalence.smoke.v1.yaml"
    )
    paired = build_paired_graphs(cfg)
    assert isinstance(paired.gearbox_mechanism, EquivalentGearbox)
    assert paired.gearbox_mechanism.matching_rule == "span"
    assert verify_matched_graphs(paired.gearbox, paired.fourbar)["ok"] is True


def test_run_sprint6_equivalence_smoke(tmp_path: Path) -> None:
    cfg = load_experiment_config(
        REPO / "configs" / "sprint6.equivalence.smoke.v1.yaml"
    )
    run = run_sprint6(
        cfg,
        results_root=tmp_path,
        run_id="sprint6_eq_smoke",
        mode="equivalence",
    )
    assert run.status == "completed"
    summary = run.read_json("summary")
    assert summary["study"] == "sprint6"
    assert summary["result_schema_version"] == "6.0.0"
    assert "grid_anisotropy_limitation" in summary
    bank = run.read_json("sample_bank")
    assert bank["mechanisms"]
    effects = run.read_json("mechanism_effects")
    assert "rows" in effects
    hci = run.read_json("hierarchical_bootstrap")
    assert hci["cluster_definition"] == "mechanism_pair"
    assert hci["treats_tasks_as_iid"] is False

    canvas = run.path / "index.html"
    assert canvas.is_file()
    html = canvas.read_text(encoding="utf-8")
    assert "Sprint Six" in html
    assert "Equivalence" in html
    assert "6.0.0" in html
    assert "Hierarchical Monte Carlo" in html
    assert "Matched vs unmatched" in html
    assert "ADR-012" in html
    assert "ADR-013" in html


def test_write_sprint6_canvas_regenerable(tmp_path: Path) -> None:
    from inequality_mechanisms.experiments.sprint6_canvas import write_sprint6_canvas

    cfg = load_experiment_config(
        REPO / "configs" / "sprint6.equivalence.smoke.v1.yaml"
    )
    run = run_sprint6(
        cfg,
        results_root=tmp_path,
        run_id="sprint6_canvas_regen",
        mode="equivalence",
    )
    out = write_sprint6_canvas(run)
    assert out.is_file()
    assert "Resolution" in out.read_text(encoding="utf-8")


def test_sprint6_showcase_path_samples(tmp_path: Path) -> None:
    cfg = load_experiment_config(REPO / "configs" / "sprint6.showcase.v1.yaml")
    # Keep CI light: shrink resolution sweep only.
    cfg = cfg.model_copy(
        update={
            "sprint6": cfg.sprint6.model_copy(
                update={"resolution_shapes": [16], "verify_equivalence": True}
            )
        }
    )
    run = run_sprint6(
        cfg,
        results_root=tmp_path,
        run_id="sprint6_showcase_paths",
        mode="monte_carlo",
    )
    assert run.status == "completed"
    summary = run.read_json("summary")
    assert int(summary.get("n_path_samples", 0)) >= 1
    path_root = run.path / "outputs" / "paths"
    assert path_root.is_dir()
    trial_dirs = sorted(p for p in path_root.iterdir() if p.is_dir())
    assert trial_dirs
    assert any(trial_dirs[0].glob("*cartesian*.png"))
    html = (run.path / "index.html").read_text(encoding="utf-8")
    assert "Path samples" in html or "Cartesian" in html
    assert "expansions_raw" in run.outputs or (
        run.path / "outputs" / "expansions_raw.png"
    ).is_file()


def test_run_sprint6_resolution_smoke(tmp_path: Path) -> None:
    cfg = load_experiment_config(
        REPO / "configs" / "sprint6.resolution.smoke.v1.yaml"
    )
    run = run_sprint6(
        cfg,
        results_root=tmp_path,
        run_id="sprint6_res_smoke",
        mode="resolution",
    )
    assert run.status == "completed"
    sweep = run.read_json("resolution_sweep")
    assert len(sweep["rows"]) == 2
    prod = run.read_json("production_resolution")
    assert "production_shape_n" in prod
