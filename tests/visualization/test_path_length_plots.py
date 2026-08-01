"""Tests for path-length distribution plot helpers."""

from __future__ import annotations

from pathlib import Path

from inequality_mechanisms.visualization.path_lengths import (
    plot_path_length_distributions,
    plot_path_length_q,
    plot_path_length_x,
    successful_path_lengths,
)


def _sample_rows() -> list[dict]:
    rows: list[dict] = []
    for trial in range(4):
        for algorithm in ("dijkstra", "astar"):
            for mechanism, lq, lx in (
                ("gearbox", 1.0 + 0.1 * trial, 0.8 + 0.05 * trial),
                ("fourbar", 1.2 + 0.15 * trial, 1.0 + 0.1 * trial),
            ):
                rows.append(
                    {
                        "trial_index": trial,
                        "algorithm": algorithm,
                        "mechanism": mechanism,
                        "found": True,
                        "path_length_q": lq,
                        "path_length_x": lx,
                    }
                )
    return rows


class TestPathLengthPlots:
    def test_successful_path_lengths_filters(self) -> None:
        rows = _sample_rows() + [
            {
                "algorithm": "dijkstra",
                "mechanism": "gearbox",
                "found": False,
                "path_length_q": 99.0,
            },
            {
                "algorithm": "dijkstra",
                "mechanism": "gearbox",
                "found": True,
                "path_length_q": float("nan"),
            },
        ]
        vals = successful_path_lengths(
            rows, "path_length_q", algorithm="dijkstra", mechanism="gearbox"
        )
        assert len(vals) == 4
        assert all(v < 2.0 for v in vals)

    def test_writes_nonempty_pngs(self, tmp_path: Path) -> None:
        rows = _sample_rows()
        q = plot_path_length_q(rows, tmp_path / "lq.png")
        x = plot_path_length_x(rows, tmp_path / "lx.png")
        generic = plot_path_length_distributions(
            rows,
            "path_length_q",
            tmp_path / "generic.png",
            title="generic",
            ylabel="L",
        )
        for path in (q, x, generic):
            assert path.is_file()
            assert path.stat().st_size > 0

    def test_empty_series_still_writes(self, tmp_path: Path) -> None:
        path = plot_path_length_q([], tmp_path / "empty.png")
        assert path.is_file()
        assert path.stat().st_size > 0
