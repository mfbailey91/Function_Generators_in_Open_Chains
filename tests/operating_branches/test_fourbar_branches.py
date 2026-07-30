"""Four-bar monotonic operating-branch tests (Sprint V2.2, V2-203/204/205)."""

from __future__ import annotations

import numpy as np
import pytest

from inequality_mechanisms.mechanisms import (
    BranchCertificationError,
    IndependentFourBars,
    OperatingBranch,
    PlanarFourBar,
    select_fourbar_monotonic_branch,
)
from inequality_mechanisms.spaces.output_space import wrap_to_pi

_CRANK_ROCKER = dict(a=1.0, b=2.5, c=2.0, d=2.0)

# A crank-rocker whose widest monotonic sector's continuous follower image
# straddles the +pi principal-angle representation seam (found by search;
# see docs/software/architecture/audits/V2_2_BRANCH_CERTIFICATION.md).
_SEAM_LENGTHS = dict(
    a=1.4107583303834286,
    b=2.6552483854563453,
    c=2.7103675205343354,
    d=1.2136827533866033,
)


def _two_axis_mechanism() -> IndependentFourBars:
    bars = [
        PlanarFourBar(**_CRANK_ROCKER, branch=1, name="b0"),
        PlanarFourBar(**_CRANK_ROCKER, branch=1, name="b1"),
    ]
    return IndependentFourBars(bars)


class TestMonotonicBranchSelection:
    def test_positive_monotonic_branch(self) -> None:
        mech = _two_axis_mechanism()
        branch = select_fourbar_monotonic_branch(mech)
        cert = branch.certificate
        assert cert.monotonic_sign == (1, 1)
        assert cert.certification_method == "fourbar_monotone_table_bisection"
        lo = np.asarray(cert.input_lower)
        hi = np.asarray(cert.input_upper)
        mid = 0.5 * (lo + hi)
        for u in (lo, mid, hi):
            q = branch.forward(u)
            u_back = branch.inverse(q)
            assert u_back == pytest.approx(u, abs=1e-6)

    def test_negative_monotonic_branch(self) -> None:
        bar = PlanarFourBar(**_CRANK_ROCKER, branch=1, name="b0")
        # sector_choice=1 selects the second-widest candidate on this bar,
        # which has sign -1 (see tests/mechanisms/test_monotonic.py sectors).
        branch = select_fourbar_monotonic_branch(bar, sector_choice=[1])
        assert branch.certificate.monotonic_sign == (-1,)
        lo = np.asarray(branch.certificate.input_lower)
        hi = np.asarray(branch.certificate.input_upper)
        for u in (lo, 0.5 * (lo + hi), hi):
            q = branch.forward(u)
            assert branch.inverse(q) == pytest.approx(u, abs=1e-6)

    def test_endpoint_consistency_with_sign(self) -> None:
        mech = _two_axis_mechanism()
        branch = select_fourbar_monotonic_branch(mech)
        cert = branch.certificate
        q_at_lo = branch.forward(np.asarray(cert.input_lower))
        q_at_hi = branch.forward(np.asarray(cert.input_upper))
        for i, sign in enumerate(cert.monotonic_sign):
            if sign > 0:
                assert q_at_lo[i] == pytest.approx(cert.output_lower[i], abs=1e-6)
                assert q_at_hi[i] == pytest.approx(cert.output_upper[i], abs=1e-6)
            else:
                assert q_at_lo[i] == pytest.approx(cert.output_upper[i], abs=1e-6)
                assert q_at_hi[i] == pytest.approx(cert.output_lower[i], abs=1e-6)

    def test_seam_crossing_branch_remains_continuous(self) -> None:
        bar = PlanarFourBar(**_SEAM_LENGTHS, branch=1)
        branch = select_fourbar_monotonic_branch(
            bar,
            u_intervals=[(5.0, 5.9)],
            min_abs_gain=0.01,
            table_samples_per_axis=65,
            certification_samples_per_axis=9,
        )
        cert = branch.certificate
        # The achieved output chart straddles the +pi seam.
        assert cert.output_lower[0] < np.pi < cert.output_upper[0]

        u_samples = np.linspace(cert.input_lower[0], cert.input_upper[0], 60)
        q_branch = np.array([float(branch.forward([u])[0]) for u in u_samples])
        # The certified branch stays continuous (small per-step change)...
        assert np.max(np.abs(np.diff(q_branch))) < 0.1
        # ...unlike a naive shortest-angle wrap of the same raw curve, which
        # exhibits a large discontinuity right at the seam (ADR-011).
        q_naive_wrapped = np.array([wrap_to_pi(float(q)) for q in q_branch])
        assert np.max(np.abs(np.diff(q_naive_wrapped))) > 1.0

    def test_deterministic_certificate_for_fixed_settings(self) -> None:
        mech1 = _two_axis_mechanism()
        mech2 = _two_axis_mechanism()
        branch1 = select_fourbar_monotonic_branch(mech1)
        branch2 = select_fourbar_monotonic_branch(mech2)
        assert branch1.certificate == branch2.certificate
        assert branch1.branch_id == branch2.branch_id

    def test_residuals_within_default_tolerance(self) -> None:
        branch = select_fourbar_monotonic_branch(_two_axis_mechanism())
        cert = branch.certificate
        assert cert.max_forward_inverse_residual <= 1e-6
        assert cert.max_inverse_forward_residual <= 1e-6

    def test_serialization_round_trip(self) -> None:
        branch = select_fourbar_monotonic_branch(_two_axis_mechanism())
        restored = OperatingBranch.from_dict(branch.to_dict())
        u = np.asarray(branch.certificate.input_lower)
        assert restored.forward(u) == pytest.approx(branch.forward(u))
        assert restored.certificate == branch.certificate
        assert restored.branch_id == branch.branch_id


