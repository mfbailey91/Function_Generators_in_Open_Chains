"""Resumable Dijkstra production Monte Carlo runner (V2-905–V2-911)."""

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
    load_v2_production_config,
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
from inequality_mechanisms.experiments.v2_production_sample_bank import (
    V2SampleBank,
    build_v2_sample_bank,
    load_v2_sample_bank,
    save_v2_sample_bank,
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
    if manifest.get("solver_id") != "dijkstra":
        raise ValueError("resume solver_id mismatch")
    if int(manifest.get("production_schema_version", -1)) != PRODUCTION_SCHEMA_VERSION:
        raise ValueError("resume production schema mismatch")
    if manifest.get("sample_bank_digest") != bank.digest:
        raise ValueError("resume sample-bank digest mismatch")
    if manifest.get("config_digest") != production_config_digest(config):
        raise ValueError("resume config digest mismatch")


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


def _completed_ids(run_dir: Path) -> set[str]:
    ids: set[str] = set()
    shard_dir = run_dir / "shards"
    if not shard_dir.is_dir():
        return ids
    for path in shard_dir.glob("mechanism_*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("record_type") == "mechanism_summary" and row.get(
                "mechanism_pair_id"
            ):
                ids.add(str(row["mechanism_pair_id"]))
                break
    return ids


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
) -> V2ProductionRunResult:
    """Run one production stage and write a resumable package."""
    global _INTERRUPT
    _INTERRUPT = False
    previous_sigint = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, _on_sigint)
    stage_name = stage or config.study.stage
    resume_flag = config.execution.resume if resume is None else bool(resume)
    root = Path(results_root) if results_root is not None else default_results_root()
    apply_numerical_thread_limits(config.execution.numerical_threads_per_worker)
    run_dir, rid, is_resume = _prepare_run_dir(
        config, results_root=root, run_id=run_id, resume=resume_flag
    )
    n_mech = stage_mechanism_count(config, stage_name)
    n_tasks = stage_task_count(config, stage_name)
    shape = tuple(int(x) for x in config.sampling.shape)
    if config.population.production_shape_n is not None and stage_name in {
        "production",
        "variance_pilot",
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
    )
    assert_preflight_allowed(preflight)

    if is_resume:
        _quarantine_tmp_shards(run_dir)
        sample_bank = load_v2_sample_bank(run_dir / "sample_bank.json")
        _validate_resume(run_dir, config, sample_bank)
    else:
        if sample_bank is None and config.study.sample_bank:
            sample_bank = load_v2_sample_bank(config.study.sample_bank)
        if sample_bank is None:
            bank_n = max(n_mech, 2)
            if stage_name in {"hardware_calibration", "resolution_calibration"}:
                bank_n = max(n_mech, config.population.calibration_mechanisms)
            elif stage_name in {"variance_pilot", "production", "build_sample_bank"}:
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
                "solver_id": "dijkstra",
                "solver_schema_version": 1,
                "heuristic_id": None,
                "production_schema_version": PRODUCTION_SCHEMA_VERSION,
                "sample_bank_digest": sample_bank.digest,
                "sample_bank_version": sample_bank.schema_version,
                "config_digest": production_config_digest(config),
                "code_revision": revision.get("git_commit"),
                "grid_anisotropy_limitation": GRID_ANISOTROPY_LIMITATION,
                "objective_id": "actuator_travel",
            },
        )

    working_bank = subset_sample_bank(sample_bank, n_mechanisms=n_mech, n_tasks=n_tasks)

    completed = sorted(_completed_ids(run_dir))
    failed: list[str] = []
    pending = [
        m.mechanism_id
        for m in working_bank.mechanisms
        if m.mechanism_id not in set(completed)
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

    def _consume_result(result_obj: Any) -> None:
        nonlocal last_progress
        _write_shard(run_dir, result_obj)
        if result_obj.status == "failed":
            failed.append(result_obj.mechanism_pair_id)
        else:
            completed.append(result_obj.mechanism_pair_id)
        if result_obj.summary.get("peak_rss_bytes"):
            calibration_peaks.append(int(result_obj.summary["peak_rss_bytes"]))
        now = time.monotonic()
        if now - last_progress >= float(config.execution.progress_interval_s):
            remaining = [
                mid
                for mid in pending
                if mid not in set(completed) and mid not in set(failed)
            ]
            _atomic_write_json(
                run_dir / "progress.json",
                _progress_payload(
                    completed=list(completed),
                    failed=list(failed),
                    pending=remaining,
                    elapsed_s=now - started,
                    stage=stage_name,
                ),
            )
            last_progress = now

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
                    result = run_mechanism_pair_work_unit(
                        config,
                        working_bank,
                        mechanism,
                        run_id=rid,
                        shape=shape,
                        retain_paths=(
                            retain_paths
                            and len(completed)
                            < config.visualization.production_path_samples
                        ),
                        code_revision=revision.get("git_commit"),
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
            if stage_name == "production" and not _INTERRUPT:
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
        )
        trials = []
        if stage_run.summary is not None:
            analysis = stage_run.summary["analysis"]
            effect = analysis["hierarchical_bootstrap"].get("estimate")
        else:
            effect = float("nan")
        merged = stage_run.path / "merged" / "trials.jsonl"
        n_components = 1
        acceptance = 1.0
        if merged.is_file():
            trials = [
                json.loads(line)
                for line in merged.read_text().splitlines()
                if line.strip()
            ]
            n_found = sum(1 for row in trials if row.get("found"))
            acceptance = float(n_found / len(trials)) if trials else 0.0
        rows.append(
            {
                "shape_n": int(shape_n),
                "primary_effect": float(effect) if effect is not None else float("nan"),
                "n_components": n_components,
                "task_acceptance_rate": acceptance,
            }
        )
    decision = select_production_resolution(rows)
    decision["grid_anisotropy_limitation"] = GRID_ANISOTROPY_LIMITATION
    out_dir = root / rid
    out_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(out_dir / "resolution_decision.json", decision)
    return decision


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
) -> V2ProductionRunResult:
    """Load a production YAML and run it."""
    config = load_v2_production_config(path)
    return run_v2_production(
        config,
        results_root=results_root,
        run_id=run_id,
        stage=stage,
        resume=resume,
        memory_override=memory_override,
    )
