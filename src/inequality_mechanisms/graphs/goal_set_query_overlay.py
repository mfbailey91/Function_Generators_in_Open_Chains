"""Multi-goal query overlays for represented goal-set lattice search (V3-632).

Attaches one exact start and an ordered collection of represented goals onto a
shared query graph. Search then terminates when any attached goal node is
optimally settled (ADR-020 ``goal_node_ids``).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray

from inequality_mechanisms.graphs.embedded import EmbeddedPlanningGraph
from inequality_mechanisms.graphs.query_overlay import (
    QueryNode,
    ResolvedQueryEndpoint,
    resolve_query_endpoint,
)
from inequality_mechanisms.graphs.sampling import (
    SamplingDomain,
    TransitionParameterization,
)
from inequality_mechanisms.graphs.topology import TensorGridTopology
from inequality_mechanisms.graphs.transitions import EdgeTraceV2, build_edge_trace_v2
from inequality_mechanisms.mechanisms.operating_branch import OperatingBranch

AttachmentRole = Literal["start", "goal"]


@dataclass(frozen=True, slots=True)
class GoalAttachmentFailure:
    """Structured failure for one represented goal attachment."""

    goal_index: int
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_index": int(self.goal_index),
            "reason": str(self.reason),
        }


class IncompleteGoalSetAttachmentError(ValueError):
    """Raised when a complete represented goal set cannot be attached.

    The exception preserves structured failure records so planner adapters can
    fail closed without discarding the identity of the rejected candidates.
    """

    def __init__(
        self,
        *,
        requested_goal_count: int,
        attached_goal_count: int,
        unique_goal_node_count: int,
        failures: Sequence[GoalAttachmentFailure],
    ) -> None:
        self.requested_goal_count = int(requested_goal_count)
        self.attached_goal_count = int(attached_goal_count)
        self.unique_goal_node_count = int(unique_goal_node_count)
        self.failures = tuple(failures)
        detail = "; ".join(
            f"goal_index={failure.goal_index}: {failure.reason}"
            for failure in self.failures
        )
        message = "goal-set overlay failed to attach every represented goal"
        if detail:
            message += ": " + detail
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class QueryAttachment:
    """One start or goal attachment on a goal-set query overlay."""

    role: AttachmentRole
    node_id: int
    q: NDArray[np.float64]
    u: NDArray[np.float64]
    requested_q: NDArray[np.float64]
    overlay_created: bool
    corner_neighbors: tuple[int, ...]
    attachment_residual_q: float
    attachment_residual_u: float | None = None
    goal_index: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "node_id": int(self.node_id),
            "q": self.q.tolist(),
            "u": self.u.tolist(),
            "requested_q": self.requested_q.tolist(),
            "overlay_created": bool(self.overlay_created),
            "corner_neighbors": list(self.corner_neighbors),
            "attachment_residual_q": float(self.attachment_residual_q),
            "attachment_residual_u": (
                None
                if self.attachment_residual_u is None
                else float(self.attachment_residual_u)
            ),
            "goal_index": self.goal_index,
        }


def _as_q_list(goal_qs: Sequence[NDArray[np.float64]]) -> list[NDArray[np.float64]]:
    out: list[NDArray[np.float64]] = []
    for q in goal_qs:
        arr = np.asarray(q, dtype=np.float64)
        if arr.ndim != 1:
            raise ValueError("each goal_q must be 1-D")
        out.append(arr)
    return out


def _as_optional_u_list(
    goal_us: Sequence[NDArray[np.float64] | None] | None,
    *,
    n_goals: int,
) -> list[NDArray[np.float64] | None]:
    if goal_us is None:
        return [None] * n_goals
    if len(goal_us) != n_goals:
        raise ValueError(
            f"goal_us length {len(goal_us)} must match goal_qs length {n_goals}"
        )
    out: list[NDArray[np.float64] | None] = []
    for u in goal_us:
        if u is None:
            out.append(None)
        else:
            arr = np.asarray(u, dtype=np.float64)
            if arr.ndim != 1:
                raise ValueError("each goal_u must be 1-D when provided")
            out.append(arr)
    return out


class GoalSetQueryOverlay:
    """SearchGraph wrapper with one start plus all represented goal attachments.

    Overlay node ids are allocated in role order: start (if needed), then each
    non-deduplicated goal in the caller-supplied order. ``goal_node_ids`` lists
    unique attached goal node ids in first-seen order for ADR-020 search.
    """

    def __init__(
        self,
        *,
        base: EmbeddedPlanningGraph,
        start_q: NDArray[np.float64],
        goal_qs: Sequence[NDArray[np.float64]],
        start_u: NDArray[np.float64] | None = None,
        goal_us: Sequence[NDArray[np.float64] | None] | None = None,
        dedup_tol: float = 1e-12,
        edge_n_samples: int = 17,
        require_all_goals: bool = True,
    ) -> None:
        if base.sampling_domain != SamplingDomain.OUTPUT:
            raise ValueError(
                "GoalSetQueryOverlay currently supports base graphs built from "
                "uniform OUTPUT sampling only"
            )
        if base.topology is None:  # pragma: no cover
            raise ValueError("base graph must provide a topology")

        goals = _as_q_list(goal_qs)
        if not goals:
            raise ValueError("goal_qs must contain at least one goal")
        goal_u_list = _as_optional_u_list(goal_us, n_goals=len(goals))

        self._base = base
        self._edge_n_samples = int(edge_n_samples)
        self._dedup_tol = float(dedup_tol)

        start_resolved = resolve_query_endpoint(
            base,
            requested_q=start_q,
            requested_u=start_u,
            dedup_tol=self._dedup_tol,
            edge_n_samples=self._edge_n_samples,
        )

        goal_resolutions: list[tuple[int, ResolvedQueryEndpoint]] = []
        failures: list[str] = []
        failure_records: list[GoalAttachmentFailure] = []
        for idx, goal_q in enumerate(goals):
            try:
                resolved = resolve_query_endpoint(
                    base,
                    requested_q=goal_q,
                    requested_u=goal_u_list[idx],
                    dedup_tol=self._dedup_tol,
                    edge_n_samples=self._edge_n_samples,
                )
            except (ValueError, TypeError) as exc:
                reason = str(exc)
                failures.append(f"goal_index={idx}: {reason}")
                failure_records.append(
                    GoalAttachmentFailure(goal_index=int(idx), reason=reason)
                )
                continue
            goal_resolutions.append((idx, resolved))

        if require_all_goals and failure_records:
            attached_base_nodes = {
                int(resolved.base_node_id)
                for _, resolved in goal_resolutions
                if resolved.base_node_id is not None
            }
            attached_overlay_count = sum(
                resolved.base_node_id is None
                for _, resolved in goal_resolutions
            )
            attached_unique_goal_node_count = (
                len(attached_base_nodes) + attached_overlay_count
            )
            raise IncompleteGoalSetAttachmentError(
                requested_goal_count=len(goals),
                attached_goal_count=len(goal_resolutions),
                unique_goal_node_count=attached_unique_goal_node_count,
                failures=failure_records,
            )

        if not goal_resolutions:
            detail = "; ".join(failures) if failures else "no goals supplied"
            raise ValueError(
                "goal-set overlay attached no represented goals; " + detail
            )

        overlay_nodes: list[QueryNode] = []
        attachments: list[QueryAttachment] = []
        overlay_id_cursor = base.node_count

        def _allocate(resolved: ResolvedQueryEndpoint) -> tuple[int, bool]:
            nonlocal overlay_id_cursor
            if resolved.base_node_id is not None:
                return int(resolved.base_node_id), False
            node_id = overlay_id_cursor
            overlay_nodes.append(
                QueryNode(
                    node_id=node_id,
                    q=resolved.q,
                    u=resolved.u,
                    corner_neighbors=resolved.corner_neighbors,
                )
            )
            overlay_id_cursor += 1
            return int(node_id), True

        start_id, start_overlay = _allocate(start_resolved)
        attachments.append(
            QueryAttachment(
                role="start",
                node_id=start_id,
                q=np.array(start_resolved.q, copy=True),
                u=np.array(start_resolved.u, copy=True),
                requested_q=np.array(start_resolved.requested_q, copy=True),
                overlay_created=start_overlay,
                corner_neighbors=start_resolved.corner_neighbors,
                attachment_residual_q=float(start_resolved.attachment_residual_q),
                attachment_residual_u=start_resolved.attachment_residual_u,
                goal_index=None,
            )
        )

        goal_node_ids: list[int] = []
        seen_goal_nodes: set[int] = set()
        for goal_index, resolved in goal_resolutions:
            goal_id, goal_overlay = _allocate(resolved)
            attachments.append(
                QueryAttachment(
                    role="goal",
                    node_id=goal_id,
                    q=np.array(resolved.q, copy=True),
                    u=np.array(resolved.u, copy=True),
                    requested_q=np.array(resolved.requested_q, copy=True),
                    overlay_created=goal_overlay,
                    corner_neighbors=resolved.corner_neighbors,
                    attachment_residual_q=float(resolved.attachment_residual_q),
                    attachment_residual_u=resolved.attachment_residual_u,
                    goal_index=int(goal_index),
                )
            )
            if goal_id not in seen_goal_nodes:
                seen_goal_nodes.add(goal_id)
                goal_node_ids.append(goal_id)

        self._start_node_id = int(start_id)
        self._goal_node_ids = tuple(int(n) for n in goal_node_ids)
        self._attachments = tuple(attachments)
        self._requested_goal_count = len(goals)
        self._attached_goal_count = len(goal_resolutions)
        self._failed_goal_attachments = tuple(failures)
        self._attachment_complete = (
            not failures and len(goal_resolutions) == len(goals)
        )

        self._overlay_nodes = tuple(overlay_nodes)
        self._overlay_idx = {n.node_id: i for i, n in enumerate(self._overlay_nodes)}

        self._valid_nodes = np.zeros(
            base.node_count + len(self._overlay_nodes), dtype=np.bool_
        )
        self._valid_nodes[: base.node_count] = np.asarray(
            base.valid_nodes, dtype=np.bool_
        )
        for n in self._overlay_nodes:
            self._valid_nodes[n.node_id] = True

        self._base_to_overlay_neighbors: dict[int, list[int]] = {}
        for n in self._overlay_nodes:
            for corner in n.corner_neighbors:
                self._base_to_overlay_neighbors.setdefault(corner, []).append(n.node_id)
        for corner, ids in self._base_to_overlay_neighbors.items():
            ids.sort()

    @property
    def base(self) -> EmbeddedPlanningGraph:
        return self._base

    @property
    def node_count(self) -> int:
        return int(self._valid_nodes.shape[0])

    def node_is_valid(self, node_id: int) -> bool:
        if node_id < 0 or node_id >= self.node_count:
            raise ValueError(f"node_id out of range: {node_id}")
        return bool(self._valid_nodes[node_id])

    @property
    def valid_nodes(self) -> NDArray[np.bool_]:
        return np.asarray(self._valid_nodes, dtype=np.bool_)

    def q_state(self, node_id: int) -> NDArray[np.float64]:
        if node_id < self._base.node_count:
            return self._base.q_state(node_id)
        overlay = self._overlay_nodes[self._overlay_idx[node_id]]
        return np.array(overlay.q, copy=True)

    def u_state(self, node_id: int) -> NDArray[np.float64]:
        if node_id < self._base.node_count:
            return self._base.u_state(node_id)
        overlay = self._overlay_nodes[self._overlay_idx[node_id]]
        return np.array(overlay.u, copy=True)

    @property
    def topology(self) -> TensorGridTopology:
        return self._base.topology

    @property
    def branch(self) -> OperatingBranch:
        return self._base.branch

    @property
    def transition_parameterization(self) -> TransitionParameterization:
        return self._base.transition_parameterization

    @property
    def sampling_domain(self) -> SamplingDomain:
        return self._base.sampling_domain

    def output_axis_spacing(self, axis: int):
        return self._base.output_axis_spacing(axis)

    def actuator_axis_spacing(self, axis: int):
        return self._base.actuator_axis_spacing(axis)

    def neighbors(self, node_id: int) -> tuple[int, ...]:
        """Return valid neighbor node ids (deterministic order)."""
        if node_id < self._base.node_count:
            base_nbs = self._base.neighbors(node_id)
            extra = tuple(self._base_to_overlay_neighbors.get(node_id, []))
            return tuple(base_nbs) + extra
        overlay = self._overlay_nodes[self._overlay_idx[node_id]]
        return tuple(overlay.corner_neighbors)

    def edge_trace(self, a: int, b: int, n_samples: int = 17) -> EdgeTraceV2:
        """Return a Version-2 edge trace between any two overlay nodes."""
        if a == b:
            raise ValueError("edge_trace requires distinct endpoints")
        n = self.node_count
        if not (0 <= a < n) or not (0 <= b < n):
            raise ValueError(f"node ids out of range: {a}, {b}")
        if not (self.node_is_valid(a) and self.node_is_valid(b)):
            raise ValueError("edge_trace endpoints must be valid nodes")

        if a < self._base.node_count and b < self._base.node_count:
            return self._base.edge_trace(a, b, n_samples=n_samples)

        return build_edge_trace_v2(
            self._base.branch,
            self._base.transition_parameterization,
            self.q_state(a),
            self.u_state(a),
            self.q_state(b),
            self.u_state(b),
            n_samples=n_samples,
        )

    @property
    def start_node_id(self) -> int:
        return self._start_node_id

    @property
    def goal_node_ids(self) -> tuple[int, ...]:
        """Unique attached goal node ids in first-seen order."""
        return self._goal_node_ids

    @property
    def goal_node_id(self) -> int:
        """First attached goal node id (single-goal overlay compatibility)."""
        return self._goal_node_ids[0]

    @property
    def attachments(self) -> tuple[QueryAttachment, ...]:
        return self._attachments

    @property
    def requested_goal_count(self) -> int:
        return int(self._requested_goal_count)

    @property
    def attached_goal_count(self) -> int:
        """Number of represented goal candidates successfully attached."""
        return int(self._attached_goal_count)

    @property
    def attachment_complete(self) -> bool:
        return bool(self._attachment_complete)

    @property
    def failed_goal_attachments(self) -> tuple[str, ...]:
        return self._failed_goal_attachments

    def attachment_for_goal_node(self, node_id: int) -> QueryAttachment | None:
        """Return the first goal attachment mapped to ``node_id``."""
        for att in self._attachments:
            if att.role == "goal" and int(att.node_id) == int(node_id):
                return att
        return None

    def attachments_as_dicts(self) -> list[dict[str, Any]]:
        return [att.to_dict() for att in self._attachments]
