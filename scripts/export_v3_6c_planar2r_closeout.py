#!/usr/bin/env python3
"""Generate the Sprint V3.6C planar-2R closeout HTML package (V3-638).

Writes only under the freeze-allowed closeout root. Canonical committed
artifact generation from a clean revision remains V3-639.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inequality_mechanisms.audits.artifact_freeze import (  # noqa: E402
    assert_v3_6c_output_allowed,
)
from inequality_mechanisms.audits.html_report import (  # noqa: E402
    DEFAULT_OWNERSHIP,
    build_manifest,
    write_architecture_html,
    write_index_html,
    write_trial_html,
)
from inequality_mechanisms.audits.metrics import edge_bundle_to_jsonable  # noqa: E402
from inequality_mechanisms.audits.planar2r_visual import (  # noqa: E402
    attach_composites,
    assert_shared_wq_wx,
    compute_mechanism_edge_metrics,
    freeze_shared_q_sampled_pair,
    load_audit_config,
    native_trace_connector,
    pack_actuator_metric_on_q_panels,
    paired_delta,
    provenance_block,
    resolve_audit_trials,
    run_planner_for_trial,
)
from inequality_mechanisms.audits.trajectory_evaluation import (  # noqa: E402
    SCHEMA_VERSION as CTE_SCHEMA,
)
from inequality_mechanisms.benchmarks.free_space_bank import build_bank_arms  # noqa: E402
from inequality_mechanisms.benchmarks.free_space_bank_v2 import (  # noqa: E402
    load_free_space_bank_v2,
    resolve_free_space_tasks_v2,
)
from inequality_mechanisms.benchmarks.smoke_lattice_2r import (  # noqa: E402
    build_paired_lattice_arms,
)
from inequality_mechanisms.graphs.topology import LatticeConnectivity  # noqa: E402
from inequality_mechanisms.visualization.audit_animation import (  # noqa: E402
    write_lattice_combined_animation,
    write_roadmap_tree_growth_animation,
)
from inequality_mechanisms.visualization.audit_graphs import write_graph_panels  # noqa: E402
from inequality_mechanisms.visualization.audit_mapping import write_mapping_panels  # noqa: E402
from inequality_mechanisms.visualization.audit_search import (  # noqa: E402
    write_direct_comparison,
    write_search_panels,
)

DEFAULT_CONFIG = ROOT / "configs" / "v3" / "planar2r_closeout_v1.json"
ARTIFACT_VERSION = "v3_6c_closeout_v1"
TRACE_SCHEMA = "v3_6c_planner_trace_v1"
REPORT_TITLE = "V3.6C Planar 2R Free-Space Closeout"
FREEZE_STATEMENT = (
    "V3.6C writes only under results/v3_review/v3_6c_planar2r_closeout/. "
    "Frozen packages under results/v3_review/ matching v3_6_*, v3_6b_*, and "
    "v3_7_* (including v3_6_free_space, v3_6_free_space_v2, "
    "v3_6b_planar2r_visual_audit, and v3_7_3r_free_space) must not be "
    "overwritten."
)


def _rel(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Path to planar2r_closeout_v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Override output directory (must pass freeze guard)",
    )
    parser.add_argument(
        "--task-ids",
        nargs="*",
        default=None,
        help="Optional subset of task ids (tests only)",
    )
    parser.add_argument(
        "--skip-animations",
        action="store_true",
        help="Skip GIF generation (still write contact sheets when possible)",
    )
    parser.add_argument(
        "--lattice-shape",
        type=int,
        nargs=2,
        default=None,
        metavar=("H", "W"),
        help="Override lattice shape (tests only)",
    )
    args = parser.parse_args(argv)

    config_path = Path(args.config).expanduser().resolve()
    if not config_path.is_file():
        raise SystemExit(f"config not found: {config_path}")
    config = load_audit_config(config_path)
    if args.lattice_shape is not None:
        config.raw["lattice"]["shape"] = list(args.lattice_shape)

    if args.output is not None:
        out_root = Path(args.output)
    else:
        out_root = ROOT / str(config.output_dir)

    out_root = assert_v3_6c_output_allowed(out_root)
    if out_root.exists():
        shutil.rmtree(out_root)
    assets_dir = out_root / "assets"
    trials_dir = out_root / "trials"
    assets_dir.mkdir(parents=True, exist_ok=True)
    trials_dir.mkdir(parents=True, exist_ok=True)

    bank_path = config.path.parent / str(config.raw["source_bank"]["contract_path"])
    contract = load_free_space_bank_v2(bank_path)
    sampling_arms = build_bank_arms(contract.base_bank)
    resolved_all = resolve_free_space_tasks_v2(contract, arms=sampling_arms)
    by_id = {t.task_id: t for t in resolved_all}
    task_ids = tuple(args.task_ids) if args.task_ids else config.task_ids
    for tid in task_ids:
        if tid not in by_id:
            raise SystemExit(f"unknown task id {tid}")

    if args.task_ids is None:
        resolve_audit_trials(config, sampling_arms=sampling_arms)

    lattice_arms = build_paired_lattice_arms(
        shape=config.lattice_shape,
        connectivity=LatticeConnectivity.CHEBYSHEV_1,
    )
    freeze_shared_q_sampled_pair(config, lattice_arms)

    print("computing edge metrics...", flush=True)
    edge_n = int(config.raw["lattice"]["edge_n_samples"])
    bundles = {
        mech: compute_mechanism_edge_metrics(
            lattice_arms[mech], sampling_arms[mech], n_samples=edge_n
        )
        for mech in ("fourbar", "gearbox")
    }
    assert_shared_wq_wx(bundles["fourbar"], bundles["gearbox"])
    (assets_dir / "edge_metrics_fourbar.json").write_text(
        json.dumps(edge_bundle_to_jsonable(bundles["fourbar"]), indent=2),
        encoding="utf-8",
    )
    (assets_dir / "edge_metrics_gearbox.json").write_text(
        json.dumps(edge_bundle_to_jsonable(bundles["gearbox"]), indent=2),
        encoding="utf-8",
    )

    labeled_branches = {
        "fourbar": sampling_arms["fourbar"].branch,
        "gearbox": sampling_arms["gearbox"].branch,
    }

    provenance = provenance_block(config)
    provenance["architecture_version"] = int(config.raw.get("architecture_version", 3))
    manifest_assets: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    fractions = tuple(
        float(x) for x in config.raw["animation_policy"]["contact_sheet_fractions"]
    )

    for task_id in task_ids:
        print(f"trial {task_id}...", flush=True)
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
            for planner in config.planners:
                run = run_planner_for_trial(
                    config=config,
                    planner_name=planner,
                    arm=sampling_arms[mech],
                    lattice_arm=lattice_arms[mech],
                    task=task,
                    contract=contract,
                    capture_trace=True,
                    lattice_arms=lattice_arms,
                )
                runs.append(run)
        runs = attach_composites(runs, config=config)

        asset_map: dict[str, str] = {}
        for key, path in mapping_assets.items():
            asset_map[key] = _rel(path, trial_dir)

        metric_assets = pack_actuator_metric_on_q_panels(
            bundles=bundles,
            out_dir=trial_assets,
            task_id=task_id,
        )
        for k, p in metric_assets.items():
            if k == "actuator_metric_shared_log_limits":
                asset_map[k] = _rel(p, trial_dir)
            else:
                asset_map[k] = _rel(p, trial_dir)

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
        if not args.skip_animations:
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
        if task_id in config.animation_growth_tasks and not args.skip_animations:
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
        for planner in config.planners:
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
                    "task_id": task_id,
                    "planner": planner,
                    "delta_L_U": paired_delta(fb, gb, "path_length_u"),
                    "fourbar_status": fb.status,
                    "gearbox_status": gb.status,
                }
            )

        trial_record = {
            "task_id": task_id,
            "start_q": task.start_q.tolist(),
            "start_tip": task.start_tip.tolist(),
            "goal_center": task.goal_center.tolist(),
            "goal_radius": float(task.goal_radius),
            "goal_points": [p.tolist() for p in task.goal_points],
            "goal_point_ids": list(task.goal_point_ids),
            "notes": task.notes,
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
                    "task_id": task_id,
                    "key": key,
                    "path": f"trials/{task_id}/{rel}",
                }
            )

    write_architecture_html(
        out_root / "architecture.html",
        provenance=provenance,
        ownership=DEFAULT_OWNERSHIP,
        report_title=f"{REPORT_TITLE} — Architecture",
    )
    write_index_html(
        out_root / "index.html",
        provenance=provenance,
        summary_rows=summary_rows,
        task_ids=task_ids,
        report_title=REPORT_TITLE,
    )
    summary = {
        "audit_id": config.audit_id,
        "task_ids": list(task_ids),
        "seed": config.seed,
        "ompl_available": provenance["ompl_available"],
        "rows": summary_rows,
        "no_inference_statement": provenance["no_inference_statement"],
    }
    (out_root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    try:
        config_rel = str(config_path.relative_to(ROOT))
    except ValueError:
        config_rel = str(config_path)
    manifest = build_manifest(
        provenance=provenance,
        task_ids=task_ids,
        assets=manifest_assets,
        root=out_root,
        extra={
            "status": "generated",
            "architecture_version": int(config.raw.get("architecture_version", 3)),
            "artifact_version": ARTIFACT_VERSION,
            "trace_schema": TRACE_SCHEMA,
            "metric_schema": {
                "actuator_metric_on_q": "actuator_metric_on_q",
                "continuous_trajectory": CTE_SCHEMA,
            },
            "config_path": config_rel,
            "freeze_statement": FREEZE_STATEMENT,
            "offline": True,
            "no_cdn": True,
        },
    )
    (out_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {out_root}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
