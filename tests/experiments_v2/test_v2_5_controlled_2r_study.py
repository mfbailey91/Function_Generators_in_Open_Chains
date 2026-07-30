from __future__ import annotations

from pathlib import Path

from inequality_mechanisms.experiments.v2_2r_study import (
    _assert_null_control_cell_b_matches,
    run_v2_2r_controlled_deterministic_matrix,
    run_v2_2r_resolution_sweep_cell_b,
)


def test_v2_5_deterministic_matrix_cell_b_null_control(tmp_path: Path) -> None:
    results = run_v2_2r_controlled_deterministic_matrix(
        results_root=tmp_path / "results",
        run_id_prefix="v2_5_det",
        shape=(6, 6),
        algorithms=["dijkstra"],
        output_tolerance=100.0,
        tasks_pairs=((0.0, 0.0), (1.0, 1.0)),
    )

    # Each run has:
    # - 1 accepted task
    # - 2 mechanisms
    # - 1 algorithm (dijkstra)
    # => 2 trial rows, 0 failures.
    for cell in ("A", "B", "C", "D"):
        assert results[cell].n_trial_rows == 2
        assert results[cell].n_failure_rows == 0

    _assert_null_control_cell_b_matches(run_path=results["B"].path, algorithm="dijkstra")


def test_v2_5_resolution_sweep_cell_b_null_control(tmp_path: Path) -> None:
    runs = run_v2_2r_resolution_sweep_cell_b(
        results_root=tmp_path / "results",
        run_id_prefix="v2_5_res",
        shapes=[(4, 4), (6, 6)],
        output_tolerance=100.0,
        tasks_pairs=((0.0, 0.0), (1.0, 1.0)),
    )

    assert len(runs) == 2
    for r in runs:
        assert r.n_trial_rows == 2
        assert r.n_failure_rows == 0
        _assert_null_control_cell_b_matches(run_path=r.path, algorithm="dijkstra")

