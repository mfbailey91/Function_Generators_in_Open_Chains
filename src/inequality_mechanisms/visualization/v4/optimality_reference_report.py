"""V4.2D question-grouped optimality-reference report (V4-246 / V4-247)."""

from __future__ import annotations

import html
import math
import statistics
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from inequality_mechanisms.analysis.v4.optimality_metrics import (
    OPTIMIZER_IDS,
    within_tolerance_fraction,
)
from inequality_mechanisms.analysis.v4.optimality_pairing import PAIRING_LABEL
from inequality_mechanisms.audits.html_report import PRINT_CSS
from inequality_mechanisms.audits.v4_artifact_guard import assert_v4_2d_output_allowed
from inequality_mechanisms.benchmarks.ompl_process_worker_v4_2c import write_atomic_json
from inequality_mechanisms.visualization.v4.ompl_planner_portfolio import (
    _empty_axes,
    _forbidden_token_in,
    _require_matplotlib,
    _save_fig,
    href_targets,
)

REPORT_SCHEMA = "v4.2d.optimality_reference_report.v1"
LEDE = (
    "Under the frozen V4.2C center-goal representation, span-matched gearbox "
    "and four-bar mechanisms possess different exact actuator-travel references, "
    "and planner families approach those mechanism-specific references at "
    "different finite-budget rates. This report is descriptive and is not a "
    "global ranking and not a mechanism ranking."
)
INTERPRETATION_BOUNDARY = (
    "J*_C is the min valid input-linear cost on the actual V4.2C center-IK set. "
    "J*_B is a representation-sensitivity control only and is never the V4.2C "
    "convergence denominator. Pairing is index-matched, not CRN. Equal OMPL "
    "seeds do not prove identical sample sequences. Already-satisfied tasks "
    "are excluded from relative-gap and time-to-tolerance plots. Checkpoint "
    "curves use wall time only for RRT* and BIT*; FMT remains a sample-count "
    "family; KPIECE is a projection diagnostic; PRM uses a sequential-goal "
    "workaround. No obstacle-routing inference."
)
PROHIBITED_CLAIMS = (
    "no universal planner ranking",
    "not a mechanism ranking",
    "no common-random-number inference",
    "no continuous Cartesian-goal-region optimality",
    "no obstacle-routing performance claim",
)
FIGURE_SPECS: tuple[tuple[str, str, str], ...] = (
    (
        "01_reference_cost_by_mechanism",
        "figures/01_reference_cost_by_mechanism.png",
        "Exact center-IK reference cost by mechanism",
    ),
    (
        "02_mechanism_optimum_delta",
        "figures/02_mechanism_optimum_delta.png",
        "Mechanism effect on the center-IK optimum",
    ),
    (
        "03_exact_solution_rate_vs_checkpoint",
        "figures/03_exact_solution_rate_vs_checkpoint.png",
        "Exact-solution rate versus checkpoint",
    ),
    (
        "04_within_5pct_vs_checkpoint",
        "figures/04_within_5pct_vs_checkpoint.png",
        "Fraction within 5% of J*_C versus checkpoint",
    ),
    (
        "05_relative_gap_vs_checkpoint",
        "figures/05_relative_gap_vs_checkpoint.png",
        "Relative optimality gap versus checkpoint",
    ),
    (
        "06_first_vs_final_gap",
        "figures/06_first_vs_final_gap.png",
        "First exact versus final relative gap",
    ),
    (
        "07_final_gap_by_family",
        "figures/07_final_gap_by_family.png",
        "Final relative gap by planner family",
    ),
    (
        "08_paired_discoverability_contrast",
        "figures/08_paired_discoverability_contrast.png",
        "Paired mechanism discoverability contrast",
    ),
    (
        "09_benefit_vs_discoverability",
        "figures/09_benefit_vs_discoverability.png",
        "Physical benefit versus discoverability",
    ),
    (
        "10_final_gap_decomposition",
        "figures/10_final_gap_decomposition.png",
        "Final gap decomposition",
    ),
    (
        "11_reference_goal_match",
        "figures/11_reference_goal_match.png",
        "Reference-goal match rate",
    ),
    (
        "12_goal_representation_sensitivity",
        "figures/12_goal_representation_sensitivity.png",
        "Center-only V4.2C versus broader V4.2B representation",
    ),
)


class V4_2DReportError(ValueError):
    """Raised when the V4.2D HTML report cannot be assembled."""


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _footer(
    ax: Any,
    *,
    grouping: str,
    denominator: str,
    n: int,
    digest_b: str,
    digest_c: str,
) -> None:
    ax.text(
        0.0,
        -0.18,
        f"{grouping}; denom={denominator}; n={n}; "
        f"V4.2B={digest_b[:12]} V4.2C={digest_c[:12]}",
        transform=ax.transAxes,
        fontsize=6,
        va="top",
    )


