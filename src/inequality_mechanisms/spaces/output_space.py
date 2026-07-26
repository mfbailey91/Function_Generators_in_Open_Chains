"""Shared output configuration space Q (ADR-011).

Sprint Two uses bounded lifted revolute coordinates. Mechanisms emit raw
forward-map values; this module owns canonicalization, displacement,
distance, and bounds checks. The interface admits future periodic revolute
and prismatic axes without changing search identity in U.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray

_TWO_PI = 2.0 * np.pi


class AxisTopology(str, Enum):
    """Per-axis topology of an output configuration coordinate."""

    BOUNDED_REVOLUTE = "bounded_revolute"
    PERIODIC_REVOLUTE = "periodic_revolute"
    PRISMATIC = "prismatic"


def wrap_to_pi(angle: float) -> float:
    """Wrap an angle to ``(-pi, pi]``."""
    return float((angle + np.pi) % _TWO_PI - np.pi)


def lift_bounded_revolute(theta: float, q_min: float, q_max: float) -> float:
    """Lift a raw angle into the bounded revolute chart ``[q_min, q_max]``.

    Uses chart center ``q_c = (q_min + q_max) / 2`` and

    ``lift(theta) = q_c + wrap_{(-pi, pi]}(theta - q_c)``.

    Parameters
    ----------
    theta :
        Raw angle (radians), typically a principal-value Freudenstein solve.
    q_min, q_max :
        Closed chart bounds with ``0 < q_max - q_min < 2 pi``.

    Returns
    -------
    float
        Representative nearest the chart center (not clipped to the box).

    Raises
    ------
    ValueError
        If the span is not strictly inside ``(0, 2 pi)`` or values are
        non-finite.
    """
    if not np.isfinite(theta):
        raise ValueError(f"theta must be finite, got {theta}")
    if not np.isfinite(q_min) or not np.isfinite(q_max):
        raise ValueError("q_min and q_max must be finite")
    span = float(q_max - q_min)
    if not (0.0 < span < _TWO_PI):
        raise ValueError(
            f"bounded revolute span must satisfy 0 < q_max - q_min < 2 pi, "
            f"got {span}"
        )
    q_c = 0.5 * (float(q_min) + float(q_max))
    return q_c + wrap_to_pi(float(theta) - q_c)


@dataclass(frozen=True, slots=True)
class OutputAxis:
    """One output coordinate with topology and optional bounds.

    Parameters
    ----------
    topology :
        Axis type. Version 1 experiments use ``BOUNDED_REVOLUTE`` only.
    lower, upper :
        Closed bounds. Required for bounded revolute and prismatic axes.
        Ignored for periodic revolute until that type is implemented.
    """

    topology: AxisTopology
    lower: float | None = None
    upper: float | None = None

    def __post_init__(self) -> None:
        if self.topology is AxisTopology.BOUNDED_REVOLUTE:
            if self.lower is None or self.upper is None:
                raise ValueError("bounded revolute axes require lower and upper")
            lo = float(self.lower)
            hi = float(self.upper)
            if not np.isfinite(lo) or not np.isfinite(hi):
                raise ValueError("bounded revolute bounds must be finite")
            span = hi - lo
            if not (0.0 < span < _TWO_PI):
                raise ValueError(
                    "bounded revolute requires 0 < upper - lower < 2 pi, "
                    f"got span {span}"
                )
            object.__setattr__(self, "lower", lo)
            object.__setattr__(self, "upper", hi)
        elif self.topology is AxisTopology.PRISMATIC:
            if self.lower is None or self.upper is None:
                raise ValueError("prismatic axes require lower and upper")
            lo = float(self.lower)
            hi = float(self.upper)
            if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
                raise ValueError("prismatic requires finite lower < upper")
            object.__setattr__(self, "lower", lo)
            object.__setattr__(self, "upper", hi)
        elif self.topology is AxisTopology.PERIODIC_REVOLUTE:
            # Future: full S^1 factor. Bounds optional / unused in V1.
            pass
        else:  # pragma: no cover
            raise ValueError(f"unknown axis topology: {self.topology!r}")

    @property
    def chart_center(self) -> float:
        """Midpoint of the bounded chart (bounded revolute / prismatic)."""
        if self.lower is None or self.upper is None:
            raise ValueError(f"axis {self.topology} has no chart center")
        return 0.5 * (float(self.lower) + float(self.upper))

    def canonicalize(self, value: float) -> float:
        """Map a raw coordinate into this axis chart."""
        if not np.isfinite(value):
            raise ValueError(f"coordinate must be finite, got {value}")
        if self.topology is AxisTopology.BOUNDED_REVOLUTE:
            assert self.lower is not None and self.upper is not None
            return lift_bounded_revolute(value, self.lower, self.upper)
        if self.topology is AxisTopology.PRISMATIC:
            return float(value)
        if self.topology is AxisTopology.PERIODIC_REVOLUTE:
            raise NotImplementedError(
                "periodic revolute output axes are not implemented in Version 1"
            )
        raise ValueError(f"unknown axis topology: {self.topology!r}")

    def contains(self, value: float) -> bool:
        """Return whether a *canonicalized* coordinate lies in closed bounds."""
        if self.topology is AxisTopology.PERIODIC_REVOLUTE:
            raise NotImplementedError(
                "periodic revolute output axes are not implemented in Version 1"
            )
        if self.lower is None or self.upper is None:
            raise ValueError(f"axis {self.topology} has no bounds for contains()")
        v = float(value)
        if not np.isfinite(v):
            raise ValueError("coordinate must be finite")
        return bool(self.lower <= v <= self.upper)

    def to_dict(self) -> dict[str, Any]:
        """Serialize this axis."""
        return {
            "topology": self.topology.value,
            "lower": self.lower,
            "upper": self.upper,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OutputAxis:
        """Deserialize an axis from ``to_dict`` output."""
        return cls(
            topology=AxisTopology(str(data["topology"])),
            lower=data.get("lower"),
            upper=data.get("upper"),
        )


@dataclass(frozen=True, slots=True)
class OutputSpace:
    """Product output configuration space with per-axis semantics.

    Parameters
    ----------
    axes :
        Non-empty sequence of ``OutputAxis`` factors.
    """

    axes: tuple[OutputAxis, ...]

    def __post_init__(self) -> None:
        if len(self.axes) < 1:
            raise ValueError("OutputSpace requires at least one axis")
        object.__setattr__(self, "axes", tuple(self.axes))

    @classmethod
    def bounded_revolute_box(
        cls,
        lower: ArrayLike,
        upper: ArrayLike,
    ) -> OutputSpace:
        """Build a product of bounded revolute axes from box bounds."""
        lo = np.asarray(lower, dtype=np.float64)
        hi = np.asarray(upper, dtype=np.float64)
        if lo.ndim != 1 or hi.ndim != 1:
            raise ValueError("lower and upper must be 1-D")
        if lo.shape != hi.shape:
            raise ValueError(
                f"lower and upper must have the same shape, got {lo.shape} and {hi.shape}"
            )
        if lo.size < 1:
            raise ValueError("lower and upper must be non-empty")
        axes = tuple(
            OutputAxis(
                topology=AxisTopology.BOUNDED_REVOLUTE,
                lower=float(lo[i]),
                upper=float(hi[i]),
            )
            for i in range(lo.shape[0])
        )
        return cls(axes=axes)

    @classmethod
    def from_limits(cls, limits: Any) -> OutputSpace:
        """Build an output space from ``OutputJointLimits``.

        Axes with ``0 < span < 2 pi`` become bounded revolute charts
        (Sprint Two default). Wider or full-period boxes become prismatic
        Euclidean axes so unit-gearbox lattice tests and non-angle boxes
        remain valid without inventing a circular metric.
        """
        lo = np.asarray(limits.lower, dtype=np.float64)
        hi = np.asarray(limits.upper, dtype=np.float64)
        axes: list[OutputAxis] = []
        for i in range(lo.shape[0]):
            span = float(hi[i] - lo[i])
            if 0.0 < span < _TWO_PI:
                axes.append(
                    OutputAxis(
                        topology=AxisTopology.BOUNDED_REVOLUTE,
                        lower=float(lo[i]),
                        upper=float(hi[i]),
                    )
                )
            else:
                axes.append(
                    OutputAxis(
                        topology=AxisTopology.PRISMATIC,
                        lower=float(lo[i]),
                        upper=float(hi[i]),
                    )
                )
        return cls(axes=tuple(axes))

    @property
    def dim(self) -> int:
        """Output dimension."""
        return len(self.axes)

    @property
    def lower(self) -> NDArray[np.floating]:
        """Per-axis lower bounds (bounded / prismatic only)."""
        vals: list[float] = []
        for axis in self.axes:
            if axis.lower is None:
                raise ValueError("axis missing lower bound")
            vals.append(float(axis.lower))
        return np.asarray(vals, dtype=np.float64)

    @property
    def upper(self) -> NDArray[np.floating]:
        """Per-axis upper bounds (bounded / prismatic only)."""
        vals: list[float] = []
        for axis in self.axes:
            if axis.upper is None:
                raise ValueError("axis missing upper bound")
            vals.append(float(axis.upper))
        return np.asarray(vals, dtype=np.float64)

    def _as_vector(self, q: ArrayLike, *, name: str) -> NDArray[np.floating]:
        arr = np.asarray(q, dtype=np.float64)
        if arr.ndim != 1:
            raise ValueError(f"{name} must be 1-D, got shape {arr.shape}")
        if arr.shape[0] != self.dim:
            raise ValueError(
                f"{name} must have length {self.dim}, got {arr.shape[0]}"
            )
        if not np.all(np.isfinite(arr)):
            raise ValueError(f"{name} must contain only finite values")
        return arr

    def canonicalize(self, q: ArrayLike) -> NDArray[np.floating]:
        """Lift / normalize raw output coordinates into this chart."""
        arr = self._as_vector(q, name="q")
        return np.asarray(
            [self.axes[i].canonicalize(float(arr[i])) for i in range(self.dim)],
            dtype=np.float64,
        )

    def displacement(self, q_from: ArrayLike, q_to: ArrayLike) -> NDArray[np.floating]:
        """Return ``canonicalize(q_to) - canonicalize(q_from)``."""
        a = self.canonicalize(q_from)
        b = self.canonicalize(q_to)
        return b - a

    def distance(self, q_from: ArrayLike, q_to: ArrayLike) -> float:
        """Return Euclidean norm of ``displacement(q_from, q_to)``."""
        return float(np.linalg.norm(self.displacement(q_from, q_to)))

    def contains(self, q: ArrayLike) -> bool:
        """Return whether canonicalized ``q`` lies in the closed product box."""
        canon = self.canonicalize(q)
        return all(self.axes[i].contains(float(canon[i])) for i in range(self.dim))

    def to_dict(self) -> dict[str, Any]:
        """Serialize axis types and bounds."""
        return {"axes": [axis.to_dict() for axis in self.axes]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OutputSpace:
        """Deserialize from ``to_dict`` output."""
        raw_axes: Sequence[dict[str, Any]] = data["axes"]
        return cls(axes=tuple(OutputAxis.from_dict(a) for a in raw_axes))
