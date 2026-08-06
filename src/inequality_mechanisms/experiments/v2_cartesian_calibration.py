"""Experiment B Cartesian radius / resolution calibration (V2B-005).

Writes decision JSON for production gates. Crossed-population inference and
orchestration remain separate work packages.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from inequality_mechanisms.experiments.resolution import select_production_resolution
from inequality_mechanisms.experiments.v2_cartesian_tasks import (
    START_ATTACHMENT_POLICY_ID,
    CartesianAnnularSectorDomain,
    CartesianPositionTask,
    assert_paired_cartesian_query_identity,
    generate_cartesian_task_bank,
    resolve_cartesian_task,
)
from inequality_mechanisms.experiments.v2_runner import (
    FOURBAR_MECHANISM_ID,
    build_graphs,
    build_mechanism_branches,
)
from inequality_mechanisms.graphs.pair_invariants import assert_shared_q_pair_invariants
from inequality_mechanisms.kinematics.planar_2r import Planar2R
from inequality_mechanisms.search.graph_solver import production_graph_solver
from inequality_mechanisms.search.v2_objectives import resolve_v2_goal_set_objective

RADIUS_DECISION_NAME = "cartesian_radius_decision"
RESOLUTION_DECISION_NAME = "cartesian_resolution_decision"
START_ATTACHMENT_DECISION_NAME = "cartesian_start_attachment_decision"

RADIUS_DECISION_FILE = f"{RADIUS_DECISION_NAME}.json"
RESOLUTION_DECISION_FILE = f"{RESOLUTION_DECISION_NAME}.json"
START_ATTACHMENT_DECISION_FILE = f"{START_ATTACHMENT_DECISION_NAME}.json"

STAGES_REQUIRING_CARTESIAN_CALIBRATION = frozenset({"production"})
DEFAULT_SEPARATION_FLOOR = 0.30
START_ATTACHMENT_RETAIN_DECISION = "retain_nearest_node_v1"


class CartesianCalibrationError(ValueError):
    """Invalid Cartesian calibration configuration or missing decisions."""


@dataclass(frozen=True, slots=True)
class CartesianCalibrationSettings:
    """Candidate sweep and selection criteria for V2B-005."""

    candidate_resolutions: tuple[int, ...]
    candidate_goal_radii: tuple[float, ...]
    min_attachment_rate: float = 0.50
    max_relative_effect_change: float = 0.05
    separation_floor: float = DEFAULT_SEPARATION_FLOOR
    run_search: bool = True

    def __post_init__(self) -> None:
        if not self.candidate_resolutions:
            raise CartesianCalibrationError("candidate_resolutions must be non-empty")
        if not self.candidate_goal_radii:
            raise CartesianCalibrationError("candidate_goal_radii must be non-empty")
        if any(int(n) < 2 for n in self.candidate_resolutions):
            raise CartesianCalibrationError("candidate resolutions must be >= 2")
        if any(float(r) <= 0.0 for r in self.candidate_goal_radii):
            raise CartesianCalibrationError("candidate radii must be positive")
        if not (0.0 < self.min_attachment_rate <= 1.0):
            raise CartesianCalibrationError(
                "min_attachment_rate must be in (0, 1]"
            )


def separation_for_radius(
    goal_radius: float,
    *,
    floor: float = DEFAULT_SEPARATION_FLOOR,
) -> float:
    """Return ADR-019-compatible start–goal separation for a radius."""
    radius = float(goal_radius)
    if radius <= 0.0 or not np.isfinite(radius):
        raise CartesianCalibrationError("goal_radius must be finite and positive")
    return float(max(float(floor), 2.0 * radius))


def domain_for_radius(
    base: CartesianAnnularSectorDomain,
    goal_radius: float,
    *,
    separation_floor: float = DEFAULT_SEPARATION_FLOOR,
) -> CartesianAnnularSectorDomain:
    """Copy a domain with equal start/goal radii and lifted separation."""
    radius = float(goal_radius)
    return CartesianAnnularSectorDomain(
        domain_id=base.domain_id,
        radial_min=base.radial_min,
        radial_max=base.radial_max,
        angle_min=base.angle_min,
        angle_max=base.angle_max,
        start_tolerance=radius,
        goal_radius=radius,
        min_start_goal_separation=separation_for_radius(
            radius, floor=separation_floor
        ),
        L1=base.L1,
        L2=base.L2,
    )


def select_cartesian_radius(
    rows: Sequence[Mapping[str, Any]],
    *,
    min_attachment_rate: float = 0.50,
) -> dict[str, Any]:
    """Choose the smallest radius meeting the attachment floor.

    If no candidate meets the floor, choose the highest attachment rate
    (ties broken by smaller radius) and record
    ``reason=best_available_below_floor``.
    """
    if not rows:
        raise CartesianCalibrationError("radius rows must be non-empty")
    ranked = sorted(
        rows,
        key=lambda row: (float(row["goal_radius"]), int(row.get("shape_n", 0))),
    )
    meeting = [
        row
        for row in ranked
        if float(row["attachment_rate"]) >= float(min_attachment_rate)
    ]
    if meeting:
        chosen = meeting[0]
        reason = "smallest_radius_meeting_attachment_floor"
    else:
        chosen = max(
            ranked,
            key=lambda row: (
                float(row["attachment_rate"]),
                -float(row["goal_radius"]),
            ),
        )
        reason = "best_available_below_floor"
    return {
        "goal_radius": float(chosen["goal_radius"]),
        "start_tolerance": float(chosen["start_tolerance"]),
        "min_start_goal_separation": float(chosen["min_start_goal_separation"]),
        "reason": reason,
        "criteria": {"min_attachment_rate": float(min_attachment_rate)},
        "chosen_attachment_rate": float(chosen["attachment_rate"]),
        "candidates": [dict(row) for row in ranked],
        "rejected_goal_radii": [
            float(row["goal_radius"])
            for row in ranked
            if float(row["goal_radius"]) != float(chosen["goal_radius"])
        ],
    }


def select_cartesian_resolution(
    rows: Sequence[Mapping[str, Any]],
    *,
    max_relative_effect_change: float = 0.05,
) -> dict[str, Any]:
    """Choose the coarsest stable grid at a frozen radius."""
    if not rows:
        raise CartesianCalibrationError("resolution rows must be non-empty")
    decision = select_production_resolution(
        rows,
        max_relative_effect_change=max_relative_effect_change,
        require_sign_stability=True,
        require_component_stability=False,
        require_task_feasibility_stability=True,
        effect_key="mean_paired_delta_expansions",
        shape_key="shape_n",
    )
    decision["candidates"] = [
        dict(row) for row in sorted(rows, key=lambda r: int(r["shape_n"]))
    ]
    decision["rejected_shape_n"] = [
        int(row["shape_n"])
        for row in rows
        if int(row["shape_n"]) != int(decision["production_shape_n"])
    ]
    return decision


def start_attachment_retain_decision(
    *,
    residual_summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Record the smoke nearest-node policy as retained pending overlay review."""
    return {
        "policy_id": START_ATTACHMENT_POLICY_ID,
        "decision": START_ATTACHMENT_RETAIN_DECISION,
        "rationale": (
            "Retain discrete nearest-node start attachment after calibration; "
            "start-only exact overlay remains deferred."
        ),
        "residual_summary": dict(residual_summary or {}),
    }


