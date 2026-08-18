"""Compile one final paired search topology (V4.2B / V4-224).

Evaluate every candidate local motion through every paired arm, classify
each weight under ADR-030, and admit an edge only when every arm reports a
finite nonnegative cost. Do not compile two final graphs and intersect them
after the fact.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Mapping

from inequality_mechanisms.adapters.finite_search_edges import (
    ADMITTED_LOCAL_MOTION,
    UNAVAILABLE_LOCAL_MOTION,
    _FilteredSearchGraph,
    classify_edge_weight,
)
from inequality_mechanisms.graphs.paired_q_planning import PairedQPlanningGraph
from inequality_mechanisms.search.protocol import EdgeCost, SearchGraph

AVAILABLE_LOCAL_MOTION = "available_local_motion"


@dataclass(frozen=True)
class EdgeAdmission:
    """Per-arm classification of one directed candidate edge.

    Attributes
    ----------
    candidate_edge_status :
        ``available_local_motion`` or ``unavailable_local_motion``.
    weight :
        Raw evaluator result for that arm.
    """

    candidate_edge_status: str
    weight: float


@dataclass(frozen=True)
class PairedCompiledSearchGraph:
    """One admitted planner graph with per-arm cached edge costs.

    Attributes
    ----------
    graph :
        Common adjacency. ``neighbors()`` is identical for every arm.
    edge_costs :
        Cached finite costs keyed by mechanism name. Lookups raise for
        edges that were not admitted.
    admitted_edge_ids :
        Directed admitted edges in candidate-walk order.
    rejected_candidates :
        Directed candidates omitted because at least one arm was
        unavailable. Every arm's classification is retained.
    candidate_edge_ids :
        Directed candidate edges before common admission.
    candidate_topology_digest :
        SHA-256 of the candidate edge encoding.
    admitted_topology_digest :
        SHA-256 of the admitted edge encoding.
    """

    graph: SearchGraph
    edge_costs: Mapping[str, EdgeCost]
    admitted_edge_ids: tuple[tuple[int, int], ...]
    rejected_candidates: Mapping[tuple[int, int], Mapping[str, EdgeAdmission]]
    candidate_edge_ids: tuple[tuple[int, int], ...]
    candidate_topology_digest: str
    admitted_topology_digest: str


def _topology_digest(edge_ids: tuple[tuple[int, int], ...]) -> str:
    payload = "".join(f"{u},{v}\n" for u, v in edge_ids)
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def _cached_edge_cost(
    name: str,
    cache: Mapping[tuple[int, int], float],
) -> EdgeCost:
    def compiled_cost(u: int, v: int) -> float:
        key = (int(u), int(v))
        cached = cache.get(key)
        if cached is None:
            raise ValueError(
                f"edge ({key[0]}, {key[1]}) is not an admitted finite "
                f"search edge for {name}"
            )
        return float(cached)

    return compiled_cost


def compile_paired_finite_neighbors(
    graph: SearchGraph,
    edge_costs: Mapping[str, EdgeCost],
) -> PairedCompiledSearchGraph:
    """Admit one common edge set from jointly classified arm costs.

    Parameters
    ----------
    graph :
        Shared candidate ``SearchGraph``. Not mutated.
    edge_costs :
        Named candidate evaluators. At least two names are required.

    Returns
    -------
    PairedCompiledSearchGraph
        Common admitted adjacency and per-arm cached costs.

    Raises
    ------
    ValueError
        If fewer than two evaluators are supplied, or any arm reports
        ``NaN``, ``-inf``, or a finite negative weight.
    """
    names = tuple(edge_costs)
    if len(names) < 2:
        raise ValueError(
            "compile_paired_finite_neighbors requires at least two edge-cost maps"
        )
    if len(set(names)) != len(names):
        raise ValueError("edge_costs keys must be unique")

    n = int(graph.node_count)
    valid_nodes = tuple(bool(graph.node_is_valid(i)) for i in range(n))
    kept: dict[int, list[int]] = {i: [] for i in range(n)}
    candidate_ids: list[tuple[int, int]] = []
    admitted_ids: list[tuple[int, int]] = []
    costs: dict[str, dict[tuple[int, int], float]] = {name: {} for name in names}
    rejected: dict[tuple[int, int], dict[str, EdgeAdmission]] = {}

    for u in range(n):
        if not valid_nodes[u]:
            continue
        for raw_v in graph.neighbors(u):
            v = int(raw_v)
            key = (u, v)
            candidate_ids.append(key)
            weights: dict[str, float] = {}
            decisions: dict[str, str] = {}
            for name in names:
                weight = float(edge_costs[name](u, v))
                decisions[name] = classify_edge_weight(weight, u=u, v=v)
                weights[name] = weight
            if any(
                decision == UNAVAILABLE_LOCAL_MOTION
                for decision in decisions.values()
            ):
                rejected[key] = {
                    name: EdgeAdmission(
                        candidate_edge_status=(
                            UNAVAILABLE_LOCAL_MOTION
                            if decisions[name] == UNAVAILABLE_LOCAL_MOTION
                            else AVAILABLE_LOCAL_MOTION
                        ),
                        weight=weights[name],
                    )
                    for name in names
                }
                continue
            if any(decision != ADMITTED_LOCAL_MOTION for decision in decisions.values()):
                raise ValueError(
                    f"edge ({u}, {v}) produced an unclassified ADR-030 result"
                )
            admitted_ids.append(key)
            kept[u].append(v)
            for name in names:
                costs[name][key] = weights[name]

    candidate_edge_ids = tuple(candidate_ids)
    admitted_edge_ids = tuple(admitted_ids)
    return PairedCompiledSearchGraph(
        graph=_FilteredSearchGraph(
            node_count=n,
            valid_nodes=valid_nodes,
            adjacency={i: tuple(kept[i]) for i in range(n)},
        ),
        edge_costs={
            name: _cached_edge_cost(name, costs[name]) for name in names
        },
        admitted_edge_ids=admitted_edge_ids,
        rejected_candidates=rejected,
        candidate_edge_ids=candidate_edge_ids,
        candidate_topology_digest=_topology_digest(candidate_edge_ids),
        admitted_topology_digest=_topology_digest(admitted_edge_ids),
    )


def compile_paired_q_search_graph(
    paired: PairedQPlanningGraph,
    edge_costs: Mapping[str, EdgeCost],
) -> PairedCompiledSearchGraph:
    """Compile a ``PairedQPlanningGraph`` onto one admitted search topology.

    Parameters
    ----------
    paired :
        Shared-Q candidate graph. One arm supplies candidate adjacency.
    edge_costs :
        Evaluators whose keys must match ``paired.arms``.

    Returns
    -------
    PairedCompiledSearchGraph
        Common admitted adjacency and per-arm cached costs.

    Raises
    ------
    ValueError
        If the cost keys do not match the paired arms.
    """
    arm_names = set(paired.arms)
    cost_names = set(edge_costs)
    if arm_names != cost_names:
        raise ValueError(
            "edge_costs keys must match paired arms: "
            f"arms={sorted(arm_names)} costs={sorted(cost_names)}"
        )
    reference = next(iter(paired.arms.values()))
    return compile_paired_finite_neighbors(reference, edge_costs)
