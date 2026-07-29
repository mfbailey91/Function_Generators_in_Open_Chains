from __future__ import annotations

import json
from pathlib import Path

from inequality_mechanisms.experiments.v2_config import (
    validate_v2_config_mapping,
)
from inequality_mechanisms.experiments.v2_runner import (
    FOURBAR_MECHANISM_ID,
    GEARBOX_MECHANISM_ID,
    build_graphs,
    build_mechanism_branches,
    run_v2_experiment,
)


def _read_trials_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def test_runner_uses_query_overlays_for_exact_q_endpoints(tmp_path: Path) -> None:
    # Use a uniform-Q lattice so base node ids are comparable across
    # mechanisms, then pick query q values that are midpoints between
    # adjacent lattice nodes (so they are *not* deduplicated).
    base_mapping = {
        "architecture_version": 2,
        "result_schema_version": 2,
        "planning_space": "output",
        "seed": 123,
        "trials": 1,
        "mechanisms": {"comparison": "fourbar_vs_equivalent_affine_gearbox", "dim": 2},
        "branch": {
            "selection": "monotonic_interval",
            "certification_samples_per_axis": 9,
            "minimum_abs_gain": 0.05,
            "inverse_tolerance": 1.0e-6,
            "endpoint_margin_fraction": 0.02,
            "n_samples": 64,
            "min_u_width": 0.3,
            "table_samples_per_axis": 17,
        },
        "sampling": {"domain": "output", "shape": [6, 6], "include_endpoints": True},
        "objective": {"cost": "actuator_travel", "heuristic": None},
        "edge_validation": {"samples": 17},
        "tasks": {
            "source": "fixed_output_pairs",
            "output_tolerance": 1e-6,
            "use_query_overlays": True,
            "pairs": [
                {"start_q": [0.0, 0.0], "goal_q": [1.0, 1.0]},
            ],
        },
        "algorithms": ["dijkstra"],
    }

    cfg = validate_v2_config_mapping(base_mapping)
    mechanism_branches = build_mechanism_branches(cfg)
    graphs = build_graphs(cfg, mechanism_branches)
    base_graph = graphs[FOURBAR_MECHANISM_ID]
    base_node_count = base_graph.node_count

    axis0 = base_graph.axis_marginal(base_graph.q_nodes, 0)
    axis1 = base_graph.axis_marginal(base_graph.q_nodes, 1)

    # Midpoints between adjacent lattice nodes on each axis.
    s0 = 0.5 * (float(axis0[1]) + float(axis0[2]))
    s1 = 0.5 * (float(axis1[1]) + float(axis1[2]))
    g0 = 0.5 * (float(axis0[3]) + float(axis0[4]))
    g1 = 0.5 * (float(axis1[3]) + float(axis1[4]))

    cfg_mapping = base_mapping
    cfg_mapping["tasks"] = dict(base_mapping["tasks"])
    cfg_mapping["tasks"]["pairs"] = [{"start_q": [s0, s1], "goal_q": [g0, g1]}]

    cfg2 = validate_v2_config_mapping(cfg_mapping)
    res = run_v2_experiment(
        cfg2, results_root=tmp_path / "results", run_id="v2_6_overlay_test"
    )

    trials_path = res.path / "trials.jsonl"
    assert trials_path.is_file()
    rows = _read_trials_jsonl(trials_path)
    assert len(rows) == 2  # 2 mechanisms × 1 algorithm × 1 task

    by_mech = {(r["mechanism_id"], r["algorithm"]): r for r in rows}
    for mech_id in (FOURBAR_MECHANISM_ID, GEARBOX_MECHANISM_ID):
        row = by_mech[(mech_id, "dijkstra")]
        assert row["start_node_id"] == base_node_count
        assert row["goal_node_id"] == base_node_count + 1
        assert row["start_residual_norm"] <= cfg2.tasks.output_tolerance
        assert row["goal_residual_norm"] <= cfg2.tasks.output_tolerance
        assert row["start_residual_norm"] < 1e-8
        assert row["goal_residual_norm"] < 1e-8
        assert row["path_node_ids"][0] == row["start_node_id"]
        assert row["path_node_ids"][-1] == row["goal_node_id"]

