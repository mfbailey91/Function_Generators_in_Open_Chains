"""Version 3 robot model protocol (ADR-021)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol, runtime_checkable

from numpy.typing import ArrayLike

from inequality_mechanisms.core.input_domain import InputDomain
from inequality_mechanisms.core.state import PhysicalState, Pose, StateCandidate


@runtime_checkable
class RobotModel(Protocol):
    """Mechanism-aware robot model that certifies physical states."""

    @property
    def dof(self) -> int:
        """Number of output degrees of freedom."""

    @property
    def input_domain(self) -> InputDomain:
        """Robot-owned actuator sampling domain."""

    def state_from_input(
        self,
        u: ArrayLike,
        assembly_state: Mapping[str, Any] | None = None,
    ) -> PhysicalState:
        """Build a consistent physical state from actuator coordinates."""

    def states_from_output(self, q: ArrayLike) -> Sequence[StateCandidate]:
        """Return physical candidates realizing output ``q``."""

    def validate_state(self, state: PhysicalState, tolerance: float) -> bool:
        """Return True when redundant coordinates agree within ``tolerance``."""

    def forward_kinematics(self, state: PhysicalState) -> Pose:
        """Return task-space pose for ``state``."""

    def jacobian_q_to_x(self, state: PhysicalState) -> Any:
        """Return the Jacobian of forward kinematics w.r.t. ``q``."""

    def state_within_limits(self, state: PhysicalState) -> bool:
        """Return True when ``state`` lies inside declared joint/mechanism limits."""
