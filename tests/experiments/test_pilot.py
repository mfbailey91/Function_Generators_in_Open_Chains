"""Tests for the pilot runner (IM-017)."""

from __future__ import annotations

from pathlib import Path

import pytest

from inequality_mechanisms.experiments import (
    ExperimentConfig,
    RunRegistryError,
    build_paired_graphs,
    create_run,
    load_run,
    run_pilot,
)
from inequality_mechanisms.mechanisms import IndependentFourBars, UnitGearbox

_CR = (1.0, 2.5, 2.0, 2.0)


def _pilot_config(**overrides: object) -> ExperimentConfig:
    data: dict = {
        "seed": 0,
        "mechanisms": {
            "gearbox": UnitGearbox(dim=2).to_dict(),
            "fourbar": IndependentFourBars.from_lengths([_CR, _CR]).to_dict(),
        },
        "graph": {
            "shape": [16, 16],
            "wrap": [True, True],
            "edge_samples": 5,
        },
        "limits": {"lower": [1.05, 1.05], "upper": [2.2, 2.2]},
        "cost": {"type": "output_euclidean"},
        "algorithms": {"names": ["dijkstra", "astar"], "validate_heuristic": False},
        "trials": {
            "n_trials": 3,
            "min_output_separation": 0.05,
            "preimage_policy": "lex_min_node_id",
            "max_sample_attempts": 5000,
        },
    }
    data.update(overrides)
    return ExperimentConfig.model_validate(data)


class TestBuildPairedGraphs:
    def test_shared_limits_and_counts(self) -> None:
        cfg = _pilot_config()
        paired = build_paired_graphs(cfg)
        assert paired.gearbox.limits is paired.limits
        assert paired.fourbar.limits is paired.limits
        assert paired.gearbox.valid_node_count >= 2
        assert paired.fourbar.valid_node_count >= 2
        assert paired.grid.shape == (16, 16)


