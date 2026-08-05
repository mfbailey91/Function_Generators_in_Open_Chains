"""Shared-Q paired mechanism study orchestration (V2.8 blend / V2.9 U-only).

V2.8 hierarchy (``q_u_blend`` + alpha sweep):

```text
run
└── task_set
    └── mechanism_pair
        └── alpha
            ├── fourbar
            ├── span_matched_gearbox
            └── unit_gearbox (optional identity control)
```

V2.9 hierarchy (raw ``actuator_travel`` only; no alpha / Q term):

```text
run
└── task_set (3)
    └── mechanism_pair (5)
        ├── fourbar
        └── span_matched_gearbox
```

Reuses Version 2 graph construction, query overlays, Dijkstra search, and the
immutable run-package writer. Does not resample failed tasks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from inequality_mechanisms.experiments.registry import (
    capture_environment,
    capture_revision,
    default_results_root,
    generate_run_id,
    validate_run_id,
)
from inequality_mechanisms.experiments.v2_canvas import write_v2_canvas
from inequality_mechanisms.experiments.v2_config import (
    V2BranchConfig,
    V2EdgeValidationConfig,
    V2ExperimentConfig,
    V2MechanismsConfig,
    V2ObjectiveConfig,
    V2OutputPair,
    V2SamplingConfig,
    V2TasksConfig,
)
from inequality_mechanisms.experiments.v2_paired_metrics import (
    compare_paired_rows,
    divergence_onset_by_alpha,
)
from inequality_mechanisms.experiments.v2_results import (
    RESULT_SCHEMA_VERSION_V2,
    V2_RESULT_FIELDS,
    V2FailureRow,
    V2ResultRow,
    rows_to_csv,
    rows_to_jsonl,
)
from inequality_mechanisms.experiments.v2_runner import (
    FOURBAR_MECHANISM_ID,
    SPAN_MATCHED_GEARBOX_MECHANISM_ID,
    UNIT_GEARBOX_MECHANISM_ID,
    V2RunnerError,
    _path_metrics,
    _utc_now_iso,
    build_graphs,
    build_mechanism_branches,
    unit_gearbox_branch,
)
from inequality_mechanisms.experiments.v2_shared_q_fixtures import (
    FROZEN_MECHANISM_PAIRS,
    TASK_TEMPLATES,
    fractions_to_q,
    pair_by_id,
    task_template_by_id,
)
from inequality_mechanisms.experiments.v2_tasks import (
    OutputTask,
    TaskRejectionReason,
)
from inequality_mechanisms.graphs.pair_invariants import (
    SharedQPairInvariantError,
    assert_identical_query_overlays,
    assert_shared_q_pair_invariants,
)
from inequality_mechanisms.graphs.query_overlay import QueryOverlayGraph
from inequality_mechanisms.search.core import best_first_search
from inequality_mechanisms.search.v2_objectives import (
    pair_box_scales,
    path_q_u_blend_components,
    resolve_v2_objective,
)

_ARM_LABELS = {
    FOURBAR_MECHANISM_ID: "Four-bar",
    SPAN_MATCHED_GEARBOX_MECHANISM_ID: "Span-matched gearbox",
    UNIT_GEARBOX_MECHANISM_ID: "Unit gearbox",
}

_U_DISTANCE_STUDY_NAMES = frozenset(
    {
        "shared_q_paired_u_2r",
        "shared_q_paired_u_smoke",
        "shared_q_paired_2r_u_distance_only",
    }
)
_BLEND_STUDY_NAMES = frozenset({"shared_q_paired_2r", "shared_q_paired_smoke"})
_SHARED_Q_STUDY_NAMES = _BLEND_STUDY_NAMES | _U_DISTANCE_STUDY_NAMES


class V2SharedQStudyError(ValueError):
    """Raised when a shared-Q paired study config is invalid."""


def is_u_distance_only_study(name: str) -> bool:
    """Return whether ``name`` selects the V2.9 actuator-travel-only study."""
    return name in _U_DISTANCE_STUDY_NAMES


class V2StudyMeta(BaseModel):
    """Top-level study selector block."""

    model_config = ConfigDict(extra="forbid")

    name: str = "shared_q_paired_2r"
    mechanism_pair_ids: list[str]
    task_template_ids: list[str]
    alphas: list[float] = Field(default_factory=list)
    reference_algorithm: str = "dijkstra"
    optional_algorithms: list[str] = Field(default_factory=list)
    include_unit_gearbox: bool = True

    @field_validator("alphas")
    @classmethod
    def _alphas_range(cls, value: list[float]) -> list[float]:
        out = [float(a) for a in value]
        if any(a < 0.0 or a > 1.0 for a in out):
            raise ValueError("study.alphas must lie in [0, 1]")
        return out

    @model_validator(mode="after")
    def _alphas_match_mode(self) -> V2StudyMeta:
        if is_u_distance_only_study(self.name):
            if self.alphas:
                raise ValueError(
                    "U-distance-only study must not set study.alphas "
                    "(use actuator_travel with no cost sweep)"
                )
            return self
        if not self.alphas:
            raise ValueError("study.alphas must be non-empty for q_u_blend studies")
        return self


class V2SharedQPairedStudyConfig(BaseModel):
    """Dedicated shared-Q paired study configuration (V2.8 / V2.9)."""

    model_config = ConfigDict(extra="forbid")

    architecture_version: int = 2
    result_schema_version: int = 2
    planning_space: str = "output"
    study: V2StudyMeta
    branch: V2BranchConfig
    sampling: V2SamplingConfig
    edge_validation: V2EdgeValidationConfig = Field(
        default_factory=V2EdgeValidationConfig
    )
    tasks: V2TasksConfig
    seed: int = 20260801
    matching_rule: str = "span"

    @model_validator(mode="after")
    def _validate_ids(self) -> V2SharedQPairedStudyConfig:
        if self.architecture_version != 2:
            raise ValueError("architecture_version must be 2")
        if self.planning_space != "output":
            raise ValueError("planning_space must be output")
        if self.sampling.domain != "output":
            raise ValueError("shared-Q study requires sampling.domain: output")
        for pair_id in self.study.mechanism_pair_ids:
            pair_by_id(pair_id)
        for task_id in self.study.task_template_ids:
            task_template_by_id(task_id)
        if self.study.reference_algorithm != "dijkstra":
            raise ValueError("reference_algorithm must be dijkstra")
        return self

    @property
    def u_distance_only(self) -> bool:
        """True when this config runs raw actuator_travel with no alpha sweep."""
        return is_u_distance_only_study(self.study.name)


def load_shared_q_paired_study_config(
    path: Path | str,
) -> V2SharedQPairedStudyConfig:
    """Load and validate a shared-Q paired study YAML config."""
    config_path = Path(path)
    with config_path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    if not isinstance(raw, dict):
        raise V2SharedQStudyError("study config root must be a mapping")
    if "study" not in raw:
        raise V2SharedQStudyError("missing study block")
    try:
        return V2SharedQPairedStudyConfig.model_validate(raw)
    except Exception as exc:  # noqa: BLE001 — surface as study error
        raise V2SharedQStudyError(str(exc)) from exc


def is_shared_q_paired_study_mapping(raw: dict[str, Any]) -> bool:
    """Return whether a raw YAML mapping is a shared-Q paired study config."""
    study = raw.get("study")
    if not isinstance(study, dict):
        return False
    name = study.get("name")
    return name in _SHARED_Q_STUDY_NAMES


def _pair_experiment_config(
    study: V2SharedQPairedStudyConfig,
    *,
    pair_id: str,
    alpha: float | None,
    start_q: list[float],
    goal_q: list[float],
) -> V2ExperimentConfig:
    pair = pair_by_id(pair_id)
    if study.u_distance_only:
        objective = V2ObjectiveConfig(
            cost="actuator_travel",
            heuristic="zero",
            alpha=None,
        )
    else:
        if alpha is None:
            raise ValueError("q_u_blend study requires a finite alpha")
        objective = V2ObjectiveConfig(
            cost="q_u_blend",
            heuristic="zero",
            alpha=float(alpha),
        )
    return V2ExperimentConfig(
        architecture_version=2,
        result_schema_version=2,
        planning_space="output",
        mechanisms=V2MechanismsConfig(
            comparison="fourbar_vs_equivalent_affine_gearbox",
            dim=2,
            fourbar=pair.fourbars[0],
            fourbars=list(pair.fourbars),
            matching_rule=study.matching_rule,  # type: ignore[arg-type]
            gearbox_mechanism_id=SPAN_MATCHED_GEARBOX_MECHANISM_ID,
        ),
        branch=study.branch,
        sampling=study.sampling,
        objective=objective,
        edge_validation=study.edge_validation,
        tasks=V2TasksConfig(
            source="fixed_output_pairs",
            output_tolerance=study.tasks.output_tolerance,
            use_query_overlays=True,
            pairs=[V2OutputPair(start_q=start_q, goal_q=goal_q)],
        ),
        algorithms=["dijkstra"],
        seed=study.seed,
        trials=1,
    )


@dataclass(frozen=True, slots=True)
class SharedQPairedStudyResult:
    """Handle summarizing one written shared-Q paired study package."""

    run_id: str
    path: Path
    n_trial_rows: int
    n_failure_rows: int
    n_pair_comparisons: int


def run_shared_q_paired_study(
    config: V2SharedQPairedStudyConfig,
    *,
    results_root: Path | str | None = None,
    run_id: str | None = None,
    write_figures: bool = True,
) -> SharedQPairedStudyResult:
    """Execute the shared-Q paired study and write one immutable run package."""
    u_only = config.u_distance_only
    cost_schedule: list[float | None]
    if u_only:
        cost_schedule = [None]
    else:
        cost_schedule = [float(a) for a in config.study.alphas]

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
    run_dir.mkdir(parents=True)
    (run_dir / "branches").mkdir()
    (run_dir / "diagnostics").mkdir()
    (run_dir / "figures").mkdir()
    (run_dir / "figures" / "paths").mkdir()

    revision = capture_revision(cwd=None)
    environment = capture_environment()
    code_revision = revision.get("git_commit")

    trial_rows: list[dict[str, Any]] = []
    failure_rows: list[dict[str, Any]] = []
    pair_comparisons: list[dict[str, Any]] = []
    invariant_reports: list[dict[str, Any]] = []
    branch_payloads: dict[str, Any] = {}
    diagnostic_payloads: dict[str, Any] = {}
    trial_index = 0
    figures_root = run_dir / "figures"
    plotters: dict[str, Any] | None = None
    if write_figures:
        try:
            from inequality_mechanisms.visualization.embedded_graphs import (
                plot_actuator_samples,
                plot_embedded_q_path,
                plot_embedded_u_path,
                plot_output_graph,
            )
            from inequality_mechanisms.visualization.branches import (
                plot_branch_axis_transmission,
            )
            from inequality_mechanisms.visualization.paths import plot_cartesian_path
            from inequality_mechanisms.visualization.v2_expansions import (
                plot_v2_expansions_by_alpha,
                plot_v2_expansions_by_mechanism,
            )
        except ImportError:
            plotters = None
        else:
            plotters = {
                "plot_actuator_samples": plot_actuator_samples,
                "plot_branch_axis_transmission": plot_branch_axis_transmission,
                "plot_embedded_q_path": plot_embedded_q_path,
                "plot_embedded_u_path": plot_embedded_u_path,
                "plot_output_graph": plot_output_graph,
                "plot_cartesian_path": plot_cartesian_path,
                "plot_v2_expansions_by_alpha": plot_v2_expansions_by_alpha,
                "plot_v2_expansions_by_mechanism": plot_v2_expansions_by_mechanism,
            }

    algorithms = [config.study.reference_algorithm] + list(
        config.study.optional_algorithms
    )
    # Dijkstra-only in the first study release; optional A* reserved.
    algorithms = ["dijkstra"]

    for pair_id in config.study.mechanism_pair_ids:
        # Build branches/graphs once per pair (reuse across tasks / cost passes).
        probe_cfg = _pair_experiment_config(
            config,
            pair_id=pair_id,
            alpha=None if u_only else 1.0,
            start_q=[0.0, 0.0],
            goal_q=[1.0, 1.0],
        )
        # Placeholder tasks are overwritten per template after we know the box.
        mechanism_branches = build_mechanism_branches(probe_cfg)
        if config.study.include_unit_gearbox:
            mechanism_branches[UNIT_GEARBOX_MECHANISM_ID] = unit_gearbox_branch(
                mechanism_branches[FOURBAR_MECHANISM_ID],
                name=UNIT_GEARBOX_MECHANISM_ID,
                certification_samples_per_axis=(
                    config.branch.certification_samples_per_axis
                ),
                min_abs_gain=config.branch.minimum_abs_gain,
                residual_tol=config.branch.inverse_tolerance,
                max_abs_gain=config.branch.max_abs_gain,
            )
        graphs = build_graphs(probe_cfg, mechanism_branches)
        # Shared feasible set: only plan on Q nodes every arm realizes.
        shared_valid = np.asarray(
            np.logical_and.reduce([g.valid_nodes for g in graphs.values()]),
            dtype=np.bool_,
        )
        graphs = {
            mid: replace(g, valid_nodes=shared_valid.copy())
            for mid, g in graphs.items()
        }
        g_fb = graphs[FOURBAR_MECHANISM_ID]
        comparison_partners = [
            mid for mid in graphs if mid != FOURBAR_MECHANISM_ID
        ]
        for partner_id in comparison_partners:
            try:
                inv = assert_shared_q_pair_invariants(
                    g_fb,
                    graphs[partner_id],
                    residual_tol=config.branch.inverse_tolerance,
                    edge_n_samples=config.edge_validation.samples,
                    raise_on_failure=True,
                )
            except SharedQPairInvariantError as exc:
                invariant_reports.append(
                    {
                        "pair_id": pair_id,
                        "partner_id": partner_id,
                        "passed": False,
                        "failures": [str(exc)],
                    }
                )
                raise V2RunnerError(f"pair {pair_id} vs {partner_id}: {exc}") from exc
            invariant_reports.append(
                {"pair_id": pair_id, "partner_id": partner_id, **inv.to_dict()}
            )

        if plotters is not None:
            pair_fig = figures_root / pair_id
            pair_fig.mkdir(parents=True, exist_ok=True)
            plotters["plot_output_graph"](
                g_fb,
                pair_fig / "q_lattice.png",
                title=f"{pair_id}: shared Q lattice",
            )
            for mid, graph in graphs.items():
                plotters["plot_actuator_samples"](
                    graph,
                    pair_fig / f"u_{mid}.png",
                    title=f"{pair_id}: {mid} U embedding",
                )
            plotters["plot_branch_axis_transmission"](
                {
                    _ARM_LABELS.get(mid, mid): branch
                    for mid, branch in mechanism_branches.items()
                },
                pair_fig / "qu_axis_maps.png",
                title=f"{pair_id}: axis transmission $q(u)$",
            )

        ref_branch = mechanism_branches[FOURBAR_MECHANISM_ID]
        cert = ref_branch.certificate
        s_q, s_u = pair_box_scales(
            np.asarray(cert.output_lower, dtype=np.float64),
            np.asarray(cert.output_upper, dtype=np.float64),
            np.asarray(cert.input_lower, dtype=np.float64),
            np.asarray(cert.input_upper, dtype=np.float64),
        )

        for mechanism_id, branch in mechanism_branches.items():
            key = f"{pair_id}__{mechanism_id}"
            branch_payloads[key] = branch.to_dict()
            graph = graphs[mechanism_id]
            dim = len(graph.topology.shape)
            q_spacing = [
                graph.output_axis_spacing(axis).to_dict() for axis in range(dim)
            ]
            u_spacing: list[dict[str, Any]] = []
            try:
                u_spacing = [
                    graph.actuator_axis_spacing(axis).to_dict() for axis in range(dim)
                ]
            except ValueError:
                u_spacing = [
                    {"error": "non_finite_actuator_samples"} for _ in range(dim)
                ]
            diagnostic_payloads[key] = {
                "pair_id": pair_id,
                "mechanism_id": mechanism_id,
                "sampling_domain": graph.sampling_domain.value,
                "transition_parameterization": graph.transition_parameterization.value,
                "graph_shape": list(graph.topology.shape),
                "node_count": graph.node_count,
                "valid_node_count": int(np.sum(graph.valid_nodes)),
                "q_spacing_summary": q_spacing,
                "u_spacing_summary": u_spacing,
                "s_q": s_q,
                "s_u": s_u,
            }

        for task_set_id in config.study.task_template_ids:
            template = task_template_by_id(task_set_id)
            start_q = fractions_to_q(
                cert.output_lower, cert.output_upper, template.start_fraction
            )
            goal_q = fractions_to_q(
                cert.output_lower, cert.output_upper, template.goal_fraction
            )
            task = OutputTask(
                np.asarray(start_q, dtype=np.float64),
                np.asarray(goal_q, dtype=np.float64),
            )

            overlays: dict[str, QueryOverlayGraph] = {}
            overlay_ok = True
            for mechanism_id, base_graph in graphs.items():
                try:
                    overlays[mechanism_id] = QueryOverlayGraph(
                        base=base_graph,
                        start_q=task.requested_start_q,
                        goal_q=task.requested_goal_q,
                        edge_n_samples=config.edge_validation.samples,
                    )
                except ValueError as exc:
                    overlay_ok = False
                    for mid in graphs:
                        failure_rows.append(
                            V2FailureRow(
                                run_id=rid,
                                trial_index=trial_index,
                                mechanism_id=mid,
                                requested_start_q=list(task.requested_start_q),
                                requested_goal_q=list(task.requested_goal_q),
                                output_tolerance=config.tasks.output_tolerance,
                                rejection_reason=str(exc),
                                start_residual_norm=None,
                                goal_residual_norm=None,
                            ).to_dict()
                            | {
                                "pair_id": pair_id,
                                "task_set_id": task_set_id,
                            }
                        )
                    trial_index += 1
                    break
            if not overlay_ok:
                continue

            for partner_id in comparison_partners:
                try:
                    assert_identical_query_overlays(
                        overlays[FOURBAR_MECHANISM_ID],
                        overlays[partner_id],
                        raise_on_failure=True,
                    )
                except SharedQPairInvariantError as exc:
                    raise V2RunnerError(
                        f"pair {pair_id} task {task_set_id} vs {partner_id}: {exc}"
                    ) from exc

            cost_rows: dict[float | None, dict[str, dict[str, Any]]] = {}
            for alpha in cost_schedule:
                cost_rows[alpha] = {}
                cost_name = "actuator_travel" if u_only else "q_u_blend"
                for mechanism_id, branch in mechanism_branches.items():
                    graph = overlays[mechanism_id]
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
                    if (
                        start_residual_norm > config.tasks.output_tolerance
                        or goal_residual_norm > config.tasks.output_tolerance
                    ):
                        failure_extra: dict[str, Any] = {
                            "pair_id": pair_id,
                            "task_set_id": task_set_id,
                        }
                        if alpha is not None:
                            failure_extra["alpha"] = float(alpha)
                        failure_rows.append(
                            V2FailureRow(
                                run_id=rid,
                                trial_index=trial_index,
                                mechanism_id=mechanism_id,
                                requested_start_q=list(task.requested_start_q),
                                requested_goal_q=list(task.requested_goal_q),
                                output_tolerance=config.tasks.output_tolerance,
                                rejection_reason=(
                                    TaskRejectionReason.START_RESIDUAL_EXCEEDS_TOLERANCE.value
                                    if start_residual_norm
                                    > config.tasks.output_tolerance
                                    else TaskRejectionReason.GOAL_RESIDUAL_EXCEEDS_TOLERANCE.value
                                ),
                                start_residual_norm=start_residual_norm,
                                goal_residual_norm=goal_residual_norm,
                            ).to_dict()
                            | failure_extra
                        )
                        continue

                    start_u = np.asarray(graph.u_state(start_id), dtype=np.float64)
                    goal_u = np.asarray(graph.u_state(goal_id), dtype=np.float64)
                    dim = branch.mechanism.output_dim
                    q_spacing = [
                        graph.output_axis_spacing(axis).to_dict() for axis in range(dim)
                    ]
                    try:
                        u_spacing = [
                            graph.actuator_axis_spacing(axis).to_dict()
                            for axis in range(dim)
                        ]
                    except ValueError:
                        u_spacing = [
                            {"error": "non_finite_actuator_samples"} for _ in range(dim)
                        ]
                    valid_edge_count = sum(
                        1
                        for a, b in graph.topology.iter_edges()
                        if graph.valid_nodes[a] and graph.valid_nodes[b]
                    )
                    if u_only:
                        objective = resolve_v2_objective(
                            graph,
                            goal_id,
                            "actuator_travel",
                            "zero",
                        )
                    else:
                        objective = resolve_v2_objective(
                            graph,
                            goal_id,
                            "q_u_blend",
                            "zero",
                            alpha=float(alpha),
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
                    length_u, length_q, length_x = _path_metrics(
                        branch, graph, result.path
                    )
                    comps = None
                    if result.found and not u_only:
                        comps = path_q_u_blend_components(
                            graph,
                            result.path,
                            alpha=float(alpha),
                            s_q=s_q,
                            s_u=s_u,
                            edge_n_samples=config.edge_validation.samples,
                        )
                    # Reporting-only normalized U length (never enters the planner).
                    norm_u_report = (
                        float(length_u) / float(s_u)
                        if result.found and s_u > 0.0 and length_u is not None
                        else None
                    )
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
                        algorithm="dijkstra",
                        cost_type=cost_name,
                        heuristic_type="zero",
                        alpha=None if u_only else float(alpha),
                        s_q=s_q,
                        s_u=s_u,
                        cost_d_q=None if comps is None else comps.d_q,
                        cost_d_u=(
                            float(length_u)
                            if u_only and result.found and length_u is not None
                            else (None if comps is None else comps.d_u)
                        ),
                        cost_norm_q=None if comps is None else comps.norm_q,
                        cost_norm_u=(
                            norm_u_report
                            if u_only
                            else (None if comps is None else comps.norm_u)
                        ),
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
                        pair_id=pair_id,
                        task_set_id=task_set_id,
                        q_spacing_summary=q_spacing,
                        u_spacing_summary=u_spacing,
                        seed=config.seed,
                        code_revision=code_revision,
                        path_node_ids=result.path,
                        expanded_node_ids=result.expanded_nodes,
                    ).to_dict()
                    trial_rows.append(row)
                    cost_rows[alpha][mechanism_id] = row

                    if plotters is not None and result.found and result.path:
                        paths_dir = figures_root / "paths"
                        paths_dir.mkdir(parents=True, exist_ok=True)
                        if u_only:
                            stem = f"{pair_id}__{task_set_id}__{mechanism_id}"
                            title_prefix = f"{pair_id} {task_set_id} {mechanism_id}"
                        else:
                            alpha_tag = f"{float(alpha):g}".replace(".", "p")
                            stem = f"{pair_id}__a{alpha_tag}__{mechanism_id}"
                            title_prefix = f"{pair_id} α={float(alpha):g} {mechanism_id}"
                        plotters["plot_embedded_q_path"](
                            graph,
                            paths_dir / f"{stem}_q.png",
                            path_node_ids=result.path,
                            expanded_node_ids=result.expanded_nodes,
                            title=f"{title_prefix}: Q",
                        )
                        plotters["plot_embedded_u_path"](
                            graph,
                            paths_dir / f"{stem}_u.png",
                            path_node_ids=result.path,
                            expanded_node_ids=None,
                            title=f"{title_prefix}: U",
                        )
                        q_path = np.vstack(
                            [
                                np.asarray(graph.q_state(n), dtype=np.float64)
                                for n in result.path
                            ]
                        )
                        if q_path.shape[1] == 2:
                            plotters["plot_cartesian_path"](
                                q_path,
                                paths_dir / f"{stem}_x.png",
                                title=f"{title_prefix}: Cartesian",
                                n_pose_samples=8,
                            )

                    # Null-control hard gate at alpha=1 vs every partner arm.
                    if (
                        not u_only
                        and alpha is not None
                        and float(alpha) == 1.0
                        and FOURBAR_MECHANISM_ID in cost_rows[1.0]
                        and all(
                            mid in cost_rows[1.0] for mid in comparison_partners
                        )
                    ):
                        ra = cost_rows[1.0][FOURBAR_MECHANISM_ID]
                        for partner_id in comparison_partners:
                            rb = cost_rows[1.0][partner_id]
                            if (
                                ra["found"] != rb["found"]
                                or ra["path_node_ids"] != rb["path_node_ids"]
                                or abs(
                                    float(ra["optimal_cost"])
                                    - float(rb["optimal_cost"])
                                )
                                > 1e-12
                                or ra["n_expanded"] != rb["n_expanded"]
                            ):
                                raise V2RunnerError(
                                    "alpha=1 null-control failed for "
                                    f"{pair_id}/{task_set_id} vs {partner_id}"
                                )

                # Paired comparisons: four-bar vs each partner arm.
                mech_map = cost_rows[alpha]
                if FOURBAR_MECHANISM_ID in mech_map:
                    ra = mech_map[FOURBAR_MECHANISM_ID]
                    q_path_a = (
                        np.asarray(
                            [
                                overlays[FOURBAR_MECHANISM_ID].q_state(n)
                                for n in ra.get("path_node_ids") or []
                            ],
                            dtype=np.float64,
                        ).reshape(-1, 2)
                        if ra.get("path_node_ids")
                        else None
                    )
                    if q_path_a is not None and q_path_a.size == 0:
                        q_path_a = None
                    for partner_id in comparison_partners:
                        if partner_id not in mech_map:
                            continue
                        rb = mech_map[partner_id]
                        q_path_b = (
                            np.asarray(
                                [
                                    overlays[partner_id].q_state(n)
                                    for n in rb.get("path_node_ids") or []
                                ],
                                dtype=np.float64,
                            ).reshape(-1, 2)
                            if rb.get("path_node_ids")
                            else None
                        )
                        if q_path_b is not None and q_path_b.size == 0:
                            q_path_b = None
                        pair_comparisons.append(
                            compare_paired_rows(
                                ra, rb, q_path_a=q_path_a, q_path_b=q_path_b
                            )
                        )
                trial_index += 1

    # Write immutable package artifacts into the already-created run directory.
    config_payload = config.model_dump(mode="python")
    config_payload["frozen_pairs"] = [p.to_dict() for p in FROZEN_MECHANISM_PAIRS]
    config_payload["task_templates"] = [t.to_dict() for t in TASK_TEMPLATES]
    (run_dir / "config.yaml").write_text(
        yaml.safe_dump(config_payload, sort_keys=False), encoding="utf-8"
    )

    onset = (
        None if u_only else divergence_onset_by_alpha(pair_comparisons)
    )
    if u_only:
        objective_manifest: dict[str, Any] = {
            "cost": "actuator_travel",
            "heuristic": "zero",
            "alphas": [],
            "normalization": {
                "planner": "none_raw_actuator_euclidean",
                "reporting_u_scale": "paired_branch_box_diagonal",
            },
        }
    else:
        objective_manifest = {
            "cost": "q_u_blend",
            "heuristic": "zero",
            "alphas": list(config.study.alphas),
            "normalization": {
                "q_scale": "output_box_diagonal",
                "u_scale": "paired_branch_box_diagonal",
            },
        }
    manifest: dict[str, Any] = {
        "run_id": rid,
        "architecture_version": 2,
        "result_schema_version": RESULT_SCHEMA_VERSION_V2,
        "study": config.study.model_dump(mode="python"),
        "seed": config.seed,
        "sampling_domain": "output",
        "objective": objective_manifest,
        "algorithms": algorithms,
        "n_trial_rows": len(trial_rows),
        "n_failure_rows": len(failure_rows),
        "n_pair_comparisons": len(pair_comparisons),
        "divergence_onset_by_alpha": onset,
        "created_at": _utc_now_iso(),
        "revision": revision,
        "environment": environment,
        "comparison": {
            "linear_control": SPAN_MATCHED_GEARBOX_MECHANISM_ID,
            "identity_control": (
                UNIT_GEARBOX_MECHANISM_ID
                if config.study.include_unit_gearbox
                else None
            ),
            "include_unit_gearbox": bool(config.study.include_unit_gearbox),
            "require_identical_q_topology": True,
            "reject_on_pair_invariant_failure": True,
        },
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (run_dir / "trials.jsonl").write_text(rows_to_jsonl(trial_rows), encoding="utf-8")
    (run_dir / "failures.jsonl").write_text(
        rows_to_jsonl(failure_rows), encoding="utf-8"
    )
    (run_dir / "pair_comparisons.jsonl").write_text(
        rows_to_jsonl(pair_comparisons), encoding="utf-8"
    )
    (run_dir / "pair_invariants.json").write_text(
        json.dumps(invariant_reports, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (run_dir / "summary.csv").write_text(
        rows_to_csv(trial_rows, fields=V2_RESULT_FIELDS), encoding="utf-8"
    )
    for key, payload in branch_payloads.items():
        (run_dir / "branches" / f"{key}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    for key, payload in diagnostic_payloads.items():
        (run_dir / "diagnostics" / f"{key}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    if write_figures:
        figures_root.mkdir(parents=True, exist_ok=True)
        if plotters is not None and trial_rows:
            plotters["plot_v2_expansions_by_mechanism"](
                trial_rows,
                figures_root / "expansions_raw.png",
                title=(
                    "Shared-Q U-distance study: expansions by mechanism"
                    if u_only
                    else "Shared-Q paired study: expansions by mechanism"
                ),
            )
            if not u_only:
                plotters["plot_v2_expansions_by_alpha"](
                    trial_rows,
                    figures_root / "expansions_by_alpha.png",
                    title="Shared-Q paired study: expansions vs alpha",
                )

    write_v2_canvas(run_dir)
    return SharedQPairedStudyResult(
        run_id=rid,
        path=run_dir.resolve(),
        n_trial_rows=len(trial_rows),
        n_failure_rows=len(failure_rows),
        n_pair_comparisons=len(pair_comparisons),
    )


def run_shared_q_paired_study_from_path(
    config_path: Path | str,
    *,
    results_root: Path | str | None = None,
    run_id: str | None = None,
    write_figures: bool = True,
) -> SharedQPairedStudyResult:
    """Load a study YAML and execute :func:`run_shared_q_paired_study`."""
    config = load_shared_q_paired_study_config(config_path)
    return run_shared_q_paired_study(
        config,
        results_root=results_root,
        run_id=run_id,
        write_figures=write_figures,
    )
