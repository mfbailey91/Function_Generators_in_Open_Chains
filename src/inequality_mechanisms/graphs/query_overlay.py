"""Query overlays for Version-2 output-state graphs (Sprint V2.6, minimal).

This module implements a lightweight :class:`QueryOverlayGraph` wrapper that
adds explicit query nodes at requested (continuous) output configurations
and connects them to the corner nodes of the query's containing cell in the
base graph's discrete output lattice.

The implementation is intentionally narrow:

- it supports nonperiodic base graphs built from uniform output sampling;
- it validates inserted edges using the certified branch transition model
  via :func:`inequality_mechanisms.graphs.transitions.build_edge_trace_v2`.

It does *not* attempt to integrate obstacle fields or long-range connectivity.

Shared attachment helpers (:func:`resolve_query_endpoint` and related
primitives) are reused by :mod:`goal_set_query_overlay` without changing the
single-goal :class:`QueryOverlayGraph` API.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from inequality_mechanisms.graphs.embedded import EmbeddedPlanningGraph
from inequality_mechanisms.graphs.sampling import (
    SamplingDomain,
    TransitionParameterization,
)
from inequality_mechanisms.graphs.topology import TensorGridTopology
from inequality_mechanisms.graphs.transitions import EdgeTraceV2, build_edge_trace_v2
from inequality_mechanisms.mechanisms.operating_branch import OperatingBranch


@dataclass(frozen=True, slots=True)
class QueryNode:
    """One query node in the overlay graph."""

    node_id: int
    q: NDArray[np.float64]
    u: NDArray[np.float64]
    corner_neighbors: tuple[int, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "q": self.q.tolist(),
            "u": self.u.tolist(),
            "corner_neighbors": list(self.corner_neighbors),
        }


@dataclass(frozen=True, slots=True)
class ResolvedQueryEndpoint:
    """Resolved attachment of one continuous query endpoint onto a lattice.

    Parameters
    ----------
    base_node_id :
        Base lattice node id when the request deduplicates to an existing
        valid node; otherwise ``None`` and an overlay node is required.
    q :
        Canonical output configuration used for attachment.
    u :
        Actuator realization attached with ``q``.
    corner_neighbors :
        Transition-valid base corner node ids when an overlay node is needed;
        empty when deduplicated.
    requested_q :
        Caller-supplied output configuration before canonicalization.
    attachment_residual_q :
        ``||q_attached - requested_q||`` after canonical attachment.
    attachment_residual_u :
        ``||u_attached - requested_u||`` when ``requested_u`` was supplied.
    """

    base_node_id: int | None
    q: NDArray[np.float64]
    u: NDArray[np.float64]
    corner_neighbors: tuple[int, ...]
    requested_q: NDArray[np.float64]
    attachment_residual_q: float
    attachment_residual_u: float | None = None


def find_exact_base_node_for_q(
    base: EmbeddedPlanningGraph,
    canon_q: NDArray[np.float64],
    *,
    tol: float,
) -> int | None:
    """Return the lowest valid base node id matching ``canon_q``, if any."""
    base_q = np.asarray(base.q_nodes, dtype=np.float64)
    valid = np.asarray(base.valid_nodes, dtype=np.bool_)

    matches = np.all(
        np.isclose(base_q, canon_q[np.newaxis, :], atol=tol, rtol=0.0), axis=1
    )
    matches = np.where(valid, matches, False)
    if not np.any(matches):
        return None
    sentinel = np.iinfo(np.int64).max
    return int(
        np.argmin(np.where(matches, np.arange(base_q.shape[0]), sentinel))
    )


def bracket_indices_per_axis(
    base: EmbeddedPlanningGraph,
    canon_q: NDArray[np.float64],
    *,
    tol: float,
) -> list[int]:
    """Return per-axis lower bracket indices for the cell containing ``canon_q``."""
    if base.topology is None:  # pragma: no cover
        raise ValueError("base graph must provide a topology")
    shape = base.topology.shape
    dim = len(shape)
    if canon_q.shape != (dim,):
        raise ValueError(f"canon_q shape must be {(dim,)}, got {canon_q.shape}")

    brackets: list[int] = []
    for axis in range(dim):
        axis_values = base.axis_marginal(base.q_nodes, axis)
        lo_v = float(axis_values[0])
        hi_v = float(axis_values[-1])
        qv = float(canon_q[axis])
        if qv < lo_v - tol or qv > hi_v + tol:
            raise ValueError(
                f"requested q out of the base output range on axis {axis}: "
                f"{qv} not in [{lo_v}, {hi_v}]"
            )
        i = int(np.searchsorted(axis_values, qv, side="right") - 1)
        i = max(0, min(i, int(shape[axis]) - 2))
        brackets.append(i)
    return brackets


def candidate_corner_ids(
    base: EmbeddedPlanningGraph, canon_q: NDArray[np.float64]
) -> list[int]:
    """Return unordered cell-corner base node ids for ``canon_q``."""
    if base.topology is None:  # pragma: no cover
        raise ValueError("base graph must provide a topology")
    brackets = bracket_indices_per_axis(base, canon_q, tol=1e-12)
    corner_index_choices: list[tuple[int, int]] = [(i, i + 1) for i in brackets]
    corner_ids: list[int] = []
    for idx in itertools.product(*corner_index_choices):
        nid = base.topology.node_id(tuple(int(x) for x in idx))
        corner_ids.append(nid)
    return corner_ids


def validate_query_to_corner_edges(
    base: EmbeddedPlanningGraph,
    *,
    q: NDArray[np.float64],
    u: NDArray[np.float64],
    corner_ids: Iterable[int],
    edge_n_samples: int,
) -> list[int]:
    """Return the subset of ``corner_ids`` that are transition-valid."""
    accepted: list[int] = []
    for corner in corner_ids:
        if not bool(base.valid_nodes[corner]):
            continue
        q_b = base.q_state(corner)
        u_b = base.u_state(corner)
        trace = build_edge_trace_v2(
            base.branch,
            base.transition_parameterization,
            q,
            u,
            q_b,
            u_b,
            n_samples=edge_n_samples,
        )
        if trace.first_invalid_index is None and bool(np.all(trace.branch_valid)):
            accepted.append(int(corner))
    accepted.sort()
    return accepted


def resolve_query_endpoint(
    base: EmbeddedPlanningGraph,
    *,
    requested_q: NDArray[np.float64],
    requested_u: NDArray[np.float64] | None = None,
    dedup_tol: float,
    edge_n_samples: int,
) -> ResolvedQueryEndpoint:
    """Resolve one continuous endpoint onto the base lattice or an overlay stub.

    Parameters
    ----------
    base :
        Uniform-output ``EmbeddedPlanningGraph``.
    requested_q :
        Continuous output configuration to attach.
    requested_u :
        Optional actuator realization. When provided and an overlay node is
        created, this ``u`` is preferred over ``branch.inverse(q)`` so candidate
        provenance is preserved. Deduplicated base nodes keep the lattice ``u``.
    dedup_tol :
        Absolute tolerance for exact base-node matching.
    edge_n_samples :
        Samples used when validating query-to-corner transitions.
    """
    if base.sampling_domain != SamplingDomain.OUTPUT:
        raise ValueError(
            "query overlays currently support base graphs built from "
            "uniform OUTPUT sampling only"
        )
    if base.topology is None:  # pragma: no cover
        raise ValueError("base graph must provide a topology")

    q_vec = np.asarray(requested_q, dtype=np.float64)
    if q_vec.ndim != 1:
        raise ValueError("requested_q must be 1-D")
    canon_q = base.branch.output_space.canonicalize(q_vec)
    residual_q = float(np.linalg.norm(canon_q - q_vec))

    exact = find_exact_base_node_for_q(base, canon_q, tol=dedup_tol)
    if exact is not None:
        u_exact = np.asarray(base.u_state(exact), dtype=np.float64)
        residual_u = None
        if requested_u is not None:
            residual_u = float(
                np.linalg.norm(u_exact - np.asarray(requested_u, dtype=np.float64))
            )
        return ResolvedQueryEndpoint(
            base_node_id=exact,
            q=canon_q,
            u=u_exact,
            corner_neighbors=(),
            requested_q=np.array(q_vec, copy=True),
            attachment_residual_q=residual_q,
            attachment_residual_u=residual_u,
        )

    if requested_u is not None:
        u = np.asarray(requested_u, dtype=np.float64)
        if u.shape != canon_q.shape:
            raise ValueError(
                f"requested_u shape must match q shape {canon_q.shape}, got {u.shape}"
            )
    else:
        u = np.asarray(base.branch.inverse(canon_q), dtype=np.float64)

    candidate_corners = candidate_corner_ids(base, canon_q)
    accepted_corners = validate_query_to_corner_edges(
        base,
        q=canon_q,
        u=u,
        corner_ids=candidate_corners,
        edge_n_samples=edge_n_samples,
    )
    if not accepted_corners:
        raise ValueError(
            "query has no transition-valid corner neighbors; requested_q likely "
            "lies too close to a certified boundary"
        )
    residual_u = None
    if requested_u is not None:
        residual_u = float(np.linalg.norm(u - np.asarray(requested_u, dtype=np.float64)))
    return ResolvedQueryEndpoint(
        base_node_id=None,
        q=canon_q,
        u=u,
        corner_neighbors=tuple(accepted_corners),
        requested_q=np.array(q_vec, copy=True),
        attachment_residual_q=residual_q,
        attachment_residual_u=residual_u,
    )


class QueryOverlayGraph:
    """Version-2 SearchGraph wrapper with explicit query nodes.

    The wrapper preserves base graph adjacency among base nodes and adds
    additional edges from each query node to validated corner nodes of the
    query's containing output-space cell.
    """

    def __init__(
        self,
        *,
        base: EmbeddedPlanningGraph,
        start_q: NDArray[np.float64],
        goal_q: NDArray[np.float64],
        dedup_tol: float = 1e-12,
        edge_n_samples: int = 17,
    ) -> None:
        if base.sampling_domain != SamplingDomain.OUTPUT:
            raise ValueError(
                "QueryOverlayGraph currently supports base graphs built from "
                "uniform OUTPUT sampling only"
            )
        if base.topology is None:  # pragma: no cover
            raise ValueError("base graph must provide a topology")

        self._base = base
        self._edge_n_samples = int(edge_n_samples)
        self._output_space = base.branch.output_space

        start_resolved = resolve_query_endpoint(
            base,
            requested_q=start_q,
            dedup_tol=dedup_tol,
            edge_n_samples=self._edge_n_samples,
        )
        goal_resolved = resolve_query_endpoint(
            base,
            requested_q=goal_q,
            dedup_tol=dedup_tol,
            edge_n_samples=self._edge_n_samples,
        )

        # Deterministically allocate compact overlay node ids for the
        # non-deduplicated endpoints, in role order: start then goal.
        overlay_nodes: list[QueryNode] = []
        overlay_id_cursor = base.node_count

        if start_resolved.base_node_id is not None:
            start_node_id = start_resolved.base_node_id
        else:
            start_node_id = overlay_id_cursor
            overlay_nodes.append(
                QueryNode(
                    node_id=overlay_id_cursor,
                    q=start_resolved.q,
                    u=start_resolved.u,
                    corner_neighbors=start_resolved.corner_neighbors,
                )
            )
            overlay_id_cursor += 1

        if goal_resolved.base_node_id is not None:
            goal_node_id = goal_resolved.base_node_id
        else:
            goal_node_id = overlay_id_cursor
            overlay_nodes.append(
                QueryNode(
                    node_id=overlay_id_cursor,
                    q=goal_resolved.q,
                    u=goal_resolved.u,
                    corner_neighbors=goal_resolved.corner_neighbors,
                )
            )
            overlay_id_cursor += 1

        self._start_node_id = int(start_node_id)
        self._goal_node_id = int(goal_node_id)

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

        # Map base-corner -> overlay query nodes that connect to it.
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
            # Base neighbor ids are always < overlay ids, so concatenation is
            # already deterministic.
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

        # Fast path for base-to-base edges.
        if a < self._base.node_count and b < self._base.node_count:
            return self._base.edge_trace(a, b, n_samples=n_samples)

        q_a = self.q_state(a)
        q_b = self.q_state(b)
        u_a = self.u_state(a)
        u_b = self.u_state(b)

        return build_edge_trace_v2(
            self._base.branch,
            self._base.transition_parameterization,
            q_a,
            u_a,
            q_b,
            u_b,
            n_samples=n_samples,
        )

    @property
    def start_node_id(self) -> int:
        return self._start_node_id

    @property
    def goal_node_id(self) -> int:
        return self._goal_node_id

    # ---------------------------------------------------------------------
    # Query resolution helpers (compat wrappers over module primitives)
    # ---------------------------------------------------------------------

    def _find_exact_base_node_for_q(
        self, canon_q: NDArray[np.float64], *, tol: float
    ) -> int | None:
        return find_exact_base_node_for_q(self._base, canon_q, tol=tol)

    def _bracket_indices_per_axis(
        self, canon_q: NDArray[np.float64], *, tol: float
    ) -> list[int]:
        return bracket_indices_per_axis(self._base, canon_q, tol=tol)

    def _candidate_corner_ids(
        self, canon_q: NDArray[np.float64]
    ) -> list[int]:
        return candidate_corner_ids(self._base, canon_q)

    def _validate_query_to_corner_edges(
        self,
        *,
        q: NDArray[np.float64],
        u: NDArray[np.float64],
        corner_ids: Iterable[int],
    ) -> list[int]:
        return validate_query_to_corner_edges(
            self._base,
            q=q,
            u=u,
            corner_ids=corner_ids,
            edge_n_samples=self._edge_n_samples,
        )

    def _resolve_query_endpoint(
        self,
        *,
        requested_q: NDArray[np.float64],
        dedup_tol: float,
    ) -> tuple[int | None, NDArray[np.float64], NDArray[np.float64], list[int]]:
        resolved = resolve_query_endpoint(
            self._base,
            requested_q=requested_q,
            dedup_tol=dedup_tol,
            edge_n_samples=self._edge_n_samples,
        )
        return (
            resolved.base_node_id,
            resolved.q,
            resolved.u,
            list(resolved.corner_neighbors),
        )
