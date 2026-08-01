"""Smoke tests for operating-branch diagnostics (Sprint V2.2, V2-207)."""

from __future__ import annotations

from pathlib import Path

import pytest

from inequality_mechanisms.mechanisms import (
    IndependentFourBars,
    PlanarFourBar,
    equivalent_gearbox_branch,
    fixed_ratio_gearbox_branch,
    select_fourbar_monotonic_branch,
)
from inequality_mechanisms.visualization.branches import (
    plot_branch_axis_transmission,
    plot_operating_branch,
)

_CRANK_ROCKER = dict(a=1.0, b=2.5, c=2.0, d=2.0)


class TestPlotOperatingBranch:
    def test_writes_nonempty_png_for_affine_branch(self, tmp_path: Path) -> None:
        branch = fixed_ratio_gearbox_branch(
            [1.5, -0.5], input_lower=[-1.0, -1.0], input_upper=[1.0, 1.0]
        )
        out = plot_operating_branch(branch, tmp_path / "affine.png", n_samples=25)
        assert out.is_file()
        assert out.stat().st_size > 0

    def test_writes_nonempty_png_for_fourbar_branch_with_matched_affine(
        self, tmp_path: Path
    ) -> None:
        bars = [
            PlanarFourBar(**_CRANK_ROCKER, branch=1, name="b0"),
            PlanarFourBar(**_CRANK_ROCKER, branch=1, name="b1"),
        ]
        mech = IndependentFourBars(bars)
        branch = select_fourbar_monotonic_branch(mech)
        matched = equivalent_gearbox_branch(branch)
        out = plot_operating_branch(
            branch,
            tmp_path / "fourbar.png",
            matched_affine=matched,
            n_samples=30,
            title="four-bar branch",
        )
        assert out.is_file()
        assert out.stat().st_size > 0

    def test_rejects_too_few_samples(self, tmp_path: Path) -> None:
        branch = fixed_ratio_gearbox_branch([1.0], input_lower=[0.0], input_upper=[1.0])
        with pytest.raises(ValueError, match="n_samples"):
            plot_operating_branch(branch, tmp_path / "bad.png", n_samples=1)


class TestPlotBranchAxisTransmission:
    def test_writes_nonempty_png_for_fourbar_and_unit(self, tmp_path: Path) -> None:
        bars = [
            PlanarFourBar(**_CRANK_ROCKER, branch=1, name="b0"),
            PlanarFourBar(**_CRANK_ROCKER, branch=1, name="b1"),
        ]
        mech = IndependentFourBars(bars)
        fourbar = select_fourbar_monotonic_branch(mech)
        unit = fixed_ratio_gearbox_branch(
            [1.0, 1.0],
            input_lower=list(fourbar.certificate.output_lower),
            input_upper=list(fourbar.certificate.output_upper),
            name="unit_gearbox",
        )
        out = plot_branch_axis_transmission(
            {"Four-bar": fourbar, "Unit gearbox": unit},
            tmp_path / "qu_axis_maps.png",
            n_samples=30,
            title="transmission",
        )
        assert out.is_file()
        assert out.stat().st_size > 0

    def test_rejects_too_few_samples(self, tmp_path: Path) -> None:
        branch = fixed_ratio_gearbox_branch([1.0], input_lower=[0.0], input_upper=[1.0])
        with pytest.raises(ValueError, match="n_samples"):
            plot_branch_axis_transmission(
                {"unit": branch}, tmp_path / "bad.png", n_samples=1
            )
