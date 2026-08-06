"""Version 3 path constraint set (ADR-021)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ConstraintSet:
    """Named path constraints attached to a planning problem.

    Version 3.1 ships an empty/default container. Concrete constraint
    evaluators arrive with later scene and manifold work.
    """

    names: tuple[str, ...] = ()
    parameters: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "names", tuple(self.names))
        object.__setattr__(self, "parameters", dict(self.parameters))

    def is_empty(self) -> bool:
        """Return True when no named constraints are present."""
        return len(self.names) == 0

    @classmethod
    def empty(cls) -> ConstraintSet:
        """Return an empty constraint set."""
        return cls()

    def extend(self, names: Sequence[str]) -> ConstraintSet:
        """Return a copy with additional constraint names."""
        return ConstraintSet(
            names=self.names + tuple(names),
            parameters=self.parameters,
        )
