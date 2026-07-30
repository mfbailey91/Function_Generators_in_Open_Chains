"""Version 2 requested output tasks and deterministic node matching (V2-402/403).

Version 2 tasks are requested output start/goal pairs in ``Q``; there is no
preimage-selection policy (ADR-014) because every valid node already carries
a unique attached actuator realization. Matching is deterministic
nearest-valid-node in ``Q`` with a lowest-node-ID tie-break, and residuals
are recorded (never silently resampled) so endpoint-snapping error is
visible before the exact query overlays of Sprint V2.6.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np
from numpy.random import Generator
from numpy.typing import ArrayLike, NDArray

from inequality_mechanisms.graphs.embedded import EmbeddedPlanningGraph


def _as_vector(x: ArrayLike, *, name: str) -> NDArray[np.float64]:
    arr = np.asarray(x, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be 1-D, got shape {arr.shape}")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must contain only finite values")
    return arr


@dataclass(frozen=True, slots=True)
class OutputTask:
    """A requested output-space start/goal pair (V2-402).

    Attributes
    ----------
    requested_start_q, requested_goal_q :
        Requested output configurations, each shape ``(output_dim,)``. Not
        necessarily achievable by any particular graph's node lattice; the
        resolver records the realized state and residual separately per
        graph (V2-403).
    """

    requested_start_q: NDArray[np.float64]
    requested_goal_q: NDArray[np.float64]

    def __post_init__(self) -> None:
        start = _as_vector(self.requested_start_q, name="requested_start_q")
        goal = _as_vector(self.requested_goal_q, name="requested_goal_q")
        if start.shape != goal.shape:
            raise ValueError(
                "requested_start_q and requested_goal_q must have the same "
                f"shape, got {start.shape} and {goal.shape}"
            )
        object.__setattr__(self, "requested_start_q", start)
        object.__setattr__(self, "requested_goal_q", goal)


class TaskRejectionReason(str, Enum):
    """Why a requested endpoint (or its task) was rejected."""

    START_RESIDUAL_EXCEEDS_TOLERANCE = "start_residual_exceeds_tolerance"
    GOAL_RESIDUAL_EXCEEDS_TOLERANCE = "goal_residual_exceeds_tolerance"
    NO_VALID_NODES = "no_valid_nodes"


@dataclass(frozen=True, slots=True)
class ResolvedTaskEndpoint:
    """One matched endpoint (start or goal) of a requested task.

    Attributes
    ----------
    requested_q :
        Requested output configuration.
    selected_node_id :
        Deterministically matched flat node ID (lowest ID on distance ties).
    realized_q :
        The matched node's actual planning-state coordinate.
    realized_u :
        The matched node's attached actuator realization.
    residual_vector, residual_norm :
        ``realized_q - canonicalize(requested_q)`` and its Euclidean norm.
    """

    requested_q: NDArray[np.float64]
    selected_node_id: int
    realized_q: NDArray[np.float64]
    realized_u: NDArray[np.float64]
    residual_vector: NDArray[np.float64]
    residual_norm: float

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "requested_q": self.requested_q.tolist(),
            "selected_node_id": self.selected_node_id,
            "realized_q": self.realized_q.tolist(),
            "realized_u": self.realized_u.tolist(),
            "residual_vector": self.residual_vector.tolist(),
            "residual_norm": self.residual_norm,
        }


@dataclass(frozen=True, slots=True)
class ResolvedTask:
    """Outcome of resolving one :class:`OutputTask` against one graph.

    Attributes
    ----------
    task :
        The originally requested task (reused verbatim across mechanisms
        and sampling modes, per V2-403).
    output_tolerance :
        Maximum acceptable endpoint residual norm.
    start, goal :
        Matched endpoints, or ``None`` when matching failed outright (no
        valid nodes at all in the graph).
    rejected :
        ``True`` when either endpoint's residual exceeds ``output_tolerance``
        or matching failed.
    rejection_reason :
        Machine-readable reason, or ``None`` when accepted.
    """

    task: OutputTask
    output_tolerance: float
    start: ResolvedTaskEndpoint | None
    goal: ResolvedTaskEndpoint | None
    rejected: bool
    rejection_reason: str | None

    @property
    def start_node_id(self) -> int:
        """Matched start node ID.

        Raises
        ------
        ValueError
            If the task was rejected.
        """
        if self.rejected or self.start is None:
            raise ValueError("task has no resolved start endpoint (rejected)")
        return self.start.selected_node_id

    @property
    def goal_node_id(self) -> int:
        """Matched goal node ID.

        Raises
        ------
        ValueError
            If the task was rejected.
        """
        if self.rejected or self.goal is None:
            raise ValueError("task has no resolved goal endpoint (rejected)")
        return self.goal.selected_node_id

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "requested_start_q": self.task.requested_start_q.tolist(),
            "requested_goal_q": self.task.requested_goal_q.tolist(),
            "output_tolerance": self.output_tolerance,
            "start": None if self.start is None else self.start.to_dict(),
            "goal": None if self.goal is None else self.goal.to_dict(),
            "rejected": self.rejected,
            "rejection_reason": self.rejection_reason,
        }


def match_nearest_valid_q_node(
    graph: EmbeddedPlanningGraph, requested_q: ArrayLike
) -> tuple[int, NDArray[np.float64], float]:
    """Deterministically match ``requested_q`` to the nearest valid node.

    Ties (exact distance equality) break to the lowest node ID: ``q_nodes``
    is indexed by ascending flat node ID and ``np.argmin`` on a vector of
    distances returns the first (lowest-index) minimum on an exact tie.

    Parameters
    ----------
    graph :
        Embedded planning graph to match against.
    requested_q :
        Requested output configuration, shape ``(output_dim,)``.

    Returns
    -------
    tuple
        ``(node_id, residual_vector, residual_norm)`` where
        ``residual_vector = graph.q_state(node_id) - canonicalize(requested_q)``.

    Raises
    ------
    ValueError
        If ``requested_q`` has the wrong shape, or the graph has no valid
        nodes at all (:class:`TaskRejectionReason.NO_VALID_NODES`).
    """
    output_space = graph.branch.output_space
    canon = output_space.canonicalize(requested_q)
    valid = graph.valid_nodes
    if not np.any(valid):
        raise ValueError(TaskRejectionReason.NO_VALID_NODES.value)

    diffs = graph.q_nodes - canon[np.newaxis, :]
    distances = np.linalg.norm(diffs, axis=1)
    distances = np.where(valid, distances, np.inf)
    node_id = int(np.argmin(distances))
    residual_vector = np.array(graph.q_nodes[node_id] - canon, dtype=np.float64)
    residual_norm = float(distances[node_id])
    return node_id, residual_vector, residual_norm


def resolve_output_task(
    graph: EmbeddedPlanningGraph,
    task: OutputTask,
    *,
    output_tolerance: float,
) -> ResolvedTask:
    """Resolve one requested task against one graph (V2-403).

    Matches both endpoints independently via
    :func:`match_nearest_valid_q_node`, then rejects the whole task (no
    silent resampling) if either endpoint's residual exceeds
    ``output_tolerance``.

    Parameters
    ----------
    graph :
        Embedded planning graph to resolve against.
    task :
        Requested output start/goal pair.
    output_tolerance :
        Maximum acceptable per-endpoint residual norm (``>= 0``).

    Returns
    -------
    ResolvedTask
    """
    if float(output_tolerance) < 0.0:
        raise ValueError(f"output_tolerance must be >= 0, got {output_tolerance}")

    try:
        start_id, start_resid_vec, start_resid = match_nearest_valid_q_node(
            graph, task.requested_start_q
        )
    except ValueError as exc:
        return ResolvedTask(
            task=task,
            output_tolerance=float(output_tolerance),
            start=None,
            goal=None,
            rejected=True,
            rejection_reason=str(exc),
        )
    try:
        goal_id, goal_resid_vec, goal_resid = match_nearest_valid_q_node(
            graph, task.requested_goal_q
        )
    except ValueError as exc:
        return ResolvedTask(
            task=task,
            output_tolerance=float(output_tolerance),
            start=None,
            goal=None,
            rejected=True,
            rejection_reason=str(exc),
        )

    start_endpoint = ResolvedTaskEndpoint(
        requested_q=task.requested_start_q,
        selected_node_id=start_id,
        realized_q=graph.q_state(start_id),
        realized_u=graph.u_state(start_id),
        residual_vector=start_resid_vec,
        residual_norm=start_resid,
    )
    goal_endpoint = ResolvedTaskEndpoint(
        requested_q=task.requested_goal_q,
        selected_node_id=goal_id,
        realized_q=graph.q_state(goal_id),
        realized_u=graph.u_state(goal_id),
        residual_vector=goal_resid_vec,
        residual_norm=goal_resid,
    )

    rejection_reason: str | None = None
    if start_resid > float(output_tolerance):
        rejection_reason = TaskRejectionReason.START_RESIDUAL_EXCEEDS_TOLERANCE.value
    elif goal_resid > float(output_tolerance):
        rejection_reason = TaskRejectionReason.GOAL_RESIDUAL_EXCEEDS_TOLERANCE.value

    return ResolvedTask(
        task=task,
        output_tolerance=float(output_tolerance),
        start=start_endpoint,
        goal=goal_endpoint,
        rejected=rejection_reason is not None,
        rejection_reason=rejection_reason,
    )


def generate_random_output_tasks(
    *,
    lower: ArrayLike,
    upper: ArrayLike,
    n_tasks: int,
    rng: Generator,
) -> list[OutputTask]:
    """Deterministically draw ``n_tasks`` uniform random output pairs.

    Parameters
    ----------
    lower, upper :
        Output-space box bounds, shape ``(output_dim,)``.
    n_tasks :
        Number of tasks to draw (``>= 0``).
    rng :
        Seeded NumPy generator (caller owns determinism via the seed).

    Returns
    -------
    list of OutputTask
        Reused verbatim across every mechanism and sampling mode (V2-403).
    """
    lo = _as_vector(lower, name="lower")
    hi = _as_vector(upper, name="upper")
    if lo.shape != hi.shape:
        raise ValueError("lower and upper must have the same shape")
    if np.any(hi <= lo):
        raise ValueError("upper must exceed lower on every axis")
    n = int(n_tasks)
    if n < 0:
        raise ValueError(f"n_tasks must be >= 0, got {n_tasks}")
    tasks: list[OutputTask] = []
    for _ in range(n):
        start = lo + rng.random(lo.shape) * (hi - lo)
        goal = lo + rng.random(lo.shape) * (hi - lo)
        tasks.append(OutputTask(start, goal))
    return tasks
