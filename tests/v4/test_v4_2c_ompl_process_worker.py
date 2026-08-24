"""V4-235: registry worker, atomic writes, typed child timeout/crash."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from inequality_mechanisms.adapters.ompl._availability import is_ompl_available
from inequality_mechanisms.benchmarks.ompl_process_worker_v4_2c import (
    OPTIONAL_PLANNER_IDS,
    PLANNER_FACTORIES,
    REQUIRED_PLANNER_IDS,
    STATUS_CHILD_CRASH,
    STATUS_CHILD_TIMEOUT,
    STATUS_COMPLETED,
    STATUS_REJECTED,
    STATUS_UNSUPPORTED_OPTIONAL,
    compare_fresh_process_agreement,
    execute_request,
    invoke_ompl_worker,
    request_digest,
    write_atomic_json,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _request(**overrides: object) -> dict:
    payload: dict = {
        "schema_id": "v4.2c.ompl_worker_request.v1",
        "planner_id": "ompl_prm",
        "seed": 7,
        "problem_source": "smoke_sampling_2r",
        "mechanism": "fourbar",
        "task_kind": "planning_feasible",
        "planner_params": {"solve_time_s": 0.05},
    }
    payload.update(overrides)
    return payload


def test_registry_covers_required_ids_and_rejects_unknown() -> None:
    assert tuple(PLANNER_FACTORIES) == REQUIRED_PLANNER_IDS
    assert "ompl_pdst_u" in OPTIONAL_PLANNER_IDS
    assert "ompl_pdst_u" not in PLANNER_FACTORIES
    unknown = execute_request(_request(planner_id="ompl_made_up"))
    assert unknown["status"] == STATUS_REJECTED
    assert "unknown_planner_id" in str(unknown["unavailable_reason"])


def test_optional_pdst_and_custom_sampler_are_unsupported_optional() -> None:
    pdst = execute_request(_request(planner_id="ompl_pdst_u"))
    assert pdst["status"] == STATUS_UNSUPPORTED_OPTIONAL
    sampler = execute_request(_request(sampler="precomputed"))
    assert sampler["status"] == STATUS_UNSUPPORTED_OPTIONAL
    assert set(PLANNER_FACTORIES) == set(REQUIRED_PLANNER_IDS)


def test_fmt_rejects_optimizer_checkpoints_and_oneshot_does_too() -> None:
    fmt = execute_request(_request(planner_id="ompl_fmt", checkpoints_s=[0.1, 0.2]))
    assert fmt["status"] == STATUS_REJECTED
    assert fmt["unavailable_reason"] == "fmt_is_independent_sample_count_run"
    oneshot = execute_request(_request(planner_id="ompl_kpiece_u", checkpoints_s=[0.1]))
    assert oneshot["status"] == STATUS_REJECTED
    assert oneshot["unavailable_reason"] == "optimizer_checkpoints_not_supported"


def test_atomic_replace_completed_out_is_full_json(tmp_path: Path) -> None:
    out = tmp_path / "result.json"
    payload = {"status": STATUS_COMPLETED, "ok": True, "n": 3}
    write_atomic_json(out, payload)
    assert json.loads(out.read_text(encoding="utf-8")) == payload
    tmp = tmp_path / f".result.json.{os.getpid()}.tmp"
    tmp.write_text('{"status": "completed", "truncated": tru', encoding="utf-8")
    assert json.loads(out.read_text(encoding="utf-8"))["status"] == STATUS_COMPLETED
    with pytest.raises(json.JSONDecodeError):
        json.loads(tmp.read_text(encoding="utf-8"))


def test_parent_types_child_timeout_and_crash(tmp_path: Path) -> None:
    request = _request()
    timeout_row = invoke_ompl_worker(
        request,
        timeout_s=0.4,
        work_dir=tmp_path / "hang",
        self_test="hang",
        cwd=REPO_ROOT,
    )
    assert timeout_row["status"] == STATUS_CHILD_TIMEOUT
    assert timeout_row["result"] is None
    assert timeout_row["request_digest"] == request_digest(request)

    crash_row = invoke_ompl_worker(
        request,
        timeout_s=5.0,
        work_dir=tmp_path / "crash",
        self_test="crash",
        cwd=REPO_ROOT,
    )
    assert crash_row["status"] == STATUS_CHILD_CRASH
    assert crash_row["result"] is None


def test_failed_attempt_is_retained_not_overwritten_as_success(tmp_path: Path) -> None:
    request = _request()
    row = invoke_ompl_worker(
        request,
        timeout_s=5.0,
        work_dir=tmp_path,
        self_test="crash-after-write",
        cwd=REPO_ROOT,
    )
    assert row["status"] == STATUS_CHILD_CRASH
    assert row["result"] is None
    on_disk = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
    assert on_disk["status"] == STATUS_CHILD_CRASH
    assert on_disk["status"] != STATUS_COMPLETED


def test_truncated_tmp_is_not_counted_complete(tmp_path: Path) -> None:
    request = _request()
    row = invoke_ompl_worker(
        request,
        timeout_s=5.0,
        work_dir=tmp_path,
        self_test="truncated-tmp",
        cwd=REPO_ROOT,
    )
    assert row["status"] == STATUS_CHILD_CRASH
    assert row["unavailable_reason"] == "missing_or_invalid_atomic_out"
    assert not (tmp_path / "result.json").exists()
    leftovers = list(tmp_path.glob(".result.json.*.tmp"))
    assert leftovers
    with pytest.raises(json.JSONDecodeError):
        json.loads(leftovers[0].read_text(encoding="utf-8"))


@pytest.mark.ompl
@pytest.mark.skipif(
    not is_ompl_available(), reason="OMPL Python bindings not installed"
)
def test_two_fresh_processes_record_agreement_without_rng_claim(
    tmp_path: Path,
) -> None:
    request = _request(planner_id="ompl_rrt_connect", seed=7)
    first = invoke_ompl_worker(
        request, timeout_s=30.0, work_dir=tmp_path / "a", cwd=REPO_ROOT
    )
    second = invoke_ompl_worker(
        request, timeout_s=30.0, work_dir=tmp_path / "b", cwd=REPO_ROOT
    )
    comparison = compare_fresh_process_agreement(first, second)
    assert comparison["reproducibility_contract"] == "not_claimed_in_process"
    assert "fresh_process_agreement" in comparison
    if first["status"] == STATUS_COMPLETED and second["status"] == STATUS_COMPLETED:
        assert comparison["status_match"] is True


@pytest.mark.ompl
@pytest.mark.skipif(
    not is_ompl_available(), reason="OMPL Python bindings not installed"
)
def test_fmt_independent_sample_count_run(tmp_path: Path) -> None:
    request = _request(
        planner_id="ompl_fmt",
        num_samples=50,
        planner_params={"solve_time_s": 0.2, "num_samples": 50},
    )
    row = invoke_ompl_worker(request, timeout_s=30.0, work_dir=tmp_path, cwd=REPO_ROOT)
    if row["status"] != STATUS_COMPLETED:
        pytest.skip(f"FMT smoke not completed: {row.get('status')}")
    extras = row["result"]["provenance"]["extras"]
    family = extras["family_metrics"]
    assert family["continuation"] == "independent_sample_count"
    assert family["checkpoints_s"] is None
    assert family["unavailable_reason"] == "fmt_is_independent_sample_count_run"
    assert family["num_samples"] == 50
