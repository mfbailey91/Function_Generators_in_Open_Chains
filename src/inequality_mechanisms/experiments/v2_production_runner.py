"""Resumable single-solver production Monte Carlo runner (V2.10–V2.11)."""

from __future__ import annotations

import gc
import json
import os
import signal
import time
from dataclasses import dataclass
from multiprocessing import get_context
from pathlib import Path
from typing import Any

from inequality_mechanisms.experiments.registry import (
    capture_revision,
    default_results_root,
    generate_run_id,
    validate_run_id,
)
from inequality_mechanisms.experiments.resolution import (
    GRID_ANISOTROPY_LIMITATION,
    select_production_resolution,
)
from inequality_mechanisms.experiments.v2_production_canvas import (
    write_production_canvas,
)
from inequality_mechanisms.experiments.v2_production_config import (
    V2ProductionConfig,
    apply_calibration_decisions,
    assert_calibration_decisions_present,
    load_calibration_decisions,
    load_v2_production_config,
    next_confirmation_shape_n,
    production_config_digest,
    stage_mechanism_count,
    stage_task_count,
    v2_production_config_to_yaml,
)
from inequality_mechanisms.experiments.v2_production_environment import (
    apply_numerical_thread_limits,
    capture_production_environment,
    peak_rss_bytes,
)
from inequality_mechanisms.experiments.v2_production_merge import merge_production_run
from inequality_mechanisms.experiments.v2_production_preflight import (
    assert_preflight_allowed,
    memory_preflight,
)
from inequality_mechanisms.experiments.v2_solver_comparison import (
    compare_exact_solver_runs,
)
from inequality_mechanisms.experiments.v2_production_sample_bank import (
    V2SampleBank,
    build_v2_sample_bank,
    load_v2_sample_bank,
    save_v2_sample_bank,
    select_confirmation_subset,
    subset_sample_bank,
)
from inequality_mechanisms.experiments.v2_production_work_unit import (
    run_mechanism_pair_work_unit,
)

PRODUCTION_SCHEMA_VERSION = 1
_INTERRUPT = False


def _on_sigint(signum: int, frame: Any) -> None:  # noqa: ARG001
    global _INTERRUPT
    _INTERRUPT = True


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    _atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _shard_name(mechanism_id: str) -> str:
    digits = "".join(ch for ch in mechanism_id if ch.isdigit()) or "0"
    return f"mechanism_{int(digits):06d}.jsonl"


def _batch_schedule(
    mechanism_ids: list[str],
    config: V2ProductionConfig,
    stage_name: str,
) -> list[list[str]]:
    """Return live launch batches; production starts at the minimum then steps."""
    ids = list(mechanism_ids)
    if stage_name != "production" or not ids:
        return [ids] if ids else []
    minimum = min(int(config.stopping.minimum_mechanisms), len(ids))
    batch_size = max(1, int(config.stopping.batch_size))
    maximum = min(int(config.stopping.maximum_mechanisms), len(ids))
    schedule = [ids[:minimum]]
    start = minimum
    while start < maximum:
        end = min(start + batch_size, maximum)
        schedule.append(ids[start:end])
        start = end
    return [batch for batch in schedule if batch]


def _scientific_fields(row: dict[str, Any]) -> dict[str, Any]:
    skip = {"runtime_s", "peak_rss_bytes", "code_revision", "run_id", "trial_index"}
    return {k: v for k, v in row.items() if k not in skip}


@dataclass(frozen=True, slots=True)
class V2ProductionRunResult:
    """Handle summarizing one production campaign directory."""

    run_id: str
    path: Path
    stage: str
    n_completed: int
    n_failed: int
    n_pending: int
    summary: dict[str, Any] | None


def _prepare_run_dir(
    config: V2ProductionConfig,
    *,
    results_root: Path,
    run_id: str | None,
    resume: bool,
) -> tuple[Path, str, bool]:
    results_root.mkdir(parents=True, exist_ok=True)
    if run_id is not None:
        rid = validate_run_id(run_id)
        run_dir = results_root / rid
        if run_dir.exists():
            if not resume:
                raise FileExistsError(f"run directory already exists: {run_dir}")
            return run_dir, rid, True
        run_dir.mkdir(parents=True)
        return run_dir, rid, False
    rid = generate_run_id(seed=config.seed)
    run_dir = results_root / rid
    run_dir.mkdir(parents=True)
    return run_dir, rid, False


