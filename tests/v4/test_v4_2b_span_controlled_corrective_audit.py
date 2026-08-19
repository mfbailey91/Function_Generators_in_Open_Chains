"""V4.2B common-physical planning audit (V4-226)."""

from __future__ import annotations

import ast
import json
import math
from pathlib import Path

import numpy as np
import pytest

from inequality_mechanisms.audits.v4_artifact_guard import (
    CANONICAL_REPO_ROOT,
    V4_2A_ALLOWED_OUTPUT_REL,
    ArtifactPathForbiddenError,
)
from inequality_mechanisms.experiments.v4.span_common_physical_bank import (
    DEFAULT_BANK_REL,
    load_common_physical_bank,
)
from inequality_mechanisms.experiments.v4.span_controlled_atlas_config import (
    FROZEN_V3_6D_DIGEST,
)
from inequality_mechanisms.experiments.v4.span_controlled_corrective_audit_config import (
    DEFAULT_CONFIG_REL,
    FROZEN_BANK_DIGEST,
    FROZEN_PLANNERS,
    FROZEN_TASK_IDS,
    NO_INFERENCE_STATEMENT,
    V4SpanCorrectiveAuditConfigError,
    load_span_corrective_audit_config,
)

DRIVER_PATH = (
    CANONICAL_REPO_ROOT
    / "src"
    / "inequality_mechanisms"
    / "experiments"
    / "v4"
    / "span_controlled_corrective_audit.py"
)
CASE_ID = "span_j1_145_j2_145"


def test_frozen_config_locks() -> None:
    config = load_span_corrective_audit_config(CANONICAL_REPO_ROOT / DEFAULT_CONFIG_REL)
    assert config.v3_6d_digest_lock == FROZEN_V3_6D_DIGEST
    assert config.source_bank.digest_lock == FROZEN_BANK_DIGEST
    assert tuple(config.task_ids) == FROZEN_TASK_IDS
    assert tuple(config.planners) == FROZEN_PLANNERS
    assert config.lattice.shape == (33, 33)
    assert config.lattice.connectivity == "axis_aligned"
    assert config.lattice.inset_fraction == 0.01
    assert config.animation_policy["authoritative"] == "static_print_panels"
    assert config.no_inference_statement == NO_INFERENCE_STATEMENT


def test_config_refuses_gravity_key(tmp_path: Path) -> None:
    src = json.loads((CANONICAL_REPO_ROOT / DEFAULT_CONFIG_REL).read_text(encoding="utf-8"))
    src["gravity"] = 9.81
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(src), encoding="utf-8")
    with pytest.raises(V4SpanCorrectiveAuditConfigError, match="gravity"):
        load_span_corrective_audit_config(path)


def test_bank_tasks_load_without_v3_reauthoring() -> None:
    import inequality_mechanisms.experiments.v4.span_controlled_corrective_audit as driver

    source = DRIVER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
    assert "realize_span_case" not in imported
    assert "resolve_free_space_tasks_v2" not in imported
    assert "load_free_space_bank_v2" not in imported
    bank = load_common_physical_bank(CANONICAL_REPO_ROOT / DEFAULT_BANK_REL)
    assert bank["sha256"] == FROZEN_BANK_DIGEST
    tasks = driver.tasks_from_common_physical_bank(bank)
    assert tuple(tasks) == FROZEN_TASK_IDS
    first = tasks["near_0"]
    assert first.start_q.shape == (2,)
    assert first.start_tip.shape == (2,)


def test_driver_module_does_not_import_native_q_audit() -> None:
    source = DRIVER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
    assert "inequality_mechanisms.experiments.v4.span_controlled_visual_audit" not in modules
    assert "span_controlled_visual_audit" not in modules


def _mounted_145():
    from inequality_mechanisms.experiments.span_cases import (
        generate_span_cases,
        realize_mounted_span_case,
    )
    from inequality_mechanisms.experiments.v4.span_controlled_atlas import (
        load_locked_v3_6d_registry,
    )
    from inequality_mechanisms.experiments.v4.span_controlled_atlas_config import (
        DEFAULT_CONFIG_REL as ATLAS_REL,
        load_span_atlas_config,
    )

    config = load_span_atlas_config(CANONICAL_REPO_ROOT / ATLAS_REL)
    registry = load_locked_v3_6d_registry(config)
    case = next(c for c in generate_span_cases() if c.case_id == CASE_ID)
    return realize_mounted_span_case(case, registry)


def test_compiled_admitted_ids_and_shared_start() -> None:
    from inequality_mechanisms.experiments.v4.span_controlled_corrective_audit import (
        CommonPhysicalGoalContract,
        _GoalRep,
        assert_mounted_pair,
        compile_mounted_paired_search,
        sampling_arms_for_mounted,
        tasks_from_common_physical_bank,
    )

    realized = _mounted_145()
    arms = sampling_arms_for_mounted(realized, L1=1.0, L2=1.0)
    paired, compiled = compile_mounted_paired_search(
        realized,
        lattice_shape=(5, 5),
        inset_fraction=0.01,
        edge_n_samples=8,
        sampling_arms=arms,
    )
    fb_n = set()
    for u in range(compiled.graph.node_count):
        fb_n.update((u, int(v)) for v in compiled.graph.neighbors(u))
    assert fb_n == set(compiled.admitted_edge_ids)
    bank = load_common_physical_bank(CANONICAL_REPO_ROOT / DEFAULT_BANK_REL)
    task = tasks_from_common_physical_bank(bank)["near_0"]
    pair = assert_mounted_pair(
        realized,
        sampling_arms=arms,
        task=task,
        contract=CommonPhysicalGoalContract(_GoalRep(max_candidates=32)),
    )
    np.testing.assert_allclose(
        pair["starts"]["fourbar"].q, pair["starts"]["gearbox"].q, atol=1e-9
    )
    np.testing.assert_allclose(
        pair["tips"]["fourbar"], pair["tips"]["gearbox"], atol=1e-9
    )
    assert not np.allclose(
        pair["starts"]["fourbar"].u, pair["starts"]["gearbox"].u, atol=1e-9
    )
    assert paired.arms["fourbar"].node_count == paired.arms["gearbox"].node_count


