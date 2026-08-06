"""Version 3 lattice edge costs via continuous local-motion connectors (V3.3)."""

from __future__ import annotations

import math
from typing import Any, Literal

import numpy as np

from inequality_mechanisms.core.local_motion import (
    InputLinearMotion,
    LocalMotionModel,
    OutputLinearMotion,
)
from inequality_mechanisms.core.objectives import ActuatorTravelObjective
from inequality_mechanisms.core.robot import RobotModel
from inequality_mechanisms.core.scene import PlanningScene
from inequality_mechanisms.core.state import PhysicalState
from inequality_mechanisms.graphs.sampling import TransitionParameterization
from inequality_mechanisms.search.protocol import EdgeCost, Heuristic
from inequality_mechanisms.search.v2_objectives import (
    V2PlanningObjective,
    actuator_travel_edge_cost,
    input_euclidean_heuristic_v2,
    resolve_v2_objective,
    zero_heuristic_v2,
)

EdgeCostMode = Literal["endpoint", "integrated"]


def _states_from_nodes(
    graph: Any,
    a: int,
    b: int,
    *,
    assembly_state: dict[str, Any] | None,
) -> tuple[PhysicalState, PhysicalState]:
    assembly = dict(assembly_state) if assembly_state is not None else {}
    start = PhysicalState(
        u=np.asarray(graph.u_state(a), dtype=np.float64),
        q=np.asarray(graph.q_state(a), dtype=np.float64),
        assembly_state=assembly,
        auxiliary_state={"lattice_node_id": int(a)},
    )
    end = PhysicalState(
        u=np.asarray(graph.u_state(b), dtype=np.float64),
        q=np.asarray(graph.q_state(b), dtype=np.float64),
        assembly_state=assembly,
        auxiliary_state={"lattice_node_id": int(b)},
    )
    return start, end


def connector_for_graph(
    graph: Any,
    robot: RobotModel,
    *,
    n_samples: int = 32,
) -> LocalMotionModel:
    """Select input- or output-linear connector from graph parameterization."""
    param = getattr(graph, "transition_parameterization", None)
    if param is TransitionParameterization.INPUT_LINEAR:
        return InputLinearMotion(robot=robot, n_samples=n_samples)
    return OutputLinearMotion(robot=robot, n_samples=n_samples)


def integrated_actuator_edge_cost(
    graph: Any,
    robot: RobotModel,
    *,
    scene: PlanningScene | None = None,
    n_samples: int = 32,
    assembly_state: dict[str, Any] | None = None,
) -> EdgeCost:
    """Build integrated actuator arc-length edge costs via V3.2 connectors.

    Failed connections or scene-invalid motions return ``+inf`` so search
    avoids those edges without mutating neighbor lists.
    """
    connector = connector_for_graph(graph, robot, n_samples=n_samples)
    objective = ActuatorTravelObjective()
    cache: dict[tuple[int, int], float] = {}

    def cost(a: int, b: int) -> float:
        key = (a, b) if a <= b else (b, a)
        cached = cache.get(key)
        if cached is not None:
            return cached
        start, end = _states_from_nodes(
            graph, a, b, assembly_state=assembly_state
        )
        motion = connector.connect(start, end)
        if motion is None:
            value = math.inf
        elif scene is not None and not scene.motion_is_valid(motion):
            value = math.inf
        else:
            value = float(objective.motion_cost(motion))
        cache[key] = value
        return value

    return cost


def path_actuator_length(
    graph: Any,
    path: tuple[int, ...] | list[int],
    *,
    robot: RobotModel,
    edge_cost_mode: EdgeCostMode,
    scene: PlanningScene | None = None,
    n_samples: int = 32,
    assembly_state: dict[str, Any] | None = None,
) -> float:
    """Sum actuator path length along ``path`` under the declared cost mode."""
    if len(path) < 2:
        return 0.0
    if edge_cost_mode == "endpoint":
        edge = actuator_travel_edge_cost(graph)
    else:
        edge = integrated_actuator_edge_cost(
            graph,
            robot,
            scene=scene,
            n_samples=n_samples,
            assembly_state=assembly_state,
        )
    total = 0.0
    for a, b in zip(path[:-1], path[1:]):
        total += float(edge(int(a), int(b)))
    return float(total)


def resolve_lattice_search_objective(
    graph: Any,
    goal_id: int,
    *,
    edge_cost_mode: EdgeCostMode,
    robot: RobotModel,
    algorithm: str,
    scene: PlanningScene | None = None,
    n_samples: int = 32,
    assembly_state: dict[str, Any] | None = None,
) -> V2PlanningObjective:
    """Return a V2-compatible planning objective for lattice Dijkstra/A*.

    Endpoint mode reuses ``resolve_v2_objective(..., "actuator_travel")``.
    Integrated mode wraps continuous connector costs with the same admissible
    ``input_euclidean`` heuristic (endpoint lower bound).
    """
    if edge_cost_mode == "endpoint":
        return resolve_v2_objective(
            graph,
            goal_id,
            "actuator_travel",
            heuristic_name="input_euclidean" if algorithm == "astar" else "zero",
        )

    edge = integrated_actuator_edge_cost(
        graph,
        robot,
        scene=scene,
        n_samples=n_samples,
        assembly_state=assembly_state,
    )
    heuristic: Heuristic
    if algorithm == "astar":
        heuristic = input_euclidean_heuristic_v2(graph, goal_id)
    else:
        heuristic = zero_heuristic_v2
    return V2PlanningObjective(
        edge_cost=edge,
        heuristic=heuristic,
        cost_name="actuator_travel_integrated",
        heuristic_name="input_euclidean" if algorithm == "astar" else "zero",
    )
