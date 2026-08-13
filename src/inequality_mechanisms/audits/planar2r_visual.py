"""Planar-2R visual audit resolver and planner orchestration (V3-621 / V3-625)."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

import numpy as np

from inequality_mechanisms.adapters import GraphSearchPlanner
from inequality_mechanisms.adapters.lattice_edge_cost import (
    connector_for_graph,
    integrated_actuator_edge_cost,
)
from inequality_mechanisms.adapters.ompl import is_ompl_available, ompl_version_string
from inequality_mechanisms.audits.metrics import (
    LatticeMetricBundle,
    composite_j_alpha,
    edge_bundle_to_jsonable,
    integrate_edge_weights,
    path_lengths,
)
from inequality_mechanisms.audits.traces import ListPlannerTraceSink
from inequality_mechanisms.audits.trajectory_evaluation import (
    evaluate_continuous_trajectory,
)
from inequality_mechanisms.benchmarks.classification import (
    TASK_ALREADY_SATISFIED,
    TASK_INVALID_UNREPRESENTABLE,
)
from inequality_mechanisms.benchmarks.free_space_bank import build_bank_arms
from inequality_mechanisms.benchmarks.free_space_bank_v2 import (
    ResolvedFreeSpaceTaskV2,
    build_problem_v2,
    goal_generator_v2,
    load_free_space_bank_v2,
    resolve_free_space_tasks_v2,
    state_from_shared_q,
)
from inequality_mechanisms.benchmarks.smoke_lattice_2r import (
    LatticeSmokeArm,
    build_paired_lattice_arms,
)
from inequality_mechanisms.benchmarks.smoke_sampling_2r import SamplingSmokeArm
from inequality_mechanisms.core.goals import (
    GoalConstraint,
    GoalResidual,
    GoalSamplingRequest,
)
from inequality_mechanisms.core.local_motion import LocalMotionModel, OutputLinearMotion
from inequality_mechanisms.core.problem import PlanningProblem
from inequality_mechanisms.core.results import (
    PlanningResult,
    PlanningStatus,
    ResultProvenance,
)
from inequality_mechanisms.core.scene import PlanningScene
from inequality_mechanisms.core.state import PhysicalState, StateCandidate
from inequality_mechanisms.graphs.topology import LatticeConnectivity
from inequality_mechanisms.planners.direct.input_linear import InputLinearDirectPlanner
from inequality_mechanisms.planners.direct.output_linear import OutputLinearDirectPlanner
from inequality_mechanisms.planners.roadmap.prm import PRMPlanner
from inequality_mechanisms.planners.tree.rrt_connect import RRTConnectPlanner

MechanismName = Literal["fourbar", "gearbox"]

DEFAULT_AUDIT_CONFIG = (
    Path(__file__).resolve().parents[3]
    / "configs"
    / "v3"
    / "planar2r_visual_audit_v1.json"
)

PAIR_Q_TOL = 1e-9
WEIGHT_TOL = 1e-9
COST_TOL = 1e-8


@dataclass(frozen=True, slots=True)
class AuditConfig:
    """Loaded planar2r visual-audit configuration."""

    raw: dict[str, Any]
    path: Path

    @property
    def audit_id(self) -> str:
        return str(self.raw["audit_id"])

    @property
    def task_ids(self) -> tuple[str, ...]:
        return tuple(str(t) for t in self.raw["task_ids"])

    @property
    def seed(self) -> int:
        return int(self.raw["seed"])

    @property
    def lattice_shape(self) -> tuple[int, int]:
        shape = self.raw["lattice"]["shape"]
        return (int(shape[0]), int(shape[1]))

    @property
    def planners(self) -> tuple[str, ...]:
        return tuple(str(p) for p in self.raw["planners"])

    @property
    def animation_growth_tasks(self) -> frozenset[str]:
        return frozenset(
            str(t) for t in self.raw["animation_policy"]["roadmap_tree_growth_task_ids"]
        )

    @property
    def composite_weights(self) -> dict[str, float]:
        return {k: float(v) for k, v in dict(self.raw["composite_diagnostic"]["weights"]).items()}

    @property
    def composite_epsilon(self) -> float:
        return float(self.raw["composite_diagnostic"]["normalization"]["epsilon"])

    @property
    def output_dir(self) -> Path:
        return Path(self.raw["artifact_contract"]["output_dir"])


@dataclass
class ResolvedTrialRecord:
    """Pair-invariant task record plus mechanism-specific physical starts."""

    task_id: str
    start_q: list[float]
    start_tip: list[float]
    goal_center: list[float]
    goal_radius: float
    goal_points: list[list[float]]
    goal_point_ids: list[str]
    starts: dict[str, dict[str, Any]]
    notes: str = ""

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "start_q": list(self.start_q),
            "start_tip": list(self.start_tip),
            "goal_center": list(self.goal_center),
            "goal_radius": float(self.goal_radius),
            "goal_points": [list(p) for p in self.goal_points],
            "goal_point_ids": list(self.goal_point_ids),
            "starts": dict(self.starts),
            "notes": self.notes,
        }


@dataclass
class PlannerRunRecord:
    """One mechanism x planner solve for a trial."""

    planner: str
    mechanism: str
    status: str
    skipped: str | None = None
    objective_cost: float | None = None
    path_length_u: float | None = None
    path_length_q: float | None = None
    path_length_x: float | None = None
    task_class: str | None = None
    selected_goal_sample_id: str | None = None
    final_goal_residual: float | None = None
    planner_metrics: dict[str, Any] = field(default_factory=dict)
    trajectory_states: list[dict[str, Any]] = field(default_factory=list)
    expanded_node_ids: list[int] = field(default_factory=list)
    trace_events: list[dict[str, Any]] = field(default_factory=list)
    composite: dict[str, Any] = field(default_factory=dict)
    result: PlanningResult | None = None

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "planner": self.planner,
            "mechanism": self.mechanism,
            "status": self.status,
            "skipped": self.skipped,
            "objective_cost": self.objective_cost,
            "path_length_u": self.path_length_u,
            "path_length_q": self.path_length_q,
            "path_length_x": self.path_length_x,
            "task_class": self.task_class,
            "selected_goal_sample_id": self.selected_goal_sample_id,
            "final_goal_residual": self.final_goal_residual,
            "planner_metrics": self.planner_metrics,
            "trajectory_states": self.trajectory_states,
            "expanded_node_ids": list(self.expanded_node_ids),
            "trace_events": list(self.trace_events),
            "composite": self.composite,
        }


def load_audit_config(path: Path | None = None) -> AuditConfig:
    """Load and lightly validate the V3.6B audit config."""
    source = Path(path) if path is not None else DEFAULT_AUDIT_CONFIG
    raw = json.loads(source.read_text(encoding="utf-8"))
    if int(raw.get("schema_version", -1)) != 1:
        raise ValueError(f"unsupported audit schema in {source}")
    if int(raw.get("seed", -1)) != 7:
        raise ValueError("audit seed must be frozen at 7")
    required = {
        "near_0", "near_1", "near_2", "near_3", "near_4",
        "far_0", "far_1", "far_2", "far_3", "far_4",
    }
    if set(raw["task_ids"]) != required:
        raise ValueError("audit task_ids must be exactly the ten frozen V3.6B tasks")
    return AuditConfig(raw=raw, path=source.resolve())


def _edge_key_set(graph: Any) -> set[tuple[int, int]]:
    keys: set[tuple[int, int]] = set()
    for a, b in graph.topology.iter_edges():
        keys.add((a, b) if a <= b else (b, a))
    return keys


def _goal_candidates(arm: SamplingSmokeArm, task: ResolvedFreeSpaceTaskV2, contract: Any) -> list[Any]:
    problem = build_problem_v2(arm, task)
    generator = goal_generator_v2(arm, task)
    request = GoalSamplingRequest(max_candidates=contract.goal_representation.max_candidates)
    return list(generator.generate(arm.robot, problem.goal, request))


def assert_pair_invariants(
    *,
    lattice_arms: Mapping[MechanismName, LatticeSmokeArm],
    sampling_arms: Mapping[MechanismName, SamplingSmokeArm],
    task: ResolvedFreeSpaceTaskV2,
    candidates_by_mech: Mapping[str, Sequence[Any]],
) -> None:
    """Fail closed when shared-Q / candidate invariants are violated."""
    fb = lattice_arms["fourbar"]
    gb = lattice_arms["gearbox"]
    if fb.graph.node_count != gb.graph.node_count:
        raise ValueError("paired lattices have different node counts")
    if not np.allclose(fb.graph.q_nodes, gb.graph.q_nodes, atol=PAIR_Q_TOL, rtol=0.0):
        raise ValueError("paired lattices do not share identical Q nodes")
    if _edge_key_set(fb.graph) != _edge_key_set(gb.graph):
        raise ValueError("paired lattices do not share identical Q adjacency")

    tips = []
    for mech, arm in sampling_arms.items():
        state = state_from_shared_q(arm, task.start_q)
        if not arm.robot.validate_state(state, 1e-9):
            raise ValueError(f"{mech} start fails validate_state")
        tip = np.asarray(arm.robot.forward_kinematics(state).position, dtype=np.float64)
        tips.append(tip)
        residual = float(np.linalg.norm(tip - task.start_tip))
        if residual > 1e-9:
            raise ValueError(f"{mech} start tip mismatch: {residual}")
    if float(np.linalg.norm(tips[0] - tips[1])) > 1e-9:
        raise ValueError("paired start tips disagree")

    fb_c = list(candidates_by_mech["fourbar"])
    gb_c = list(candidates_by_mech["gearbox"])
    if len(fb_c) != len(gb_c):
        raise ValueError("paired goal candidate counts disagree")
    for a, b in zip(fb_c, gb_c):
        id_a = a.provenance.get("goal_sample_id")
        id_b = b.provenance.get("goal_sample_id")
        if id_a != id_b:
            raise ValueError(f"candidate ordering mismatch: {id_a!r} vs {id_b!r}")
        if not np.allclose(a.state.q, b.state.q, atol=PAIR_Q_TOL, rtol=0.0):
            raise ValueError(f"candidate q mismatch for {id_a}")


def resolve_audit_trials(
    config: AuditConfig,
    *,
    sampling_arms: Mapping[MechanismName, SamplingSmokeArm] | None = None,
    lattice_shape: tuple[int, int] | None = None,
) -> tuple[ResolvedTrialRecord, ...]:
    """Resolve the ten frozen tasks and fail closed on pair mismatches."""
    bank_path = config.path.parent / str(config.raw["source_bank"]["contract_path"])
    contract = load_free_space_bank_v2(bank_path)
    arms = dict(sampling_arms) if sampling_arms is not None else build_bank_arms(contract.base_bank)
    resolved = resolve_free_space_tasks_v2(contract, arms=arms)
    by_id = {t.task_id: t for t in resolved}
    missing = [tid for tid in config.task_ids if tid not in by_id]
    if missing:
        raise ValueError(f"missing audit tasks in bank: {missing}")

    shape = lattice_shape if lattice_shape is not None else config.lattice_shape
    lattice_arms = build_paired_lattice_arms(
        shape=shape,
        connectivity=LatticeConnectivity.CHEBYSHEV_1,
    )
    out: list[ResolvedTrialRecord] = []
    for tid in config.task_ids:
        task = by_id[tid]
        cands = {mech: _goal_candidates(arms[mech], task, contract) for mech in ("fourbar", "gearbox")}
        assert_pair_invariants(
            lattice_arms=lattice_arms,
            sampling_arms=arms,
            task=task,
            candidates_by_mech=cands,
        )
        starts: dict[str, dict[str, Any]] = {}
        for mech, arm in arms.items():
            state = state_from_shared_q(arm, task.start_q)
            starts[mech] = {
                "u": state.u.tolist(),
                "q": state.q.tolist(),
                "assembly_state": dict(state.assembly_state),
            }
        out.append(
            ResolvedTrialRecord(
                task_id=task.task_id,
                start_q=task.start_q.tolist(),
                start_tip=task.start_tip.tolist(),
                goal_center=task.goal_center.tolist(),
                goal_radius=float(task.goal_radius),
                goal_points=[p.tolist() for p in task.goal_points],
                goal_point_ids=list(task.goal_point_ids),
                starts=starts,
                notes=task.notes,
            )
        )
    return tuple(out)


def _result_core_signature(result: PlanningResult) -> tuple[Any, ...]:
    path_u = None
    path_q = None
    if result.trajectory is not None:
        path_u = tuple(tuple(float(v) for v in s.u) for s in result.trajectory.states)
        path_q = tuple(tuple(float(v) for v in s.q) for s in result.trajectory.states)
    selected_u = (
        None
        if result.selected_goal_state is None
        else tuple(float(v) for v in result.selected_goal_state.u)
    )
    return (
        str(result.status),
        result.objective_cost,
        path_u,
        path_q,
        selected_u,
        result.path_length_u,
        result.path_length_q,
        result.task_class,
    )


def _serialize_states(states: Sequence[PhysicalState]) -> list[dict[str, Any]]:
    return [
        {"u": s.u.tolist(), "q": s.q.tolist(), "assembly_state": dict(s.assembly_state)}
        for s in states
    ]


def _selected_goal_sample_id(result: PlanningResult) -> str | None:
    cand = result.selected_goal_candidate
    if cand is not None and "goal_sample_id" in cand.provenance:
        return str(cand.provenance["goal_sample_id"])
    state = result.selected_goal_state
    if state is None:
        return None
    aux = dict(state.auxiliary_state or {})
    if "goal_sample_id" in aux:
        return str(aux["goal_sample_id"])
    return None


def _with_goal_sample(result: PlanningResult, sample_id: Any) -> PlanningResult:
    if result.selected_goal_state is None:
        return result
    selected = PhysicalState(
        u=result.selected_goal_state.u,
        q=result.selected_goal_state.q,
        assembly_state=dict(result.selected_goal_state.assembly_state),
        auxiliary_state={
            **dict(result.selected_goal_state.auxiliary_state or {}),
            "goal_sample_id": sample_id,
        },
    )
    candidate = result.selected_goal_candidate
    if candidate is not None:
        provenance = {**dict(candidate.provenance), "goal_sample_id": sample_id}
        candidate = StateCandidate(
            state=selected,
            residual=float(candidate.residual),
            provenance=provenance,
        )
    return replace(
        result,
        selected_goal_state=selected,
        selected_goal_candidate=candidate,
    )


def _physical_residual_primary(result: PlanningResult) -> float | None:
    """Return the physical task residual primary value for audit tables."""
    if result.goal_residuals is not None and result.goal_residuals.physical is not None:
        return float(result.goal_residuals.physical.primary)
    residual = result.final_goal_residual
    if residual is None:
        return None
    if isinstance(residual, GoalResidual):
        return float(residual.primary)
    if isinstance(residual, (float, int)):
        return float(residual)
    return None


def _solve_lattice_goal_set(
    *,
    arm: SamplingSmokeArm,
    task: ResolvedFreeSpaceTaskV2,
    candidates: Sequence[Any],
    lattice_arm: LatticeSmokeArm,
    algorithm: Literal["dijkstra", "astar"],
    edge_n_samples: int,
    trace_sink: ListPlannerTraceSink | None,
) -> tuple[PlanningResult, list[int]]:
    """Solve the represented goal set on the audit lattice (one V3-632 query)."""
    problem = build_problem_v2(arm, task)
    planner_id = f"lattice_goal_set_{algorithm}_eight_integrated"
    if problem.goal.satisfied(problem.start):
        return (
            PlanningResult(
                status=PlanningStatus.SUCCESS,
                trajectory=None,
                selected_goal_state=problem.start,
                total_wall_time_s=0.0,
                objective_cost=0.0,
                path_length_u=0.0,
                path_length_q=0.0,
                path_length_x=0.0,
                task_class=TASK_ALREADY_SATISFIED,
                final_goal_residual=problem.goal.residual(problem.start),
                planner_metrics={
                    "graph": {
                        "expansions": 0,
                        "path_node_ids": [],
                        "expansions_are_total_query_work": True,
                    }
                },
                provenance=ResultProvenance(architecture_version=3, planner_id=planner_id),
            ),
            [],
        )
    if not candidates:
        return (
            PlanningResult(
                status=PlanningStatus.INVALID,
                trajectory=None,
                selected_goal_state=None,
                total_wall_time_s=0.0,
                objective_cost=None,
                path_length_u=None,
                path_length_q=None,
                path_length_x=None,
                task_class=TASK_INVALID_UNREPRESENTABLE,
                final_goal_residual=None,
                planner_metrics={
                    "graph": {
                        "goal_set_cardinality": 0,
                        "expansions_are_total_query_work": True,
                    }
                },
                provenance=ResultProvenance(architecture_version=3, planner_id=planner_id),
            ),
            [],
        )

    assembly = dict(problem.start.assembly_state)
    shared_base_edge = integrated_actuator_edge_cost(
        lattice_arm.graph,
        problem.robot,
        scene=problem.scene,
        n_samples=edge_n_samples,
        assembly_state=assembly,
    )
    planner = GraphSearchPlanner(
        graph=lattice_arm.graph,
        algorithm=algorithm,
        edge_cost_mode="integrated",
        allow_query_overlay=True,
        edge_n_samples=edge_n_samples,
        q_match_tolerance=1e-9,
        record_expanded=True,
        trace_sink=trace_sink,
        shared_edge_cost=shared_base_edge,
    )
    result = planner.solve_goal_set(problem, list(candidates))
    # Preserve audit planner_id while keeping V3-632 metrics/provenance.
    result = PlanningResult(
        status=result.status,
        trajectory=result.trajectory,
        selected_goal_state=result.selected_goal_state,
        selected_goal_candidate=result.selected_goal_candidate,
        total_wall_time_s=result.total_wall_time_s,
        query_time_s=result.query_time_s,
        objective_cost=result.objective_cost,
        path_length_u=result.path_length_u,
        path_length_q=result.path_length_q,
        path_length_x=result.path_length_x,
        task_class=result.task_class,
        final_goal_residual=result.final_goal_residual,
        goal_residuals=result.goal_residuals,
        planner_metrics=result.planner_metrics,
        provenance=ResultProvenance(
            architecture_version=3,
            code_revision=result.provenance.code_revision,
            planner_id=planner_id,
            extras=dict(result.provenance.extras),
        ),
    )
    sample_id = None
    if result.selected_goal_candidate is not None:
        sample_id = result.selected_goal_candidate.provenance.get("goal_sample_id")
    result = _with_goal_sample(result, sample_id)
    graph_metrics = result.planner_metrics.get("graph") or {}
    expanded = [int(n) for n in graph_metrics.get("expanded_node_ids") or []]
    return result, expanded



def _pack_run(
    *,
    planner: str,
    mechanism: str,
    result: PlanningResult | None,
    skipped: str | None,
    expanded: Sequence[int] | None,
    sink: ListPlannerTraceSink | None,
    robot: Any | None,
    connector: LocalMotionModel | None = None,
    goal: GoalConstraint | None = None,
    scene: PlanningScene | None = None,
) -> PlannerRunRecord:
    if result is None:
        return PlannerRunRecord(
            planner=planner,
            mechanism=mechanism,
            status="unavailable",
            skipped=skipped,
            planner_metrics={"unavailable": True, "reason": skipped},
        )
    states: list[PhysicalState] = []
    if result.trajectory is not None and result.trajectory.states:
        states = list(result.trajectory.states)
    elif (
        result.selected_goal_state is not None
        and result.status == PlanningStatus.SUCCESS
        and result.objective_cost == 0.0
    ):
        states = [result.selected_goal_state]
    length_x = result.path_length_x
    length_q = result.path_length_q
    length_u = result.path_length_u
    planner_metrics = dict(result.planner_metrics or {})
    if (
        result.status == PlanningStatus.SUCCESS
        and len(states) >= 2
        and connector is not None
        and robot is not None
    ):
        cte = evaluate_continuous_trajectory(
            states,
            connector=connector,
            robot=robot,
            goal=goal,
            scene=scene,
        )
        planner_metrics["continuous_trajectory"] = cte.to_jsonable()
        # Continuous lengths are the fresh reporting truth; never fall back to
        # waypoint chords when reconstruction fails.
        length_u = cte.length_u
        length_q = cte.length_q
        length_x = cte.length_x
    elif states and robot is not None:
        metrics = path_lengths(states, robot=robot)
        length_u = length_u if length_u is not None else metrics.length_u
        length_q = length_q if length_q is not None else metrics.length_q
        length_x = length_x if length_x is not None else metrics.length_x
    residual_f = _physical_residual_primary(result)
    return PlannerRunRecord(
        planner=planner,
        mechanism=mechanism,
        status=str(result.status),
        skipped=skipped,
        objective_cost=result.objective_cost,
        path_length_u=length_u,
        path_length_q=length_q,
        path_length_x=length_x,
        task_class=result.task_class,
        selected_goal_sample_id=_selected_goal_sample_id(result),
        final_goal_residual=residual_f,
        planner_metrics=planner_metrics,
        trajectory_states=_serialize_states(states),
        expanded_node_ids=list(expanded or []),
        trace_events=sink.to_jsonable() if sink is not None else [],
        result=result,
    )


def run_planner_for_trial(
    *,
    config: AuditConfig,
    planner_name: str,
    arm: SamplingSmokeArm,
    lattice_arm: LatticeSmokeArm,
    task: ResolvedFreeSpaceTaskV2,
    contract: Any,
    capture_trace: bool = True,
) -> PlannerRunRecord:
    """Run one planner for one mechanism x task, optionally capturing traces."""
    max_candidates = int(config.raw["planner_settings"]["max_goal_candidates"])
    edge_n_samples = int(config.raw["lattice"]["edge_n_samples"])
    seed = config.seed
    generator = goal_generator_v2(arm, task)
    problem = build_problem_v2(arm, task)
    candidates = _goal_candidates(arm, task, contract)
    sink = ListPlannerTraceSink() if capture_trace else None

    if planner_name in ("ompl_prm", "ompl_rrt_connect") and not is_ompl_available():
        return _pack_run(
            planner=planner_name,
            mechanism=arm.name,
            result=None,
            skipped="ompl_unavailable",
            expanded=None,
            sink=None,
            robot=arm.robot,
        )

    if planner_name == "input_linear":
        result = InputLinearDirectPlanner(
            goal_generator=generator, max_candidates=max_candidates
        ).solve(problem)
        return _pack_run(
            planner=planner_name, mechanism=arm.name, result=result,
            skipped=None, expanded=None, sink=sink, robot=arm.robot,
            connector=problem.local_motion,
            goal=problem.goal,
            scene=problem.scene,
        )

    if planner_name == "output_linear":
        out_problem = PlanningProblem(
            robot=problem.robot,
            scene=problem.scene,
            start=problem.start,
            goal=problem.goal,
            path_constraints=problem.path_constraints,
            local_motion=OutputLinearMotion(robot=arm.robot, n_samples=64),
            objective=problem.objective,
        )
        result = OutputLinearDirectPlanner(
            goal_generator=generator, max_candidates=max_candidates
        ).solve(out_problem)
        return _pack_run(
            planner=planner_name, mechanism=arm.name, result=result,
            skipped=None, expanded=None, sink=sink, robot=arm.robot,
            connector=out_problem.local_motion,
            goal=out_problem.goal,
            scene=out_problem.scene,
        )

    if planner_name in ("lattice_dijkstra", "lattice_astar"):
        algorithm: Literal["dijkstra", "astar"] = (
            "dijkstra" if planner_name == "lattice_dijkstra" else "astar"
        )
        result, expanded = _solve_lattice_goal_set(
            arm=arm,
            task=task,
            candidates=candidates,
            lattice_arm=lattice_arm,
            algorithm=algorithm,
            edge_n_samples=edge_n_samples,
            trace_sink=sink,
        )
        lattice_connector = connector_for_graph(
            lattice_arm.graph, arm.robot, n_samples=edge_n_samples
        )
        return _pack_run(
            planner=planner_name, mechanism=arm.name, result=result,
            skipped=None, expanded=expanded, sink=sink, robot=arm.robot,
            connector=lattice_connector,
            goal=problem.goal,
            scene=problem.scene,
        )

    settings = config.raw["planner_settings"]
    if planner_name == "prm":
        prm_cfg = settings["prm"]
        result = PRMPlanner(
            seed=seed,
            n_samples=int(prm_cfg["n_samples"]),
            k_neighbors=int(prm_cfg["k_neighbors"]),
            max_edge_u=float(prm_cfg["max_edge_u"]),
            max_goal_candidates=max_candidates,
            goal_generator=generator,
            trace_sink=sink,
        ).solve(problem)
        return _pack_run(
            planner=planner_name, mechanism=arm.name, result=result,
            skipped=None, expanded=None, sink=sink, robot=arm.robot,
            connector=problem.local_motion,
            goal=problem.goal,
            scene=problem.scene,
        )

    if planner_name == "rrt_connect":
        rrt_cfg = settings["rrt_connect"]
        result = RRTConnectPlanner(
            seed=seed,
            max_iterations=int(rrt_cfg["max_iterations"]),
            step_u=float(rrt_cfg["step_u"]),
            goal_bias=float(rrt_cfg["goal_bias"]),
            max_goal_candidates=max_candidates,
            goal_generator=generator,
            trace_sink=sink,
        ).solve(problem)
        return _pack_run(
            planner=planner_name, mechanism=arm.name, result=result,
            skipped=None, expanded=None, sink=sink, robot=arm.robot,
            connector=problem.local_motion,
            goal=problem.goal,
            scene=problem.scene,
        )

    if planner_name == "ompl_prm":
        from inequality_mechanisms.adapters.ompl import OmplPRMPlanner

        result = OmplPRMPlanner(
            seed=seed,
            max_goal_candidates=max_candidates,
            goal_generator=generator,
            solve_time_s=float(settings["ompl"]["solve_time_s"]),
            trace_sink=sink,
        ).solve(problem)
        return _pack_run(
            planner=planner_name, mechanism=arm.name, result=result,
            skipped=None, expanded=None, sink=sink, robot=arm.robot,
            connector=problem.local_motion,
            goal=problem.goal,
            scene=problem.scene,
        )

    if planner_name == "ompl_rrt_connect":
        from inequality_mechanisms.adapters.ompl import OmplRRTConnectPlanner

        result = OmplRRTConnectPlanner(
            seed=seed,
            max_goal_candidates=max_candidates,
            goal_generator=generator,
            solve_time_s=float(settings["ompl"]["solve_time_s"]),
            trace_sink=sink,
        ).solve(problem)
        return _pack_run(
            planner=planner_name, mechanism=arm.name, result=result,
            skipped=None, expanded=None, sink=sink, robot=arm.robot,
            connector=problem.local_motion,
            goal=problem.goal,
            scene=problem.scene,
        )

    raise ValueError(f"unknown planner {planner_name!r}")


def attach_composites(
    runs: Sequence[PlannerRunRecord],
    *,
    config: AuditConfig,
) -> list[PlannerRunRecord]:
    """Attach per-planner paired normalization composites."""
    by_planner: dict[str, list[PlannerRunRecord]] = {}
    for run in runs:
        by_planner.setdefault(run.planner, []).append(run)
    out: list[PlannerRunRecord] = []
    weights = config.composite_weights
    eps = config.composite_epsilon
    for _planner, group in by_planner.items():
        refs = {
            "L_U": max((abs(r.path_length_u) for r in group if r.path_length_u is not None), default=0.0),
            "L_Q": max((abs(r.path_length_q) for r in group if r.path_length_q is not None), default=0.0),
            "L_X": max((abs(r.path_length_x) for r in group if r.path_length_x is not None), default=0.0),
        }
        for run in group:
            run.composite = composite_j_alpha(
                length_u=run.path_length_u,
                length_q=run.path_length_q,
                length_x=run.path_length_x,
                weights=weights,
                norm_refs=refs,
                epsilon=eps,
            )
            out.append(run)
    return out


def paired_delta(fourbar: PlannerRunRecord, gearbox: PlannerRunRecord, field: str) -> float | None:
    """Return z_fourbar - z_gearbox for a numeric field."""
    a = getattr(fourbar, field)
    b = getattr(gearbox, field)
    if a is None or b is None:
        return None
    return float(a) - float(b)


def compute_mechanism_edge_metrics(
    lattice_arm: LatticeSmokeArm,
    sampling_arm: SamplingSmokeArm,
    *,
    n_samples: int = 32,
) -> LatticeMetricBundle:
    """Integrate edge weights on the audit lattice for one mechanism."""
    assembly = sampling_arm.robot.state_from_input(lattice_arm.graph.u_state(0)).assembly_state
    return integrate_edge_weights(
        lattice_arm.graph,
        sampling_arm.robot,
        n_samples=n_samples,
        assembly_state=assembly,
    )


def assert_shared_wq_wx(
    fourbar: LatticeMetricBundle,
    gearbox: LatticeMetricBundle,
    *,
    tol: float = WEIGHT_TOL,
) -> None:
    """Assert shared-Q output-linear w_Q / w_X agree across mechanisms."""
    fb = {(e.a, e.b): e for e in fourbar.edges}
    gb = {(e.a, e.b): e for e in gearbox.edges}
    if set(fb) != set(gb):
        raise ValueError("edge sets disagree between mechanisms")
    for key, e_fb in fb.items():
        e_gb = gb[key]
        if not np.isfinite(e_fb.w_q) or not np.isfinite(e_gb.w_q):
            continue
        if abs(e_fb.w_q - e_gb.w_q) > tol:
            raise ValueError(f"w_Q mismatch on edge {key}")
        if abs(e_fb.w_x - e_gb.w_x) > tol:
            raise ValueError(f"w_X mismatch on edge {key}")


def provenance_block(config: AuditConfig) -> dict[str, Any]:
    """Return architecture/provenance fields for HTML/manifest."""
    try:
        import numpy

        numpy_v = numpy.__version__
    except Exception:
        numpy_v = None
    try:
        rev = subprocess.run(
            ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        rev = None
    return {
        "audit_id": config.audit_id,
        "config_path": str(config.path),
        "git_revision": rev,
        "python_version": sys.version.split()[0],
        "dependency_versions": {"numpy": numpy_v},
        "ompl_available": bool(is_ompl_available()),
        "ompl_version": ompl_version_string(),
        "no_inference_statement": config.raw["no_inference_statement"],
        "delta_convention": config.raw["delta_convention"],
        "seed": config.seed,
        "lattice": config.raw["lattice"],
        "planners": list(config.planners),
    }


__all__ = [
    "AuditConfig",
    "COST_TOL",
    "DEFAULT_AUDIT_CONFIG",
    "PlannerRunRecord",
    "ResolvedTrialRecord",
    "WEIGHT_TOL",
    "_result_core_signature",
    "assert_pair_invariants",
    "assert_shared_wq_wx",
    "attach_composites",
    "compute_mechanism_edge_metrics",
    "edge_bundle_to_jsonable",
    "load_audit_config",
    "paired_delta",
    "provenance_block",
    "resolve_audit_trials",
    "run_planner_for_trial",
]
