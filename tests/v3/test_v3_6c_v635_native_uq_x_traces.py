"""V3-635: native PRM/RRT synchronized U/Q/X traces."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest
from tests.graphs_v2._fixtures import fourbar_2d_branch

from inequality_mechanisms.adapters import planar_2r_operating_branch_robot
from inequality_mechanisms.audits.planar2r_visual import (
    _pack_run,
    _result_core_signature,
    native_trace_connector,
)
from inequality_mechanisms.audits.traces import ListPlannerTraceSink
from inequality_mechanisms.audits.trajectory_evaluation import (
    evaluate_continuous_trajectory,
    evaluate_trajectory_segment,
)
from inequality_mechanisms.core import (
    ActuatorTravelObjective,
    ConstraintSet,
    ExactOutputGoal,
    FreeSpaceScene,
    InputLinearMotion,
    PlanningProblem,
    PlanningStatus,
)
from types import SimpleNamespace

from inequality_mechanisms.kinematics.planar_2r import Planar2R
from inequality_mechanisms.planners import PRMPlanner, RRTConnectPlanner
from inequality_mechanisms.visualization.audit_animation import (
    write_roadmap_tree_growth_animation,
)
from inequality_mechanisms.visualization.audit_search import write_search_panels
from inequality_mechanisms.visualization.audit_trace_geometry import (
    extract_prm_geometry,
    extract_rrt_geometry,
    final_path_samples_from_cte,
    reconstruct_edge_samples,
)


def _robot_problem() -> tuple[Any, PlanningProblem]:
    fk = Planar2R(1.0, 1.0)
    robot = planar_2r_operating_branch_robot(fourbar_2d_branch(), planar_fk=fk)
    cert = robot.branch.certificate
    u_lo = np.asarray(cert.input_lower, dtype=np.float64)
    u_hi = np.asarray(cert.input_upper, dtype=np.float64)
    start = robot.state_from_input(u_lo + 0.2 * (u_hi - u_lo))
    goal_state = robot.state_from_input(u_lo + 0.65 * (u_hi - u_lo))
    problem = PlanningProblem(
        robot=robot,
        scene=FreeSpaceScene(robot=robot),
        start=start,
        goal=ExactOutputGoal(q_goal=goal_state.q.copy()),
        path_constraints=ConstraintSet.empty(),
        local_motion=InputLinearMotion(robot=robot, n_samples=16),
        objective=ActuatorTravelObjective(),
    )
    return robot, problem


def _tiny_graph(robot: Any) -> Any:
    cert = robot.branch.certificate
    q_lo = np.asarray(cert.output_lower, dtype=np.float64)
    q_hi = np.asarray(cert.output_upper, dtype=np.float64)
    q_nodes = np.vstack(
        [
            q_lo + 0.25 * (q_hi - q_lo),
            q_lo + 0.5 * (q_hi - q_lo),
            q_lo + 0.75 * (q_hi - q_lo),
        ]
    )
    u_nodes = np.asarray(
        [robot.states_from_output(q)[0].state.u for q in q_nodes],
        dtype=np.float64,
    )
    return SimpleNamespace(
        q_nodes=q_nodes,
        u_nodes=u_nodes,
        valid_nodes=np.ones(3, dtype=bool),
        node_count=3,
    )


def test_trace_noninterference_prm_and_rrt() -> None:
    _robot, problem = _robot_problem()
    prm0 = PRMPlanner(seed=3, n_samples=24, k_neighbors=6, max_edge_u=1.5).solve(problem)
    sink = ListPlannerTraceSink()
    prm1 = PRMPlanner(
        seed=3, n_samples=24, k_neighbors=6, max_edge_u=1.5, trace_sink=sink
    ).solve(problem)
    assert _result_core_signature(prm0) == _result_core_signature(prm1)
    assert sink.events

    rrt0 = RRTConnectPlanner(
        seed=5, max_iterations=250, step_u=0.35, goal_bias=0.15
    ).solve(problem)
    sink2 = ListPlannerTraceSink()
    rrt1 = RRTConnectPlanner(
        seed=5,
        max_iterations=250,
        step_u=0.35,
        goal_bias=0.15,
        trace_sink=sink2,
    ).solve(problem)
    assert _result_core_signature(rrt0) == _result_core_signature(rrt1)
    assert sink2.events


def test_prm_payloads_include_q_and_reconstructable_endpoints() -> None:
    _robot, problem = _robot_problem()
    sink = ListPlannerTraceSink()
    result = PRMPlanner(
        seed=3, n_samples=20, k_neighbors=5, max_edge_u=1.5, trace_sink=sink
    ).solve(problem)
    assert result.status is PlanningStatus.SUCCESS
    accepts = [e for e in sink.events if e.event_type == "sample_accept"]
    assert accepts
    assert all("q" in e.payload and "u" in e.payload for e in accepts)
    edges = [e for e in sink.events if e.event_type == "edge_accept"]
    assert edges
    for e in edges:
        for key in ("u_i", "q_i", "u_j", "q_j"):
            assert key in e.payload
    attaches = [e for e in sink.events if e.event_type == "attach_edge"]
    assert attaches
    for e in attaches:
        for key in ("u_src", "q_src", "u_dst", "q_dst"):
            assert key in e.payload
    finals = [e for e in sink.events if e.event_type == "final_path"]
    assert finals and "node_ids" in finals[0].payload
    assert finals[0].payload["node_ids"]


def test_rrt_payloads_include_q_and_parent_edges() -> None:
    _robot, problem = _robot_problem()
    sink = ListPlannerTraceSink()
    result = RRTConnectPlanner(
        seed=5,
        max_iterations=300,
        step_u=0.35,
        goal_bias=0.2,
        trace_sink=sink,
    ).solve(problem)
    assert result.status is PlanningStatus.SUCCESS
    inserts = [e for e in sink.events if e.event_type == "vertex_insert"]
    assert inserts
    assert all("q" in e.payload and "u" in e.payload for e in inserts)
    children = [e for e in inserts if e.payload.get("parent") is not None]
    assert children
    assert all("parent_u" in e.payload and "parent_q" in e.payload for e in children)
    roots = [
        e
        for e in inserts
        if e.payload.get("tree") == "goal" and e.payload.get("parent") is None
    ]
    assert roots
    assert all("provenance" in e.payload for e in roots)


def test_accepted_edges_q_x_map_to_same_u_via_connector() -> None:
    robot, problem = _robot_problem()
    sink = ListPlannerTraceSink()
    PRMPlanner(
        seed=3, n_samples=20, k_neighbors=5, max_edge_u=1.5, trace_sink=sink
    ).solve(problem)
    geom = extract_prm_geometry(sink.to_jsonable())
    assert geom.edges
    reconstructed = reconstruct_edge_samples(
        geom.edges, connector=problem.local_motion, robot=robot
    )
    drawn = [r for r in reconstructed if r.drawn]
    assert drawn
    for rec in drawn:
        assert rec.sample_u is not None and rec.sample_q is not None
        assert np.allclose(rec.sample_u[0], rec.edge.start.u)
        assert np.allclose(rec.sample_u[-1], rec.edge.end.u)
        assert np.allclose(rec.sample_q[0], rec.edge.start.q)
        assert np.allclose(rec.sample_q[-1], rec.edge.end.q)
        if rec.sample_x is not None:
            tip0 = np.asarray(
                robot.forward_kinematics(rec.edge.start).position, dtype=np.float64
            )
            tip1 = np.asarray(
                robot.forward_kinematics(rec.edge.end).position, dtype=np.float64
            )
            assert np.allclose(rec.sample_x[0], tip0)
            assert np.allclose(rec.sample_x[-1], tip1)

    sink2 = ListPlannerTraceSink()
    RRTConnectPlanner(
        seed=5, max_iterations=300, step_u=0.35, goal_bias=0.2, trace_sink=sink2
    ).solve(problem)
    geom2 = extract_rrt_geometry(sink2.to_jsonable())
    assert geom2.edges
    reconstructed2 = reconstruct_edge_samples(
        geom2.edges, connector=problem.local_motion, robot=robot
    )
    drawn2 = [r for r in reconstructed2 if r.drawn]
    assert drawn2
    for rec in drawn2:
        assert rec.sample_u is not None and rec.sample_q is not None


def test_projected_edge_set_identical_across_spaces() -> None:
    robot, problem = _robot_problem()
    sink = ListPlannerTraceSink()
    PRMPlanner(
        seed=3, n_samples=18, k_neighbors=5, max_edge_u=1.5, trace_sink=sink
    ).solve(problem)
    geom = extract_prm_geometry(sink.to_jsonable())
    reconstructed = reconstruct_edge_samples(
        geom.edges, connector=problem.local_motion, robot=robot
    )
    keys_u = {r.edge.key for r in reconstructed if r.drawn and r.sample_u is not None}
    keys_q = {r.edge.key for r in reconstructed if r.drawn and r.sample_q is not None}
    keys_x = {r.edge.key for r in reconstructed if r.drawn and r.sample_x is not None}
    assert keys_u == keys_q == keys_x
    assert keys_u == {r.edge.key for r in reconstructed if r.drawn}


def test_final_path_plot_samples_match_cte(tmp_path: Path) -> None:
    robot, problem = _robot_problem()
    sink = ListPlannerTraceSink()
    result = PRMPlanner(
        seed=3, n_samples=24, k_neighbors=6, max_edge_u=1.5, trace_sink=sink
    ).solve(problem)
    assert result.status is PlanningStatus.SUCCESS
    assert result.trajectory is not None
    cte = evaluate_continuous_trajectory(
        result.trajectory.states,
        connector=problem.local_motion,
        robot=robot,
        goal=problem.goal,
        scene=problem.scene,
    )
    run = _pack_run(
        planner="prm",
        mechanism="fourbar",
        result=result,
        skipped=None,
        expanded=None,
        sink=sink,
        robot=robot,
        connector=problem.local_motion,
        goal=problem.goal,
        scene=problem.scene,
    )
    su, sq, sx = final_path_samples_from_cte(run.planner_metrics)
    assert su is not None and sq is not None
    assert cte.segments
    assert np.allclose(su[: cte.segments[0].n_samples], cte.segments[0].sample_u)
    assert np.allclose(sq[: cte.segments[0].n_samples], cte.segments[0].sample_q)
    if sx is not None and cte.segments[0].sample_x is not None:
        assert np.allclose(sx[: cte.segments[0].n_samples], cte.segments[0].sample_x)

    graph = _tiny_graph(robot)
    assets = write_search_panels(
        graph=graph,
        robot=robot,
        run=run,
        out_dir=tmp_path,
        task_id="near_0",
        connector=problem.local_motion,
    )
    assert "final_trace_u" in assets and assets["final_trace_u"].is_file()
    assert "final_trace_q" in assets and assets["final_trace_q"].is_file()
    assert "final_trace_x" in assets and assets["final_trace_x"].is_file()
    assert assets["final_trace"] == assets["final_trace_u"]


def test_static_uq_x_and_growth_for_designated_tasks(tmp_path: Path) -> None:
    robot, problem = _robot_problem()
    sink = ListPlannerTraceSink()
    result = RRTConnectPlanner(
        seed=5, max_iterations=300, step_u=0.35, goal_bias=0.2, trace_sink=sink
    ).solve(problem)
    run = _pack_run(
        planner="rrt_connect",
        mechanism="gearbox",
        result=result,
        skipped=None,
        expanded=None,
        sink=sink,
        robot=robot,
        connector=problem.local_motion,
        goal=problem.goal,
        scene=problem.scene,
    )
    graph = _tiny_graph(robot)
    connector = native_trace_connector(robot, n_samples=16)
    assets = write_search_panels(
        graph=graph,
        robot=robot,
        run=run,
        out_dir=tmp_path / "static",
        task_id="far_2",
        connector=connector,
    )
    for space in ("u", "q", "x"):
        assert assets[f"final_trace_{space}"].is_file()

    designated = ("near_0", "near_3", "far_2")
    for task_id in designated:
        growth = write_roadmap_tree_growth_animation(
            task_id=task_id,
            mechanism="gearbox",
            planner="rrt_connect",
            run=run,
            out_dir=tmp_path / "growth" / task_id,
            fractions=(0.0, 0.5, 1.0),
            n_frames=3,
            connector=connector,
            robot=robot,
        )
        assert growth["anim"].is_file()
        assert growth["contact"].is_file()
        assert growth["contact_u"].is_file()
        assert growth["contact_q"].is_file()
        assert growth["contact_x"].is_file()


def test_fail_closed_missing_q_no_silent_chords() -> None:
    robot, problem = _robot_problem()
    events = [
        {
            "family": "roadmap",
            "phase": "edge",
            "step": 0,
            "event_type": "edge_accept",
            "payload": {
                "i": 0,
                "j": 1,
                "dist_u": 0.1,
                "u_i": [0.1, 0.1],
                "u_j": [0.2, 0.2],
            },
        }
    ]
    geom = extract_prm_geometry(events)
    assert geom.edges == ()
    reconstructed = reconstruct_edge_samples(
        geom.edges, connector=problem.local_motion, robot=robot
    )
    assert reconstructed == []

    start = problem.start
    seg = evaluate_trajectory_segment(
        start,
        start,
        connector=problem.local_motion,
        robot=robot,
    )
    if not seg.valid:
        assert seg.sample_u is None and seg.sample_q is None
    else:
        assert seg.sample_u is not None
