"""V4.2C-R frozen-data report clarification.

Reads retained V4.2C stage files and writes a sibling presentation package.
It does not rerun planners, mutate frozen rows, or rank families.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from inequality_mechanisms.audits.html_report import PRINT_CSS
from inequality_mechanisms.audits.v4_artifact_guard import (
    assert_v4_2c_r_output_allowed,
    canonical_v4_2c_retained_root,
)
from inequality_mechanisms.benchmarks.classification import TASK_ALREADY_SATISFIED
from inequality_mechanisms.benchmarks.ompl_process_worker_v4_2c import write_atomic_json
from inequality_mechanisms.experiments.v4.ompl_planner_portfolio_config import (
    CONTROL_PLANNER_IDS,
    NO_INFERENCE_STATEMENT,
    PRIMARY_PLANNER_IDS,
    PROJECTION_PLANNER_IDS,
)
from inequality_mechanisms.visualization.v4 import ompl_planner_portfolio as base
from inequality_mechanisms.visualization.v4.ompl_planner_portfolio import (
    FAMILY_UNITS,
    INTERPRETATION_BOUNDARY,
    PROHIBITED_CLAIMS,
    V4OmplPortfolioReportError,
    extract_row_view,
    href_targets,
    load_retained_stage,
)

CLARIFICATION_SCHEMA = "v4.2c_r.frozen_data_report.v1"
FROZEN_V4_2C_FILES_DIGEST = (
    "99ec523a706632391c85e16cae505e6cd11a6f14d15682eb711515aefcf76c93"
)
EXAMPLE_CASE_ID = "span_j1_145_j2_145"
EXAMPLE_TASK_ID = "far_0"
OPTIMIZER_IDS = ("ompl_rrt_star", "ompl_bit_star")
KPIECE_UNAVAILABLE = "kpiece_cell_stats_not_exposed_by_binding"
MAX_X_CATEGORIES = 80

CLARIFICATION_LEDE = (
    "This clarification report reads frozen V4.2C Stage C rows only. "
    "Already-satisfied tasks are separated from search evidence. "
    "Figures are descriptive and are not a global ranking."
)


def _task_family(task_id: Any) -> str | None:
    text = str(task_id or "")
    if text.startswith("near_"):
        return "near"
    if text.startswith("far_"):
        return "far"
    return None


def _is_already_satisfied(view: Mapping[str, Any]) -> bool:
    return view.get("task_class") == TASK_ALREADY_SATISFIED


def _nontrivial(views: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [
        view
        for view in views
        if view.get("completed") and not _is_already_satisfied(view)
    ]


def _digest(view: Mapping[str, Any]) -> str | None:
    value = view.get("request_digest")
    return None if value is None else str(value)


def _u_linear_reference(view: Mapping[str, Any]) -> float | None:
    """Euclidean U length from retained trajectory endpoints."""
    traj = view.get("trajectory")
    if not isinstance(traj, Mapping):
        return None
    samples = traj.get("u")
    if not isinstance(samples, list) or len(samples) < 2:
        return None
    start = samples[0]
    end = samples[-1]
    if not isinstance(start, list) or not isinstance(end, list):
        return None
    if not start or len(start) != len(end):
        return None
    total = 0.0
    for left, right in zip(start, end, strict=True):
        total += (float(left) - float(right)) ** 2
    return math.sqrt(total)


def _relative_improvement(view: Mapping[str, Any]) -> float | None:
    first = view.get("first_exact_cost")
    final = view.get("objective_cost")
    if first is None or final is None:
        return None
    first_f = float(first)
    if first_f <= 0.0:
        return None
    return (first_f - float(final)) / first_f


def _figure_payload(
    figure_id: str,
    relpath: str,
    title: str,
    unit: str,
    digests: Sequence[str],
    n_x_categories: int,
) -> dict[str, Any]:
    if n_x_categories > MAX_X_CATEGORIES:
        raise V4OmplPortfolioReportError(
            f"{figure_id} has {n_x_categories} x categories; "
            f"executive figures must stay under {MAX_X_CATEGORIES}"
        )
    payload = base._figure_payload(figure_id, relpath, title, unit, digests)
    payload["n_x_categories"] = n_x_categories
    return payload


def _plot_optimizer(
    views: Sequence[Mapping[str, Any]],
    planner_id: str,
    path: Path,
) -> tuple[list[str], int]:
    plt = base._require_matplotlib()
    rows = [
        view
        for view in _nontrivial(views)
        if view.get("planner_id") == planner_id and view.get("checkpoints")
    ]
    cases = sorted({str(view.get("case_id")) for view in rows})
    families = ("near", "far")
    used: list[str] = []
    if not cases:
        fig, ax = plt.subplots(figsize=(7.2, 3.2))
        base._empty_axes(ax, f"No nontrivial {planner_id} checkpoint rows.")
        base._save_fig(fig, path)
        plt.close(fig)
        return used, 0
    fig, axes = plt.subplots(
        nrows=len(cases),
        ncols=2,
        figsize=(9.6, max(2.6, 2.15 * len(cases))),
        sharex=True,
        squeeze=False,
    )
    styles = {"fourbar": "-", "gearbox": "--"}
    for row_i, case_id in enumerate(cases):
        for col_i, family in enumerate(families):
            ax = axes[row_i][col_i]
            grouped: dict[str, dict[float, list[float]]] = defaultdict(
                lambda: defaultdict(list)
            )
            refs: dict[str, list[float]] = defaultdict(list)
            for view in rows:
                if str(view.get("case_id")) != case_id:
                    continue
                if _task_family(view.get("task_id")) != family:
                    continue
                mechanism = str(view.get("mechanism"))
                digest = _digest(view)
                if digest:
                    used.append(digest)
                ref = _u_linear_reference(view)
                if ref is not None:
                    refs[mechanism].append(ref)
                for record in view.get("checkpoints") or []:
                    if record.get("best_cost") is None:
                        continue
                    grouped[mechanism][float(record["checkpoint_s"])].append(
                        float(record["best_cost"])
                    )
            for mechanism, times in sorted(grouped.items()):
                xs = sorted(times)
                if not xs:
                    continue
                means = [sum(times[t]) / len(times[t]) for t in xs]
                ax.plot(
                    xs,
                    means,
                    linestyle=styles.get(mechanism, "-"),
                    marker="o",
                    label=f"{planner_id} {case_id} {family} {mechanism}",
                )
            for mechanism, values in sorted(refs.items()):
                if not values:
                    continue
                ax.axhline(
                    sum(values) / len(values),
                    linestyle=":",
                    linewidth=0.9,
                    label=f"U-linear start-to-selected-goal {mechanism}",
                )
            ax.set_title(f"{case_id} / {family}")
            ax.set_ylabel("best U cost")
            if row_i == len(cases) - 1:
                ax.set_xlabel("checkpoint (s)")
            handles, labels = ax.get_legend_handles_labels()
            if labels:
                ax.legend(handles, labels, fontsize=6, loc="best")
    fig.suptitle(
        f"{planner_id} convergence (repetition mean; already-satisfied excluded)"
    )
    base._save_fig(fig, path)
    plt.close(fig)
    return used, 0


def _plot_first_to_final(
    views: Sequence[Mapping[str, Any]], path: Path
) -> tuple[list[str], int]:
    plt = base._require_matplotlib()
    rows = [
        view for view in _nontrivial(views) if _relative_improvement(view) is not None
    ]
    planners = sorted({str(view.get("planner_id")) for view in rows})
    mechanisms = ("fourbar", "gearbox")
    used = [digest for view in rows if (digest := _digest(view))]
    if not planners:
        fig, ax = plt.subplots(figsize=(7.2, 3.2))
        base._empty_axes(ax, "No nontrivial first-to-final pairs.")
        base._save_fig(fig, path)
        plt.close(fig)
        return used, 0
    fig, axes = plt.subplots(
        nrows=len(planners),
        ncols=2,
        figsize=(8.8, max(2.4, 1.9 * len(planners))),
        squeeze=False,
    )
    for row_i, planner_id in enumerate(planners):
        for col_i, mechanism in enumerate(mechanisms):
            ax = axes[row_i][col_i]
            values = [
                float(_relative_improvement(view) or 0.0)
                for view in rows
                if view.get("planner_id") == planner_id
                and view.get("mechanism") == mechanism
            ]
            if values:
                ax.hist(values, bins=min(12, max(4, len(set(values)))))
            else:
                base._empty_axes(ax, "no rows")
            ax.set_title(f"{planner_id} / {mechanism}")
            ax.set_xlabel("(J_first - J_final) / J_first")
            ax.set_ylabel("row count")
    fig.suptitle("First-to-final relative improvement (already-satisfied excluded)")
    base._save_fig(fig, path)
    plt.close(fig)
    return used, 0


def _plot_paired_delta(
    views: Sequence[Mapping[str, Any]], path: Path
) -> tuple[list[str], int]:
    plt = base._require_matplotlib()
    pairs = [
        item
        for item in base._paired_rows(_nontrivial(views))
        if not str(item.get("task_id", "")).startswith("already")
    ]
    used = [
        str(item[key])
        for item in pairs
        for key in ("fourbar_digest", "gearbox_digest")
        if item.get(key)
    ]
    cases = sorted({str(item["case_id"]) for item in pairs})
    planners = sorted({str(item["planner_id"]) for item in pairs})
    n_categories = len(planners)
    if not cases or not planners:
        fig, ax = plt.subplots(figsize=(7.2, 3.2))
        base._empty_axes(ax, "No nontrivial paired mechanism costs.")
        base._save_fig(fig, path)
        plt.close(fig)
        return used, 0
    fig, axes = plt.subplots(
        nrows=len(cases),
        ncols=1,
        figsize=(8.4, max(2.6, 2.2 * len(cases))),
        squeeze=False,
    )
    for row_i, case_id in enumerate(cases):
        ax = axes[row_i][0]
        series = []
        labels = []
        for planner_id in planners:
            values = [
                float(item["fourbar_minus_gearbox"])
                for item in pairs
                if item["case_id"] == case_id and item["planner_id"] == planner_id
            ]
            series.append(values if values else [0.0])
            labels.append(str(planner_id))
        ax.boxplot(series, tick_labels=labels, showfliers=False)
        ax.axhline(0.0, color="#444", linewidth=0.8)
        ax.set_title(f"{case_id} paired ΔJ = J_fourbar - J_gearbox")
        ax.set_ylabel("ΔJ (U travel)")
        ax.tick_params(axis="x", labelrotation=20, labelsize=7)
    base._save_fig(fig, path)
    plt.close(fig)
    return used, n_categories


def _plot_goal_agreement(
    views: Sequence[Mapping[str, Any]], path: Path
) -> tuple[list[str], int]:
    plt = base._require_matplotlib()
    grouped: dict[tuple[Any, ...], dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for view in _nontrivial(views):
        mechanism = str(view.get("mechanism"))
        if mechanism not in ("fourbar", "gearbox"):
            continue
        key = (
            view.get("planner_id"),
            view.get("case_id"),
            _task_family(view.get("task_id")),
            view.get("repetition"),
        )
        grouped[key][mechanism] = view
    rates: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    used: list[str] = []
    for key, arms in grouped.items():
        if "fourbar" not in arms or "gearbox" not in arms:
            continue
        family = key[2]
        if family is None:
            continue
        agree = int(
            arms["fourbar"].get("selected_goal_id")
            == arms["gearbox"].get("selected_goal_id")
            and arms["fourbar"].get("selected_goal_id") is not None
        )
        rates[(str(key[0]), str(key[1]), str(family))].append(agree)
        for arm in arms.values():
            digest = _digest(arm)
            if digest:
                used.append(digest)
    labels = sorted(rates)
    n_categories = len(labels)
    fig, ax = plt.subplots(figsize=(8.8, max(3.2, 0.28 * max(n_categories, 1) + 1.6)))
    if not labels:
        base._empty_axes(ax, "No paired selected-goal IDs.")
    else:
        values = [sum(rates[key]) / len(rates[key]) for key in labels]
        names = [f"{planner} {case} {family}" for planner, case, family in labels]
        ax.barh(range(len(names)), values)
        ax.set_yticks(range(len(names)), names, fontsize=7)
        ax.set_xlim(0.0, 1.0)
        ax.set_xlabel("paired goal-ID agreement rate")
        ax.set_title("Four-bar vs gearbox selected-goal agreement (nontrivial rows)")
    base._save_fig(fig, path)
    plt.close(fig)
    return used, n_categories


def _plot_kpiece(
    views: Sequence[Mapping[str, Any]], path: Path
) -> tuple[list[str], int]:
    plt = base._require_matplotlib()
    rows = [
        view
        for view in _nontrivial(views)
        if view.get("planner_id") in set(PROJECTION_PLANNER_IDS)
    ]
    used = [digest for view in rows if (digest := _digest(view))]
    fig, axes = plt.subplots(1, 3, figsize=(10.4, 3.4), squeeze=False)
    metrics = (
        ("first_exact_time_s", "first exact time (s)"),
        ("objective_cost", "final U cost"),
        ("num_vertices", "PlannerData vertices"),
    )
    for ax, (field, ylabel) in zip(axes[0], metrics, strict=True):
        for planner_id in ("ompl_kpiece_u", "ompl_kpiece_q", "ompl_kpiece_x"):
            xs = []
            ys = []
            for view in rows:
                if view.get("planner_id") != planner_id:
                    continue
                value = view.get(field)
                if value is None:
                    continue
                xs.append(str(view.get("case_id")))
                ys.append(float(value))
            if ys:
                ax.scatter(xs, ys, label=planner_id, alpha=0.7)
        ax.set_ylabel(ylabel)
        ax.tick_params(axis="x", labelrotation=25, labelsize=7)
        handles, labels = ax.get_legend_handles_labels()
        if labels:
            ax.legend(handles, labels, fontsize=6)
    fig.suptitle(
        "KPIECE U/Q/X available metrics; cell occupancy is not exposed by the binding"
    )
    base._save_fig(fig, path)
    plt.close(fig)
    return used, 5


def _plot_planner_data_scatter(
    views: Sequence[Mapping[str, Any]], path: Path
) -> tuple[list[str], int]:
    plt = base._require_matplotlib()
    rows = [
        view
        for view in _nontrivial(views)
        if view.get("num_vertices") is not None
        and view.get("first_exact_time_s") is not None
    ]
    used = [digest for view in rows if (digest := _digest(view))]
    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    if not rows:
        base._empty_axes(ax, "No nontrivial PlannerData vertex counts.")
    else:
        by_planner: dict[str, list[tuple[float, float]]] = defaultdict(list)
        for view in rows:
            by_planner[str(view.get("planner_id"))].append(
                (float(view["first_exact_time_s"]), float(view["num_vertices"]))
            )
        for planner_id, points in sorted(by_planner.items()):
            ax.scatter(
                [point[0] for point in points],
                [point[1] for point in points],
                label=planner_id,
                alpha=0.75,
            )
        ax.set_xlabel("first exact solution time (s)")
        ax.set_ylabel("final PlannerData vertices")
        ax.set_title(
            "Final planner-data size vs first-solution time (not a growth path)"
        )
        ax.legend(fontsize=7)
    base._save_fig(fig, path)
    plt.close(fig)
    return used, 0


def _select_uqx_example(
    views: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]] | None:
    candidates = [
        view
        for view in _nontrivial(views)
        if view.get("case_id") == EXAMPLE_CASE_ID
        and view.get("task_id") == EXAMPLE_TASK_ID
        and (view.get("trajectory") or {}).get("u")
        and view.get("planner_id") in set(PRIMARY_PLANNER_IDS | CONTROL_PLANNER_IDS)
    ]
    grouped: dict[tuple[Any, ...], dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for view in candidates:
        key = (view.get("planner_id"), view.get("repetition"))
        grouped[key][str(view.get("mechanism"))] = view
    ranked: list[tuple[str, dict[str, Mapping[str, Any]]]] = []
    for arms in grouped.values():
        if "fourbar" not in arms or "gearbox" not in arms:
            continue
        digest = str(arms["fourbar"].get("request_digest") or "")
        ranked.append((digest, arms))
    if not ranked:
        return None
    ranked.sort(key=lambda item: item[0])
    return ranked[0][1]


def _plot_uqx_example(
    views: Sequence[Mapping[str, Any]], path: Path
) -> tuple[list[str], int, dict[str, Any] | None]:
    plt = base._require_matplotlib()
    example = _select_uqx_example(views)
    fig, axes = plt.subplots(2, 3, figsize=(10.6, 6.2), sharex=False)
    if example is None:
        for ax in axes.ravel():
            base._empty_axes(ax, "No paired nontrivial U/Q/X example.")
        base._save_fig(fig, path)
        plt.close(fig)
        return [], 0, None
    used: list[str] = []
    record: dict[str, Any] = {
        "case_id": EXAMPLE_CASE_ID,
        "task_id": EXAMPLE_TASK_ID,
        "selection_rule": (
            "nontrivial far_0 on span_j1_145_j2_145; lowest four-bar "
            "request_digest among paired trajectories"
        ),
        "arms": {},
    }
    for row_i, mechanism in enumerate(("fourbar", "gearbox")):
        view = example[mechanism]
        digest = _digest(view)
        if digest:
            used.append(digest)
        traj = view.get("trajectory") or {}
        record["arms"][mechanism] = {
            "request_digest": digest,
            "planner_id": view.get("planner_id"),
            "repetition": view.get("repetition"),
            "selected_goal_id": view.get("selected_goal_id"),
            "path_length_u": view.get("path_length_u"),
            "path_length_q": view.get("path_length_q"),
            "path_length_x": view.get("path_length_x"),
            "objective_cost": view.get("objective_cost"),
        }
        for col_i, axis in enumerate(("u", "q", "x")):
            ax = axes[row_i][col_i]
            samples = traj.get(axis) or []
            if not samples:
                ax.text(0.5, 0.5, f"no {axis} samples", ha="center", va="center")
                continue
            for dim in range(len(samples[0])):
                ax.plot([row[dim] for row in samples], label=f"{axis}{dim}")
            ax.scatter([0], [samples[0][0]], marker="o")
            ax.scatter([len(samples) - 1], [samples[-1][0]], marker="x")
            ax.set_title(f"{mechanism} {axis}")
            ax.set_ylabel(axis)
            ax.legend(fontsize=6)
    fig.suptitle(
        f"Paired U/Q/X example: {EXAMPLE_CASE_ID} {EXAMPLE_TASK_ID} "
        f"(start=o, selected-goal axis0=x)"
    )
    base._save_fig(fig, path)
    plt.close(fig)
    return used, 0, record


def _summarize_counts(views: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    completed = [view for view in views if view.get("completed")]
    already = [view for view in completed if _is_already_satisfied(view)]
    return {
        "n_views": len(views),
        "n_completed": len(completed),
        "n_already_satisfied": len(already),
        "n_nontrivial": len(completed) - len(already),
    }


def _render_html(
    summary: Mapping[str, Any],
    figures: Sequence[Mapping[str, Any]],
) -> str:
    nav = " ".join(
        f'<a href="#{item["id"]}">{base._esc(item["title"])}</a>' for item in figures
    )
    blocks = []
    for item in figures:
        blocks.append(
            f'<section id="{base._esc(item["id"])}" class="section">'
            f"<h2>{base._esc(item['title'])}</h2>"
            f"<p class='muted'>unit: {base._esc(item['unit'])}</p>"
            f'<figure><img src="{base._esc(item["relpath"])}" '
            f'alt="{base._esc(item["title"])}"/>'
            f"<figcaption>{base._esc(item['title'])}</figcaption></figure>"
            "</section>"
        )
    claims = "".join(
        f"<li>{base._esc(claim)}</li>" for claim in summary["prohibited_claims"]
    )
    units = "".join(
        f"<li><code>{base._esc(planner_id)}</code>: {base._esc(unit)}</li>"
        for planner_id, unit in FAMILY_UNITS.items()
    )
    example = summary.get("uqx_example") or {}
    example_html = "<p class='muted'>No paired nontrivial U/Q/X example.</p>"
    if example:
        rows = []
        for mechanism, arm in (example.get("arms") or {}).items():
            rows.append(
                "<tr>"
                f"<td>{base._esc(mechanism)}</td>"
                f"<td><code>{base._esc(arm.get('planner_id'))}</code></td>"
                f"<td><code>{base._esc(arm.get('request_digest'))}</code></td>"
                f"<td>{base._esc(arm.get('selected_goal_id'))}</td>"
                f"<td>{base._esc(arm.get('path_length_u'))}</td>"
                f"<td>{base._esc(arm.get('path_length_q'))}</td>"
                f"<td>{base._esc(arm.get('path_length_x'))}</td>"
                "</tr>"
            )
        example_html = (
            f"<p>Selection rule: {base._esc(example.get('selection_rule'))}</p>"
            "<table><thead><tr><th>mechanism</th><th>planner</th><th>digest</th>"
            "<th>goal</th><th>U length</th><th>Q length</th><th>X length</th>"
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
        )
    counts = summary["counts"]
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>V4.2C-R frozen-data report clarification</title>
<style>{PRINT_CSS}
figure {{ margin: 1rem 0 1.6rem; }}
figcaption {{ font-size: 0.9rem; color: #444; }}
#lede {{ font-size: 1.05rem; }}
</style></head><body>
<p id="lede"><strong>{base._esc(summary["lede"])}</strong></p>
<h1>V4.2C-R frozen-data report clarification</h1>
<p><strong>No-inference:</strong> {base._esc(summary["no_inference_statement"])}</p>
<p>{base._esc(summary["interpretation_boundary"])}</p>
<p class="muted">schema <code>{base._esc(summary["schema_version"])}</code>
· source V4.2C files_digest <code>{base._esc(summary["source_files_digest"])}</code>
· stage <code>{base._esc(summary["stage"])}</code>
· config digest <code>{base._esc(summary["config_digest"])}</code></p>
<nav>{nav}</nav>
<section id="interpretation" class="section">
<h2>How to read this page</h2>
<p>Sprint V4.2C is closed. These figures re-present frozen rows. They do not
rerun OMPL, change the physical contract, or support a universal planner or
mechanism claim.</p>
<p>Completed rows: {counts["n_completed"]}. Already satisfied (not search
evidence): {counts["n_already_satisfied"]}. Nontrivial completed rows:
{counts["n_nontrivial"]}.</p>
<p>KPIECE cell occupancy is unavailable from the OMPL 2.0.1 binding
(<code>{KPIECE_UNAVAILABLE}</code>). Occupancy heatmaps are not scientific
evidence here.</p>
<h3>Prohibited claims</h3>
<ul>{claims}</ul>
<h3>Family units (do not pool)</h3>
<ul>{units}</ul>
</section>
{"".join(blocks)}
<section id="uqx_example_table" class="section">
<h2>Paired U/Q/X example table</h2>
{example_html}
</section>
<p class="muted">Regenerated exclusively from frozen V4.2C machine-readable
stage files. HTML contains no calculations absent from
<a href="summary.json">summary.json</a>.</p>
</body></html>
"""


