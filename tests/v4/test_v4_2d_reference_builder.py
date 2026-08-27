"""V4-241 / V4-242 center-IK builder and V4.2B historical loader."""

from __future__ import annotations

from inequality_mechanisms.analysis.v4.optimality_metrics import (
    extract_stage_c_views,
    join_stage_c_to_reference,
    load_stage_c_records,
)
from inequality_mechanisms.analysis.v4.optimality_pairing import (
    decompose_final_gaps,
    pair_mechanism_contrasts,
)
from inequality_mechanisms.analysis.v4.optimality_reference import (
    CANDIDATE_GENERATOR_ID,
    FROZEN_STAGE_C_ROWS,
    PRIMARY_REFERENCE_COUNT,
    build_center_ik_references,
    canonical_dumps,
    load_report_config,
    load_v4_2b_historical_references,
    verify_source_package_digests,
)
from inequality_mechanisms.audits.v4_artifact_guard import (
    canonical_v4_2b_retained_root,
    canonical_v4_2c_retained_root,
    digest_directory_tree,
)
from inequality_mechanisms.experiments.v4.ompl_planner_portfolio_config import (
    FROZEN_V4_2B_FILES_DIGEST,
)


def test_source_package_digests_match_locks() -> None:
    live = verify_source_package_digests()
    assert live["v4_2b_files_digest"] == FROZEN_V4_2B_FILES_DIGEST


def test_center_ik_reference_table_has_100_rows() -> None:
    config = load_report_config()
    records = load_stage_c_records()
    assert len(records) == FROZEN_STAGE_C_ROWS
    payload = build_center_ik_references(config=config, stage_c_rows=records)
    rows = payload["reference_rows"]
    assert len(rows) == PRIMARY_REFERENCE_COUNT
    already = [row for row in rows if row["already_satisfied"]]
    assert already
    assert all(row["j_star_c"] == 0.0 for row in already)
    assert all(row["candidate_generator_id"] == CANDIDATE_GENERATOR_ID for row in rows)
    keys = {(row["case_id"], row["task_id"], row["mechanism"]) for row in rows}
    assert len(keys) == PRIMARY_REFERENCE_COUNT
    views = extract_stage_c_views(records)
    assert len(views) == FROZEN_STAGE_C_ROWS
    assert any(view["already_satisfied"] for view in views)
    joined = join_stage_c_to_reference(
        views,
        rows,
        tau=float(config["tau"]),
        tau_zero=float(config["tau_zero"]),
        eta=tuple(float(item) for item in config["eta"]),
        checkpoints_s=tuple(float(item) for item in config["checkpoints_s"]),
    )
    assert joined["n_stage_c_rows"] == FROZEN_STAGE_C_ROWS
    assert joined["n_orphans"] == 0
    assert len(joined["final_rows"]) == FROZEN_STAGE_C_ROWS
    paired = pair_mechanism_contrasts(
        joined["final_rows"], rows, tau=float(config["tau"])
    )
    assert paired
    assert all(item["pairing_label"] == "index-matched, not CRN" for item in paired)
    decomp = decompose_final_gaps(
        joined["final_rows"],
        payload["candidate_rows"],
        tau=float(config["tau"]),
    )
    assert len(decomp) == FROZEN_STAGE_C_ROWS


def test_center_ik_reference_is_byte_identical_on_regen() -> None:
    config = load_report_config()
    first = build_center_ik_references(config=config)
    second = build_center_ik_references(config=config)
    assert canonical_dumps(first["reference_rows"]) == canonical_dumps(
        second["reference_rows"]
    )
    assert canonical_dumps(first["candidate_rows"]) == canonical_dumps(
        second["candidate_rows"]
    )


def test_v4_2b_input_linear_rows_are_unique() -> None:
    rows = load_v4_2b_historical_references()
    assert len(rows) == PRIMARY_REFERENCE_COUNT
    keys = {(row["case_id"], row["task_id"], row["mechanism"]) for row in rows}
    assert len(keys) == PRIMARY_REFERENCE_COUNT
    assert all(row["j_star_b"] is not None for row in rows)


def test_reference_builder_does_not_write_frozen_packages() -> None:
    before_b = digest_directory_tree(canonical_v4_2b_retained_root())
    before_c = digest_directory_tree(canonical_v4_2c_retained_root())
    load_v4_2b_historical_references()
    build_center_ik_references()
    assert digest_directory_tree(canonical_v4_2b_retained_root()) == before_b
    assert digest_directory_tree(canonical_v4_2c_retained_root()) == before_c
