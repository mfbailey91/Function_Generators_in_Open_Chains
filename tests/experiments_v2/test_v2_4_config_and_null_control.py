from __future__ import annotations

import json
from pathlib import Path

import pytest

from inequality_mechanisms.experiments.v2_config import (
    V2ConfigError,
    validate_v2_config_mapping,
)
from inequality_mechanisms.experiments.v2_runner import run_v2_experiment_from_path

_REPO = Path(__file__).resolve().parents[2]
_SMOKE = _REPO / "configs" / "v2" / "smoke.yaml"


def test_v2_rejects_v1_only_preimage_policy() -> None:
    raw = {
        "architecture_version": 2,
        "planning_space": "output",
        "tasks": {"preimage_policy": "lex_min_node_id"},
    }
    with pytest.raises(V2ConfigError, match="preimage_policy is Version 1-only"):
        validate_v2_config_mapping(raw)


def test_v2_null_control_hard_gate_matches_across_mechanisms(tmp_path: Path) -> None:
    # Hard gate: shared uniform-Q lattice + output-distance objective
    # must yield identical node IDs, costs, paths, and expansion order.
    res = run_v2_experiment_from_path(
        _SMOKE,
        results_root=tmp_path / "results",
        run_id="v2_smoke_test",
        write_figures=False,
    )

    trial_rows = []
    trials_path = res.path / "trials.jsonl"
    assert trials_path.is_file()
    for line in trials_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            trial_rows.append(json.loads(line))

    # With 1 requested task and 2 algorithms, each run produces:
    # 2 mechanisms × 2 algorithms = 4 rows.
    assert len(trial_rows) == 4

    by_mech_algo: dict[tuple[str, str], dict] = {}
    for row in trial_rows:
        by_mech_algo[(row["mechanism_id"], row["algorithm"])] = row

    mech_a = "fourbar"
    mech_b = "equivalent_affine_gearbox"

    for algorithm in ("dijkstra", "astar"):
        row_a = by_mech_algo[(mech_a, algorithm)]
        row_b = by_mech_algo[(mech_b, algorithm)]

        assert row_a["found"] == row_b["found"]
        assert row_a["start_node_id"] == row_b["start_node_id"]
        assert row_a["goal_node_id"] == row_b["goal_node_id"]
        assert row_a["optimal_cost"] == pytest.approx(
            row_b["optimal_cost"], rel=0.0, abs=1e-12
        )
        assert row_a["path_node_ids"] == row_b["path_node_ids"]
        assert row_a["expanded_node_ids"] == row_b["expanded_node_ids"]
        assert row_a["n_expanded"] == row_b["n_expanded"]
        assert row_a["n_generated"] == row_b["n_generated"]
        assert row_a["n_stale"] == row_b["n_stale"]
