"""Integration tests for Sprint Four monotonic U vs Q control (S4-11)."""

from __future__ import annotations

from pathlib import Path

import pytest

from inequality_mechanisms.experiments import load_experiment_config, run_sprint4_qgrid

_REPO = Path(__file__).resolve().parents[2]
_SMOKE = _REPO / "configs" / "sprint4.qgrid.smoke.v1.yaml"


@pytest.mark.skipif(not _SMOKE.is_file(), reason="smoke config missing")
def test_run_sprint4_qgrid_smoke(tmp_path: Path) -> None:
    config = load_experiment_config(_SMOKE)
    run = run_sprint4_qgrid(config, results_root=tmp_path, run_id="qgrid_smoke")
    assert run.status == "completed"
    summary = run.resolve_output("summary")
    assert summary.is_file()
    trials = run.resolve_output("trials")
    assert trials.is_file()
    comparison = run.resolve_output("qgrid_comparison")
    assert comparison.is_file()
    plot = run.resolve_output("qgrid_u_vs_q_expansions")
    assert plot.is_file()

    import json

    summary_payload = json.loads(summary.read_text(encoding="utf-8"))
    assert summary_payload["result_schema_version"] == "4.2.0"
    assert summary_payload["n_trials_accepted"] == 2
    assert summary_payload["n_rows"] == 8  # 2 trials × 2 reps × 2 algos
    assert "ADR-001" in summary_payload["control_note"]

    lines = [ln for ln in trials.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 8
    row0 = json.loads(lines[0])
    assert row0["result_schema_version"] == "4.2.0"
    assert row0["representation"] in {"uniform_u", "uniform_q"}
    assert row0["cost_type"] == "output_euclidean"
    assert row0["adr001_unchanged"] is True
    assert "path_length_u" in row0
    assert "path_length_q" in row0
    assert "path_length_x" in row0
    assert "resolution" in row0
