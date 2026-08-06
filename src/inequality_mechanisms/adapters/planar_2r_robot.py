"""Planar 2R OperatingBranch robot factory (Sprint V3.2 / V3-200)."""

from __future__ import annotations

from inequality_mechanisms.adapters.operating_branch_robot import (
    OperatingBranchRobotModel,
)
from inequality_mechanisms.kinematics.planar_2r import Planar2R
from inequality_mechanisms.mechanisms.operating_branch import OperatingBranch


def planar_2r_operating_branch_robot(
    branch: OperatingBranch,
    *,
    L1: float = 1.0,
    L2: float = 1.0,
    planar_fk: Planar2R | None = None,
) -> OperatingBranchRobotModel:
    """Wrap a certified 2R operating branch with planar tip FK.

    Parameters
    ----------
    branch :
        Certified monotonic operating branch (transmission map).
    L1, L2 :
        Link lengths when ``planar_fk`` is omitted.
    planar_fk :
        Optional shared ``Planar2R`` instance (e.g. paired smoke studies).
    """
    fk = planar_fk if planar_fk is not None else Planar2R(L1=L1, L2=L2)
    return OperatingBranchRobotModel(branch=branch, planar_fk=fk)
