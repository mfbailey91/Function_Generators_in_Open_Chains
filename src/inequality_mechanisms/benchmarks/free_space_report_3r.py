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


_PLANNER_ORDER = (
    "input_linear",
    "output_linear",
    "prm",
    "rrt_connect",
    "ompl_prm",
    "ompl_rrt_connect",
)


def _fmt(value: Any, *, digits: int = 4) -> str:
    if value is None:
        return "—"
    return f"{float(value):.{digits}g}"


def _ordered_planners(planners: dict[str, Any]) -> list[str]:
    known = [p for p in _PLANNER_ORDER if p in planners]
    extras = sorted(p for p in planners if p not in _PLANNER_ORDER)
    return known + extras


def _svg_bar_chart(
    *,
    title: str,
    y_label: str,
    series: list[tuple[str, float | None]],
    color: str = "#1f4e79",
    width: int = 720,
    height: int = 260,
) -> str:
    """Return a self-contained SVG horizontal-ish vertical bar chart."""
    usable = [(name, float(v)) for name, v in series if v is not None]
    if not usable:
        return f"<p><em>{html.escape(title)}: no values</em></p>"

    max_v = max(abs(v) for _, v in usable) or 1.0
    # Allow signed ΔJ charts.
    min_v = min(v for _, v in usable)
    has_neg = min_v < 0
    y_min = min(0.0, min_v) if has_neg else 0.0
    y_max = max(0.0, max(v for _, v in usable))
    span = (y_max - y_min) or 1.0

    left, right, top, bottom = 56, 16, 28, 72
    plot_w = width - left - right
    plot_h = height - top - bottom
    n = len(usable)
    gap = 10.0
    bar_w = max(12.0, (plot_w - gap * (n + 1)) / n)
    zero_y = top + plot_h * (y_max / span)

    bars: list[str] = []
    labels: list[str] = []
    for i, (name, value) in enumerate(usable):
        x = left + gap + i * (bar_w + gap)
        y_val = top + plot_h * ((y_max - value) / span)
        y = min(y_val, zero_y)
        h = abs(zero_y - y_val)
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" '
            f'fill="{color}" />'
        )
        bars.append(
            f'<text x="{x + bar_w / 2:.1f}" y="{y - 4:.1f}" text-anchor="middle" '
            f'font-size="10" fill="#222">{_fmt(value)}</text>'
        )
        labels.append(
            f'<text transform="translate({x + bar_w / 2:.1f},{height - 10}) '
            f'rotate(-35)" text-anchor="end" font-size="10" fill="#333">'
            f"{html.escape(name)}</text>"
        )

    axis = (
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" '
        f'stroke="#444" stroke-width="1"/>'
        f'<line x1="{left}" y1="{zero_y:.1f}" x2="{left + plot_w}" '
        f'y2="{zero_y:.1f}" stroke="#888" stroke-width="1"/>'
        f'<text x="14" y="{top + plot_h / 2:.1f}" transform='
        f'"rotate(-90 14,{top + plot_h / 2:.1f})" font-size="11" fill="#333">'
        f"{html.escape(y_label)}</text>"
    )
    return (
        f'<figure class="chart"><figcaption>{html.escape(title)}</figcaption>'
        f'<svg viewBox="0 0 {width} {height}" width="100%" '
        f'role="img" aria-label="{html.escape(title)}">'
        f"{axis}{''.join(bars)}{''.join(labels)}</svg></figure>"
    )


