"""Paired planar 3R mechanism arms (Sprint V3.7 / V3-701)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from inequality_mechanisms.adapters.planar_3r_robot import (
    planar_3r_operating_branch_robot,
)
from inequality_mechanisms.core.state import PhysicalState
from inequality_mechanisms.kinematics.planar_3r import Planar3R
from inequality_mechanisms.mechanisms import (
    IndependentFourBars,
    PlanarFourBar,
    equivalent_gearbox_branch,
    select_fourbar_monotonic_branch,
)
from inequality_mechanisms.mechanisms.operating_branch import OperatingBranch

MechanismName = Literal["fourbar", "gearbox"]

_CRANK_ROCKER = dict(a=1.0, b=2.5, c=2.0, d=2.0)


def _fourbar_3d_branch() -> OperatingBranch:
    bars = [
        PlanarFourBar(**_CRANK_ROCKER, branch=1, name="b0"),
        PlanarFourBar(**_CRANK_ROCKER, branch=1, name="b1"),
        PlanarFourBar(**_CRANK_ROCKER, branch=1, name="b2"),
    ]
    return select_fourbar_monotonic_branch(IndependentFourBars(bars))


@dataclass(frozen=True, slots=True)
class Planar3RArm:
    """One paired 3R mechanism arm sharing planar FK."""

    name: MechanismName
    branch: OperatingBranch
    robot: Any
    planar_fk: Planar3R


def build_paired_3r_arms(
    *,
    L1: float = 1.0,
    L2: float = 1.0,
    L3: float = 1.0,
) -> dict[MechanismName, Planar3RArm]:
    """Return four-bar and span-matched gearbox robots sharing ``Planar3R`` FK."""
    fk = Planar3R(L1=L1, L2=L2, L3=L3)
    fourbar = _fourbar_3d_branch()
    gearbox = equivalent_gearbox_branch(fourbar, name="span_matched_gearbox_3r")
    return {
        "fourbar": Planar3RArm(
            name="fourbar",
            branch=fourbar,
            robot=planar_3r_operating_branch_robot(fourbar, planar_fk=fk),
            planar_fk=fk,
        ),
        "gearbox": Planar3RArm(
            name="gearbox",
            branch=gearbox,
            robot=planar_3r_operating_branch_robot(gearbox, planar_fk=fk),
            planar_fk=fk,
        ),
    }


def state_from_u_frac(
    arm: Planar3RArm,
    frac: tuple[float, float, float],
) -> PhysicalState:
    """Map normalized actuator fractions to a physical state."""
    cert = arm.branch.certificate
    u_lo = np.asarray(cert.input_lower, dtype=np.float64)
    u_hi = np.asarray(cert.input_upper, dtype=np.float64)
    u = u_lo + np.asarray(frac, dtype=np.float64) * (u_hi - u_lo)
    return arm.robot.state_from_input(u)


__all__ = [
    "MechanismName",
    "Planar3RArm",
    "build_paired_3r_arms",
    "state_from_u_frac",
]
