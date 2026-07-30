"""Sampling provenance records for Version 2 embedded planning graphs.

ADR-015 requires that "how nodes were sampled" be tracked separately from
node identity, adjacency, and edge parameterization. This module owns that
provenance: which domain (``U`` or ``Q``) supplied the axis lattice, which
transition parameterization an edge should use, and the concrete
per-axis bounds/shape/endpoint policy a sampler used (Sprint V2.3, V2-301).

This module owns no mechanism or topology semantics; it is pure data plus
a small spacing-statistics helper shared by the uniform-input and
uniform-output samplers (V2-302 / V2-303).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray


class SamplingDomain(str, Enum):
    """Which coordinate domain supplied the per-axis lattice samples.

    Per ADR-015, this describes *how nodes were placed*, not an alternate
    planning-state space: Version 2 planning identity is always ``Q``
    (ADR-014).
    """

    INPUT = "input"
    OUTPUT = "output"


class TransitionParameterization(str, Enum):
    """How an edge between two nodes is parameterized for tracing/costing.

    ``INPUT_LINEAR`` interpolates ``u`` and recovers ``q = g(u)``;
    ``OUTPUT_LINEAR`` interpolates ``q`` and recovers ``u = g^{-1}(q)``
    (ADR-015).
    """

    INPUT_LINEAR = "input_linear"
    OUTPUT_LINEAR = "output_linear"


@dataclass(frozen=True, slots=True)
class SamplingSpecification:
    """Serializable record of how a lattice's axis samples were constructed.

    Attributes
    ----------
    domain :
        Coordinate domain the axis samples were drawn from.
    shape :
        Number of samples along each axis, ``(n_0, ..., n_{D-1})``.
    endpoint :
        Whether both endpoints of each axis interval were included
        (``np.linspace(..., endpoint=True)`` per the sprint contract; both
        samplers always use ``True``, recorded explicitly rather than
        assumed).
    axis_lower, axis_upper :
        Closed per-axis bounds used to build the ``linspace`` samples, in
        the coordinate domain named by ``domain`` (``u`` bounds for
        ``INPUT``, ``q`` bounds for ``OUTPUT``).
    """

    domain: SamplingDomain
    shape: tuple[int, ...]
    endpoint: bool
    axis_lower: tuple[float, ...]
    axis_upper: tuple[float, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "domain", SamplingDomain(self.domain))
        shape = tuple(int(n) for n in self.shape)
        lower = tuple(float(x) for x in self.axis_lower)
        upper = tuple(float(x) for x in self.axis_upper)
        if len(shape) < 1:
            raise ValueError("shape must have at least one axis")
        if any(n < 2 for n in shape):
            raise ValueError(f"shape entries must be >= 2, got {shape}")
        if len(lower) != len(shape) or len(upper) != len(shape):
            raise ValueError(
                "axis_lower/axis_upper must have the same length as shape, "
                f"got shape={shape}, axis_lower={lower}, axis_upper={upper}"
            )
        if not all(np.isfinite(x) for x in lower) or not all(
            np.isfinite(x) for x in upper
        ):
            raise ValueError("axis_lower/axis_upper must be finite")
        if any(hi <= lo for lo, hi in zip(lower, upper)):
            raise ValueError(
                f"axis_upper must exceed axis_lower on every axis, "
                f"got lower={lower}, upper={upper}"
            )
        object.__setattr__(self, "shape", shape)
        object.__setattr__(self, "axis_lower", lower)
        object.__setattr__(self, "axis_upper", upper)

    @property
    def ndim(self) -> int:
        """Number of sampled axes."""
        return len(self.shape)

    def axis_samples(self, axis: int) -> NDArray[np.float64]:
        """Return the ``linspace`` samples used to build axis ``axis``."""
        return np.linspace(
            self.axis_lower[axis],
            self.axis_upper[axis],
            self.shape[axis],
            endpoint=self.endpoint,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "domain": self.domain.value,
            "shape": list(self.shape),
            "endpoint": self.endpoint,
            "axis_lower": list(self.axis_lower),
            "axis_upper": list(self.axis_upper),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SamplingSpecification:
        """Deserialize from :meth:`to_dict` output."""
        return cls(
            domain=SamplingDomain(str(data["domain"])),
            shape=tuple(int(x) for x in data["shape"]),
            endpoint=bool(data["endpoint"]),
            axis_lower=tuple(float(x) for x in data["axis_lower"]),
            axis_upper=tuple(float(x) for x in data["axis_upper"]),
        )


@dataclass(frozen=True, slots=True)
class AxisSpacingStatistics:
    """Per-axis spacing statistics for a mapped 1-D marginal sample sequence.

    Spacing is the absolute difference between consecutive samples along
    one lattice axis, reported in whatever coordinate the caller supplied
    (mapped output spacing for uniform-input sampling, V2-302; mapped
    actuator spacing for uniform-output sampling, V2-303).

    Attributes
    ----------
    axis :
        Lattice axis index this statistic describes.
    minimum, maximum, mean, std :
        Minimum, maximum, mean, and population standard deviation of the
        per-step absolute spacing.
    max_to_min_ratio :
        ``maximum / minimum``. ``inf`` when the minimum spacing is exactly
        zero (degenerate axis).
    """

    axis: int
    minimum: float
    maximum: float
    mean: float
    std: float
    max_to_min_ratio: float

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "axis": self.axis,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "mean": self.mean,
            "std": self.std,
            "max_to_min_ratio": self.max_to_min_ratio,
        }


def compute_axis_spacing_statistics(
    samples: ArrayLike, *, axis: int
) -> AxisSpacingStatistics:
    """Compute spacing statistics for one axis' 1-D marginal sample sequence.

    Parameters
    ----------
    samples :
        1-D array of mapped coordinate values along one lattice axis
        (``shape[axis]`` entries), in sample order.
    axis :
        Lattice axis index recorded on the returned statistic.

    Returns
    -------
    AxisSpacingStatistics
        Minimum, maximum, mean, standard deviation, and max/min ratio of
        the absolute consecutive spacing.

    Raises
    ------
    ValueError
        If ``samples`` is not a finite 1-D array with at least two entries.
    """
    arr = np.asarray(samples, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError(f"samples must be 1-D, got shape {arr.shape}")
    if arr.shape[0] < 2:
        raise ValueError("samples must have at least two entries")
    if not np.all(np.isfinite(arr)):
        raise ValueError("samples must contain only finite values")
    spacing = np.abs(np.diff(arr))
    minimum = float(np.min(spacing))
    maximum = float(np.max(spacing))
    mean = float(np.mean(spacing))
    std = float(np.std(spacing))
    ratio = float(maximum / minimum) if minimum > 0.0 else float("inf")
    return AxisSpacingStatistics(
        axis=int(axis),
        minimum=minimum,
        maximum=maximum,
        mean=mean,
        std=std,
        max_to_min_ratio=ratio,
    )
