"""Narrow graph-solver protocol for sequenced production campaigns.

Sprint V2.10 implements Dijkstra and V2.11 adds A*. Each campaign still
selects exactly one solver so solver effects remain isolated. Sampling-based
solvers remain deferred behind the same protocol.
"""

from __future__ import annotations

from collections.abc import Collection
from typing import Protocol, runtime_checkable

from inequality_mechanisms.search.protocol import GoalTest, SearchGraph
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
        goal: int | None,
        objective: V2PlanningObjective,
        *,
        goal_node_ids: Collection[int] | None = None,
        goal_test: GoalTest | None = None,
        record_expanded: bool = False,
    ) -> SearchResult:
        """Return one exact search result for one active goal representation."""


class DijkstraGraphSolver:
    """Uninformed exact search wrapping :func:`best_first_search`."""

    solver_id = "dijkstra"
    heuristic_id = None
    solver_schema_version = 1

    def solve(
        self,
        graph: SearchGraph,
        start: int,
        goal: int | None,
        objective: V2PlanningObjective,
        *,
        goal_node_ids: Collection[int] | None = None,
        goal_test: GoalTest | None = None,
        record_expanded: bool = False,
    ) -> SearchResult:
        from inequality_mechanisms.search.core import best_first_search

        return best_first_search(
            graph,
            start,
            goal,
            goal_node_ids=goal_node_ids,
            goal_test=goal_test,
            edge_cost=objective.edge_cost,
            heuristic=objective.heuristic,
            record_expanded=record_expanded,
        )


class AStarGraphSolver:
    """Exact A* using the frozen admissible input-Euclidean heuristic."""

    solver_id = "astar"
    heuristic_id = "input_euclidean"
    solver_schema_version = 1

    def solve(
        self,
        graph: SearchGraph,
        start: int,
        goal: int | None,
        objective: V2PlanningObjective,
        *,
        goal_node_ids: Collection[int] | None = None,
        goal_test: GoalTest | None = None,
        record_expanded: bool = False,
    ) -> SearchResult:
        from inequality_mechanisms.search.core import best_first_search

        return best_first_search(
            graph,
            start,
            goal,
            goal_node_ids=goal_node_ids,
            goal_test=goal_test,
            edge_cost=objective.edge_cost,
            heuristic=objective.heuristic,
            record_expanded=record_expanded,
        )


def production_graph_solver(algorithm: str) -> GraphSolver:
    """Resolve the single exact graph solver selected for one campaign."""
    if algorithm == "dijkstra":
        return DijkstraGraphSolver()
    if algorithm == "astar":
        return AStarGraphSolver()
    raise ValueError(f"unknown production graph solver {algorithm!r}")


def production_dijkstra_solver() -> DijkstraGraphSolver:
    """Backward-compatible V2.10 Dijkstra factory."""
    return DijkstraGraphSolver()
