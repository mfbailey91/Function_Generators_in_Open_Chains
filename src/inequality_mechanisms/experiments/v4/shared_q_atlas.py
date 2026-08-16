"""Deterministic shared-Q sample bank for the V4.1 atlas."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray


class SharedQDomainError(ValueError):
    """Raised when the inset grid would empty or invalidate the Q box."""

    failure_code = "q_domain_mismatch"


@dataclass(frozen=True, slots=True)
class SharedQSample:
    """One shared output sample with a stable integer-grid identifier."""

    q_sample_id: str
    grid_index: tuple[int, int]
    q: tuple[float, float]


@dataclass(frozen=True, slots=True)
class SharedQSampleBank:
    """Inset shared-Q grid reused by every atlas arm."""

    samples: tuple[SharedQSample, ...]
    shape: tuple[int, int]
    q_lower: tuple[float, float]
    q_upper: tuple[float, float]
    inset: tuple[float, float]
    inner_lower: tuple[float, float]
    inner_upper: tuple[float, float]

    def q_array(self) -> NDArray[np.float64]:
        """Return sample coordinates as shape ``(N, 2)``."""
        return np.asarray([sample.q for sample in self.samples], dtype=np.float64)


def q_sample_id(i: int, j: int) -> str:
    """Stable identifier from integer grid coordinates."""
    return f"q_{i:04d}_{j:04d}"


def build_shared_q_bank(
    q_lower: ArrayLike,
    q_upper: ArrayLike,
    *,
    shape: tuple[int, int],
    inset_fraction: float,
) -> SharedQSampleBank:
    """Build one inset shared-Q grid from a certified output box.

    Samples ``q`` first. Does not sample ``U``.
    """
    lo = np.asarray(q_lower, dtype=np.float64)
    hi = np.asarray(q_upper, dtype=np.float64)
    if lo.shape != (2,) or hi.shape != (2,):
        raise SharedQDomainError(
            f"Q box must be 2-D, got lower={lo.shape}, upper={hi.shape}"
        )
    if np.any(hi <= lo):
        raise SharedQDomainError("Q upper must exceed Q lower on every axis")
    n0, n1 = int(shape[0]), int(shape[1])
    span = hi - lo
    inset = inset_fraction * span
    inner_lo = lo + inset
    inner_hi = hi - inset
    if np.any(inner_hi <= inner_lo):
        raise SharedQDomainError(
            "configured inset emptied the certified output box: "
            f"lower={lo.tolist()}, upper={hi.tolist()}, inset={inset.tolist()}"
        )
    axis0 = np.linspace(float(inner_lo[0]), float(inner_hi[0]), n0)
    axis1 = np.linspace(float(inner_lo[1]), float(inner_hi[1]), n1)
    samples: list[SharedQSample] = []
    for i, q0 in enumerate(axis0):
        for j, q1 in enumerate(axis1):
            samples.append(
                SharedQSample(
                    q_sample_id=q_sample_id(i, j),
                    grid_index=(i, j),
                    q=(float(q0), float(q1)),
                )
            )
    return SharedQSampleBank(
        samples=tuple(samples),
        shape=(n0, n1),
        q_lower=(float(lo[0]), float(lo[1])),
        q_upper=(float(hi[0]), float(hi[1])),
        inset=(float(inset[0]), float(inset[1])),
        inner_lower=(float(inner_lo[0]), float(inner_lo[1])),
        inner_upper=(float(inner_hi[0]), float(inner_hi[1])),
    )