def load_cartesian_calibration_decisions(path: Path | str) -> dict[str, Any]:
    """Load a Cartesian calibration decision directory or combined JSON file."""
    target = Path(path)
    if target.is_dir():
        payload: dict[str, Any] = {}
        for name in (
            RADIUS_DECISION_FILE,
            RESOLUTION_DECISION_FILE,
            START_ATTACHMENT_DECISION_FILE,
        ):
            candidate = target / name
            if candidate.is_file():
                key = name.removesuffix(".json")
                payload[key] = json.loads(candidate.read_text(encoding="utf-8"))
        if not payload:
            raise CartesianCalibrationError(
                f"no Cartesian calibration decisions in {target}"
            )
        return payload
    data = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise CartesianCalibrationError(
            f"calibration decisions must be a mapping: {target}"
        )
    return data


def assert_cartesian_calibration_decisions_present(
    stage: str,
    *,
    decisions: Mapping[str, Any] | None = None,
) -> None:
    """Refuse production-oriented stages that lack radius/resolution decisions."""
    if stage not in STAGES_REQUIRING_CARTESIAN_CALIBRATION:
        return
    if decisions is None:
        raise CartesianCalibrationError(
            f"stage {stage!r} requires recorded Cartesian calibration decisions "
            "(pass --apply-decisions or study.calibration_decisions)"
        )
    radius = decisions.get(RADIUS_DECISION_NAME) or decisions.get("radius")
    resolution = decisions.get(RESOLUTION_DECISION_NAME) or decisions.get(
        "resolution"
    )
    attachment = decisions.get(START_ATTACHMENT_DECISION_NAME) or decisions.get(
        "start_attachment"
    )
    missing: list[str] = []
    if not isinstance(radius, Mapping) or radius.get("goal_radius") is None:
        missing.append(RADIUS_DECISION_NAME)
    if (
        not isinstance(resolution, Mapping)
        or resolution.get("production_shape_n") is None
    ):
        missing.append(RESOLUTION_DECISION_NAME)
    if not isinstance(attachment, Mapping) or attachment.get("decision") is None:
        missing.append(START_ATTACHMENT_DECISION_NAME)
    if missing:
        raise CartesianCalibrationError(
            f"stage {stage!r} missing calibration decisions: "
            + ", ".join(missing)
        )