def _validate_resume(
    run_dir: Path,
    config: V2ProductionConfig,
    bank: V2SampleBank,
) -> None:
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"cannot resume without manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("solver_id") != config.search.algorithm:
        raise ValueError("resume solver_id mismatch")
    expected_heuristic = (
        None
        if config.search.algorithm == "dijkstra"
        else config.search.resolved_heuristic
    )
    if manifest.get("heuristic_id") != expected_heuristic:
        raise ValueError("resume heuristic_id mismatch")
    if int(manifest.get("production_schema_version", -1)) != PRODUCTION_SCHEMA_VERSION:
        raise ValueError("resume production schema mismatch")
    if manifest.get("sample_bank_digest") != bank.digest:
        raise ValueError("resume sample-bank digest mismatch")
    if manifest.get("config_digest") != production_config_digest(config):
        raise ValueError("resume config digest mismatch")
    revision = capture_revision()
    stored_rev = manifest.get("code_revision")
    current_rev = revision.get("git_commit")
    if stored_rev and current_rev and stored_rev != current_rev:
        raise ValueError(
            f"resume code-revision mismatch: stored {stored_rev} current {current_rev}"
        )


def _quarantine_tmp_shards(run_dir: Path) -> list[str]:
    shard_dir = run_dir / "shards"
    if not shard_dir.is_dir():
        return []
    quarantined: list[str] = []
    quarantine_dir = run_dir / "failures" / "stale_tmp"
    for tmp in shard_dir.glob(".mechanism_*.tmp"):
        quarantine_dir.mkdir(parents=True, exist_ok=True)
        dest = quarantine_dir / tmp.name.lstrip(".")
        if dest.exists():
            dest.unlink()
        tmp.replace(dest)
        quarantined.append(str(dest.relative_to(run_dir)))
    return quarantined


def _shard_status_ids(run_dir: Path) -> tuple[set[str], set[str]]:
    completed: set[str] = set()
    failed: set[str] = set()
    shard_dir = run_dir / "shards"
    if not shard_dir.is_dir():
        return completed, failed
    for path in shard_dir.glob("mechanism_*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("record_type") != "mechanism_summary":
                continue
            mid = row.get("mechanism_pair_id")
            if not mid:
                break
            status = str(row.get("status") or "")
            if status in {"completed", "completed_with_task_failures"}:
                completed.add(str(mid))
            elif status == "failed":
                failed.add(str(mid))
            break
    return completed, failed


def _completed_ids(run_dir: Path) -> set[str]:
    completed, _failed = _shard_status_ids(run_dir)
    return completed


def _write_shard(run_dir: Path, result: Any) -> Path:
    shard_dir = run_dir / "shards"
    shard_dir.mkdir(parents=True, exist_ok=True)
    final = shard_dir / _shard_name(result.mechanism_pair_id)
    tmp = (
        shard_dir
        / f".{_shard_name(result.mechanism_pair_id).replace('.jsonl', '.tmp')}"
    )
    text = "".join(
        json.dumps(record, sort_keys=True) + "\n"
        for record in result.to_jsonl_records()
    )
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, final)
    if result.status == "failed":
        fail_dir = run_dir / "failures"
        fail_dir.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(
            fail_dir / f"{result.mechanism_pair_id}.json",
            {
                "status": result.status,
                "summary": result.summary,
                "failures": result.failures,
            },
        )
    return final


def _progress_payload(
    *,
    completed: list[str],
    failed: list[str],
    pending: list[str],
    elapsed_s: float,
    stage: str,
) -> dict[str, Any]:
    return {
        "stage": stage,
        "completed": completed,
        "failed": failed,
        "excluded": [],
        "pending": pending,
        "n_completed": len(completed),
        "n_failed": len(failed),
        "n_pending": len(pending),
        "elapsed_s": elapsed_s,
        "updated_at_monotonic": time.monotonic(),
    }