def _median(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return float(statistics.median(values))


def _quantiles(
    values: Sequence[float],
) -> tuple[float | None, float | None, float | None]:
    if not values:
        return None, None, None
    ordered = sorted(float(v) for v in values)
    mid = _median(ordered)
    if len(ordered) == 1:
        return mid, mid, mid
    lower = ordered[: max(1, len(ordered) // 2)]
    upper = ordered[(len(ordered) + 1) // 2 :] or ordered[-1:]
    return _median(lower), mid, _median(upper)


def _nontrivial_final(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [
        row
        for row in rows
        if not row.get("already_satisfied") and not row.get("zero_reference")
    ]


def _plot_reference_cost(
    refs: Sequence[Mapping[str, Any]],
    path: Path,
    *,
    digest_b: str,
    digest_c: str,
) -> None:
    plt = _require_matplotlib()
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    rows = [row for row in refs if not row.get("already_satisfied")]
    if not rows:
        _empty_axes(ax, "No nontrivial center-IK references.")
    else:
        cases = sorted({str(row["case_id"]) for row in rows})
        x = list(range(len(cases)))
        for mechanism, marker in (("fourbar", "o"), ("gearbox", "s")):
            ys = []
            for case_id in cases:
                vals = [
                    float(row["j_star_c"])
                    for row in rows
                    if row["case_id"] == case_id and row["mechanism"] == mechanism
                ]
                ys.append(_median(vals) if vals else math.nan)
            ax.plot(x, ys, marker=marker, label=mechanism)
        ax.set_xticks(x, [case.replace("span_", "") for case in cases], rotation=20)
        ax.set_ylabel("median J*_C")
        ax.legend(fontsize=8)
        ax.set_title("Exact V4.2C center-IK reference before any planner")
        ax.axhline(0.0, color="#888", linewidth=0.8)
    _footer(
        ax,
        grouping="case median over nontrivial tasks",
        denominator="nontrivial references",
        n=len(rows),
        digest_b=digest_b,
        digest_c=digest_c,
    )
    _save_fig(fig, path)
    plt.close(fig)


def _plot_delta_j(
    refs: Sequence[Mapping[str, Any]],
    path: Path,
    *,
    digest_b: str,
    digest_c: str,
) -> None:
    plt = _require_matplotlib()
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 4.2), sharey=True)
    paired: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    for row in refs:
        if row.get("already_satisfied"):
            continue
        pair = paired[(str(row["case_id"]), str(row["task_id"]))]
        pair[str(row["mechanism"])] = float(row["j_star_c"])
    for ax, family in zip(axes, ("near", "far"), strict=True):
        xs: list[str] = []
        ys: list[float] = []
        for (case_id, task_id), arms in sorted(paired.items()):
            if not task_id.startswith(family + "_"):
                continue
            if "fourbar" not in arms or "gearbox" not in arms:
                continue
            xs.append(case_id.replace("span_", ""))
            ys.append(arms["fourbar"] - arms["gearbox"])
        if not ys:
            _empty_axes(ax, f"No {family} paired references.")
            continue
        ax.axhline(0.0, color="#888", linewidth=0.8)
        ax.scatter(xs, ys, alpha=0.7)
        ax.set_title(f"{family} tasks")
        ax.tick_params(axis="x", labelrotation=25, labelsize=7)
        ax.set_ylabel(r"$\Delta J_C^*$ fourbar-gearbox")
        _footer(
            ax,
            grouping="one point per case/task",
            denominator="nontrivial paired references",
            n=len(ys),
            digest_b=digest_b,
            digest_c=digest_c,
        )
    fig.suptitle("Negative: four-bar has the lower center-IK actuator optimum")
    _save_fig(fig, path)
    plt.close(fig)


def _plot_exact_rate(
    checkpoint_rows: Sequence[Mapping[str, Any]],
    path: Path,
    *,
    digest_b: str,
    digest_c: str,
) -> None:
    plt = _require_matplotlib()
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 4.2), sharey=True)
    rows = [
        row
        for row in checkpoint_rows
        if row.get("planner_id") in OPTIMIZER_IDS and not row.get("already_satisfied")
    ]
    for ax, planner_id in zip(axes, ("ompl_rrt_star", "ompl_bit_star"), strict=True):
        for mechanism in ("fourbar", "gearbox"):
            xs: list[float] = []
            ys: list[float] = []
            times = sorted({float(row["checkpoint_s"]) for row in rows})
            for t_s in times:
                bucket = [
                    row
                    for row in rows
                    if row.get("planner_id") == planner_id
                    and row.get("mechanism") == mechanism
                    and abs(float(row["checkpoint_s"]) - t_s) < 1e-12
                ]
                if not bucket:
                    continue
                xs.append(t_s)
                ys.append(
                    sum(1 for row in bucket if row.get("ompl_exact_solution"))
                    / len(bucket)
                )
            ax.plot(xs, ys, marker="o", label=mechanism)
        ax.set_title(planner_id)
        ax.set_xlabel("checkpoint (s)")
        ax.set_ylabel("exact-solution fraction")
        ax.set_ylim(-0.05, 1.05)
        handles, labels = ax.get_legend_handles_labels()
        if labels:
            ax.legend(handles, labels, fontsize=7)
        _footer(
            ax,
            grouping="RRT*/BIT* wall-time checkpoints",
            denominator="nontrivial requested runs",
            n=sum(1 for row in rows if row.get("planner_id") == planner_id),
            digest_b=digest_b,
            digest_c=digest_c,
        )
    fig.suptitle("Already-satisfied rows are excluded from planner-success rates")
    _save_fig(fig, path)
    plt.close(fig)


def _plot_within_5(
    checkpoint_rows: Sequence[Mapping[str, Any]],
    path: Path,
    *,
    digest_b: str,
    digest_c: str,
) -> None:
    plt = _require_matplotlib()
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 4.2), sharey=True)
    times = sorted({float(row["checkpoint_s"]) for row in checkpoint_rows})
    for ax, planner_id in zip(axes, ("ompl_rrt_star", "ompl_bit_star"), strict=True):
        for mechanism in ("fourbar", "gearbox"):
            xs: list[float] = []
            ys: list[float] = []
            for t_s in times:
                payload = within_tolerance_fraction(
                    checkpoint_rows,
                    planner_id=planner_id,
                    checkpoint_s=t_s,
                    eta=0.05,
                    mechanism=mechanism,
                )
                if payload["p_eta"] is None:
                    continue
                xs.append(t_s)
                ys.append(float(payload["p_eta"]))
            ax.plot(xs, ys, marker="o", label=mechanism)
        ax.set_title(planner_id)
        ax.set_xlabel("checkpoint (s)")
        ax.set_ylabel(r"$P_{5\%}(t)$")
        ax.set_ylim(-0.05, 1.05)
        handles, labels = ax.get_legend_handles_labels()
        if labels:
            ax.legend(handles, labels, fontsize=7)
        _footer(
            ax,
            grouping="RRT*/BIT* only",
            denominator="all nontrivial requested runs",
            n=sum(
                1
                for row in checkpoint_rows
                if row.get("planner_id") == planner_id
                and not row.get("already_satisfied")
            ),
            digest_b=digest_b,
            digest_c=digest_c,
        )
    fig.suptitle("Unsolved runs count as not within 5% of J*_C")
    _save_fig(fig, path)
    plt.close(fig)


