"""V4.2B mounted-Q common-physical planning audit driver.

Consumes the frozen V3.6D registry through mounted realization and the
frozen common-physical task bank. Lattice Dijkstra/A* search the jointly
compiled paired topology. Identity-on-shared-Q is not a planner arm.
"""

from __future__ import annotations

import gzip
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib
import numpy as np

matplotlib.use("Agg")

from inequality_mechanisms.adapters.lattice_edge_cost import (
    connector_for_graph,
    integrated_actuator_edge_cost,
)
from inequality_mechanisms.adapters.paired_lattice_search import solve_paired_lattice_goal_set
from inequality_mechanisms.adapters.planar_2r_robot import planar_2r_operating_branch_robot
from inequality_mechanisms.audits.planar2r_visual import (
    AuditConfig,
    PlannerRunRecord,
    _goal_candidates,
    _pack_run,
    compute_mechanism_edge_metrics,
    native_trace_connector,
    paired_delta,
    provenance_block,
    run_planner_for_trial,
)
from inequality_mechanisms.audits.v4_2b_artifact import (
    MANIFEST_INVENTORY_RULE,
    files_digest,
    inventory_file,
    media_for,
)
from inequality_mechanisms.audits.v4_artifact_guard import (
    CANONICAL_REPO_ROOT,
    ArtifactPathForbiddenError,
    allowed_v4_2b_output_root,
    assert_v4_2b_output_allowed,
    git_rev_parse_head,
    git_status_porcelain,
)
from inequality_mechanisms.benchmarks.free_space_bank_v2 import (
    ResolvedFreeSpaceTaskV2,
    build_problem_v2,
    state_from_shared_q,
)
from inequality_mechanisms.benchmarks.smoke_lattice_2r import LatticeSmokeArm
from inequality_mechanisms.benchmarks.smoke_sampling_2r import SamplingSmokeArm
from inequality_mechanisms.experiments.span_cases import (
    RealizedSpanCase,
    generate_span_cases,
    realize_mounted_span_case,
)
from inequality_mechanisms.experiments.v4.geometry_atlas import git_revision
from inequality_mechanisms.experiments.v4.span_common_physical_bank import (
    DEFAULT_BANK_REL,
    load_common_physical_bank,
)
from inequality_mechanisms.experiments.v4.span_controlled_atlas import (
    load_locked_v3_6d_registry,
)
from inequality_mechanisms.experiments.v4.span_controlled_atlas_config import (
    DEFAULT_CONFIG_REL as V4_2_DEFAULT_CONFIG_REL,
    FROZEN_V3_6D_DIGEST,
    SPAN_175_STATUS,
    load_span_atlas_config,
)
from inequality_mechanisms.experiments.v4.span_controlled_corrective_audit_config import (
    DEFAULT_CONFIG_REL,
    FROZEN_BANK_DIGEST,
    FROZEN_PLANNERS,
    NO_INFERENCE_STATEMENT,
    SpanControlledCorrectiveAuditConfig,
    load_span_corrective_audit_config,
)
from inequality_mechanisms.experiments.v4.span_controlled_corrective_config import (
    V4_2B_PACKAGE,
)
from inequality_mechanisms.graphs.paired_edge_admission import (
    PairedCompiledSearchGraph,
    compile_paired_q_search_graph,
)
from inequality_mechanisms.graphs.paired_q_planning import build_paired_q_planning_graph
from inequality_mechanisms.graphs.topology import LatticeConnectivity
from inequality_mechanisms.kinematics.planar_2r import Planar2R
from inequality_mechanisms.visualization.audit_graphs import write_graph_panels
from inequality_mechanisms.visualization.audit_mapping import write_mapping_panels
from inequality_mechanisms.visualization.audit_search import (
    write_direct_comparison,
    write_search_panels,
)
from inequality_mechanisms.visualization.v4.span_controlled_corrective_audit import (
    write_case_audit_html,
    write_planning_audit_root_html,
    write_task_audit_html,
)

