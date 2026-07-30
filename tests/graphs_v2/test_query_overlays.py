from __future__ import annotations

import numpy as np
import pytest
from tests.graphs_v2._fixtures import affine_1d_branch

from inequality_mechanisms.graphs import QueryOverlayGraph
from inequality_mechanisms.graphs.embedded import EmbeddedPlanningGraph
from inequality_mechanisms.search.core import best_first_search
from inequality_mechanisms.search.v2_objectives import resolve_v2_objective


def _base_graph() -> EmbeddedPlanningGraph:
    return EmbeddedPlanningGraph.from_uniform_output(affine_1d_branch(), shape=(6,))


def test_query_midpoint_connects_to_two_corner_nodes_1d() -> None:
    base = _base_graph()

    q1 = base.q_state(1)
    q2 = base.q_state(2)
    q_mid = 0.5 * (q1 + q2)

    # Make goal an exact base node so only one overlay node is needed.
    goal_id = 4
    goal_q = base.q_state(goal_id)

    overlay = QueryOverlayGraph(
        base=base, start_q=q_mid, goal_q=goal_q, dedup_tol=1e-12, edge_n_samples=17
    )

    assert overlay.node_count == base.node_count + 1
    assert overlay.start_node_id == base.node_count
    assert overlay.goal_node_id == goal_id

    assert overlay.neighbors(overlay.start_node_id) == (1, 2)


def test_dijkstra_on_overlay_finds_path() -> None:
    base = _base_graph()
    start_q = 0.5 * (base.q_state(1) + base.q_state(2))
    goal_id = 5
    goal_q = base.q_state(goal_id)

    overlay = QueryOverlayGraph(base=base, start_q=start_q, goal_q=goal_q)
    objective = resolve_v2_objective(
        overlay, overlay.goal_node_id, "output_euclidean", "zero"
    )

    result = best_first_search(
        overlay,
        overlay.start_node_id,
        overlay.goal_node_id,
        edge_cost=objective.edge_cost,
        heuristic=objective.heuristic,
    )
    assert result.found
    assert result.cost >= 0.0
    assert result.path[0] == overlay.start_node_id
    assert result.path[-1] == overlay.goal_node_id


def test_exact_query_state_is_deduplicated() -> None:
    base = _base_graph()
    start_id = 2
    goal_id = 4
    overlay = QueryOverlayGraph(
        base=base, start_q=base.q_state(start_id), goal_q=base.q_state(goal_id)
    )
    assert overlay.node_count == base.node_count
    assert overlay.start_node_id == start_id
    assert overlay.goal_node_id == goal_id


def test_out_of_range_query_is_rejected() -> None:
    base = _base_graph()
    upper = float(base.branch.output_space.upper[0])
    with pytest.raises(
        ValueError,
        match=(
            "requested q out of the base output range|"
            "outside the branch output range"
        ),
    ):
        _ = QueryOverlayGraph(
            base=base,
            start_q=np.array([upper + 0.1], dtype=np.float64),
            goal_q=base.q_state(3),
        )

