"""Wrap certified OperatingBranch as a Version 3 RobotModel."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from inequality_mechanisms.core.input_domain import InputDomain
from inequality_mechanisms.core.state import PhysicalState, Pose, StateCandidate
from inequality_mechanisms.mechanisms.operating_branch import (
    BranchInverseError,
    OperatingBranch,
)
from inequality_mechanisms.transmission_geometry.protocols import (
    DEFAULT_STATE_TOLERANCE,
)


@dataclass(frozen=True, slots=True)
class OperatingBranchRobotModel:
    """RobotModel adapter around a certified monotonic operating branch.

    Parameters
    ----------
    branch :
        Version 2 certified operating branch.
    kinematic_model :
        Optional ``KinematicModel`` exposing ``forward`` / ``jacobian`` and
        ``dof``. When the object also provides ``forward_pose``, orientation is
        attached to the returned ``Pose``. When omitted, FK raises
        ``NotImplementedError``.
    """

    branch: OperatingBranch
    kinematic_model: Any | None = None

    def __post_init__(self) -> None:
        if self.kinematic_model is None:
            return
        model_dof = int(self.kinematic_model.dof)
        branch_dof = int(self.branch.mechanism.output_dim)
        if model_dof != branch_dof:
            raise ValueError(
                "kinematic_model.dof must match branch output_dim: "
                f"got model_dof={model_dof}, output_dim={branch_dof}"
            )

    @property
    def planar_fk(self) -> Any | None:
        """Compatibility alias for ``kinematic_model``."""
        return self.kinematic_model

    @property
    def dof(self) -> int:
        """Output degrees of freedom."""
        return int(self.branch.mechanism.output_dim)

    @property
    def input_domain(self) -> InputDomain:
        """Certified actuator box from the operating-branch certificate."""
        cert = self.branch.certificate
        lo = np.asarray(cert.input_lower, dtype=np.float64)
        hi = np.asarray(cert.input_upper, dtype=np.float64)
        return InputDomain(
            lower=lo,
            upper=hi,
            periodic=tuple(False for _ in range(lo.shape[0])),
        )

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
        """Return tip pose when a kinematic model is configured."""
        if self.kinematic_model is None:
            raise NotImplementedError(
                "OperatingBranchRobotModel requires kinematic_model "
                "for forward_kinematics"
            )
        expected = int(self.dof)
        if state.q.shape != (expected,):
            raise ValueError(
                f"FK requires q shape ({expected},), got {state.q.shape}"
            )
        fk = self.kinematic_model
        if hasattr(fk, "forward_pose"):
            position, orientation = fk.forward_pose(state.q)
            return Pose(
                position=np.asarray(position, dtype=np.float64),
                orientation=np.asarray(orientation, dtype=np.float64),
            )
        return Pose(position=np.asarray(fk.forward(state.q), dtype=np.float64))

    def jacobian_q_to_x(self, state: PhysicalState) -> NDArray[np.float64]:
        """Return tip Jacobian when a kinematic model is configured."""
        if self.kinematic_model is None:
            raise NotImplementedError(
                "OperatingBranchRobotModel requires kinematic_model "
                "for jacobian_q_to_x"
            )
        return np.asarray(self.kinematic_model.jacobian(state.q), dtype=np.float64)

    def jacobian_u_to_q(self, state: PhysicalState) -> NDArray[np.float64]:
        """Return the transmission Jacobian ``J_g = dq/du`` at ``state``.

        Parameters
        ----------
        state :
            Certified physical state on this operating branch.

        Returns
        -------
        ndarray
            New finite ``float64`` matrix of shape ``(dof, input_dim)``.

        Raises
        ------
        ValueError
            If ``state`` has the wrong dimension, is inconsistent with
            ``g(u)``, or lies outside the certified branch.
        """
        input_dim = int(self.branch.mechanism.input_dim)
        output_dim = int(self.dof)
        if state.u.shape != (input_dim,):
            raise ValueError(
                f"jacobian_u_to_q requires u shape ({input_dim},), "
                f"got {state.u.shape}"
            )
        if state.q.shape != (output_dim,):
            raise ValueError(
                f"jacobian_u_to_q requires q shape ({output_dim},), "
                f"got {state.q.shape}"
            )
        if not self.validate_state(state, DEFAULT_STATE_TOLERANCE):
            raise ValueError(
                "state is inconsistent with the transmission map g(u)"
            )
        if not self.state_within_limits(state):
            raise ValueError("state is outside the certified operating branch")
        j_g = np.array(
            self.branch.jacobian(state.u),
            dtype=np.float64,
            copy=True,
        )
        if j_g.shape != (output_dim, input_dim):
            raise ValueError(
                "branch.jacobian must return shape "
                f"({output_dim}, {input_dim}), got {j_g.shape}"
            )
        if not np.all(np.isfinite(j_g)):
            raise ValueError("branch.jacobian must return a finite matrix")
        return j_g

    def state_within_limits(self, state: PhysicalState) -> bool:
        """Return True when ``u`` and ``q`` lie in the certified branch ranges."""
        domain = self.input_domain
        cert = self.branch.certificate
        u = state.u
        q = state.q
        q_lo = np.asarray(cert.output_lower, dtype=np.float64)
        q_hi = np.asarray(cert.output_upper, dtype=np.float64)
        if u.shape != domain.lower.shape or q.shape != q_lo.shape:
            return False
        return bool(
            np.all(u >= domain.lower - 1e-9)
            and np.all(u <= domain.upper + 1e-9)
            and np.all(q >= q_lo - 1e-9)
            and np.all(q <= q_hi + 1e-9)
        )