def _plot_relative_gap(
    checkpoint_rows: Sequence[Mapping[str, Any]],
    path: Path,
    *,
    digest_b: str,
    digest_c: str,
) -> None:
    plt = _require_matplotlib()
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 4.2), sharey=True)
    rows = [
        row
        for row in checkpoint_rows
        if row.get("ompl_exact_solution")
        and row.get("epsilon_rel") is not None
        and not row.get("already_satisfied")
        and not row.get("zero_reference")
    ]
    for ax, planner_id in zip(axes, ("ompl_rrt_star", "ompl_bit_star"), strict=True):
        for mechanism in ("fourbar", "gearbox"):
            times = sorted({float(row["checkpoint_s"]) for row in rows})
            xs: list[float] = []
            med: list[float] = []
            lo: list[float] = []
            hi: list[float] = []
            ns: list[int] = []
            for t_s in times:
                vals = [
                    float(row["epsilon_rel"])
                    for row in rows
                    if row.get("planner_id") == planner_id
                    and row.get("mechanism") == mechanism
                    and abs(float(row["checkpoint_s"]) - t_s) < 1e-12
                ]
                q1, q2, q3 = _quantiles(vals)
                if q2 is None:
                    continue
                xs.append(t_s)
                med.append(q2)
                lo.append(q1 if q1 is not None else q2)
                hi.append(q3 if q3 is not None else q2)
                ns.append(len(vals))
            if not xs:
                continue
            ax.fill_between(xs, lo, hi, alpha=0.15)
            ax.plot(xs, med, marker="o", label=f"{mechanism} n={ns[-1]}")
        ax.axhline(0.0, color="#888", linewidth=0.8)
        ax.set_title(planner_id)
        ax.set_xlabel("checkpoint (s)")
        ax.set_ylabel("median relative gap | exact")
        handles, labels = ax.get_legend_handles_labels()
        if labels:
            ax.legend(handles, labels, fontsize=7)
        _footer(
            ax,
            grouping="conditional on exact solution",
            denominator="exact nontrivial checkpoints",
            n=sum(1 for row in rows if row.get("planner_id") == planner_id),
            digest_b=digest_b,
            digest_c=digest_c,
        )
    fig.suptitle("IQR band; already-satisfied rows excluded")
    _save_fig(fig, path)
    plt.close(fig)