def _execute_one(
    payload: dict[str, Any],
) -> dict[str, Any]:
    config = V2ProductionConfig.model_validate(payload["config"])
    bank = V2SampleBank.from_dict(payload["bank"])
    mechanism = next(
        m for m in bank.mechanisms if m.mechanism_id == payload["mechanism_id"]
    )
    apply_numerical_thread_limits(config.execution.numerical_threads_per_worker)
    result = run_mechanism_pair_work_unit(
        config,
        bank,
        mechanism,
        run_id=str(payload["run_id"]),
        shape=tuple(int(x) for x in payload["shape"]),
        retain_paths=bool(payload["retain_paths"]),
        code_revision=payload.get("code_revision"),
    )
    gc.collect()
    return {
        "mechanism_pair_id": result.mechanism_pair_id,
        "status": result.status,
        "records": result.to_jsonl_records(),
        "summary": result.summary,
        "failures": result.failures,
        "trials": result.trials,
        "comparisons": result.comparisons,
        "peak_rss_bytes": peak_rss_bytes(),
    }


def _result_from_worker_payload(payload: dict[str, Any]) -> Any:
    from inequality_mechanisms.experiments.v2_production_work_unit import (
        MechanismPairWorkResult,
    )

    return MechanismPairWorkResult(
        mechanism_pair_id=str(payload["mechanism_pair_id"]),
        status=str(payload["status"]),
        summary=dict(payload["summary"]),
        trials=list(payload["trials"]),
        comparisons=list(payload["comparisons"]),
        failures=list(payload["failures"]),
    )


