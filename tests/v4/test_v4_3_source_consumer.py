"""V4-301: digest-locked V4.2B consumption and no-recomputation sentinels."""

from __future__ import annotations

from pathlib import Path

import pytest

from inequality_mechanisms.experiments.v4.intrinsic_static_wrench import (
    V4_3SourceError,
    assert_v4_2b_source_lock,
    consume_v4_2b_corpus,
    coverage_record,
    freeze_lock_constants,
    iter_retained_atlas_rows,
    load_v4_2b_cases,
    resolve_smoke_case_ids,
    resolve_smoke_selection,
    smoke_selection_record,
)
from inequality_mechanisms.experiments.v4.intrinsic_static_wrench_config import (
    FROZEN_MECHANISM_IDS,
    FROZEN_V4_2B_N_GEOMETRY_ROWS,
    FROZEN_V4_2B_N_ROWS_PER_ARM,
    SMOKE_N_RECORDS,
    SourceLock,
    load_intrinsic_static_wrench_config,
)


def test_source_lock_matches_canonical_package() -> None:
    summary = assert_v4_2b_source_lock()
    lock = freeze_lock_constants()
    assert summary["files_digest"] == lock["files_digest"]
    assert summary["n_geometry_rows"] == lock["n_geometry_rows"]
    assert summary["source_revision"] == lock["source_revision"]
    assert summary["n_files"] == lock["n_files"]
    assert len(summary["case_ids"]) == lock["n_cases"]


def test_config_source_lock_matches_freeze() -> None:
    config = load_intrinsic_static_wrench_config()
    assert config.source == SourceLock()
    summary = assert_v4_2b_source_lock(config.source)
    assert summary["config_digest"] == config.source.config_digest


def test_tampered_files_digest_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    lock = SourceLock().model_copy(
        update={
            "files_digest": "0" * 64,
        }
    )
    with pytest.raises(V4_3SourceError, match="files_digest mismatch"):
        assert_v4_2b_source_lock(lock)


def test_cases_require_mounted_coordinate_provenance() -> None:
    cases = load_v4_2b_cases()
    assert len(cases) == 17
    for case in cases:
        assert case["output_coordinate_kind"] == "mounted_joint"
        assert "native_output_offset_rad" in case


def test_full_corpus_row_accounting_without_wrench() -> None:
    consumed, pairs, coverage = consume_v4_2b_corpus(evaluate_wrench=False)
    assert coverage.n_rows == FROZEN_V4_2B_N_GEOMETRY_ROWS
    assert coverage.n_typed_failures == 0
    assert coverage.n_silent_drops == 0
    for mech in FROZEN_MECHANISM_IDS:
        assert coverage.n_rows_per_arm[mech] == FROZEN_V4_2B_N_ROWS_PER_ARM
    assert coverage.n_pairs == FROZEN_V4_2B_N_GEOMETRY_ROWS // 3
    assert len(consumed) == FROZEN_V4_2B_N_GEOMETRY_ROWS
    assert len(pairs) == coverage.n_pairs
    assert all(item.wrench is None for item in consumed)
    payload = coverage_record(coverage)
    assert payload["n_rows"] == FROZEN_V4_2B_N_GEOMETRY_ROWS


def test_smoke_selection_resolves_sixty_records_and_evaluates_wrench() -> None:
    selection, consumed, pairs = resolve_smoke_selection()
    assert selection.n_records == SMOKE_N_RECORDS
    assert len(consumed) == SMOKE_N_RECORDS
    assert len(pairs) == SMOKE_N_RECORDS // 3
    assert all(item.wrench is not None for item in consumed)
    assert all(item.source_failure_code is None for item in consumed)
    case_ids = resolve_smoke_case_ids()
    assert case_ids == selection.case_ids
    assert "span_j1_145_j2_145" in case_ids
    assert "span_j1_175_j2_145" in case_ids
    record = smoke_selection_record(selection)
    assert record["n_records"] == SMOKE_N_RECORDS
    assert len(record["selection_digest"]) == 64


