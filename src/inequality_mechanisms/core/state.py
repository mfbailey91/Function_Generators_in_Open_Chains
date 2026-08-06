"""Version 3 physical state and pose types (ADR-021, ADR-022)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class Pose:
    """Task-space pose carrier for Version 3 kinematics.

    Parameters
    ----------
    position :
        Cartesian position, shape ``(2,)`` or ``(3,)``.
    orientation :
        Optional orientation parameters (planar angle, quaternion, etc.).
    frame_id :
        Optional frame label for multi-frame robots.
    """

    position: NDArray[np.float64]
    orientation: NDArray[np.float64] | None = None
    frame_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "position", np.asarray(self.position, dtype=np.float64).copy()
        )
        if self.orientation is not None:
            object.__setattr__(
                self,
                "orientation",
                np.asarray(self.orientation, dtype=np.float64).copy(),
            )


@dataclass(frozen=True, slots=True)
class PhysicalState:
    """Mechanism-aware physical state ``(u, q, assembly_state, ...)``.

    Callers must construct or certify states through a ``RobotModel`` so that
    redundant coordinates remain consistent (ADR-021).
    """

    u: NDArray[np.float64]
    q: NDArray[np.float64]
    assembly_state: Mapping[str, Any] = field(default_factory=dict)
    auxiliary_state: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "u", np.asarray(self.u, dtype=np.float64).copy())
        object.__setattr__(self, "q", np.asarray(self.q, dtype=np.float64).copy())
        object.__setattr__(self, "assembly_state", dict(self.assembly_state))
        object.__setattr__(self, "auxiliary_state", dict(self.auxiliary_state))
        if self.u.ndim != 1 or self.q.ndim != 1:
            raise ValueError("u and q must be 1-D vectors")
        if not np.all(np.isfinite(self.u)) or not np.all(np.isfinite(self.q)):
            raise ValueError("u and q must be finite")


@dataclass(frozen=True, slots=True)
class StateCandidate:
    """A physical-state candidate returned by inverse or goal generation."""

    state: PhysicalState
    residual: float
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "provenance", dict(self.provenance))
        if not np.isfinite(self.residual) or self.residual < 0.0:
            raise ValueError("residual must be finite and nonnegative")
