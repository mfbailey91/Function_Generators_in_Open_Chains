"""Q-neighbor query overlay for the frozen shared-Q sampled roadmap (V3-637).

Attaches the exact start and every represented goal onto a frozen
``SampledQRoadmapGraph`` using the same Q k-NN rule for every mechanism.
Does not use lattice ``GoalSetQueryOverlay`` (grid-corner attachment).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray

from inequality_mechanisms.graphs.pair_invariants import SharedQPairInvariantError
from inequality_mechanisms.graphs.sampled_q_roadmap import (
    SampledQRoadmapGraph,
    q_knn_indices,
)
from inequality_mechanisms.graphs.sampling import (
    SamplingDomain,
    TransitionParameterization,
)
from inequality_mechanisms.mechanisms.operating_branch import OperatingBranch

AttachmentRole = Literal["start", "goal"]


@dataclass(frozen=True, slots=True)
class SampledQQueryAttachment:
    """One exact start or represented-goal attachment on the sampled-Q overlay."""

    role: AttachmentRole
    node_id: int
    q: NDArray[np.float64]
    u: NDArray[np.float64]
    requested_q: NDArray[np.float64]
    q_neighbors: tuple[int, ...]
    attachment_residual_q: float
    goal_index: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "node_id": int(self.node_id),
            "q": self.q.tolist(),
            "u": self.u.tolist(),
            "requested_q": self.requested_q.tolist(),
            "q_neighbors": list(self.q_neighbors),
            "attachment_residual_q": float(self.attachment_residual_q),
            "goal_index": self.goal_index,
        }


class SampledQQueryOverlay:
    """SearchGraph wrapper with exact start plus ordered represented goals.

    Overlay node ids are allocated in role order: start, then each goal in the
    caller-supplied order. ``goal_node_ids`` lists attached goal ids in that
    order for ADR-020 ``goal_node_ids`` search.

    Q-neighbor selection uses the frozen bank's ``k_neighbors`` / ``max_edge_q``
    and does not consult mechanism validity. Searchable ``neighbors()`` then
    drops inverse-invalid bank endpoints; failed motions cost ``+inf`` without
    mutating the frozen bank adjacency.
    """

    def __init__(
        self,
        *,
        base: SampledQRoadmapGraph,
        start_q: NDArray[np.float64],
        start_u: NDArray[np.float64],
        goal_qs: Sequence[NDArray[np.float64]],
        goal_us: Sequence[NDArray[np.float64]],
    ) -> None:
        start_q_arr = np.asarray(start_q, dtype=np.float64)
        start_u_arr = np.asarray(start_u, dtype=np.float64)
        if start_q_arr.ndim != 1 or start_u_arr.ndim != 1:
            raise ValueError("start_q and start_u must be 1-D")
        if len(goal_qs) != len(goal_us):
            raise ValueError("goal_qs and goal_us must have the same length")
        goals_q = [np.asarray(q, dtype=np.float64) for q in goal_qs]
        goals_u = [np.asarray(u, dtype=np.float64) for u in goal_us]
        for q, u in zip(goals_q, goals_u):
            if q.ndim != 1 or u.ndim != 1:
                raise ValueError("each goal q/u must be 1-D")

        self._base = base
        bank = base.bank
        attachments: list[SampledQQueryAttachment] = []
        overlay_nodes: list[SampledQQueryAttachment] = []

        start_id = int(base.node_count)
        start_nbs = q_knn_indices(
            start_q_arr,
            bank.q_samples,
            k_neighbors=bank.k_neighbors,
            max_edge_q=bank.max_edge_q,
        )
        start_att = SampledQQueryAttachment(
            role="start",
            node_id=start_id,
            q=np.array(start_q_arr, copy=True),
            u=np.array(start_u_arr, copy=True),
            requested_q=np.array(start_q_arr, copy=True),
            q_neighbors=start_nbs,
            attachment_residual_q=0.0,
            goal_index=None,
        )
        attachments.append(start_att)
        overlay_nodes.append(start_att)

        goal_node_ids: list[int] = []
        next_id = start_id + 1
        for idx, (gq, gu) in enumerate(zip(goals_q, goals_u)):
            nbs = q_knn_indices(
                gq,
                bank.q_samples,
                k_neighbors=bank.k_neighbors,
                max_edge_q=bank.max_edge_q,
            )
            att = SampledQQueryAttachment(
                role="goal",
                node_id=next_id,
                q=np.array(gq, copy=True),
                u=np.array(gu, copy=True),
                requested_q=np.array(gq, copy=True),
                q_neighbors=nbs,
                attachment_residual_q=0.0,
                goal_index=int(idx),
            )
            attachments.append(att)
            overlay_nodes.append(att)
            goal_node_ids.append(next_id)
            next_id += 1

        self._start_node_id = start_id
        self._goal_node_ids = tuple(goal_node_ids)
        self._attachments = tuple(attachments)
        self._overlay_nodes = tuple(overlay_nodes)
        self._overlay_idx = {n.node_id: i for i, n in enumerate(self._overlay_nodes)}
        self._requested_goal_count = len(goals_q)

        total = int(base.node_count) + len(self._overlay_nodes)
        self._valid_nodes = np.zeros(total, dtype=np.bool_)
        self._valid_nodes[: base.node_count] = np.asarray(base.valid_nodes, dtype=np.bool_)
        for n in self._overlay_nodes:
            self._valid_nodes[n.node_id] = True

        self._base_to_overlay: dict[int, list[int]] = {}
        for n in self._overlay_nodes:
            for nb in n.q_neighbors:
                self._base_to_overlay.setdefault(int(nb), []).append(n.node_id)
        for ids in self._base_to_overlay.values():
            ids.sort()

    @property
    def base(self) -> SampledQRoadmapGraph:
        return self._base

    @property
    def start_node_id(self) -> int:
        return int(self._start_node_id)

    @property
    def goal_node_ids(self) -> tuple[int, ...]:
        return self._goal_node_ids

    @property
    def requested_goal_count(self) -> int:
        return int(self._requested_goal_count)

    @property
    def node_count(self) -> int:
        return int(self._valid_nodes.shape[0])

    @property
    def branch(self) -> OperatingBranch:
        return self._base.branch

    @property
    def transition_parameterization(self) -> TransitionParameterization:
        return self._base.transition_parameterization

    @property
    def sampling_domain(self) -> SamplingDomain:
        return self._base.sampling_domain

    def node_is_valid(self, node_id: int) -> bool:
        if node_id < 0 or node_id >= self.node_count:
            raise ValueError(f"node_id out of range: {node_id}")
        return bool(self._valid_nodes[node_id])

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

    def q_neighbors_raw(self, node_id: int) -> tuple[int, ...]:
        """Frozen Q-kNN bank ids for an overlay node (validity not applied)."""
        overlay = self._overlay_nodes[self._overlay_idx[node_id]]
        return overlay.q_neighbors

    def neighbors(self, node_id: int) -> tuple[int, ...]:
        """Return valid neighbor node ids (deterministic order)."""
        if node_id < 0 or node_id >= self.node_count:
            raise ValueError(f"node_id out of range: {node_id}")
        if node_id < self._base.node_count:
            base_nbs = self._base.neighbors(node_id)
            extra = tuple(
                oid
                for oid in self._base_to_overlay.get(node_id, [])
                if self._valid_nodes[oid]
            )
            return tuple(base_nbs) + extra
        overlay = self._overlay_nodes[self._overlay_idx[node_id]]
        return tuple(nb for nb in overlay.q_neighbors if self._valid_nodes[nb])

    def attachment_for_goal_node(self, node_id: int) -> SampledQQueryAttachment | None:
        idx = self._overlay_idx.get(int(node_id))
        if idx is None:
            return None
        att = self._overlay_nodes[idx]
        if att.role != "goal":
            return None
        return att

    def attachments_as_dicts(self) -> list[dict[str, Any]]:
        return [a.to_dict() for a in self._attachments]


def assert_identical_sampled_q_query_overlays(
    overlay_a: SampledQQueryOverlay,
    overlay_b: SampledQQueryOverlay,
) -> None:
    """Require identical overlay ids and Q-neighbor attachments across the pair."""
    failures: list[str] = []
    if overlay_a.start_node_id != overlay_b.start_node_id:
        failures.append("start_node_id mismatch")
    if overlay_a.goal_node_ids != overlay_b.goal_node_ids:
        failures.append("goal_node_ids mismatch")
    if overlay_a.requested_goal_count != overlay_b.requested_goal_count:
        failures.append("requested_goal_count mismatch")
    shared_ids = []
    if overlay_a.start_node_id == overlay_b.start_node_id:
        shared_ids.append(overlay_a.start_node_id)
    for nid in overlay_a.goal_node_ids:
        if nid in overlay_b.goal_node_ids:
            shared_ids.append(nid)
    for nid in shared_ids:
        if overlay_a.q_neighbors_raw(nid) != overlay_b.q_neighbors_raw(nid):
            failures.append(f"Q-neighbor list mismatch at overlay node {nid}")
        if not np.array_equal(overlay_a.q_state(nid), overlay_b.q_state(nid)):
            failures.append(f"overlay q mismatch at node {nid}")
    if failures:
        raise SharedQPairInvariantError(
            "shared-Q sampled-roadmap query overlay mismatch: "
            + "; ".join(failures)
        )
