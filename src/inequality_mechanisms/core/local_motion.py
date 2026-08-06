"""Version 3 local motion types (ADR-021, ADR-024)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

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
