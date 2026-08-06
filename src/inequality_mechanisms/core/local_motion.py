"""Version 3 local motion types (ADR-021, ADR-024)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import numpy as np

from inequality_mechanisms.core.robot import RobotModel
from inequality_mechanisms.core.state import PhysicalState


@dataclass(frozen=True, slots=True)
class LocalMotion:
    """Continuous motion with declared endpoints.

    Parameterization is model-specific and stored in ``parameters``.
    """

    start: PhysicalState
    end: PhysicalState
    model_id: str
    parameters: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.model_id:
            raise ValueError("model_id must be nonempty")
        object.__setattr__(self, "parameters", dict(self.parameters))


@runtime_checkable
class LocalMotionModel(Protocol):
    """Connector that produces a continuous local motion or None."""

    def connect(
        self,
        start: PhysicalState,
        end: PhysicalState,
    ) -> LocalMotion | None:
        """Return a local motion from ``start`` to ``end``, or None if rejected."""


@dataclass(frozen=True, slots=True)
class EndpointDeclaredMotion:
    """Minimal connector that records endpoints without interpolating.

    Used by graph-search adapters where edge geometry is owned by the
    discrete graph objective rather than a continuous interpolant.
    """

    model_id: str = "endpoint_declared"

    def connect(
        self,
        start: PhysicalState,
        end: PhysicalState,
    ) -> LocalMotion | None:
        """Return an endpoint-declared motion."""
        return LocalMotion(start=start, end=end, model_id=self.model_id)


def _polyline_length(samples: np.ndarray) -> float:
    if samples.shape[0] < 2:
        return 0.0
    diffs = np.diff(samples, axis=0)
    return float(np.sum(np.linalg.norm(diffs, axis=1)))


@dataclass(frozen=True, slots=True)
class OutputLinearMotion:
    """Output-linear connector ``q(t)=(1-t)q_a+t q_b`` lifted by unique inverse.

    Actuator cost is the numerically integrated arc length ``∫||du/dt|| dt``
    along the lifted samples. Endpoint ``||u_b-u_a||`` is only a lower bound
    for nonlinear maps (ADR-024).
    """

    robot: RobotModel
    model_id: str = "output_linear_v1"
    n_samples: int = 64
    endpoint_tolerance: float = 1e-8

    def __post_init__(self) -> None:
        if self.n_samples < 2:
            raise ValueError("n_samples must be >= 2")

    def connect(
        self,
        start: PhysicalState,
        end: PhysicalState,
    ) -> LocalMotion | None:
        """Lift a straight segment in ``q`` through ``states_from_output``."""
        if start.q.shape != end.q.shape:
            return None
        ts = np.linspace(0.0, 1.0, self.n_samples, dtype=np.float64)
        sample_q = np.empty((self.n_samples, start.q.shape[0]), dtype=np.float64)
        sample_u = np.empty((self.n_samples, start.u.shape[0]), dtype=np.float64)
        for i, t in enumerate(ts):
            q_t = (1.0 - t) * start.q + t * end.q
            cands = self.robot.states_from_output(q_t)
            if len(cands) != 1:
                return None
            lifted = cands[0].state
            if not self.robot.validate_state(lifted, self.endpoint_tolerance):
                return None
            sample_q[i] = lifted.q
            sample_u[i] = lifted.u
        if float(np.linalg.norm(sample_u[0] - start.u)) > self.endpoint_tolerance:
            return None
        if float(np.linalg.norm(sample_u[-1] - end.u)) > self.endpoint_tolerance:
            return None
        actuator_length = _polyline_length(sample_u)
        endpoint_lower = float(np.linalg.norm(end.u - start.u))
        return LocalMotion(
            start=start,
            end=end,
            model_id=self.model_id,
            parameters={
                "actuator_path_length": actuator_length,
                "endpoint_actuator_lower_bound": endpoint_lower,
                "sample_u": sample_u,
                "sample_q": sample_q,
                "n_samples": int(self.n_samples),
            },
        )


@dataclass(frozen=True, slots=True)
class InputLinearMotion:
    """Input-linear connector ``u(t)=(1-t)u_a+t u_b`` with ``q=g(u)``.

    Under Euclidean actuator length the cost is exact ``||u_b-u_a||_2``
    (ADR-024).
    """

    robot: RobotModel
    model_id: str = "input_linear_v1"
    n_samples: int = 64
    endpoint_tolerance: float = 1e-8

    def __post_init__(self) -> None:
        if self.n_samples < 2:
            raise ValueError("n_samples must be >= 2")

    def connect(
        self,
        start: PhysicalState,
        end: PhysicalState,
    ) -> LocalMotion | None:
        """Build a straight segment in ``u`` and reconstruct ``q`` via FK map."""
        if start.u.shape != end.u.shape:
            return None
        if not self.robot.validate_state(start, self.endpoint_tolerance):
            return None
        if not self.robot.validate_state(end, self.endpoint_tolerance):
            return None
        ts = np.linspace(0.0, 1.0, self.n_samples, dtype=np.float64)
        sample_q = np.empty((self.n_samples, start.q.shape[0]), dtype=np.float64)
        sample_u = np.empty((self.n_samples, start.u.shape[0]), dtype=np.float64)
        for i, t in enumerate(ts):
            u_t = (1.0 - t) * start.u + t * end.u
            state = self.robot.state_from_input(
                u_t, assembly_state=start.assembly_state
            )
            if not self.robot.validate_state(state, self.endpoint_tolerance):
                return None
            sample_u[i] = state.u
            sample_q[i] = state.q
        if float(np.linalg.norm(sample_q[-1] - end.q)) > self.endpoint_tolerance:
            return None
        actuator_length = float(np.linalg.norm(end.u - start.u))
        return LocalMotion(
            start=start,
            end=end,
            model_id=self.model_id,
            parameters={
                "actuator_path_length": actuator_length,
                "endpoint_actuator_lower_bound": actuator_length,
                "sample_u": sample_u,
                "sample_q": sample_q,
                "n_samples": int(self.n_samples),
            },
        )
