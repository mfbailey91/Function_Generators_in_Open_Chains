"""Compile unavailable local motions out of search adjacency (V4.2B / V4-225).

Generic Dijkstra/A* remain strict: they reject nonfinite and negative
weights. This adapter evaluates candidate edges first and classifies
each weight under ADR-030:

- finite nonnegative costs are admitted and cached;
- ``+inf`` is omitted as unavailable local motion;
- ``NaN``, ``-inf``, and finite negative values raise.

Do not treat ``not math.isfinite(weight)`` as the unavailable-motion test.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Mapping

from inequality_mechanisms.search.protocol import EdgeCost, SearchGraph

UNAVAILABLE_LOCAL_MOTION = "unavailable_local_motion"
ADMITTED_LOCAL_MOTION = "admit"
EdgeWeightDecision = Literal["admit", "unavailable_local_motion"]


def classify_edge_weight(
    weight: float,
    *,
    u: int | None = None,
    v: int | None = None,
) -> EdgeWeightDecision:
    """Classify one candidate edge weight under ADR-030.

    Parameters
    ----------
    weight :
        Raw evaluator result.
    u, v :
        Optional directed edge endpoints included in error messages.

    Returns
    -------
    {"admit", "unavailable_local_motion"}
        ``admit`` for finite nonnegative costs; unavailable for ``+inf``.

    Raises
    ------
    ValueError
        If ``weight`` is ``NaN``, ``-inf``, or finite negative.
    """
    where = f" from {u} to {v}" if u is not None and v is not None else ""
    if math.isnan(weight):
        raise ValueError(f"edge cost{where} is NaN")
    if weight == -math.inf:
        raise ValueError(f"edge cost{where} is negative infinity")
    if weight == math.inf:
        return UNAVAILABLE_LOCAL_MOTION
    if weight < 0.0:
        raise ValueError(f"edge cost{where} is negative: {weight}")
    return ADMITTED_LOCAL_MOTION


class _FilteredSearchGraph:
    """SearchGraph whose adjacency contains only compiled finite edges."""

    def __init__(
        self,
        *,
        node_count: int,
        valid_nodes: tuple[bool, ...],
        adjacency: Mapping[int, tuple[int, ...]],
    ) -> None:
        self._node_count = int(node_count)
        self._valid_nodes = valid_nodes
        self._adjacency = dict(adjacency)

    @property
    def node_count(self) -> int:
        return self._node_count

    def node_is_valid(self, node_id: int) -> bool:
        idx = int(node_id)
        if idx < 0 or idx >= self._node_count:
            return False
        return bool(self._valid_nodes[idx])

    def neighbors(self, node_id: int) -> tuple[int, ...]:
        return self._adjacency.get(int(node_id), ())


@dataclass(frozen=True)
class CompiledFiniteNeighbors:
    """Filtered search graph plus cached finite edge costs.

    Attributes
    ----------
    graph :
        Adjacency contains only edges with finite nonnegative cost.
    edge_cost :
        Cached cost for admitted edges. Does not return ``+inf``.
    rejected_candidates :
        Directed candidate edges omitted as unavailable local motions.
    """

    graph: SearchGraph
    edge_cost: EdgeCost
    rejected_candidates: Mapping[tuple[int, int], Mapping[str, str]]


def compile_finite_neighbors(
    graph: SearchGraph,
    edge_cost: EdgeCost,
) -> CompiledFiniteNeighbors:
    """Omit unavailable candidate edges before generic search.

    Parameters
    ----------
    graph :
        Raw search graph. Not mutated.
    edge_cost :
        Candidate edge evaluator. Positive infinity is omitted as
        unavailable local motion. ``NaN``, negative infinity, and
        finite negative values raise.

    Returns
    -------
    CompiledFiniteNeighbors
        Filtered adjacency, cached finite costs, and rejection records.

    Raises
    ------
    ValueError
        If a candidate edge has a ``NaN``, ``-inf``, or finite negative
        weight.
    """
    n = int(graph.node_count)
    valid_nodes = tuple(bool(graph.node_is_valid(i)) for i in range(n))
    adjacency: dict[int, tuple[int, ...]] = {}
    costs: dict[tuple[int, int], float] = {}
    rejected: dict[tuple[int, int], dict[str, str]] = {}

    for u in range(n):
        kept: list[int] = []
        if valid_nodes[u]:
            for raw_v in graph.neighbors(u):
                v = int(raw_v)
                weight = float(edge_cost(u, v))
                decision = classify_edge_weight(weight, u=u, v=v)
                if decision == UNAVAILABLE_LOCAL_MOTION:
                    rejected[(u, v)] = {
                        "candidate_edge_status": UNAVAILABLE_LOCAL_MOTION
                    }
                    continue
                kept.append(v)
                costs[(u, v)] = weight
        adjacency[u] = tuple(kept)

    def compiled_cost(u: int, v: int) -> float:
        key = (int(u), int(v))
        cached = costs.get(key)
        if cached is None:
            raise ValueError(
                f"edge ({key[0]}, {key[1]}) is not an admitted finite search edge"
            )
        return float(cached)

    return CompiledFiniteNeighbors(
        graph=_FilteredSearchGraph(
            node_count=n,
            valid_nodes=valid_nodes,
            adjacency=adjacency,
        ),
        edge_cost=compiled_cost,
        rejected_candidates=rejected,
    )
