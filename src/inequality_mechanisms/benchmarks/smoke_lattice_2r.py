"""Deterministic lattice ablation smoke pack (Sprint V3.3 / V3-304)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from inequality_mechanisms.adapters import (
    GraphSearchPlanner,
    OperatingBranchRobotModel,
)
from inequality_mechanisms.adapters.lattice_edge_cost import EdgeCostMode
from inequality_mechanisms.core.constraints import ConstraintSet
from inequality_mechanisms.core.goals import ExactOutputGoal
from inequality_mechanisms.core.local_motion import EndpointDeclaredMotion
from inequality_mechanisms.core.objectives import ActuatorTravelObjective
from inequality_mechanisms.core.problem import PlanningProblem
from inequality_mechanisms.core.results import PlanningResult, PlanningStatus
from inequality_mechanisms.core.scene import FreeSpaceScene
from inequality_mechanisms.core.state import PhysicalState
from inequality_mechanisms.graphs.embedded import (
    EmbeddedPlanningGraph,
    UniformOutputLattice,
)
from inequality_mechanisms.graphs.topology import LatticeConnectivity
from inequality_mechanisms.mechanisms import (
    IndependentFourBars,
    PlanarFourBar,
    equivalent_gearbox_branch,
    select_fourbar_monotonic_branch,
)
from inequality_mechanisms.mechanisms.operating_branch import OperatingBranch

MechanismName = Literal["fourbar", "gearbox"]
AlgorithmName = Literal["dijkstra", "astar"]

_CRANK_ROCKER = dict(a=1.0, b=2.5, c=2.0, d=2.0)
COST_TOL = 1e-10


def _fourbar_2d_branch() -> OperatingBranch:
    bars = [
        PlanarFourBar(**_CRANK_ROCKER, branch=1, name="b0"),
        PlanarFourBar(**_CRANK_ROCKER, branch=1, name="b1"),
    ]
    return select_fourbar_monotonic_branch(IndependentFourBars(bars))


@dataclass(frozen=True, slots=True)
class LatticeSmokeArm:
    """One mechanism arm on a shared uniform-Q lattice."""

    name: MechanismName
    branch: OperatingBranch
    graph: EmbeddedPlanningGraph
    robot: OperatingBranchRobotModel


def build_paired_lattice_arms(
    *,
    shape: tuple[int, int] = (6, 6),
    connectivity: LatticeConnectivity | str = LatticeConnectivity.CHEBYSHEV_1,
) -> dict[MechanismName, LatticeSmokeArm]:
    """Build four-bar and span-matched gearbox graphs on one shared lattice."""
    fourbar = _fourbar_2d_branch()
    gearbox = equivalent_gearbox_branch(fourbar, name="span_matched_gearbox")
    shared = UniformOutputLattice.from_output_space(
        fourbar.output_space,
        shape=shape,
        connectivity=connectivity,
    )
    g_fb = EmbeddedPlanningGraph.from_output_lattice(shared, fourbar)
    g_gb = EmbeddedPlanningGraph.from_output_lattice(shared, gearbox)
    return {
        "fourbar": LatticeSmokeArm(
            name="fourbar",
            branch=fourbar,
            graph=g_fb,
            robot=OperatingBranchRobotModel(branch=fourbar),
        ),
        "gearbox": LatticeSmokeArm(
            name="gearbox",
            branch=gearbox,
            graph=g_gb,
            robot=OperatingBranchRobotModel(branch=gearbox),
        ),
    }


def _on_lattice_problem(
    arm: LatticeSmokeArm,
    start_id: int,
    goal_id: int,
) -> PlanningProblem:
    start = PhysicalState(
        u=np.asarray(arm.graph.u_state(start_id), dtype=np.float64),
        q=np.asarray(arm.graph.q_state(start_id), dtype=np.float64),
        assembly_state=arm.robot.state_from_input(arm.graph.u_state(start_id)).assembly_state,
    )
    goal = ExactOutputGoal(
        q_goal=np.asarray(arm.graph.q_state(goal_id), dtype=np.float64)
    )
    return PlanningProblem(
        robot=arm.robot,
        scene=FreeSpaceScene(robot=arm.robot),
        start=start,
        goal=goal,
        path_constraints=ConstraintSet.empty(),
        local_motion=EndpointDeclaredMotion(),
        objective=ActuatorTravelObjective(),
    )


def _off_lattice_problem(arm: LatticeSmokeArm) -> PlanningProblem:
    """Exact start/goal at cell centers (generally off lattice nodes)."""
    topo = arm.graph.topology
    i0, i1 = 1, 1
    j0, j1 = 3, 4
    q_a = arm.graph.q_state(topo.node_id((i0, i1)))
    q_b = arm.graph.q_state(topo.node_id((i0 + 1, i1 + 1)))
    q_start = 0.5 * (q_a + q_b)
    q_c = arm.graph.q_state(topo.node_id((j0, j1)))
    q_d = arm.graph.q_state(topo.node_id((j0 + 1, j1 + 1)))
    q_goal = 0.5 * (q_c + q_d)
    start_cands = arm.robot.states_from_output(q_start)
    if not start_cands:
        raise RuntimeError("off-lattice start is not representable on the branch")
    start = start_cands[0].state
    return PlanningProblem(
        robot=arm.robot,
        scene=FreeSpaceScene(robot=arm.robot),
        start=start,
        goal=ExactOutputGoal(q_goal=np.asarray(q_goal, dtype=np.float64)),
        path_constraints=ConstraintSet.empty(),
        local_motion=EndpointDeclaredMotion(),
        objective=ActuatorTravelObjective(),
    )


def run_lattice_query(
    arm: LatticeSmokeArm,
    problem: PlanningProblem,
    *,
    algorithm: AlgorithmName,
    edge_cost_mode: EdgeCostMode,
) -> PlanningResult:
    """Solve one lattice smoke query."""
    planner = GraphSearchPlanner(
        graph=arm.graph,
        algorithm=algorithm,
        edge_cost_mode=edge_cost_mode,
        allow_query_overlay=True,
    )
    return planner.solve(problem)


def run_lattice_smoke_pack() -> list[dict[str, Any]]:
    """Run 8-connected integrated + ablations; return summary rows."""
    rows: list[dict[str, Any]] = []
    configs: list[tuple[str, LatticeConnectivity, EdgeCostMode]] = [
        ("eight_integrated", LatticeConnectivity.CHEBYSHEV_1, "integrated"),
        ("four_integrated", LatticeConnectivity.AXIS_ALIGNED, "integrated"),
        ("eight_endpoint", LatticeConnectivity.CHEBYSHEV_1, "endpoint"),
    ]
    for label, connectivity, cost_mode in configs:
        arms = build_paired_lattice_arms(connectivity=connectivity)
        for mech, arm in arms.items():
            start_id = arm.graph.topology.node_id((0, 0))
            goal_id = arm.graph.topology.node_id((5, 5))
            problem = _on_lattice_problem(arm, start_id, goal_id)
            for algorithm in ("dijkstra", "astar"):
                result = run_lattice_query(
                    arm,
                    problem,
                    algorithm=algorithm,  # type: ignore[arg-type]
                    edge_cost_mode=cost_mode,
                )
                rows.append(
                    {
                        "config": label,
                        "mechanism": mech,
                        "algorithm": algorithm,
                        "status": str(result.status),
                        "objective_cost": result.objective_cost,
                        "expansions": result.planner_metrics.get("graph", {}).get(
                            "expansions"
                        ),
                        "architecture_version": result.provenance.architecture_version,
                        "overlay_used": result.planner_metrics.get("graph", {}).get(
                            "overlay_used"
                        ),
                        "connectivity": str(arm.graph.topology.connectivity),
                        "edge_cost_mode": cost_mode,
                    }
                )
        # One off-lattice overlay case on eight-connected integrated four-bar.
        if label == "eight_integrated":
            arm = arms["fourbar"]
            problem = _off_lattice_problem(arm)
            result = run_lattice_query(
                arm, problem, algorithm="dijkstra", edge_cost_mode="integrated"
            )
            rows.append(
                {
                    "config": "eight_integrated_overlay",
                    "mechanism": "fourbar",
                    "algorithm": "dijkstra",
                    "status": str(result.status),
                    "objective_cost": result.objective_cost,
                    "expansions": result.planner_metrics.get("graph", {}).get(
                        "expansions"
                    ),
                    "architecture_version": result.provenance.architecture_version,
                    "overlay_used": result.planner_metrics.get("graph", {}).get(
                        "overlay_used"
                    ),
                    "connectivity": str(arm.graph.topology.connectivity),
                    "edge_cost_mode": "integrated",
                }
            )
    return rows


__all__ = [
    "COST_TOL",
    "LatticeSmokeArm",
    "build_paired_lattice_arms",
    "run_lattice_query",
    "run_lattice_smoke_pack",
]
