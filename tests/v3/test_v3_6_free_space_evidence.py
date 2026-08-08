"""Tests for Sprint V3.6 free-space bank, strata, and evidence runner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from inequality_mechanisms.adapters.ompl import is_ompl_available
from inequality_mechanisms.benchmarks.free_space_bank import (
    default_bank_path,
    load_free_space_bank,
    build_bank_arms,
    build_cartesian_problem,
)
from inequality_mechanisms.benchmarks.free_space_report import (
    build_html,
    summarize_strata,
)
from inequality_mechanisms.benchmarks.free_space_strata import (
    assign_size_stratum,
    classify_problem_presearch,
    paired_stratum_from_classes,
    presearch_descriptors,
    tip_separation,
)
from inequality_mechanisms.benchmarks.run_free_space_evidence import (
    evidence_manifest,
    run_free_space_evidence,
)
from inequality_mechanisms.core.goals import CartesianDiskGoalGenerator


REQUIRED_ROW_KEYS = {
    "bank_id",
    "task_id",
    "mechanism",
    "planner",
    "paired_stratum",
    "size_stratum",
    "task_class",
    "tip_distance",
    "presearch",
    "skipped",
    "status",
    "objective_cost",
    "query_time_s",
    "planner_metrics",
    "architecture_version",
}


def test_frozen_bank_loads_from_canonical_path() -> None:
    path = default_bank_path()
    assert path.is_file()
    bank = load_free_space_bank(path)
    assert bank.bank_id == "free_space_planar2r_v1"
    assert bank.schema_version == 1
    assert bank.mechanisms == ("fourbar", "gearbox")
    # Bounded hand-designed evidence pack (not a production Monte Carlo bank).
    assert 10 <= len(bank.tasks) <= 40
    ids = [t.task_id for t in bank.tasks]
    assert len(ids) == len(set(ids))
    assert "already_0" in ids
    assert any(t.task_id.startswith("invalid") for t in bank.tasks)


def test_frozen_bank_path_content_is_stable_json() -> None:
    """Loader must not rewrite the frozen bank file."""
    path = default_bank_path()
    before = path.read_bytes()
    _ = load_free_space_bank(path)
    after = path.read_bytes()
    assert before == after
    raw = json.loads(before.decode("utf-8"))
    assert raw["bank_id"] == "free_space_planar2r_v1"


def test_size_and_paired_strata_deterministic() -> None:
    bank = load_free_space_bank()
    arms = build_bank_arms(bank)
    classes: dict[tuple[str, str], str] = {}
    for task in bank.tasks:
        for mech in bank.mechanisms:
            arm = arms[mech]
            problem = build_cartesian_problem(arm, task)
            fk = arm.robot.planar_fk
            assert fk is not None
            generator = CartesianDiskGoalGenerator(planar_fk=fk)
            task_class, extras, cands = classify_problem_presearch(
                problem, goal_generator=generator
            )
            classes[(task.task_id, mech)] = task_class
            tip_d = tip_separation(arm, task)
            size = assign_size_stratum(tip_d, bank.size_bins)
            desc = presearch_descriptors(
                arm,
                task,
                bank,
                problem,
                task_class=task_class,
                class_extras=extras,
                goal_candidates=cands,
            )
            assert desc["size_stratum"] == size
            assert desc["task_class"] == task_class
            assert desc["tip_distance"] == pytest.approx(tip_d)

    # Second pass must match exactly.
    for task in bank.tasks:
        for mech in bank.mechanisms:
            arm = arms[mech]
            problem = build_cartesian_problem(arm, task)
            fk = arm.robot.planar_fk
            assert fk is not None
            generator = CartesianDiskGoalGenerator(planar_fk=fk)
            task_class, _, _ = classify_problem_presearch(
                problem, goal_generator=generator
            )
            assert task_class == classes[(task.task_id, mech)]

        paired = paired_stratum_from_classes(
            classes[(task.task_id, "fourbar")],
            classes[(task.task_id, "gearbox")],
        )
        assert paired in {
            "both_direct",
            "fourbar_only_direct",
            "gearbox_only_direct",
            "neither_direct",
            "paired_invalid",
        }


def test_runner_required_columns_and_ompl_skip_without_bindings() -> None:
    bank = load_free_space_bank()
    # Keep CI fast: one already + one near task; skip lattice.
    rows = run_free_space_evidence(
        bank=bank,
        planners=(
            "input_linear",
            "output_linear",
            "prm",
            "rrt_connect",
            "ompl_prm",
            "ompl_rrt_connect",
        ),
        task_ids=("already_0", "near_0"),
        ompl_solve_time_s=0.5,
    )
    assert len(rows) == 2 * 2 * 6
    for row in rows:
        missing = REQUIRED_ROW_KEYS - set(row)
        assert not missing, missing
        assert row["architecture_version"] == 3
        assert row["bank_id"] == bank.bank_id
        assert row["task_class"] is not None
        assert row["size_stratum"] in {"short", "medium", "long"}
        assert row["paired_stratum"] is not None

    ompl_rows = [r for r in rows if r["planner"].startswith("ompl_")]
    assert ompl_rows
    if is_ompl_available():
        assert all(r["skipped"] is None for r in ompl_rows)
        assert all(r["status"] is not None for r in ompl_rows)
    else:
        assert all(r["skipped"] == "ompl_unavailable" for r in ompl_rows)
        assert all(r["status"] is None for r in ompl_rows)

    manifest = evidence_manifest(
        rows,
        bank=bank,
        seed=7,
        ompl_solve_time_s=0.5,
        planners=("input_linear", "ompl_prm"),
    )
    assert manifest["snapshot_id"] == "v3_6_free_space"
    assert "not population" in manifest["scope_note"].lower() or (
        "population inference" in manifest["scope_note"].lower()
    )


def test_report_helpers_emit_html() -> None:
    rows = run_free_space_evidence(
        planners=("input_linear",),
        task_ids=("already_0",),
        ompl_solve_time_s=0.1,
    )
    bank = load_free_space_bank()
    manifest = evidence_manifest(
        rows,
        bank=bank,
        seed=7,
        ompl_solve_time_s=0.1,
        planners=("input_linear",),
    )
    summary = summarize_strata(rows)
    html = build_html(manifest=manifest, rows=rows, summary=summary)
    assert "Not population evidence" in html
    assert "already_0" in html
    assert "input_linear" in html