def _plot_first_vs_final(
    final_rows: Sequence[Mapping[str, Any]],
    path: Path,
    *,
    digest_b: str,
    digest_c: str,
) -> None:
    plt = _require_matplotlib()
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 4.2), sharex=True, sharey=True)
    rows = [
        row
        for row in _nontrivial_final(final_rows)
        if row.get("planner_id") in OPTIMIZER_IDS
        and row.get("first_epsilon_rel") is not None
        and row.get("final_epsilon_rel") is not None
    ]
    for ax, planner_id in zip(axes, ("ompl_rrt_star", "ompl_bit_star"), strict=True):
        for mechanism, marker in (("fourbar", "o"), ("gearbox", "s")):
            xs = [
                float(row["first_epsilon_rel"])
                for row in rows
                if row.get("planner_id") == planner_id
                and row.get("mechanism") == mechanism
            ]
            ys = [
                float(row["final_epsilon_rel"])
                for row in rows
                if row.get("planner_id") == planner_id
                and row.get("mechanism") == mechanism
            ]
            ax.scatter(xs, ys, marker=marker, alpha=0.65, label=mechanism)
        ax.axline((0.0, 0.0), slope=1.0, color="#888", linewidth=0.8)
        ax.set_title(planner_id)
        ax.set_xlabel("first exact relative gap")
        ax.set_ylabel("final relative gap")
        handles, labels = ax.get_legend_handles_labels()
        if labels:
            ax.legend(handles, labels, fontsize=7)
        _footer(
            ax,
            grouping="below diagonal improved after first exact",
            denominator="exact nontrivial optimizer runs",
            n=sum(1 for row in rows if row.get("planner_id") == planner_id),
            digest_b=digest_b,
            digest_c=digest_c,
        )
    _save_fig(fig, path)
    plt.close(fig)


def _plot_final_by_family(
    final_rows: Sequence[Mapping[str, Any]],
    path: Path,
    *,
    digest_b: str,
    digest_c: str,
) -> None:
    plt = _require_matplotlib()
    panels = (
        (
            "RRT*/BIT*/FMT (FMT is sample-count, not wall time)",
            ("ompl_rrt_star", "ompl_bit_star", "ompl_fmt"),
        ),
        (
            "KPIECE U/Q/X projection diagnostic, not faster convergence",
            ("ompl_kpiece_u", "ompl_kpiece_q", "ompl_kpiece_x"),
        ),
        (
            "PRM/RRTConnect controls; PRM sequential-goal workaround",
            ("ompl_prm", "ompl_rrt_connect"),
        ),
    )
    fig, axes = plt.subplots(1, 3, figsize=(10.4, 4.2), sharey=True)
    rows = [
        row
        for row in _nontrivial_final(final_rows)
        if row.get("final_epsilon_rel") is not None
    ]
    for ax, (title, planners) in zip(axes, panels, strict=True):
        labels: list[str] = []
        data: list[list[float]] = []
        for planner_id in planners:
            vals = [
                float(row["final_epsilon_rel"])
                for row in rows
                if row.get("planner_id") == planner_id
            ]
            if not vals:
                continue
            labels.append(planner_id.replace("ompl_", ""))
            data.append(vals)
        if data:
            ax.boxplot(data, showfliers=False)
            ax.set_xticks(range(1, len(labels) + 1), labels, rotation=20)
        else:
            _empty_axes(ax, "No exact relative gaps.")
        ax.axhline(0.0, color="#888", linewidth=0.8)
        ax.set_title(title, fontsize=8)
        ax.tick_params(axis="x", labelrotation=20, labelsize=7)
        _footer(
            ax,
            grouping="family-specific frozen budget",
            denominator="exact nontrivial finals",
            n=sum(len(item) for item in data),
            digest_b=digest_b,
            digest_c=digest_c,
        )
    fig.suptitle("Cross-family effort units remain separate")
    _save_fig(fig, path)
    plt.close(fig)


