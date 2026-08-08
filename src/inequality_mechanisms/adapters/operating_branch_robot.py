"""Wrap certified OperatingBranch as a Version 3 RobotModel."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from inequality_mechanisms.core.state import PhysicalState, Pose, StateCandidate
from inequality_mechanisms.mechanisms.operating_branch import (
    BranchInverseError,
    OperatingBranch,
)


@dataclass(frozen=True, slots=True)
class OperatingBranchRobotModel:
    """RobotModel adapter around a certified monotonic operating branch.

    Parameters
    ----------
    branch :
        Version 2 certified operating branch.
    planar_fk :
        Optional planar FK exposing ``forward`` / ``jacobian``. When the object
        also provides ``forward_pose``, orientation is attached to the returned
        ``Pose``. When omitted, FK raises ``NotImplementedError``.
    """

    branch: OperatingBranch
    planar_fk: Any | None = None

    @property
    def dof(self) -> int:
        """Output degrees of freedom."""
        return int(self.branch.mechanism.output_dim)

    def _canonical_assembly(self) -> dict[str, Any]:
        return {
            "mechanism_name": self.branch.mechanism.name,
            "branch_id": self.branch.branch_id,
        }

    def state_from_input(
        self,
        u: ArrayLike,
        assembly_state: Mapping[str, Any] | None = None,
    ) -> PhysicalState:
        """Build a consistent physical state from actuator coordinates."""
        u_arr = np.asarray(u, dtype=np.float64)
        q = np.asarray(self.branch.forward(u_arr), dtype=np.float64)
        assembly = (
            dict(assembly_state)
            if assembly_state is not None
            else self._canonical_assembly()
        )
        return PhysicalState(u=u_arr, q=q, assembly_state=assembly)

    def states_from_output(self, q: ArrayLike) -> Sequence[StateCandidate]:
        """Return the unique monotonic inverse candidate for ``q``."""
        q_arr = np.asarray(q, dtype=np.float64)
        try:
            u = np.asarray(self.branch.inverse(q_arr), dtype=np.float64)
        except BranchInverseError:
            return ()
        q_fwd = np.asarray(self.branch.forward(u), dtype=np.float64)
        residual = float(
            np.linalg.norm(q_fwd - self.branch.output_space.canonicalize(q_arr))
        )
        state = PhysicalState(
            u=u,
            q=q_fwd,
            assembly_state=self._canonical_assembly(),
        )
        return (
            StateCandidate(
                state=state,
                residual=residual,
                provenance={"inverse": "operating_branch.unique"},
            ),
        )

    def validate_state(self, state: PhysicalState, tolerance: float) -> bool:
        """Return True when ``||q - g(u)|| <= tolerance``."""
        try:
            q_fwd = np.asarray(self.branch.forward(state.u), dtype=np.float64)
        except (ValueError, BranchInverseError):
            return False
        return float(np.linalg.norm(state.q - q_fwd)) <= float(tolerance)

    def forward_kinematics(self, state: PhysicalState) -> Pose:
        """Return planar tip pose when FK is configured."""
        if self.planar_fk is None:
            raise NotImplementedError(
                "OperatingBranchRobotModel requires planar_fk for forward_kinematics"
            )
        expected = int(self.dof)
        if state.q.shape != (expected,):
            raise ValueError(
                f"planar FK requires q shape ({expected},), got {state.q.shape}"
            )
        fk = self.planar_fk
        if hasattr(fk, "forward_pose"):
            position, orientation = fk.forward_pose(state.q)
            return Pose(
                position=np.asarray(position, dtype=np.float64),
                orientation=np.asarray(orientation, dtype=np.float64),
            )
        return Pose(
            position=np.asarray(fk.forward(state.q), dtype=np.float64)
        )

    def jacobian_q_to_x(self, state: PhysicalState) -> NDArray[np.float64]:
        """Return planar FK Jacobian when configured."""
        if self.planar_fk is None:
            raise NotImplementedError(
                "OperatingBranchRobotModel requires planar_fk for jacobian_q_to_x"
            )
        return np.asarray(self.planar_fk.jacobian(state.q), dtype=np.float64)

    def state_within_limits(self, state: PhysicalState) -> bool:
        """Return True when ``u`` and ``q`` lie in the certified branch ranges."""
        cert = self.branch.certificate
        u = state.u
        q = state.q
        u_lo = np.asarray(cert.input_lower, dtype=np.float64)
        u_hi = np.asarray(cert.input_upper, dtype=np.float64)
        q_lo = np.asarray(cert.output_lower, dtype=np.float64)
        q_hi = np.asarray(cert.output_upper, dtype=np.float64)
        if u.shape != u_lo.shape or q.shape != q_lo.shape:
            return False
        return bool(
            np.all(u >= u_lo - 1e-9)
            and np.all(u <= u_hi + 1e-9)
            and np.all(q >= q_lo - 1e-9)
            and np.all(q <= q_hi + 1e-9)
        )
