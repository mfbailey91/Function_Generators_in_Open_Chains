"""Version 2 HTML printout tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from inequality_mechanisms.experiments.v2_canvas import (
    V2CanvasError,
    resolve_v2_run_for_canvas,
    write_v2_canvas,
)
from inequality_mechanisms.experiments.v2_runner import run_v2_experiment_from_path

_REPO = Path(__file__).resolve().parents[2]
_SMOKE = _REPO / "configs" / "v2" / "smoke.yaml"


def test_v2_runner_writes_index_html(tmp_path: Path) -> None:
    res = run_v2_experiment_from_path(
        _SMOKE,
        results_root=tmp_path / "results",
        run_id="v2_canvas_smoke",
        write_figures=False,
    )
    canvas = res.path / "index.html"
    assert canvas.is_file()
    text = canvas.read_text(encoding="utf-8")
    assert "architecture_version" in text
    assert res.run_id in text
    assert "fourbar" in text
    assert "equivalent_affine_gearbox" in text
    assert "Null-control" in text or "null-control" in text.lower()


def test_write_v2_canvas_does_not_mutate_trials_jsonl(tmp_path: Path) -> None:
    res = run_v2_experiment_from_path(
        _SMOKE,
        results_root=tmp_path / "results",
        run_id="v2_canvas_regen",
        write_figures=False,
    )
    trials_path = res.path / "trials.jsonl"
    before = trials_path.read_bytes()
    write_v2_canvas(res.path)
    after = trials_path.read_bytes()
    assert before == after
    assert (res.path / "index.html").is_file()


def test_resolve_rejects_non_v2_directory(tmp_path: Path) -> None:
    bogus = tmp_path / "not_v2"
    bogus.mkdir()
    (bogus / "manifest.json").write_text(
        '{"architecture_version": 1, "run_id": "x"}\n', encoding="utf-8"
    )
    with pytest.raises(V2CanvasError, match="not a Version 2 run package"):
        resolve_v2_run_for_canvas(bogus)


def test_resolve_latest_v2_run(tmp_path: Path) -> None:
    root = tmp_path / "results"
    run_a = run_v2_experiment_from_path(
        _SMOKE,
        results_root=root,
        run_id="v2_canvas_a",
        write_figures=False,
    )
    run_b = run_v2_experiment_from_path(
        _SMOKE,
        results_root=root,
        run_id="v2_canvas_b",
        write_figures=False,
    )
    latest = resolve_v2_run_for_canvas(None, results_root=root)
    assert latest in {run_a.path.resolve(), run_b.path.resolve()}
