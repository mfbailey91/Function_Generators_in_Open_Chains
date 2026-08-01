"""Tests for Version 2 shared-Q expansion figures."""

from __future__ import annotations

from pathlib import Path

from inequality_mechanisms.visualization.v2_expansions import (
    _mechanism_ids_present,
    plot_v2_expansions_by_alpha,
    plot_v2_expansions_by_mechanism,
)


def _three_arm_rows() -> list[dict]:
    rows: list[dict] = []
    for alpha in (1.0, 0.5):
        for mech, n_exp in (
            ("fourbar", 40),
            ("span_matched_gearbox", 35),
            ("unit_gearbox", 40),
        ):
            rows.append(
                {
                    "mechanism_id": mech,
                    "algorithm": "dijkstra",
                    "found": True,
                    "alpha": alpha,
                    "n_expanded": n_exp,
                }
            )
    return rows


class TestMechanismIdsPresent:
    def test_includes_unit_gearbox(self) -> None:
        ids = _mechanism_ids_present(_three_arm_rows())
        assert ids == ["fourbar", "span_matched_gearbox", "unit_gearbox"]

    def test_drops_equivalent_when_span_matched_present(self) -> None:
        rows = _three_arm_rows() + [
            {
                "mechanism_id": "equivalent_affine_gearbox",
                "algorithm": "dijkstra",
                "found": True,
                "alpha": 1.0,
                "n_expanded": 10,
            }
        ]
        ids = _mechanism_ids_present(rows)
        assert "equivalent_affine_gearbox" not in ids
        assert "unit_gearbox" in ids


class TestV2ExpansionPlots:
    def test_by_mechanism_writes_png(self, tmp_path: Path) -> None:
        out = plot_v2_expansions_by_mechanism(
            _three_arm_rows(), tmp_path / "expansions_raw.png"
        )
        assert out.is_file()
        assert out.stat().st_size > 0

    def test_by_alpha_writes_png(self, tmp_path: Path) -> None:
        out = plot_v2_expansions_by_alpha(
            _three_arm_rows(), tmp_path / "expansions_by_alpha.png"
        )
        assert out.is_file()
        assert out.stat().st_size > 0