def run_v2_production(
    config: V2ProductionConfig,
    *,
    results_root: Path | str | None = None,
    run_id: str | None = None,
    stage: str | None = None,
    resume: bool | None = None,
    sample_bank: V2SampleBank | None = None,
    memory_override: bool | None = None,
    shape_override: tuple[int, int] | None = None,
    n_tasks_override: int | None = None,
    apply_decisions: Path | str | dict[str, Any] | None = None,
    export_sample_bank: Path | str | None = None,
    retry_failed: bool = False,
) -> V2ProductionRunResult:
    """Run one production stage and write a resumable package."""
    global _INTERRUPT
    _INTERRUPT = False
    previous_sigint = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, _on_sigint)
    decisions_payload: dict[str, Any] | None = None
    if apply_decisions is not None:
        decisions_payload = (
            dict(apply_decisions)
            if isinstance(apply_decisions, dict)
            else load_calibration_decisions(apply_decisions)
        )
        config = apply_calibration_decisions(config, decisions_payload)
    elif config.study.calibration_decisions:
        decisions_payload = load_calibration_decisions(
            config.study.calibration_decisions
        )
        config = apply_calibration_decisions(config, decisions_payload)
    stage_name = stage or config.study.stage
    assert_calibration_decisions_present(
        config, stage_name, decisions=decisions_payload
    )
    resume_flag = config.execution.resume if resume is None else bool(resume)
    root = Path(results_root) if results_root is not None else default_results_root()
    apply_numerical_thread_limits(config.execution.numerical_threads_per_worker)
    run_dir, rid, is_resume = _prepare_run_dir(
        config, results_root=root, run_id=run_id, resume=resume_flag
    )
    n_mech = stage_mechanism_count(config, stage_name)
    n_tasks = (
        int(n_tasks_override)
        if n_tasks_override is not None
        else stage_task_count(config, stage_name)
    )
    shape = tuple(int(x) for x in config.sampling.shape)
    if shape_override is not None:
        shape = (int(shape_override[0]), int(shape_override[1]))
    elif stage_name == "high_resolution_confirmation":
        n = next_confirmation_shape_n(config)
        shape = (n, n)
    elif config.population.production_shape_n is not None and stage_name in {
        "production",
        "variance_pilot",
        "hardware_calibration",
        "task_count_calibration",
    }:
        n = int(config.population.production_shape_n)
        shape = (n, n)

    revision = capture_revision()
    environment = capture_production_environment(
        workers=config.execution.workers,
        numerical_threads_per_worker=config.execution.numerical_threads_per_worker,
        graph_shape=shape,
        process_start_method="spawn" if config.execution.workers > 1 else None,
    )
    preflight = memory_preflight(
        config,
        total_memory_bytes=environment.get("total_memory_bytes"),
        override=memory_override,
        stage=stage_name,
    )
    if stage_name != "build_sample_bank":
        assert_preflight_allowed(preflight)

    if is_resume:
        _quarantine_tmp_shards(run_dir)
        sample_bank = load_v2_sample_bank(run_dir / "sample_bank.json")
        _validate_resume(run_dir, config, sample_bank)
    else:
        if sample_bank is None and config.study.sample_bank:
            bank_path = Path(config.study.sample_bank)
            if bank_path.is_file():
                sample_bank = load_v2_sample_bank(bank_path)
            elif stage_name != "build_sample_bank":
                raise FileNotFoundError(f"sample bank not found: {bank_path}")
        if sample_bank is None:
            bank_n = max(n_mech, 2)
            if stage_name in {"hardware_calibration", "resolution_calibration"}:
                bank_n = max(n_mech, config.population.calibration_mechanisms)
            elif stage_name in {
                "variance_pilot",
                "production",
                "build_sample_bank",
                "high_resolution_confirmation",
            }:
                bank_n = max(n_mech, config.population.variance_pilot_mechanisms)
            bank_tasks = n_tasks
            if stage_name != "smoke":
                bank_tasks = max(
                    n_tasks, int(config.population.candidate_tasks_per_mechanism[0])
                )
            sample_bank = build_v2_sample_bank(
                config,
                n_mechanisms=bank_n,
                n_tasks=bank_tasks,
            )
        _atomic_write_text(
            run_dir / "config.snapshot.yaml", v2_production_config_to_yaml(config)
        )
        save_v2_sample_bank(sample_bank, run_dir / "sample_bank.json")
        _atomic_write_json(run_dir / "environment.json", environment)
        _atomic_write_json(run_dir / "revision.json", revision)
        _atomic_write_json(
            run_dir / "manifest.json",
            {
                "run_id": rid,
                "architecture_version": 2,
                "package_kind": "production_monte_carlo",
                "stage": stage_name,
                "status": "running",
                "solver_id": config.search.algorithm,
                "solver_schema_version": 1,
                "heuristic_id": (
                    None
                    if config.search.algorithm == "dijkstra"
                    else config.search.resolved_heuristic
                ),
                "production_schema_version": PRODUCTION_SCHEMA_VERSION,
                "sample_bank_digest": sample_bank.digest,
                "sample_bank_version": sample_bank.schema_version,
                "config_digest": production_config_digest(config),
                "code_revision": revision.get("git_commit"),
                "grid_anisotropy_limitation": GRID_ANISOTROPY_LIMITATION,
                "objective_id": "actuator_travel",
                "reference_run": config.study.reference_run,
                "confirmation_subset_source": config.study.confirmation_subset,
            },
        )

    if sample_bank is None:
        raise RuntimeError("sample bank missing after run setup")
    if export_sample_bank is not None:
        save_v2_sample_bank(sample_bank, export_sample_bank)
    reference_ids: list[str] | None = None
    if config.study.reference_run:
        reference_dir = Path(config.study.reference_run)
        reference_manifest_path = reference_dir / "manifest.json"
        if not reference_manifest_path.is_file():
            raise FileNotFoundError(
                f"reference run manifest not found: {reference_manifest_path}"
            )
        reference_manifest = json.loads(
            reference_manifest_path.read_text(encoding="utf-8")
        )
        if reference_manifest.get("solver_id") != "dijkstra":
            raise ValueError("A* reference run must be a Dijkstra campaign")
        if reference_manifest.get("sample_bank_digest") != sample_bank.digest:
            raise ValueError("reference run sample-bank digest mismatch")
        reference_completed, _reference_failed = _shard_status_ids(reference_dir)
        reference_ids = [
            m.mechanism_id
            for m in sample_bank.mechanisms
            if m.mechanism_id in reference_completed
        ]
        if not reference_ids:
            raise ValueError("reference run has no completed mechanism shards")
        manifest_path = run_dir / "manifest.json"
        manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_payload["reference_mechanism_count"] = len(reference_ids)
        manifest_payload["reference_mechanism_ids"] = reference_ids
        _atomic_write_json(manifest_path, manifest_payload)
    if stage_name == "build_sample_bank":
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        manifest["status"] = "completed"
        manifest["n_completed"] = 0
        manifest["n_failed"] = 0
        manifest["n_pending"] = 0
        manifest["n_mechanisms"] = len(sample_bank.mechanisms)
        manifest["n_tasks"] = len(sample_bank.tasks)
        _atomic_write_json(run_dir / "manifest.json", manifest)
        return V2ProductionRunResult(
            run_id=rid,
            path=run_dir,
            stage=stage_name,
            n_completed=0,
            n_failed=0,
            n_pending=0,
            summary={
                "n_mechanisms": len(sample_bank.mechanisms),
                "n_tasks": len(sample_bank.tasks),
                "sample_bank_digest": sample_bank.digest,
            },
        )

    if stage_name == "high_resolution_confirmation":
        subset_path = run_dir / "confirmation_subset.json"
        if subset_path.is_file():
            subset_payload = json.loads(subset_path.read_text(encoding="utf-8"))
            confirmation_ids = [str(x) for x in subset_payload.get("mechanism_ids", [])]
        elif config.study.confirmation_subset:
            source_subset = Path(config.study.confirmation_subset)
            subset_payload = json.loads(source_subset.read_text(encoding="utf-8"))
            confirmation_ids = [str(x) for x in subset_payload.get("mechanism_ids", [])]
            if not confirmation_ids:
                raise ValueError("configured confirmation subset contains no IDs")
            copied_payload = dict(subset_payload)
            copied_payload["reused_from"] = str(source_subset)
            copied_payload["solver_campaign"] = config.search.algorithm
            _atomic_write_json(subset_path, copied_payload)
        else:
            selected = select_confirmation_subset(
                sample_bank, n_mechanisms=n_mech, seed=config.seed
            )
            confirmation_ids = [m.mechanism_id for m in selected]
            _atomic_write_json(
                subset_path,
                {
                    "mechanism_ids": confirmation_ids,
                    "n_mechanisms": len(confirmation_ids),
                    "selection_rule": "stratified_mean_log_gain_var",
                    "shape": list(shape),
                    "selected_before_search": True,
                },
            )
        working_bank = subset_sample_bank(
            sample_bank, mechanism_ids=confirmation_ids, n_tasks=n_tasks
        )
    elif reference_ids is not None:
        working_bank = subset_sample_bank(
            sample_bank, mechanism_ids=reference_ids, n_tasks=n_tasks
        )
    else:
        working_bank = subset_sample_bank(
            sample_bank, n_mechanisms=n_mech, n_tasks=n_tasks
        )

    completed_set, failed_set = _shard_status_ids(run_dir)
    completed = sorted(completed_set)
    failed = sorted(failed_set)
    skip = set(completed) if retry_failed else set(completed) | set(failed)
    pending = [
        m.mechanism_id for m in working_bank.mechanisms if m.mechanism_id not in skip
    ]
    started = time.monotonic()
    last_progress = started
    _atomic_write_json(
        run_dir / "progress.json",
        _progress_payload(
            completed=completed,
            failed=failed,
            pending=pending,
            elapsed_s=0.0,
            stage=stage_name,
        ),
    )

    retain_paths = config.visualization.production_path_samples > 0
    workers = int(config.execution.workers)
    calibration_peaks: list[int] = []
    stop_reason: str | None = None

    def _emit_progress(elapsed_s: float) -> None:
        remaining = [
            mid
            for mid in pending
            if mid not in set(completed) and mid not in set(failed)
        ]
        payload = _progress_payload(
            completed=list(completed),
            failed=list(failed),
            pending=remaining,
            elapsed_s=elapsed_s,
            stage=stage_name,
        )
        _atomic_write_json(run_dir / "progress.json", payload)
        print(
            f"[{stage_name}] completed={payload['n_completed']} "
            f"failed={payload['n_failed']} pending={payload['n_pending']} "
            f"elapsed_s={elapsed_s:.1f}",
            flush=True,
        )

    def _consume_result(result_obj: Any) -> None:
        nonlocal last_progress
        _write_shard(run_dir, result_obj)
        mid = str(result_obj.mechanism_pair_id)
        if result_obj.status == "failed":
            if mid not in failed:
                failed.append(mid)
            if mid in completed:
                completed.remove(mid)
        else:
            if mid in failed:
                failed.remove(mid)
            if mid not in completed:
                completed.append(mid)
        if result_obj.summary.get("peak_rss_bytes"):
            calibration_peaks.append(int(result_obj.summary["peak_rss_bytes"]))
        now = time.monotonic()
        if now - last_progress >= float(config.execution.progress_interval_s):
            _emit_progress(now - started)
            last_progress = now

    def _run_one_mechanism(mechanism: Any, *, retain: bool) -> Any:
        attempts = 1 + int(config.execution.pair_build_retries)
        result = None
        for attempt in range(1, attempts + 1):
            result = run_mechanism_pair_work_unit(
                config,
                working_bank,
                mechanism,
                run_id=rid,
                shape=shape,
                retain_paths=retain,
                code_revision=revision.get("git_commit"),
            )
            if result.status != "failed" or attempt >= attempts:
                return result
            fail_dir = run_dir / "failures"
            fail_dir.mkdir(parents=True, exist_ok=True)
            _atomic_write_json(
                fail_dir / f"{result.mechanism_pair_id}.attempt{attempt}.json",
                {
                    "status": result.status,
                    "attempt": attempt,
                    "summary": result.summary,
                    "failures": result.failures,
                },
            )
        return result

    try:
        for batch_ids in _batch_schedule(
            [m.mechanism_id for m in working_bank.mechanisms],
            config,
            stage_name,
        ):
            if _INTERRUPT or stop_reason is not None:
                break
            batch_mechs = [
                m for m in working_bank.mechanisms if m.mechanism_id in set(batch_ids)
            ]
            if workers == 1 or stage_name == "smoke":
                for mechanism in batch_mechs:
                    if _INTERRUPT:
                        break
                    if mechanism.mechanism_id in set(completed):
                        continue
                    if mechanism.mechanism_id in set(failed) and not retry_failed:
                        continue
                    result = _run_one_mechanism(
                        mechanism,
                        retain=(
                            retain_paths
                            and len(completed)
                            < config.visualization.production_path_samples
                        ),
                    )
                    _consume_result(result)
                    gc.collect()
            else:
                ctx = get_context("spawn")
                jobs = [
                    {
                        "config": config.model_dump(mode="json"),
                        "bank": working_bank.to_dict(),
                        "mechanism_id": mechanism.mechanism_id,
                        "run_id": rid,
                        "shape": list(shape),
                        "retain_paths": False,
                        "code_revision": revision.get("git_commit"),
                    }
                    for mechanism in batch_mechs
                    if mechanism.mechanism_id not in set(completed)
                    and (retry_failed or mechanism.mechanism_id not in set(failed))
                ]
                if jobs:
                    with ctx.Pool(processes=workers) as pool:
                        for payload in pool.imap_unordered(
                            _execute_one, jobs, chunksize=1
                        ):
                            if _INTERRUPT:
                                pool.terminate()
                                break
                            _consume_result(_result_from_worker_payload(payload))
            if (
                stage_name == "production"
                and not _INTERRUPT
                and reference_ids is None
            ):
                interim = merge_production_run(run_dir, config)
                precision = interim["analysis"]["precision"]
                if precision.get("stop"):
                    stop_reason = str(precision.get("stop_reason") or "precision")
                    break
    finally:
        signal.signal(signal.SIGINT, previous_sigint)

    remaining = [
        mid for mid in pending if mid not in set(completed) and mid not in set(failed)
    ]
    _atomic_write_json(
        run_dir / "progress.json",
        _progress_payload(
            completed=list(completed),
            failed=list(failed),
            pending=remaining,
            elapsed_s=time.monotonic() - started,
            stage=stage_name,
        ),
    )
    if calibration_peaks:
        _atomic_write_json(
            run_dir / "calibration_resources.json",
            {
                "n_pairs": len(calibration_peaks),
                "peak_rss_bytes_max": max(calibration_peaks),
                "peak_rss_bytes_mean": sum(calibration_peaks) / len(calibration_peaks),
                "elapsed_s": time.monotonic() - started,
                "workers": workers,
                "shape": list(shape),
            },
        )

    summary = None
    if remaining and _INTERRUPT:
        status = "interrupted"
    elif stop_reason is not None:
        status = "completed"
        summary = merge_production_run(run_dir, config)
    elif remaining:
        status = "incomplete"
    else:
        status = "completed"
        summary = merge_production_run(
            run_dir,
            config,
            expected_mechanism_ids=[m.mechanism_id for m in working_bank.mechanisms],
        )
    if status == "completed" and config.study.reference_run:
        if summary is None:
            summary = merge_production_run(run_dir, config)
        solver_comparison = compare_exact_solver_runs(
            config.study.reference_run,
            run_dir,
        )
        _atomic_write_json(
            run_dir / "reports" / "solver_comparison.json",
            solver_comparison,
        )
        summary["solver_comparison"] = {
            key: value
            for key, value in solver_comparison.items()
            if key != "paired_trials"
        }
        _atomic_write_json(run_dir / "merged" / "summary.json", summary)
    if status == "completed" and config.visualization.generate_canvas_after_run:
        if summary is None:
            summary = merge_production_run(run_dir, config)
        env_payload = json.loads((run_dir / "environment.json").read_text())
        write_production_canvas(
            run_dir,
            {"summary": summary, "environment": env_payload, "stage": stage_name},
        )
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest["status"] = status
    manifest["stop_reason"] = stop_reason
    manifest["n_completed"] = len(completed)
    manifest["n_failed"] = len(failed)
    manifest["n_pending"] = len(remaining)
    _atomic_write_json(run_dir / "manifest.json", manifest)
    return V2ProductionRunResult(
        run_id=rid,
        path=run_dir,
        stage=stage_name,
        n_completed=len(completed),
        n_failed=len(failed),
        n_pending=len(remaining),
        summary=summary,
    )


