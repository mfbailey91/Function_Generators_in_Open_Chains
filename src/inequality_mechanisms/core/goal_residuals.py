"""Typed physical / representation / attachment goal residuals (V3-631)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from inequality_mechanisms.core.goals import GoalConstraint, GoalResidual
from inequality_mechanisms.core.state import PhysicalState, StateCandidate


@dataclass(frozen=True, slots=True)
class GoalResidualReport:
    """Separated residual meanings for a selected goal state.

    Parameters
    ----------
    physical :
        Residual from the original ``GoalConstraint`` on the selected state.
        This is the main success-quality value.
    goal_margin :
        Signed distance to the physical tolerance boundary when the predicate
        exposes it (for example ``signed_disk_residual``).
    representation :
        Error associated with finite goal sampling or IK when a candidate is
        known; never substituted for ``physical``.
    attachment :
        Numerical query-overlay or reconstruction error when known; never
        substituted for ``physical``.
    """

    physical: GoalResidual | None
    goal_margin: float | None = None
    representation: float | None = None
    attachment: float | None = None


def _extract_goal_margin(physical: GoalResidual) -> float | None:
    extras = physical.extras
    if "signed_disk_residual" in extras:
        return float(extras["signed_disk_residual"])
    if "signed_orientation_residual" in extras:
        return float(extras["signed_orientation_residual"])
    return None


def _representation_residual(
    goal: GoalConstraint,
    candidate: StateCandidate | None,
) -> float | None:
    if candidate is None:
        return None
    sample_point = candidate.provenance.get("goal_sample_point")
    robot = getattr(goal, "robot", None)
    if sample_point is not None and robot is not None:
        tip = np.asarray(
            robot.forward_kinematics(candidate.state).position, dtype=np.float64
        )
        point = np.asarray(sample_point, dtype=np.float64)
        return float(np.linalg.norm(tip - point))
    return float(candidate.residual)


def build_goal_residual_report(
    goal: GoalConstraint,
    selected: PhysicalState,
    *,
    candidate: StateCandidate | None = None,
    attachment_residual: float | None = None,
) -> GoalResidualReport:
    """Build a typed residual report for ``selected`` under ``goal``.

    ``physical`` is always ``goal.residual(selected)``. Attachment is taken only
    from ``attachment_residual`` when provided and is never used as the physical
    task residual.
    """
    physical = goal.residual(selected)
    attachment = None
    if attachment_residual is not None:
        attachment = float(attachment_residual)
        if not np.isfinite(attachment):
            raise ValueError("attachment_residual must be finite")
    return GoalResidualReport(
        physical=physical,
        goal_margin=_extract_goal_margin(physical),
        representation=_representation_residual(goal, candidate),
        attachment=attachment,
    )
