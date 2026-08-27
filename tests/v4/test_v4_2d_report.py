"""V4-246–V4-248 figures, HTML, packager, and verifier."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from inequality_mechanisms.audits.v4_2d_artifact import (
    generate_optimality_reference_report,
    package_v4_2d_report,
    verify_v4_2d_artifact,
)
from inequality_mechanisms.audits.v4_artifact_guard import (
    V4_2D_ALLOWED_PACKAGE,
    ArtifactPathForbiddenError,
)
from inequality_mechanisms.benchmarks.classification import TASK_ALREADY_SATISFIED
from inequality_mechanisms.benchmarks.ompl_process_worker_v4_2c import STATUS_COMPLETED
from inequality_mechanisms.visualization.v4.ompl_planner_portfolio import href_targets
from inequality_mechanisms.visualization.v4.optimality_reference_report import (
    FIGURE_SPECS,
    write_figures,
    write_html_report,
)


def _synthetic_record(
    *,
    digest: str,
    mechanism: str,
    planner_id: str,
    task_id: str = "far_0",
    cost: float,
    task_class: str = "direct/local feasible",
    ik_family: str = "elbow_up",
) -> dict:
    checkpoints = [
        {
            "checkpoint_s": t,
            "best_cost": cost,
            "ompl_exact_solution": task_class != TASK_ALREADY_SATISFIED,
        }
        for t in (0.05, 0.10, 0.25, 0.50, 1.00)
    ]
    return {
        "request_digest": digest,
        "case_id": "span_j1_145_j2_145",
        "task_id": task_id,
        "mechanism": mechanism,
        "planner_id": planner_id,
        "repetition": 0,
        "seed": 7,
        "worker": {
            "status": STATUS_COMPLETED,
            "result": {
                "task_class": task_class,
                "objective_cost": cost,
                "selected_goal_candidate": {
                    "provenance": {
                        "candidate_generator_id": "cartesian_disk_center_ik",
                        "goal_sample_id": "disk_center",
                        "ik_family": ik_family,
                    }
                },
                "planner_metrics": {
                    "ompl": {
                        "ompl_exact_solution": True,
                        "direct_connector_available": True,
                        "discrete_goal_state_count": 2,
                        "first_exact_time_s": 0.05,
                        "first_exact_cost": cost,
                        "checkpoints": checkpoints,
                    }
                },
            },
        },
    }


@pytest.fixture
def synthetic_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from inequality_mechanisms.audits import v4_artifact_guard as guard

    monkeypatch.setattr(guard, "REPO_ROOT", tmp_path)
    output = tmp_path / "results" / "v4_review" / V4_2D_ALLOWED_PACKAGE
    output.mkdir(parents=True)
    return output


def test_figures_and_html_links_and_nonclaims(synthetic_output: Path) -> None:
    refs = []
    finals = []
    checkpoints = []
    decomp = []
    paired = []
    for mechanism, j_star, cost in (
        ("fourbar", 1.0, 1.1),
        ("gearbox", 1.2, 1.5),
    ):
        refs.append(
            {
                "case_id": "span_j1_145_j2_145",
                "task_id": "far_0",
                "mechanism": mechanism,
                "task_family": "far",
                "already_satisfied": False,
                "zero_reference": False,
                "j_star_c": j_star,
                "j_star_b": j_star - 0.1,
                "reference_candidate_key": "disk_center::elbow_up",
            }
        )
        finals.append(
            {
                "case_id": "span_j1_145_j2_145",
                "task_id": "far_0",
                "mechanism": mechanism,
                "planner_id": "ompl_rrt_star",
                "repetition": 0,
                "already_satisfied": False,
                "zero_reference": False,
                "ompl_exact_solution": True,
                "objective_cost": cost,
                "final_epsilon_rel": (cost - j_star) / j_star,
                "first_epsilon_rel": (cost - j_star) / j_star,
                "j_star_c": j_star,
                "request_digest": ("a" if mechanism == "fourbar" else "b") * 64,
                "selected_candidate_key": "disk_center::elbow_up",
                "reference_candidate_key": "disk_center::elbow_up",
                "reference_goal_match": True,
            }
        )
        for t in (0.05, 0.10, 0.25, 0.50, 1.00):
            checkpoints.append(
                {
                    "planner_id": "ompl_rrt_star",
                    "mechanism": mechanism,
                    "checkpoint_s": t,
                    "ompl_exact_solution": True,
                    "epsilon_rel": (cost - j_star) / j_star,
                    "already_satisfied": False,
                    "zero_reference": False,
                    "j_star_c": j_star,
                }
            )
        decomp.append(
            {
                "planner_id": "ompl_rrt_star",
                "mechanism": mechanism,
                "decomposition_status": "ok",
                "goal_selection_regret": 0.0,
                "path_inefficiency": cost - j_star,
                "total_gap": cost - j_star,
                "reference_goal_match": True,
            }
        )
    paired.append(
        {
            "case_id": "span_j1_145_j2_145",
            "planner_id": "ompl_rrt_star",
            "already_satisfied": False,
            "delta_j_star_c_fourbar_minus_gearbox": -0.2,
            "delta_epsilon_rel_fourbar_minus_gearbox": -0.15,
        }
    )
    figures = write_figures(
        output_dir=synthetic_output,
        reference_rows=refs,
        checkpoint_rows=checkpoints,
        final_rows=finals,
        paired_rows=paired,
        decomposition_rows=decomp,
        digest_b="c" * 64,
        digest_c="d" * 64,
    )
    assert len(figures) == 12
    for _figure_id, relpath, _title in FIGURE_SPECS:
        assert (synthetic_output / relpath).is_file()
    summary = {
        "lede": (
            "This report is descriptive and is not a global ranking and "
            "not a mechanism ranking."
        ),
        "no_inference_statement": "descriptive only",
        "interpretation_boundary": "same-seed limitation is visible here",
        "prohibited_claims": ["no universal planner ranking"],
        "source_contract": {
            "v4_2b_files_digest": "c" * 64,
            "v4_2c_files_digest": "d" * 64,
            "v4_2c_source_revision": "e" * 40,
        },
        "case_ids": ["span_j1_145_j2_145"],
        "counts": {
            "n_reference_rows": 2,
            "n_stage_c_rows": 2,
            "n_already_satisfied": 0,
        },
        "figures": figures,
    }
    write_html_report(synthetic_output, summary)
    index = synthetic_output / "index.html"
    html = index.read_text(encoding="utf-8")
    assert "winner" not in html.lower()
    assert "same-seed limitation" in html
    assert "not a global ranking" in html
    missing = [path for path in href_targets(index) if not path.exists()]
    assert missing == []
    case_page = synthetic_output / "cases" / "span_j1_145_j2_145" / "index.html"
    assert case_page.is_file()
    case_missing = [path for path in href_targets(case_page) if not path.exists()]
    assert case_missing == []


def test_generate_package_verify_synthetic(
    synthetic_output: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from inequality_mechanisms.analysis.v4 import optimality_reference as refmod
    from inequality_mechanisms.audits import v4_2d_artifact as artifact

    digest_b = "b" * 64
    digest_c = "c" * 64
    monkeypatch.setattr(
        refmod,
        "verify_source_package_digests",
        lambda config=None: {
            "v4_2b_files_digest": digest_b,
            "v4_2c_files_digest": digest_c,
            "v4_2c_source_revision": "d" * 40,
        },
    )
    monkeypatch.setattr(
        artifact,
        "verify_source_package_digests",
        lambda config=None: {
            "v4_2b_files_digest": digest_b,
            "v4_2c_files_digest": digest_c,
            "v4_2c_source_revision": "d" * 40,
        },
    )

    def fake_center(*, config=None, stage_c_rows=None):
        rows = []
        cands = []
        for case_id in config["case_ids"]:
            for task_id in config["task_ids"]:
                for mechanism, j_star in (("fourbar", 1.0), ("gearbox", 1.2)):
                    already = task_id == "near_0"
                    rows.append(
                        {
                            "case_id": case_id,
                            "task_id": task_id,
                            "mechanism": mechanism,
                            "task_family": (
                                "near" if task_id.startswith("near_") else "far"
                            ),
                            "already_satisfied": already,
                            "zero_reference": already,
                            "j_star_c": 0.0 if already else j_star,
                            "reference_candidate_key": None
                            if already
                            else "disk_center::elbow_up",
                            "n_candidates": 2,
                            "candidate_generator_id": "cartesian_disk_center_ik",
                        }
                    )
                    cands.append(
                        {
                            "case_id": case_id,
                            "task_id": task_id,
                            "mechanism": mechanism,
                            "candidate_key": "disk_center::elbow_up",
                            "direct_cost": 0.0 if already else j_star,
                            "direct_valid": True,
                        }
                    )
        return {"reference_rows": rows, "candidate_rows": cands}

    monkeypatch.setattr(artifact, "build_center_ik_references", fake_center)
    monkeypatch.setattr(refmod, "build_center_ik_references", fake_center)

    def fake_hist(*, config=None, package_root=None):
        rows = []
        for case_id in config["case_ids"]:
            for task_id in config["task_ids"]:
                for mechanism, j_star in (("fourbar", 0.8), ("gearbox", 1.0)):
                    rows.append(
                        {
                            "case_id": case_id,
                            "task_id": task_id,
                            "mechanism": mechanism,
                            "j_star_b": 0.0 if task_id == "near_0" else j_star,
                            "selected_goal_sample_id": "center",
                        }
                    )
        return rows

    monkeypatch.setattr(artifact, "load_v4_2b_historical_references", fake_hist)

    records = []
    planners = (
        "ompl_rrt_star",
        "ompl_bit_star",
        "ompl_fmt",
        "ompl_kpiece_u",
        "ompl_prm",
        "ompl_rrt_connect",
    )
    n = 0
    config = json.loads(
        Path("configs/v4/optimality_reference_report_v1.json").read_text(
            encoding="utf-8"
        )
    )
    for case_id in config["case_ids"]:
        for task_id in config["task_ids"]:
            for mechanism in ("fourbar", "gearbox"):
                for planner_id in planners:
                    n += 1
                    already = task_id == "near_0"
                    records.append(
                        _synthetic_record(
                            digest=f"{n:064d}",
                            mechanism=mechanism,
                            planner_id=planner_id,
                            task_id=task_id,
                            cost=(
                                0.0
                                if already
                                else (1.05 if mechanism == "fourbar" else 1.3)
                            ),
                            task_class=TASK_ALREADY_SATISFIED
                            if already
                            else "direct/local feasible",
                        )
                    )
                    records[-1]["case_id"] = case_id

    summary = generate_optimality_reference_report(
        synthetic_output,
        stage_c_records=records,
        verify_sources=False,
    )
    assert summary["n_reference_rows"] == 100
    packaged = package_v4_2d_report(
        synthetic_output,
        source_git_revision="a" * 40,
        allow_dirty=True,
    )
    assert packaged["package"] == V4_2D_ALLOWED_PACKAGE
    verified = verify_v4_2d_artifact(synthetic_output, require_frozen_counts=False)
    assert verified["n_reference_rows"] == 100
    html = (synthetic_output / "index.html").read_text(encoding="utf-8")
    assert "index-matched, not CRN" in html
    frozen_c = synthetic_output.parent / "v4_2c_ompl_planner_portfolio"
    with pytest.raises(ArtifactPathForbiddenError):
        from inequality_mechanisms.audits.v4_artifact_guard import (
            assert_v4_2d_output_allowed,
        )

        assert_v4_2d_output_allowed(frozen_c)
