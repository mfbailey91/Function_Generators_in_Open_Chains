"""Extract namespaced OMPL PlannerData summaries (V3-504)."""

from __future__ import annotations

from typing import Any


def planner_data_metrics(si: Any, planner: Any) -> dict[str, Any]:
    """Return a compact ``planner_metrics['ompl']``-ready PlannerData summary."""
    try:
        from inequality_mechanisms.adapters.ompl._availability import require_ompl

        ob, _og = require_ompl()
        data = ob.PlannerData(si)
        planner.getPlannerData(data)
        return {
            "num_vertices": int(data.numVertices()),
            "num_edges": int(data.numEdges()),
            "num_start_vertices": int(data.numStartVertices()),
            "num_goal_vertices": int(data.numGoalVertices()),
        }
    except Exception as exc:  # pragma: no cover - binding differences
        return {
            "planner_data_error": str(exc),
            "num_vertices": None,
            "num_edges": None,
        }