def run_resolution_calibration(
    config: V2ProductionConfig,
    *,
    results_root: Path | str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Run a representative subset across candidate resolutions."""
    root = Path(results_root) if results_root is not None else default_results_root()
    rid = run_id or generate_run_id(seed=config.seed)
    bank = build_v2_sample_bank(
        config,
        n_mechanisms=stage_mechanism_count(config, "resolution_calibration"),
        n_tasks=stage_task_count(config, "hardware_calibration"),
    )
    rows: list[dict[str, Any]] = []
    for shape_n in config.population.candidate_resolutions:
        stage_run = run_v2_production(
            config,
            results_root=root,
            run_id=f"{rid}_n{shape_n}",
            stage="resolution_calibration",
            resume=False,
            sample_bank=bank,
            shape_override=(int(shape_n), int(shape_n)),
            memory_override=True,
        )
        trials = []
        if stage_run.summary is not None:
            analysis = stage_run.summary["analysis"]
            effect = analysis["hierarchical_bootstrap"].get("estimate")
        else:
            effect = float("nan")
        merged = stage_run.path / "merged" / "trials.jsonl"
        summaries = stage_run.path / "merged" / "mechanism_summary.jsonl"
        n_components = 1
        shapes_seen: set[tuple[int, ...]] = set()
        acceptance = 1.0
        if merged.is_file():
            trials = [
                json.loads(line)
                for line in merged.read_text().splitlines()
                if line.strip()
            ]
            n_found = sum(1 for row in trials if row.get("found"))
            acceptance = float(n_found / len(trials)) if trials else 0.0
            for row in trials:
                graph_shape = row.get("graph_shape")
                if isinstance(graph_shape, list):
                    shapes_seen.add(tuple(int(x) for x in graph_shape))
        if summaries.is_file():
            n_components = 0
            for line in summaries.read_text().splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("graph_invariant_status") == "passed":
                    n_components += 1
            n_components = max(n_components, 1)
        rows.append(
            {
                "shape_n": int(shape_n),
                "primary_effect": float(effect) if effect is not None else float("nan"),
                "n_components": int(n_components),
                "task_acceptance_rate": acceptance,
                "observed_graph_shapes": [list(s) for s in sorted(shapes_seen)],
            }
        )
    decision = select_production_resolution(rows)
    decision["grid_anisotropy_limitation"] = GRID_ANISOTROPY_LIMITATION
    decision["candidates"] = rows
    chosen_n = int(decision["production_shape_n"])
    decision["rejected_shape_n"] = [
        int(row["shape_n"]) for row in rows if int(row["shape_n"]) != chosen_n
    ]
    out_dir = root / rid
    out_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(out_dir / "resolution_decision.json", decision)
    return decision


def run_task_count_calibration(
    config: V2ProductionConfig,
    *,
    results_root: Path | str | None = None,
    run_id: str | None = None,
    apply_decisions: Path | str | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the same calibration bank across candidate tasks-per-mechanism."""
    if apply_decisions is not None:
        decisions_payload = (
            dict(apply_decisions)
            if isinstance(apply_decisions, dict)
            else load_calibration_decisions(apply_decisions)
        )
        config = apply_calibration_decisions(config, decisions_payload)
    elif config.study.calibration_decisions:
        config = apply_calibration_decisions(
            config, load_calibration_decisions(config.study.calibration_decisions)
        )
    root = Path(results_root) if results_root is not None else default_results_root()
    rid = run_id or generate_run_id(seed=config.seed)
    max_k = max(int(k) for k in config.population.candidate_tasks_per_mechanism)
    bank = build_v2_sample_bank(
        config,
        n_mechanisms=stage_mechanism_count(config, "task_count_calibration"),
        n_tasks=max_k,
    )
    rows: list[dict[str, Any]] = []
    prev_effect: float | None = None
    for task_k in config.population.candidate_tasks_per_mechanism:
        stage_run = run_v2_production(
            config,
            results_root=root,
            run_id=f"{rid}_k{task_k}",
            stage="task_count_calibration",
            resume=False,
            sample_bank=bank,
            n_tasks_override=int(task_k),
            memory_override=True,
        )
        effect = float("nan")
        half_width = float("nan")
        if stage_run.summary is not None:
            analysis = stage_run.summary["analysis"]
            bootstrap = analysis["hierarchical_bootstrap"]
            effect = float(bootstrap.get("estimate") or float("nan"))
            precision = analysis.get("precision") or {}
            batches = list(precision.get("batches") or [])
            if batches and batches[-1].get("ci_half_width") is not None:
                half_width = float(batches[-1]["ci_half_width"])
        rel = (
            float("nan")
            if (
                prev_effect is None
                or not np_isfinite(prev_effect)
                or abs(prev_effect) < 1e-12
            )
            else abs(effect - prev_effect) / abs(prev_effect)
        )
        rows.append(
            {
                "tasks_per_mechanism": int(task_k),
                "primary_effect": effect,
                "ci_half_width": half_width,
                "relative_change": rel,
            }
        )
        prev_effect = effect
    chosen = int(rows[-1]["tasks_per_mechanism"])
    reason = "fallback_largest_k"
    threshold = float(config.stopping.max_relative_estimate_change)
    for i, row in enumerate(rows[:-1]):
        nxt = rows[i + 1]
        nxt_rel = nxt.get("relative_change")
        if not isinstance(nxt_rel, (int, float)):
            continue
        nxt_rel_f = float(nxt_rel)
        if np_isfinite(nxt_rel_f) and nxt_rel_f <= threshold:
            chosen = int(row["tasks_per_mechanism"])
            reason = "smallest_stable_k"
            break
    decision = {
        "tasks_per_mechanism": chosen,
        "reason": reason,
        "threshold_relative_change": threshold,
        "candidates": rows,
        "rejected_tasks_per_mechanism": [
            int(row["tasks_per_mechanism"])
            for row in rows
            if int(row["tasks_per_mechanism"]) != chosen
        ],
        "production_shape_n": config.population.production_shape_n,
    }
    out_dir = root / rid
    out_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(out_dir / "task_count_decision.json", decision)
    return decision


def np_isfinite(value: float) -> bool:
    return bool(value == value and value not in {float("inf"), float("-inf")})


def compare_worker_scientific_equivalence(
    serial_trials: list[dict[str, Any]],
    parallel_trials: list[dict[str, Any]],
) -> bool:
    """Return whether two trial lists match on scientific fields."""

    def _key(row: dict[str, Any]) -> tuple[str, str, str]:
        return (
            str(row.get("mechanism_pair_id")),
            str(row.get("mechanism_id")),
            str(row.get("task_id")),
        )

    a = sorted(serial_trials, key=_key)
    b = sorted(parallel_trials, key=_key)
    if len(a) != len(b):
        return False
    return all(_scientific_fields(x) == _scientific_fields(y) for x, y in zip(a, b))


def run_v2_production_from_path(
    path: Path | str,
    *,
    results_root: Path | str | None = None,
    run_id: str | None = None,
    stage: str | None = None,
    resume: bool | None = None,
    memory_override: bool | None = None,
    apply_decisions: Path | str | None = None,
    export_sample_bank: Path | str | None = None,
    retry_failed: bool = False,
) -> V2ProductionRunResult | dict[str, Any]:
    """Load a production YAML and run it."""
    config = load_v2_production_config(path)
    stage_name = stage or config.study.stage
    if stage_name == "resolution_calibration":
        return run_resolution_calibration(
            config, results_root=results_root, run_id=run_id
        )
    if stage_name == "task_count_calibration":
        return run_task_count_calibration(
            config,
            results_root=results_root,
            run_id=run_id,
            apply_decisions=apply_decisions,
        )
    return run_v2_production(
        config,
        results_root=results_root,
        run_id=run_id,
        stage=stage,
        resume=resume,
        memory_override=memory_override,
        apply_decisions=apply_decisions,
        export_sample_bank=export_sample_bank,
        retry_failed=retry_failed,
    )
