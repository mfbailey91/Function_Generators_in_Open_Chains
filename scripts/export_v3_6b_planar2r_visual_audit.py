#!/usr/bin/env python3
"""Generate the Sprint V3.6B planar-2R visual audit HTML tree."""

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

from inequality_mechanisms.audits.html_report import (
    DEFAULT_OWNERSHIP,
    build_manifest,
    write_architecture_html,
    write_index_html,
    write_trial_html,
)
from inequality_mechanisms.audits.metrics import edge_bundle_to_jsonable
from inequality_mechanisms.audits.planar2r_visual import (
    attach_composites,
    assert_shared_wq_wx,
    compute_mechanism_edge_metrics,
    load_audit_config,
    paired_delta,
    provenance_block,
    resolve_audit_trials,
    run_planner_for_trial,
)
from inequality_mechanisms.benchmarks.free_space_bank import build_bank_arms
from inequality_mechanisms.benchmarks.free_space_bank_v2 import (
    load_free_space_bank_v2,
    resolve_free_space_tasks_v2,
)
from inequality_mechanisms.benchmarks.smoke_lattice_2r import build_paired_lattice_arms
from inequality_mechanisms.graphs.topology import LatticeConnectivity
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


def _rel(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to planar2r_visual_audit_v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Override output directory",
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

    config = load_audit_config(args.config)
    if args.lattice_shape is not None:
        config.raw["lattice"]["shape"] = list(args.lattice_shape)

    out_root = Path(args.output) if args.output is not None else (ROOT / config.output_dir)
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

    # Fail-closed resolve for requested tasks (full ten when default).
    if args.task_ids is None:
        resolve_audit_trials(config, sampling_arms=sampling_arms)

    lattice_arms = build_paired_lattice_arms(
        shape=config.lattice_shape,
        connectivity=LatticeConnectivity.CHEBYSHEV_1,
    )

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
                )
                runs.append(run)
        runs = attach_composites(runs, config=config)

        # Graph panels once per mechanism (use input_linear path overlay if present).
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

        # Search panels.
        for run in runs:
            s_assets = write_search_panels(
                graph=lattice_arms[run.mechanism].graph,
                robot=sampling_arms[run.mechanism].robot,
                run=run,
                out_dir=trial_assets,
                task_id=task_id,
                goal_center=task.goal_center.tolist(),
                goal_radius=float(task.goal_radius),
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

        # Lattice combined animation.
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

        # Roadmap/tree growth for designated trials.
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
                    )
                    key = f"{mech}_{planner}_growth_anim"
                    asset_map[key] = _rel(growth["anim"], trial_dir)
                    asset_map[key + "_contact"] = _rel(growth["contact"], trial_dir)
                    growth_html_parts.append(key)
            # Placeholder key consumed by trial HTML for growth block.
            if growth_html_parts:
                asset_map["growth_anims"] = asset_map[growth_html_parts[0]]
                asset_map["growth_anims_contact"] = asset_map[growth_html_parts[0] + "_contact"]

        # Deltas.
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
    )
    write_index_html(
        out_root / "index.html",
        provenance=provenance,
        summary_rows=summary_rows,
        task_ids=task_ids,
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
    manifest = build_manifest(
        provenance=provenance,
        task_ids=task_ids,
        assets=manifest_assets,
        root=out_root,
    )
    (out_root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"wrote {out_root}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
