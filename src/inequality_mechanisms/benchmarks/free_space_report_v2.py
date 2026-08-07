"""Review summaries for corrected Sprint V3.6 evidence."""

from __future__ import annotations

import html
import json
import statistics
from collections import Counter, defaultdict
from typing import Any


def _success(row: dict[str, Any]) -> bool:
    return not row.get("skipped") and str(row.get("status")) == "success"


def _mean(values: list[float]) -> float | None:
    return None if not values else float(sum(values) / len(values))


def _median(values: list[float]) -> float | None:
    return None if not values else float(statistics.median(values))


def summarize_v3_6_v2(rows: list[dict[str, Any]]) -> dict[str, Any]:
    status_by_planner: dict[str, Counter[str]] = defaultdict(Counter)
    by_size: dict[str, Counter[str]] = defaultdict(Counter)
    by_paired: dict[str, Counter[str]] = defaultdict(Counter)
    cost: dict[str, list[float]] = defaultdict(list)
    total_time: dict[str, list[float]] = defaultdict(list)
    query_time: dict[str, list[float]] = defaultdict(list)
    subopt: dict[str, list[float]] = defaultdict(list)

    paired_rows: dict[tuple[str, str, Any], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        planner = str(row["planner"])
        label = (
            f"skipped:{row['skipped']}"
            if row.get("skipped")
            else str(row.get("status"))
        )
        status_by_planner[planner][label] += 1
        by_size[str(row["size_stratum"])][label] += 1
        by_paired[str(row["paired_stratum"])][label] += 1

        key = (str(row["task_id"]), planner, row.get("seed"))
        paired_rows[key][str(row["mechanism"])] = row

        if not _success(row):
            continue
        if row.get("objective_cost") is not None:
            cost[planner].append(float(row["objective_cost"]))
        if row.get("total_wall_time_s") is not None:
            total_time[planner].append(float(row["total_wall_time_s"]))
        if row.get("query_time_s") is not None:
            query_time[planner].append(float(row["query_time_s"]))
        if row.get("suboptimality_to_direct_reference") is not None:
            subopt[planner].append(
                float(row["suboptimality_to_direct_reference"])
            )

    paired_effects: list[dict[str, Any]] = []
    delta_j: dict[str, list[float]] = defaultdict(list)
    delta_total: dict[str, list[float]] = defaultdict(list)
    for (task_id, planner, seed), pair in paired_rows.items():
        if set(pair) != {"fourbar", "gearbox"}:
            continue
        fb = pair["fourbar"]
        gb = pair["gearbox"]
        if not (_success(fb) and _success(gb)):
            continue
        if fb.get("objective_cost") is None or gb.get("objective_cost") is None:
            continue
        dj = float(fb["objective_cost"]) - float(gb["objective_cost"])
        dt = None
        if (
            fb.get("total_wall_time_s") is not None
            and gb.get("total_wall_time_s") is not None
        ):
            dt = float(fb["total_wall_time_s"]) - float(
                gb["total_wall_time_s"]
            )
            delta_total[planner].append(dt)
        delta_j[planner].append(dj)
        paired_effects.append(
            {
                "task_id": task_id,
                "planner": planner,
                "seed": seed,
                "paired_stratum": fb["paired_stratum"],
                "size_stratum": fb["size_stratum"],
                "delta_J_fourbar_minus_gearbox": dj,
                "delta_total_wall_time_s_fourbar_minus_gearbox": dt,
                "fourbar_cost": fb["objective_cost"],
                "gearbox_cost": gb["objective_cost"],
            }
        )

    planners = sorted(status_by_planner)
    planner_summary = {}
    for planner in planners:
        planner_summary[planner] = {
            "status_counts": dict(status_by_planner[planner]),
            "n_success": len(cost[planner]),
            "mean_objective_cost": _mean(cost[planner]),
            "median_objective_cost": _median(cost[planner]),
            "mean_total_wall_time_s": _mean(total_time[planner]),
            "median_total_wall_time_s": _median(total_time[planner]),
            "mean_query_time_s_secondary": _mean(query_time[planner]),
            "mean_suboptimality_to_direct_reference": _mean(subopt[planner]),
            "median_suboptimality_to_direct_reference": _median(subopt[planner]),
            "mean_delta_J_fourbar_minus_gearbox": _mean(delta_j[planner]),
            "median_delta_J_fourbar_minus_gearbox": _median(delta_j[planner]),
            "mean_delta_total_wall_time_s_fourbar_minus_gearbox": _mean(
                delta_total[planner]
            ),
        }

    return {
        "planner_summary": planner_summary,
        "by_size": {k: dict(v) for k, v in sorted(by_size.items())},
        "by_paired": {k: dict(v) for k, v in sorted(by_paired.items())},
        "paired_effects": paired_effects,
    }


def build_readme_v2(
    *,
    manifest: dict[str, Any],
    summary: dict[str, Any],
) -> str:
    lines = [
        "# Version 3 review snapshot — corrected V3.6 free-space evidence",
        "",
        "This is the **v2 corrective closeout candidate** for Sprint V3.6. "
        "The v1 artifact is retained as pilot provenance.",
        "",
        f"- Implementation revision: `{manifest.get('implementation_revision')}`",
        f"- Generated UTC: `{manifest.get('generated_at_utc')}`",
        f"- Bank: `{manifest.get('bank_id')}`",
        f"- Frozen stochastic seeds: `{manifest.get('stochastic_seeds')}`",
        f"- OMPL process isolation: `{manifest.get('ompl_process_isolation')}`",
        f"- Rows: `{manifest.get('n_rows')}`",
        "",
        "## Interpretation",
        "",
        "All paired tasks use the same resolved `start_q` and Cartesian start tip. "
        "The physical Cartesian disk remains the goal predicate, while every "
        "planner receives the same frozen center + near-boundary representation.",
        "",
        "In this unconstrained convex free-space baseline, valid represented goals "
        "are expected to be input-linearly direct. The primary question is therefore "
        "planner representation/optimality relative to the direct represented-goal "
        "reference, not whether nonlocal routing is necessary.",
        "",
        "Primary cross-family timing is `total_wall_time_s`; query-only timing is "
        "reported as a secondary implementation diagnostic.",
        "",
        "## Planner summary",
        "",
        "| planner | n success | mean cost | mean subopt | mean total wall s | mean ΔJ F-G |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for planner, values in summary["planner_summary"].items():
        def fmt(v: Any) -> str:
            return "—" if v is None else f"{float(v):.5g}"
        lines.append(
            f"| `{planner}` | {values['n_success']} | "
            f"{fmt(values['mean_objective_cost'])} | "
            f"{fmt(values['mean_suboptimality_to_direct_reference'])} | "
            f"{fmt(values['mean_total_wall_time_s'])} | "
            f"{fmt(values['mean_delta_J_fourbar_minus_gearbox'])} |"
        )
    lines.extend(
        [
            "",
            "Files:",
            "",
            "- `resolved_bank.json` — audited shared starts and frozen goal points",
            "- `rows.json` — row-level evidence",
            "- `manifest.json` — implementation revision and run contract",
            "- `summary.json` — paired/suboptimality aggregates",
            "- `V3_6_FREE_SPACE_EVIDENCE_V2.html` — GitHub/print review",
            "",
            "This remains bounded evidence, not a population estimand or Monte Carlo campaign.",
            "",
        ]
    )
    return "\n".join(lines)


def build_html_v2(
    *,
    manifest: dict[str, Any],
    summary: dict[str, Any],
) -> str:
    esc = lambda x: html.escape(str(x))
    rows = []
    for planner, values in summary["planner_summary"].items():
        def fmt(v: Any) -> str:
            return "—" if v is None else f"{float(v):.5g}"
        rows.append(
            "<tr>"
            f"<td><code>{esc(planner)}</code></td>"
            f"<td>{values['n_success']}</td>"
            f"<td>{fmt(values['mean_objective_cost'])}</td>"
            f"<td>{fmt(values['mean_suboptimality_to_direct_reference'])}</td>"
            f"<td>{fmt(values['mean_total_wall_time_s'])}</td>"
            f"<td>{fmt(values['mean_delta_J_fourbar_minus_gearbox'])}</td>"
            "</tr>"
        )
    paired_json = html.escape(
        json.dumps(summary["by_paired"], indent=2, sort_keys=True)
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>V3.6 corrected free-space evidence</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#17212b}}
.banner{{padding:.8rem 1rem;background:#fff4d9;border:1px solid #ecd187;border-radius:8px}}
table{{border-collapse:collapse;width:100%;margin-top:1rem}}
th,td{{padding:.45rem;border-bottom:1px solid #d8dee6;text-align:left}}
code{{background:#eef2f6;padding:.1rem .25rem;border-radius:4px}}
pre{{background:#f6f8fa;padding:1rem;overflow:auto}}
</style>
</head>
<body>
<h1>Sprint V3.6 — corrected free-space evidence</h1>
<div class="banner">Bounded representation/optimality evidence only — not population inference.</div>
<p>Implementation revision <code>{esc(manifest.get('implementation_revision'))}</code>;
bank <code>{esc(manifest.get('bank_id'))}</code>;
frozen seeds <code>{esc(manifest.get('stochastic_seeds'))}</code>.</p>
<p>Paired mechanisms share the same resolved <code>start_q</code> and Cartesian
start. All planners consume one frozen represented Cartesian goal set. Primary
cross-family timing is total wall time.</p>
<h2>Planner summary</h2>
<table>
<thead><tr><th>planner</th><th>n success</th><th>mean cost</th><th>mean subopt</th><th>mean total wall s</th><th>mean ΔJ F-G</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table>
<h2>Paired strata</h2>
<pre>{paired_json}</pre>
</body>
</html>
"""


__all__ = [
    "build_html_v2",
    "build_readme_v2",
    "summarize_v3_6_v2",
]
