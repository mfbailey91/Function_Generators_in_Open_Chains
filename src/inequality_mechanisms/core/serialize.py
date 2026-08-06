"""Serialization helpers for Version 3 core types."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from inequality_mechanisms.core.goals import GoalResidual
from inequality_mechanisms.core.planner import PlannerCapabilities
from inequality_mechanisms.core.results import (
    PlanningResult,
    PlanningStatus,
    ResultProvenance,
    Trajectory,
)
from inequality_mechanisms.core.state import PhysicalState


def _arr_to_list(x: np.ndarray) -> list[float]:
    return [float(v) for v in np.asarray(x, dtype=np.float64).tolist()]


def physical_state_to_dict(state: PhysicalState) -> dict[str, Any]:
    """Serialize a physical state to a JSON-friendly mapping."""
    return {
        "u": _arr_to_list(state.u),
        "q": _arr_to_list(state.q),
        "assembly_state": dict(state.assembly_state),
        "auxiliary_state": dict(state.auxiliary_state),
    }


def physical_state_from_dict(data: Mapping[str, Any]) -> PhysicalState:
    """Deserialize a physical state from a mapping."""
    return PhysicalState(
        u=np.asarray(data["u"], dtype=np.float64),
        q=np.asarray(data["q"], dtype=np.float64),
        assembly_state=dict(data.get("assembly_state", {})),
        auxiliary_state=dict(data.get("auxiliary_state", {})),
    )


def planner_capabilities_to_dict(caps: PlannerCapabilities) -> dict[str, Any]:
    """Serialize planner capabilities."""
    return {
        "deterministic": caps.deterministic,
        "reproducible_with_seed": caps.reproducible_with_seed,
        "multi_query": caps.multi_query,
        "optimizing": caps.optimizing,
        "probabilistically_complete": caps.probabilistically_complete,
        "asymptotically_optimal": caps.asymptotically_optimal,
        "requires_metric_space": caps.requires_metric_space,
        "supports_optimization_objective": caps.supports_optimization_objective,
        "supports_goal_region": caps.supports_goal_region,
        "supports_goal_sampling": caps.supports_goal_sampling,
        "supports_multi_start": caps.supports_multi_start,
        "supports_path_constraints": caps.supports_path_constraints,
        "supports_approximate_solution": caps.supports_approximate_solution,
        "supports_incremental_solutions": caps.supports_incremental_solutions,
        "reports_graph_exploration": caps.reports_graph_exploration,
        "supports_exact_start": caps.supports_exact_start,
    }


def planner_capabilities_from_dict(data: Mapping[str, Any]) -> PlannerCapabilities:
    """Deserialize planner capabilities."""
    return PlannerCapabilities(**dict(data))


def planning_result_to_dict(result: PlanningResult) -> dict[str, Any]:
    """Serialize a planning result."""
    traj = None
    if result.trajectory is not None:
        traj = {
            "states": [physical_state_to_dict(s) for s in result.trajectory.states]
        }
    residual = None
    if result.final_goal_residual is not None:
        r = result.final_goal_residual
        residual = {
            "primary": float(r.primary),
            "components": None
            if r.components is None
            else _arr_to_list(r.components),
            "extras": dict(r.extras),
        }
    return {
        "status": result.status.value,
        "trajectory": traj,
        "selected_goal_state": None
        if result.selected_goal_state is None
        else physical_state_to_dict(result.selected_goal_state),
        "setup_time_s": result.setup_time_s,
        "preprocessing_time_s": result.preprocessing_time_s,
        "query_time_s": result.query_time_s,
        "postprocessing_time_s": result.postprocessing_time_s,
        "total_wall_time_s": result.total_wall_time_s,
        "objective_cost": result.objective_cost,
        "path_length_u": result.path_length_u,
        "path_length_q": result.path_length_q,
        "path_length_x": result.path_length_x,
        "state_validity_checks": result.state_validity_checks,
        "motion_validity_checks": result.motion_validity_checks,
        "collision_checks": result.collision_checks,
        "task_class": result.task_class,
        "final_goal_residual": residual,
        "planner_metrics": dict(result.planner_metrics),
        "provenance": {
            "architecture_version": result.provenance.architecture_version,
            "code_revision": result.provenance.code_revision,
            "planner_id": result.provenance.planner_id,
            "extras": dict(result.provenance.extras),
        },
    }


def planning_result_from_dict(data: Mapping[str, Any]) -> PlanningResult:
    """Deserialize a planning result."""
    traj_data = data.get("trajectory")
    trajectory = None
    if traj_data is not None:
        trajectory = Trajectory(
            states=tuple(
                physical_state_from_dict(s) for s in traj_data["states"]
            )
        )
    selected = data.get("selected_goal_state")
    residual_data = data.get("final_goal_residual")
    residual = None
    if residual_data is not None:
        comps = residual_data.get("components")
        residual = GoalResidual(
            primary=float(residual_data["primary"]),
            components=None if comps is None else np.asarray(comps, dtype=np.float64),
            extras=dict(residual_data.get("extras", {})),
        )
    prov = data["provenance"]
    return PlanningResult(
        status=PlanningStatus(data["status"]),
        trajectory=trajectory,
        selected_goal_state=None
        if selected is None
        else physical_state_from_dict(selected),
        setup_time_s=data.get("setup_time_s"),
        preprocessing_time_s=data.get("preprocessing_time_s"),
        query_time_s=data.get("query_time_s"),
        postprocessing_time_s=data.get("postprocessing_time_s"),
        total_wall_time_s=float(data["total_wall_time_s"]),
        objective_cost=data.get("objective_cost"),
        path_length_u=data.get("path_length_u"),
        path_length_q=data.get("path_length_q"),
        path_length_x=data.get("path_length_x"),
        state_validity_checks=data.get("state_validity_checks"),
        motion_validity_checks=data.get("motion_validity_checks"),
        collision_checks=data.get("collision_checks"),
        task_class=data.get("task_class"),
        final_goal_residual=residual,
        planner_metrics=dict(data.get("planner_metrics", {})),
        provenance=ResultProvenance(
            architecture_version=int(prov["architecture_version"]),
            code_revision=prov.get("code_revision"),
            planner_id=prov.get("planner_id"),
            extras=dict(prov.get("extras", {})),
        ),
    )
