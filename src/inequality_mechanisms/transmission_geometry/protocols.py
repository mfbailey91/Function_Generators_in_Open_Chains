"""Version 4 differential capability protocol (ADR-027, V4-001).

This extension is the compatibility boundary for kinematic transmission
geometry. It is not added to the accepted Version 3 ``RobotModel`` protocol.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray

from inequality_mechanisms.core.robot import RobotModel
from inequality_mechanisms.core.state import PhysicalState

DEFAULT_STATE_TOLERANCE = 1e-9
"""Declared ``||q - g(u)||`` cutoff for Version 4 differential queries."""


@runtime_checkable
class KinematicTransmissionRobotModel(RobotModel, Protocol):
    """Robot model that exposes the transmission Jacobian ``J_g = dq/du``."""

    def jacobian_u_to_q(
        self,
        state: PhysicalState,
    ) -> NDArray[np.float64]:
        """Return ``J_g = dq/du`` at a certified physical state.

        Parameters
        ----------
        state :
            Physical state whose ``u`` and ``q`` agree with the transmission
            map within the robot's declared state tolerance.

        Returns
        -------
        ndarray
            Finite ``float64`` matrix of shape ``(dof, input_dim)``.
        """
        ...


__all__ = [
    "DEFAULT_STATE_TOLERANCE",
    "KinematicTransmissionRobotModel",
]
