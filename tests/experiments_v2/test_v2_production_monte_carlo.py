"""Sprint V2.10 production Monte Carlo orchestration tests."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from inequality_mechanisms.experiments.v2_production_canvas import (
    is_v2_production_run_dir,
)
from inequality_mechanisms.experiments.v2_production_config import (
    V2ProductionConfigError,
    load_v2_production_config,
    production_config_digest,
    validate_v2_production_config_mapping,
)
from inequality_mechanisms.experiments.v2_production_environment import (
    apply_numerical_thread_limits,
    capture_production_environment,
    capture_thread_environment,
)
from inequality_mechanisms.experiments.v2_production_merge import (
    ProductionMergeError,
    load_production_shards,
    merge_production_run,
)
from inequality_mechanisms.experiments.v2_production_preflight import (
    ProductionPreflightError,
    assert_preflight_allowed,
    memory_preflight,
)
from inequality_mechanisms.experiments.v2_production_runner import (
    _batch_schedule,
    compare_worker_scientific_equivalence,
    run_v2_production,
)
from inequality_mechanisms.experiments.v2_production_sample_bank import (
    V2SampleBank,
    build_v2_sample_bank,
    load_v2_sample_bank,
    sample_bank_digest_payload,
    save_v2_sample_bank,
    select_task_templates,
    subset_sample_bank,
)
from inequality_mechanisms.experiments.v2_production_work_unit import (
    run_mechanism_pair_work_unit,
)
from inequality_mechanisms.metrics.hierarchical_bootstrap import (
    assert_not_task_level_iid,
)
from inequality_mechanisms.search.graph_solver import production_dijkstra_solver

REPO = Path(__file__).resolve().parents[2]
SMOKE_CONFIG = REPO / "configs" / "v2" / "production_dijkstra_smoke.yaml"


@pytest.fixture(scope="module")
def smoke_config():
    return load_v2_production_config(SMOKE_CONFIG)


class TestProductionConfig:
    def test_smoke_config_loads(self, smoke_config) -> None:
        assert smoke_config.search.algorithm == "dijkstra"
        assert smoke_config.study.objective_cost == "actuator_travel"
        assert smoke_config.execution.workers == 1

    def test_solver_list_rejected(self, smoke_config) -> None:
        raw = yaml.safe_load(SMOKE_CONFIG.read_text())
        raw["search"] = {"algorithms": ["dijkstra", "astar"]}
        with pytest.raises(V2ProductionConfigError, match="algorithms lists"):
            validate_v2_production_config_mapping(raw)

    def test_non_dijkstra_rejected(self) -> None:
        raw = yaml.safe_load(SMOKE_CONFIG.read_text())
        raw["search"] = {"algorithm": "astar"}
        with pytest.raises(V2ProductionConfigError, match="dijkstra"):
            validate_v2_production_config_mapping(raw)

    def test_alpha_rejected(self) -> None:
        raw = yaml.safe_load(SMOKE_CONFIG.read_text())
        raw["study"]["alphas"] = [0.0, 1.0]
        with pytest.raises(V2ProductionConfigError, match="alphas"):
            validate_v2_production_config_mapping(raw)

    def test_digest_stable(self, smoke_config) -> None:
        assert production_config_digest(smoke_config) == production_config_digest(
            smoke_config
        )


class TestSampleBank:
    def test_task_library_prefixes(self) -> None:
        tasks = select_task_templates(8)
        assert len(tasks) == 8
        assert tasks[0].task_id == "short_interior"
        assert tasks[3].task_id == "long_cross_range"

    def test_bank_build_deterministic(self, smoke_config, tmp_path: Path) -> None:
        bank_a = build_v2_sample_bank(smoke_config, n_mechanisms=2, n_tasks=2)
        bank_b = build_v2_sample_bank(smoke_config, n_mechanisms=2, n_tasks=2)
        assert bank_a.digest == bank_b.digest
        assert len(bank_a.mechanisms) == 2
        assert len(bank_a.tasks) == 2
        path = save_v2_sample_bank(bank_a, tmp_path / "bank.json")
        loaded = load_v2_sample_bank(path)
        assert loaded.digest == bank_a.digest
        assert sample_bank_digest_payload(loaded) == loaded.digest

    def test_digest_mismatch_rejected(self, smoke_config, tmp_path: Path) -> None:
        bank = build_v2_sample_bank(smoke_config, n_mechanisms=2, n_tasks=2)
        payload = bank.to_dict()
        payload["digest"] = "0" * 64
        path = tmp_path / "bad.json"
        path.write_text(json.dumps(payload))
        with pytest.raises(ValueError, match="digest mismatch"):
            load_v2_sample_bank(path)


class TestWorkUnit:
    def test_shared_q_and_dijkstra(self, smoke_config) -> None:
        bank = build_v2_sample_bank(smoke_config, n_mechanisms=1, n_tasks=2)
        result = run_mechanism_pair_work_unit(
            smoke_config,
            subset_sample_bank(bank, n_mechanisms=1, n_tasks=2),
            bank.mechanisms[0],
            run_id="work_unit_test",
            shape=(6, 6),
            retain_paths=True,
        )
        assert result.status in {"completed", "completed_with_task_failures"}
        assert result.summary["graph_invariant_status"] == "passed"
        sides = {row["mechanism_id"] for row in result.trials}
        assert "fourbar" in sides
        assert "span_matched_gearbox" in sides
        assert all(row["solver_id"] == "dijkstra" for row in result.trials)
        assert all(row["heuristic_id"] is None for row in result.trials)
        assert all(row["objective_id"] == "actuator_travel" for row in result.trials)
        assert all(row.get("alpha") is None for row in result.trials)
        solver = production_dijkstra_solver()
        assert solver.solver_id == "dijkstra"


class TestPreflightAndEnvironment:
    def test_memory_preflight_rejects_unsafe_profile(self, smoke_config) -> None:
        report = memory_preflight(
            smoke_config,
            total_memory_bytes=1_000,
            parent_rss_bytes=400,
            worker_peak_rss_bytes=400,
            override=False,
        )
        assert report.allowed is False
        with pytest.raises(ProductionPreflightError):
            assert_preflight_allowed(report)

    def test_memory_override_recorded(self, smoke_config) -> None:
        report = memory_preflight(
            smoke_config,
            total_memory_bytes=1_000,
            parent_rss_bytes=400,
            worker_peak_rss_bytes=400,
            override=True,
        )
        assert report.allowed is True
        assert report.override is True
        assert report.reason == "override_above_limit"

    def test_thread_environment_missing_vars(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for name in (
            "OMP_NUM_THREADS",
            "OPENBLAS_NUM_THREADS",
            "MKL_NUM_THREADS",
            "VECLIB_MAXIMUM_THREADS",
            "NUMEXPR_NUM_THREADS",
        ):
            monkeypatch.delenv(name, raising=False)
        captured = capture_thread_environment()
        assert captured["OMP_NUM_THREADS"] is None
        apply_numerical_thread_limits(1)
        assert capture_thread_environment()["OMP_NUM_THREADS"] == "1"

    def test_environment_capture_includes_hardware_fields(self) -> None:
        env = capture_production_environment(
            workers=1,
            numerical_threads_per_worker=1,
            graph_shape=(8, 8),
        )
        assert "physical_cpu" in env
        assert "total_memory_bytes" in env
        assert env["runner_workers"] == 1
        assert "OMP_NUM_THREADS" in env["numerical_thread_environment"]


class TestShardingAndResume:
    def test_smoke_run_and_resume_skips_completed(
        self, smoke_config, tmp_path: Path
    ) -> None:
        first = run_v2_production(
            smoke_config,
            results_root=tmp_path,
            run_id="prod_smoke_a",
            stage="smoke",
            resume=False,
        )
        assert first.n_completed == 2
        assert first.n_pending == 0
        shard_dir = first.path / "shards"
        shards = sorted(shard_dir.glob("mechanism_*.jsonl"))
        assert len(shards) == 2
        first_mtime = {p.name: p.stat().st_mtime_ns for p in shards}
        first_bytes = {p.name: p.read_bytes() for p in shards}

        second = run_v2_production(
            smoke_config,
            results_root=tmp_path,
            run_id="prod_smoke_a",
            stage="smoke",
            resume=True,
        )
        assert second.n_completed == 2
        assert second.n_pending == 0
        for path in sorted(shard_dir.glob("mechanism_*.jsonl")):
            assert path.stat().st_mtime_ns == first_mtime[path.name]
            assert path.read_bytes() == first_bytes[path.name]

    def test_stale_tmp_quarantined(self, smoke_config, tmp_path: Path) -> None:
        first = run_v2_production(
            smoke_config,
            results_root=tmp_path,
            run_id="prod_smoke_tmp",
            stage="smoke",
            resume=False,
        )
        stale = first.path / "shards" / ".mechanism_000099.tmp"
        stale.write_text("{}\n", encoding="utf-8")
        run_v2_production(
            smoke_config,
            results_root=tmp_path,
            run_id="prod_smoke_tmp",
            stage="smoke",
            resume=True,
        )
        assert not stale.exists()
        quarantined = list((first.path / "failures" / "stale_tmp").glob("*"))
        assert quarantined

    def test_serial_determinism(self, smoke_config, tmp_path: Path) -> None:
        a = run_v2_production(
            smoke_config,
            results_root=tmp_path,
            run_id="prod_det_a",
            stage="smoke",
        )
        b = run_v2_production(
            smoke_config,
            results_root=tmp_path,
            run_id="prod_det_b",
            stage="smoke",
        )
        trials_a = [
            json.loads(line)
            for line in (a.path / "merged" / "trials.jsonl").read_text().splitlines()
            if line.strip()
        ]
        trials_b = [
            json.loads(line)
            for line in (b.path / "merged" / "trials.jsonl").read_text().splitlines()
            if line.strip()
        ]
        assert compare_worker_scientific_equivalence(trials_a, trials_b)

    def test_resume_digest_mismatch_starts_new_campaign(
        self, smoke_config, tmp_path: Path
    ) -> None:
        run_v2_production(
            smoke_config,
            results_root=tmp_path,
            run_id="prod_mismatch",
            stage="smoke",
        )
        manifest = json.loads(
            (tmp_path / "prod_mismatch" / "manifest.json").read_text()
        )
        manifest["sample_bank_digest"] = "deadbeef"
        (tmp_path / "prod_mismatch" / "manifest.json").write_text(json.dumps(manifest))
        with pytest.raises(ValueError, match="sample-bank digest"):
            run_v2_production(
                smoke_config,
                results_root=tmp_path,
                run_id="prod_mismatch",
                stage="smoke",
                resume=True,
            )


class TestMergeAndAnalysis:
    def test_merge_detects_duplicate_ids(self, smoke_config, tmp_path: Path) -> None:
        run = run_v2_production(
            smoke_config,
            results_root=tmp_path,
            run_id="prod_dup",
            stage="smoke",
        )
        shards = load_production_shards(run.path)
        assert shards["trial"]
        duplicate = run.path / "shards" / "mechanism_999999.jsonl"
        duplicate.write_text(
            (run.path / "shards" / "mechanism_000000.jsonl").read_text()
        )
        with pytest.raises(ProductionMergeError, match="duplicate"):
            merge_production_run(run.path, smoke_config)

    def test_hierarchical_grouping_preserved(
        self, smoke_config, tmp_path: Path
    ) -> None:
        run = run_v2_production(
            smoke_config,
            results_root=tmp_path,
            run_id="prod_hier",
            stage="smoke",
        )
        assert run.summary is not None
        analysis = run.summary["analysis"]
        assert analysis["precision"]["cluster_definition"] == "mechanism_pair"
        assert analysis["precision"]["treats_tasks_as_iid"] is False
        assert_not_task_level_iid(analysis["precision"])
        assert "hierarchical_bootstrap" in analysis
        assert (run.path / "reports" / "index.html").is_file()
        html = (run.path / "reports" / "index.html").read_text()
        assert "dijkstra" in html
        assert "actuator_travel" in html

    def test_task_and_mechanism_ids_round_trip(
        self, smoke_config, tmp_path: Path
    ) -> None:
        run = run_v2_production(
            smoke_config,
            results_root=tmp_path,
            run_id="prod_ids",
            stage="smoke",
        )
        trials = [
            json.loads(line)
            for line in (run.path / "merged" / "trials.jsonl").read_text().splitlines()
            if line.strip()
        ]
        assert trials
        assert all(row.get("mechanism_pair_id") for row in trials)
        assert all(row.get("task_id") for row in trials)
        assert all(row.get("sample_bank_digest") for row in trials)


def _expanded_smoke_bank(smoke_config, n_mechanisms: int = 4) -> V2SampleBank:
    base = build_v2_sample_bank(smoke_config, n_mechanisms=2, n_tasks=2)
    mechanisms = [
        replace(base.mechanisms[i % len(base.mechanisms)], mechanism_id=f"pair_{i:06d}")
        for i in range(n_mechanisms)
    ]
    bank = V2SampleBank(
        schema_version=base.schema_version,
        seed=base.seed,
        matching_rule=base.matching_rule,
        objective_id=base.objective_id,
        tasks=list(base.tasks),
        mechanisms=mechanisms,
        digest="",
        provenance=dict(base.provenance),
    )
    return replace(bank, digest=sample_bank_digest_payload(bank))


class TestLiveSequentialProduction:
    def test_batch_schedule_starts_at_minimum(self, smoke_config) -> None:
        ids = [f"pair_{i:06d}" for i in range(8)]
        config = smoke_config.model_copy(
            update={
                "stopping": smoke_config.stopping.model_copy(
                    update={
                        "minimum_mechanisms": 3,
                        "batch_size": 2,
                        "maximum_mechanisms": 7,
                    }
                )
            }
        )
        assert _batch_schedule(ids, config, "smoke") == [ids]
        assert _batch_schedule(ids, config, "production") == [
            ids[:3],
            ids[3:5],
            ids[5:7],
        ]

    def test_production_stops_before_hard_cap(
        self, smoke_config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config = smoke_config.model_copy(
            update={
                "study": smoke_config.study.model_copy(update={"stage": "production"}),
                "population": smoke_config.population.model_copy(
                    update={
                        "minimum_production_mechanisms": 2,
                        "maximum_production_mechanisms": 4,
                        "production_batch_size": 2,
                    }
                ),
                "stopping": smoke_config.stopping.model_copy(
                    update={
                        "minimum_mechanisms": 2,
                        "batch_size": 2,
                        "maximum_mechanisms": 4,
                        "stable_batches_required": 1,
                    }
                ),
            }
        )
        original = __import__(
            "inequality_mechanisms.experiments.v2_production_merge",
            fromlist=["analyze_production_trials"],
        ).analyze_production_trials

        def _force_stop(*args, **kwargs):
            analysis = original(*args, **kwargs)
            analysis["precision"]["stop"] = True
            analysis["precision"]["stop_reason"] = "precision_and_stability"
            return analysis

        monkeypatch.setattr(
            "inequality_mechanisms.experiments.v2_production_merge.analyze_production_trials",
            _force_stop,
        )
        run = run_v2_production(
            config,
            results_root=tmp_path,
            run_id="prod_live_stop",
            stage="production",
            sample_bank=_expanded_smoke_bank(smoke_config, n_mechanisms=4),
        )
        assert run.n_completed == 2
        assert run.n_pending == 2
        manifest = json.loads((run.path / "manifest.json").read_text())
        assert manifest["status"] == "completed"
        assert manifest["stop_reason"] == "precision_and_stability"
        assert manifest["package_kind"] == "production_monte_carlo"
        assert is_v2_production_run_dir(run.path)
        assert (run.path / "reports" / "index.html").is_file()

    def test_generate_v2_canvas_refreshes_production_package(
        self, smoke_config, tmp_path: Path
    ) -> None:
        import importlib.util

        run = run_v2_production(
            smoke_config,
            results_root=tmp_path,
            run_id="prod_canvas_refresh",
            stage="smoke",
        )
        canvas = run.path / "reports" / "index.html"
        canvas.write_text("stale\n", encoding="utf-8")
        script_path = REPO / "scripts" / "generate_v2_canvas.py"
        spec = importlib.util.spec_from_file_location(
            "generate_v2_canvas_script", script_path
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        target, kind = module._resolve_target(
            run.path, latest=False, results_root=tmp_path
        )
        assert kind == "production"
        assert target == run.path.resolve()
        written = module.refresh_production_canvas(target)
        assert written.is_file()
        html = written.read_text(encoding="utf-8")
        assert "dijkstra" in html
        assert "stale" not in html