def test_duplicate_identity_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    case_id = "span_j1_145_j2_145"
    first = next(iter_retained_atlas_rows(case_id))

    def _dup_iter(requested_case_id: str, *, root: Path | None = None):  # type: ignore[no-untyped-def]
        del root
        assert requested_case_id == case_id
        yield first
        yield first

    monkeypatch.setattr(
        "inequality_mechanisms.experiments.v4.intrinsic_static_wrench.iter_retained_atlas_rows",
        _dup_iter,
    )
    monkeypatch.setattr(
        "inequality_mechanisms.experiments.v4.intrinsic_static_wrench.load_v4_2b_cases",
        lambda *, root=None: [
            {
                "case_id": case_id,
                "output_coordinate_kind": "mounted_joint",
                "native_output_offset_rad": [0.0, 0.0],
            }
        ],
    )
    with pytest.raises(V4_3SourceError, match="duplicate source identity"):
        consume_v4_2b_corpus(case_ids=[case_id], evaluate_wrench=False)


def test_missing_arm_fails_closed() -> None:
    case_id = resolve_smoke_case_ids()[0]
    consumed = []
    for identity, row in iter_retained_atlas_rows(case_id):
        if identity.mechanism_id == "identity_on_shared_q":
            continue
        if identity.grid_index != (0, 0):
            continue
        from inequality_mechanisms.experiments.v4.intrinsic_static_wrench import (
            evaluate_restored_row,
        )

        consumed.append(evaluate_restored_row(identity, row, evaluate_wrench=False))
    from inequality_mechanisms.experiments.v4.intrinsic_static_wrench import (
        pair_physical_samples,
    )

    with pytest.raises(V4_3SourceError, match="missing arms"):
        pair_physical_samples(consumed)


def test_altered_mounted_provenance_fails_closed() -> None:
    case_id = "span_j1_145_j2_145"
    identity = None
    row = None
    for cand_identity, cand_row in iter_retained_atlas_rows(case_id):
        if cand_identity.mechanism_id == "fourbar":
            identity, row = cand_identity, cand_row
            break
    assert identity is not None and row is not None and row.snapshot is not None
    bad_prov = dict(row.snapshot.provenance)
    bad_prov["mechanism_type"] = "native_joint"
    from dataclasses import replace

    bad_snapshot = replace(row.snapshot, provenance=bad_prov)
    bad_row = replace(row, snapshot=bad_snapshot)
    from inequality_mechanisms.experiments.v4.intrinsic_static_wrench import (
        evaluate_restored_row,
    )

    with pytest.raises(V4_3SourceError, match="mechanism_type"):
        evaluate_restored_row(identity, bad_row, evaluate_wrench=False)


def test_consumer_does_not_call_geometry_or_rank_recompute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def _boom_geometry(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        calls.append("geometry_snapshot")
        raise AssertionError("geometry_snapshot must not be called")

    def _boom_evaluate(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        calls.append("evaluate_atlas_sample")
        raise AssertionError("evaluate_atlas_sample must not be called")

    def _boom_rank(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        calls.append("rank_report")
        raise AssertionError("rank_report must not be called")

    # Patch the real imported call sites the consumer stack could hit.
    monkeypatch.setattr(
        "inequality_mechanisms.metrics.static_wrench.geometry_snapshot",
        _boom_geometry,
    )
    monkeypatch.setattr(
        "inequality_mechanisms.metrics.static_wrench.rank_report",
        _boom_rank,
    )
    monkeypatch.setattr(
        "inequality_mechanisms.experiments.v4.geometry_atlas.evaluate_atlas_sample",
        _boom_evaluate,
    )
    monkeypatch.setattr(
        "inequality_mechanisms.transmission_geometry.snapshot.geometry_snapshot",
        _boom_geometry,
    )

    selection, consumed, _pairs = resolve_smoke_selection()
    assert selection.n_records == SMOKE_N_RECORDS
    assert len(consumed) == SMOKE_N_RECORDS
    assert calls == []


def test_wrong_source_root_fails_verification(tmp_path: Path) -> None:
    fake = tmp_path / "not_v4_2b"
    fake.mkdir()
    (fake / "manifest.json").write_text("{}", encoding="utf-8")
    with pytest.raises(Exception):
        assert_v4_2b_source_lock(root=fake)
