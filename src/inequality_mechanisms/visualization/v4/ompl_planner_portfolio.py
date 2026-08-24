"""V4-238 question-grouped OMPL planner-portfolio report.

Reads only retained machine-readable stage files. HTML contains no
calculations that cannot be regenerated from ``summary.json``. There is no
cross-family effort ranking.
"""

from __future__ import annotations

import html
import json
import re
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from inequality_mechanisms.audits.html_report import PRINT_CSS
from inequality_mechanisms.audits.v4_artifact_guard import assert_v4_2c_output_allowed
from inequality_mechanisms.benchmarks.ompl_process_worker_v4_2c import (
    OPTIONAL_PLANNER_IDS,
    REQUIRED_PLANNER_IDS,
    STATUS_COMPLETED,
    STATUS_UNSUPPORTED_OPTIONAL,
    write_atomic_json,
)
from inequality_mechanisms.experiments.v4.ompl_planner_portfolio_config import (
    CONTROL_PLANNER_IDS,
    NO_INFERENCE_STATEMENT,
    PRIMARY_PLANNER_IDS,
    PROJECTION_PLANNER_IDS,
    OmplPlannerPortfolioConfig,
)

REPORT_SCHEMA = "v4.2c.ompl_planner_portfolio.report.v1"
LEDE = (
    "U is the authoritative planning state. A free-space direct actuator-travel "
    "reference is available. Planner families expose different internal metrics, "
    "so those units are not pooled. This report is descriptive and is not a "
    "global ranking."
)
INTERPRETATION_BOUNDARY = (
    "The certified free-space actuator box and the direct U-linear connector "
    "are a strong reference and a weak routing challenge. V4.2C diagnoses "
    "planner geometry, finite-time convergence, and U/Q/X projection "
    "sensitivity. It does not establish obstacle-routing superiority or "
    "general application performance. Valid direct connections are not disabled."
)
PROHIBITED_CLAIMS = (
    "no universal planner ranking",
    "no universal mechanism advantage",
    "no pooled cross-family effort score",
    "no obstacle-routing inference from free space",
    "finite-time failure is not unreachability",
    "optional PDST does not prove metric independence",
)
SECTION_SPECS: tuple[tuple[str, str], ...] = (
    ("contract_and_capability", "1. Contract and capability matrix"),
    ("frozen_matrix", "2. Frozen case/task/repetition matrix"),
    ("direct_and_deterministic_references", "3. Direct and deterministic references"),
    ("optimizer_convergence", "4. Optimizer convergence: RRT*, BIT*, FMT"),
    ("kpiece_projection_ablation", "5. KPIECE U/Q/X projection ablation"),
    ("prm_rrtconnect_controls", "6. PRM/RRTConnect controls"),
    ("optional_pdst", "7. Optional PDST"),
    (
        "tasks_failures_unsupported",
        "8. Task classes, failures, and unsupported capabilities",
    ),
    ("mechanism_paired_summaries", "9. Mechanism-paired summaries by case and task"),
    ("methods_provenance_nonclaims", "10. Methods, provenance, and nonclaims"),
)
FAMILY_UNITS: dict[str, str] = {
    "ompl_rrt_star": (
        "actuator travel in raw U (Euclidean); cumulative checkpoints in seconds; "
        "PlannerData vertices/edges"
    ),
    "ompl_bit_star": (
        "actuator travel in raw U (Euclidean); cumulative checkpoints in seconds; "
        "batch/queue events stay in family_metrics"
    ),
    "ompl_fmt": (
        "actuator travel in raw U (Euclidean); independent sample-count runs "
        "(not cumulative wall-clock continuation)"
    ),
    "ompl_kpiece_u": "normalized-U projection cells; not comparable to tree vertices",
    "ompl_kpiece_q": "normalized mounted-Q projection cells; physical state remains U",
    "ompl_kpiece_x": (
        "normalized Cartesian-X projection cells; physical state remains U"
    ),
    "ompl_prm": "roadmap vertices/edges; architecture control, not primary evidence",
    "ompl_rrt_connect": (
        "first-feasible tree control; feasible cost is not asymptotic optimality"
    ),
    "ompl_pdst_u": (
        "optional geometric PDST; reported as unsupported unless a retained "
        "capability/result row says otherwise"
    ),
}
FORBIDDEN_REPORT_TOKENS = ("winner", "outperform", "ranking", "estimand")
# The sprint requires the lede/nonclaims to say the report is not a ranking.
# Those phrases are retained; the tokens remain forbidden elsewhere.
_ALLOWED_RANKING_PHRASES = (
    "not a global ranking",
    "no universal planner ranking",
    "not a mechanism ranking",
)
FigureDrawer = Callable[[Sequence[Mapping[str, Any]], Path], list[str]]


class V4OmplPortfolioReportError(ValueError):
    """Raised when a portfolio report cannot be built from retained files."""


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _text_without_allowed_ranking_phrases(text: str) -> str:
    cleaned = text
    for phrase in _ALLOWED_RANKING_PHRASES:
        cleaned = re.sub(re.escape(phrase), " ", cleaned, flags=re.IGNORECASE)
    return cleaned