def _plot_paired_contrast(
    paired: Sequence[Mapping[str, Any]],
    path: Path,
    *,
    digest_b: str,
    digest_c: str,
) -> None:
    plt = _require_matplotlib()
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    rows = [
        row
        for row in paired
        if not row.get("already_satisfied")
        and row.get("delta_epsilon_rel_fourbar_minus_gearbox") is not None
        and row.get("planner_id") in OPTIMIZER_IDS
    ]
    if not rows:
        _empty_axes(ax, "No paired discoverability contrasts.")
    else:
        by_planner: dict[str, list[float]] = defaultdict(list)
        for row in rows:
            by_planner[str(row["planner_id"])].append(
                float(row["delta_epsilon_rel_fourbar_minus_gearbox"])
            )
        labels = sorted(by_planner)
        ax.boxplot([by_planner[name] for name in labels], showfliers=False)
        ax.set_xticks(
            range(1, len(labels) + 1),
            [name.replace("ompl_", "") for name in labels],
        )
        ax.axhline(0.0, color="#888", linewidth=0.8)
        ax.set_ylabel(r"$\Delta\epsilon^{rel}$ fourbar-gearbox")
        ax.set_title(f"Negative: four-bar closer to its own optimum ({PAIRING_LABEL})")
    _footer(
        ax,
        grouping="index-matched planner/case/task/repetition",
        denominator="exact nontrivial paired optimizer runs",
        n=len(rows),
        digest_b=digest_b,
        digest_c=digest_c,
    )
    _save_fig(fig, path)
    plt.close(fig)


def _plot_quadrants(
    paired: Sequence[Mapping[str, Any]],
    path: Path,
    *,
    digest_b: str,
    digest_c: str,
) -> None:
    plt = _require_matplotlib()
    fig, ax = plt.subplots(figsize=(6.8, 6.2))
    grouped: dict[tuple[Any, Any], list[Mapping[str, Any]]] = defaultdict(list)
    for row in paired:
        if row.get("already_satisfied"):
            continue
        if row.get("planner_id") not in OPTIMIZER_IDS:
            continue
        grouped[(row.get("case_id"), row.get("planner_id"))].append(row)
    xs: list[float] = []
    ys: list[float] = []
    for items in grouped.values():
        dj = [float(row["delta_j_star_c_fourbar_minus_gearbox"]) for row in items]
        de = [
            float(row["delta_epsilon_rel_fourbar_minus_gearbox"])
            for row in items
            if row.get("delta_epsilon_rel_fourbar_minus_gearbox") is not None
        ]
        if not dj or not de:
            continue
        xs.append(float(statistics.median(dj)))
        ys.append(float(statistics.median(de)))
    ax.axhline(0.0, color="#888", linewidth=0.8)
    ax.axvline(0.0, color="#888", linewidth=0.8)
    ax.scatter(xs, ys, alpha=0.75)
    ax.set_xlabel(r"median $\Delta J_C^*$")
    ax.set_ylabel(r"median $\Delta\epsilon^{rel}$")
    ax.set_title("Quadrants separate lower/higher optimum from easier/harder discovery")
    _footer(
        ax,
        grouping="median over tasks/reps per case and optimizer",
        denominator="nontrivial paired optimizer contrasts",
        n=len(xs),
        digest_b=digest_b,
        digest_c=digest_c,
    )
    _save_fig(fig, path)
    plt.close(fig)


def _plot_decomposition(
    decomp: Sequence[Mapping[str, Any]],
    path: Path,
    *,
    digest_b: str,
    digest_c: str,
) -> None:
    plt = _require_matplotlib()
    fig, ax = plt.subplots(figsize=(8.4, 4.4))
    rows = [row for row in decomp if row.get("decomposition_status") == "ok"]
    planners = sorted({str(row["planner_id"]) for row in rows})
    x = list(range(len(planners)))
    regret = []
    ineff = []
    for planner_id in planners:
        rvals = [
            float(row["goal_selection_regret"])
            for row in rows
            if row["planner_id"] == planner_id
        ]
        ivals = [
            float(row["path_inefficiency"])
            for row in rows
            if row["planner_id"] == planner_id
        ]
        regret.append(_median(rvals) or 0.0)
        ineff.append(_median(ivals) or 0.0)
    if planners:
        ax.bar(x, regret, label="goal-selection regret")
        ax.bar(x, ineff, bottom=regret, label="path inefficiency")
        ax.set_xticks(x, [name.replace("ompl_", "") for name in planners], rotation=25)
        ax.legend(fontsize=8)
        ax.set_ylabel("median contribution")
    else:
        _empty_axes(ax, "No certified final-gap decompositions.")
    ax.set_title("Checkpoint-level goal identity is not inferred")
    _footer(
        ax,
        grouping="final selected candidate only",
        denominator="exact nontrivial decompositions",
        n=len(rows),
        digest_b=digest_b,
        digest_c=digest_c,
    )
    _save_fig(fig, path)
    plt.close(fig)


