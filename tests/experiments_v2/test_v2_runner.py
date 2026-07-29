"""Version 2 runner tests, including the null-control hard gate (V2-406..409)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from tests.experiments_v2._config_fixtures import base_v2_config_mapping

from inequality_mechanisms.experiments.v2_config import validate_v2_config_mapping
from inequality_mechanisms.experiments.v2_runner import (
    V2RunnerError,
    _assert_null_control_invariant,
    build_graphs,
    build_mechanism_branches,
    run_v2_experiment,
)
from inequality_mechanisms.search.result import SearchResult

_SMALL_SHAPE = [6, 6]
_EXPLICIT_PAIRS = [
    {"start_q": [1.5, 1.5], "goal_q": [2.0, 2.0]},
    {"start_q": [1.2, 2.0], "goal_q": [2.2, 1.3]},
]


def _config(**overrides: Any):
    data = base_v2_config_mapping()
    data["sampling"]["shape"] = list(_SMALL_SHAPE)
    data["tasks"]["pairs"] = [dict(p) for p in _EXPLICIT_PAIRS]
    data["tasks"]["output_tolerance"] = 0.5
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(data.get(key), dict):
            data[key].update(value)
        else:
            data[key] = value
    return validate_v2_config_mapping(data)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


class TestRunPackageLayout:
    def test_expected_files_and_dirs(self, tmp_path: Path) -> None:
        cfg = _config()
        result = run_v2_experiment(
            cfg, results_root=tmp_path, run_id="layout_run", write_figures=False
        )
        run_dir = result.path
        assert run_dir == (tmp_path / "layout_run").resolve()
        for name in (
            "config.yaml",
            "manifest.json",
            "trials.jsonl",
            "summary.csv",
            "failures.jsonl",
        ):
            assert (run_dir / name).is_file(), name
        for name in ("branches", "diagnostics", "figures"):
            assert (run_dir / name).is_dir(), name
        assert (run_dir / "branches" / "fourbar.json").is_file()
        assert (run_dir / "branches" / "equivalent_affine_gearbox.json").is_file()

        manifest = json.loads((run_dir / "manifest.json").read_text())
        assert manifest["architecture_version"] == 2
        assert manifest["result_schema_version"] == 2
        assert manifest["seed"] == cfg.seed
        assert "revision" in manifest
        assert "environment" in manifest
        assert "git_dirty" in manifest["revision"]

    def test_refuses_to_overwrite_existing_run(self, tmp_path: Path) -> None:
        cfg = _config()
        run_v2_experiment(
            cfg, results_root=tmp_path, run_id="dup_run", write_figures=False
        )
        with pytest.raises(FileExistsError):
            run_v2_experiment(
                cfg, results_root=tmp_path, run_id="dup_run", write_figures=False
            )

    def test_trial_rows_cover_both_mechanisms_and_algorithms(
        self, tmp_path: Path
    ) -> None:
        cfg = _config()
        result = run_v2_experiment(
            cfg, results_root=tmp_path, run_id="rows_run", write_figures=False
        )
        rows = _read_jsonl(result.path / "trials.jsonl")
        mechanisms = {row["mechanism_id"] for row in rows}
        algorithms = {row["algorithm"] for row in rows}
        assert mechanisms == {"fourbar", "equivalent_affine_gearbox"}
        assert algorithms == {"dijkstra", "astar"}
        # 2 tasks * 2 mechanisms * 2 algorithms.
        assert len(rows) == 2 * 2 * 2
        assert result.n_failure_rows == 0


class TestNullControlHardGate:
    """PROJECT_PLAN invariant 9 / Sprint V2.4 V2-409 hard gate."""

    @pytest.mark.parametrize("cost_name", ["output_euclidean", "uniform"])
    def test_matched_mechanisms_agree_exactly(
        self, tmp_path: Path, cost_name: str
    ) -> None:
        heuristic = (
            "output_euclidean" if cost_name == "output_euclidean" else "uniform_step"
        )
        cfg = _config(objective={"cost": cost_name, "heuristic": heuristic})
        result = run_v2_experiment(
            cfg,
            results_root=tmp_path,
            run_id=f"null_control_{cost_name}",
            write_figures=False,
        )
        rows = _read_jsonl(result.path / "trials.jsonl")
        assert result.n_failure_rows == 0

        by_key: dict[tuple[int, str], dict[str, dict[str, Any]]] = {}
        for row in rows:
            key = (row["trial_index"], row["algorithm"])
            by_key.setdefault(key, {})[row["mechanism_id"]] = row

        assert by_key, "expected at least one trial/algorithm combination"
        for (trial_index, algorithm), by_mechanism in by_key.items():
            assert set(by_mechanism) == {"fourbar", "equivalent_affine_gearbox"}
            fb = by_mechanism["fourbar"]
            gb = by_mechanism["equivalent_affine_gearbox"]
            assert fb["start_node_id"] == gb["start_node_id"], (trial_index, algorithm)
            assert fb["goal_node_id"] == gb["goal_node_id"], (trial_index, algorithm)
            assert fb["found"] == gb["found"], (trial_index, algorithm)
            assert fb["optimal_cost"] == pytest.approx(gb["optimal_cost"], abs=0.0), (
                trial_index,
                algorithm,
            )
            assert fb["path_node_ids"] == gb["path_node_ids"], (trial_index, algorithm)
            assert fb["n_expanded"] == gb["n_expanded"], (trial_index, algorithm)
            assert fb["n_generated"] == gb["n_generated"], (trial_index, algorithm)
            assert fb["n_stale"] == gb["n_stale"], (trial_index, algorithm)
            assert fb["expanded_node_ids"] == gb["expanded_node_ids"], (
                trial_index,
                algorithm,
            )
            # Shared uniform-Q lattice: identical q, generally different u.
            assert fb["realized_start_q"] == gb["realized_start_q"]
            assert fb["realized_goal_q"] == gb["realized_goal_q"]

    def test_dijkstra_and_astar_agree_on_cost_per_mechanism(
        self, tmp_path: Path
    ) -> None:
        cfg = _config(
            objective={"cost": "output_euclidean", "heuristic": "output_euclidean"}
        )
        result = run_v2_experiment(
            cfg,
            results_root=tmp_path,
            run_id="dijkstra_astar_agree",
            write_figures=False,
        )
        rows = _read_jsonl(result.path / "trials.jsonl")
        by_key: dict[tuple[int, str], dict[str, float]] = {}
        for row in rows:
            by_key.setdefault((row["trial_index"], row["mechanism_id"]), {})[
                row["algorithm"]
            ] = row["optimal_cost"]
        for key, costs in by_key.items():
            assert costs["dijkstra"] == pytest.approx(costs["astar"], abs=1e-9), key

    def test_helper_raises_on_synthetic_mismatch(self, tmp_path: Path) -> None:
        cfg = _config()
        good = SearchResult(
            found=True, path=(0, 1, 2), cost=1.0, n_expanded=3, n_generated=3, n_stale=0
        )
        bad = SearchResult(
            found=True, path=(0, 1, 3), cost=1.5, n_expanded=4, n_generated=4, n_stale=0
        )
        with pytest.raises(V2RunnerError):
            _assert_null_control_invariant(
                cfg,
                0,
                {
                    "fourbar": {"dijkstra": good},
                    "equivalent_affine_gearbox": {"dijkstra": bad},
                },
            )

    def test_helper_skips_non_null_control_cost(self, tmp_path: Path) -> None:
        cfg = _config(objective={"cost": "input_euclidean", "heuristic": "zero"})
        mismatched_a = SearchResult(
            found=True, path=(0, 1), cost=1.0, n_expanded=2, n_generated=2, n_stale=0
        )
        mismatched_b = SearchResult(
            found=True, path=(0, 2), cost=9.0, n_expanded=5, n_generated=5, n_stale=0
        )
        # input_euclidean is the deliberately mechanism-dependent cell of
        # the experimental matrix: must not be forced equal.
        _assert_null_control_invariant(
            cfg,
            0,
            {
                "fourbar": {"dijkstra": mismatched_a},
                "equivalent_affine_gearbox": {"dijkstra": mismatched_b},
            },
        )


class TestInputEuclideanNotForcedEqual:
    def test_run_completes_without_raising(self, tmp_path: Path) -> None:
        cfg = _config(objective={"cost": "input_euclidean", "heuristic": "zero"})
        result = run_v2_experiment(
            cfg,
            results_root=tmp_path,
            run_id="input_euclidean_run",
            write_figures=False,
        )
        assert result.n_trial_rows > 0


class TestSamplingDomains:
    def test_input_domain_builds_independent_graphs(self, tmp_path: Path) -> None:
        cfg = _config(sampling={"domain": "input", "shape": _SMALL_SHAPE})
        branches = build_mechanism_branches(cfg)
        graphs = build_graphs(cfg, branches)
        # Independent uniform-U sampling: same node count, generally
        # different q, and (for this crank-rocker vs its matched affine
        # gearbox) different achieved output ranges away from endpoints.
        fb_graph = graphs["fourbar"]
        gb_graph = graphs["equivalent_affine_gearbox"]
        assert fb_graph.q_nodes.shape == gb_graph.q_nodes.shape
        import numpy as np

        assert not np.array_equal(fb_graph.q_nodes, gb_graph.q_nodes)

    def test_output_domain_shares_q_nodes(self, tmp_path: Path) -> None:
        cfg = _config(sampling={"domain": "output", "shape": _SMALL_SHAPE})
        branches = build_mechanism_branches(cfg)
        graphs = build_graphs(cfg, branches)
        import numpy as np

        assert np.array_equal(
            graphs["fourbar"].q_nodes, graphs["equivalent_affine_gearbox"].q_nodes
        )


class TestFailureRecording:
    def test_out_of_range_task_is_rejected_and_recorded(self, tmp_path: Path) -> None:
        cfg = _config(
            tasks={
                "source": "fixed_output_pairs",
                "output_tolerance": 1e-6,
                "pairs": [{"start_q": [-50.0, -50.0], "goal_q": [2.0, 2.0]}],
            }
        )
        result = run_v2_experiment(
            cfg, results_root=tmp_path, run_id="failure_run", write_figures=False
        )
        failures = _read_jsonl(result.path / "failures.jsonl")
        assert len(failures) >= 1
        for row in failures:
            assert row["rejection_reason"] is not None
            assert row["output_tolerance"] == pytest.approx(1e-6)