class TestMonotonicBranchRejection:
    def test_rejects_interval_spanning_a_reversal(self) -> None:
        mech = _two_axis_mechanism()
        with pytest.raises(
            BranchCertificationError, match="not strictly monotonic|reversal"
        ):
            select_fourbar_monotonic_branch(mech, u_intervals=[(0.0, 6.2), (0.0, 6.2)])

    def test_rejects_when_no_interval_meets_min_gain(self) -> None:
        mech = _two_axis_mechanism()
        with pytest.raises(
            BranchCertificationError, match="no monotonic candidate interval"
        ):
            select_fourbar_monotonic_branch(mech, min_abs_gain=100.0)

    def test_rejects_low_gain_close_to_sector_boundary(self) -> None:
        """An interval with no safety margin can dip below min_abs_gain."""
        bar = PlanarFourBar(**_CRANK_ROCKER, branch=1)
        from inequality_mechanisms.mechanisms.monotonic import find_monotonic_sectors

        sector = find_monotonic_sectors(bar, min_abs_gain=0.05)[0]
        with pytest.raises(BranchCertificationError, match="minimum \\|dq/du\\|"):
            select_fourbar_monotonic_branch(
                bar,
                u_intervals=[(sector.u_lo, sector.u_hi)],
                min_abs_gain=0.05,
                certification_samples_per_axis=25,
            )

    def test_endpoint_margin_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError, match="endpoint_margin_fraction"):
            select_fourbar_monotonic_branch(
                PlanarFourBar(**_CRANK_ROCKER, branch=1), endpoint_margin_fraction=0.9
            )

    def test_inverse_outside_range_raises(self) -> None:
        branch = select_fourbar_monotonic_branch(
            PlanarFourBar(**_CRANK_ROCKER, branch=1)
        )
        from inequality_mechanisms.mechanisms import BranchInverseError

        # A small offset (not a multiple that could wrap back inside the
        # bounded revolute chart) that lies just past the certified range.
        just_outside = branch.certificate.output_upper[0] + 0.05
        with pytest.raises(BranchInverseError, match="outside the branch output range"):
            branch.inverse([just_outside])
