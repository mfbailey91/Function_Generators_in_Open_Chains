"""Tests for the experiment run registry (IM-016)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from inequality_mechanisms.experiments import (
    ExperimentConfig,
    RunRegistryError,
    capture_environment,
    capture_revision,
    create_run,
    generate_run_id,
    list_runs,
    load_run,
    validate_run_id,
)
from inequality_mechanisms.mechanisms import IndependentFourBars, UnitGearbox

_CR = (1.0, 2.5, 2.0, 2.0)


def _minimal_config(**overrides: object) -> ExperimentConfig:
    data: dict = {
        "seed": 7,
        "mechanisms": {
            "gearbox": UnitGearbox(dim=2).to_dict(),
            "fourbar": IndependentFourBars.from_lengths([_CR, _CR]).to_dict(),
        },
        "graph": {"shape": [8, 8], "wrap": [True, True]},
        "limits": {"lower": [1.0, 1.0], "upper": [2.0, 2.0]},
        "cost": {"type": "output_euclidean"},
        "algorithms": {"names": ["dijkstra", "astar"]},
        "trials": {"n_trials": 2, "preimage_policy": "lex_min_node_id"},
    }
    data.update(overrides)
    return ExperimentConfig.model_validate(data)


class TestRunId:
    def test_generate_unique(self) -> None:
        a = generate_run_id(seed=1)
        b = generate_run_id(seed=1)
        assert a != b
        assert a.startswith("seed1_")
        validate_run_id(a)

    def test_rejects_path_separators(self) -> None:
        with pytest.raises(ValueError, match="path separators"):
            validate_run_id("../escape")

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            validate_run_id("")


class TestCreateAndLoad:
    def test_creates_layout_and_provenance(self, tmp_path: Path) -> None:
        cfg = _minimal_config()
        run = create_run(
            cfg,
            results_root=tmp_path,
            run_id="pilot_smoke",
            revision={
                "package_version": "0.1.0",
                "git_commit": "abc",
                "git_dirty": False,
            },
            environment={"python_version": "test", "packages": {}},
        )
        assert run.run_id == "pilot_smoke"
        assert run.seed == 7
        assert run.status == "created"
        assert (run.path / "manifest.json").is_file()
        assert (run.path / "config.yaml").is_file()
        assert (run.path / "revision.json").is_file()
        assert (run.path / "environment.json").is_file()
        assert (run.path / "outputs").is_dir()

        restored_cfg = run.load_config()
        assert restored_cfg.seed == cfg.seed
        assert restored_cfg.trials.n_trials == 2
        assert run.revision["git_commit"] == "abc"
        assert run.environment["python_version"] == "test"

        loaded = load_run("pilot_smoke", results_root=tmp_path)
        assert loaded.path == run.path
        assert loaded.seed == 7

    def test_refuses_existing_directory(self, tmp_path: Path) -> None:
        cfg = _minimal_config()
        create_run(cfg, results_root=tmp_path, run_id="dup")
        with pytest.raises(FileExistsError):
            create_run(cfg, results_root=tmp_path, run_id="dup")

    def test_auto_run_id_includes_seed(self, tmp_path: Path) -> None:
        run = create_run(_minimal_config(seed=99), results_root=tmp_path)
        assert run.run_id.startswith("seed99_")
        assert run.path.parent == tmp_path.resolve() or run.path.parent == tmp_path


class TestOutputsAndImmutability:
    def test_write_json_and_jsonl(self, tmp_path: Path) -> None:
        run = create_run(_minimal_config(), results_root=tmp_path, run_id="out1")
        run.mark_running()
        assert run.status == "running"
        path = run.write_json("summary", {"n_trials": 2, "ok": True})
        assert path.is_file()
        assert run.outputs["summary"] == "outputs/summary.json"
        assert run.read_json("summary")["n_trials"] == 2

        run.append_jsonl(
            "trials",
            [
                {"trial_index": 0, "status": "ok", "n_expanded": 10},
                {
                    "trial_index": 1,
                    "status": "failed",
                    "failure_reason": "no path",
                },
            ],
        )
        rows = run.read_jsonl("trials")
        assert len(rows) == 2
        assert rows[1]["failure_reason"] == "no path"

        png = run.outputs_dir / "figure.png"
        png.write_bytes(b"\x89PNG\r\n\x1a\n")
        registered = run.register_output("figure", "outputs/figure.png")
        assert registered == png
        assert run.outputs["figure"] == "outputs/figure.png"

        run.mark_completed()
        assert run.status == "completed"
        with pytest.raises(RunRegistryError, match="completed"):
            run.write_json("more", {"x": 1})
        with pytest.raises(RunRegistryError, match="completed"):
            run.append_jsonl("trials", [{"trial_index": 2}])
        with pytest.raises(RunRegistryError, match="completed"):
            run.mark_failed("nope")

    def test_failed_run_remains_writable(self, tmp_path: Path) -> None:
        run = create_run(_minimal_config(), results_root=tmp_path, run_id="fail1")
        run.mark_running()
        run.mark_failed("sampling exhausted")
        assert run.status == "failed"
        assert run.failure_reason == "sampling exhausted"
        run.append_jsonl(
            "trials",
            [
                {
                    "trial_index": 0,
                    "status": "failed",
                    "failure_reason": "sampling exhausted",
                }
            ],
        )
        assert len(run.read_jsonl("trials")) == 1

    def test_rebind_output_path_rejected(self, tmp_path: Path) -> None:
        run = create_run(_minimal_config(), results_root=tmp_path, run_id="rebind")
        run.write_json("artifact", {"a": 1})
        with pytest.raises(RunRegistryError, match="already registered"):
            run.write_text("artifact", "plain", suffix=".txt")


class TestListRuns:
    def test_list_and_filter(self, tmp_path: Path) -> None:
        a = create_run(_minimal_config(seed=1), results_root=tmp_path, run_id="a")
        b = create_run(_minimal_config(seed=2), results_root=tmp_path, run_id="b")
        b.mark_completed()
        all_runs = list_runs(tmp_path)
        assert {r.run_id for r in all_runs} == {"a", "b"}
        completed = list_runs(tmp_path, status="completed")
        assert [r.run_id for r in completed] == ["b"]
        assert a.status == "created"


class TestCaptureHelpers:
    def test_environment_has_python(self) -> None:
        env = capture_environment()
        assert "python_version" in env
        assert "packages" in env
        assert "numpy" in env["packages"]

    def test_revision_package_version(self, tmp_path: Path) -> None:
        # Even outside a git worktree, package_version is set.
        rev = capture_revision(cwd=tmp_path)
        assert rev["package_version"]
        assert "git_commit" in rev


class TestLoadErrors:
    def test_missing_run(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_run("missing", results_root=tmp_path)

    def test_malformed_manifest(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "bad"
        run_dir.mkdir()
        (run_dir / "manifest.json").write_text("{}\n", encoding="utf-8")
        (run_dir / "config.yaml").write_text("seed: 0\n", encoding="utf-8")
        with pytest.raises(RunRegistryError, match="required fields"):
            load_run(run_dir)

    def test_load_by_path(self, tmp_path: Path) -> None:
        run = create_run(_minimal_config(), results_root=tmp_path, run_id="bypath")
        loaded = load_run(run.path)
        assert loaded.run_id == "bypath"
        manifest = json.loads((run.path / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["seed"] == 7
