"""Sprint V3.6B planar-2R visual audit invariants (V3-629)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from inequality_mechanisms.adapters import GraphSearchPlanner
from inequality_mechanisms.audits.planar2r_visual import (
    COST_TOL,
    WEIGHT_TOL,
    _goal_candidates,
    _result_core_signature,
    assert_shared_wq_wx,
    attach_composites,
    compute_mechanism_edge_metrics,
    load_audit_config,
    resolve_audit_trials,
    run_planner_for_trial,
)
from inequality_mechanisms.audits.traces import ListPlannerTraceSink
from inequality_mechanisms.benchmarks.free_space_bank import build_bank_arms
from inequality_mechanisms.benchmarks.free_space_bank_v2 import (
    build_problem_v2,
    goal_generator_v2,
    load_free_space_bank_v2,
    resolve_free_space_tasks_v2,
)
from inequality_mechanisms.benchmarks.smoke_lattice_2r import build_paired_lattice_arms
from inequality_mechanisms.core.goals import ExactOutputGoal
from inequality_mechanisms.core.problem import PlanningProblem
from inequality_mechanisms.core.results import PlanningStatus
from inequality_mechanisms.graphs.topology import LatticeConnectivity
from inequality_mechanisms.planners.roadmap.prm import PRMPlanner


@pytest.fixture(scope="module")
def audit_config():
    return load_audit_config()


@pytest.fixture(scope="module")
def bank_bundle(audit_config):
    bank_path = audit_config.path.parent / audit_config.raw["source_bank"]["contract_path"]
    contract = load_free_space_bank_v2(bank_path)
    arms = build_bank_arms(contract.base_bank)
    tasks = {t.task_id: t for t in resolve_free_space_tasks_v2(contract, arms=arms)}
    lattice = build_paired_lattice_arms(
        shape=(8, 8), connectivity=LatticeConnectivity.CHEBYSHEV_1
    )
    return contract, arms, tasks, lattice


def _fast_cfg():
    cfg = load_audit_config()
    cfg.raw["lattice"]["shape"] = [8, 8]
    cfg.raw["planner_settings"]["prm"]["n_samples"] = 24
    cfg.raw["planner_settings"]["rrt_connect"]["max_iterations"] = 120
    cfg.raw["planner_settings"]["ompl"]["solve_time_s"] = 0.25
    return cfg


def test_config_contract_frozen(audit_config):
    assert audit_config.seed == 7
    assert set(audit_config.task_ids) == {
        "near_0", "near_1", "near_2", "near_3", "near_4",
        "far_0", "far_1", "far_2", "far_3", "far_4",
    }
    assert audit_config.lattice_shape == (32, 32)
    assert "lattice_dijkstra" in audit_config.planners
    assert "ompl_rrt_connect" in audit_config.planners
    assert audit_config.raw["delta_convention"]["expression"].startswith("delta_z")
    assert "no_inference_statement" in audit_config.raw


def test_pair_invariants_resolver(audit_config, bank_bundle):
    _contract, arms, _tasks, _lattice = bank_bundle
    trials = resolve_audit_trials(
        audit_config, sampling_arms=arms, lattice_shape=(8, 8)
    )
    assert len(trials) == 10
    assert {t.task_id for t in trials} == set(audit_config.task_ids)
    for trial in trials:
        assert "fourbar" in trial.starts and "gearbox" in trial.starts
        assert trial.starts["fourbar"]["q"] == pytest.approx(
            trial.starts["gearbox"]["q"], abs=1e-9, rel=0.0
        )
        assert list(trial.starts["fourbar"]["u"]) != list(trial.starts["gearbox"]["u"])


def test_shared_wq_wx_mechanism_specific_wu(bank_bundle):
    _contract, arms, _tasks, lattice = bank_bundle
    fb = compute_mechanism_edge_metrics(lattice["fourbar"], arms["fourbar"], n_samples=12)
    gb = compute_mechanism_edge_metrics(lattice["gearbox"], arms["gearbox"], n_samples=12)
    assert_shared_wq_wx(fb, gb, tol=WEIGHT_TOL)
    fb_map = {(e.a, e.b): e for e in fb.edges}
    gb_map = {(e.a, e.b): e for e in gb.edges}
    diffs = [
        abs(fb_map[k].w_u - gb_map[k].w_u)
        for k in fb_map
        if np.isfinite(fb_map[k].w_u) and np.isfinite(gb_map[k].w_u)
    ]
    assert diffs and max(diffs) > WEIGHT_TOL


def test_dijkstra_astar_cost_parity(bank_bundle):
    contract, arms, tasks, lattice = bank_bundle
    cfg = _fast_cfg()
    task = tasks["near_0"]
    runs = {}
    for planner in ("lattice_dijkstra", "lattice_astar"):
        for mech in ("fourbar", "gearbox"):
            runs[(mech, planner)] = run_planner_for_trial(
                config=cfg,
                planner_name=planner,
                arm=arms[mech],
                lattice_arm=lattice[mech],
                task=task,
                contract=contract,
                capture_trace=True,
            )
    for mech in ("fourbar", "gearbox"):
        d = runs[(mech, "lattice_dijkstra")]
        a = runs[(mech, "lattice_astar")]
        if d.status == PlanningStatus.SUCCESS and a.status == PlanningStatus.SUCCESS:
            assert d.objective_cost == pytest.approx(a.objective_cost, abs=COST_TOL)


def test_direct_lower_bound(bank_bundle):
    contract, arms, tasks, lattice = bank_bundle
    cfg = _fast_cfg()
    task = tasks["near_0"]
    for mech in ("fourbar", "gearbox"):
        direct = run_planner_for_trial(
            config=cfg,
            planner_name="input_linear",
            arm=arms[mech],
            lattice_arm=lattice[mech],
            task=task,
            contract=contract,
            capture_trace=False,
        )
        lattice_run = run_planner_for_trial(
            config=cfg,
            planner_name="lattice_dijkstra",
            arm=arms[mech],
            lattice_arm=lattice[mech],
            task=task,
            contract=contract,
            capture_trace=False,
        )
        if (
            direct.status == PlanningStatus.SUCCESS
            and lattice_run.status == PlanningStatus.SUCCESS
            and direct.objective_cost is not None
            and lattice_run.objective_cost is not None
        ):
            assert direct.objective_cost <= lattice_run.objective_cost + 1e-6


def test_trace_noninterference(bank_bundle):
    contract, arms, tasks, lattice = bank_bundle
    task = tasks["near_0"]
    arm = arms["fourbar"]
    graph = lattice["fourbar"].graph
    problem = build_problem_v2(arm, task)
    cands = _goal_candidates(arm, task, contract)
    assert cands
    exact = PlanningProblem(
        robot=problem.robot,
        scene=problem.scene,
        start=problem.start,
        goal=ExactOutputGoal(q_goal=np.asarray(cands[0].state.q, dtype=np.float64)),
        path_constraints=problem.path_constraints,
        local_motion=problem.local_motion,
        objective=problem.objective,
    )
    r0 = GraphSearchPlanner(
        graph=graph, algorithm="dijkstra", edge_cost_mode="integrated", record_expanded=False
    ).solve(exact)
    sink = ListPlannerTraceSink()
    r1 = GraphSearchPlanner(
        graph=graph,
        algorithm="dijkstra",
        edge_cost_mode="integrated",
        record_expanded=True,
        trace_sink=sink,
    ).solve(exact)
    assert _result_core_signature(r0) == _result_core_signature(r1)
    assert sink.events
    gen = goal_generator_v2(arm, task)
    p0 = PRMPlanner(seed=7, n_samples=24, k_neighbors=6, max_edge_u=1.25, goal_generator=gen).solve(
        problem
    )
    sink2 = ListPlannerTraceSink()
    p1 = PRMPlanner(
        seed=7,
        n_samples=24,
        k_neighbors=6,
        max_edge_u=1.25,
        goal_generator=gen,
        trace_sink=sink2,
    ).solve(problem)
    assert _result_core_signature(p0) == _result_core_signature(p1)
    assert any(e.event_type.startswith("sample_") for e in sink2.events)


def test_complete_mechanism_planner_rows(bank_bundle):
    contract, arms, tasks, lattice = bank_bundle
    cfg = _fast_cfg()
    task = tasks["far_2"]
    rows = []
    for mech in ("fourbar", "gearbox"):
        for planner in cfg.planners:
            rows.append(
                run_planner_for_trial(
                    config=cfg,
                    planner_name=planner,
                    arm=arms[mech],
                    lattice_arm=lattice[mech],
                    task=task,
                    contract=contract,
                    capture_trace=False,
                )
            )
    assert len(rows) == 2 * len(cfg.planners)
    assert {r.mechanism for r in rows} == {"fourbar", "gearbox"}
    for r in rows:
        assert r.planner in cfg.planners
        if r.skipped == "ompl_unavailable":
            assert r.status == "unavailable"
        else:
            assert r.status in {
                PlanningStatus.SUCCESS,
                PlanningStatus.UNSOLVED,
                PlanningStatus.INVALID,
                "success",
                "unsolved",
                "invalid",
            }


def test_export_mini_report_deterministic(tmp_path):
    script = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "export_v3_6b_planar2r_visual_audit.py"
    )
    spec = importlib.util.spec_from_file_location("export_v3_6b", script)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    out1 = tmp_path / "a"
    out2 = tmp_path / "b"
    args = [
        "--output",
        str(out1),
        "--task-ids",
        "near_0",
        "--lattice-shape",
        "6",
        "6",
        "--skip-animations",
    ]
    assert mod.main(args) == 0
    args[1] = str(out2)
    assert mod.main(args) == 0
    man1 = json.loads((out1 / "manifest.json").read_text(encoding="utf-8"))
    assert man1["task_ids"] == ["near_0"]
    assert (out1 / "index.html").is_file()
    assert (out1 / "architecture.html").is_file()
    trial_html = (out1 / "trials" / "near_0" / "index.html").read_text(encoding="utf-8")
    assert "@media print" in trial_html
    assert "anim-live" in trial_html
    assert "contact-sheet" in trial_html
    assert (out1 / "trials" / "near_0" / "trial.json").is_file()
    assert (out1 / "trials" / "near_0" / "runs.json").is_file()
    for asset in man1["assets"]:
        assert (out1 / asset["path"]).is_file(), asset["path"]
    # Both mechanisms present in runs even if a planner fails.
    runs = json.loads((out1 / "trials" / "near_0" / "runs.json").read_text(encoding="utf-8"))
    assert {r["mechanism"] for r in runs} == {"fourbar", "gearbox"}
    assert {r["planner"] for r in runs} >= {
        "input_linear",
        "output_linear",
        "lattice_dijkstra",
        "lattice_astar",
        "prm",
        "rrt_connect",
        "ompl_prm",
        "ompl_rrt_connect",
    }


def test_composite_components_exposed(bank_bundle):
    contract, arms, tasks, lattice = bank_bundle
    cfg = _fast_cfg()
    task = tasks["near_0"]
    runs = []
    for mech in ("fourbar", "gearbox"):
        runs.append(
            run_planner_for_trial(
                config=cfg,
                planner_name="input_linear",
                arm=arms[mech],
                lattice_arm=lattice[mech],
                task=task,
                contract=contract,
                capture_trace=False,
            )
        )
    runs = attach_composites(runs, config=cfg)
    for r in runs:
        assert "components_unnormalized" in r.composite
        assert "weights" in r.composite
        assert "J_alpha" in r.composite