def apply_cartesian_calibration_decisions(
    *,
    domain: CartesianAnnularSectorDomain,
    base_experiment: Any,
    decisions: Mapping[str, Any],
    separation_floor: float = DEFAULT_SEPARATION_FLOOR,
) -> tuple[CartesianAnnularSectorDomain, Any]:
    """Return domain and base experiment with frozen radius/resolution applied."""
    radius_decision = decisions.get(RADIUS_DECISION_NAME) or decisions.get("radius")
    resolution_decision = decisions.get(RESOLUTION_DECISION_NAME) or decisions.get(
        "resolution"
    )
    if not isinstance(radius_decision, Mapping):
        raise CartesianCalibrationError("radius decision mapping required")
    if not isinstance(resolution_decision, Mapping):
        raise CartesianCalibrationError("resolution decision mapping required")
    goal_radius = float(radius_decision["goal_radius"])
    shape_n = int(resolution_decision["production_shape_n"])
    new_domain = domain_for_radius(
        domain, goal_radius, separation_floor=separation_floor
    )
    new_base = base_experiment.model_copy(
        update={
            "sampling": base_experiment.sampling.model_copy(
                update={"shape": [shape_n, shape_n]}
            )
        }
    )
    return new_domain, new_base


def write_cartesian_calibration_decisions(
    run_dir: Path,
    *,
    radius_decision: Mapping[str, Any],
    resolution_decision: Mapping[str, Any],
    start_attachment_decision: Mapping[str, Any],
) -> None:
    """Write the three immutable Experiment B decision artifacts."""
    run_dir.mkdir(parents=True, exist_ok=True)
    mapping = {
        RADIUS_DECISION_FILE: radius_decision,
        RESOLUTION_DECISION_FILE: resolution_decision,
        START_ATTACHMENT_DECISION_FILE: start_attachment_decision,
    }
    for name, payload in mapping.items():
        (run_dir / name).write_text(
            json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _percentile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    return float(np.percentile(np.asarray(values, dtype=np.float64), q))


def _summary(values: Sequence[float]) -> dict[str, float | None]:
    if not values:
        return {
            "n": 0,
            "mean": None,
            "p50": None,
            "p90": None,
            "max": None,
        }
    return {
        "n": len(values),
        "mean": float(statistics.fmean(values)),
        "p50": _percentile(values, 50),
        "p90": _percentile(values, 90),
        "max": float(max(values)),
    }


def _cardinality_summary(sizes: Sequence[int]) -> dict[str, Any]:
    if not sizes:
        return {"n": 0, "mean": None, "p50": None, "p90": None, "max": None}
    as_float = [float(s) for s in sizes]
    return {
        "n": len(sizes),
        "mean": float(statistics.fmean(as_float)),
        "p50": _percentile(as_float, 50),
        "p90": _percentile(as_float, 90),
        "max": int(max(sizes)),
        "min": int(min(sizes)),
    }


def evaluate_cartesian_candidate(
    *,
    base_experiment: Any,
    branches: Mapping[str, Any],
    domain: CartesianAnnularSectorDomain,
    tasks: Sequence[CartesianPositionTask],
    shape_n: int,
    run_search: bool,
    edge_n_samples: int,
) -> dict[str, Any]:
    """Evaluate attachment and optional Dijkstra effect at one (n, radius)."""
    experiment = base_experiment.model_copy(
        update={
            "sampling": base_experiment.sampling.model_copy(
                update={"shape": [int(shape_n), int(shape_n)]}
            )
        }
    )
    graphs = build_graphs(experiment, branches)
    graph_items = list(graphs.items())
    if len(graph_items) != 2:
        raise CartesianCalibrationError(
            "Cartesian calibration requires exactly two mechanisms"
        )
    assert_shared_q_pair_invariants(
        graph_items[0][1],
        graph_items[1][1],
        residual_tol=experiment.branch.inverse_tolerance,
        edge_n_samples=edge_n_samples,
        raise_on_failure=True,
    )
    fk = Planar2R(domain.L1, domain.L2)
    n_tasks = len(tasks)
    n_empty_start = 0
    n_empty_goal = 0
    n_start_in_goal = 0
    n_other_reject = 0
    n_accepted = 0
    goal_sizes: list[int] = []
    start_residuals: list[float] = []
    nearest_goal_residuals: list[float] = []
    selected_goal_residuals: list[float] = []
    paired_delta_cost: list[float] = []
    paired_delta_expansions: list[float] = []

    fourbar_graph = graphs[FOURBAR_MECHANISM_ID]
    gearbox_id = next(mid for mid in graphs if mid != FOURBAR_MECHANISM_ID)
    gearbox_graph = graphs[gearbox_id]

    for task in tasks:
        resolved_fourbar = resolve_cartesian_task(
            fourbar_graph, task, domain, fk=fk
        )
        resolved_gearbox = resolve_cartesian_task(
            gearbox_graph, task, domain, fk=fk
        )
        assert_paired_cartesian_query_identity(
            fourbar_graph,
            gearbox_graph,
            resolved_fourbar,
            resolved_gearbox,
        )
        reference = resolved_fourbar
        if reference.start_residual is not None:
            start_residuals.append(float(reference.start_residual))
        if reference.nearest_goal_residual is not None:
            nearest_goal_residuals.append(float(reference.nearest_goal_residual))
        if not reference.accepted:
            reason = reference.rejection_reason
            if reason == "start_region_has_no_graph_node":
                n_empty_start += 1
            elif reason == "goal_region_has_no_graph_node":
                n_empty_goal += 1
            elif reason == "start_node_inside_goal_region":
                n_start_in_goal += 1
            else:
                n_other_reject += 1
            continue
        n_accepted += 1
        goal_sizes.append(len(reference.goal_node_ids))
        assert reference.start_node_id is not None
        if not run_search:
            continue

        costs: dict[str, float] = {}
        expansions: dict[str, float] = {}
        for mechanism_id, graph in (
            (FOURBAR_MECHANISM_ID, fourbar_graph),
            (gearbox_id, gearbox_graph),
        ):
            objective = resolve_v2_goal_set_objective(
                graph,
                reference.goal_node_ids,
                cost_name="actuator_travel",
                heuristic_name="zero",
                edge_n_samples=edge_n_samples,
            )
            result = production_graph_solver("dijkstra").solve(
                graph,
                reference.start_node_id,
                None,
                objective,
                goal_node_ids=reference.goal_node_ids,
                record_expanded=False,
            )
            if not result.found or result.selected_goal_node_id is None:
                continue
            selected = int(result.selected_goal_node_id)
            selected_x = fk.forward(graph.q_state(selected))
            selected_goal_residuals.append(
                float(np.linalg.norm(selected_x - task.requested_goal_x))
            )
            costs[mechanism_id] = float(result.cost)
            expansions[mechanism_id] = float(result.n_expanded)
        if FOURBAR_MECHANISM_ID in costs and gearbox_id in costs:
            paired_delta_cost.append(costs[FOURBAR_MECHANISM_ID] - costs[gearbox_id])
            paired_delta_expansions.append(
                expansions[FOURBAR_MECHANISM_ID] - expansions[gearbox_id]
            )

    attachment_rate = float(n_accepted) / float(n_tasks) if n_tasks else 0.0
    mean_delta_exp = (
        float(statistics.fmean(paired_delta_expansions))
        if paired_delta_expansions
        else 0.0
    )
    mean_delta_cost = (
        float(statistics.fmean(paired_delta_cost)) if paired_delta_cost else 0.0
    )
    return {
        "shape_n": int(shape_n),
        "goal_radius": float(domain.goal_radius),
        "start_tolerance": float(domain.start_tolerance),
        "min_start_goal_separation": float(domain.min_start_goal_separation),
        "n_tasks": int(n_tasks),
        "n_accepted": int(n_accepted),
        "attachment_rate": attachment_rate,
        "task_acceptance_rate": attachment_rate,
        "empty_start_rate": float(n_empty_start) / float(n_tasks) if n_tasks else 0.0,
        "empty_goal_rate": float(n_empty_goal) / float(n_tasks) if n_tasks else 0.0,
        "start_in_goal_rate": (
            float(n_start_in_goal) / float(n_tasks) if n_tasks else 0.0
        ),
        "other_reject_rate": (
            float(n_other_reject) / float(n_tasks) if n_tasks else 0.0
        ),
        "goal_set_cardinality": _cardinality_summary(goal_sizes),
        "start_residual": _summary(start_residuals),
        "nearest_goal_residual": _summary(nearest_goal_residuals),
        "selected_goal_residual": _summary(selected_goal_residuals),
        "mean_paired_delta_expansions": mean_delta_exp,
        "mean_paired_delta_cost": mean_delta_cost,
        "n_paired_search_outcomes": len(paired_delta_expansions),
        "primary_effect": mean_delta_exp,
    }


def run_cartesian_calibration_sweep(
    *,
    base_experiment: Any,
    domain: CartesianAnnularSectorDomain,
    settings: CartesianCalibrationSettings,
    task_count: int,
    seed: int,
    tasks: Sequence[CartesianPositionTask] | None = None,
) -> dict[str, Any]:
    """Sweep candidates, select radius then resolution, and return decisions."""
    max_radius = max(float(r) for r in settings.candidate_goal_radii)
    bank_domain = domain_for_radius(
        domain,
        max_radius,
        separation_floor=settings.separation_floor,
    )
    # Preserve geometry id; bank only needs the strictest separation.
    bank_domain = CartesianAnnularSectorDomain(
        domain_id=domain.domain_id,
        radial_min=domain.radial_min,
        radial_max=domain.radial_max,
        angle_min=domain.angle_min,
        angle_max=domain.angle_max,
        start_tolerance=domain.start_tolerance,
        goal_radius=domain.goal_radius,
        min_start_goal_separation=bank_domain.min_start_goal_separation,
        L1=domain.L1,
        L2=domain.L2,
    )
    task_bank = (
        tuple(tasks)
        if tasks is not None
        else generate_cartesian_task_bank(
            bank_domain, n_tasks=task_count, seed=seed
        )
    )
    branches = build_mechanism_branches(base_experiment)
    edge_n = int(base_experiment.edge_validation.samples)
    candidate_rows: list[dict[str, Any]] = []
    for radius in settings.candidate_goal_radii:
        candidate_domain = domain_for_radius(
            domain, float(radius), separation_floor=settings.separation_floor
        )
        for shape_n in settings.candidate_resolutions:
            candidate_rows.append(
                evaluate_cartesian_candidate(
                    base_experiment=base_experiment,
                    branches=branches,
                    domain=candidate_domain,
                    tasks=task_bank,
                    shape_n=int(shape_n),
                    run_search=bool(settings.run_search),
                    edge_n_samples=edge_n,
                )
            )

    finest = max(int(n) for n in settings.candidate_resolutions)
    radius_rows = [
        row for row in candidate_rows if int(row["shape_n"]) == finest
    ]
    radius_decision = select_cartesian_radius(
        radius_rows, min_attachment_rate=settings.min_attachment_rate
    )
    chosen_radius = float(radius_decision["goal_radius"])
    resolution_rows = [
        row
        for row in candidate_rows
        if float(row["goal_radius"]) == chosen_radius
    ]
    resolution_decision = select_cartesian_resolution(
        resolution_rows,
        max_relative_effect_change=settings.max_relative_effect_change,
    )
    chosen_shape = int(resolution_decision["production_shape_n"])
    chosen_row = next(
        row
        for row in candidate_rows
        if float(row["goal_radius"]) == chosen_radius
        and int(row["shape_n"]) == chosen_shape
    )
    attachment_decision = start_attachment_retain_decision(
        residual_summary={
            "start_residual": chosen_row["start_residual"],
            "nearest_goal_residual": chosen_row["nearest_goal_residual"],
            "selected_goal_residual": chosen_row["selected_goal_residual"],
            "attachment_rate": chosen_row["attachment_rate"],
        }
    )
    return {
        "tasks": [task.to_dict() for task in task_bank],
        "candidate_rows": candidate_rows,
        "cartesian_radius_decision": radius_decision,
        "cartesian_resolution_decision": resolution_decision,
        "cartesian_start_attachment_decision": attachment_decision,
        "chosen": {
            "goal_radius": chosen_radius,
            "start_tolerance": chosen_radius,
            "min_start_goal_separation": separation_for_radius(
                chosen_radius, floor=settings.separation_floor
            ),
            "production_shape_n": chosen_shape,
            "start_attachment_decision": START_ATTACHMENT_RETAIN_DECISION,
        },
    }