def test_overlay_search_costs_are_finite() -> None:
    from inequality_mechanisms.adapters.paired_lattice_search import (
        OverlayCandidateGraph,
        compile_overlay_search_graph,
    )
    from inequality_mechanisms.audits.planar2r_visual import _goal_candidates
    from inequality_mechanisms.benchmarks.free_space_bank_v2 import build_problem_v2
    from inequality_mechanisms.experiments.v4.span_controlled_corrective_audit import (
        CommonPhysicalGoalContract,
        _GoalRep,
        compile_mounted_paired_search,
        sampling_arms_for_mounted,
        tasks_from_common_physical_bank,
    )
    from inequality_mechanisms.graphs.goal_set_query_overlay import GoalSetQueryOverlay

    realized = _mounted_145()
    arms = sampling_arms_for_mounted(realized, L1=1.0, L2=1.0)
    paired, compiled = compile_mounted_paired_search(
        realized,
        lattice_shape=(5, 5),
        inset_fraction=0.01,
        edge_n_samples=8,
        sampling_arms=arms,
    )
    bank = load_common_physical_bank(CANONICAL_REPO_ROOT / DEFAULT_BANK_REL)
    task = tasks_from_common_physical_bank(bank)["near_0"]
    arm = arms["fourbar"]
    problem = build_problem_v2(arm, task)
    candidates = _goal_candidates(
        arm, task, CommonPhysicalGoalContract(_GoalRep(max_candidates=32))
    )
    overlay = GoalSetQueryOverlay(
        base=paired.arms["fourbar"],
        start_q=np.asarray(problem.start.q, dtype=np.float64),
        goal_qs=[np.asarray(c.state.q, dtype=np.float64) for c in candidates],
        start_u=np.asarray(problem.start.u, dtype=np.float64),
        goal_us=[np.asarray(c.state.u, dtype=np.float64) for c in candidates],
        edge_n_samples=8,
        require_all_goals=True,
    )
    candidate = OverlayCandidateGraph(overlay=overlay, compiled=compiled)
    admitted = set(compiled.admitted_edge_ids)
    base_n = int(overlay.base.node_count)
    for u in range(base_n):
        for v in candidate.neighbors(u):
            if int(v) < base_n:
                assert (int(u), int(v)) in admitted
    search, cost, _rejected = compile_overlay_search_graph(
        overlay,
        compiled,
        arm_name="fourbar",
        robot=arm.robot,
        scene=problem.scene,
        n_samples=8,
        assembly_state=dict(problem.start.assembly_state),
    )
    for u in range(search.node_count):
        if not search.node_is_valid(u):
            continue
        for v in search.neighbors(u):
            weight = float(cost(int(u), int(v)))
            assert math.isfinite(weight)
            assert weight >= 0.0


def test_tmp_export_one_case_one_task(tmp_path: Path) -> None:
    from inequality_mechanisms.experiments.v4.span_controlled_corrective_audit import (
        generate_span_controlled_corrective_audit,
    )

    output = tmp_path / "planning_audit"
    package = generate_span_controlled_corrective_audit(
        output=output,
        case_ids=[CASE_ID],
        task_ids=["near_0"],
        lattice_shape=(5, 5),
    )
    root = Path(package["output"])
    assert root == output.resolve()
    assert int(package["n_silent_drops"]) == 0
    assert int(package["n_rows"]) == len(FROZEN_PLANNERS) * 2
    assert package["common_task_bank_digest"] == FROZEN_BANK_DIGEST
    assert (root / "index.html").is_file()
    assert (root / "summary.json").is_file()
    assert (root / "failures.json").is_file()
    assert (root / "manifest.json").is_file()
    assert (root / "data" / "planner_rows.jsonl.gz").is_file()
    assert (root / "data" / "topology.jsonl.gz").is_file()
    case_page = root / "cases" / CASE_ID / "index.html"
    task_page = root / "cases" / CASE_ID / "tasks" / "near_0.html"
    assert case_page.is_file()
    assert task_page.is_file()
    html = task_page.read_text(encoding="utf-8")
    assert "near_0" in html
    assert "ompl" in html.lower()
    assert list(root.rglob("*.gif")) == []
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    assert summary["n_silent_drops"] == 0
    assert summary["case_ids"] == [CASE_ID]
    ompl_rows = [row for row in summary["rows"] if str(row["planner"]).startswith("ompl")]
    assert len(ompl_rows) == 4
    assert all(row.get("status") or row.get("skipped") for row in ompl_rows)
    marker = CANONICAL_REPO_ROOT / V4_2A_ALLOWED_OUTPUT_REL / ".v4_2b_must_not_write"
    assert not marker.exists()


def test_refuses_frozen_v4_2a_output() -> None:
    from inequality_mechanisms.experiments.v4.span_controlled_corrective_audit import (
        generate_span_controlled_corrective_audit,
    )

    frozen = CANONICAL_REPO_ROOT / V4_2A_ALLOWED_OUTPUT_REL
    with pytest.raises(ArtifactPathForbiddenError, match="V4.2A"):
        generate_span_controlled_corrective_audit(
            output=frozen,
            case_ids=[CASE_ID],
            task_ids=["near_0"],
            lattice_shape=(5, 5),
        )