def _plot_match_rate(
    decomp: Sequence[Mapping[str, Any]],
    path: Path,
    *,
    digest_b: str,
    digest_c: str,
) -> None:
    plt = _require_matplotlib()
    fig, ax = plt.subplots(figsize=(8.2, 4.2))
    rows = [row for row in decomp if row.get("decomposition_status") == "ok"]
    planners = sorted({str(row["planner_id"]) for row in rows})
    ys = []
    for planner_id in planners:
        bucket = [row for row in rows if row["planner_id"] == planner_id]
        n_match = sum(1 for row in bucket if row.get("reference_goal_match"))
        ys.append(n_match / len(bucket) if bucket else math.nan)
    if planners:
        ax.bar(range(len(planners)), ys)
        ax.set_xticks(
            range(len(planners)),
            [name.replace("ompl_", "") for name in planners],
            rotation=25,
        )
        ax.set_ylim(0.0, 1.05)
        ax.set_ylabel("match rate vs J*_C candidate")
    else:
        _empty_axes(ax, "No selected-candidate matches.")
    ax.set_title("disk_center::elbow_up / elbow_down identity")
    _footer(
        ax,
        grouping="final selected key vs reconstructed reference key",
        denominator="exact nontrivial decompositions",
        n=len(rows),
        digest_b=digest_b,
        digest_c=digest_c,
    )
    _save_fig(fig, path)
    plt.close(fig)


def _plot_representation(
    refs: Sequence[Mapping[str, Any]],
    path: Path,
    *,
    digest_b: str,
    digest_c: str,
) -> None:
    plt = _require_matplotlib()
    fig, ax = plt.subplots(figsize=(6.6, 6.0))
    rows = [
        row
        for row in refs
        if not row.get("already_satisfied") and row.get("j_star_b") is not None
    ]
    xs = [float(row["j_star_b"]) for row in rows]
    ys = [float(row["j_star_c"]) for row in rows]
    if xs:
        ax.scatter(xs, ys, alpha=0.7)
        lo = min(min(xs), min(ys))
        hi = max(max(xs), max(ys))
        ax.plot([lo, hi], [lo, hi], color="#888", linewidth=0.8)
    else:
        _empty_axes(ax, "No historical V4.2B references.")
    ax.set_xlabel("J*_B broader V4.2B representation")
    ax.set_ylabel("J*_C center-only V4.2C representation")
    ax.set_title(
        "center-only V4.2C representation versus broader "
        "historical V4.2B representation"
    )
    _footer(
        ax,
        grouping="one point per case/task/mechanism",
        denominator="nontrivial references",
        n=len(rows),
        digest_b=digest_b,
        digest_c=digest_c,
    )
    _save_fig(fig, path)
    plt.close(fig)


def write_figures(
    *,
    output_dir: Path,
    reference_rows: Sequence[Mapping[str, Any]],
    checkpoint_rows: Sequence[Mapping[str, Any]],
    final_rows: Sequence[Mapping[str, Any]],
    paired_rows: Sequence[Mapping[str, Any]],
    decomposition_rows: Sequence[Mapping[str, Any]],
    digest_b: str,
    digest_c: str,
) -> list[dict[str, Any]]:
    """Write the twelve executive figures under ``output_dir/figures``."""
    root = assert_v4_2d_output_allowed(output_dir)
    figures_dir = root / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    drawers = {
        "01_reference_cost_by_mechanism": lambda path: _plot_reference_cost(
            reference_rows, path, digest_b=digest_b, digest_c=digest_c
        ),
        "02_mechanism_optimum_delta": lambda path: _plot_delta_j(
            reference_rows, path, digest_b=digest_b, digest_c=digest_c
        ),
        "03_exact_solution_rate_vs_checkpoint": lambda path: _plot_exact_rate(
            checkpoint_rows, path, digest_b=digest_b, digest_c=digest_c
        ),
        "04_within_5pct_vs_checkpoint": lambda path: _plot_within_5(
            checkpoint_rows, path, digest_b=digest_b, digest_c=digest_c
        ),
        "05_relative_gap_vs_checkpoint": lambda path: _plot_relative_gap(
            checkpoint_rows, path, digest_b=digest_b, digest_c=digest_c
        ),
        "06_first_vs_final_gap": lambda path: _plot_first_vs_final(
            final_rows, path, digest_b=digest_b, digest_c=digest_c
        ),
        "07_final_gap_by_family": lambda path: _plot_final_by_family(
            final_rows, path, digest_b=digest_b, digest_c=digest_c
        ),
        "08_paired_discoverability_contrast": lambda path: _plot_paired_contrast(
            paired_rows, path, digest_b=digest_b, digest_c=digest_c
        ),
        "09_benefit_vs_discoverability": lambda path: _plot_quadrants(
            paired_rows, path, digest_b=digest_b, digest_c=digest_c
        ),
        "10_final_gap_decomposition": lambda path: _plot_decomposition(
            decomposition_rows, path, digest_b=digest_b, digest_c=digest_c
        ),
        "11_reference_goal_match": lambda path: _plot_match_rate(
            decomposition_rows, path, digest_b=digest_b, digest_c=digest_c
        ),
        "12_goal_representation_sensitivity": lambda path: _plot_representation(
            reference_rows, path, digest_b=digest_b, digest_c=digest_c
        ),
    }
    payloads: list[dict[str, Any]] = []
    for figure_id, relpath, title in FIGURE_SPECS:
        dest = root / relpath
        drawers[figure_id](dest)
        if not dest.is_file():
            raise V4_2DReportError(f"missing figure {dest}")
        payloads.append(
            {
                "figure_id": figure_id,
                "relpath": relpath,
                "title": title,
                "source_v4_2b_digest": digest_b,
                "source_v4_2c_digest": digest_c,
            }
        )
    return payloads


