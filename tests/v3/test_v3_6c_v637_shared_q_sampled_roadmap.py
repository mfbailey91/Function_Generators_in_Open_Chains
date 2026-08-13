"""V3-637: frozen shared-Q sampled-roadmap diagnostic invariants."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from tests.graphs_v2._fixtures import fourbar_2d_branch

from inequality_mechanisms.adapters.lattice_edge_cost import integrated_actuator_edge_cost
from inequality_mechanisms.adapters.planar_2r_robot import (
    planar_2r_operating_branch_robot,
)
from inequality_mechanisms.audits.planar2r_visual import (
    freeze_shared_q_sampled_pair,
    load_audit_config,
    run_planner_for_trial,
)
from inequality_mechanisms.audits.shared_q_sampled_roadmap import (
    METRICS_KEY,
    PLANNER_ID_ASTAR,
    PLANNER_ID_DIJKSTRA,
    solve_shared_q_sampled_roadmap,
)
from inequality_mechanisms.benchmarks.free_space_bank import build_bank_arms
from inequality_mechanisms.benchmarks.free_space_bank_v2 import (
    load_free_space_bank_v2,
    resolve_free_space_tasks_v2,
)
from inequality_mechanisms.benchmarks.smoke_lattice_2r import build_paired_lattice_arms
from inequality_mechanisms.core import (
    ActuatorTravelObjective,
    ConstraintSet,
    ExactOutputGoal,
    FreeSpaceScene,
    InputLinearMotion,
    PhysicalState,
    PlanningProblem,
    PlanningStatus,
    StateCandidate,
)
from inequality_mechanisms.graphs.pair_invariants import SharedQPairInvariantError
from inequality_mechanisms.graphs.sampled_q_query_overlay import (
    SampledQQueryOverlay,
    assert_identical_sampled_q_query_overlays,
)
from inequality_mechanisms.graphs.sampled_q_roadmap import (
    assert_identical_sampled_q_graphs,
    embed_paired_sampled_q_roadmaps,
    freeze_reusable_q_sample_bank,
)
from inequality_mechanisms.graphs.topology import LatticeConnectivity
from inequality_mechanisms.kinematics.planar_2r import Planar2R
from inequality_mechanisms.mechanisms import equivalent_gearbox_branch
from inequality_mechanisms.planners.roadmap.prm import PRMPlanner

REPO_ROOT = Path(__file__).resolve().parents[2]
CLOSEOUT_CONFIG = REPO_ROOT / "configs" / "v3" / "planar2r_closeout_v1.json"

SEED = 7
N_SAMPLES = 24
K_NEIGHBORS = 6
MAX_EDGE_Q = 2.0
EDGE_N_SAMPLES = 8


def _paired_branches():
    fourbar = fourbar_2d_branch()
    gearbox = equivalent_gearbox_branch(fourbar, name="span_matched_gearbox")
    return {"fourbar": fourbar, "gearbox": gearbox}


def _freeze_pair():
    branches = _paired_branches()
    bank = freeze_reusable_q_sample_bank(
        branches["fourbar"].output_space,
        n_samples=N_SAMPLES,
        k_neighbors=K_NEIGHBORS,
        max_edge_q=MAX_EDGE_Q,
        seed=SEED,
    )
    graphs = embed_paired_sampled_q_roadmaps(bank, branches)
    robots = {
        name: planar_2r_operating_branch_robot(branch, planar_fk=Planar2R(1.0, 1.0))
        for name, branch in branches.items()
    }
    return bank, graphs, robots


def _valid_ids(graph) -> list[int]:
    return [i for i in range(graph.node_count) if graph.node_is_valid(i)]


def _state_from_node(graph, robot, node_id: int) -> PhysicalState:
    u = graph.u_state(node_id)
    return PhysicalState(
        u=u,
        q=graph.q_state(node_id),
        assembly_state=dict(robot.state_from_input(u).assembly_state),
        auxiliary_state={"sampled_q_node_id": int(node_id)},
    )


def _candidate(graph, robot, node_id: int, *, index: int, sample_id: str) -> StateCandidate:
    state = _state_from_node(graph, robot, node_id)
    tip = np.asarray(robot.forward_kinematics(state).position, dtype=np.float64)
    return StateCandidate(
        state=state,
        residual=0.0,
        provenance={
            "goal_sample_id": sample_id,
            "goal_sample_index": int(index),
            "goal_sample_point": tip.tolist(),
            "ik_family": "sampled_q_fixture",
            "candidate_generator_id": "v3_637_test",
        },
    )


def _problem(robot, start: PhysicalState, goal) -> PlanningProblem:
    return PlanningProblem(
        robot=robot,
        scene=FreeSpaceScene(robot=robot),
        start=start,
        goal=goal,
        path_constraints=ConstraintSet.empty(),
        local_motion=InputLinearMotion(robot=robot, n_samples=EDGE_N_SAMPLES),
        objective=ActuatorTravelObjective(),
    )


def test_closeout_config_declares_diagnostic_separately_from_prm() -> None:
    data = json.loads(CLOSEOUT_CONFIG.read_text(encoding="utf-8"))
    planners = data["planners"]
    assert "shared_q_sampled_dijkstra" in planners
    assert "shared_q_sampled_astar" in planners
    assert "prm" in planners
    settings = data["planner_settings"]["shared_q_sampled_roadmap"]
    assert settings["bank_mode"] == "reusable"
    assert settings["n_samples"] == 80
    assert settings["k_neighbors"] == 10
    assert settings["max_edge_q"] == 0.75
    assert data["planner_settings"]["prm"]["max_edge_u"] == 1.25
    assert "max_edge_q" not in data["planner_settings"]["prm"]


def test_identical_q_vertices_and_edges_across_pair() -> None:
    bank, graphs, _robots = _freeze_pair()
    fb = graphs["fourbar"]
    gb = graphs["gearbox"]
    assert_identical_sampled_q_graphs(fb, gb)
    assert fb.bank is bank
    assert gb.bank is bank
    assert np.array_equal(fb.q_nodes, gb.q_nodes)
    assert fb.edges == gb.edges
    assert fb.edges == bank.edges
    assert not np.allclose(fb.u_nodes, gb.u_nodes, equal_nan=True)


def test_separately_frozen_banks_with_same_seed_match() -> None:
    branches = _paired_branches()
    a = freeze_reusable_q_sample_bank(
        branches["fourbar"].output_space,
        n_samples=N_SAMPLES,
        k_neighbors=K_NEIGHBORS,
        max_edge_q=MAX_EDGE_Q,
        seed=SEED,
    )
    b = freeze_reusable_q_sample_bank(
        branches["gearbox"].output_space,
        n_samples=N_SAMPLES,
        k_neighbors=K_NEIGHBORS,
        max_edge_q=MAX_EDGE_Q,
        seed=SEED,
    )
    assert np.array_equal(a.q_samples, b.q_samples)
    assert a.edges == b.edges


def test_failed_integrated_cost_does_not_mutate_adjacency() -> None:
    _bank, graphs, robots = _freeze_pair()
    fb = graphs["fourbar"]
    edges_before = fb.edges
    adj_before = fb.bank.frozen_adjacency
    assembly = dict(
        robots["fourbar"].state_from_input(fb.u_state(_valid_ids(fb)[0])).assembly_state
    )
    cost = integrated_actuator_edge_cost(
        fb,
        robots["fourbar"],
        n_samples=EDGE_N_SAMPLES,
        assembly_state=assembly,
    )
    for a, b in fb.edges[: min(8, len(fb.edges))]:
        if fb.node_is_valid(a) and fb.node_is_valid(b):
            value = float(cost(a, b))
            assert value >= 0.0
    assert fb.edges is edges_before or fb.edges == edges_before
    assert fb.bank.frozen_adjacency == adj_before


def test_query_overlay_q_neighbors_and_ordered_goals_match() -> None:
    _bank, graphs, robots = _freeze_pair()
    valid = _valid_ids(graphs["fourbar"])
    assert len(valid) >= 4
    start_id, g0, g1 = valid[0], valid[-2], valid[-1]
    overlays = {}
    for name in ("fourbar", "gearbox"):
        graph = graphs[name]
        robot = robots[name]
        start = _state_from_node(graph, robot, start_id)
        cands = [
            _candidate(graph, robot, g0, index=0, sample_id="goal_a"),
            _candidate(graph, robot, g1, index=1, sample_id="goal_b"),
        ]
        overlays[name] = SampledQQueryOverlay(
            base=graph,
            start_q=start.q,
            start_u=start.u,
            goal_qs=[c.state.q for c in cands],
            goal_us=[c.state.u for c in cands],
        )
        assert overlays[name].goal_node_ids[0] == graph.node_count + 1
        atts = overlays[name].attachments_as_dicts()
        goal_atts = [a for a in atts if a["role"] == "goal"]
        assert [a["goal_index"] for a in goal_atts] == [0, 1]
    assert_identical_sampled_q_query_overlays(overlays["fourbar"], overlays["gearbox"])
    broken = SampledQQueryOverlay(
        base=graphs["fourbar"],
        start_q=overlays["fourbar"].q_state(overlays["fourbar"].start_node_id),
        start_u=overlays["fourbar"].u_state(overlays["fourbar"].start_node_id),
        goal_qs=[
            overlays["fourbar"].q_state(nid)
            for nid in overlays["fourbar"].goal_node_ids[:1]
        ],
        goal_us=[
            overlays["fourbar"].u_state(nid)
            for nid in overlays["fourbar"].goal_node_ids[:1]
        ],
    )
    with pytest.raises(SharedQPairInvariantError):
        assert_identical_sampled_q_query_overlays(overlays["fourbar"], broken)


def test_dijkstra_astar_cost_parity_and_provenance() -> None:
    _bank, graphs, robots = _freeze_pair()
    graph = graphs["fourbar"]
    robot = robots["fourbar"]
    valid = _valid_ids(graph)
    start = _state_from_node(graph, robot, valid[0])
    candidates = [
        _candidate(graph, robot, valid[-3], index=0, sample_id="near_goal"),
        _candidate(graph, robot, valid[-1], index=1, sample_id="far_goal"),
    ]
    problem = _problem(
        robot,
        start,
        ExactOutputGoal(q_goal=np.asarray(candidates[0].state.q, dtype=np.float64)),
    )
    dijkstra = solve_shared_q_sampled_roadmap(
        graph=graph,
        problem=problem,
        candidates=candidates,
        algorithm="dijkstra",
        edge_n_samples=EDGE_N_SAMPLES,
    )
    astar = solve_shared_q_sampled_roadmap(
        graph=graph,
        problem=problem,
        candidates=candidates,
        algorithm="astar",
        edge_n_samples=EDGE_N_SAMPLES,
    )
    assert dijkstra.status is PlanningStatus.SUCCESS
    assert astar.status is PlanningStatus.SUCCESS
    assert dijkstra.objective_cost == pytest.approx(astar.objective_cost, abs=1e-9)
    assert dijkstra.selected_goal_candidate is not None
    assert astar.selected_goal_candidate is not None
    assert (
        dijkstra.selected_goal_candidate.provenance["goal_sample_id"]
        == astar.selected_goal_candidate.provenance["goal_sample_id"]
    )
    assert dijkstra.selected_goal_candidate.provenance["goal_sample_id"] in {
        "near_goal",
        "far_goal",
    }
    assert dijkstra.provenance.planner_id == PLANNER_ID_DIJKSTRA
    assert astar.provenance.planner_id == PLANNER_ID_ASTAR
    assert dijkstra.provenance.planner_id != PRMPlanner().planner_id
    assert METRICS_KEY in dijkstra.planner_metrics
    assert "roadmap" not in dijkstra.planner_metrics
    assert dijkstra.planner_metrics[METRICS_KEY]["heuristic_name"] == "zero"
    assert astar.planner_metrics[METRICS_KEY]["heuristic_name"] == (
        "input_euclidean_goal_set"
    )
    assert dijkstra.planner_metrics[METRICS_KEY]["goal_candidate_count"] == 2
    assert dijkstra.goal_residuals is not None


def test_pair_solve_keeps_same_ordered_goal_set() -> None:
    _bank, graphs, robots = _freeze_pair()
    valid = _valid_ids(graphs["fourbar"])
    results = {}
    for name in ("fourbar", "gearbox"):
        graph = graphs[name]
        robot = robots[name]
        start = _state_from_node(graph, robot, valid[1])
        candidates = [
            _candidate(graph, robot, valid[-2], index=0, sample_id="g0"),
            _candidate(graph, robot, valid[-1], index=1, sample_id="g1"),
        ]
        problem = _problem(
            robot,
            start,
            ExactOutputGoal(q_goal=np.asarray(candidates[0].state.q, dtype=np.float64)),
        )
        results[name] = solve_shared_q_sampled_roadmap(
            graph=graph,
            problem=problem,
            candidates=candidates,
            algorithm="dijkstra",
            edge_n_samples=EDGE_N_SAMPLES,
        )
        metrics = results[name].planner_metrics[METRICS_KEY]
        assert metrics["goal_candidate_count"] == 2
        ids = [
            att["goal_index"]
            for att in results[name].planner_metrics["graph"]["attachments"]
            if att["role"] == "goal"
        ]
        assert ids == [0, 1]
    assert results["fourbar"].status is PlanningStatus.SUCCESS
    assert results["gearbox"].status is PlanningStatus.SUCCESS
    assert graphs["fourbar"].edges == graphs["gearbox"].edges


def test_audit_dispatch_asserts_shared_bank_and_labels() -> None:
    cfg = load_audit_config(CLOSEOUT_CONFIG)
    cfg.raw["planner_settings"]["shared_q_sampled_roadmap"]["n_samples"] = N_SAMPLES
    cfg.raw["planner_settings"]["shared_q_sampled_roadmap"]["k_neighbors"] = K_NEIGHBORS
    cfg.raw["planner_settings"]["shared_q_sampled_roadmap"]["max_edge_q"] = MAX_EDGE_Q
    cfg.raw["planner_settings"]["shared_q_sampled_roadmap"]["edge_n_samples"] = (
        EDGE_N_SAMPLES
    )
    lattice = build_paired_lattice_arms(
        shape=(6, 6), connectivity=LatticeConnectivity.CHEBYSHEV_1
    )
    bank, graphs = freeze_shared_q_sampled_pair(cfg, lattice)
    assert_identical_sampled_q_graphs(graphs["fourbar"], graphs["gearbox"])
    assert bank.seed == SEED
    assert bank.bank_mode == "reusable"

    contract = load_free_space_bank_v2(
        cfg.path.parent / str(cfg.raw["source_bank"]["contract_path"])
    )
    arms = build_bank_arms(contract.base_bank)
    tasks = {t.task_id: t for t in resolve_free_space_tasks_v2(contract, arms=arms)}
    task = tasks["near_0"]
    run_fb = run_planner_for_trial(
        config=cfg,
        planner_name="shared_q_sampled_dijkstra",
        arm=arms["fourbar"],
        lattice_arm=lattice["fourbar"],
        task=task,
        contract=contract,
        capture_trace=False,
        lattice_arms=lattice,
    )
    run_gb = run_planner_for_trial(
        config=cfg,
        planner_name="shared_q_sampled_dijkstra",
        arm=arms["gearbox"],
        lattice_arm=lattice["gearbox"],
        task=task,
        contract=contract,
        capture_trace=False,
        lattice_arms=lattice,
    )
    assert run_fb.result is not None
    assert run_gb.result is not None
    assert run_fb.result.provenance.planner_id == PLANNER_ID_DIJKSTRA
    assert run_fb.result.provenance.planner_id != PRMPlanner().planner_id
    assert METRICS_KEY in run_fb.planner_metrics
    assert "roadmap" not in run_fb.planner_metrics
    assert run_fb.planner_metrics[METRICS_KEY]["bank_mode"] == "reusable"
    assert run_gb.planner_metrics[METRICS_KEY]["n_samples"] == N_SAMPLES
