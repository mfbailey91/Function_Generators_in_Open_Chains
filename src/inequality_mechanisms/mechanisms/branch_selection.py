"""Four-bar monotonic operating-branch selection (Sprint V2.2, V2-203).

Selects a certified, nonperiodic ``OperatingBranch`` from an existing
continuous four-bar follower curve. Reuses the candidate-interval search
from ``mechanisms.monotonic.find_monotonic_sectors`` (Sprint Four), but
produces a certified ``OperatingBranch`` with a deterministic branch-local
inverse rather than a bare ``MonotonicSector``.

The Freudenstein algebraic branch (``PlanarFourBar.branch``, ``+1``/``-1``)
is fixed at four-bar construction time and is not re-selected here; "one
fixed assembly mode" (ADR-014) refers to that existing choice.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from inequality_mechanisms.mechanisms.fourbar import IndependentFourBars, PlanarFourBar
from inequality_mechanisms.mechanisms.monotonic import (
    MonotonicSector,
    find_monotonic_sectors,
    open_axis_independent_fourbars,
)
from inequality_mechanisms.mechanisms.operating_branch import (
    BranchCertificationError,
    MonotoneTableAxisInverse,
    OperatingBranch,
    certify_branch,
)
from inequality_mechanisms.spaces.output_space import (
    AxisTopology,
    OutputAxis,
    OutputSpace,
)

_TWO_PI = 2.0 * np.pi


def _as_independent_fourbars(
    mech: PlanarFourBar | IndependentFourBars,
) -> IndependentFourBars:
    if isinstance(mech, IndependentFourBars):
        return mech
    if isinstance(mech, PlanarFourBar):
        return IndependentFourBars([mech], name=mech.name)
    raise TypeError(
        f"mech must be PlanarFourBar or IndependentFourBars, got {type(mech).__name__}"
    )


def _select_axis_interval(
    bar: PlanarFourBar,
    *,
    axis_index: int,
    u_interval: tuple[float, float] | None,
    n_samples: int,
    min_abs_gain: float,
    min_u_width: float,
    endpoint_margin_fraction: float,
    sector_choice: int,
) -> tuple[float, float]:
    """Return the shrunk crank interval ``(u_lo, u_hi)`` for one axis."""
    if u_interval is not None:
        u_lo, u_hi = float(u_interval[0]), float(u_interval[1])
        if not (u_hi > u_lo):
            raise ValueError(
                f"axis {axis_index}: require u_interval[1] > u_interval[0]"
            )
        return u_lo, u_hi

    sectors: list[MonotonicSector] = find_monotonic_sectors(
        bar, n_samples=n_samples, min_abs_gain=min_abs_gain, min_u_width=min_u_width
    )
    if not sectors:
        raise BranchCertificationError(
            f"axis {axis_index}: no monotonic candidate interval found "
            f"(min_abs_gain={min_abs_gain}, min_u_width={min_u_width})"
        )
    idx = int(sector_choice)
    if not (0 <= idx < len(sectors)):
        raise ValueError(
            f"axis {axis_index}: sector_choice={idx} out of range "
            f"[0, {len(sectors) - 1}]"
        )
    sector = sectors[idx]
    if not (0.0 <= endpoint_margin_fraction < 0.5):
        raise ValueError(
            f"endpoint_margin_fraction must be in [0, 0.5), got "
            f"{endpoint_margin_fraction}"
        )
    width = sector.u_hi - sector.u_lo
    margin = float(endpoint_margin_fraction) * width
    u_lo = sector.u_lo + margin
    u_hi = sector.u_hi - margin
    if not (u_hi > u_lo):
        raise BranchCertificationError(
            f"axis {axis_index}: endpoint_margin_fraction={endpoint_margin_fraction} "
            f"collapses candidate interval [{sector.u_lo}, {sector.u_hi}]"
        )
    return u_lo, u_hi


def _select_axis_branch(
    bar: PlanarFourBar,
    *,
    axis_index: int,
    u_interval: tuple[float, float] | None,
    n_samples: int,
    min_abs_gain: float,
    min_u_width: float,
    endpoint_margin_fraction: float,
    sector_choice: int,
    table_samples_per_axis: int,
    bisection_tol: float,
    bisection_max_iter: int,
) -> tuple[float, float, OutputAxis, MonotoneTableAxisInverse, int]:
    """Select, canonicalize, and package one axis of a four-bar branch."""
    u_lo, u_hi = _select_axis_interval(
        bar,
        axis_index=axis_index,
        u_interval=u_interval,
        n_samples=n_samples,
        min_abs_gain=min_abs_gain,
        min_u_width=min_u_width,
        endpoint_margin_fraction=endpoint_margin_fraction,
        sector_choice=sector_choice,
    )

    if int(table_samples_per_axis) < 4:
        raise ValueError(
            f"table_samples_per_axis must be >= 4, got {table_samples_per_axis}"
        )
    u_table = np.linspace(u_lo, u_hi, int(table_samples_per_axis))
    q_raw_table = bar.follower_curve(u_table, unwrap=True)
    diffs = np.diff(q_raw_table)
    if np.all(diffs > 0.0):
        sign = 1
    elif np.all(diffs < 0.0):
        sign = -1
    else:
        raise BranchCertificationError(
            f"axis {axis_index}: candidate interval [{u_lo}, {u_hi}] is not strictly "
            "monotonic (a follower reversal was detected inside the interval)"
        )

    chart_lo = float(np.min(q_raw_table))
    chart_hi = float(np.max(q_raw_table))
    if not (chart_hi > chart_lo):
        raise BranchCertificationError(f"axis {axis_index}: degenerate output chart")
    if not (chart_hi - chart_lo < _TWO_PI):
        raise BranchCertificationError(
            f"axis {axis_index}: output chart span {chart_hi - chart_lo} >= 2*pi "
            "is not permitted for a nonperiodic bounded branch"
        )

    axis = OutputAxis(
        topology=AxisTopology.BOUNDED_REVOLUTE, lower=chart_lo, upper=chart_hi
    )
    q_table_canonical = np.array(
        [axis.canonicalize(float(q)) for q in q_raw_table], dtype=np.float64
    )
    inv = MonotoneTableAxisInverse(
        sign=sign,
        u_table=tuple(float(x) for x in u_table),
        q_table=tuple(float(x) for x in q_table_canonical),
        tol=float(bisection_tol),
        max_iter=int(bisection_max_iter),
    )
    return u_lo, u_hi, axis, inv, sign


def select_fourbar_monotonic_branch(
    mech: PlanarFourBar | IndependentFourBars,
    *,
    u_intervals: Sequence[tuple[float, float] | None] | None = None,
    n_samples: int = 361,
    min_abs_gain: float = 0.05,
    min_u_width: float = 0.3,
    endpoint_margin_fraction: float = 0.05,
    sector_choice: Sequence[int] | None = None,
    table_samples_per_axis: int = 65,
    certification_samples_per_axis: int = 17,
    max_abs_gain: float | None = None,
    residual_tol: float = 1e-6,
    bisection_tol: float = 1e-10,
    bisection_max_iter: int = 100,
    name: str | None = None,
) -> OperatingBranch:
    """Select and certify a nonperiodic monotonic operating branch of a four-bar.

    Per axis (each ``PlanarFourBar`` factor of ``mech``):

    1. use the fixed algebraic branch already selected on that
       ``PlanarFourBar`` (``+1``/``-1``, unchanged);
    2. find candidate monotonic crank intervals between follower extrema
       (:func:`inequality_mechanisms.mechanisms.monotonic.find_monotonic_sectors`);
    3. shrink the chosen interval by ``endpoint_margin_fraction`` at both
       ends, moving away from the near-zero-gain sector boundary;
    4. unwrap the continuous follower image and canonicalize it into a
       dedicated bounded-revolute ``OutputSpace`` chart sized to the
       achieved range (ADR-011), so a curve crossing the principal-angle
       seam stays continuous;
    5. verify strict derivative sign consistency and reject a reversal;
    6. certify
       (:func:`inequality_mechanisms.mechanisms.operating_branch.certify_branch`),
       which also rejects gain too close to ``min_abs_gain``.

    The resulting branch's underlying mechanism is a nonperiodic copy
    (``periodic=False`` on every axis); it never uses full-cycle wraparound.

    Parameters
    ----------
    mech :
        Single ``PlanarFourBar`` or ``IndependentFourBars``.
    u_intervals :
        Optional explicit per-axis ``(u_lo, u_hi)`` override, bypassing
        automatic sector search and margin shrinking for that axis (``None``
        entries still use automatic selection). Useful to construct
        intervals that deliberately include a reversal or too-small gain
        for negative testing; :func:`certify_branch` will reject them.
    n_samples, min_abs_gain, min_u_width :
        Forwarded to ``find_monotonic_sectors`` for automatic candidate
        interval detection.
    endpoint_margin_fraction :
        Fraction (``[0, 0.5)``) of each automatically selected interval's
        width trimmed from both ends.
    sector_choice :
        Per-axis index into the width-sorted candidate list (default widest
        candidate, index ``0``, on every axis).
    table_samples_per_axis :
        Interpolation table density for the branch-local monotone-table
        inverse seed.
    certification_samples_per_axis, max_abs_gain, residual_tol :
        Forwarded to :func:`certify_branch`.
    bisection_tol, bisection_max_iter :
        Explicit tolerance and iteration cap for the in-house bracketed
        bisection root refine used by ``inverse``.
    name :
        Optional branch mechanism name.

    Returns
    -------
    OperatingBranch
        Certified, nonperiodic, axis-separable four-bar operating branch.

    Raises
    ------
    BranchCertificationError
        If no monotonic candidate interval exists, the interval collapses
        under the safety margin, a reversal or excessive output span is
        detected, or certification fails (coupling, sign, gain, residual).
    """
    base_mech = _as_independent_fourbars(mech)
    dim = base_mech.input_dim

    intervals: list[tuple[float, float] | None]
    if u_intervals is None:
        intervals = [None] * dim
    else:
        intervals = list(u_intervals)
        if len(intervals) != dim:
            raise ValueError(
                f"u_intervals must have length {dim}, got {len(intervals)}"
            )

    choices: list[int]
    if sector_choice is None:
        choices = [0] * dim
    else:
        choices = list(sector_choice)
        if len(choices) != dim:
            raise ValueError(
                f"sector_choice must have length {dim}, got {len(choices)}"
            )

    u_lower = np.empty(dim, dtype=np.float64)
    u_upper = np.empty(dim, dtype=np.float64)
    axes: list[OutputAxis] = []
    axis_inverses: list[MonotoneTableAxisInverse] = []
    signs: list[int] = []
    for i, bar in enumerate(base_mech.bars):
        u_lo, u_hi, axis, inv, sign = _select_axis_branch(
            bar,
            axis_index=i,
            u_interval=intervals[i],
            n_samples=n_samples,
            min_abs_gain=min_abs_gain,
            min_u_width=min_u_width,
            endpoint_margin_fraction=endpoint_margin_fraction,
            sector_choice=choices[i],
            table_samples_per_axis=table_samples_per_axis,
            bisection_tol=bisection_tol,
            bisection_max_iter=bisection_max_iter,
        )
        u_lower[i] = u_lo
        u_upper[i] = u_hi
        axes.append(axis)
        axis_inverses.append(inv)
        signs.append(sign)

    open_mech: IndependentFourBars = open_axis_independent_fourbars(base_mech)
    if name is not None:
        open_mech = IndependentFourBars(open_mech.bars, name=name)
    output_space = OutputSpace(axes=tuple(axes))

    certificate = certify_branch(
        open_mech,
        output_space,
        axis_inverses,
        input_lower=u_lower,
        input_upper=u_upper,
        certification_samples_per_axis=certification_samples_per_axis,
        min_abs_gain=min_abs_gain,
        max_abs_gain=max_abs_gain,
        residual_tol=residual_tol,
        certification_method="fourbar_monotone_table_bisection",
    )

    selector_meta: dict[str, Any] = {
        "method": "fourbar_monotone_branch",
        "n_samples": int(n_samples),
        "min_abs_gain": float(min_abs_gain),
        "min_u_width": float(min_u_width),
        "endpoint_margin_fraction": float(endpoint_margin_fraction),
        "sector_choice": [int(c) for c in choices],
        "table_samples_per_axis": int(table_samples_per_axis),
        "u_intervals_override": [
            None if iv is None else [float(iv[0]), float(iv[1])] for iv in intervals
        ],
    }

    return OperatingBranch(
        open_mech,
        output_space,
        axis_inverses=tuple(axis_inverses),
        certificate=certificate,
        selector=selector_meta,
        residual_tol=residual_tol,
    )
