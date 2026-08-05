"""Narrow graph-solver protocol for sequenced production campaigns.

Sprint V2.10 implements Dijkstra only. Later campaigns may add A* or
sampling-based solvers that satisfy the same protocol without changing the
production runner's one-solver-per-campaign rule.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from inequality_mechanisms.search.protocol import SearchGraph
from inequality_mechanisms.search.result import SearchResult
from inequality_mechanisms.search.v2_objectives import V2PlanningObjective


@runtime_checkable
class GraphSolver(Protocol):
    """One discrete-graph solver identity plus a ``solve`` entry point."""

    @property
    def solver_id(self) -> str:
        """Stable solver registry name (for example ``dijkstra``)."""

    @property
    def heuristic_id(self) -> str | None:
        """Heuristic registry name, or ``None`` for uninformed search."""

    @property
    def solver_schema_version(self) -> int:
        """Result-metadata schema version for this solver family."""

    def solve(
        self,
        graph: SearchGraph,
        start: int,
        goal: int,
        objective: V2PlanningObjective,
        *,
        record_expanded: bool = False,
    ) -> SearchResult:
        """Return one search result on ``graph`` from ``start`` to ``goal``."""


class DijkstraGraphSolver:
    """Uninformed exact search wrapping :func:`best_first_search`."""

    solver_id = "dijkstra"
    heuristic_id = None
    solver_schema_version = 1

    def solve(
        self,
        graph: SearchGraph,
        start: int,
        goal: int,
        objective: V2PlanningObjective,
        *,
        record_expanded: bool = False,
    ) -> SearchResult:
        from inequality_mechanisms.search.core import best_first_search

        return best_first_search(
            graph,
            start,
            goal,
            edge_cost=objective.edge_cost,
            heuristic=objective.heuristic,
            record_expanded=record_expanded,
        )


def production_dijkstra_solver() -> DijkstraGraphSolver:
    """Return the only solver permitted in the V2.10 production campaign."""
    return DijkstraGraphSolver()
