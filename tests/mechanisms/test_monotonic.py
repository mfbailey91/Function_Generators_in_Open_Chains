"""Tests for monotonic-branch helpers (S4-11a)."""

from __future__ import annotations

import numpy as np
import pytest

from inequality_mechanisms.mechanisms import (
    IndependentFourBars,
    PlanarFourBar,
    find_monotonic_sectors,
    monotonic_box_for_independent_fourbars,
    open_axis_independent_fourbars,
    primary_monotonic_sector,
    unique_inverse_output,
)

_CRANK_ROCKER = dict(a=1.0, b=2.5, c=2.0, d=2.0)


class TestMonotonicSectors:
    def test_primary_sector_has_constant_sign_gain(self) -> None:
        bar = PlanarFourBar(**_CRANK_ROCKER, branch=1)
        sector = primary_monotonic_sector(bar)
        assert sector.u_hi > sector.u_lo
        assert sector.q_hi > sector.q_lo
        assert sector.sign in (-1, 1)
        u = np.linspace(sector.u_lo, sector.u_hi, 40, endpoint=False)
        for uu in u:
            r = float(bar.output_jacobian([float(uu)])[0, 0])
            assert np.isfinite(r)
            assert np.sign(r) == sector.sign or abs(r) < 1e-12

    def test_sectors_sorted_by_width(self) -> None:
        bar = PlanarFourBar(**_CRANK_ROCKER, branch=1)
        sectors = find_monotonic_sectors(bar)
        assert len(sectors) >= 1
        widths = [s.u_width for s in sectors]
        assert widths == sorted(widths, reverse=True)


class TestUniqueInverse:
    def test_unique_inverse_roundtrip_inside_box(self) -> None:
        bars = [
            PlanarFourBar(**_CRANK_ROCKER, branch=1, name="b0"),
            PlanarFourBar(**_CRANK_ROCKER, branch=1, name="b1"),
        ]
        mech = IndependentFourBars(bars)
        box = monotonic_box_for_independent_fourbars(mech)
        q = np.array(
            [
                0.5 * (box.q_ranges[0][0] + box.q_ranges[0][1]),
                0.5 * (box.q_ranges[1][0] + box.q_ranges[1][1]),
            ]
        )
        u = unique_inverse_output(mech, q, u_ranges=box.u_ranges)
        q_fwd = mech.input_to_output(u)
        for i in range(2):
            delta = float(q_fwd[i] - q[i])
            delta = (delta + np.pi) % (2.0 * np.pi) - np.pi
            assert abs(delta) < 1e-6

    def test_unique_inverse_fails_outside_image(self) -> None:
        bars = [
            PlanarFourBar(**_CRANK_ROCKER, branch=1, name="b0"),
            PlanarFourBar(**_CRANK_ROCKER, branch=1, name="b1"),
        ]
        mech = IndependentFourBars(bars)
        box = monotonic_box_for_independent_fourbars(mech)
        q = np.array([box.q_ranges[0][1] + 1.0, box.q_ranges[1][0]])
        with pytest.raises(ValueError, match="no inverse|non-unique|verification"):
            unique_inverse_output(mech, q, u_ranges=box.u_ranges)

    def test_open_axis_clone_reports_nonperiodic(self) -> None:
        mech = IndependentFourBars(
            [
                PlanarFourBar(**_CRANK_ROCKER, branch=1, name="b0"),
                PlanarFourBar(**_CRANK_ROCKER, branch=1, name="b1"),
            ]
        )
        open_mech = open_axis_independent_fourbars(mech)
        assert open_mech.periodic_axes() == (False, False)
        assert open_mech.bars[0].lengths == mech.bars[0].lengths
        assert open_mech.bars[1].lengths == mech.bars[1].lengths
