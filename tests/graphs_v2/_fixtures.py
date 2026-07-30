"""Shared certified-branch fixtures for Sprint V2.3 graph tests."""

from __future__ import annotations

from inequality_mechanisms.mechanisms import (
    IndependentFourBars,
    OperatingBranch,
    PlanarFourBar,
    fixed_ratio_gearbox_branch,
    select_fourbar_monotonic_branch,
    unit_gearbox_branch,
)

_CRANK_ROCKER = dict(a=1.0, b=2.5, c=2.0, d=2.0)


def affine_1d_branch() -> OperatingBranch:
    """A 1-D affine (unit gearbox) branch: ``q = u``."""
    return unit_gearbox_branch(1, input_lower=[0.0], input_upper=[10.0])


def gearbox_2d_branch() -> OperatingBranch:
    """A 2-D affine (fixed-ratio gearbox) branch: ``q = diag(2, -3) u``."""
    return fixed_ratio_gearbox_branch(
        [2.0, -3.0], input_lower=[-1.0, -1.0], input_upper=[1.0, 1.0]
    )


def fourbar_2d_mechanism() -> IndependentFourBars:
    """Two independent crank-rocker four-bars (2R fixture)."""
    bars = [
        PlanarFourBar(**_CRANK_ROCKER, branch=1, name="b0"),
        PlanarFourBar(**_CRANK_ROCKER, branch=1, name="b1"),
    ]
    return IndependentFourBars(bars)


def fourbar_2d_branch() -> OperatingBranch:
    """A certified 2-D nonlinear (four-bar) operating branch."""
    return select_fourbar_monotonic_branch(fourbar_2d_mechanism())