def _section(title: str, body: str) -> str:
    return f"<section><h2>{_esc(title)}</h2>{body}</section>"


def _img(relpath: str, title: str) -> str:
    return (
        f'<figure><img src="{_esc(relpath)}" alt="{_esc(title)}">'
        f"<figcaption>{_esc(title)}</figcaption></figure>"
    )


def render_index_html(summary: Mapping[str, Any]) -> str:
    """Render the question-grouped landing page from ``summary.json``."""
    figures = {item["figure_id"]: item for item in summary.get("figures") or []}
    counts = summary.get("counts") or {}
    contract = summary.get("source_contract") or {}
    digest_b = _esc(contract.get("v4_2b_files_digest"))
    digest_c = _esc(contract.get("v4_2c_files_digest"))
    revision = _esc(contract.get("v4_2c_source_revision"))
    claims = _esc(
        "; ".join(str(item) for item in summary.get("prohibited_claims") or [])
    )
    nav = " ".join(
        f'<a href="#{sid}">{label}</a>'
        for sid, label in (
            ("s1", "Reference"),
            ("s2", "Mechanism"),
            ("s3", "Optimizers"),
            ("s4", "Discoverability"),
            ("s5", "Suboptimality"),
            ("s6", "Controls"),
            ("s7", "Methods"),
        )
    )
    case_links = " ".join(
        f'<a href="cases/{_esc(case_id)}/index.html">{_esc(case_id)}</a>'
        for case_id in summary.get("case_ids") or []
    )
    s1 = _section(
        "1. What is the exact reference?",
        "<p>The V4.2C worker represented the Cartesian disk by planar-2R IK "
        "lifts of the disk center only. Candidate keys are "
        "<code>disk_center::elbow_up</code> and "
        "<code>disk_center::elbow_down</code>. "
        f"Primary reference rows: {_esc(counts.get('n_reference_rows'))}. "
        f"Stage C rows joined: {_esc(counts.get('n_stage_c_rows'))}. "
        f"Already-satisfied: {_esc(counts.get('n_already_satisfied'))}.</p>"
        + _img(
            figures["01_reference_cost_by_mechanism"]["relpath"],
            figures["01_reference_cost_by_mechanism"]["title"],
        ),
    )
    s2 = _section(
        "2. What did the mechanism change?",
        "<p>Negative "
        r"&Delta;J<sub>C</sub>* means the four-bar has the lower center-goal "
        "actuator optimum. J*_B is a representation-sensitivity control only.</p>"
        + _img(
            figures["02_mechanism_optimum_delta"]["relpath"],
            figures["02_mechanism_optimum_delta"]["title"],
        )
        + _img(
            figures["12_goal_representation_sensitivity"]["relpath"],
            figures["12_goal_representation_sensitivity"]["title"],
        ),
    )
    s3 = _section(
        "3. How quickly did optimizers approach it?",
        "<p>RRT* and BIT* use wall-time checkpoints "
        "0.05, 0.10, 0.25, 0.50, 1.00 s. "
        "Already-satisfied queries are excluded from these plots.</p>"
        + _img(
            figures["03_exact_solution_rate_vs_checkpoint"]["relpath"],
            figures["03_exact_solution_rate_vs_checkpoint"]["title"],
        )
        + _img(
            figures["04_within_5pct_vs_checkpoint"]["relpath"],
            figures["04_within_5pct_vs_checkpoint"]["title"],
        )
        + _img(
            figures["05_relative_gap_vs_checkpoint"]["relpath"],
            figures["05_relative_gap_vs_checkpoint"]["title"],
        )
        + _img(
            figures["06_first_vs_final_gap"]["relpath"],
            figures["06_first_vs_final_gap"]["title"],
        ),
    )
    s4 = _section(
        "4. Did the mechanism change discoverability?",
        f"<p>Paired contrasts are {_esc(PAIRING_LABEL)}. Equal seeds are not a "
        "common-random-number estimator.</p>"
        + _img(
            figures["08_paired_discoverability_contrast"]["relpath"],
            figures["08_paired_discoverability_contrast"]["title"],
        )
        + _img(
            figures["09_benefit_vs_discoverability"]["relpath"],
            figures["09_benefit_vs_discoverability"]["title"],
        ),
    )
    s5 = _section(
        "5. Why was the final solution suboptimal?",
        "<p>Goal-selection regret uses the reconstructed direct cost of the "
        "final selected center-IK family. Checkpoint-level goal identity is "
        "not retained in V4.2C and is not inferred here.</p>"
        + _img(
            figures["11_reference_goal_match"]["relpath"],
            figures["11_reference_goal_match"]["title"],
        )
        + _img(
            figures["10_final_gap_decomposition"]["relpath"],
            figures["10_final_gap_decomposition"]["title"],
        ),
    )
    s6 = _section(
        "6. Fixed-budget and projection controls",
        "<p>FMT is an independent sample-count run and is not placed on the "
        "RRT*/BIT* wall-time axis. KPIECE-U/Q/X is a projection diagnostic; "
        "a lower final cost is not faster convergence. PRM retains the "
        "sequential-goal workaround label. RRTConnect is a first-feasible "
        "control.</p>"
        + _img(
            figures["07_final_gap_by_family"]["relpath"],
            figures["07_final_gap_by_family"]["title"],
        ),
    )
    s7 = _section(
        "7. Methods, provenance, and nonclaims",
        "<ul>"
        f"<li>V4.2B files_digest <code>{digest_b}</code></li>"
        f"<li>V4.2C files_digest <code>{digest_c}</code></li>"
        f"<li>V4.2C source revision <code>{revision}</code></li>"
        f"<li>Pairing: {_esc(PAIRING_LABEL)}</li>"
        "<li>Same-seed limitation: equal OMPL seeds do not prove identical "
        "samples.</li>"
        f"<li>Nonclaims: {claims}</li>"
        f"<li>{_esc(summary.get('no_inference_statement'))}</li>"
        f"<li>{_esc(summary.get('interpretation_boundary'))}</li>"
        "</ul>",
    )
    body = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>V4.2D optimality reference</title>
