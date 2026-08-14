"""V3-638 closeout report layout, family metrics, freeze, and link checks."""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

from inequality_mechanisms.audits.artifact_freeze import (
    REPO_ROOT,
    V3_6C_ALLOWED_PACKAGE,
    assert_v3_6c_output_allowed,
)
from inequality_mechanisms.audits.html_report import family_metrics_html
from inequality_mechanisms.audits import artifact_freeze

CLOSEOUT_CONFIG = REPO_ROOT / "configs" / "v3" / "planar2r_closeout_v1.json"
EXPORT_SCRIPT = REPO_ROOT / "scripts" / "export_v3_6c_planar2r_closeout.py"


def _load_exporter():
    spec = importlib.util.spec_from_file_location("export_v3_6c_v638", EXPORT_SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _relative_refs(html: str) -> list[str]:
    refs = re.findall(r"""(?:href|src)=["']([^"']+)["']""", html)
    out = []
    for ref in refs:
        if ref.startswith(("http://", "https://", "mailto:", "data:", "#")):
            continue
        out.append(ref)
    return out


def test_family_metrics_html_labels_prm_and_shared_q_separately() -> None:
    runs = [
        {
            "mechanism": "fourbar",
            "planner": "lattice_dijkstra",
            "planner_metrics": {
                "graph": {
                    "expansions": 12,
                    "generated": 20,
                    "reopened_or_stale": 1,
                    "goal_set_cardinality": 4,
                    "path_node_ids": [0, 1, 2],
                    "expansions_are_total_query_work": True,
                }
            },
        },
        {
            "mechanism": "fourbar",
            "planner": "prm",
            "planner_metrics": {
                "roadmap": {
                    "n_samples_requested": 80,
                    "vertices": 40,
                    "attempted_edges": 10,
                    "accepted_edges": 8,
                    "start_attached": True,
                    "goal_attachment_count": 3,
                    "expansions": 5,
                }
            },
        },
        {
            "mechanism": "fourbar",
            "planner": "rrt_connect",
            "planner_metrics": {
                "tree": {
                    "iterations": 100,
                    "extensions": 40,
                    "nn_ops": 80,
                    "start_tree_size": 10,
                    "goal_tree_size": 6,
                    "goal_root_count": 4,
                    "selected_goal_root_index": 2,
                }
            },
        },
        {
            "mechanism": "gearbox",
            "planner": "shared_q_sampled_dijkstra",
            "planner_metrics": {
                "shared_q_sampled_roadmap": {
                    "n_samples": 24,
                    "vertices": 24,
                    "edges": 30,
                    "start_attached": True,
                    "goal_attachment_count": 4,
                    "bank_mode": "reusable",
                    "diagnostic_label": "metric-isolation diagnostic; not native PRM",
                }
            },
        },
    ]
    html = family_metrics_html(runs)
    assert "expansions_are_total_query_work" in html
    assert "vertices" in html
    assert "goal-root count" in html
    assert "not native PRM" in html
    assert "shared_q_sampled_dijkstra" in html
    assert "PRM (native roadmap-family control)" in html


def test_closeout_mini_report_layout_and_labels(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(artifact_freeze, "REPO_ROOT", tmp_path)
    allowed = tmp_path / "results" / "v3_review" / V3_6C_ALLOWED_PACKAGE
    mod = _load_exporter()
    monkeypatch.setattr(mod, "assert_v3_6c_output_allowed", assert_v3_6c_output_allowed)

    raw = json.loads(CLOSEOUT_CONFIG.read_text(encoding="utf-8"))
    raw["source_bank"]["contract_path"] = str(
        (CLOSEOUT_CONFIG.parent / raw["source_bank"]["contract_path"]).resolve()
    )
    raw["planner_settings"]["prm"]["n_samples"] = 16
    raw["planner_settings"]["rrt_connect"]["max_iterations"] = 80
    raw["planner_settings"]["ompl"]["solve_time_s"] = 0.15
    raw["planner_settings"]["shared_q_sampled_roadmap"]["n_samples"] = 16
    raw["planner_settings"]["shared_q_sampled_roadmap"]["k_neighbors"] = 4
    raw["lattice"]["edge_n_samples"] = 8
    cfg_path = tmp_path / "planar2r_closeout_fast.json"
    cfg_path.write_text(json.dumps(raw), encoding="utf-8")

    rc = mod.main(
        [
            "--config",
            str(cfg_path),
            "--output",
            str(allowed),
            "--task-ids",
            "near_0",
            "--lattice-shape",
            "6",
            "6",
            "--skip-animations",
        ]
    )
    assert rc == 0
    assert assert_v3_6c_output_allowed(allowed) == allowed.resolve()

    assert (allowed / "index.html").is_file()
    assert (allowed / "architecture.html").is_file()
    assert (allowed / "manifest.json").is_file()
    assert (allowed / "summary.json").is_file()
    trial_dir = allowed / "trials" / "near_0"
    assert (trial_dir / "index.html").is_file()
    assert (trial_dir / "trial.json").is_file()
    assert (trial_dir / "runs.json").is_file()

    man = json.loads((allowed / "manifest.json").read_text(encoding="utf-8"))
    assert man["status"] == "generated"
    assert man["status"] != "scaffold"
    assert man["artifact_version"] == "v3_6c_closeout_v1"
    assert man["task_ids"] == ["near_0"]
    assert man["seed"] == 7
    assert "git_revision" in man
    assert "config_path" in man
    assert man["trace_schema"] == "v3_6c_planner_trace_v1"
    assert man["metric_schema"]["actuator_metric_on_q"] == "actuator_metric_on_q"
    assert man["metric_schema"]["continuous_trajectory"] == "v3_6c_cte_v1"
    assert "freeze_statement" in man
    assert man.get("no_cdn") is True

    index_html = (allowed / "index.html").read_text(encoding="utf-8")
    assert "V3.6C Planar 2R Free-Space Closeout" in index_html
    trial_html = (trial_dir / "index.html").read_text(encoding="utf-8")
    assert "@media print" in trial_html
    assert "anim-live" in trial_html
    assert "contact-sheet" in trial_html
    assert "physical residual" in trial_html
    assert "expansions_are_total_query_work" in trial_html
    assert "vertices" in trial_html
    assert "goal-root count" in trial_html
    assert "not native PRM" in trial_html
    assert "shared_q_sampled" in trial_html
    assert "http://" not in trial_html
    assert "https://cdn" not in trial_html.lower()

    for html_path in (
        allowed / "index.html",
        allowed / "architecture.html",
        trial_dir / "index.html",
    ):
        text = html_path.read_text(encoding="utf-8")
        for ref in _relative_refs(text):
            target = (html_path.parent / ref).resolve()
            assert target.is_file(), f"broken link {ref} from {html_path}"

    for asset in man["assets"]:
        assert (allowed / asset["path"]).is_file(), asset["path"]

    runs = json.loads((trial_dir / "runs.json").read_text(encoding="utf-8"))
    planners = {r["planner"] for r in runs}
    assert "prm" in planners
    assert "shared_q_sampled_dijkstra" in planners
    assert "shared_q_sampled_astar" in planners
    prm_run = next(r for r in runs if r["planner"] == "prm" and r["mechanism"] == "fourbar")
    sq_run = next(
        r for r in runs if r["planner"] == "shared_q_sampled_dijkstra" and r["mechanism"] == "fourbar"
    )
    assert "roadmap" in (prm_run.get("planner_metrics") or {})
    assert "shared_q_sampled_roadmap" in (sq_run.get("planner_metrics") or {})
    assert "roadmap" not in (sq_run.get("planner_metrics") or {})
    provenance = (sq_run.get("planner_metrics") or {}).get("shared_q_sampled_roadmap") or {}
    assert provenance.get("diagnostic_label")


def test_exporter_refuses_frozen_v3_6b_package(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(artifact_freeze, "REPO_ROOT", tmp_path)
    forbidden = tmp_path / "results" / "v3_review" / "v3_6b_planar2r_visual_audit"
    forbidden.mkdir(parents=True)
    mod = _load_exporter()
    monkeypatch.setattr(mod, "assert_v3_6c_output_allowed", assert_v3_6c_output_allowed)
    with pytest.raises(ValueError, match="frozen"):
        mod.main(["--config", str(CLOSEOUT_CONFIG), "--output", str(forbidden)])
    assert not (forbidden / "manifest.json").exists()
    assert not (forbidden / "index.html").exists()
