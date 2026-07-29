"""Property-style forward/inverse invariants for operating branches (Sprint V2.2)."""

from __future__ import annotations

import numpy as np
import pytest

from inequality_mechanisms.mechanisms import (
    IndependentFourBars,
    PlanarFourBar,
    equivalent_gearbox_branch,
    fixed_ratio_gearbox_branch,
    select_fourbar_monotonic_branch,
    unit_gearbox_branch,
)

_CRANK_ROCKER = dict(a=1.0, b=2.5, c=2.0, d=2.0)
_N_SAMPLES = 40
_EPS_U = 1e-6
_EPS_Q = 1e-6


def _assert_roundtrip_invariants(branch, u_samples: np.ndarray) -> None:
    for u in u_samples:
        q = branch.forward(u)
        u_back = branch.inverse(q)
        assert np.linalg.norm(u_back - u) <= _EPS_U
        q_back = branch.forward(u_back)
        assert np.linalg.norm(q_back - q) <= _EPS_Q


class TestAffineBranchInvariants:
    def test_unit_gearbox_roundtrip_invariants(self) -> None:
        branch = unit_gearbox_branch(
            2, input_lower=[-2.0, -2.0], input_upper=[2.0, 2.0]
        )
        rng = np.random.default_rng(42)
        u_samples = rng.uniform([-2.0, -2.0], [2.0, 2.0], size=(_N_SAMPLES, 2))
        _assert_roundtrip_invariants(branch, u_samples)

    def test_fixed_ratio_gearbox_roundtrip_invariants(self) -> None:
        branch = fixed_ratio_gearbox_branch(
            [1.7, -0.6], input_lower=[-1.0, -1.0], input_upper=[1.0, 1.0]
        )
        rng = np.random.default_rng(43)
        u_samples = rng.uniform([-1.0, -1.0], [1.0, 1.0], size=(_N_SAMPLES, 2))
        _assert_roundtrip_invariants(branch, u_samples)

    def test_equivalent_gearbox_roundtrip_invariants(self) -> None:
        reference = fixed_ratio_gearbox_branch(
            [2.2], input_lower=[-1.0], input_upper=[1.5]
        )
        matched = equivalent_gearbox_branch(reference)
        rng = np.random.default_rng(44)
        u_samples = rng.uniform([-1.0], [1.5], size=(_N_SAMPLES, 1))
        _assert_roundtrip_invariants(matched, u_samples)


class TestFourBarBranchInvariants:
    def test_single_axis_roundtrip_invariants(self) -> None:
        bar = PlanarFourBar(**_CRANK_ROCKER, branch=1)
        branch = select_fourbar_monotonic_branch(bar)
        lo = float(branch.certificate.input_lower[0])
        hi = float(branch.certificate.input_upper[0])
        rng = np.random.default_rng(45)
        u_samples = rng.uniform(lo, hi, size=(_N_SAMPLES, 1))
        _assert_roundtrip_invariants(branch, u_samples)

    def test_two_axis_roundtrip_invariants(self) -> None:
        bars = [
            PlanarFourBar(**_CRANK_ROCKER, branch=1, name="b0"),
            PlanarFourBar(**_CRANK_ROCKER, branch=1, name="b1"),
        ]
        mech = IndependentFourBars(bars)
        branch = select_fourbar_monotonic_branch(mech)
        lo = np.asarray(branch.certificate.input_lower)
        hi = np.asarray(branch.certificate.input_upper)
        rng = np.random.default_rng(46)
        u_samples = rng.uniform(lo, hi, size=(_N_SAMPLES, 2))
        _assert_roundtrip_invariants(branch, u_samples)

    @pytest.mark.parametrize("sector_choice", [0, 1])
    def test_roundtrip_invariants_hold_on_both_signed_branches(
        self, sector_choice: int
    ) -> None:
        bar = PlanarFourBar(**_CRANK_ROCKER, branch=1)
        branch = select_fourbar_monotonic_branch(bar, sector_choice=[sector_choice])
        lo = float(branch.certificate.input_lower[0])
        hi = float(branch.certificate.input_upper[0])
        rng = np.random.default_rng(47 + sector_choice)
        u_samples = rng.uniform(lo, hi, size=(_N_SAMPLES, 1))
        _assert_roundtrip_invariants(branch, u_samples)
