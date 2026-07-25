"""Paired gearbox / four-bar planning tasks (IM-015).

Each task shares output endpoints ``(q_start, q_goal)`` sampled from the
unit-gearbox lattice and stores the selected discrete input preimages on
both mechanisms. Duplicate four-bar preimages remain distinct candidates;
selection follows the configured policy.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray

from inequality_mechanisms.graphs.grid import PeriodicGrid2D
from inequality_mechanisms.graphs.validation import ConstrainedInputGraph

PreimagePolicy = Literal["lex_min_node_id", "random"]


@dataclass(frozen=True, slots=True)
class SelectedPreimages:
    """Discrete start/goal preimages for one mechanism on a paired task.

    Attributes
    ----------
    mechanism_name :
        ``Mechanism.name`` at selection time.
    start_node_id, goal_node_id :
        Flat valid lattice ids used as search endpoints.
    start_u, goal_u :
        Lattice coordinates of those nodes.
    n_start_candidates, n_goal_candidates :
        Number of valid discrete preimage candidates before selection.
    """

    mechanism_name: str
    start_node_id: int
    goal_node_id: int
    start_u: tuple[float, ...]
    goal_u: tuple[float, ...]
    n_start_candidates: int
    n_goal_candidates: int

    def to_dict(self) -> dict[str, Any]:
        """Serialize for trial-level records."""
        return {
            "mechanism_name": self.mechanism_name,
            "start_node_id": self.start_node_id,
            "goal_node_id": self.goal_node_id,
            "start_u": list(self.start_u),
            "goal_u": list(self.goal_u),
            "n_start_candidates": self.n_start_candidates,
            "n_goal_candidates": self.n_goal_candidates,
        }


@dataclass(frozen=True, slots=True)
class PairedTask:
    """Matched output endpoints with per-mechanism selected preimages.

    Attributes
    ----------
    trial_index :
        Zero-based index within a generated batch.
    q_start, q_goal :
        Shared output configurations (from the gearbox lattice nodes).
    gearbox, fourbar :
        Selected discrete preimages on each constrained graph.
    """

    trial_index: int
    q_start: NDArray[np.floating]
    q_goal: NDArray[np.floating]
    gearbox: SelectedPreimages
    fourbar: SelectedPreimages

    def to_dict(self) -> dict[str, Any]:
        """Serialize for trial-level records."""
        return {
            "trial_index": self.trial_index,
            "q_start": self.q_start.tolist(),
            "q_goal": self.q_goal.tolist(),
            "gearbox": self.gearbox.to_dict(),
            "fourbar": self.fourbar.to_dict(),
        }


def nearest_grid_indices(
    grid: PeriodicGrid2D,
    u: ArrayLike,
    *,
    periodic: Sequence[bool],
) -> tuple[int, int]:
    """Return lattice indices nearest to continuous configuration ``u``.

    Periodic axes wrap the residual into ``[-step/2, step/2]`` before
    rounding so samples near the period seam snap correctly.

    Parameters
    ----------
    grid :
        Target lattice.
    u :
        Continuous configuration, length 2.
    periodic :
        Per-axis wrap flags (typically ``mechanism.periodic_axes()``).

    Returns
    -------
    tuple of int
        Lattice indices ``(i0, i1)``.
    """
    arr = np.asarray(u, dtype=np.float64)
    if arr.shape != (2,):
        raise ValueError(f"u must have shape (2,), got {arr.shape}")
    if not np.all(np.isfinite(arr)):
        raise ValueError("u must contain only finite values")
    if len(periodic) != 2:
        raise ValueError(f"periodic must have length 2, got {len(periodic)}")

    indices: list[int] = []
    for axis in range(2):
        lo, hi = grid.ranges[axis]
        step = grid.steps[axis]
        n = grid.shape[axis]
        span = hi - lo
        x = float(arr[axis])
        if periodic[axis]:
            # Map into [lo, hi) then nearest sample.
            x = lo + ((x - lo) % span)
            raw = (x - lo) / step
            idx = int(round(raw)) % n
        else:
            raw = (x - lo) / step
            idx = int(round(raw))
            idx = max(0, min(n - 1, idx))
        indices.append(idx)
    return indices[0], indices[1]


def default_snap_tol(grid: PeriodicGrid2D) -> float:
    """Heuristic output snap tolerance from maximum lattice step."""
    return float(math.hypot(*grid.steps))


def discrete_preimage_candidates(
    graph: ConstrainedInputGraph,
    q: ArrayLike,
    *,
    snap_tol: float,
) -> list[int]:
    """Return valid node ids that approximate preimages of ``q``.

    Continuous ``inverse_output(q)`` solutions are snapped to the lattice.
    A snapped node is kept when it is valid and
    ``||g(u_node) - q||_2 <= snap_tol``.

    Parameters
    ----------
    graph :
        Constrained mechanism graph.
    q :
        Target output configuration.
    snap_tol :
        Maximum allowed output residual after snapping.

    Returns
    -------
    list of int
        Distinct valid flat node ids, sorted ascending.
    """
    if not math.isfinite(snap_tol) or snap_tol < 0.0:
        raise ValueError(f"snap_tol must be finite and >= 0, got {snap_tol}")
    q_arr = np.asarray(q, dtype=np.float64)
    mech = graph.mechanism
    continuous = mech.inverse_output(q_arr)
    periodic = mech.periodic_axes()
    seen: set[int] = set()
    for u_cont in continuous:
        i0, i1 = nearest_grid_indices(graph.grid, u_cont, periodic=periodic)
        if not graph.node_is_valid(i0, i1):
            continue
        node_id = graph.grid.node_id(i0, i1)
        u_node = graph.grid.coordinates(i0, i1)
        q_node = mech.input_to_output(u_node)
        if float(np.linalg.norm(q_node - q_arr)) <= snap_tol:
            seen.add(node_id)
    return sorted(seen)


def select_preimage(
    candidates: Sequence[int],
    *,
    policy: PreimagePolicy,
    rng: np.random.Generator,
) -> int:
    """Select one discrete preimage node id under ``policy``.

    Raises
    ------
    ValueError
        If ``candidates`` is empty or ``policy`` is unknown.
    """
    if not candidates:
        raise ValueError("cannot select preimage from an empty candidate list")
    if policy == "lex_min_node_id":
        return int(min(candidates))
    if policy == "random":
        idx = int(rng.integers(0, len(candidates)))
        return int(candidates[idx])
    raise ValueError(f"unknown preimage policy: {policy!r}")


def _node_coords(graph: ConstrainedInputGraph, node_id: int) -> tuple[float, ...]:
    i0, i1 = graph.grid.indices_from_id(node_id)
    return tuple(graph.grid.coordinates(i0, i1))


def _selected_from_nodes(
    graph: ConstrainedInputGraph,
    start_id: int,
    goal_id: int,
    *,
    n_start: int,
    n_goal: int,
) -> SelectedPreimages:
    return SelectedPreimages(
        mechanism_name=graph.mechanism.name,
        start_node_id=start_id,
        goal_node_id=goal_id,
        start_u=_node_coords(graph, start_id),
        goal_u=_node_coords(graph, goal_id),
        n_start_candidates=n_start,
        n_goal_candidates=n_goal,
    )


def generate_paired_tasks(
    gearbox_graph: ConstrainedInputGraph,
    fourbar_graph: ConstrainedInputGraph,
    *,
    n_trials: int,
    rng: np.random.Generator,
    min_output_separation: float = 0.0,
    preimage_policy: PreimagePolicy = "lex_min_node_id",
    max_sample_attempts: int = 10_000,
    snap_tol: float | None = None,
) -> list[PairedTask]:
    """Generate matched output start/goal tasks with stored preimages.

    Sampling draws distinct valid gearbox lattice nodes as endpoints so
    ``q_start`` / ``q_goal`` lie exactly on the gearbox graph. Four-bar
    discrete preimages are obtained by continuous inverse plus lattice
    snap with residual check. Failed draws are retried up to
    ``max_sample_attempts`` total attempts for the whole batch.

    Parameters
    ----------
    gearbox_graph, fourbar_graph :
        Constrained graphs sharing the same ``OutputJointLimits`` object
        identity is recommended (ADR-004); limits bounds must match.
    n_trials :
        Number of paired tasks to produce.
    rng :
        NumPy generator (deterministic under a fixed seed).
    min_output_separation :
        Reject pairs with ``||q_goal - q_start||_2 <`` this value.
    preimage_policy :
        How to choose among multiple valid four-bar (or gearbox) snaps.
    max_sample_attempts :
        Hard cap on random draws while filling ``n_trials``.
    snap_tol :
        Output residual tolerance; default is ``default_snap_tol``.

    Returns
    -------
    list of PairedTask
        Exactly ``n_trials`` tasks.

    Raises
    ------
    ValueError
        On inconsistent graphs/limits, non-positive ``n_trials``, or if
        sampling exhausts ``max_sample_attempts``.
    """
    if n_trials < 1:
        raise ValueError(f"n_trials must be >= 1, got {n_trials}")
    if max_sample_attempts < 1:
        raise ValueError(f"max_sample_attempts must be >= 1, got {max_sample_attempts}")
    if not math.isfinite(min_output_separation) or min_output_separation < 0.0:
        raise ValueError(
            "min_output_separation must be finite and >= 0, "
            f"got {min_output_separation}"
        )
    if gearbox_graph.limits.dim != fourbar_graph.limits.dim:
        raise ValueError("gearbox and fourbar limits must have the same dimension")
    if not np.allclose(gearbox_graph.limits.lower, fourbar_graph.limits.lower):
        raise ValueError("gearbox and fourbar limits.lower must match")
    if not np.allclose(gearbox_graph.limits.upper, fourbar_graph.limits.upper):
        raise ValueError("gearbox and fourbar limits.upper must match")

    gb_nodes = [n.node_id for n in gearbox_graph.iter_valid_nodes()]
    if len(gb_nodes) < 2:
        raise ValueError("gearbox graph must have at least two valid nodes")

    tol = default_snap_tol(fourbar_graph.grid) if snap_tol is None else float(snap_tol)
    tasks: list[PairedTask] = []
    attempts = 0

    while len(tasks) < n_trials:
        attempts += 1
        if attempts > max_sample_attempts:
            raise ValueError(
                f"failed to sample {n_trials} paired tasks after "
                f"{max_sample_attempts} attempts ({len(tasks)} succeeded)"
            )
        pair = rng.choice(gb_nodes, size=2, replace=False)
        start_gb = int(pair[0])
        goal_gb = int(pair[1])
        q_start = gearbox_graph.mechanism.input_to_output(
            _node_coords(gearbox_graph, start_gb)
        )
        q_goal = gearbox_graph.mechanism.input_to_output(
            _node_coords(gearbox_graph, goal_gb)
        )
        if float(np.linalg.norm(q_goal - q_start)) < min_output_separation:
            continue

        start_fb = discrete_preimage_candidates(fourbar_graph, q_start, snap_tol=tol)
        goal_fb = discrete_preimage_candidates(fourbar_graph, q_goal, snap_tol=tol)
        if not start_fb or not goal_fb:
            continue
        # Require distinct four-bar endpoints when possible; allow equal only
        # if both endpoint candidate sets collapse to the same single node.
        start_sel = select_preimage(start_fb, policy=preimage_policy, rng=rng)
        goal_sel = select_preimage(goal_fb, policy=preimage_policy, rng=rng)
        if start_sel == goal_sel:
            # Try alternate goal candidate under lex / remaining set.
            alt_goals = [c for c in goal_fb if c != start_sel]
            if not alt_goals:
                continue
            goal_sel = select_preimage(alt_goals, policy=preimage_policy, rng=rng)

        gearbox_sel = _selected_from_nodes(
            gearbox_graph,
            start_gb,
            goal_gb,
            n_start=1,
            n_goal=1,
        )
        fourbar_sel = _selected_from_nodes(
            fourbar_graph,
            start_sel,
            goal_sel,
            n_start=len(start_fb),
            n_goal=len(goal_fb),
        )
        tasks.append(
            PairedTask(
                trial_index=len(tasks),
                q_start=np.asarray(q_start, dtype=np.float64).copy(),
                q_goal=np.asarray(q_goal, dtype=np.float64).copy(),
                gearbox=gearbox_sel,
                fourbar=fourbar_sel,
            )
        )

    return tasks
