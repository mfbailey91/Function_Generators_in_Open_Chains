"""One mechanism-pair Dijkstra work unit (V2-904)."""

from __future__ import annotations

import time
from dataclasses import dataclass, replace
from typing import Any

import numpy as np

from inequality_mechanisms.experiments.v2_config import (
    FourBarLinkConfig,
    V2ExperimentConfig,
    V2MechanismsConfig,
    V2ObjectiveConfig,
    V2OutputPair,
    V2SamplingConfig,
    V2TasksConfig,
)
from inequality_mechanisms.experiments.v2_paired_metrics import compare_paired_rows
from inequality_mechanisms.experiments.v2_production_config import V2ProductionConfig
from inequality_mechanisms.experiments.v2_production_environment import peak_rss_bytes
from inequality_mechanisms.experiments.v2_production_sample_bank import (
    V2SampleBank,
    V2SampleBankMechanism,
)
from inequality_mechanisms.experiments.v2_runner import (
    FOURBAR_MECHANISM_ID,
    SPAN_MATCHED_GEARBOX_MECHANISM_ID,
    _path_metrics,
    build_graphs,
    build_mechanism_branches,
)
from inequality_mechanisms.experiments.v2_shared_q_fixtures import fractions_to_q
from inequality_mechanisms.experiments.v2_tasks import OutputTask
from inequality_mechanisms.graphs.pair_invariants import (
    SharedQPairInvariantError,
    assert_identical_query_overlays,
    assert_shared_q_pair_invariants,
)
from inequality_mechanisms.graphs.query_overlay import QueryOverlayGraph
from inequality_mechanisms.search.graph_solver import production_dijkstra_solver
from inequality_mechanisms.search.v2_objectives import (
    pair_box_scales,
    resolve_v2_objective,
)


@dataclass(frozen=True, slots=True)
class MechanismPairWorkResult:
    """Deterministic output of one mechanism-pair work unit."""

    mechanism_pair_id: str
    status: str
    summary: dict[str, Any]
    trials: list[dict[str, Any]]
    comparisons: list[dict[str, Any]]
    failures: list[dict[str, Any]]

    def to_jsonl_records(self) -> list[dict[str, Any]]:
        records = [
            {"record_type": "mechanism_summary", **self.summary, "status": self.status}
        ]
        records.extend({"record_type": "trial", **row} for row in self.trials)
        records.extend(
            {"record_type": "pair_comparison", **row} for row in self.comparisons
        )
        records.extend({"record_type": "failure", **row} for row in self.failures)
        return records


def _pair_experiment_config(
    config: V2ProductionConfig,
    mechanism: V2SampleBankMechanism,
    *,
    shape: tuple[int, ...],
) -> V2ExperimentConfig:
    fourbars = [FourBarLinkConfig.model_validate(fb) for fb in mechanism.fourbars]
    return V2ExperimentConfig(
        architecture_version=2,
        result_schema_version=2,
        planning_space="output",
        mechanisms=V2MechanismsConfig(
            comparison="fourbar_vs_equivalent_affine_gearbox",
            dim=2,
            fourbar=fourbars[0],
            fourbars=fourbars,
            matching_rule=config.matching_rule,
            gearbox_mechanism_id="span_matched_gearbox",
        ),
        branch=config.branch,
        sampling=V2SamplingConfig(
            domain="output",
            shape=list(shape),
            include_endpoints=True,
        ),
        objective=V2ObjectiveConfig(cost="actuator_travel", heuristic="zero"),
        edge_validation=config.edge_validation,
        tasks=V2TasksConfig(
            source="fixed_output_pairs",
            output_tolerance=config.tasks_output_tolerance,
            use_query_overlays=True,
            pairs=[V2OutputPair(start_q=[0.0, 0.0], goal_q=[1.0, 1.0])],
        ),
        algorithms=["dijkstra"],
        seed=config.seed,
        trials=1,
    )


def _analysis_side(mechanism_id: str) -> str:
    if mechanism_id == FOURBAR_MECHANISM_ID:
        return "fourbar"
    return "gearbox"


