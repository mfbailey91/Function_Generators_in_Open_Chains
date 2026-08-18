"""V4.2A span-controlled visual planning audit driver.

Consumes the frozen V3.6D registry. Does not call span synthesis.
Identity-on-shared-Q is not a planner arm.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib
import numpy as np

matplotlib.use("Agg")

from inequality_mechanisms.adapters import planar_2r_operating_branch_robot
from inequality_mechanisms.audits.html_report import (
    DEFAULT_OWNERSHIP,
    build_manifest,
    write_architecture_html,
    write_index_html,
    write_trial_html,
)
from inequality_mechanisms.audits.metrics import edge_bundle_to_jsonable
from inequality_mechanisms.audits.planar2r_visual import (
    AuditConfig,
    PlannerRunRecord,
    attach_composites,
    assert_shared_wq_wx,
    compute_mechanism_edge_metrics,
    native_trace_connector,
    paired_delta,
    provenance_block,
    resolve_audit_trials,
    run_planner_for_trial,
)
from inequality_mechanisms.audits.v4_artifact_guard import (
    CANONICAL_REPO_ROOT,
    assert_v4_2a_output_allowed,
    prepare_v4_2a_output_dir,
)
from inequality_mechanisms.benchmarks.free_space_bank_v2 import (
    load_free_space_bank_v2,
    resolve_free_space_tasks_v2,
)
from inequality_mechanisms.benchmarks.smoke_lattice_2r import (
    build_paired_lattice_arms_from_branches,
)
from inequality_mechanisms.benchmarks.smoke_sampling_2r import SamplingSmokeArm
from inequality_mechanisms.experiments.span_cases import (
    RealizedSpanCase,
    generate_span_cases,
    realize_span_case,
)
from inequality_mechanisms.experiments.v4.geometry_atlas import git_revision
from inequality_mechanisms.experiments.v4.span_controlled_atlas_config import (
    FROZEN_V3_6D_DIGEST,
    SPAN_175_STATUS,
)
from inequality_mechanisms.experiments.v4.span_controlled_visual_audit_config import (
    DEFAULT_CONFIG_REL,
    NO_INFERENCE_STATEMENT,
    SpanControlledVisualAuditConfig,
    load_span_visual_audit_config,
)
from inequality_mechanisms.graphs.topology import LatticeConnectivity
from inequality_mechanisms.kinematics.planar_2r import Planar2R
from inequality_mechanisms.mechanisms.span_registry import SpanRegistry
from inequality_mechanisms.visualization.audit_animation import (
    write_lattice_combined_animation,
    write_roadmap_tree_growth_animation,
)
from inequality_mechanisms.visualization.audit_graphs import write_graph_panels
from inequality_mechanisms.visualization.audit_mapping import write_mapping_panels
from inequality_mechanisms.visualization.audit_search import (
    write_direct_comparison,
    write_search_panels,
)
from inequality_mechanisms.visualization.v4.span_controlled_visual_audit import (
    write_span_visual_audit_root_html,
)

REQUIRED_FILES = (
    "manifest.json",
    "summary.json",
    "index.html",
    "architecture.html",
    "README.md",
)

V4_2A_OWNERSHIP = DEFAULT_OWNERSHIP + (
    {
        "concern": "span case realization / V3.6D consume",
        "owner": "span_cases.realize_span_case",
        "module": "experiments/span_cases.py",
    },
    {
        "concern": "V4.2A artifact path guard",
        "owner": "v4_artifact_guard",
        "module": "audits/v4_artifact_guard.py",
    },
)


class SpanVisualAuditError(ValueError):
    """Typed V4.2A visual-audit construction failure."""

    failure_code = "span_visual_audit_failed"


@dataclass(frozen=True, slots=True)
class CaseAuditResult:
    """One generated span case with a V3.6B-style trial tree."""

    realized: RealizedSpanCase
    summary_rows: tuple[dict[str, Any], ...]
    task_ids: tuple[str, ...]


def _rel(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _run_or_record_failure(**kwargs: Any) -> PlannerRunRecord:
    """Run one planner; record typed failures instead of aborting the audit."""
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


def _shared_weight_note(fourbar: Any, gearbox: Any) -> dict[str, Any]:
    """Compare shared-Q edge weights without aborting on valid-node mismatch.

    V3.6B requires identical edge sets. Span-family lattices can drop different
    valid nodes when a 32×32 sample sits near a certified endpoint. The audit
    still compares ``w_Q`` / ``w_X`` on the intersection.
    """
    from inequality_mechanisms.audits.planar2r_visual import WEIGHT_TOL

    fb = {(e.a, e.b): e for e in fourbar.edges}
    gb = {(e.a, e.b): e for e in gearbox.edges}
    shared = set(fb) & set(gb)
    note = {
        "fourbar_edges": len(fb),
        "gearbox_edges": len(gb),
        "shared_edges": len(shared),
        "edge_sets_equal": set(fb) == set(gb),
        "w_q_mismatch_count": 0,
        "w_x_mismatch_count": 0,
    }
    for key in shared:
        e_fb = fb[key]
        e_gb = gb[key]
        if not (np.isfinite(e_fb.w_q) and np.isfinite(e_gb.w_q)):
            continue
        if abs(e_fb.w_q - e_gb.w_q) > WEIGHT_TOL:
            note["w_q_mismatch_count"] += 1
        if abs(e_fb.w_x - e_gb.w_x) > WEIGHT_TOL:
            note["w_x_mismatch_count"] += 1
    if note["edge_sets_equal"]:
        assert_shared_wq_wx(fourbar, gearbox)
    return note


def sampling_arms_for_realized(
    realized: RealizedSpanCase,
    *,
    L1: float,
    L2: float,
) -> dict[str, SamplingSmokeArm]:
    """Wrap the V3.6D four-bar and span-matched gearbox as audit arms.

    Identity-on-shared-Q is intentionally omitted.
    """
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


def load_locked_registry_for_audit(
    config: SpanControlledVisualAuditConfig,
    *,
    repo_root: Path | None = None,
) -> SpanRegistry:
    """Load the frozen V3.6D registry without calling synthesis."""
    return _load_registry(config, repo_root=repo_root)


def _load_registry(
    config: SpanControlledVisualAuditConfig,
    *,
    repo_root: Path | None = None,
) -> SpanRegistry:
    from inequality_mechanisms.mechanisms.span_registry import load_span_registry

    root = CANONICAL_REPO_ROOT if repo_root is None else Path(repo_root)
    path = root / config.v3_6d_registry
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SpanVisualAuditError(f"missing frozen V3.6D registry at {path}") from exc
    except json.JSONDecodeError as exc:
        raise SpanVisualAuditError(f"invalid V3.6D registry JSON at {path}: {exc}") from exc
    registry = load_span_registry(payload)
    if registry.sha256 != config.v3_6d_digest_lock:
        raise SpanVisualAuditError(
            "V3.6D registry digest mismatch: "
            f"file={registry.sha256} lock={config.v3_6d_digest_lock}"
        )
    if registry.sha256 != FROZEN_V3_6D_DIGEST:
        raise SpanVisualAuditError(
            "V3.6D registry digest is not the frozen lock "
            f"{FROZEN_V3_6D_DIGEST}, got {registry.sha256}"
        )
    status_175 = registry.record_for(175.0).status
    if status_175 != SPAN_175_STATUS or status_175 != config.span_175_status:
        raise SpanVisualAuditError(
            "175° status must remain "
            f"{SPAN_175_STATUS!r}, got registry={status_175!r} "
            f"config={config.span_175_status!r}"
        )
    return registry


def export_case_visual_audit(
    *,
    realized: RealizedSpanCase,
    config: SpanControlledVisualAuditConfig,
    audit: AuditConfig,
    case_root: Path,
    task_ids: Sequence[str],
    lattice_shape: tuple[int, int],
    skip_animations: bool,
    provenance: Mapping[str, Any],
) -> CaseAuditResult:
    """Write one V3.6B-style case tree under ``case_root``."""
    case_root = Path(case_root)
    case_root.mkdir(parents=True, exist_ok=True)
    assets_dir = case_root / "assets"
    trials_dir = case_root / "trials"
    assets_dir.mkdir(parents=True, exist_ok=True)
    trials_dir.mkdir(parents=True, exist_ok=True)

    sampling_arms = sampling_arms_for_realized(
        realized, L1=config.planar2r.L1, L2=config.planar2r.L2
    )
    lattice_arms = build_paired_lattice_arms_from_branches(
        realized.fourbar,
        realized.gearbox,
        shape=lattice_shape,
        connectivity=LatticeConnectivity.CHEBYSHEV_1,
    )
    audit.raw["task_ids"] = list(task_ids)
    audit.raw["lattice"]["shape"] = [int(lattice_shape[0]), int(lattice_shape[1])]
    resolve_audit_trials(
        audit,
        sampling_arms=sampling_arms,
        lattice_shape=lattice_shape,
        lattice_arms=lattice_arms,
    )

    bank_path = audit.path.parent / str(audit.raw["source_bank"]["contract_path"])
    contract = load_free_space_bank_v2(bank_path)
    resolved_all = resolve_free_space_tasks_v2(contract, arms=sampling_arms)
    by_id = {t.task_id: t for t in resolved_all}

    edge_n = int(audit.raw["lattice"]["edge_n_samples"])
    bundles = {
        mech: compute_mechanism_edge_metrics(
            lattice_arms[mech], sampling_arms[mech], n_samples=edge_n
        )
        for mech in ("fourbar", "gearbox")
    }
    edge_weight_note = _shared_weight_note(bundles["fourbar"], bundles["gearbox"])
    (assets_dir / "edge_metrics_fourbar.json").write_text(
        json.dumps(edge_bundle_to_jsonable(bundles["fourbar"]), indent=2),
        encoding="utf-8",
    )
    (assets_dir / "edge_metrics_gearbox.json").write_text(
        json.dumps(edge_bundle_to_jsonable(bundles["gearbox"]), indent=2),
        encoding="utf-8",
    )
    (assets_dir / "edge_weight_note.json").write_text(
        json.dumps(edge_weight_note, indent=2), encoding="utf-8"
    )

    labeled_branches = {
        "fourbar": sampling_arms["fourbar"].branch,
        "gearbox": sampling_arms["gearbox"].branch,
    }
    fractions = tuple(
        float(x) for x in audit.raw["animation_policy"]["contact_sheet_fractions"]
    )
    summary_rows: list[dict[str, Any]] = []
    manifest_assets: list[dict[str, Any]] = []

    for task_id in task_ids:
        task = by_id[task_id]
        trial_dir = trials_dir / task_id
        trial_assets = trial_dir / "assets"
        trial_assets.mkdir(parents=True, exist_ok=True)

        mapping_assets = write_mapping_panels(
            labeled_branches=labeled_branches,
            out_dir=trial_assets,
            task_id=task_id,
        )
        runs = []
        for mech in ("fourbar", "gearbox"):
            for planner in audit.planners:
                print(f"  {task_id} {mech} {planner}", flush=True)
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
        runs = attach_composites(runs, config=audit)

        asset_map: dict[str, str] = {}
        for key, path in mapping_assets.items():
            asset_map[key] = _rel(path, trial_dir)

        for mech in ("fourbar", "gearbox"):
            path_q = None
            for run in runs:
                if run.mechanism == mech and run.planner == "input_linear" and run.trajectory_states:
                    path_q = [s["q"] for s in run.trajectory_states]
                    break
            g_assets = write_graph_panels(
                graph=lattice_arms[mech].graph,
                robot=sampling_arms[mech].robot,
                bundle=bundles[mech],
                out_dir=trial_assets,
                task_id=task_id,
                mechanism=mech,
                start_q=task.start_q.tolist(),
                goal_center=task.goal_center.tolist(),
                goal_radius=float(task.goal_radius),
                goal_points=[p.tolist() for p in task.goal_points],
                path_q=path_q,
            )
            for k, p in g_assets.items():
                asset_map[f"{mech}_{k}"] = _rel(p, trial_dir)

        for run in runs:
            connector = None
            if run.planner in ("prm", "rrt_connect"):
                connector = native_trace_connector(sampling_arms[run.mechanism].robot)
            try:
                s_assets = write_search_panels(
                    graph=lattice_arms[run.mechanism].graph,
                    robot=sampling_arms[run.mechanism].robot,
                    run=run,
                    out_dir=trial_assets,
                    task_id=task_id,
                    goal_center=task.goal_center.tolist(),
                    goal_radius=float(task.goal_radius),
                    connector=connector,
                )
            except (ValueError, KeyError, TypeError) as exc:
                print(
                    f"  search-panel skip {run.mechanism} {run.planner}: {exc}",
                    flush=True,
                )
                s_assets = {}
            for k, p in s_assets.items():
                asset_map[f"{run.mechanism}_{run.planner}_{k}"] = _rel(p, trial_dir)

        direct_runs = {
            f"{r.mechanism}/{r.planner}": r
            for r in runs
            if r.planner in ("input_linear", "output_linear")
        }
        path_len = write_direct_comparison(
            runs=direct_runs, out_dir=trial_assets, task_id=task_id
        )
        asset_map["path_lengths"] = _rel(path_len, trial_dir)

        lattice_runs = {
            (r.mechanism, r.planner): r
            for r in runs
            if r.planner in ("lattice_dijkstra", "lattice_astar")
        }
        if not skip_animations:
            anim = write_lattice_combined_animation(
                task_id=task_id,
                graphs={m: lattice_arms[m].graph for m in ("fourbar", "gearbox")},
                runs=lattice_runs,
                out_dir=trial_assets,
                fractions=fractions,
            )
            asset_map["lattice_combined_anim"] = _rel(anim["anim"], trial_dir)
            asset_map["lattice_combined_anim_contact"] = _rel(anim["contact"], trial_dir)
            asset_map["lattice_combined__contact.png"] = _rel(anim["contact"], trial_dir)

        growth_html_parts: list[str] = []
        if task_id in audit.animation_growth_tasks and not skip_animations:
            for mech in ("fourbar", "gearbox"):
                for planner in ("prm", "rrt_connect"):
                    run = next(
                        r for r in runs if r.mechanism == mech and r.planner == planner
                    )
                    growth = write_roadmap_tree_growth_animation(
                        task_id=task_id,
                        mechanism=mech,
                        planner=planner,
                        run=run,
                        out_dir=trial_assets,
                        fractions=fractions,
                        connector=native_trace_connector(sampling_arms[mech].robot),
                        robot=sampling_arms[mech].robot,
                    )
                    key = f"{mech}_{planner}_growth_anim"
                    asset_map[key] = _rel(growth["anim"], trial_dir)
                    asset_map[key + "_contact"] = _rel(growth["contact"], trial_dir)
                    for space in ("u", "q", "x"):
                        ckey = f"contact_{space}"
                        if ckey in growth:
                            asset_map[f"{mech}_{planner}_growth_{space}_contact"] = _rel(
                                growth[ckey], trial_dir
                            )
                    growth_html_parts.append(key)
            if growth_html_parts:
                asset_map["growth_anims"] = asset_map[growth_html_parts[0]]
                asset_map["growth_anims_contact"] = asset_map[
                    growth_html_parts[0] + "_contact"
                ]

        deltas: list[dict[str, Any]] = []
        by_key = {(r.mechanism, r.planner): r for r in runs}
        for planner in audit.planners:
            fb = by_key.get(("fourbar", planner))
            gb = by_key.get(("gearbox", planner))
            if fb is None or gb is None:
                continue
            for field in ("objective_cost", "path_length_u", "path_length_q", "path_length_x"):
                d = paired_delta(fb, gb, field)
                deltas.append(
                    {
                        "planner": planner,
                        "field": field,
                        "delta": d,
                        "abs_delta": None if d is None else abs(d),
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
                    "fourbar_expansions": (fb.planner_metrics or {}).get("graph", {}).get(
                        "expansions"
                    )
                    if isinstance(fb.planner_metrics, dict)
                    else None,
                    "gearbox_expansions": (gb.planner_metrics or {}).get("graph", {}).get(
                        "expansions"
                    )
                    if isinstance(gb.planner_metrics, dict)
                    else None,
                    "j1_status": realized.j1.status,
                    "j2_status": realized.j2.status,
                }
            )

        trial_record = {
            "case_id": realized.case.case_id,
            "task_id": task_id,
            "start_q": task.start_q.tolist(),
            "start_tip": task.start_tip.tolist(),
            "goal_center": task.goal_center.tolist(),
            "goal_radius": float(task.goal_radius),
            "goal_points": [p.tolist() for p in task.goal_points],
            "goal_point_ids": list(task.goal_point_ids),
            "notes": task.notes,
            "start_resolution": "per_case_start_u_frac_on_v3_6d_fourbar",
        }
        (trial_dir / "trial.json").write_text(
            json.dumps(trial_record, indent=2), encoding="utf-8"
        )
        runs_json = [r.to_jsonable() for r in runs]
        (trial_dir / "runs.json").write_text(
            json.dumps(runs_json, indent=2), encoding="utf-8"
        )
        write_trial_html(
            trial_dir / "index.html",
            trial=trial_record,
            assets=asset_map,
            runs=runs_json,
            deltas=deltas,
        )
        for key, rel in asset_map.items():
            manifest_assets.append(
                {
                    "case_id": realized.case.case_id,
                    "task_id": task_id,
                    "key": key,
                    "path": f"trials/{task_id}/{rel}",
                }
            )

    write_architecture_html(
        case_root / "architecture.html",
        provenance=dict(provenance),
        ownership=V4_2A_OWNERSHIP,
        report_title=f"V4.2A Architecture ({realized.case.case_id})",
    )
    extra = (
        f"<p class=\"muted\">Case <code>{realized.case.case_id}</code> · "
        f"J1 {realized.case.span_j1_deg:g}° ({realized.j1.status}) · "
        f"J2 {realized.case.span_j2_deg:g}° ({realized.j2.status}) · "
        f"memberships {', '.join(realized.case.memberships)}. "
        "Identity-on-shared-Q is not a planner arm. "
        f"Shared lattice edges: fourbar {edge_weight_note['fourbar_edges']}, "
        f"gearbox {edge_weight_note['gearbox_edges']}, "
        f"intersection {edge_weight_note['shared_edges']}. "
        "<a href=\"../../index.html\">Back to V4.2A index</a></p>"
    )
    write_index_html(
        case_root / "index.html",
        provenance=dict(provenance),
        summary_rows=summary_rows,
        task_ids=list(task_ids),
        report_title=f"V4.2A {realized.case.case_id}",
        extra_html=extra,
    )
    summary = {
        "case_id": realized.case.case_id,
        "task_ids": list(task_ids),
        "seed": audit.seed,
        "j1_status": realized.j1.status,
        "j2_status": realized.j2.status,
        "rows": summary_rows,
        "no_inference_statement": provenance["no_inference_statement"],
    }
    (case_root / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    manifest = build_manifest(
        provenance=dict(provenance),
        task_ids=list(task_ids),
        assets=manifest_assets,
        root=case_root,
        extra={
            "case_id": realized.case.case_id,
            "j1_status": realized.j1.status,
            "j2_status": realized.j2.status,
            "span_j1_deg": realized.case.span_j1_deg,
            "span_j2_deg": realized.case.span_j2_deg,
        },
    )
    (case_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return CaseAuditResult(
        realized=realized,
        summary_rows=tuple(summary_rows),
        task_ids=tuple(task_ids),
    )


def generate_span_controlled_visual_audit(
    *,
    config_path: Path | None = None,
    output: Path | None = None,
    case_ids: Sequence[str] | None = None,
    task_ids: Sequence[str] | None = None,
    lattice_shape: tuple[int, int] | None = None,
    skip_animations: bool = False,
    resume: bool = False,
) -> Path:
    """Generate the V4.2A visual-audit package.

    Parameters
    ----------
    config_path :
        Frozen V4.2A config. Defaults to the committed JSON.
    output :
        Output root. Must be the allowed V4.2A package (or a monkeypatched tmp).
    case_ids :
        Optional subset of generated case ids (tests only).
    task_ids :
        Optional subset of frozen task ids (tests only).
    lattice_shape :
        Optional lattice override (tests only).
    skip_animations :
        Skip GIF generation. Static panels remain authoritative.
    resume :
        Reuse case trees that already have every requested trial page.
    """
    cfg_path = (
        Path(config_path)
        if config_path is not None
        else CANONICAL_REPO_ROOT / DEFAULT_CONFIG_REL
    )
    config = load_span_visual_audit_config(cfg_path)
    out_root = Path(output) if output is not None else CANONICAL_REPO_ROOT / config.output_dir
    out_root = prepare_v4_2a_output_dir(out_root)
    assert_v4_2a_output_allowed(out_root)

    registry = _load_registry(config)
    cases = generate_span_cases()
    if len(cases) != 17:
        raise SpanVisualAuditError(f"expected 17 unique cases, got {len(cases)}")
    realized_all = tuple(realize_span_case(case, registry) for case in cases)
    wanted_cases = set(case_ids) if case_ids is not None else {c.case_id for c in cases}
    unknown = wanted_cases - {c.case_id for c in cases}
    if unknown:
        raise SpanVisualAuditError(f"unknown case ids: {sorted(unknown)}")

    audit = config.as_audit_config(cfg_path)
    used_tasks = tuple(task_ids) if task_ids is not None else tuple(config.task_ids)
    missing_tasks = [tid for tid in used_tasks if tid not in config.task_ids]
    if missing_tasks:
        raise SpanVisualAuditError(f"unknown task ids: {missing_tasks}")
    shape = lattice_shape if lattice_shape is not None else config.lattice.shape

    provenance = provenance_block(audit)
    provenance["no_inference_statement"] = NO_INFERENCE_STATEMENT
    provenance["audit_id"] = config.audit_id
    provenance["v3_6d_digest"] = registry.sha256
    provenance["config_digest"] = config.digest()
    provenance["span_175_status"] = SPAN_175_STATUS

    case_results: list[CaseAuditResult] = []
    all_rows: list[dict[str, Any]] = []
    for realized in realized_all:
        if realized.case.case_id not in wanted_cases:
            continue
        case_dir = out_root / "cases" / realized.case.case_id
        if resume:
            existing = [
                tid
                for tid in used_tasks
                if (case_dir / "trials" / tid / "index.html").is_file()
            ]
            if (case_dir / "index.html").is_file() and len(existing) == len(used_tasks):
                print(f"case {realized.case.case_id} (resume skip)", flush=True)
                summary_path = case_dir / "summary.json"
                if summary_path.is_file():
                    payload = json.loads(summary_path.read_text(encoding="utf-8"))
                    rows = list(payload.get("rows") or [])
                    case_results.append(
                        CaseAuditResult(
                            realized=realized,
                            summary_rows=tuple(rows),
                            task_ids=tuple(used_tasks),
                        )
                    )
                    all_rows.extend(rows)
                continue
        print(f"case {realized.case.case_id}...", flush=True)
        result = export_case_visual_audit(
            realized=realized,
            config=config,
            audit=audit,
            case_root=case_dir,
            task_ids=used_tasks,
            lattice_shape=shape,
            skip_animations=skip_animations,
            provenance=provenance,
        )
        case_results.append(result)
        all_rows.extend(result.summary_rows)

    write_architecture_html(
        out_root / "architecture.html",
        provenance=provenance,
        ownership=V4_2A_OWNERSHIP,
        report_title="V4.2A Architecture",
    )
    write_span_visual_audit_root_html(
        out_root,
        config=config,
        registry=registry,
        realized=realized_all,
        manifest={
            "git_revision": provenance.get("git_revision"),
            "seed": config.seed,
            "lattice_shape": list(shape),
            "v3_6d_digest": registry.sha256,
            "no_inference_statement": NO_INFERENCE_STATEMENT,
        },
    )
    summary = {
        "audit_id": config.audit_id,
        "schema_version": config.schema_version,
        "n_cases": len(realized_all),
        "exported_case_ids": [r.realized.case.case_id for r in case_results],
        "task_ids": list(used_tasks),
        "seed": config.seed,
        "lattice_shape": list(shape),
        "ompl_available": provenance.get("ompl_available"),
        "v3_6d_digest": registry.sha256,
        "config_digest": config.digest(),
        "span_175_status": SPAN_175_STATUS,
        "no_inference_statement": NO_INFERENCE_STATEMENT,
        "rows": all_rows,
    }
    (out_root / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    manifest = {
        "schema_version": config.schema_version,
        "package": "v4_2a_span_controlled_visual_audit",
        "git_revision": provenance.get("git_revision") or git_revision(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "no_inference_statement": NO_INFERENCE_STATEMENT,
        "config_digest": config.digest(),
        "v3_6d_digest": registry.sha256,
        "span_175_status": SPAN_175_STATUS,
        "n_cases": len(realized_all),
        "exported_cases": len(case_results),
        "task_ids": list(used_tasks),
        "seed": config.seed,
        "lattice_shape": list(shape),
        "case_ids": [c.case_id for c in cases],
    }
    (out_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    (out_root / "README.md").write_text(
        "# V4.2A span-controlled visual planning audit\n\n"
        "Trial-scoped visual audit of the frozen V3.6D span family. "
        "Four-bar versus span-matched gearbox only. "
        f"{NO_INFERENCE_STATEMENT}\n\n"
        f"- cases: {len(realized_all)}\n"
        f"- tasks: {list(used_tasks)}\n"
        f"- lattice: {list(shape)}\n"
        f"- V3.6D digest: `{registry.sha256}`\n"
        f"- 175° status: `{SPAN_175_STATUS}`\n",
        encoding="utf-8",
    )
    return out_root