<style>{PRINT_CSS}</style></head><body>
<h1>V4.2D optimality-reference and gearbox-control report</h1>
<p>{_esc(summary.get("lede"))}</p>
<nav>{nav}</nav>
<p class="muted">Cases: {case_links}</p>
<section id="s1">{s1}</section>
<section id="s2">{s2}</section>
<section id="s3">{s3}</section>
<section id="s4">{s4}</section>
<section id="s5">{s5}</section>
<section id="s6">{s6}</section>
<section id="s7">{s7}</section>
</body></html>
"""
    return body


def render_case_html(summary: Mapping[str, Any], case_id: str) -> str:
    """Render one per-case drill-down page."""
    contract = summary.get("source_contract") or {}
    digest_b = _esc(contract.get("v4_2b_files_digest"))
    digest_c = _esc(contract.get("v4_2c_files_digest"))
    figures = summary.get("figures") or []
    imgs = "".join(
        f'<p><img src="../../{_esc(item["relpath"])}" alt="{_esc(item["title"])}"></p>'
        for item in figures
    )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>{_esc(case_id)}</title>
<style>{PRINT_CSS}</style></head><body>
<p><a href="../../index.html">Back to V4.2D landing page</a></p>
<h1>{_esc(case_id)}</h1>
<p>Audit-wide figures are reproduced for navigation. Calculations live in
<code>summary.json</code>. Pairing is {_esc(PAIRING_LABEL)}.</p>
<p>Source digests: V4.2B <code>{digest_b}</code>;
V4.2C <code>{digest_c}</code>.</p>
{imgs}
</body></html>
"""


def write_html_report(
    output_dir: Path,
    summary: Mapping[str, Any],
) -> dict[str, Any]:
    """Write landing and per-case HTML, then check local links."""
    root = assert_v4_2d_output_allowed(output_dir)
    index = root / "index.html"
    html_text = render_index_html(summary)
    token = _forbidden_token_in(html_text)
    if token is not None:
        raise V4_2DReportError(f"HTML contains forbidden token {token!r}")
    index.write_text(html_text, encoding="utf-8")
    for case_id in summary.get("case_ids") or []:
        case_dir = assert_v4_2d_output_allowed(root / "cases" / str(case_id))
        case_dir.mkdir(parents=True, exist_ok=True)
        page = render_case_html(summary, str(case_id))
        token = _forbidden_token_in(page)
        if token is not None:
            raise V4_2DReportError(f"case HTML contains forbidden token {token!r}")
        (case_dir / "index.html").write_text(page, encoding="utf-8")
    missing = [path for path in href_targets(index) if not path.exists()]
    if missing:
        raise V4_2DReportError(f"missing href/src targets: {missing}")
    write_atomic_json(root / "summary.json", dict(summary))
    return {"index_path": str(index), "n_figures": len(summary.get("figures") or [])}
