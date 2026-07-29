"""Monotonic-branch helpers for Sprint Four Q-grid control (S4-11).

These utilities restrict a four-bar to a one-to-one crank sector so a
regular output lattice can attach a unique inverse ``u = g^{-1}(q)``.
They are experimental-control tools, not a replacement for ADR-001
input-space state identity.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from inequality_mechanisms.mechanisms.fourbar import IndependentFourBars, PlanarFourBar

_TWO_PI = 2.0 * np.pi


@dataclass(frozen=True, slots=True)
class MonotonicSector:
    """One injective crank sector of a planar four-bar.

    Attributes
    ----------
    u_lo, u_hi :
        Inclusive crank interval on ``[0, 2 pi)`` (may wrap conceptually
        only if ``u_hi < u_lo``; Version 1 sectors are non-wrapping).
    q_lo, q_hi :
        Continuous follower image of that crank interval (unwrapped).
    sign :
        Sign of ``dq/du`` on the sector (``+1`` or ``-1``).
    """

    u_lo: float
    u_hi: float
    q_lo: float
    q_hi: float
    sign: int

    @property
    def u_width(self) -> float:
        """Length of the crank interval."""
        return float(self.u_hi - self.u_lo)

    @property
    def q_width(self) -> float:
        """Width of the follower image."""
        return float(self.q_hi - self.q_lo)


def _wrap_to_two_pi(x: float) -> float:
    return float(x % _TWO_PI)


def find_monotonic_sectors(
    bar: PlanarFourBar,
    *,
    n_samples: int = 361,
    min_abs_gain: float = 0.05,
    min_u_width: float = 0.3,
) -> list[MonotonicSector]:
    """Find contiguous crank sectors with constant-sign finite gain.

    Parameters
    ----------
    bar :
        Planar four-bar on a fixed algebraic branch.
    n_samples :
        Dense crank samples on ``[0, 2 pi)``.
    min_abs_gain :
        Require ``|dq/du| >= min_abs_gain`` (away from rocker extrema /
        change points).
    min_u_width :
        Discard sectors shorter than this crank width.

    Returns
    -------
    list of MonotonicSector
        Non-wrapping sectors sorted by decreasing ``u_width``.
    """
    if not isinstance(bar, PlanarFourBar):
        raise TypeError("bar must be a PlanarFourBar")
    if int(n_samples) < 16:
        raise ValueError(f"n_samples must be >= 16, got {n_samples}")
    if float(min_abs_gain) <= 0.0:
        raise ValueError("min_abs_gain must be positive")

    u = np.linspace(0.0, _TWO_PI, int(n_samples), endpoint=False)
    qs = bar.follower_curve(u, unwrap=True)
    ratios = np.empty(u.shape[0], dtype=np.float64)
    ok = np.zeros(u.shape[0], dtype=bool)
    for i, uu in enumerate(u):
        try:
            r = float(bar.output_jacobian([float(uu)])[0, 0])
        except ValueError:
            ratios[i] = np.nan
            continue
        ratios[i] = r
        ok[i] = np.isfinite(r) and abs(r) >= float(min_abs_gain)

    sectors: list[MonotonicSector] = []
    i = 0
    n = int(u.shape[0])
    while i < n:
        if not ok[i]:
            i += 1
            continue
        sign = 1 if ratios[i] > 0.0 else -1
        j = i
        while j + 1 < n and ok[j + 1]:
            s2 = 1 if ratios[j + 1] > 0.0 else -1
            if s2 != sign:
                break
            j += 1
        u_lo = float(u[i])
        u_hi = float(u[j])
        # Include one sample step so the closed interval covers the last point.
        step = float(u[1] - u[0]) if n > 1 else 0.0
        u_hi_closed = min(_TWO_PI - 1e-12, u_hi + step)
        q_seg = qs[i : j + 1]
        q_lo = float(np.min(q_seg))
        q_hi = float(np.max(q_seg))
        width = u_hi_closed - u_lo
        if width >= float(min_u_width) and (q_hi - q_lo) > 1e-9:
            sectors.append(
                MonotonicSector(
                    u_lo=u_lo,
                    u_hi=u_hi_closed,
                    q_lo=q_lo,
                    q_hi=q_hi,
                    sign=int(sign),
                )
            )
        i = j + 1

    sectors.sort(key=lambda s: s.u_width, reverse=True)
    return sectors


def primary_monotonic_sector(
    bar: PlanarFourBar,
    *,
    n_samples: int = 361,
    min_abs_gain: float = 0.05,
    min_u_width: float = 0.3,
) -> MonotonicSector:
    """Return the longest monotonic sector, or raise if none exist."""
    sectors = find_monotonic_sectors(
        bar,
        n_samples=n_samples,
        min_abs_gain=min_abs_gain,
        min_u_width=min_u_width,
    )
    if not sectors:
        raise ValueError("no monotonic sector found for four-bar")
    return sectors[0]


@dataclass(frozen=True, slots=True)
class MonotonicBox2D:
    """Product of per-axis monotonic sectors for ``IndependentFourBars``."""

    sectors: tuple[MonotonicSector, MonotonicSector]

    @property
    def u_ranges(self) -> tuple[tuple[float, float], tuple[float, float]]:
        """Crank box ``((u0_lo, u0_hi), (u1_lo, u1_hi))``."""
        s0, s1 = self.sectors
        return (s0.u_lo, s0.u_hi), (s1.u_lo, s1.u_hi)

    @property
    def q_ranges(self) -> tuple[tuple[float, float], tuple[float, float]]:
        """Follower-image box ``((q0_lo, q0_hi), (q1_lo, q1_hi))``."""
        s0, s1 = self.sectors
        return (s0.q_lo, s0.q_hi), (s1.q_lo, s1.q_hi)


def monotonic_box_for_independent_fourbars(
    mech: IndependentFourBars,
    *,
    n_samples: int = 361,
    min_abs_gain: float = 0.05,
    min_u_width: float = 0.3,
) -> MonotonicBox2D:
    """Build a 2-D monotonic box from per-axis primary sectors."""
    if not isinstance(mech, IndependentFourBars):
        raise TypeError("mech must be IndependentFourBars")
    if mech.input_dim != 2:
        raise ValueError("Version 1 control requires input_dim == 2")
    sectors = tuple(
        primary_monotonic_sector(
            bar,
            n_samples=n_samples,
            min_abs_gain=min_abs_gain,
            min_u_width=min_u_width,
        )
        for bar in mech.bars
    )
    return MonotonicBox2D(sectors=sectors)  # type: ignore[arg-type]


def open_axis_independent_fourbars(mech: IndependentFourBars) -> IndependentFourBars:
    """Return a kinematics-equivalent copy with non-periodic crank axes.

    Used by the monotonic U/Q control so edge interpolation stays inside the
    open sector box (``wrap=(False, False)``).
    """
    if not isinstance(mech, IndependentFourBars):
        raise TypeError("mech must be IndependentFourBars")
    bars = [
        PlanarFourBar(
            *bar.lengths,
            branch=int(bar.branch),
            periodic=(False,),
            name=str(bar.name),
        )
        for bar in mech.bars
    ]
    return IndependentFourBars(bars, name=f"{mech.name}_open")


def _in_u_interval(u: float, lo: float, hi: float, *, atol: float = 1e-9) -> bool:
    return float(lo) - atol <= float(u) <= float(hi) + atol


def unique_inverse_output(
    mech: IndependentFourBars,
    q: ArrayLike,
    *,
    u_ranges: tuple[tuple[float, float], tuple[float, float]],
    atol: float = 1e-8,
) -> NDArray[np.floating]:
    """Return the unique crank preimage of ``q`` inside ``u_ranges``.

    Parameters
    ----------
    mech :
        Independent four-bars.
    q :
        Output configuration, shape ``(2,)``.
    u_ranges :
        Allowed crank box (monotonic sector product).
    atol :
        Angle agreement tolerance when verifying ``g(u) ≈ q``.

    Returns
    -------
    ndarray
        Unique ``u``, shape ``(2,)``.

    Raises
    ------
    ValueError
        If zero or multiple preimages lie in the box.
    """
    q_vec = np.asarray(q, dtype=np.float64).reshape(-1)
    if q_vec.shape != (2,):
        raise ValueError(f"q must have shape (2,), got {q_vec.shape}")

    # Per-axis candidates filtered to the monotonic interval, then product.
    per_axis: list[list[float]] = []
    for axis, bar in enumerate(mech.bars):
        lo, hi = u_ranges[axis]
        opts = []
        for u1 in bar.inverse_output([float(q_vec[axis])]):
            uu = float(np.asarray(u1, dtype=np.float64).reshape(-1)[0])
            uu = _wrap_to_two_pi(uu)
            if _in_u_interval(uu, lo, hi):
                opts.append(uu)
        # Deduplicate.
        uniq: list[float] = []
        for uu in opts:
            if not any(abs(uu - v) <= 1e-10 for v in uniq):
                uniq.append(uu)
        per_axis.append(uniq)

    if any(len(opts) == 0 for opts in per_axis):
        raise ValueError(f"no inverse of q={q_vec} inside u_ranges={u_ranges}")
    if any(len(opts) > 1 for opts in per_axis):
        raise ValueError(
            f"non-unique inverse of q={q_vec} inside u_ranges={u_ranges}: "
            f"counts={[len(o) for o in per_axis]}"
        )

    u = np.array([per_axis[0][0], per_axis[1][0]], dtype=np.float64)
    q_fwd = np.asarray(mech.input_to_output(u), dtype=np.float64)
    # Compare in a lifted sense on the sector image: use absolute difference
    # after choosing the nearest 2-pi sheet to the requested q.
    for i in range(2):
        delta = float(q_fwd[i] - q_vec[i])
        delta = (delta + np.pi) % _TWO_PI - np.pi
        if abs(delta) > float(atol):
            raise ValueError(
                f"inverse verification failed at axis {i}: "
                f"g(u)={q_fwd[i]} vs q={q_vec[i]}"
            )
    return u
