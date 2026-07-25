"""Equal valid-node-count graph matching (IM-018 / ADR-010).

Native mode shares one U lattice; valid-node counts then differ under shared
Q limits. Equal-node mode keeps the four-bar on the baseline crank lattice
and builds a gearbox lattice over the same Q box with resolution chosen so
``N_valid`` approximately matches.
"""

from __future__ import annotations

import math
from typing import Any

from inequality_mechanisms.graphs.grid import PeriodicGrid2D
from inequality_mechanisms.graphs.validation import ConstrainedInputGraph
from inequality_mechanisms.mechanisms.base import Mechanism
from inequality_mechanisms.spaces.limits import OutputJointLimits


def _square_shape_for_count(target: int) -> int:
    n = int(round(math.sqrt(max(int(target), 1))))
    return max(2, n)


def gearbox_grid_over_limits(
    limits: OutputJointLimits,
    shape: tuple[int, int],
    *,
    wrap: tuple[bool, bool] = (False, False),
) -> PeriodicGrid2D:
    """Build a gearbox U lattice whose axis ranges equal the shared Q box.

    For a unit gearbox ``q = u``, nearly every sample inside the box is
    limit-valid. Wrapping defaults to ``False`` because the box is a bounded
    joint window, not a full ``S^1`` period.
    """
    if limits.dim != 2:
        raise ValueError(f"equal-node gearbox grid requires limits.dim == 2, got {limits.dim}")
    ranges = (
        (float(limits.lower[0]), float(limits.upper[0])),
        (float(limits.lower[1]), float(limits.upper[1])),
    )
    return PeriodicGrid2D(shape, ranges=ranges, wrap=wrap)


def match_gearbox_to_fourbar_valid_count(
    *,
    gearbox_mechanism: Mechanism,
    fourbar_graph: ConstrainedInputGraph,
    limits: OutputJointLimits,
    edge_samples: int,
    relative_tol: float = 0.1,
    shape_lo: int = 2,
    shape_hi: int = 128,
) -> tuple[PeriodicGrid2D, ConstrainedInputGraph, dict[str, Any]]:
    """Refine a gearbox lattice over ``limits`` until ``N_valid`` ≈ four-bar.

    Starts from ``round(sqrt(N_fourbar))`` and searches nearby square shapes
    within ``[shape_lo, shape_hi]`` for the closest valid-node count.

    Returns
    -------
    grid, graph, meta
        Gearbox grid/graph and a small metadata dict for trial records.
    """
    if relative_tol <= 0.0 or not math.isfinite(relative_tol):
        raise ValueError(f"relative_tol must be finite and > 0, got {relative_tol}")
    if shape_lo < 2 or shape_hi < shape_lo:
        raise ValueError(f"require 2 <= shape_lo <= shape_hi, got {shape_lo}, {shape_hi}")

    target = int(fourbar_graph.valid_node_count)
    if target < 1:
        raise ValueError("four-bar graph has no valid nodes to match")

    start = min(shape_hi, max(shape_lo, _square_shape_for_count(target)))
    # Prefer shapes near the geometric start; expand outward.
    candidates: list[int] = [start]
    for delta in range(1, shape_hi - shape_lo + 1):
        lo = start - delta
        hi = start + delta
        if lo >= shape_lo:
            candidates.append(lo)
        if hi <= shape_hi:
            candidates.append(hi)
        if lo < shape_lo and hi > shape_hi:
            break

    best: tuple[int, PeriodicGrid2D, ConstrainedInputGraph] | None = None
    best_err: float | None = None
    tol_abs = relative_tol * float(target)

    for n in candidates:
        grid = gearbox_grid_over_limits(limits, (n, n))
        graph = ConstrainedInputGraph(
            grid,
            gearbox_mechanism,
            limits,
            edge_samples=edge_samples,
        )
        n_valid = int(graph.valid_node_count)
        err = abs(n_valid - target)
        if best_err is None or err < best_err:
            best_err = float(err)
            best = (n, grid, graph)
        if err <= tol_abs:
            meta = {
                "match_mode": "equal_valid_nodes",
                "target_n_valid": target,
                "gearbox_grid_shape": [n, n],
                "gearbox_valid_nodes": n_valid,
                "fourbar_valid_nodes": target,
                "fourbar_grid_shape": list(fourbar_graph.grid.shape),
                "relative_error": err / float(target),
                "relative_tol": float(relative_tol),
            }
            return grid, graph, meta

    assert best is not None and best_err is not None
    n, grid, graph = best
    raise ValueError(
        f"failed to match gearbox N_valid to four-bar target={target} "
        f"within relative_tol={relative_tol}; best shape=({n},{n}) "
        f"N_valid={graph.valid_node_count} abs_err={best_err}"
    )