def write_ompl_planner_portfolio_clarification(
    stage_dir: Path,
    *,
    output_dir: Path,
    source_files_digest: str | None = None,
) -> dict[str, Any]:
    """Write the V4.2C-R executive report from a retained stage directory."""
    loaded = load_retained_stage(stage_dir)
    views = [extract_row_view(row) for row in loaded["rows"]]
    views.extend(extract_row_view(row) for row in loaded["attempts"])
    report_dir = assert_v4_2c_r_output_allowed(output_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = report_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    digest = source_files_digest or FROZEN_V4_2C_FILES_DIGEST
    drawers: list[tuple[str, str, str, str, Any]] = [
        (
            "optimizer_convergence_rrt_star",
            "figures/optimizer_convergence_rrt_star.png",
            "RRT* optimizer convergence by case and task class",
            FAMILY_UNITS["ompl_rrt_star"],
            lambda rows, path: _plot_optimizer(rows, "ompl_rrt_star", path),
        ),
        (
            "optimizer_convergence_bit_star",
            "figures/optimizer_convergence_bit_star.png",
            "BIT* optimizer convergence by case and task class",
            FAMILY_UNITS["ompl_bit_star"],
            lambda rows, path: _plot_optimizer(rows, "ompl_bit_star", path),
        ),
        (
            "first_to_final_improvement",
            "figures/first_to_final_improvement.png",
            "First-to-final relative improvement",
            "dimensionless (J_first - J_final) / J_first",
            _plot_first_to_final,
        ),
        (
            "paired_mechanism_delta_distribution",
            "figures/paired_mechanism_delta_distribution.png",
            "Paired four-bar minus gearbox objective-cost distribution",
            "actuator travel in raw U (paired difference)",
            _plot_paired_delta,
        ),
        (
            "paired_goal_selection",
            "figures/paired_goal_selection.png",
            "Paired selected-goal agreement by planner, case, and task class",
            "agreement rate (dimensionless)",
            _plot_goal_agreement,
        ),
        (
            "kpiece_projection_diagnostic",
            "figures/kpiece_projection_diagnostic.png",
            "KPIECE U/Q/X available metrics",
            FAMILY_UNITS["ompl_kpiece_u"],
            _plot_kpiece,
        ),
        (
            "final_planner_data_size_vs_solution_time",
            "figures/final_planner_data_size_vs_solution_time.png",
            "Final PlannerData size versus first-solution time",
            "PlannerData vertices vs seconds; not a within-run growth path",
            _plot_planner_data_scatter,
        ),
    ]
    figures: list[dict[str, Any]] = []
    for figure_id, relpath, title, unit, drawer in drawers:
        digests, n_cats = drawer(views, figures_dir / Path(relpath).name)
        figures.append(
            _figure_payload(
                figure_id, relpath, title, unit, sorted(set(digests)), n_cats
            )
        )
    uqx_digests, uqx_cats, uqx_record = _plot_uqx_example(
        views, figures_dir / "paired_uqx_example.png"
    )
    figures.append(
        _figure_payload(
            "paired_uqx_example",
            "figures/paired_uqx_example.png",
            "Paired U/Q/X trajectory example",
            "U, mounted Q, Cartesian X path coordinates",
            sorted(set(uqx_digests)),
            uqx_cats,
        )
    )
    config = loaded["config"]
    summary = {
        "schema_version": CLARIFICATION_SCHEMA,
        "lede": CLARIFICATION_LEDE,
        "no_inference_statement": NO_INFERENCE_STATEMENT,
        "interpretation_boundary": INTERPRETATION_BOUNDARY,
        "prohibited_claims": list(PROHIBITED_CLAIMS),
        "source_package": "v4_2c_ompl_planner_portfolio",
        "source_stage": str(Path(stage_dir).name),
        "source_files_digest": digest,
        "canonical_v4_2c_root": str(canonical_v4_2c_retained_root()),
        "config_digest": config.digest(),
        "mode": config.mode,
        "stage": config.stage_name(),
        "counts": _summarize_counts(views),
        "figures": figures,
        "uqx_example": uqx_record,
        "kpiece_occupancy_status": KPIECE_UNAVAILABLE,
    }
    prose = (
        str(summary["lede"])
        + " "
        + str(summary["no_inference_statement"])
        + " "
        + str(summary["interpretation_boundary"])
        + " "
        + " ".join(str(item) for item in summary["prohibited_claims"])
    )
    token = base._forbidden_token_in(prose)
    if token is not None:
        raise V4OmplPortfolioReportError(
            f"report prose contains forbidden token {token!r}"
        )
    write_atomic_json(
        report_dir / "summary.json", json.loads(base._canonical_json(summary))
    )
    html_text = _render_html(summary, figures)
    token = base._forbidden_token_in(html_text)
    if token is not None:
        raise V4OmplPortfolioReportError(f"HTML contains forbidden token {token!r}")
    (report_dir / "index.html").write_text(html_text, encoding="utf-8")
    missing = [
        path for path in href_targets(report_dir / "index.html") if not path.exists()
    ]
    if missing:
        raise V4OmplPortfolioReportError(f"missing href/src targets: {missing}")
    return {
        "report_dir": str(report_dir),
        "summary_path": str(report_dir / "summary.json"),
        "index_path": str(report_dir / "index.html"),
        "n_figures": len(figures),
        "source_files_digest": digest,
        "counts": summary["counts"],
    }
