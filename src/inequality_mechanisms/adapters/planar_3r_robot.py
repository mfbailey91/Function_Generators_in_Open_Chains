"""Planar 3R OperatingBranch robot factory (Sprint V3.7 / V3-701)."""

from __future__ import annotations

from inequality_mechanisms.adapters.operating_branch_robot import (
    OperatingBranchRobotModel,
)
from inequality_mechanisms.kinematics.planar_3r import Planar3R
from inequality_mechanisms.mechanisms.operating_branch import OperatingBranch


def planar_3r_operating_branch_robot(
    branch: OperatingBranch,
    *,
    L1: float = 1.0,
    L2: float = 1.0,
    L3: float = 1.0,
    planar_fk: Planar3R | None = None,
) -> OperatingBranchRobotModel:
    """Wrap a certified 3R operating branch with planar tip/pose FK.

    Parameters
    ----------
    branch :
        Certified monotonic operating branch with ``output_dim == 3``.
    L1, L2, L3 :
        Link lengths when ``planar_fk`` is omitted.
    planar_fk :
        Optional shared ``Planar3R`` instance for paired studies.
    """
    if int(branch.mechanism.output_dim) != 3:
        raise ValueError(
            f"planar 3R factory requires output_dim 3, got {branch.mechanism.output_dim}"
        )
    fk = planar_fk if planar_fk is not None else Planar3R(L1=L1, L2=L2, L3=L3)
    return OperatingBranchRobotModel(branch=branch, planar_fk=fk)