class TestRunPilot:
    def test_end_to_end_artifacts(self, tmp_path: Path) -> None:
        cfg = _pilot_config()
        run = run_pilot(cfg, results_root=tmp_path, run_id="pilot_e2e")
        assert run.status == "completed"
        assert "trials" in run.outputs
        assert "summary" in run.outputs
        assert "summary_table" in run.outputs
        assert "expansions_raw" in run.outputs
        assert "expansions_normalized" in run.outputs
        assert "expansions_ratio" in run.outputs

        rows = run.read_jsonl("trials")
        # 3 trials × 2 mechanisms × 2 algorithms
        assert len(rows) == 12
        summary = run.read_json("summary")
        assert summary["n_rows"] == 12
        assert "by_group" in summary
        assert summary["result_schema_version"] == "4.0.0"
        assert summary["cost_type"] == "output_euclidean"

        for row in rows:
            assert row["result_schema_version"] == "4.0.0"
            assert row["cost_type"] == "output_euclidean"
            assert row["heuristic_type"] in ("zero", "output_euclidean")
            assert "optimal_cost" in row
            if row["found"]:
                assert row["path_length_u"] is not None
                assert row["path_length_q"] is not None
                assert row["path_length_x"] is not None
                assert row["cost"] == row["optimal_cost"]

        canvas = run.path / "index.html"
        assert canvas.is_file()
        assert "4.0.0" in canvas.read_text(encoding="utf-8")

        for name in (
            "expansions_raw",
            "expansions_normalized",
            "expansions_ratio",
        ):
            path = run.resolve_output(name)
            assert path.is_file()
            assert path.stat().st_size > 0

        table_path = run.resolve_output("summary_table")
        assert table_path.read_text(encoding="utf-8").startswith("section,")

    @pytest.mark.parametrize("cost_type", ["uniform", "input_euclidean"])
    def test_alternate_costs_record_schema(self, tmp_path: Path, cost_type: str) -> None:
        cfg = _pilot_config(
            cost={"type": cost_type},
            trials={
                "n_trials": 1,
                "min_output_separation": 0.05,
                "preimage_policy": "lex_min_node_id",
                "max_sample_attempts": 5000,
                "n_path_samples": 0,
            },
        )
        run = run_pilot(cfg, results_root=tmp_path, run_id=f"cost_{cost_type}")
        rows = run.read_jsonl("trials")
        assert rows
        for row in rows:
            assert row["cost_type"] == cost_type
            if row["algorithm"] == "dijkstra":
                assert row["heuristic_type"] == "zero"
            else:
                assert row["heuristic_type"] in (
                    "uniform_step",
                    "input_euclidean",
                    "output_euclidean",
                )
            if row["found"]:
                assert row["optimal_cost"] == row["cost"]
                assert row["path_length_u"] is not None

        # Dijkstra and A* agree on C* for the same objective.
        by_key: dict[tuple[int, str], dict[str, dict]] = {}
        for row in rows:
            key = (int(row["trial_index"]), str(row["mechanism"]))
            by_key.setdefault(key, {})[str(row["algorithm"])] = row
        for pair in by_key.values():
            d = pair.get("dijkstra")
            a = pair.get("astar")
            if d and a and d["found"] and a["found"]:
                assert a["optimal_cost"] == pytest.approx(
                    d["optimal_cost"], rel=0.0, abs=1e-9
                )

    def test_determinism_same_seed(self, tmp_path: Path) -> None:
        cfg = _pilot_config(seed=11)
        a = run_pilot(cfg, results_root=tmp_path, run_id="det_a")
        b = run_pilot(cfg, results_root=tmp_path, run_id="det_b")
        rows_a = a.read_jsonl("trials")
        rows_b = b.read_jsonl("trials")
        assert len(rows_a) == len(rows_b)
        for ra, rb in zip(rows_a, rows_b, strict=True):
            assert ra["trial_index"] == rb["trial_index"]
            assert ra["mechanism"] == rb["mechanism"]
            assert ra["algorithm"] == rb["algorithm"]
            assert ra["found"] == rb["found"]
            assert ra["n_expanded"] == rb["n_expanded"]
            assert ra["cost"] == rb["cost"]

    def test_astar_matches_dijkstra_cost_when_found(self, tmp_path: Path) -> None:
        cfg = _pilot_config(
            seed=3,
            trials={
                "n_trials": 5,
                "min_output_separation": 0.05,
                "preimage_policy": "lex_min_node_id",
                "max_sample_attempts": 5000,
            },
        )
        run = run_pilot(cfg, results_root=tmp_path, run_id="cost_check")
        by_key: dict[tuple[int, str], dict[str, dict]] = {}
        for row in run.read_jsonl("trials"):
            key = (int(row["trial_index"]), str(row["mechanism"]))
            by_key.setdefault(key, {})[str(row["algorithm"])] = row

        compared = 0
        for pair in by_key.values():
            d = pair.get("dijkstra")
            a = pair.get("astar")
            if d is None or a is None:
                continue
            if not (d["found"] and a["found"]):
                continue
            assert a["cost"] == pytest.approx(d["cost"], rel=0.0, abs=1e-9)
            compared += 1
        assert compared >= 1

    def test_unreachable_rows_preserved(self, tmp_path: Path) -> None:
        cfg = _pilot_config(seed=0)
        run = run_pilot(cfg, results_root=tmp_path, run_id="unreachable_check")
        rows = run.read_jsonl("trials")
        missing = [r for r in rows if not r["found"]]
        # Four-bar start/goal preimages are often disconnected on a coarse grid.
        if missing:
            assert all(r.get("failure_reason") for r in missing)
            assert any(r["failure_reason"] == "unreachable" for r in missing)
        summary = run.read_json("summary")
        assert summary["n_unreachable"] == len(missing)

    def test_population_mode_per_trial_lengths(self, tmp_path: Path) -> None:
        cfg = ExperimentConfig.model_validate(
            {
                "seed": 5,
                "mechanisms": {
                    "gearbox": UnitGearbox(dim=2).to_dict(),
                    "fourbar": {
                        "mode": "population",
                        "n_bars": 2,
                        "d": 1.0,
                        "length_low": 0.2,
                        "length_high": 2.0,
                        "n_crank_samples": 91,
                    },
                },
                "graph": {
                    "shape": [12, 12],
                    "wrap": [True, True],
                    "edge_samples": 5,
                },
                "cost": {"type": "output_euclidean"},
                "algorithms": {
                    "names": ["dijkstra", "astar"],
                    "validate_heuristic": False,
                },
                "trials": {
                    "n_trials": 2,
                    "min_output_separation": 0.05,
                    "preimage_policy": "lex_min_node_id",
                    "max_sample_attempts": 2000,
                    "require_reachable": True,
                },
            }
        )
        run = run_pilot(cfg, results_root=tmp_path, run_id="pop_smoke")
        assert run.status == "completed"
        rows = run.read_jsonl("trials")
        assert len(rows) == 8  # 2 trials × 2 mechanisms × 2 algorithms
        by_trial: dict[int, list[list[float]]] = {}
        for row in rows:
            assert row["fourbar_mode"] == "population"
            assert "fourbar_lengths" in row
            assert "limits" in row
            assert len(row["fourbar_lengths"]) == 2
            assert len(row["limits"]["lower"]) == 2
            by_trial.setdefault(int(row["trial_index"]), row["fourbar_lengths"])
        assert set(by_trial) == {0, 1}
        assert by_trial[0] != by_trial[1]
        meta = run.read_json("graph_meta")
        assert meta["fourbar_mode"] == "population"
        assert "fourbar_valid_nodes" not in meta

    def test_duplicate_run_id_rejected(self, tmp_path: Path) -> None:
        cfg = _pilot_config()
        run_pilot(cfg, results_root=tmp_path, run_id="dup")
        with pytest.raises(FileExistsError):
            run_pilot(cfg, results_root=tmp_path, run_id="dup")

    def test_completed_run_immutable(self, tmp_path: Path) -> None:
        cfg = _pilot_config()
        run_pilot(cfg, results_root=tmp_path, run_id="immutable")
        loaded = load_run("immutable", results_root=tmp_path)
        with pytest.raises(RunRegistryError, match="completed"):
            loaded.write_json("extra", {"x": 1})

    def test_figures_dir_copy(self, tmp_path: Path) -> None:
        cfg = _pilot_config()
        figs = tmp_path / "figs"
        run_pilot(
            cfg,
            results_root=tmp_path / "runs",
            run_id="figcopy",
            figures_dir=figs,
        )
        assert (figs / "expansions_raw.png").is_file()
        assert (figs / "expansions_normalized.png").is_file()
        assert (figs / "expansions_ratio.png").is_file()

    def test_register_output_rejects_missing(self, tmp_path: Path) -> None:
        cfg = _pilot_config()
        run = create_run(cfg, results_root=tmp_path, run_id="reg_missing")
        run.mark_running()
        with pytest.raises(FileNotFoundError):
            run.register_output("missing", "outputs/nope.png")