def build_html_v3_7(
    *,
    manifest: dict[str, Any],
    summary: dict[str, Any],
) -> str:
    """Build a printable HTML review page with SVG comparison charts."""
    rev = str(manifest.get("implementation_revision") or "")
    short_rev = rev[:7] if rev else "—"
    styles = """
    :root { color-scheme: light; }
    body { font-family: "IBM Plex Sans", "Segoe UI", Helvetica, Arial, sans-serif;
           margin: 2rem; color: #1a1a1a; line-height: 1.45; max-width: 1100px; }
    h1 { font-size: 1.75rem; margin-bottom: 0.25rem; }
    h2 { margin-top: 2rem; border-bottom: 1px solid #ccc; padding-bottom: 0.25rem; }
    h3 { margin-top: 1.25rem; color: #1f4e79; }
    .meta { color: #444; margin-bottom: 1.25rem; }
    .meta code { background: #f3f3f3; padding: 0.1rem 0.35rem; }
    .stats { display: flex; flex-wrap: wrap; gap: 0.75rem; margin: 1rem 0; }
    .stat { border: 1px solid #d0d0d0; padding: 0.65rem 0.9rem; min-width: 8rem; }
    .stat .k { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.04em; color: #555; }
    .stat .v { font-size: 1.15rem; font-weight: 600; }
    table { border-collapse: collapse; width: 100%; margin: 0.75rem 0 1.25rem; font-size: 0.92rem; }
    th, td { border: 1px solid #c8c8c8; padding: 0.4rem 0.55rem; text-align: left; }
    th { background: #eef2f6; }
    td.num { text-align: right; font-variant-numeric: tabular-nums; }
    figure.chart { margin: 1rem 0 1.5rem; page-break-inside: avoid; }
    figcaption { font-weight: 600; margin-bottom: 0.35rem; }
    .note { font-size: 0.9rem; color: #444; }
    @media print {
      body { margin: 0.6in; }
      .stat { break-inside: avoid; }
      figure.chart { break-inside: avoid; }
    }
    """

    body: list[str] = [
        "<h1>Sprint V3.7 — Planar 3R Free-Space Evidence</h1>",
        '<p class="meta">',
        f"Bank <code>{html.escape(str(manifest.get('bank_id')))}</code> · ",
        f"revision <code>{html.escape(short_rev)}</code> · ",
        f"rows {html.escape(str(manifest.get('n_rows')))} · ",
        f"OMPL solve {html.escape(str(manifest.get('ompl_solve_time_s')))} s · ",
        f"OMPL {html.escape(str(manifest.get('ompl_version') or '—'))}",
        "</p>",
        '<p class="note">Position-only and full-pose estimands are kept separate. '
        "Invalid counts are unreachable bank tasks; non-invalid rows succeed across "
        "planners. Charts use success-row means from <code>summary.json</code>.</p>",
        '<div class="stats">',
        f'<div class="stat"><div class="k">Rows</div><div class="v">'
        f"{html.escape(str(summary.get('n_rows')))}</div></div>",
    ]
    for family, block in summary.get("by_task_family", {}).items():
        body.append(
            f'<div class="stat"><div class="k">{html.escape(family)}</div>'
            f'<div class="v">{html.escape(str(block.get("n_rows")))} rows</div></div>'
        )
    body.append("</div>")

    for family, block in summary.get("by_task_family", {}).items():
        planners = dict(block.get("planners", {}))
        order = _ordered_planners(planners)
        body.append(f"<h2>Task family: {html.escape(family)}</h2>")
        body.append(f"<p>{html.escape(str(block.get('n_rows')))} rows</p>")

        cost_series = [
            (p, planners[p].get("mean_objective_cost")) for p in order
        ]
        wall_series = [
            (p, planners[p].get("mean_total_wall_time_s")) for p in order
        ]
        subopt_series = [
            (p, planners[p].get("mean_suboptimality_to_direct")) for p in order
        ]
        delta_series = [
            (p, planners[p].get("mean_delta_J_fourbar_minus_gearbox"))
            for p in order
        ]

        body.append(
            _svg_bar_chart(
                title=f"{family}: mean objective cost J*",
                y_label="mean J*",
                series=cost_series,
                color="#1f4e79",
            )
        )
        body.append(
            _svg_bar_chart(
                title=f"{family}: mean total wall time",
                y_label="seconds",
                series=wall_series,
                color="#2f6f4e",
            )
        )
        body.append(
            _svg_bar_chart(
                title=f"{family}: mean suboptimality vs direct reference",
                y_label="Δ cost",
                series=subopt_series,
                color="#8a4b12",
            )
        )
        body.append(
            _svg_bar_chart(
                title=f"{family}: mean ΔJ (fourbar − gearbox)",
                y_label="ΔJ",
                series=delta_series,
                color="#5b2c6f",
            )
        )

        body.append("<h3>Numeric table</h3>")
        body.append("<table><thead><tr>")
        body.append(
            "<th>planner</th><th>success</th><th>invalid</th>"
            "<th>mean J*</th><th>mean wall (s)</th>"
            "<th>mean subopt.</th><th>mean ΔJ (fb−gb)</th></tr></thead><tbody>"
        )
        for planner in order:
            stats = planners[planner]
            counts = dict(stats.get("status_counts") or {})
            body.append(
                "<tr>"
                f"<td><code>{html.escape(planner)}</code></td>"
                f'<td class="num">{html.escape(str(counts.get("success", 0)))}</td>'
                f'<td class="num">{html.escape(str(counts.get("invalid", 0)))}</td>'
                f'<td class="num">{html.escape(_fmt(stats.get("mean_objective_cost")))}</td>'
                f'<td class="num">{html.escape(_fmt(stats.get("mean_total_wall_time_s")))}</td>'
                f'<td class="num">{html.escape(_fmt(stats.get("mean_suboptimality_to_direct")))}</td>'
                f'<td class="num">{html.escape(_fmt(stats.get("mean_delta_J_fourbar_minus_gearbox")))}</td>'
                "</tr>"
            )
        body.append("</tbody></table>")

    return (
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>V3.7 3R Free-Space Evidence</title>"
        f"<style>{styles}</style></head><body>"
        + "".join(body)
        + "</body></html>\n"
    )


__all__ = [
    "build_html_v3_7",
    "build_readme_v3_7",
    "summarize_v3_7",
]
