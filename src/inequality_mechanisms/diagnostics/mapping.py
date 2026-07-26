"""Output-axis mapping diagnostics (IM-045 / S3-06)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from inequality_mechanisms.graphs.edge_trace import (
    crossed_native_seam,
    winding_number,
)
from inequality_mechanisms.spaces.output_space import OutputSpace


@dataclass(frozen=True, slots=True)
class AxisMappingDiagnostic:
    """Per-axis raw → canonical mapping record.

    Attributes
    ----------
    raw :
        Mechanism-native principal (or raw) angle.
    canonical :
        Chart-lifted coordinate, or ``None`` when assembly failed upstream.
    winding :
        Integer ``k`` with ``canonical ≈ raw + 2 pi k``, or ``None``.
    within_bounds :
        Whether the canonical value lies in the closed chart interval.
    crossed_native_seam :
        Whether the lift differs from the principal representative.
    """

    raw: float
    canonical: float | None
    winding: int | None
    within_bounds: bool
    crossed_native_seam: bool

    def to_dict(self) -> dict[str, Any]:
        """Serialize for experiment bundles."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class OutputMappingDiagnostic:
    """Vector diagnostic for one input configuration."""

    u: tuple[float, ...]
    assembly_valid: bool
    axes: tuple[AxisMappingDiagnostic, ...]

    def to_dict(self) -> dict[str, Any]:
        """Serialize for experiment bundles."""
        return {
            "u": list(self.u),
            "assembly_valid": self.assembly_valid,
            "axes": [a.to_dict() for a in self.axes],
        }


def inspect_raw_output(
    raw: ArrayLike,
    output_space: OutputSpace,
) -> tuple[AxisMappingDiagnostic, ...]:
    """Build per-axis diagnostics from a raw output vector."""
    arr = np.asarray(raw, dtype=np.float64)
    if arr.ndim != 1 or arr.shape[0] != output_space.dim:
        raise ValueError(
            f"raw must have shape ({output_space.dim},), got {arr.shape}"
        )
    axes: list[AxisMappingDiagnostic] = []
    for i, axis in enumerate(output_space.axes):
        r = float(arr[i])
        if not np.isfinite(r):
            axes.append(
                AxisMappingDiagnostic(
                    raw=r,
                    canonical=None,
                    winding=None,
                    within_bounds=False,
                    crossed_native_seam=False,
                )
            )
            continue
        c = float(axis.canonicalize(r))
        w = winding_number(r, c)
        axes.append(
            AxisMappingDiagnostic(
                raw=r,
                canonical=c,
                winding=w,
                within_bounds=bool(axis.contains(c)),
                crossed_native_seam=crossed_native_seam(r, c),
            )
        )
    return tuple(axes)


def mapping_curve(
    mechanism_raw_fn,
    output_space: OutputSpace,
    u_samples: ArrayLike,
    *,
    axis: int = 0,
) -> dict[str, NDArray[np.floating]]:
    """Evaluate raw / canonical / winding / dq_du along an actuator sample path.

    ``mechanism_raw_fn(u_scalar) -> float`` returns the raw output for ``axis``.
    """
    u = np.asarray(u_samples, dtype=np.float64)
    if u.ndim != 1:
        raise ValueError(f"u_samples must be 1-D, got {u.shape}")
    if axis < 0 or axis >= output_space.dim:
        raise ValueError(f"axis out of range: {axis}")
    out_axis = output_space.axes[axis]
    raw = np.empty(u.shape[0], dtype=np.float64)
    can = np.empty(u.shape[0], dtype=np.float64)
    wind = np.empty(u.shape[0], dtype=np.float64)
    for i, uu in enumerate(u):
        r = float(mechanism_raw_fn(float(uu)))
        c = float(out_axis.canonicalize(r))
        raw[i] = r
        can[i] = c
        wind[i] = float(winding_number(r, c))
    # Central differences on canonical curve (radians per radian of u).
    dq_du = np.gradient(can, u)
    return {
        "u": u,
        "raw": raw,
        "canonical": can,
        "winding": wind,
        "dq_du": dq_du,
        "q_min": np.full_like(u, float(out_axis.lower) if out_axis.lower is not None else np.nan),
        "q_max": np.full_like(u, float(out_axis.upper) if out_axis.upper is not None else np.nan),
    }