_POSE_ATOL = 1e-9
_MOUNTED_KIND = "mounted_joint"
PLANNING_PACKAGE = f"{V4_2B_PACKAGE}/planning_audit"
PLANNING_SCHEMA = "v4.2b.planar2r.span_controlled_corrective.v1"


class SpanCorrectiveAuditError(ValueError):
    """Typed V4.2B planning-audit construction failure."""

    failure_code = "span_corrective_audit_failed"


@dataclass(frozen=True)
class _GoalRep:
    max_candidates: int


@dataclass(frozen=True)
class CommonPhysicalGoalContract:
    """Shim so reused candidate helpers read max_candidates only."""

    goal_representation: _GoalRep


def _rel(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _is_under(path: Path, parent: Path) -> bool:
    path_r = path.resolve()
    parent_r = parent.resolve()
    return path_r == parent_r or parent_r in path_r.parents


def _refuse_historical_output(output: Path) -> Path:
    from inequality_mechanisms.audits.v4_artifact_guard import (
        canonical_v4_0_retained_root,
        canonical_v4_1_retained_root,
        canonical_v4_2_retained_root,
        canonical_v4_2a_retained_root,
    )

    resolved = Path(output).expanduser().resolve()
    historical = (
        (canonical_v4_0_retained_root(), "frozen V4.0"),
        (canonical_v4_1_retained_root(), "frozen V4.1"),
        (canonical_v4_2_retained_root(), "frozen V4.2"),
        (canonical_v4_2a_retained_root(), "frozen V4.2A"),
    )
    for root, label in historical:
        if _is_under(resolved, root):
            raise ArtifactPathForbiddenError(
                f"Refusing to write into {label} retained evidence at {resolved}."
            )
    v3_root = (CANONICAL_REPO_ROOT / "results" / "v3_review").resolve()
    if _is_under(resolved, v3_root):
        raise ArtifactPathForbiddenError(
            f"Refusing to write into frozen V3 retained evidence at {resolved}."
        )
    return resolved


def _resolve_audit_output(output: Path) -> Path:
    resolved = Path(output).expanduser().resolve()
    allowed = allowed_v4_2b_output_root()
    if _is_under(resolved, allowed):
        return assert_v4_2b_output_allowed(resolved)
    return _refuse_historical_output(resolved)


def tasks_from_common_physical_bank(
    bank: Mapping[str, Any],
) -> dict[str, ResolvedFreeSpaceTaskV2]:
    """Build resolved tasks directly from the frozen bank payload."""
    out: dict[str, ResolvedFreeSpaceTaskV2] = {}
    for raw in bank["tasks"]:
        task_id = str(raw["task_id"])
        out[task_id] = ResolvedFreeSpaceTaskV2(
            task_id=task_id,
            start_q=raw["start_q"],
            start_tip=raw["start_x"],
            goal_center=raw["goal_center"],
            goal_radius=float(raw["goal_radius"]),
            goal_points=raw["goal_points"],
            goal_point_ids=tuple(str(item) for item in raw["goal_point_ids"]),
        )
    return out


def sampling_arms_for_mounted(
    realized: RealizedSpanCase,
    *,
    L1: float,
    L2: float,
) -> dict[str, SamplingSmokeArm]:
    """Wrap the mounted four-bar and span-matched gearbox as audit arms."""
    fk = Planar2R(L1=L1, L2=L2)
    return {
        "fourbar": SamplingSmokeArm(
            name="fourbar",
            branch=realized.fourbar,
            robot=planar_2r_operating_branch_robot(realized.fourbar, planar_fk=fk),
        ),
        "gearbox": SamplingSmokeArm(
            name="gearbox",
            branch=realized.gearbox,
            robot=planar_2r_operating_branch_robot(realized.gearbox, planar_fk=fk),
        ),
    }


def compile_mounted_paired_search(
    realized: RealizedSpanCase,
    *,
    lattice_shape: tuple[int, int],
    inset_fraction: float,
    edge_n_samples: int,
    sampling_arms: Mapping[str, SamplingSmokeArm],
) -> tuple[Any, PairedCompiledSearchGraph]:
    """Build and jointly compile one paired lattice for a mounted case."""
    paired = build_paired_q_planning_graph(
        {"fourbar": realized.fourbar, "gearbox": realized.gearbox},
        q_shape=lattice_shape,
        connectivity=LatticeConnectivity.AXIS_ALIGNED,
        inset_fraction=inset_fraction,
    )
    costs = {}
    for name, graph in paired.arms.items():
        robot = sampling_arms[name].robot
        costs[name] = integrated_actuator_edge_cost(
            graph, robot, n_samples=edge_n_samples
        )
    compiled = compile_paired_q_search_graph(paired, costs)
    return paired, compiled


def assert_mounted_pair(
    realized: RealizedSpanCase,
    *,
    sampling_arms: Mapping[str, SamplingSmokeArm],
    task: ResolvedFreeSpaceTaskV2,
    contract: CommonPhysicalGoalContract,
) -> dict[str, Any]:
    """Fail closed unless start/goal identity is shared across the pair."""
    kind = realized.fourbar.selector.get("output_coordinate_kind")
    if kind != _MOUNTED_KIND:
        raise SpanCorrectiveAuditError(
            f"{realized.case.case_id} fourbar output_coordinate_kind "
            f"must be {_MOUNTED_KIND!r}, got {kind!r}"
        )
    starts = {
        mech: state_from_shared_q(arm, task.start_q)
        for mech, arm in sampling_arms.items()
    }
    fb = starts["fourbar"]
    gb = starts["gearbox"]
    if not np.allclose(fb.q, gb.q, atol=_POSE_ATOL, rtol=0.0):
        raise SpanCorrectiveAuditError("paired start_q disagree")
    if not np.allclose(fb.q, task.start_q, atol=_POSE_ATOL, rtol=0.0):
        raise SpanCorrectiveAuditError("start_q is not the frozen bank start")
    tips = {
        mech: np.asarray(
            arm.robot.forward_kinematics(starts[mech]).position, dtype=np.float64
        )
        for mech, arm in sampling_arms.items()
    }
    if not np.allclose(tips["fourbar"], tips["gearbox"], atol=_POSE_ATOL, rtol=0.0):
        raise SpanCorrectiveAuditError("paired start_x disagree")
    if not np.allclose(tips["fourbar"], task.start_tip, atol=_POSE_ATOL, rtol=0.0):
        raise SpanCorrectiveAuditError("start_x is not the frozen bank start")
    if np.allclose(fb.u, gb.u, atol=_POSE_ATOL, rtol=0.0):
        raise SpanCorrectiveAuditError("paired start_u must differ")
    cands = {
        mech: _goal_candidates(arm, task, contract)
        for mech, arm in sampling_arms.items()
    }
    ids_fb = [c.provenance.get("goal_sample_id") for c in cands["fourbar"]]
    ids_gb = [c.provenance.get("goal_sample_id") for c in cands["gearbox"]]
    if ids_fb != ids_gb:
        raise SpanCorrectiveAuditError("paired goal candidate ids disagree")
    return {
        "starts": starts,
        "tips": tips,
        "candidates": cands,
    }


def _run_or_record_failure(**kwargs: Any) -> PlannerRunRecord:
    try:
        return run_planner_for_trial(**kwargs)
    except ValueError as exc:
        arm = kwargs["arm"]
        return PlannerRunRecord(
            planner=str(kwargs["planner_name"]),
            mechanism=str(arm.name),
            status="failed",
            skipped="planner_exception",
            planner_metrics={
                "failure_code": "planner_exception",
                "message": str(exc),
            },
        )


def _run_lattice_or_record(
    *,
    arm: SamplingSmokeArm,
    task: ResolvedFreeSpaceTaskV2,
    contract: CommonPhysicalGoalContract,
    compiled: PairedCompiledSearchGraph,
    embedded: Any,
    planner_name: str,
    edge_n_samples: int,
) -> PlannerRunRecord:
    algorithm = "dijkstra" if planner_name == "lattice_dijkstra" else "astar"
    problem = build_problem_v2(arm, task)
    candidates = _goal_candidates(arm, task, contract)
    try:
        result, expanded = solve_paired_lattice_goal_set(
            problem=problem,
            candidates=candidates,
            compiled=compiled,
            embedded=embedded,
            arm_name=arm.name,
            algorithm=algorithm,
            edge_n_samples=edge_n_samples,
        )
    except ValueError as exc:
        return PlannerRunRecord(
            planner=planner_name,
            mechanism=arm.name,
            status="failed",
            skipped="planner_exception",
            planner_metrics={
                "failure_code": "planner_exception",
                "message": str(exc),
            },
        )
    connector = connector_for_graph(embedded, arm.robot, n_samples=edge_n_samples)
    return _pack_run(
        planner=planner_name,
        mechanism=arm.name,
        result=result,
        skipped=None,
        expanded=expanded,
        sink=None,
        robot=arm.robot,
        connector=connector,
        goal=problem.goal,
        scene=problem.scene,
    )


def _write_jsonl_gz(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _inventory_planning_files(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel == "manifest.json":
            continue
        if not (
            rel.endswith(".html")
            or rel.endswith(".json")
            or rel.endswith(".jsonl.gz")
            or rel.endswith(".md")
        ):
            continue
        schema_version, media_type, compression = media_for(rel)
        records.append(
            inventory_file(
                root,
                rel,
                schema_version=schema_version,
                media_type=media_type,
                compression=compression,
            )
        )
    return records


def _topology_record(
    *,
    case_id: str,
    compiled: PairedCompiledSearchGraph,
) -> dict[str, Any]:
    rejected_counts = {"fourbar": 0, "gearbox": 0}
    for record in compiled.rejected_candidates.values():
        for name, admission in record.items():
            if admission.candidate_edge_status == "unavailable_local_motion":
                rejected_counts[name] = rejected_counts.get(name, 0) + 1
    reasons = {
        name: {"unavailable_local_motion": int(count)}
        for name, count in rejected_counts.items()
    }
    return {
        "case_id": case_id,
        "candidate_edge_count": len(compiled.candidate_edge_ids),
        "admitted_edge_count": len(compiled.admitted_edge_ids),
        "candidate_topology_digest": compiled.candidate_topology_digest,
        "admitted_topology_digest": compiled.admitted_topology_digest,
        "rejected_edge_reasons_by_mechanism": reasons,
    }


def export_case_planning_audit(
    *,
    realized: RealizedSpanCase,
    config: SpanControlledCorrectiveAuditConfig,
    audit: AuditConfig,
    case_root: Path,
    tasks: Mapping[str, ResolvedFreeSpaceTaskV2],
    task_ids: Sequence[str],
    lattice_shape: tuple[int, int],
    contract: CommonPhysicalGoalContract,
    provenance: Mapping[str, Any],
) -> tuple[tuple[dict[str, Any], ...], dict[str, Any]]:
    """Write one case tree under ``case_root``."""
    case_root = Path(case_root)
    case_root.mkdir(parents=True, exist_ok=True)
    tasks_dir = case_root / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    sampling_arms = sampling_arms_for_mounted(
        realized, L1=config.planar2r.L1, L2=config.planar2r.L2
    )
    paired, compiled = compile_mounted_paired_search(
        realized,
        lattice_shape=lattice_shape,
        inset_fraction=float(config.lattice.inset_fraction),
        edge_n_samples=int(config.lattice.edge_n_samples),
        sampling_arms=sampling_arms,
    )
    lattice_arms = {
        name: LatticeSmokeArm(
            name=name,  # type: ignore[arg-type]
            branch=sampling_arms[name].branch,
            graph=paired.arms[name],
            robot=sampling_arms[name].robot,
        )
        for name in ("fourbar", "gearbox")
    }
    topology = _topology_record(
        case_id=realized.case.case_id, compiled=compiled
    )
    labeled_branches = {
        "fourbar": sampling_arms["fourbar"].branch,
        "gearbox": sampling_arms["gearbox"].branch,
    }
    edge_n = int(audit.raw["lattice"]["edge_n_samples"])
    bundles = {
        mech: compute_mechanism_edge_metrics(
            lattice_arms[mech], sampling_arms[mech], n_samples=edge_n
        )
        for mech in ("fourbar", "gearbox")
    }
    summary_rows: list[dict[str, Any]] = []
    planner_rows: list[dict[str, Any]] = []

    for task_id in task_ids:
        task = tasks[task_id]
        pair_state = assert_mounted_pair(
            realized,
            sampling_arms=sampling_arms,
            task=task,
            contract=contract,
        )
        asset_dir = tasks_dir / f"{task_id}_assets"
        asset_dir.mkdir(parents=True, exist_ok=True)
        mapping_assets = write_mapping_panels(
            labeled_branches=labeled_branches,
            out_dir=asset_dir,
            task_id=task_id,
        )
        runs: list[PlannerRunRecord] = []
        for mech in ("fourbar", "gearbox"):
            for planner in audit.planners:
                if planner in ("lattice_dijkstra", "lattice_astar"):
                    run = _run_lattice_or_record(
                        arm=sampling_arms[mech],
                        task=task,
                        contract=contract,
                        compiled=compiled,
                        embedded=paired.arms[mech],
                        planner_name=planner,
                        edge_n_samples=edge_n,
                    )
                else:
                    run = _run_or_record_failure(
                        config=audit,
                        planner_name=planner,
                        arm=sampling_arms[mech],
                        lattice_arm=lattice_arms[mech],
                        task=task,
                        contract=contract,
                        capture_trace=True,
                    )
                runs.append(run)

        asset_map: dict[str, str] = {}
        html_dir = tasks_dir
        for key, path in mapping_assets.items():
            asset_map[key] = _rel(path, html_dir)
        for mech in ("fourbar", "gearbox"):
            path_q = None
            for run in runs:
                if (
                    run.mechanism == mech
                    and run.planner == "input_linear"
                    and run.trajectory_states
                ):
                    path_q = [s["q"] for s in run.trajectory_states]
                    break
            g_assets = write_graph_panels(
                graph=lattice_arms[mech].graph,
                robot=sampling_arms[mech].robot,
                bundle=bundles[mech],
                out_dir=asset_dir,
                task_id=task_id,
                mechanism=mech,
                start_q=task.start_q.tolist(),
                goal_center=task.goal_center.tolist(),
                goal_radius=float(task.goal_radius),
                goal_points=[p.tolist() for p in task.goal_points],
                path_q=path_q,
            )
            for key, path in g_assets.items():
                asset_map[f"{mech}_{key}"] = _rel(path, html_dir)
        for run in runs:
            connector = None
            if run.planner in ("prm", "rrt_connect"):
                connector = native_trace_connector(sampling_arms[run.mechanism].robot)
            try:
                s_assets = write_search_panels(
                    graph=lattice_arms[run.mechanism].graph,
                    robot=sampling_arms[run.mechanism].robot,
                    run=run,
                    out_dir=asset_dir,
                    task_id=task_id,
                    goal_center=task.goal_center.tolist(),
                    goal_radius=float(task.goal_radius),
                    connector=connector,
                )
            except (ValueError, KeyError, TypeError):
                s_assets = {}
            for key, path in s_assets.items():
                asset_map[f"{run.mechanism}_{run.planner}_{key}"] = _rel(
                    path, html_dir
                )
        direct_runs = {
            f"{run.mechanism}/{run.planner}": run
            for run in runs
            if run.planner in ("input_linear", "output_linear")
        }
        path_len = write_direct_comparison(
            runs=direct_runs, out_dir=asset_dir, task_id=task_id
        )
        asset_map["path_lengths"] = _rel(path_len, html_dir)

        deltas: list[dict[str, Any]] = []
        by_key = {(run.mechanism, run.planner): run for run in runs}
        for planner in audit.planners:
            fb = by_key.get(("fourbar", planner))
            gb = by_key.get(("gearbox", planner))
            if fb is None or gb is None:
                continue
            for field in (
                "objective_cost",
                "path_length_u",
                "path_length_q",
                "path_length_x",
            ):
                delta = paired_delta(fb, gb, field)
                deltas.append(
                    {
                        "planner": planner,
                        "field": field,
                        "delta": delta,
                        "abs_delta": None if delta is None else abs(delta),
                    }
                )
            summary_rows.append(
                {
                    "case_id": realized.case.case_id,
                    "task_id": task_id,
                    "planner": planner,
                    "delta_L_U": paired_delta(fb, gb, "path_length_u"),
                    "fourbar_status": fb.status,
                    "gearbox_status": gb.status,
                }
            )

        trial_record = {
            "case_id": realized.case.case_id,
            "task_id": task_id,
            "start_q": task.start_q.tolist(),
            "start_tip": task.start_tip.tolist(),
            "start_u_fourbar": pair_state["starts"]["fourbar"].u.tolist(),
            "start_u_gearbox": pair_state["starts"]["gearbox"].u.tolist(),
            "goal_center": task.goal_center.tolist(),
            "goal_radius": float(task.goal_radius),
            "goal_points": [p.tolist() for p in task.goal_points],
            "goal_point_ids": list(task.goal_point_ids),
            "admitted_topology_digest": compiled.admitted_topology_digest,
            "candidate_edge_count": len(compiled.candidate_edge_ids),
            "admitted_edge_count": len(compiled.admitted_edge_ids),
            "task_bank_digest": provenance["common_task_bank_digest"],
        }
        runs_json = [run.to_jsonable() for run in runs]
        write_task_audit_html(
            tasks_dir / f"{task_id}.html",
            trial=trial_record,
            assets=asset_map,
            runs=runs_json,
            deltas=deltas,
        )
        for run in runs_json:
            planner_rows.append(
                {
                    **run,
                    "case_id": realized.case.case_id,
                    "task_id": task_id,
                    "admitted_topology_digest": compiled.admitted_topology_digest,
                    "candidate_edge_count": len(compiled.candidate_edge_ids),
                    "admitted_edge_count": len(compiled.admitted_edge_ids),
                    "start_q": task.start_q.tolist(),
                    "start_x": task.start_tip.tolist(),
                    "goal_center": task.goal_center.tolist(),
                    "goal_radius": float(task.goal_radius),
                    "goal_point_ids": list(task.goal_point_ids),
                    "config_digest": provenance["config_digest"],
                    "common_task_bank_digest": provenance["common_task_bank_digest"],
                    "v3_6d_registry_digest": provenance["v3_6d_registry_digest"],
                    "source_git_revision": provenance["source_git_revision"],
                    "no_inference_statement": NO_INFERENCE_STATEMENT,
                }
            )

    write_case_audit_html(
        case_root / "index.html",
        realized=realized,
        task_ids=task_ids,
        summary_rows=summary_rows,
        admitted_topology_digest=compiled.admitted_topology_digest,
        candidate_edge_count=len(compiled.candidate_edge_ids),
        admitted_edge_count=len(compiled.admitted_edge_ids),
        no_inference_statement=NO_INFERENCE_STATEMENT,
    )
    return tuple(planner_rows), topology


def generate_span_controlled_corrective_audit(
    *,
    config_path: Path | str | None = None,
    output: Path | str | None = None,
    case_ids: Sequence[str] | None = None,
    task_ids: Sequence[str] | None = None,
    lattice_shape: tuple[int, int] | None = None,
    prepare_subdir: bool = True,
    source_git_revision: str | None = None,
    source_git_dirty: bool | None = None,
) -> dict[str, Any]:
    """Generate the V4.2B planning-audit package under ``output``.

    Parameters
    ----------
    config_path :
        Frozen audit config. Defaults to the committed JSON.
    output :
        ``planning_audit`` directory. Canonical V4.0–V4.2A paths are refused.
    case_ids, task_ids, lattice_shape :
        Optional test-only subsets / overrides.
    prepare_subdir :
        Remove an existing ``output`` directory before writing.
    source_git_revision, source_git_dirty :
        Optional provenance from a package orchestrator.
    """
    cfg_path = (
        Path(config_path)
        if config_path is not None
        else CANONICAL_REPO_ROOT / DEFAULT_CONFIG_REL
    )
    config = load_span_corrective_audit_config(cfg_path)
    target = (
        Path(output)
        if output is not None
        else (CANONICAL_REPO_ROOT / config.output_dir / "planning_audit")
    )
    resolved = _resolve_audit_output(target)
    if prepare_subdir and resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True, exist_ok=True)

    if source_git_revision is None:
        source_git_revision = git_revision() or git_rev_parse_head()
    if source_git_dirty is None:
        source_git_dirty = bool(git_status_porcelain().strip())

    bank = load_common_physical_bank(CANONICAL_REPO_ROOT / DEFAULT_BANK_REL)
    bank_digest = str(bank["sha256"])
    if bank_digest != FROZEN_BANK_DIGEST or bank_digest != config.source_bank.digest_lock:
        raise SpanCorrectiveAuditError(
            "task bank digest mismatch: "
            f"file={bank_digest} lock={config.source_bank.digest_lock}"
        )
    tasks = tasks_from_common_physical_bank(bank)
    used_tasks = tuple(task_ids) if task_ids is not None else tuple(config.task_ids)
    missing_tasks = [tid for tid in used_tasks if tid not in tasks]
    if missing_tasks:
        raise SpanCorrectiveAuditError(f"unknown task ids: {missing_tasks}")

    v42_config = load_span_atlas_config(CANONICAL_REPO_ROOT / V4_2_DEFAULT_CONFIG_REL)
    registry = load_locked_v3_6d_registry(v42_config)
    if registry.sha256 != FROZEN_V3_6D_DIGEST:
        raise SpanCorrectiveAuditError(
            f"V3.6D digest mismatch: {registry.sha256}"
        )
    cases = generate_span_cases()
    wanted = set(case_ids) if case_ids is not None else {c.case_id for c in cases}
    unknown = wanted - {c.case_id for c in cases}
    if unknown:
        raise SpanCorrectiveAuditError(f"unknown case ids: {sorted(unknown)}")
    realized_all = tuple(realize_mounted_span_case(case, registry) for case in cases)
    realized_export = tuple(
        row for row in realized_all if row.case.case_id in wanted
    )
    shape = lattice_shape if lattice_shape is not None else config.lattice.shape
    audit = config.as_audit_config(cfg_path)
    audit.raw["task_ids"] = list(used_tasks)
    audit.raw["lattice"]["shape"] = [int(shape[0]), int(shape[1])]
    max_candidates = int(config.planner_settings["max_goal_candidates"])
    contract = CommonPhysicalGoalContract(_GoalRep(max_candidates=max_candidates))

    provenance = provenance_block(audit)
    provenance["no_inference_statement"] = NO_INFERENCE_STATEMENT
    provenance["config_digest"] = config.digest()
    provenance["common_task_bank_digest"] = bank_digest
    provenance["v3_6d_registry_digest"] = registry.sha256
    provenance["source_git_revision"] = source_git_revision
    provenance["source_git_dirty"] = source_git_dirty
    provenance["span_175_status"] = SPAN_175_STATUS

    all_rows: list[dict[str, Any]] = []
    topology_rows: list[dict[str, Any]] = []
    for realized in realized_export:
        case_dir = resolved / "cases" / realized.case.case_id
        rows, topology = export_case_planning_audit(
            realized=realized,
            config=config,
            audit=audit,
            case_root=case_dir,
            tasks=tasks,
            task_ids=used_tasks,
            lattice_shape=shape,
            contract=contract,
            provenance=provenance,
        )
        all_rows.extend(rows)
        topology_rows.append(topology)

    n_expected = len(realized_export) * len(used_tasks) * len(FROZEN_PLANNERS) * 2
    n_silent = n_expected - len(all_rows)
    if n_silent != 0:
        raise SpanCorrectiveAuditError(
            f"silent drops must be 0, got {n_silent} "
            f"(n_rows={len(all_rows)}, expected={n_expected})"
        )
    failures = [
        row
        for row in all_rows
        if row.get("skipped") or str(row.get("status")) not in ("success",)
    ]
    n_typed = len(failures)
    data_dir = resolved / "data"
    _write_jsonl_gz(data_dir / "planner_rows.jsonl.gz", all_rows)
    _write_jsonl_gz(data_dir / "topology.jsonl.gz", topology_rows)

    exported_ids = [row.case.case_id for row in realized_export]
    summary = {
        "schema_version": PLANNING_SCHEMA,
        "package": PLANNING_PACKAGE,
        "n_cases": len(realized_export),
        "n_tasks": len(used_tasks),
        "n_planners": len(FROZEN_PLANNERS),
        "n_rows": len(all_rows),
        "n_typed_failures": n_typed,
        "n_silent_drops": 0,
        "case_ids": exported_ids,
        "task_ids": list(used_tasks),
        "planners": list(FROZEN_PLANNERS),
        "lattice_shape": list(shape),
        "config_digest": config.digest(),
        "common_task_bank_digest": bank_digest,
        "v3_6d_registry_digest": registry.sha256,
        "source_git_revision": source_git_revision,
        "source_git_dirty": source_git_dirty,
        "no_inference_statement": NO_INFERENCE_STATEMENT,
        "span_175_status": SPAN_175_STATUS,
        "ompl_available": provenance.get("ompl_available"),
        "rows": [
            {
                "case_id": row["case_id"],
                "task_id": row["task_id"],
                "mechanism": row["mechanism"],
                "planner": row["planner"],
                "status": row["status"],
                "skipped": row.get("skipped"),
            }
            for row in all_rows
        ],
    }
    (resolved / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    (resolved / "failures.json").write_text(
        json.dumps(failures, indent=2), encoding="utf-8"
    )
    manifest = {
        "schema_version": PLANNING_SCHEMA,
        "package": PLANNING_PACKAGE,
        "manifest_inventory_rule": MANIFEST_INVENTORY_RULE,
        "source_git_revision": source_git_revision,
        "source_git_dirty": source_git_dirty,
        "config_digest": config.digest(),
        "v3_6d_registry_digest": registry.sha256,
        "common_task_bank_digest": bank_digest,
        "case_ids": exported_ids,
        "n_rows": len(all_rows),
        "n_typed_failures": n_typed,
        "n_silent_drops": 0,
        "seed": config.seed,
        "lattice_shape": list(shape),
        "no_inference_statement": NO_INFERENCE_STATEMENT,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_planning_audit_root_html(
        resolved,
        config=config,
        registry=registry,
        realized=realized_all,
        manifest=manifest,
    )
    files = _inventory_planning_files(resolved)
    manifest["files"] = files
    manifest["files_digest"] = files_digest(files)
    (resolved / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return {
        "output": str(resolved),
        "n_rows": len(all_rows),
        "n_typed_failures": n_typed,
        "n_silent_drops": 0,
        "n_cases": len(realized_export),
        "case_ids": exported_ids,
        "common_task_bank_digest": bank_digest,
    }


__all__ = [
    "CommonPhysicalGoalContract",
    "SpanCorrectiveAuditError",
    "assert_mounted_pair",
    "compile_mounted_paired_search",
    "generate_span_controlled_corrective_audit",
    "sampling_arms_for_mounted",
    "tasks_from_common_physical_bank",
]