def _forbidden_token_in(text: str) -> str | None:
    cleaned = _text_without_allowed_ranking_phrases(text)
    for token in FORBIDDEN_REPORT_TOKENS:
        if re.search(rf"\b{re.escape(token)}\b", cleaned, flags=re.IGNORECASE):
            return token
    return None


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _nested(mapping: Mapping[str, Any] | None, *keys: str) -> Any:
    current: Any = mapping
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def load_retained_stage(stage_dir: Path) -> dict[str, Any]:
    """Load resolved config, frozen matrix, rows, and attempts from ``stage_dir``."""
    root = Path(stage_dir)
    config_path = root / "resolved_config.json"
    matrix_path = root / "request_matrix.json"
    if not config_path.is_file() or not matrix_path.is_file():
        raise V4OmplPortfolioReportError(
            "stage directory "
            f"{root} is missing resolved_config.json or request_matrix.json"
        )
    config = OmplPlannerPortfolioConfig.model_validate(_read_json(config_path))
    matrix = _read_json(matrix_path)
    if not isinstance(matrix, dict):
        raise V4OmplPortfolioReportError("request_matrix.json must be a JSON object")
    progress_path = root / "progress.json"
    progress = _read_json(progress_path) if progress_path.is_file() else {}
    capability_path = root / "capability_matrix.json"
    if not capability_path.is_file():
        capability_path = root.parent / "capability_matrix.json"
    capability = _read_json(capability_path) if capability_path.is_file() else None
    rows: list[dict[str, Any]] = []
    rows_dir = root / "rows"
    if rows_dir.is_dir():
        for path in sorted(rows_dir.glob("*.json")):
            payload = _read_json(path)
            if isinstance(payload, dict):
                payload["_source_rel"] = f"rows/{path.name}"
                rows.append(payload)
    attempts: list[dict[str, Any]] = []
    attempts_dir = root / "attempts"
    if attempts_dir.is_dir():
        for path in sorted(attempts_dir.glob("*.json")):
            payload = _read_json(path)
            if isinstance(payload, dict):
                payload["_source_rel"] = f"attempts/{path.name}"
                attempts.append(payload)
    return {
        "stage_dir": root,
        "config": config,
        "matrix": matrix,
        "progress": progress if isinstance(progress, dict) else {},
        "capability": capability if isinstance(capability, dict) else None,
        "rows": rows,
        "attempts": attempts,
    }


def _goal_id(result: Mapping[str, Any] | None) -> str | None:
    if not isinstance(result, Mapping):
        return None
    candidate = result.get("selected_goal_candidate")
    if not isinstance(candidate, Mapping):
        return None
    provenance = candidate.get("provenance")
    if isinstance(provenance, Mapping):
        for key in ("candidate_id", "goal_id", "id"):
            if provenance.get(key) is not None:
                return str(provenance[key])
    if candidate.get("candidate_id") is not None:
        return str(candidate["candidate_id"])
    return None


