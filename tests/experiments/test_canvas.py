"""Tests for Monte Carlo HTML canvas generation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from inequality_mechanisms.experiments.canvas import (
    collect_canvas_payload,
    render_monte_carlo_canvas_html,
    resolve_run_for_canvas,
    write_monte_carlo_canvas,
)
from inequality_mechanisms.experiments.registry import (
    RunRegistryError,
    create_run,
)
from inequality_mechanisms.experiments import ExperimentConfig
from inequality_mechanisms.mechanisms import IndependentFourBars, UnitGearbox

_CR = (0.5, 1.25, 1.0, 1.0)


def _tiny_config() -> ExperimentConfig:
    return ExperimentConfig.model_validate(
        {
            "seed": 7,
            "mechanisms": {
                "gearbox": UnitGearbox(dim=2).to_dict(),
                "fourbar": IndependentFourBars.from_lengths([_CR, _CR]).to_dict(),
            },
            "graph": {"shape": [4, 4], "wrap": [True, True], "edge_samples": 3},
            "limits": {"lower": [-1.0, -1.0], "upper": [1.0, 1.0]},
            "cost": {"type": "output_euclidean"},
            "algorithms": {"names": ["dijkstra"]},
            "trials": {
                "n_trials": 1,
                "min_output_separation": 0.01,
                "preimage_policy": "lex_min_node_id",
                "max_sample_attempts": 10,
                "require_reachable": False,
            },
        }
    )


def _completed_synthetic_run(tmp_path: Path) -> Path:
    """Build a completed run with synthetic summary + fake PNGs (no search)."""
    cfg = _tiny_config()
    run = create_run(cfg, results_root=tmp_path, run_id="canvas_synth")
    run.mark_running()

    summary = {
        "n_rows": 4,
        "n_found": 4,
        "n_unreachable": 0,
        "n_trials_config": 2,
        "n_discarded_unreachable": 0,
        "n_sample_attempts": 2,
        "seed": 7,
        "cost_type": "output_euclidean",
        "result_schema_version": "4.1.0",
        "graph_meta": {
            "fourbar_mode": "population",
            "match_valid_nodes": True,
            "cost_type": "output_euclidean",
        },
        "by_group": {
            "dijkstra|gearbox": {
                "algorithm": "dijkstra",
                "mechanism": "gearbox",
                "n_trials": 2,
                "n_found": 2,
                "n_unreachable": 0,
                "median_n_expanded": 10.0,
                "mean_rho_expanded": 0.25,
            },
            "dijkstra|fourbar": {
                "algorithm": "dijkstra",
                "mechanism": "fourbar",
                "n_trials": 2,
                "n_found": 2,
                "n_unreachable": 0,
                "median_n_expanded": 20.0,
                "mean_rho_expanded": 0.5,
            },
        },
        "paired_log_ratios": {
            "dijkstra": {
                "algorithm": "dijkstra",
                "n_pairs": 2,
                "median": 0.693147,
                "mean": 0.7,
            }
        },
    }
    run.write_json("summary", summary)
    run.write_text(
        "summary_table",
        "section,algorithm,mechanism,median_n_expanded\n"
        "group,dijkstra,gearbox,10.0\n",
        suffix=".csv",
    )
    run.append_jsonl(
        "trials",
        [
            {
                "result_schema_version": "4.1.0",
                "trial_index": 0,
                "mechanism": "gearbox",
                "algorithm": "dijkstra",
                "cost_type": "output_euclidean",
                "heuristic_type": "zero",
                "found": True,
                "optimal_cost": 1.5,
                "n_path_edges": 3,
                "path_length_u": 1.2,
                "path_length_q": 1.5,
                "path_length_x": 2.0,
            }
        ],
    )

    for name in (
        "expansions_raw.png",
        "expansions_normalized.png",
        "expansions_ratio.png",
    ):
        path = run.outputs_dir / name
        path.write_bytes(b"\x89PNG\r\n\x1a\n")  # minimal header bytes
        run.register_output(name.replace(".png", ""), f"outputs/{name}")

    paths_dir = run.outputs_dir / "paths" / "trial_0000"
    paths_dir.mkdir(parents=True)
    sample = paths_dir / "gearbox_input.png"
    sample.write_bytes(b"\x89PNG\r\n\x1a\n")
    run.register_output("path_t0000_gearbox_input", sample.relative_to(run.path).as_posix())

    run.mark_completed()
    return run.path


class TestMonteCarloCanvas:
    def test_render_contains_key_sections(self, tmp_path: Path) -> None:
        run_path = _completed_synthetic_run(tmp_path)
        from inequality_mechanisms.experiments.registry import load_run

        run = load_run(run_path)
        payload = collect_canvas_payload(run)
        html_text = render_monte_carlo_canvas_html(payload)

        assert "Monte Carlo Canvas" in html_text
        assert "canvas_synth" in html_text
        assert "expansions_raw.png" in html_text
        assert "expansions_normalized.png" in html_text
        assert "median N_expanded" in html_text
        assert "0.6931" in html_text or "0.693147" in html_text
        assert "match_valid_nodes" in html_text
        assert "seed: 7" in html_text or ">7</dd>" in html_text
        assert "trial_0000" in html_text
        assert "result_schema_version" in html_text
        assert "4.1.0" in html_text or "4.0.0" in html_text
        assert "output_euclidean" in html_text
        assert "mean L_U" in html_text
        assert "Path metrics" in html_text

    def test_canvas_tolerates_missing_path_metrics(self, tmp_path: Path) -> None:
        cfg = _tiny_config()
        run = create_run(cfg, results_root=tmp_path, run_id="legacy_canvas")
        run.mark_running()
        run.write_json("summary", {"by_group": {}, "paired_log_ratios": {}})
        run.mark_completed()
        html_text = render_monte_carlo_canvas_html(collect_canvas_payload(run))
        assert "No Sprint Four path-metric fields" in html_text

    def test_write_canvas_and_regenerate(self, tmp_path: Path) -> None:
        run_path = _completed_synthetic_run(tmp_path)
        out = write_monte_carlo_canvas(run_path)
        assert out.is_file()
        assert out.name == "index.html"
        text = out.read_text(encoding="utf-8")
        assert "dijkstra" in text
        assert "path_length_q.png" in text
        assert "path_length_x.png" in text
        assert "Joint path length" in text
        assert "End-effector path length" in text
        assert (run_path / "outputs" / "path_length_q.png").is_file()
        assert (run_path / "outputs" / "path_length_x.png").is_file()

        # Regeneration overwrites derived HTML only; summary untouched.
        summary_before = (run_path / "outputs" / "summary.json").read_text()
        out.write_text("stale", encoding="utf-8")
        again = write_monte_carlo_canvas(run_path)
        assert again.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")
        assert (run_path / "outputs" / "summary.json").read_text() == summary_before

    def test_write_canvas_emits_path_length_plots_from_trials(
        self, tmp_path: Path
    ) -> None:
        run_path = _completed_synthetic_run(tmp_path)
        # No pre-registered path-length PNGs; canvas regen must write them.
        assert not (run_path / "outputs" / "path_length_q.png").is_file()
        write_monte_carlo_canvas(run_path)
        assert (run_path / "outputs" / "path_length_q.png").stat().st_size > 0
        assert (run_path / "outputs" / "path_length_x.png").stat().st_size > 0
        html_text = (run_path / "index.html").read_text(encoding="utf-8")
        assert 'src="outputs/path_length_q.png"' in html_text
        assert 'src="outputs/path_length_x.png"' in html_text
    def test_resolve_latest(self, tmp_path: Path) -> None:
        import time

        first = _completed_synthetic_run(tmp_path)
        time.sleep(1.1)
        # Second completed run with a later timestamp.
        cfg = _tiny_config()
        run = create_run(cfg, results_root=tmp_path, run_id="canvas_later")
        run.mark_running()
        run.write_json("summary", {"by_group": {}, "paired_log_ratios": {}})
        run.mark_completed()

        latest = resolve_run_for_canvas(None, results_root=tmp_path)
        assert latest.run_id == "canvas_later"
        assert first.name == "canvas_synth"

    def test_rejects_incomplete_run(self, tmp_path: Path) -> None:
        cfg = _tiny_config()
        run = create_run(cfg, results_root=tmp_path, run_id="not_done")
        run.mark_running()
        with pytest.raises(RunRegistryError, match="completed"):
            write_monte_carlo_canvas(run)

    def test_payload_json_serializable(self, tmp_path: Path) -> None:
        run_path = _completed_synthetic_run(tmp_path)
        from inequality_mechanisms.experiments.registry import load_run

        payload = collect_canvas_payload(load_run(run_path))
        json.dumps(payload)  # must not raise
