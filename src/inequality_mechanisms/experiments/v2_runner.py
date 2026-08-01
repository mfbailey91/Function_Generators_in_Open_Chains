"""Version 2 experiment runner (Sprint V2.4, V2-406/V2-407/V2-409).

Sequence (per the sprint): load/validate config -> construct the certified
mechanism pair -> select and certify operating branches -> construct the
matched affine gearbox branch -> construct the requested graph(s) -> resolve
fixed output tasks -> resolve the objective/heuristic -> run Dijkstra and/or
A* -> compute U/Q/X path metrics -> write an immutable run package.

This module never loads or dispatches Version 1 configs
(``experiments/config.py`` / ``experiments/pilot.py`` remain untouched and
unimported here): :func:`load_v2_experiment_config` already rejects any
mapping that is not a strict Version 2 config (ADR-016).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from inequality_mechanisms.experiments.registry import (
    capture_environment,
    capture_revision,
    default_results_root,
    generate_run_id,
    validate_run_id,
)
from inequality_mechanisms.experiments.v2_canvas import write_v2_canvas
from inequality_mechanisms.experiments.v2_config import (
    V2ExperimentConfig,
    load_v2_experiment_config,
    v2_experiment_config_to_yaml,
)
from inequality_mechanisms.experiments.v2_results import (
    RESULT_SCHEMA_VERSION_V2,
    V2_RESULT_FIELDS,
    V2FailureRow,
    V2ResultRow,
    rows_to_csv,
    rows_to_jsonl,
)
from inequality_mechanisms.experiments.v2_tasks import (
    OutputTask,
    TaskRejectionReason,
    generate_random_output_tasks,
    resolve_output_task,
)
from inequality_mechanisms.graphs.embedded import (
    EmbeddedPlanningGraph,
    UniformOutputLattice,
)
from inequality_mechanisms.graphs.query_overlay import QueryOverlayGraph
from inequality_mechanisms.graphs.pair_invariants import assert_shared_q_pair_invariants
from inequality_mechanisms.kinematics import Planar2R
from inequality_mechanisms.mechanisms.branch_selection import (
    select_fourbar_monotonic_branch,
)
from inequality_mechanisms.mechanisms.fourbar import IndependentFourBars, PlanarFourBar
from inequality_mechanisms.mechanisms.operating_branch import (
    OperatingBranch,
    equivalent_gearbox_branch,
)
from inequality_mechanisms.search.core import best_first_search
from inequality_mechanisms.search.result import SearchResult
from inequality_mechanisms.search.v2_objectives import (
    pair_box_scales,
    path_q_u_blend_components,
    resolve_v2_objective,
)

FOURBAR_MECHANISM_ID = "fourbar"
GEARBOX_MECHANISM_ID = "equivalent_affine_gearbox"
SPAN_MATCHED_GEARBOX_MECHANISM_ID = "span_matched_gearbox"
_GEARBOX_IDS = frozenset({GEARBOX_MECHANISM_ID, SPAN_MATCHED_GEARBOX_MECHANISM_ID})

_NULL_CONTROL_COSTS: frozenset[str] = frozenset(
    {"uniform", "output_euclidean", "q_u_blend"}
)


class V2RunnerError(RuntimeError):
    """Raised for Version 2 runner failures, including invariant violations."""


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class V2RunResult:
    """Handle summarizing one written Version 2 run package.

    Attributes
    ----------
    run_id :
        Directory name under ``results_root``.
    path :
        Absolute path to the run directory.
    mechanism_ids :
        The two compared mechanism identifiers.
    n_tasks :
        Number of requested output tasks (shared across mechanisms).
    n_trial_rows :
        Number of accepted (mechanism, task, algorithm) trial rows written.
    n_failure_rows :
        Number of rejected (mechanism, task) failure rows written.
    """

    run_id: str
    path: Path
    mechanism_ids: tuple[str, str]
    n_tasks: int
    n_trial_rows: int
    n_failure_rows: int


def build_mechanism_branches(
    config: V2ExperimentConfig,
) -> dict[str, OperatingBranch]:
    """Construct the certified four-bar branch and its matched affine gearbox.

    Implements ``mechanisms.comparison: fourbar_vs_equivalent_affine_gearbox``,
    the only comparison Version 2.4 supports: ``config.mechanisms.dim``
    independent crank-rockers from ``fourbars`` (or replicated ``fourbar``), a
    monotonic operating branch selected per ``config.branch``, and an
    endpoint-matched
    :class:`~inequality_mechanisms.mechanisms.gearbox.EquivalentGearbox`
    branch sharing the four-bar's certified output chart (the null-control
    pair, ADR-014/ADR-015). The gearbox mechanism id defaults to
    ``equivalent_affine_gearbox`` and may be set to ``span_matched_gearbox``
    (ADR-017 / Sprint V2.8).
    """
    mech_cfg = config.mechanisms
    branch_cfg = config.branch
    bars = [
        PlanarFourBar(
            a=fb.a,
            b=fb.b,
            c=fb.c,
            d=fb.d,
            branch=fb.branch,
            name=f"bar{i}",
        )
        for i, fb in enumerate(mech_cfg.resolved_fourbars())
    ]
    gearbox_id = str(mech_cfg.gearbox_mechanism_id)
    fourbar_mech = IndependentFourBars(bars, name=FOURBAR_MECHANISM_ID)
    fourbar_branch = select_fourbar_monotonic_branch(
        fourbar_mech,
        n_samples=branch_cfg.n_samples,
        min_abs_gain=branch_cfg.minimum_abs_gain,
        min_u_width=branch_cfg.min_u_width,
        endpoint_margin_fraction=branch_cfg.endpoint_margin_fraction,
        table_samples_per_axis=branch_cfg.table_samples_per_axis,
        certification_samples_per_axis=branch_cfg.certification_samples_per_axis,
        max_abs_gain=branch_cfg.max_abs_gain,
        residual_tol=branch_cfg.inverse_tolerance,
        name=FOURBAR_MECHANISM_ID,
    )
    gearbox_branch = equivalent_gearbox_branch(
        fourbar_branch,
        matching_rule=mech_cfg.matching_rule,
        name=gearbox_id,
        certification_samples_per_axis=branch_cfg.certification_samples_per_axis,
        min_abs_gain=branch_cfg.minimum_abs_gain,
        residual_tol=branch_cfg.inverse_tolerance,
    )
    return {
        FOURBAR_MECHANISM_ID: fourbar_branch,
        gearbox_id: gearbox_branch,
    }


def build_graphs(
    config: V2ExperimentConfig, mechanism_branches: dict[str, OperatingBranch]
) -> dict[str, EmbeddedPlanningGraph]:
    """Build one embedded planning graph per mechanism.

    ``sampling.domain: input`` samples each branch's actuator box
    independently (mechanism-specific ``Q`` lattices). ``sampling.domain:
    output`` builds one shared :class:`UniformOutputLattice` from the
    reference (four-bar) branch's certified output chart and attaches each
    mechanism's actuator realization on top of the *same* ``q`` array
    (V2-306 null control): this is the shared-uniform-``Q`` configuration
    the hard-gate test exercises.

    Raises
    ------
    ValueError
        If ``sampling.shape`` does not match the branch dimension, or (for
        ``domain: output``) the two branches do not share an output
        dimension.
    """
    shape = tuple(int(n) for n in config.sampling.shape)
    graphs: dict[str, EmbeddedPlanningGraph] = {}

    if config.sampling.domain == "input":
        for mechanism_id, branch in mechanism_branches.items():
            if len(shape) != branch.mechanism.input_dim:
                raise ValueError(
                    f"sampling.shape length {len(shape)} must match "
                    f"{mechanism_id} branch input_dim "
                    f"{branch.mechanism.input_dim}"
                )
            graphs[mechanism_id] = EmbeddedPlanningGraph.from_uniform_input(
                branch, shape
            )
        return graphs

    # domain == "output": shared uniform-Q lattice (V2-306).
    reference_id, reference_branch = next(iter(mechanism_branches.items()))
    for mechanism_id, branch in mechanism_branches.items():
        if branch.output_space.dim != reference_branch.output_space.dim:
            raise ValueError(
                "branch output_space dimensions must match for shared "
                f"uniform-Q sampling: {reference_id}="
                f"{reference_branch.output_space.dim}, {mechanism_id}="
                f"{branch.output_space.dim}"
            )
    if len(shape) != reference_branch.output_space.dim:
        raise ValueError(
            f"sampling.shape length {len(shape)} must match branch "
            f"output_dim {reference_branch.output_space.dim}"
        )
    shared = UniformOutputLattice.from_output_space(
        reference_branch.output_space, shape
    )
    for mechanism_id, branch in mechanism_branches.items():
        graphs[mechanism_id] = EmbeddedPlanningGraph.from_output_lattice(shared, branch)
    return graphs


def _resolve_tasks(
    config: V2ExperimentConfig, reference_output_space: Any
) -> list[OutputTask]:
    if config.tasks.pairs:
        return [
            OutputTask(
                np.asarray(pair.start_q, dtype=np.float64),
                np.asarray(pair.goal_q, dtype=np.float64),
            )
            for pair in config.tasks.pairs
        ]
    rng = np.random.default_rng(config.seed)
    return generate_random_output_tasks(
        lower=reference_output_space.lower,
        upper=reference_output_space.upper,
        n_tasks=config.trials,
        rng=rng,
    )


def _path_metrics(
    branch: OperatingBranch,
    graph: EmbeddedPlanningGraph | QueryOverlayGraph,
    path: tuple[int, ...],
) -> tuple[float, float, float | None]:
    """Return ``(path_length_u, path_length_q, path_length_x)`` for a node path.

    ``path_length_x`` uses planar-2R forward kinematics and is only defined
    for ``output_dim == 2`` (Sprint V2.4 non-goal: no 3R); ``None`` records
    that it is out of scope rather than silently reporting zero.
    """
    output_space = graph.branch.output_space
    if len(path) < 2:
        length_x0 = 0.0 if branch.mechanism.output_dim == 2 else None
        return 0.0, 0.0, length_x0

    length_u = 0.0
    length_q = 0.0
    for a, b in zip(path[:-1], path[1:]):
        length_u += float(np.linalg.norm(graph.u_state(b) - graph.u_state(a)))
        length_q += output_space.distance(graph.q_state(a), graph.q_state(b))

    length_x: float | None
    if branch.mechanism.output_dim == 2:
        fk = Planar2R()
        x_samples = np.vstack([fk.forward(graph.q_state(n)) for n in path])
        length_x = float(np.sum(np.linalg.norm(np.diff(x_samples, axis=0), axis=1)))
    else:
        length_x = None
    return length_u, length_q, length_x


def _assert_null_control_invariant(
    config: V2ExperimentConfig,
    trial_index: int,
    per_mechanism_results: dict[str, dict[str, SearchResult]],
) -> None:
    """Enforce the shared uniform-Q null-control hard gate at run time.

    Only applies when sampling is uniform-``Q`` (shared lattice) and the
    edge cost is a pure function of ``q`` (``uniform``, ``output_euclidean``,
    or ``q_u_blend`` with ``alpha == 1``). Mechanism-dependent actuator
    metrics must *not* be forced equal.
    """
    cost = config.objective.cost
    if cost not in _NULL_CONTROL_COSTS:
        return
    if cost == "q_u_blend" and float(config.objective.alpha or 0.0) != 1.0:
        return
    if len(per_mechanism_results) != 2:
        return
    (mech_a, algos_a), (mech_b, algos_b) = per_mechanism_results.items()
    for algorithm, result_a in algos_a.items():
        result_b = algos_b[algorithm]
        mismatch = (
            result_a.found != result_b.found
            or result_a.path != result_b.path
            or result_a.cost != result_b.cost
            or result_a.n_expanded != result_b.n_expanded
            or result_a.n_generated != result_b.n_generated
            or result_a.n_stale != result_b.n_stale
            or result_a.expanded_nodes != result_b.expanded_nodes
        )
        if mismatch:
            raise V2RunnerError(
                "shared uniform-Q null-control invariant violated at trial "
                f"{trial_index}, algorithm {algorithm!r}: "
                f"{mech_a} vs {mech_b} disagree "
                f"(found={result_a.found}/{result_b.found}, "
                f"cost={result_a.cost}/{result_b.cost}, "
                f"path={result_a.path}/{result_b.path}, "
                f"n_expanded={result_a.n_expanded}/{result_b.n_expanded})"
            )


def _objective_scales(
    config: V2ExperimentConfig, reference_branch: OperatingBranch
) -> tuple[float | None, float | None, float | None]:
    """Return ``(alpha, s_q, s_u)`` for the configured objective."""
    if config.objective.cost != "q_u_blend":
        return None, None, None
    cert = reference_branch.certificate
    s_q, s_u = pair_box_scales(
        np.asarray(cert.output_lower, dtype=np.float64),
        np.asarray(cert.output_upper, dtype=np.float64),
        np.asarray(cert.input_lower, dtype=np.float64),
        np.asarray(cert.input_upper, dtype=np.float64),
    )
    return float(config.objective.alpha), s_q, s_u


def _write_run_package(
    run_dir: Path,
    *,
    run_id: str,
    config: V2ExperimentConfig,
    config_yaml_text: str,
    revision: dict[str, Any],
    environment: dict[str, Any],
    mechanism_branches: dict[str, OperatingBranch],
    graphs: dict[str, EmbeddedPlanningGraph],
    trial_rows: list[dict[str, Any]],
    failure_rows: list[dict[str, Any]],
    write_figures: bool,
) -> None:
    if run_dir.exists():
        raise FileExistsError(f"run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True)
    (run_dir / "branches").mkdir()
    (run_dir / "diagnostics").mkdir()
    (run_dir / "figures").mkdir()

    (run_dir / "config.yaml").write_text(config_yaml_text, encoding="utf-8")

    manifest: dict[str, Any] = {
        "run_id": run_id,
        "architecture_version": 2,
        "result_schema_version": RESULT_SCHEMA_VERSION_V2,
        "seed": config.seed,
        "trials_requested": config.trials,
        "mechanisms": {
            mechanism_id: {"branch_id": branch.branch_id}
            for mechanism_id, branch in mechanism_branches.items()
        },
        "sampling_domain": config.sampling.domain,
        "objective": {
            "cost": config.objective.cost,
            "heuristic": config.objective.resolved_heuristic(),
        },
        "algorithms": list(config.algorithms),
        "n_trial_rows": len(trial_rows),
        "n_failure_rows": len(failure_rows),
        "created_at": _utc_now_iso(),
        "revision": revision,
        "environment": environment,
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    (run_dir / "trials.jsonl").write_text(rows_to_jsonl(trial_rows), encoding="utf-8")
    (run_dir / "failures.jsonl").write_text(
        rows_to_jsonl(failure_rows), encoding="utf-8"
    )
    (run_dir / "summary.csv").write_text(
        rows_to_csv(trial_rows, fields=V2_RESULT_FIELDS), encoding="utf-8"
    )

    for mechanism_id, branch in mechanism_branches.items():
        payload = branch.to_dict()
        (run_dir / "branches" / f"{mechanism_id}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    for mechanism_id, graph in graphs.items():
        dim = len(graph.topology.shape)
        diag = {
            "mechanism_id": mechanism_id,
            "sampling_domain": graph.sampling_domain.value,
            "transition_parameterization": graph.transition_parameterization.value,
            "graph_shape": list(graph.topology.shape),
            "node_count": graph.node_count,
            "valid_node_count": int(np.sum(graph.valid_nodes)),
            "q_spacing_summary": [
                graph.output_axis_spacing(axis).to_dict() for axis in range(dim)
            ],
            "u_spacing_summary": [
                graph.actuator_axis_spacing(axis).to_dict() for axis in range(dim)
            ],
        }
        (run_dir / "diagnostics" / f"{mechanism_id}.json").write_text(
            json.dumps(diag, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    if write_figures:
        try:
            from inequality_mechanisms.visualization.embedded_graphs import (
                plot_actuator_samples,
                plot_output_graph,
            )
        except ImportError:
            pass
        else:
            for mechanism_id, graph in graphs.items():
                if len(graph.topology.shape) not in (1, 2):
                    continue
                plot_output_graph(graph, run_dir / "figures" / f"{mechanism_id}_q.png")
                plot_actuator_samples(
                    graph, run_dir / "figures" / f"{mechanism_id}_u.png"
                )

    # Derived HTML printout (does not mutate trials.jsonl).
    write_v2_canvas(run_dir)


def run_v2_experiment(
    config: V2ExperimentConfig,
    *,
    results_root: Path | str | None = None,
    run_id: str | None = None,
    write_figures: bool = True,
) -> V2RunResult:
    """Run the full Version 2 pipeline and write an immutable run package.

    Parameters
    ----------
    config :
        Already-validated :class:`V2ExperimentConfig`.
    results_root :
        Parent directory for run folders. Defaults to the repository
        ``results/`` directory.
    run_id :
        Optional explicit run id; otherwise a fresh one is generated. The
        run directory must not already exist (immutability).
    write_figures :
        Best-effort ``figures/`` PNGs (skipped without raising if
        matplotlib is unavailable).

    Returns
    -------
    V2RunResult

    Raises
    ------
    FileExistsError
        If the run directory already exists.
    V2RunnerError
        If the shared uniform-Q null-control invariant is violated (a
        defect, not an expected experimental outcome).
    """
    root = Path(results_root) if results_root is not None else default_results_root()
    root.mkdir(parents=True, exist_ok=True)
    rid = (
        validate_run_id(run_id)
        if run_id is not None
        else generate_run_id(seed=config.seed)
    )
    run_dir = root / rid
    if run_dir.exists():
        raise FileExistsError(f"run directory already exists: {run_dir}")

    revision = capture_revision(cwd=None)
    environment = capture_environment()
    code_revision = revision.get("git_commit")

    mechanism_branches = build_mechanism_branches(config)
    graphs = build_graphs(config, mechanism_branches)
    if config.sampling.domain == "output" and len(graphs) == 2:
        g_a, g_b = list(graphs.values())
        assert_shared_q_pair_invariants(
            g_a,
            g_b,
            residual_tol=config.branch.inverse_tolerance,
            edge_n_samples=config.edge_validation.samples,
            raise_on_failure=True,
        )
    reference_branch = next(iter(mechanism_branches.values()))
    reference_output_space = reference_branch.output_space
    alpha, s_q, s_u = _objective_scales(config, reference_branch)
    tasks = _resolve_tasks(config, reference_output_space)

    trial_rows: list[dict[str, Any]] = []
    failure_rows: list[dict[str, Any]] = []

    for trial_index, task in enumerate(tasks):
        per_mechanism_results: dict[str, dict[str, SearchResult]] = {}
        for mechanism_id, branch in mechanism_branches.items():
            base_graph = graphs[mechanism_id]
            graph: EmbeddedPlanningGraph | QueryOverlayGraph

            start_id: int
            goal_id: int
            start_residual_vec: np.ndarray
            goal_residual_vec: np.ndarray
            start_residual_norm: float
            goal_residual_norm: float
            start_u: np.ndarray
            goal_u: np.ndarray

            if config.tasks.use_query_overlays:
                try:
                    graph = QueryOverlayGraph(
                        base=base_graph,
                        start_q=task.requested_start_q,
                        goal_q=task.requested_goal_q,
                        edge_n_samples=config.edge_validation.samples,
                    )
                    start_id = graph.start_node_id
                    goal_id = graph.goal_node_id

                    output_space = branch.output_space
                    canon_start = output_space.canonicalize(task.requested_start_q)
                    canon_goal = output_space.canonicalize(task.requested_goal_q)

                    start_q_real = np.asarray(graph.q_state(start_id), dtype=np.float64)
                    goal_q_real = np.asarray(graph.q_state(goal_id), dtype=np.float64)
                    start_residual_vec = np.asarray(
                        start_q_real - canon_start, dtype=np.float64
                    )
                    goal_residual_vec = np.asarray(
                        goal_q_real - canon_goal, dtype=np.float64
                    )
                    start_residual_norm = float(np.linalg.norm(start_residual_vec))
                    goal_residual_norm = float(np.linalg.norm(goal_residual_vec))

                    if start_residual_norm > config.tasks.output_tolerance:
                        failure_rows.append(
                            V2FailureRow(
                                run_id=rid,
                                trial_index=trial_index,
                                mechanism_id=mechanism_id,
                                requested_start_q=list(task.requested_start_q),
                                requested_goal_q=list(task.requested_goal_q),
                                output_tolerance=config.tasks.output_tolerance,
                                rejection_reason=TaskRejectionReason.START_RESIDUAL_EXCEEDS_TOLERANCE.value,
                                start_residual_norm=start_residual_norm,
                                goal_residual_norm=goal_residual_norm,
                            ).to_dict()
                        )
                        continue
                    if goal_residual_norm > config.tasks.output_tolerance:
                        failure_rows.append(
                            V2FailureRow(
                                run_id=rid,
                                trial_index=trial_index,
                                mechanism_id=mechanism_id,
                                requested_start_q=list(task.requested_start_q),
                                requested_goal_q=list(task.requested_goal_q),
                                output_tolerance=config.tasks.output_tolerance,
                                rejection_reason=TaskRejectionReason.GOAL_RESIDUAL_EXCEEDS_TOLERANCE.value,
                                start_residual_norm=start_residual_norm,
                                goal_residual_norm=goal_residual_norm,
                            ).to_dict()
                        )
                        continue

                    start_u = np.asarray(graph.u_state(start_id), dtype=np.float64)
                    goal_u = np.asarray(graph.u_state(goal_id), dtype=np.float64)
                except ValueError as exc:
                    failure_rows.append(
                        V2FailureRow(
                            run_id=rid,
                            trial_index=trial_index,
                            mechanism_id=mechanism_id,
                            requested_start_q=list(task.requested_start_q),
                            requested_goal_q=list(task.requested_goal_q),
                            output_tolerance=config.tasks.output_tolerance,
                            rejection_reason=str(exc),
                            start_residual_norm=None,
                            goal_residual_norm=None,
                        ).to_dict()
                    )
                    continue
            else:
                resolved = resolve_output_task(
                    base_graph, task, output_tolerance=config.tasks.output_tolerance
                )
                if resolved.rejected:
                    failure_rows.append(
                        V2FailureRow(
                            run_id=rid,
                            trial_index=trial_index,
                            mechanism_id=mechanism_id,
                            requested_start_q=list(task.requested_start_q),
                            requested_goal_q=list(task.requested_goal_q),
                            output_tolerance=config.tasks.output_tolerance,
                            rejection_reason=str(resolved.rejection_reason),
                            start_residual_norm=(
                                None
                                if resolved.start is None
                                else resolved.start.residual_norm
                            ),
                            goal_residual_norm=(
                                None
                                if resolved.goal is None
                                else resolved.goal.residual_norm
                            ),
                        ).to_dict()
                    )
                    continue

                graph = base_graph
                start_id = resolved.start_node_id
                goal_id = resolved.goal_node_id
                start_residual_vec = np.asarray(
                    resolved.start.residual_vector, dtype=np.float64
                )
                goal_residual_vec = np.asarray(
                    resolved.goal.residual_vector, dtype=np.float64
                )
                start_residual_norm = float(resolved.start.residual_norm)
                goal_residual_norm = float(resolved.goal.residual_norm)
                start_u = np.asarray(resolved.start.realized_u, dtype=np.float64)
                goal_u = np.asarray(resolved.goal.realized_u, dtype=np.float64)

            dim = branch.mechanism.output_dim
            q_spacing = [
                graph.output_axis_spacing(axis).to_dict() for axis in range(dim)
            ]
            u_spacing = [
                graph.actuator_axis_spacing(axis).to_dict() for axis in range(dim)
            ]
            valid_edge_count = sum(
                1
                for a, b in graph.topology.iter_edges()
                if graph.valid_nodes[a] and graph.valid_nodes[b]
            )

            algo_results: dict[str, SearchResult] = {}
            for algorithm in config.algorithms:
                heuristic_name = (
                    "zero"
                    if algorithm == "dijkstra"
                    else config.objective.resolved_heuristic()
                )
                objective = resolve_v2_objective(
                    graph,
                    goal_id,
                    config.objective.cost,
                    heuristic_name,
                    alpha=alpha,
                    s_q=s_q,
                    s_u=s_u,
                    edge_n_samples=config.edge_validation.samples,
                )
                result = best_first_search(
                    graph,
                    start_id,
                    goal_id,
                    edge_cost=objective.edge_cost,
                    heuristic=objective.heuristic,
                    record_expanded=True,
                )
                algo_results[algorithm] = result
                length_u, length_q, length_x = _path_metrics(branch, graph, result.path)

                cost_d_q = cost_d_u = cost_norm_q = cost_norm_u = None
                if (
                    config.objective.cost == "q_u_blend"
                    and alpha is not None
                    and s_q is not None
                    and s_u is not None
                    and result.found
                ):
                    comps = path_q_u_blend_components(
                        graph,
                        result.path,
                        alpha=alpha,
                        s_q=s_q,
                        s_u=s_u,
                        edge_n_samples=config.edge_validation.samples,
                    )
                    cost_d_q = comps.d_q
                    cost_d_u = comps.d_u
                    cost_norm_q = comps.norm_q
                    cost_norm_u = comps.norm_u

                start_q_real = np.asarray(graph.q_state(start_id), dtype=np.float64)
                goal_q_real = np.asarray(graph.q_state(goal_id), dtype=np.float64)
                valid_node_count = int(np.sum(graph.valid_nodes))
                expansion_fraction = (
                    float(result.n_expanded) / float(valid_node_count)
                    if valid_node_count > 0
                    else None
                )
                row = V2ResultRow(
                    architecture_version=2,
                    result_schema_version=RESULT_SCHEMA_VERSION_V2,
                    run_id=rid,
                    trial_index=trial_index,
                    mechanism_id=mechanism_id,
                    branch_id=branch.branch_id,
                    branch_certificate=branch.certificate.to_dict(),
                    sampling_domain=graph.sampling_domain.value,
                    transition_parameterization=graph.transition_parameterization.value,
                    graph_shape=tuple(graph.topology.shape),
                    node_count=graph.node_count,
                    valid_node_count=valid_node_count,
                    valid_edge_count=valid_edge_count,
                    algorithm=algorithm,
                    cost_type=objective.cost_name,
                    heuristic_type=objective.heuristic_name,
                    alpha=alpha,
                    s_q=s_q,
                    s_u=s_u,
                    cost_d_q=cost_d_q,
                    cost_d_u=cost_d_u,
                    cost_norm_q=cost_norm_q,
                    cost_norm_u=cost_norm_u,
                    requested_start_q=list(task.requested_start_q),
                    requested_goal_q=list(task.requested_goal_q),
                    realized_start_q=list(start_q_real),
                    realized_goal_q=list(goal_q_real),
                    start_residual_q=list(start_residual_vec),
                    goal_residual_q=list(goal_residual_vec),
                    start_residual_norm=start_residual_norm,
                    goal_residual_norm=goal_residual_norm,
                    start_u=list(start_u),
                    goal_u=list(goal_u),
                    start_node_id=start_id,
                    goal_node_id=goal_id,
                    found=result.found,
                    optimal_cost=result.cost,
                    n_expanded=result.n_expanded,
                    n_generated=result.n_generated,
                    n_stale=result.n_stale,
                    n_path_edges=result.n_path_edges,
                    path_length_u=length_u,
                    path_length_q=length_q,
                    path_length_x=length_x,
                    expansion_fraction=expansion_fraction,
                    pair_id=None,
                    task_set_id=None,
                    q_spacing_summary=q_spacing,
                    u_spacing_summary=u_spacing,
                    seed=config.seed,
                    code_revision=code_revision,
                    path_node_ids=result.path,
                    expanded_node_ids=result.expanded_nodes,
                )
                trial_rows.append(row.to_dict())
            per_mechanism_results[mechanism_id] = algo_results

        if config.sampling.domain == "output":
            _assert_null_control_invariant(config, trial_index, per_mechanism_results)

    config_yaml_text = v2_experiment_config_to_yaml(config)
    _write_run_package(
        run_dir,
        run_id=rid,
        config=config,
        config_yaml_text=config_yaml_text,
        revision=revision,
        environment=environment,
        mechanism_branches=mechanism_branches,
        graphs=graphs,
        trial_rows=trial_rows,
        failure_rows=failure_rows,
        write_figures=write_figures,
    )

    return V2RunResult(
        run_id=rid,
        path=run_dir.resolve(),
        mechanism_ids=tuple(mechanism_branches.keys()),  # type: ignore[arg-type]
        n_tasks=len(tasks),
        n_trial_rows=len(trial_rows),
        n_failure_rows=len(failure_rows),
    )


def run_v2_experiment_from_path(
    config_path: Path | str,
    *,
    results_root: Path | str | None = None,
    run_id: str | None = None,
    write_figures: bool = True,
) -> V2RunResult:
    """Load, strictly validate, and run a Version 2 experiment YAML config."""
    config = load_v2_experiment_config(config_path)
    return run_v2_experiment(
        config,
        results_root=results_root,
        run_id=run_id,
        write_figures=write_figures,
    )