def _checkpoints(result: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(result, Mapping):
        return []
    records = _nested(result, "planner_metrics", "ompl", "checkpoints")
    if records is None:
        records = _nested(
            result, "provenance", "extras", "family_metrics", "checkpoints"
        )
    if not isinstance(records, list):
        return []
    return [dict(item) for item in records if isinstance(item, Mapping)]


def _planner_data_counts(
    result: Mapping[str, Any] | None,
) -> tuple[int | None, int | None]:
    if not isinstance(result, Mapping):
        return None, None
    data = _nested(result, "planner_metrics", "ompl")
    if not isinstance(data, Mapping):
        extras = _nested(result, "provenance", "extras", "family_metrics")
        data = extras if isinstance(extras, Mapping) else {}
    vertices = data.get("num_vertices", data.get("vertices"))
    edges = data.get("num_edges", data.get("edges"))
    try:
        n_v = int(vertices) if vertices is not None else None
    except (TypeError, ValueError):
        n_v = None
    try:
        n_e = int(edges) if edges is not None else None
    except (TypeError, ValueError):
        n_e = None
    return n_v, n_e


def _trajectory_series(
    result: Mapping[str, Any] | None,
) -> dict[str, list[list[float]]]:
    series: dict[str, list[list[float]]] = {"u": [], "q": [], "x": []}
    if not isinstance(result, Mapping):
        return series
    traj = result.get("trajectory")
    states = traj.get("states") if isinstance(traj, Mapping) else None
    if not isinstance(states, list):
        return series
    for state in states:
        if not isinstance(state, Mapping):
            continue
        for axis in ("u", "q", "x"):
            raw = state.get(axis)
            if isinstance(raw, list) and raw:
                series[axis].append([float(v) for v in raw])
            elif axis == "x":
                aux = state.get("auxiliary_state")
                if isinstance(aux, Mapping) and isinstance(aux.get("x"), list):
                    series["x"].append([float(v) for v in aux["x"]])
    return series


def extract_row_view(record: Mapping[str, Any]) -> dict[str, Any]:
    """Return a compact provenance+metric view of one retained row or attempt."""
    worker = record.get("worker") if isinstance(record.get("worker"), Mapping) else {}
    result = worker.get("result") if isinstance(worker.get("result"), Mapping) else None
    status = str(worker.get("status") or record.get("status") or "unknown")
    family: dict[str, Any] = {}
    extras = None
    if isinstance(result, Mapping):
        extras = _nested(result, "provenance", "extras")
        if isinstance(extras, Mapping) and isinstance(
            extras.get("family_metrics"), Mapping
        ):
            family = dict(extras["family_metrics"])
    vertices, edges = _planner_data_counts(result)
    first_time = (
        None if not isinstance(extras, Mapping) else extras.get("first_exact_time_s")
    )
    first_cost = (
        None if not isinstance(extras, Mapping) else extras.get("first_exact_cost")
    )
    checkpoints = _checkpoints(result)
    if first_time is None:
        for item in checkpoints:
            if item.get("ompl_exact_solution") and item.get("best_cost") is not None:
                first_time = item.get("checkpoint_s")
                first_cost = item.get("best_cost")
                break
    objective = (
        None if not isinstance(result, Mapping) else result.get("objective_cost")
    )
    return {
        "request_digest": record.get("request_digest"),
        "source_rel": record.get("_source_rel"),
        "case_id": record.get("case_id"),
        "task_id": record.get("task_id"),
        "mechanism": record.get("mechanism"),
        "planner_id": record.get("planner_id"),
        "repetition": record.get("repetition"),
        "seed": record.get("seed"),
        "role": record.get("role"),
        "status": status,
        "unavailable_reason": worker.get("unavailable_reason"),
        "objective_cost": objective,
        "path_length_u": None
        if not isinstance(result, Mapping)
        else result.get("path_length_u"),
        "path_length_q": None
        if not isinstance(result, Mapping)
        else result.get("path_length_q"),
        "path_length_x": None
        if not isinstance(result, Mapping)
        else result.get("path_length_x"),
        "selected_goal_id": _goal_id(result),
        "first_exact_time_s": first_time,
        "first_exact_cost": first_cost,
        "checkpoints": checkpoints,
        "num_vertices": vertices,
        "num_edges": edges,
        "family_metrics": family,
        "trajectory": _trajectory_series(result),
        "completed": status == STATUS_COMPLETED and isinstance(result, Mapping),
        "unsupported_optional": status == STATUS_UNSUPPORTED_OPTIONAL,
    }


def _paired_rows(views: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for view in views:
        if view.get("objective_cost") is None:
            continue
        mechanism = str(view.get("mechanism"))
        if mechanism not in ("fourbar", "gearbox"):
            continue
        key = (
            view.get("planner_id"),
            view.get("case_id"),
            view.get("task_id"),
            view.get("repetition"),
        )
        grouped[key][mechanism] = view
    out: list[dict[str, Any]] = []
    for key, arms in sorted(
        grouped.items(), key=lambda item: tuple(str(x) for x in item[0])
    ):
        if "fourbar" not in arms or "gearbox" not in arms:
            continue
        four = float(arms["fourbar"]["objective_cost"])
        gear = float(arms["gearbox"]["objective_cost"])
        out.append(
            {
                "planner_id": key[0],
                "case_id": key[1],
                "task_id": key[2],
                "repetition": key[3],
                "fourbar_cost": four,
                "gearbox_cost": gear,
                "fourbar_minus_gearbox": four - gear,
                "fourbar_digest": arms["fourbar"].get("request_digest"),
                "gearbox_digest": arms["gearbox"].get("request_digest"),
            }
        )
    return out


def _pdst_status(views: Sequence[Mapping[str, Any]]) -> str:
    rows = [
        view for view in views if view.get("planner_id") in set(OPTIONAL_PLANNER_IDS)
    ]
    if not rows:
        return "not_run_optional_disabled"
    if any(view.get("unsupported_optional") for view in rows):
        return STATUS_UNSUPPORTED_OPTIONAL
    if any(view.get("completed") for view in rows):
        return STATUS_COMPLETED
    return str(rows[0].get("status"))


def summarize_ompl_portfolio_stage(stage_dir: Path) -> dict[str, Any]:
    """Build the canonical machine-readable report summary from retained files."""
    loaded = load_retained_stage(stage_dir)
    config: OmplPlannerPortfolioConfig = loaded["config"]
    matrix = loaded["matrix"]
    views = [extract_row_view(row) for row in loaded["rows"]]
    attempt_views = [extract_row_view(row) for row in loaded["attempts"]]
    present = sorted(
        {
            str(row.get("planner_id"))
            for row in matrix.get("rows", [])
            if isinstance(row, Mapping) and row.get("planner_id") is not None
        }
        | {str(view["planner_id"]) for view in views if view.get("planner_id")}
    )
    pdst_status = _pdst_status(views + attempt_views)
    optional_ids = sorted(OPTIONAL_PLANNER_IDS)
    return {
        "schema_version": REPORT_SCHEMA,
        "config_digest": config.digest(),
        "mode": config.mode,
        "stage": config.stage_name(),
        "no_inference_statement": NO_INFERENCE_STATEMENT,
        "lede": LEDE,
        "interpretation_boundary": INTERPRETATION_BOUNDARY,
        "prohibited_claims": list(PROHIBITED_CLAIMS),
        "u_authoritative": True,
        "free_space_direct_reference_available": True,
        "descriptive_not_ranking": True,
        "family_units": dict(FAMILY_UNITS),
        "required_planner_ids": list(REQUIRED_PLANNER_IDS),
        "optional_planner_ids": optional_ids,
        "control_planner_ids": sorted(CONTROL_PLANNER_IDS),
        "primary_planner_ids": sorted(PRIMARY_PLANNER_IDS),
        "projection_planner_ids": sorted(PROJECTION_PLANNER_IDS),
        "unsupported_planners": [
            {
                "planner_id": planner_id,
                "status": pdst_status
                if planner_id == "ompl_pdst_u"
                else "not_in_matrix",
                "required": False,
            }
            for planner_id in optional_ids
        ],
        "capability_matrix": loaded["capability"],
        "capability_matrix_retained": loaded["capability"] is not None,
        "matrix": {
            "n_rows": matrix.get("n_rows"),
            "config_digest": matrix.get("config_digest"),
            "case_ids": list(config.case_ids),
            "task_ids": list(config.task_ids),
            "mechanisms": list(config.mechanisms),
            "planner_ids_present": present,
        },
        "progress": {
            "n_completed": loaded["progress"].get("n_completed"),
            "n_failed": loaded["progress"].get("n_failed"),
            "n_skipped": loaded["progress"].get("n_skipped"),
        },
        "rows": [
            {key: value for key, value in view.items() if key != "trajectory"}
            for view in views
        ],
        "attempts": [
            {key: value for key, value in view.items() if key != "trajectory"}
            for view in attempt_views
        ],
        "paired_mechanism_deltas": _paired_rows(views),
        "v4_2b_source": config.source.model_dump(mode="json"),
        "physical_contract": config.physical_contract.model_dump(mode="json"),
        "sections": [
            {"id": section_id, "title": title} for section_id, title in SECTION_SPECS
        ],
    }


def _figure_payload(
    figure_id: str,
    relpath: str,
    title: str,
    unit: str,
    digests: Sequence[str],
) -> dict[str, Any]:
    return {
        "id": figure_id,
        "relpath": relpath,
        "title": title,
        "unit": unit,
        "row_digests": list(digests),
    }


def _empty_axes(ax: Any, message: str) -> None:
    ax.set_axis_off()
    ax.text(0.5, 0.5, message, ha="center", va="center", wrap=True, fontsize=10)


def _save_fig(fig: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    fig.clf()


def _require_matplotlib() -> Any:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _plot_optimizer_curves(views: Sequence[Mapping[str, Any]], path: Path) -> list[str]:
    plt = _require_matplotlib()
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    used: list[str] = []
    grouped: dict[tuple[Any, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for view in views:
        if view.get("planner_id") not in PRIMARY_PLANNER_IDS or not view.get(
            "checkpoints"
        ):
            continue
        key = (
            view.get("planner_id"),
            view.get("case_id"),
            view.get("task_id"),
            view.get("mechanism"),
        )
        grouped[key].append(view)
        if view.get("request_digest"):
            used.append(str(view["request_digest"]))
    if not grouped:
        _empty_axes(ax, "No retained optimizer checkpoint rows.")
        _save_fig(fig, path)
        plt.close(fig)
        return used
    for key, items in sorted(
        grouped.items(), key=lambda item: tuple(str(x) for x in item[0])
    ):
        times: dict[float, list[float]] = defaultdict(list)
        for item in items:
            for record in item.get("checkpoints") or []:
                if record.get("best_cost") is None:
                    continue
                times[float(record["checkpoint_s"])].append(float(record["best_cost"]))
        if not times:
            continue
        xs = sorted(times)
        means = [sum(times[t]) / len(times[t]) for t in xs]
        ax.plot(xs, means, marker="o", label=f"{key[0]} {key[3]} {key[2]}")
        ax.fill_between(
            xs, [min(times[t]) for t in xs], [max(times[t]) for t in xs], alpha=0.15
        )
    ax.set_xlabel("checkpoint (s)")
    ax.set_ylabel("best actuator-travel cost in U")
    ax.set_title("Optimizer best-cost vs checkpoint (band = min/max over repetitions)")
    ax.legend(fontsize=7, loc="best")
    _save_fig(fig, path)
    plt.close(fig)
    return used


def _plot_first_vs_final(views: Sequence[Mapping[str, Any]], path: Path) -> list[str]:
    plt = _require_matplotlib()
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    used: list[str] = []
    xs: list[float] = []
    ys: list[float] = []
    for view in views:
        if view.get("first_exact_cost") is None or view.get("objective_cost") is None:
            continue
        xs.append(float(view["first_exact_cost"]))
        ys.append(float(view["objective_cost"]))
        if view.get("request_digest"):
            used.append(str(view["request_digest"]))
    if not xs:
        _empty_axes(ax, "No retained first-exact vs final-cost pairs.")
    else:
        ax.scatter(xs, ys)
        lo = min(xs + ys)
        hi = max(xs + ys)
        ax.plot([lo, hi], [lo, hi], linestyle="--", color="#888", label="first = final")
        ax.set_xlabel("first exact cost (actuator travel U)")
        ax.set_ylabel("final objective cost (actuator travel U)")
        ax.set_title("First exact solution vs final cost")
        ax.legend(fontsize=8)
    _save_fig(fig, path)
    plt.close(fig)
    return used


def _plot_goal_ids(views: Sequence[Mapping[str, Any]], path: Path) -> list[str]:
    plt = _require_matplotlib()
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    used: list[str] = []
    counts: dict[str, int] = defaultdict(int)
    for view in views:
        goal_id = view.get("selected_goal_id")
        if not goal_id:
            continue
        counts[str(goal_id)] += 1
        if view.get("request_digest"):
            used.append(str(view["request_digest"]))
    if not counts:
        _empty_axes(ax, "No retained selected-goal candidate IDs.")
    else:
        labels = sorted(counts)
        ax.bar(labels, [counts[label] for label in labels])
        ax.set_xlabel("selected goal candidate ID")
        ax.set_ylabel("row count")
        ax.set_title("Selected-goal candidate distribution")
    _save_fig(fig, path)
    plt.close(fig)
    return used


def _plot_planner_data(views: Sequence[Mapping[str, Any]], path: Path) -> list[str]:
    plt = _require_matplotlib()
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    used: list[str] = []
    by_planner: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for view in views:
        if view.get("num_vertices") is None:
            continue
        time_s = view.get("first_exact_time_s")
        checkpoints = view.get("checkpoints") or []
        if time_s is None and checkpoints:
            time_s = checkpoints[-1].get("checkpoint_s")
        if time_s is None:
            time_s = view.get("repetition") or 0
        by_planner[str(view.get("planner_id"))].append(
            (float(time_s), float(view["num_vertices"]))
        )
        if view.get("request_digest"):
            used.append(str(view["request_digest"]))
    if not by_planner:
        _empty_axes(ax, "No retained PlannerData vertex counts.")
    else:
        for planner_id, points in sorted(by_planner.items()):
            points = sorted(points)
            ax.plot(
                [point[0] for point in points],
                [point[1] for point in points],
                marker="o",
                label=planner_id,
            )
        ax.set_xlabel("time or checkpoint (s)")
        ax.set_ylabel("PlannerData vertices")
        ax.set_title("PlannerData growth (family-specific; do not pool)")
        ax.legend(fontsize=8)
    _save_fig(fig, path)
    plt.close(fig)
    return used


def _plot_paired_delta(views: Sequence[Mapping[str, Any]], path: Path) -> list[str]:
    plt = _require_matplotlib()
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    pairs = _paired_rows(views)
    used = [
        str(item[key])
        for item in pairs
        for key in ("fourbar_digest", "gearbox_digest")
        if item.get(key)
    ]
    if not pairs:
        _empty_axes(
            ax, "No retained four-bar/gearbox pairs for the same planner condition."
        )
    else:
        labels = [f"{item['planner_id']}\n{item['task_id']}" for item in pairs]
        deltas = [float(item["fourbar_minus_gearbox"]) for item in pairs]
        ax.bar(range(len(labels)), deltas)
        ax.set_xticks(range(len(labels)), labels, fontsize=7)
        ax.axhline(0.0, color="#444", linewidth=0.8)
        ax.set_ylabel("four-bar minus gearbox objective cost (U travel)")
        ax.set_title("Paired mechanism difference within one planner condition")
    _save_fig(fig, path)
    plt.close(fig)
    return used


def _plot_uqx_path(views: Sequence[Mapping[str, Any]], path: Path) -> list[str]:
    plt = _require_matplotlib()
    fig, axes = plt.subplots(3, 1, figsize=(6.6, 6.4), sharex=True)
    chosen = next(
        (view for view in views if (view.get("trajectory") or {}).get("u")), None
    )
    if chosen is None:
        for ax in axes:
            _empty_axes(ax, "No retained U/Q/X trajectory samples.")
        _save_fig(fig, path)
        plt.close(fig)
        return []
    traj = chosen["trajectory"]
    for ax, axis, ylabel in zip(
        axes, ("u", "q", "x"), ("U", "mounted Q", "Cartesian X"), strict=True
    ):
        samples = traj.get(axis) or []
        if not samples:
            ax.text(
                0.5,
                0.5,
                (
                    f"No {ylabel} samples retained; "
                    f"path_length={chosen.get(f'path_length_{axis}')}"
                ),
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            ax.set_ylabel(ylabel)
            continue
        for dim in range(len(samples[0])):
            ax.plot([row[dim] for row in samples], label=f"{axis}{dim}")
        ax.set_ylabel(ylabel)
        ax.legend(fontsize=7)
    axes[-1].set_xlabel("path sample index")
    axes[0].set_title(
        f"Synchronized path views {chosen['planner_id']} "
        f"{chosen['mechanism']} {chosen['task_id']}"
    )
    _save_fig(fig, path)
    plt.close(fig)
    return [str(chosen["request_digest"])] if chosen.get("request_digest") else []


def _plot_kpiece_occupancy(views: Sequence[Mapping[str, Any]], path: Path) -> list[str]:
    plt = _require_matplotlib()
    fig, axes = plt.subplots(1, 3, figsize=(9.2, 3.2))
    used: list[str] = []
    selected: dict[str, Mapping[str, Any] | None] = {
        "ompl_kpiece_u": None,
        "ompl_kpiece_q": None,
        "ompl_kpiece_x": None,
    }
    for view in views:
        planner_id = str(view.get("planner_id"))
        if planner_id in selected and selected[planner_id] is None:
            selected[planner_id] = view
            if view.get("request_digest"):
                used.append(str(view["request_digest"]))
    for ax, planner_id in zip(
        axes, ("ompl_kpiece_u", "ompl_kpiece_q", "ompl_kpiece_x"), strict=True
    ):
        view = selected[planner_id]
        ax.set_title(planner_id)
        family = view.get("family_metrics") if view is not None else {}
        grid = (
            family.get("kpiece_cell_occupancy") if isinstance(family, Mapping) else None
        )
        reason = (
            str(family.get("unavailable_reason"))
            if isinstance(family, Mapping) and family.get("unavailable_reason")
            else "kpiece_cell_stats_not_exposed_by_binding"
        )
        if isinstance(grid, list) and grid:
            ax.imshow(grid, origin="lower", aspect="auto")
            ax.set_xlabel("cell i")
            ax.set_ylabel("cell j")
        else:
            _empty_axes(ax, f"{planner_id}: {reason}")
    _save_fig(fig, path)
    plt.close(fig)
    return used


def _row_link(view: Mapping[str, Any]) -> str:
    rel = view.get("source_rel") or (
        f"rows/{view.get('request_digest')}.json" if view.get("request_digest") else ""
    )
    href = f"../{_esc(rel)}" if rel else "#"
    label = (
        f"{view.get('planner_id')} · {view.get('mechanism')} · "
        f"{view.get('task_id')} · rep {view.get('repetition')} · "
        f"{str(view.get('request_digest') or '')[:12]}"
    )
    return f'<a href="{href}">{_esc(label)}</a>'


def _table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    head = "".join(f"<th>{_esc(header)}</th>" for header in headers)
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>")
    return (
        f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"
    )


def _figure_html(
    figure: Mapping[str, Any],
    views_by_digest: Mapping[str, Mapping[str, Any]],
) -> str:
    links = []
    for digest in figure.get("row_digests") or []:
        view = views_by_digest.get(str(digest))
        links.append(
            _row_link(view) if view is not None else f"<code>{_esc(digest)}</code>"
        )
    provenance = (
        "<ul>" + "".join(f"<li>{item}</li>" for item in links) + "</ul>"
        if links
        else '<p class="muted">No plotted rows.</p>'
    )
    return (
        f'<figure id="{_esc(figure["id"])}">'
        f'<img src="{_esc(figure["relpath"])}" alt="{_esc(figure["title"])}"/>'
        f"<figcaption><strong>{_esc(figure['title'])}</strong>"
        f" · unit: {_esc(figure['unit'])}</figcaption>"
        f'<p class="muted">Plotted row provenance</p>{provenance}</figure>'
    )


def _render_html(
    *,
    summary: Mapping[str, Any],
    figures: Sequence[Mapping[str, Any]],
    views: Sequence[Mapping[str, Any]],
) -> str:
    views_by_digest = {
        str(view["request_digest"]): view
        for view in views
        if view.get("request_digest")
    }
    figure_blocks = {
        item["id"]: _figure_html(item, views_by_digest) for item in figures
    }
    nav = " ".join(
        f'<a href="#{_esc(item["id"])}">{_esc(item["title"])}</a>'
        for item in summary["sections"]
    )
    units_rows = [
        [_esc(planner_id), _esc(unit)]
        for planner_id, unit in sorted(summary["family_units"].items())
    ]
    matrix = summary["matrix"]
    capability = summary.get("capability_matrix")
    cap_rows: list[list[Any]] = []
    if isinstance(capability, Mapping):
        for row in capability.get("rows") or []:
            if isinstance(row, Mapping):
                cap_rows.append(
                    [
                        _esc(row.get("feature_id")),
                        _esc(row.get("status")),
                        _esc(row.get("required")),
                        _esc(row.get("detail")),
                    ]
                )
    if not cap_rows:
        cap_rows.append(
            [
                "capability_matrix.json",
                "not_retained_in_stage",
                "",
                "Optional PDST remains visible below even without a retained matrix.",
            ]
        )
    unsupported_rows = [
        [
            _esc(item.get("planner_id")),
            _esc(item.get("status")),
            _esc(item.get("required")),
        ]
        for item in summary.get("unsupported_planners") or []
    ]
    fail_rows = []
    for view in list(summary.get("attempts") or []) + [
        item for item in summary.get("rows") or [] if not item.get("completed")
    ]:
        fail_rows.append(
            [
                _row_link(view)
                if view.get("request_digest")
                else _esc(view.get("planner_id")),
                _esc(view.get("status")),
                _esc(view.get("unavailable_reason")),
            ]
        )
    if not fail_rows:
        fail_rows.append(['<span class="muted">none retained</span>', "", ""])
    pair_rows = []
    for item in summary.get("paired_mechanism_deltas") or []:
        pair_rows.append(
            [
                _esc(item.get("planner_id")),
                _esc(item.get("case_id")),
                _esc(item.get("task_id")),
                _esc(item.get("repetition")),
                _esc(item.get("fourbar_minus_gearbox")),
                f"<code>{_esc(item.get('fourbar_digest'))}</code>",
                f"<code>{_esc(item.get('gearbox_digest'))}</code>",
            ]
        )
    if not pair_rows:
        pair_rows.append(
            [
                '<span class="muted">no paired retained costs</span>',
                "",
                "",
                "",
                "",
                "",
                "",
            ]
        )
    claims = "".join(
        f"<li>{_esc(claim)}</li>" for claim in summary["prohibited_claims"]
    )
    source = summary.get("v4_2b_source") or {}
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>V4.2C OMPL planner-geometry portfolio</title>
<style>{PRINT_CSS}
figure {{ margin: 1rem 0 1.6rem; }}
figcaption {{ font-size: 0.9rem; color: #444; }}
#lede {{ font-size: 1.05rem; }}
</style></head><body>
<p id="lede"><strong>{_esc(summary["lede"])}</strong></p>
<h1>V4.2C OMPL planner-geometry portfolio</h1>
<p><strong>No-inference:</strong> {_esc(summary["no_inference_statement"])}</p>
<p class="muted">mode <code>{_esc(summary["mode"])}</code>
· stage <code>{_esc(summary["stage"])}</code>
· config digest <code>{_esc(summary["config_digest"])}</code>
· schema <code>{_esc(summary["schema_version"])}</code></p>
<p>
<a href="summary.json">summary.json</a> ·
<a href="../resolved_config.json">resolved_config.json</a> ·
<a href="../request_matrix.json">request_matrix.json</a> ·
<a href="../progress.json">progress.json</a>
</p>
<nav>{nav}</nav>
<section id="contract_and_capability" class="section">
<h2>1. Contract and capability matrix</h2>
<p>Physical state identity is complete PhysicalState encoded to OMPL in
actuator coordinates U. Local motion is input-linear. The objective is
Euclidean actuator travel. Goals are a frozen finite physical set. Q and X
appear only as projections, tasks, metrics, and interpretation.</p>
{_table(("feature", "status", "required", "detail"), cap_rows)}
<h3>Family metric units (not interchangeable)</h3>
{_table(("planner_id", "unit"), units_rows)}
</section>
<section id="frozen_matrix" class="section">
<h2>2. Frozen case/task/repetition matrix</h2>
<p>Case and task IDs were frozen before planner outcomes. Matrix rows:
<code>{_esc(matrix.get("n_rows"))}</code>.</p>
<p>Cases: <code>{_esc(", ".join(matrix.get("case_ids") or []))}</code></p>
<p>Tasks: <code>{_esc(", ".join(matrix.get("task_ids") or []))}</code></p>
<p>Mechanisms: <code>{_esc(", ".join(matrix.get("mechanisms") or []))}</code></p>
<p>Planners present:
<code>{_esc(", ".join(matrix.get("planner_ids_present") or []))}</code></p>
</section>
<section id="direct_and_deterministic_references" class="section">
<h2>3. Direct and deterministic references</h2>
<p>The free-space direct U-linear represented-set reference remains available
from the Version 3 / V4.2B planning contract. This portfolio does not disable
valid direct edges. Lattice Dijkstra/A* references live in the frozen V4.2B
planning audit and are not recomputed here.</p>
<p>V4.2B files digest
<code>{_esc(source.get("v4_2b_files_digest"))}</code>
· git-tracked
<code>{_esc(source.get("v4_2b_git_tracked_sha256"))}</code>.</p>
</section>
<section id="optimizer_convergence" class="section">
<h2>4. Optimizer convergence: RRT*, BIT*, FMT</h2>
<p>RRT* and BIT* continue cumulatively inside one process. FMT is an
independent sample-count run; sample count is not a wall-clock continuation.
Units remain actuator travel in U plus family-specific internals.</p>
{figure_blocks.get("optimizer_cost_vs_checkpoint", "")}
{figure_blocks.get("first_vs_final_cost", "")}
{figure_blocks.get("planner_data_growth", "")}
</section>
<section id="kpiece_projection_ablation" class="section">
<h2>5. KPIECE U/Q/X projection ablation</h2>
<p>The three KPIECE IDs share physical U-state, local motion, objective, and
non-projection knobs. Only the declared exploration projection changes.
Cell occupancy is shown when retained; otherwise the binding omission is kept
visible as null plus reason.</p>
{figure_blocks.get("kpiece_projection_occupancy", "")}
{figure_blocks.get("synchronized_uqx_path", "")}
</section>
<section id="prm_rrtconnect_controls" class="section">
<h2>6. PRM/RRTConnect controls</h2>
<p>PRM and RRTConnect remain architecture controls. They are not promoted to
primary mechanism evidence. Multi-goal binding workarounds stay explicit in
row provenance rather than being relabeled as a true multi-goal solve.</p>
<p>Control planner IDs:
<code>{_esc(", ".join(summary.get("control_planner_ids") or []))}</code>.</p>
</section>
<section id="optional_pdst" class="section">
<h2>7. Optional PDST</h2>
<p>Geometric PDST is optional and nonblocking. It remains visible when
disabled or unsupported.</p>
{_table(("planner_id", "status", "required"), unsupported_rows)}
</section>
<section id="tasks_failures_unsupported" class="section">
<h2>8. Task classes, failures, and unsupported capabilities</h2>
<p>Failed attempts are retained and are not rewritten as successes.
Unsupported capabilities stay in the table.</p>
{_table(("row", "status", "unavailable_reason"), fail_rows)}
{figure_blocks.get("selected_goal_ids", "")}
</section>
<section id="mechanism_paired_summaries" class="section">
<h2>9. Mechanism-paired summaries by case and task</h2>
<p>Each difference is four-bar minus gearbox inside one planner/case/task
condition. These are descriptive paired deltas, not a mechanism ranking.</p>
{
        _table(
            (
                "planner",
                "case",
                "task",
                "rep",
                "fourbar−gearbox",
                "fourbar digest",
                "gearbox digest",
            ),
            pair_rows,
        )
    }
{figure_blocks.get("paired_mechanism_delta", "")}
</section>
<section id="methods_provenance_nonclaims" class="section">
<h2>10. Methods, provenance, and nonclaims</h2>
<p id="interpretation-boundary">{_esc(summary["interpretation_boundary"])}</p>
<p>Prohibited claims:</p>
<ul>{claims}</ul>
<p>Source of truth is <a href="summary.json">summary.json</a> plus the
retained row JSON under the stage directory. HTML does not introduce
calculations that cannot be regenerated from those files.</p>
</section>
</body></html>
"""


def write_ompl_planner_portfolio_report(
    stage_dir: Path,
    *,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Write ``summary.json``, figures, and ``index.html`` under the guarded root."""
    stage = Path(stage_dir)
    loaded = load_retained_stage(stage)
    views = [extract_row_view(row) for row in loaded["rows"]]
    views.extend(extract_row_view(row) for row in loaded["attempts"])
    report_dir = Path(output_dir) if output_dir is not None else stage / "report"
    report_dir = assert_v4_2c_output_allowed(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = report_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    drawers: tuple[tuple[str, str, str, str, FigureDrawer], ...] = (
        (
            "optimizer_cost_vs_checkpoint",
            "figures/optimizer_cost_vs_checkpoint.png",
            "Optimizer best-cost versus checkpoint",
            FAMILY_UNITS["ompl_rrt_star"],
            _plot_optimizer_curves,
        ),
        (
            "first_vs_final_cost",
            "figures/first_vs_final_cost.png",
            "First exact cost versus final cost",
            "actuator travel in raw U",
            _plot_first_vs_final,
        ),
        (
            "selected_goal_ids",
            "figures/selected_goal_ids.png",
            "Selected goal candidate IDs",
            "candidate ID counts (dimensionless)",
            _plot_goal_ids,
        ),
        (
            "planner_data_growth",
            "figures/planner_data_growth.png",
            "PlannerData vertex growth",
            "PlannerData vertices (family-specific)",
            _plot_planner_data,
        ),
        (
            "paired_mechanism_delta",
            "figures/paired_mechanism_delta.png",
            "Four-bar minus gearbox objective cost",
            "actuator travel in raw U (paired difference)",
            _plot_paired_delta,
        ),
        (
            "synchronized_uqx_path",
            "figures/synchronized_uqx_path.png",
            "Synchronized U/Q/X path views",
            "U, mounted Q, Cartesian X path coordinates",
            _plot_uqx_path,
        ),
        (
            "kpiece_projection_occupancy",
            "figures/kpiece_projection_occupancy.png",
            "KPIECE projection occupancy",
            FAMILY_UNITS["ompl_kpiece_u"],
            _plot_kpiece_occupancy,
        ),
    )
    figures = []
    for figure_id, relpath, title, unit, drawer in drawers:
        digests = drawer(views, figures_dir / Path(relpath).name)
        figures.append(
            _figure_payload(figure_id, relpath, title, unit, sorted(set(digests)))
        )
    summary = summarize_ompl_portfolio_stage(stage)
    summary["figures"] = figures
    prose = (
        str(summary["lede"])
        + " "
        + str(summary["no_inference_statement"])
        + " "
        + str(summary["interpretation_boundary"])
        + " "
        + " ".join(str(item) for item in summary["prohibited_claims"])
    )
    token = _forbidden_token_in(prose)
    if token is not None:
        raise V4OmplPortfolioReportError(
            f"report prose contains forbidden token {token!r}"
        )
    write_atomic_json(report_dir / "summary.json", json.loads(_canonical_json(summary)))
    html_text = _render_html(summary=summary, figures=figures, views=views)
    token = _forbidden_token_in(html_text)
    if token is not None:
        raise V4OmplPortfolioReportError(f"HTML contains forbidden token {token!r}")
    (report_dir / "index.html").write_text(html_text, encoding="utf-8")
    return {
        "report_dir": str(report_dir),
        "summary_path": str(report_dir / "summary.json"),
        "index_path": str(report_dir / "index.html"),
        "n_figures": len(figures),
        "config_digest": summary["config_digest"],
    }


def href_targets(index_html: Path) -> list[Path]:
    """Return local file targets referenced by ``href`` and ``src`` on the page."""
    text = index_html.read_text(encoding="utf-8")
    base = index_html.parent
    found: list[Path] = []
    for attr in ("href", "src"):
        for match in re.finditer(rf'{attr}="([^"]+)"', text):
            target = match.group(1)
            if target.startswith(("#", "mailto:", "http://", "https://")):
                continue
            found.append((base / target).resolve())
    return found
