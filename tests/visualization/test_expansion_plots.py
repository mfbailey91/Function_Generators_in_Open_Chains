"""Tests for expansion plot helpers (IM-017)."""

from __future__ import annotations

from pathlib import Path

from inequality_mechanisms.visualization.expansions import (
    plot_normalized_expansions,
    plot_paired_log_ratios,
    plot_raw_expansions,
)


def _sample_rows() -> list[dict]:
    rows: list[dict] = []
    for trial in range(4):
        for algorithm in ("dijkstra", "astar"):
            for mechanism, n_exp, n_valid in (
                ("gearbox", 50 + trial * 3, 200),
                ("fourbar", 5 + trial, 40),
            ):
                rows.append(
                    {
                        "trial_index": trial,
                        "algorithm": algorithm,
                        "mechanism": mechanism,
                        "found": True,
                        "n_expanded": n_exp,
                        "n_valid_nodes": n_valid,
                        "rho_expanded": n_exp / n_valid,
                    }
                )
    return rows


class TestExpansionPlots:
    def test_writes_nonempty_pngs(self, tmp_path: Path) -> None:
        rows = _sample_rows()
        raw = plot_raw_expansions(rows, tmp_path / "raw.png")
        norm = plot_normalized_expansions(rows, tmp_path / "norm.png")
        ratio = plot_paired_log_ratios(rows, tmp_path / "ratio.png")
        for path in (raw, norm, ratio):
            assert path.is_file()
            assert path.stat().st_size > 0

    def test_empty_series_still_writes(self, tmp_path: Path) -> None:
        path = plot_raw_expansions([], tmp_path / "empty.png")
        assert path.is_file()
        assert path.stat().st_size > 0
