"""Shared edge-validation traces for graph construction and diagnostics.

Validator decisions and the edge microscope must consume the same builder
(IM-046 / S3-07). Search identity remains in U; this module only records
raw and canonical outputs along short input segments.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray

from inequality_mechanisms.mechanisms.base import Mechanism
from inequality_mechanisms.spaces.limits import OutputJointLimits
from inequality_mechanisms.spaces.output_space import OutputSpace

_TWO_PI = 2.0 * np.pi
_DEFAULT_EDGE_SAMPLES = 17

InvalidReason = Literal["assembly", "limits"]


def winding_number(raw: float, canonical: float) -> int:
    """Return integer winding taking ``raw`` to ``canonical`` modulo ``2 pi``."""
    if not np.isfinite(raw) or not np.isfinite(canonical):
        raise ValueError("raw and canonical must be finite")
    return int(np.round((float(canonical) - float(raw)) / _TWO_PI))


def crossed_native_seam(raw: float, canonical: float, *, tol: float = 1e-9) -> bool:
    """Return whether chart lift applies a nonzero ``2 pi`` winding."""
    del tol
    return winding_number(raw, canonical) != 0


@dataclass(frozen=True, slots=True)
class EdgeSamplePoint:
    """One sample along a short input-space edge."""

    s: float
    u: tuple[float, ...]
    q_raw: tuple[float, ...] | None
    q_canonical: tuple[float, ...] | None
    windings: tuple[int, ...] | None
    assembly_valid: bool
    limits_valid: bool
    segment_cost_from_prev: float | None

    def to_dict(self) -> dict[str, Any]:
        """Serialize this sample."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class EdgeTrace:
    """Full validation / cost trace for one undirected lattice edge.

    Attributes
    ----------
    is_valid :
        Same decision as ``edge_is_valid`` / ``ConstrainedInputGraph.edge_is_valid``.
    first_invalid_index :
        Index into ``samples`` of the first failing sample, or ``None``.
    first_invalid_reason :
        ``\"assembly\"`` or ``\"limits\"`` when invalid.
    total_endpoint_cost :
        ``d_Q`` between endpoint configurations when both assemble; else ``None``.
    """

    u_a: tuple[float, ...]
    u_b: tuple[float, ...]
    n_samples: int
    periodic_axes: tuple[bool, ...]
    samples: tuple[EdgeSamplePoint, ...]
    is_valid: bool
    first_invalid_index: int | None
    first_invalid_reason: InvalidReason | None
    total_endpoint_cost: float | None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the full trace for experiment bundles."""
        return {
            "u_a": list(self.u_a),
            "u_b": list(self.u_b),
            "n_samples": self.n_samples,
            "periodic_axes": list(self.periodic_axes),
            "samples": [s.to_dict() for s in self.samples],
            "is_valid": self.is_valid,
            "first_invalid_index": self.first_invalid_index,
            "first_invalid_reason": self.first_invalid_reason,
            "total_endpoint_cost": self.total_endpoint_cost,
        }


def build_edge_trace(
    mechanism: Mechanism,
    limits: OutputJointLimits,
    u_a: ArrayLike,
    u_b: ArrayLike,
    *,
    n_samples: int = _DEFAULT_EDGE_SAMPLES,
    periodic_axes: tuple[bool, ...] | None = None,
    output_space: OutputSpace | None = None,
) -> EdgeTrace:
    """Build the shared edge sample trace used by validation and plots.

    Parameters
    ----------
    mechanism :
        Mechanism providing assembly and raw ``g``.
    limits :
        Shared output joint limits.
    u_a, u_b :
        Endpoint input configurations.
    n_samples :
        Inclusive sample count along the short input segment (``>= 2``).
    periodic_axes :
        Override for short-path wrapping; defaults to ``mechanism.periodic_axes()``.
    output_space :
        Shared chart; defaults to ``OutputSpace.from_limits(limits)``.

    Returns
    -------
    EdgeTrace
        Sample records, validity decision, and first failure metadata.
    """
    if n_samples < 2:
        raise ValueError(f"n_samples must be >= 2, got {n_samples}")
    # Local import avoids a circular dependency with validation.py.
    from inequality_mechanisms.graphs.validation import interpolate_input_segment

    if limits.dim != mechanism.output_dim:
        raise ValueError(
            f"limits.dim ({limits.dim}) must equal mechanism.output_dim "
            f"({mechanism.output_dim})"
        )
    space = OutputSpace.from_limits(limits) if output_space is None else output_space
    if space.dim != mechanism.output_dim:
        raise ValueError(
            f"output_space.dim ({space.dim}) must equal mechanism.output_dim "
            f"({mechanism.output_dim})"
        )
    axes = mechanism.periodic_axes() if periodic_axes is None else periodic_axes
    a = np.asarray(u_a, dtype=np.float64)
    b = np.asarray(u_b, dtype=np.float64)
    if a.ndim != 1 or b.ndim != 1 or a.shape != b.shape:
        raise ValueError("u_a and u_b must be finite 1-D arrays of equal shape")

    samples: list[EdgeSamplePoint] = []
    first_invalid_index: int | None = None
    first_invalid_reason: InvalidReason | None = None
    prev_raw: NDArray[np.floating] | None = None

    for k in range(n_samples):
        s = k / (n_samples - 1)
        u = interpolate_input_segment(a, b, s, periodic_axes=axes)
        assembly = bool(mechanism.valid_input(u))
        q_raw_t: tuple[float, ...] | None = None
        q_can_t: tuple[float, ...] | None = None
        windings_t: tuple[int, ...] | None = None
        limits_ok = False
        seg_cost: float | None = None

        if assembly:
            # Construction / trace helper: raw g before graph-owned output().
            q_raw = np.asarray(mechanism.input_to_output(u), dtype=np.float64)
            q_can = space.canonicalize(q_raw)
            q_raw_t = tuple(float(x) for x in q_raw)
            q_can_t = tuple(float(x) for x in q_can)
            windings_t = tuple(
                winding_number(float(q_raw[i]), float(q_can[i])) for i in range(space.dim)
            )
            limits_ok = bool(space.contains(q_raw))
            if prev_raw is not None:
                seg_cost = space.distance(prev_raw, q_raw)
            prev_raw = q_raw
        else:
            prev_raw = None

        if first_invalid_index is None:
            if not assembly:
                first_invalid_index = k
                first_invalid_reason = "assembly"
            elif not limits_ok:
                first_invalid_index = k
                first_invalid_reason = "limits"

        samples.append(
            EdgeSamplePoint(
                s=float(s),
                u=tuple(float(x) for x in u),
                q_raw=q_raw_t,
                q_canonical=q_can_t,
                windings=windings_t,
                assembly_valid=assembly,
                limits_valid=limits_ok,
                segment_cost_from_prev=seg_cost,
            )
        )

    is_valid = first_invalid_index is None
    endpoint_cost: float | None = None
    if samples[0].q_raw is not None and samples[-1].q_raw is not None:
        endpoint_cost = space.distance(
            np.asarray(samples[0].q_raw, dtype=np.float64),
            np.asarray(samples[-1].q_raw, dtype=np.float64),
        )

    return EdgeTrace(
        u_a=tuple(float(x) for x in a),
        u_b=tuple(float(x) for x in b),
        n_samples=int(n_samples),
        periodic_axes=tuple(bool(x) for x in axes),
        samples=tuple(samples),
        is_valid=is_valid,
        first_invalid_index=first_invalid_index,
        first_invalid_reason=first_invalid_reason,
        total_endpoint_cost=endpoint_cost,
    )
