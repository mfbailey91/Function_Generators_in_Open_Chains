"""V3-633: PRM / RRTConnect shared goal-set parity and multi-root trees."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np
import pytest
from tests.graphs_v2._fixtures import fourbar_2d_branch

from inequality_mechanisms.adapters import planar_2r_operating_branch_robot
from inequality_mechanisms.audits.traces import ListPlannerTraceSink
from inequality_mechanisms.benchmarks.free_space_bank_v2 import (
    FrozenCartesianDiskGoalGenerator,
)
from inequality_mechanisms.core import (
    ActuatorTravelObjective,
    CartesianDiskGoal,
    ConstraintSet,
    ExactOutputGoal,
    FreeSpaceScene,
    InputLinearMotion,
    PlanningProblem,
    PlanningStatus,
)
from inequality_mechanisms.core.local_motion import LocalMotion
from inequality_mechanisms.kinematics.planar_2r import Planar2R
from inequality_mechanisms.planners import PRMPlanner, RRTConnectPlanner
from inequality_mechanisms.planners.sampling_space import select_goal_candidates


class CountingScene:
    """Wrap a free-space scene and count ``motion_is_valid`` calls."""

    def __init__(
        self,
        inner: FreeSpaceScene,
        *,
        reject_end_u: np.ndarray | None = None,
    ) -> None:
        self._inner = inner
        self.motion_checks = 0
        self.reject_end_u = (
            None
            if reject_end_u is None
            else np.asarray(reject_end_u, dtype=np.float64)
        )

    def state_is_valid(self, state: Any) -> bool:
        return self._inner.state_is_valid(state)

    def motion_is_valid(self, motion: LocalMotion) -> bool:
        self.motion_checks += 1
        if self.reject_end_u is not None:
            for endpoint in (motion.start, motion.end):
                if np.allclose(endpoint.u, self.reject_end_u, rtol=0.0, atol=1e-12):
                    return False
        return self._inner.motion_is_valid(motion)


def _ordered_far_near_problem() -> tuple[
    Any, PlanningProblem, FrozenCartesianDiskGoalGenerator, list
]:
    """Disk with ordered frozen points: far tip first, near tip second."""
    fk = Planar2R(1.0, 1.0)
    robot = planar_2r_operating_branch_robot(fourbar_2d_branch(), planar_fk=fk)
    cert = robot.branch.certificate
    u_lo = np.asarray(cert.input_lower)
    u_hi = np.asarray(cert.input_upper)
    start = robot.state_from_input(u_lo + np.array([0.15, 0.15]) * (u_hi - u_lo))
    near_state = robot.state_from_input(u_lo + np.array([0.25, 0.25]) * (u_hi - u_lo))
    far_state = robot.state_from_input(u_lo + np.array([0.85, 0.85]) * (u_hi - u_lo))
    near_tip = np.asarray(robot.forward_kinematics(near_state).position, dtype=np.float64)
    far_tip = np.asarray(robot.forward_kinematics(far_state).position, dtype=np.float64)
    center = 0.5 * (near_tip + far_tip)
    radius = float(np.linalg.norm(far_tip - center)) + 0.05
    goal = CartesianDiskGoal(center=center, radius=radius, robot=robot)
    assert not goal.satisfied(start)
    generator = FrozenCartesianDiskGoalGenerator(
        planar_fk=fk,
        goal_points=(far_tip.copy(), near_tip.copy()),
        goal_point_ids=("far", "near"),
    )
    problem = PlanningProblem(
        robot=robot,
        scene=FreeSpaceScene(robot=robot),
        start=start,
        goal=goal,
        path_constraints=ConstraintSet.empty(),
        local_motion=InputLinearMotion(robot=robot, n_samples=16),
        objective=ActuatorTravelObjective(),
    )
    cands = select_goal_candidates(
        problem, goal_generator=generator, max_candidates=16
    )
    assert len(cands) >= 2
    assert cands[0].provenance["goal_sample_id"] == "far"
    assert any(c.provenance["goal_sample_id"] == "near" for c in cands)
    return robot, problem, generator, cands


def _result_core_signature(result: Any) -> tuple[Any, ...]:
    selected = result.selected_goal_state
    cand = result.selected_goal_candidate
    metrics = result.planner_metrics.get("tree") or result.planner_metrics.get(
        "roadmap"
    )
    return (
        result.status,
        None if result.objective_cost is None else float(result.objective_cost),
        None if selected is None else tuple(np.round(selected.u, 12)),
        None if cand is None else cand.provenance.get("goal_sample_id"),
        dict(metrics) if metrics is not None else {},
    )


def test_prm_and_rrt_share_ordered_goal_set() -> None:
    _robot, problem, generator, cands = _ordered_far_near_problem()
    expected_ids = [c.provenance["goal_sample_id"] for c in cands]
    expected_u = [tuple(np.round(c.state.u, 12)) for c in cands]

    prm = PRMPlanner(
        seed=11,
        n_samples=40,
        k_neighbors=8,
        max_edge_u=1.5,
        max_goal_candidates=16,
        goal_generator=generator,
    ).solve(problem)
    rrt = RRTConnectPlanner(
        seed=11,
        max_iterations=300,
        step_u=0.4,
        goal_bias=0.5,
        max_goal_candidates=16,
        goal_generator=generator,
    ).solve(problem)

    assert prm.status is PlanningStatus.SUCCESS
    assert rrt.status is PlanningStatus.SUCCESS
    assert prm.planner_metrics["roadmap"]["goal_candidate_count"] == len(cands)
    assert rrt.planner_metrics["tree"]["goal_root_count"] == len(cands)
    assert prm.planner_metrics["roadmap"]["goal_attachment_count"] >= 1

    # Same declared ordered set: both planners can match any accepted root.
    assert prm.selected_goal_candidate is not None
    assert rrt.selected_goal_candidate is not None
    assert prm.selected_goal_candidate.provenance["goal_sample_id"] in expected_ids
    assert rrt.selected_goal_candidate.provenance["goal_sample_id"] in expected_ids
    assert tuple(np.round(prm.selected_goal_state.u, 12)) in expected_u  # type: ignore[union-attr]
    assert tuple(np.round(rrt.selected_goal_state.u, 12)) in expected_u  # type: ignore[union-attr]


def test_rrt_deterministic_non_first_winner() -> None:
    _robot, problem, generator, cands = _ordered_far_near_problem()
    assert cands[0].provenance["goal_sample_id"] == "far"

    result = RRTConnectPlanner(
        seed=0,
        max_iterations=300,
        step_u=0.4,
        goal_bias=0.5,
        max_goal_candidates=16,
        goal_generator=generator,
    ).solve(problem)
    assert result.status is PlanningStatus.SUCCESS
    root_idx = result.planner_metrics["tree"]["selected_goal_root_index"]
    assert root_idx > 0
    assert result.selected_goal_candidate is not None
    assert result.selected_goal_candidate.provenance["goal_sample_id"] == cands[
        root_idx
    ].provenance["goal_sample_id"]
    assert np.allclose(
        result.selected_goal_state.u, cands[root_idx].state.u  # type: ignore[union-attr]
    )


def test_rrt_and_prm_preserve_exact_start() -> None:
    _robot, problem, generator, _cands = _ordered_far_near_problem()
    start_u = problem.start.u.copy()

    prm = PRMPlanner(
        seed=3,
        n_samples=32,
        k_neighbors=6,
        max_edge_u=1.5,
        max_goal_candidates=16,
        goal_generator=generator,
    ).solve(problem)
    rrt = RRTConnectPlanner(
        seed=3,
        max_iterations=300,
        step_u=0.4,
        goal_bias=0.5,
        max_goal_candidates=16,
        goal_generator=generator,
    ).solve(problem)
    assert prm.status is PlanningStatus.SUCCESS
    assert rrt.status is PlanningStatus.SUCCESS
    assert np.allclose(prm.trajectory.states[0].u, start_u)  # type: ignore[union-attr]
    assert np.allclose(rrt.trajectory.states[0].u, start_u)  # type: ignore[union-attr]


def test_rrt_exact_output_goal_preserves_exact_start() -> None:
    from inequality_mechanisms.adapters import OperatingBranchRobotModel

    branch = fourbar_2d_branch()
    robot = OperatingBranchRobotModel(branch=branch)
    cert = branch.certificate
    u_lo = np.asarray(cert.input_lower)
    u_hi = np.asarray(cert.input_upper)
    start = robot.state_from_input(u_lo + 0.2 * (u_hi - u_lo))
    goal_state = robot.state_from_input(u_lo + 0.7 * (u_hi - u_lo))
    problem = PlanningProblem(
        robot=robot,
        scene=FreeSpaceScene(robot=robot),
        start=start,
        goal=ExactOutputGoal(q_goal=goal_state.q.copy()),
        path_constraints=ConstraintSet.empty(),
        local_motion=InputLinearMotion(robot=robot, n_samples=12),
        objective=ActuatorTravelObjective(),
    )
    cands = select_goal_candidates(problem, goal_generator=None, max_candidates=8)
    assert cands
    result = RRTConnectPlanner(
        seed=42, max_iterations=400, step_u=0.3, goal_bias=0.1, max_goal_candidates=8
    ).solve(problem)
    assert result.status is PlanningStatus.SUCCESS
    assert result.planner_metrics["tree"]["goal_root_count"] == len(cands)
    assert np.allclose(result.trajectory.states[0].u, start.u)  # type: ignore[union-attr]


def test_trace_sink_noninterference_rrt_and_prm() -> None:
    _robot, problem, generator, cands = _ordered_far_near_problem()

    r0 = RRTConnectPlanner(
        seed=0,
        max_iterations=300,
        step_u=0.4,
        goal_bias=0.5,
        max_goal_candidates=16,
        goal_generator=generator,
    ).solve(problem)
    sink = ListPlannerTraceSink()
    r1 = RRTConnectPlanner(
        seed=0,
        max_iterations=300,
        step_u=0.4,
        goal_bias=0.5,
        max_goal_candidates=16,
        goal_generator=generator,
        trace_sink=sink,
    ).solve(problem)
    assert _result_core_signature(r0) == _result_core_signature(r1)
    root_inserts = [
        e
        for e in sink.events
        if e.event_type == "vertex_insert"
        and e.payload.get("tree") == "goal"
        and e.payload.get("parent") is None
    ]
    assert len(root_inserts) == len(cands)
    assert all("provenance" in e.payload for e in root_inserts)
    connect_events = [e for e in sink.events if e.event_type == "trees_connected"]
    assert connect_events
    assert "selected_goal_root_index" in connect_events[0].payload
    assert connect_events[0].payload["selected_goal_root_index"] == r1.planner_metrics[
        "tree"
    ]["selected_goal_root_index"]

    p0 = PRMPlanner(
        seed=7,
        n_samples=28,
        k_neighbors=6,
        max_edge_u=1.5,
        max_goal_candidates=16,
        goal_generator=generator,
    ).solve(problem)
    sink2 = ListPlannerTraceSink()
    p1 = PRMPlanner(
        seed=7,
        n_samples=28,
        k_neighbors=6,
        max_edge_u=1.5,
        max_goal_candidates=16,
        goal_generator=generator,
        trace_sink=sink2,
    ).solve(problem)
    assert _result_core_signature(p0) == _result_core_signature(p1)
    assert any(e.event_type == "query_attach" for e in sink2.events)
    attach = next(e for e in sink2.events if e.event_type == "query_attach")
    assert len(attach.payload["goal_indices"]) == len(cands)


def test_prm_query_edges_are_canonical_and_traced_once() -> None:
    _robot, problem, generator, cands = _ordered_far_near_problem()
    scene = CountingScene(problem.scene)
    problem = replace(problem, scene=scene)
    sink = ListPlannerTraceSink()
    result = PRMPlanner(
        seed=23,
        n_samples=0,
        k_neighbors=1,
        max_edge_u=10.0,
        max_goal_candidates=16,
        goal_generator=generator,
        trace_sink=sink,
    ).solve(problem)

    assert result.status is PlanningStatus.SUCCESS
    roadmap = result.planner_metrics["roadmap"]
    goal_count = len(cands)
    assert roadmap["start_attachment_count"] == goal_count
    assert roadmap["goal_attachment_count"] == goal_count
    assert roadmap["query_unique_edges_attempted"] == goal_count
    assert roadmap["query_unique_edges_accepted"] == goal_count
    assert roadmap["query_duplicate_edge_reuses"] == goal_count
    assert roadmap["attempted_edges"] == 0
    assert result.motion_validity_checks == goal_count
    assert scene.motion_checks == goal_count

    attach_edges = [
        event
        for event in sink.events
        if event.family == "roadmap"
        and event.phase == "query"
        and event.event_type == "attach_edge"
    ]
    assert len(attach_edges) == goal_count
    pairs = [
        tuple(sorted((int(event.payload["src"]), int(event.payload["dst"]))))
        for event in attach_edges
    ]
    assert len(pairs) == len(set(pairs))
    pair_set = set(pairs)
    assert all(
        tuple(event.payload["edge_key"]) in pair_set for event in attach_edges
    )


def test_prm_classifies_after_failed_then_successful_direct_goal() -> None:
    _robot, problem, generator, cands = _ordered_far_near_problem()
    assert len(cands) >= 2
    fail_u = np.asarray(cands[0].state.u, dtype=np.float64)
    scene = CountingScene(problem.scene, reject_end_u=fail_u)
    problem = replace(problem, scene=scene)
    sink = ListPlannerTraceSink()
    result = PRMPlanner(
        seed=23,
        n_samples=0,
        k_neighbors=1,
        max_edge_u=10.0,
        max_goal_candidates=16,
        goal_generator=generator,
        trace_sink=sink,
    ).solve(problem)

    assert result.status is PlanningStatus.SUCCESS
    roadmap = result.planner_metrics["roadmap"]
    goal_count = len(cands)
    assert roadmap["direct_connector_available"] is True
    assert result.selected_goal_candidate is not None
    assert result.selected_goal_candidate.provenance["goal_sample_id"] != cands[
        0
    ].provenance["goal_sample_id"]
    assert roadmap["start_attachment_count"] == goal_count - 1
    assert roadmap["goal_attachment_count"] == goal_count - 1
    assert roadmap["query_unique_edges_attempted"] == goal_count
    assert roadmap["query_unique_edges_accepted"] == goal_count - 1
    assert roadmap["query_duplicate_edge_reuses"] == goal_count
    assert result.motion_validity_checks == goal_count
    assert scene.motion_checks == goal_count

    attach_edges = [
        event
        for event in sink.events
        if event.family == "roadmap"
        and event.phase == "query"
        and event.event_type == "attach_edge"
    ]
    assert len(attach_edges) == goal_count - 1
    pairs = [
        tuple(sorted((int(event.payload["src"]), int(event.payload["dst"]))))
        for event in attach_edges
    ]
    assert len(pairs) == len(set(pairs))


def test_seed_reproducibility_multi_root_rrt() -> None:
    _robot, problem, generator, _cands = _ordered_far_near_problem()
    kwargs = dict(
        seed=17,
        max_iterations=300,
        step_u=0.4,
        goal_bias=0.5,
        max_goal_candidates=16,
        goal_generator=generator,
    )
    a = RRTConnectPlanner(**kwargs).solve(problem)
    b = RRTConnectPlanner(**kwargs).solve(problem)
    assert a.status is PlanningStatus.SUCCESS
    assert b.status is PlanningStatus.SUCCESS
    assert a.objective_cost == pytest.approx(b.objective_cost)
    assert a.planner_metrics["tree"]["iterations"] == b.planner_metrics["tree"][
        "iterations"
    ]
    assert a.planner_metrics["tree"]["selected_goal_root_index"] == b.planner_metrics[
        "tree"
    ]["selected_goal_root_index"]
    assert a.selected_goal_candidate is not None
    assert b.selected_goal_candidate is not None
    assert (
        a.selected_goal_candidate.provenance["goal_sample_id"]
        == b.selected_goal_candidate.provenance["goal_sample_id"]
    )
    assert np.allclose(a.selected_goal_state.u, b.selected_goal_state.u)  # type: ignore[union-attr]
