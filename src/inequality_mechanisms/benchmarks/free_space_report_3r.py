"""Review summaries for Sprint V3.7 planar 3R free-space evidence."""

from __future__ import annotations

import html
import statistics
from collections import Counter, defaultdict
from typing import Any


def _success(row: dict[str, Any]) -> bool:
    return not row.get("skipped") and str(row.get("status")) == "success"


def _mean(values: list[float]) -> float | None:
    return None if not values else float(sum(values) / len(values))


def _median(values: list[float]) -> float | None:
    return None if not values else float(statistics.median(values))


def summarize_v3_7(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize V3.7 rows with position-only and full-pose estimands separated."""
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_family[str(row["task_family"])].append(row)

    family_summaries: dict[str, Any] = {}
    for family, family_rows in sorted(by_family.items()):
        status_by_planner: dict[str, Counter[str]] = defaultdict(Counter)
        cost: dict[str, list[float]] = defaultdict(list)
        total_time: dict[str, list[float]] = defaultdict(list)
        subopt: dict[str, list[float]] = defaultdict(list)
        paired_rows: dict[tuple[str, str, Any], dict[str, dict[str, Any]]] = (
            defaultdict(dict)
        )
        for row in family_rows:
            planner = str(row["planner"])
            label = (
                f"skipped:{row['skipped']}"
                if row.get("skipped")
                else str(row.get("status"))
            )
            status_by_planner[planner][label] += 1
            paired_rows[(str(row["task_id"]), planner, row.get("seed"))][
                str(row["mechanism"])
            ] = row
            if not _success(row):
                continue
            if row.get("objective_cost") is not None:
                cost[planner].append(float(row["objective_cost"]))
            if row.get("total_wall_time_s") is not None:
                total_time[planner].append(float(row["total_wall_time_s"]))
            if row.get("suboptimality_to_direct_reference") is not None:
                subopt[planner].append(
                    float(row["suboptimality_to_direct_reference"])
                )

        delta_j: dict[str, list[float]] = defaultdict(list)
        for (_, planner, _), pair in paired_rows.items():
            if set(pair) != {"fourbar", "gearbox"}:
                continue
            fb = pair["fourbar"]
            gb = pair["gearbox"]
            if not (_success(fb) and _success(gb)):
                continue
            if fb.get("objective_cost") is None or gb.get("objective_cost") is None:
                continue
            delta_j[planner].append(
                float(fb["objective_cost"]) - float(gb["objective_cost"])
            )

        planner_summary = {}
        for planner in sorted(status_by_planner):
            planner_summary[planner] = {
                "status_counts": dict(status_by_planner[planner]),
                "mean_objective_cost": _mean(cost[planner]),
                "median_objective_cost": _median(cost[planner]),
                "mean_total_wall_time_s": _mean(total_time[planner]),
                "mean_suboptimality_to_direct": _mean(subopt[planner]),
                "mean_delta_J_fourbar_minus_gearbox": _mean(delta_j[planner]),
                "n_paired_delta_j": len(delta_j[planner]),
            }
        family_summaries[family] = {
            "n_rows": len(family_rows),
            "planners": planner_summary,
        }

    return {
        "n_rows": len(rows),
        "by_task_family": family_summaries,
    }


def build_readme_v3_7(
    *,
    manifest: dict[str, Any],
    summary: dict[str, Any],
) -> str:
    lines = [
        "# Sprint V3.7 — Planar 3R Free-Space Evidence",
        "",
        f"- bank: `{manifest.get('bank_id')}`",
        f"- implementation revision: `{manifest.get('implementation_revision')}`",
        f"- rows: {manifest.get('n_rows')}",
        f"- OMPL solve time (s): {manifest.get('ompl_solve_time_s')}",
        "",
        "Position-only and full-pose estimands are summarized separately.",
        "Dense 3D lattice search is diagnostic-only and not an evidence exit criterion.",
        "",
    ]
    for family, block in summary.get("by_task_family", {}).items():
        lines.append(f"## Task family `{family}`")
        lines.append("")
        lines.append(f"- rows: {block.get('n_rows')}")
        for planner, stats in block.get("planners", {}).items():
            lines.append(
                f"- `{planner}`: status={stats.get('status_counts')}, "
                f"mean J*={stats.get('mean_objective_cost')}, "
                f"mean wall={stats.get('mean_total_wall_time_s')}, "
                f"mean ΔJ(fb−gb)={stats.get('mean_delta_J_fourbar_minus_gearbox')}"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def build_html_v3_7(
    *,
    manifest: dict[str, Any],
    summary: dict[str, Any],
) -> str:
    body_parts = [
        "<h1>Sprint V3.7 — Planar 3R Free-Space Evidence</h1>",
        f"<p>Bank <code>{html.escape(str(manifest.get('bank_id')))}</code>; "
        f"revision <code>{html.escape(str(manifest.get('implementation_revision')))}</code>; "
        f"rows {html.escape(str(manifest.get('n_rows')))}.</p>",
        "<p>Position-only and full-pose estimands are kept separate.</p>",
    ]
    for family, block in summary.get("by_task_family", {}).items():
        body_parts.append(f"<h2>Task family {html.escape(family)}</h2>")
        body_parts.append("<table border='1' cellpadding='4'><tr>")
        body_parts.append(
            "<th>planner</th><th>status</th><th>mean J*</th>"
            "<th>mean wall (s)</th><th>mean ΔJ (fb−gb)</th></tr>"
        )
        for planner, stats in block.get("planners", {}).items():
            body_parts.append(
                "<tr>"
                f"<td>{html.escape(planner)}</td>"
                f"<td><code>{html.escape(str(stats.get('status_counts')))}</code></td>"
                f"<td>{html.escape(str(stats.get('mean_objective_cost')))}</td>"
                f"<td>{html.escape(str(stats.get('mean_total_wall_time_s')))}</td>"
                f"<td>{html.escape(str(stats.get('mean_delta_J_fourbar_minus_gearbox')))}</td>"
                "</tr>"
            )
        body_parts.append("</table>")
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<title>V3.7 3R Free-Space Evidence</title></head><body>"
        + "".join(body_parts)
        + "</body></html>\n"
    )


__all__ = [
    "build_html_v3_7",
    "build_readme_v3_7",
    "summarize_v3_7",
]