def run_mechanism_pair_work_unit(
    config: V2ProductionConfig,
    bank: V2SampleBank,
    mechanism: V2SampleBankMechanism,
    *,
    run_id: str,
    shape: tuple[int, ...] | None = None,
    retain_paths: bool = False,
    code_revision: str | None = None,
) -> MechanismPairWorkResult:
    """Execute all bank tasks serially for one mechanism pair under Dijkstra."""
    graph_shape = tuple(int(x) for x in (shape or tuple(config.sampling.shape)))
    solver = production_dijkstra_solver()
    exp_cfg = _pair_experiment_config(config, mechanism, shape=graph_shape)
    t0 = time.perf_counter()
    try:
        branches = build_mechanism_branches(exp_cfg)
        graphs = build_graphs(exp_cfg, branches)
        shared_valid = np.asarray(
            np.logical_and.reduce([g.valid_nodes for g in graphs.values()]),
            dtype=np.bool_,
        )
        graphs = {
            mid: replace(g, valid_nodes=shared_valid.copy())
            for mid, g in graphs.items()
        }
        g_fb = graphs[FOURBAR_MECHANISM_ID]
        inv = assert_shared_q_pair_invariants(
            g_fb,
            graphs[SPAN_MATCHED_GEARBOX_MECHANISM_ID],
            residual_tol=config.branch.inverse_tolerance,
            edge_n_samples=config.edge_validation.samples,
            raise_on_failure=True,
        )
    except (SharedQPairInvariantError, ValueError, TypeError) as exc:
        failure = {
            "run_id": run_id,
            "mechanism_pair_id": mechanism.mechanism_id,
            "failure_code": "pair_invariant_or_build_failed",
            "detail": str(exc),
            "solver_id": solver.solver_id,
        }
        return MechanismPairWorkResult(
            mechanism_pair_id=mechanism.mechanism_id,
            status="failed",
            summary={
                "run_id": run_id,
                "mechanism_pair_id": mechanism.mechanism_id,
                "sample_bank_digest": bank.digest,
                "solver_id": solver.solver_id,
                "failure_code": "pair_invariant_or_build_failed",
                "detail": str(exc),
                "runtime_s": float(time.perf_counter() - t0),
                "peak_rss_bytes": peak_rss_bytes(),
            },
            trials=[],
            comparisons=[],
            failures=[failure],
        )

    cert = branches[FOURBAR_MECHANISM_ID].certificate
    s_q, s_u = pair_box_scales(
        np.asarray(cert.output_lower, dtype=np.float64),
        np.asarray(cert.output_upper, dtype=np.float64),
        np.asarray(cert.input_lower, dtype=np.float64),
        np.asarray(cert.input_upper, dtype=np.float64),
    )
    u_span = float(
        np.linalg.norm(
            np.asarray(cert.input_upper, dtype=np.float64)
            - np.asarray(cert.input_lower, dtype=np.float64)
        )
    )
    graph_id = f"{mechanism.mechanism_id}:output:{graph_shape[0]}x{graph_shape[1]}"
    trials: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []
    trial_index = 0

    for task in bank.tasks:
        start_q = fractions_to_q(
            cert.output_lower, cert.output_upper, task.start_fraction
        )
        goal_q = fractions_to_q(
            cert.output_lower, cert.output_upper, task.goal_fraction
        )
        requested = OutputTask(
            np.asarray(start_q, dtype=np.float64),
            np.asarray(goal_q, dtype=np.float64),
        )
        overlays: dict[str, QueryOverlayGraph] = {}
        try:
            for mid, base_graph in graphs.items():
                overlays[mid] = QueryOverlayGraph(
                    base=base_graph,
                    start_q=requested.requested_start_q,
                    goal_q=requested.requested_goal_q,
                    edge_n_samples=config.edge_validation.samples,
                )
            assert_identical_query_overlays(
                overlays[FOURBAR_MECHANISM_ID],
                overlays[SPAN_MATCHED_GEARBOX_MECHANISM_ID],
                raise_on_failure=True,
            )
        except (SharedQPairInvariantError, ValueError) as exc:
            for mid in graphs:
                failures.append(
                    {
                        "run_id": run_id,
                        "trial_index": trial_index,
                        "mechanism_pair_id": mechanism.mechanism_id,
                        "mechanism_id": mid,
                        "task_id": task.task_id,
                        "failure_code": "task_overlay_failed",
                        "detail": str(exc),
                        "requested_start_q": list(requested.requested_start_q),
                        "requested_goal_q": list(requested.requested_goal_q),
                    }
                )
                trial_index += 1
            continue

        task_rows: dict[str, dict[str, Any]] = {}
        for mid, branch in branches.items():
            graph = overlays[mid]
            start_id = graph.start_node_id
            goal_id = graph.goal_node_id
            objective = resolve_v2_objective(
                graph,  # type: ignore[arg-type]
                goal_id,
                "actuator_travel",
                "zero",
            )
            search_t0 = time.perf_counter()
            result = solver.solve(graph, start_id, goal_id, objective)
            runtime_s = float(time.perf_counter() - search_t0)
            length_u, length_q, length_x = _path_metrics(branch, graph, result.path)
            valid_count = int(np.sum(graph.valid_nodes))
            reachable = valid_count
            expansion_fraction = (
                float(result.n_expanded) / float(reachable) if reachable else None
            )
            cost_norm_u = (
                float(result.cost) / u_span if result.found and u_span > 0.0 else None
            )
            row = {
                "architecture_version": 2,
                "result_schema_version": 2,
                "production_schema_version": 1,
                "run_id": run_id,
                "trial_index": trial_index,
                "sample_bank_version": bank.schema_version,
                "sample_bank_digest": bank.digest,
                "mechanism_pair_id": mechanism.mechanism_id,
                "mechanism_id": mid,
                "mechanism": _analysis_side(mid),
                "task_id": task.task_id,
                "task_category": task.category,
                "graph_id": graph_id,
                "graph_shape": list(graph_shape),
                "solver_id": solver.solver_id,
                "solver_schema_version": solver.solver_schema_version,
                "heuristic_id": solver.heuristic_id,
                "objective_id": "actuator_travel",
                "objective_parameters": {},
                "cost_type": "actuator_travel",
                "algorithm": "dijkstra",
                "start_q": list(map(float, requested.requested_start_q)),
                "goal_q": list(map(float, requested.requested_goal_q)),
                "requested_start_q": list(map(float, requested.requested_start_q)),
                "requested_goal_q": list(map(float, requested.requested_goal_q)),
                "start_u": [float(x) for x in graph.u_state(start_id)],
                "goal_u": [float(x) for x in graph.u_state(goal_id)],
                "start_node_id": int(start_id),
                "goal_node_id": int(goal_id),
                "graph_invariant_status": "passed" if inv.passed else "failed",
                "task_feasibility_status": "ok" if result.found else "unreachable",
                "found": bool(result.found),
                "n_expanded": int(result.n_expanded),
                "n_generated": int(result.n_generated),
                "n_reopened": 0,
                "n_stale": int(result.n_stale),
                "reachable_node_count": reachable,
                "valid_node_count": valid_count,
                "expansion_fraction": expansion_fraction,
                "optimal_cost": float(result.cost) if result.found else None,
                "cost_norm_u": cost_norm_u,
                "s_q": s_q,
                "s_u": s_u,
                "path_node_count": len(result.path) if result.found else 0,
                "path_edge_count": int(result.n_path_edges),
                "n_path_edges": int(result.n_path_edges),
                "path_length_u": length_u if result.found else None,
                "path_length_q": length_q if result.found else None,
                "path_length_x": length_x if result.found else None,
                "runtime_s": runtime_s,
                "peak_rss_bytes": peak_rss_bytes(),
                "path_node_ids": (
                    [int(n) for n in result.path]
                    if retain_paths and result.found
                    else []
                ),
                "seed": int(config.seed),
                "code_revision": code_revision,
                "exclusion_code": None,
                "failure_code": None if result.found else "unreachable",
            }
            trials.append(row)
            task_rows[mid] = row
            trial_index += 1

        if (
            FOURBAR_MECHANISM_ID in task_rows
            and SPAN_MATCHED_GEARBOX_MECHANISM_ID in task_rows
        ):
            comparisons.append(
                {
                    "mechanism_pair_id": mechanism.mechanism_id,
                    "task_id": task.task_id,
                    **compare_paired_rows(
                        task_rows[FOURBAR_MECHANISM_ID],
                        task_rows[SPAN_MATCHED_GEARBOX_MECHANISM_ID],
                    ),
                }
            )

    runtime_s = float(time.perf_counter() - t0)
    status = "completed" if not failures or trials else "failed"
    if failures and not trials:
        status = "failed"
    elif failures:
        status = "completed_with_task_failures"
    summary = {
        "run_id": run_id,
        "mechanism_pair_id": mechanism.mechanism_id,
        "sample_bank_version": bank.schema_version,
        "sample_bank_digest": bank.digest,
        "solver_id": solver.solver_id,
        "solver_schema_version": solver.solver_schema_version,
        "heuristic_id": solver.heuristic_id,
        "objective_id": "actuator_travel",
        "graph_id": graph_id,
        "graph_shape": list(graph_shape),
        "n_tasks": len(bank.tasks),
        "n_trials": len(trials),
        "n_failures": len(failures),
        "n_comparisons": len(comparisons),
        "graph_invariant_status": "passed",
        "invariant_report": inv.to_dict(),
        "descriptors": dict(mechanism.descriptors),
        "runtime_s": runtime_s,
        "peak_rss_bytes": peak_rss_bytes(),
        "code_revision": code_revision,
    }
    del graphs, branches
    return MechanismPairWorkResult(
        mechanism_pair_id=mechanism.mechanism_id,
        status=status,
        summary=summary,
        trials=trials,
        comparisons=comparisons,
        failures=failures,
    )
