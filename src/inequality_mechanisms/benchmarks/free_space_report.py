"""HTML / README helpers for free-space evidence review (Sprint V3.6 / V3-604)."""

from __future__ import annotations

import html
import json
from collections import Counter, defaultdict
from typing import Any


def _esc(value: Any) -> str:
    return html.escape(str(value))


def _fmt_cost(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.4g}"
    except (TypeError, ValueError):
        return _esc(value)


def _fmt_time(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.3f}"
    except (TypeError, ValueError):
        return _esc(value)


def _is_success(row: dict[str, Any]) -> bool:
    if row.get("skipped"):
        return False
    status = str(row.get("status") or "").lower()
    return "success" in status


def summarize_strata(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate status and timing by size/paired stratum and planner."""
    by_size: dict[str, Counter[str]] = defaultdict(Counter)
    by_paired: dict[str, Counter[str]] = defaultdict(Counter)
    by_planner: dict[str, Counter[str]] = defaultdict(Counter)
    planner_cost: dict[str, list[float]] = defaultdict(list)
    planner_time: dict[str, list[float]] = defaultdict(list)

    for row in rows:
        planner = str(row.get("planner"))
        size = str(row.get("size_stratum"))
        paired = str(row.get("paired_stratum"))
        if row.get("skipped"):
            label = f"skipped:{row['skipped']}"
        else:
            label = str(row.get("status"))
        by_size[size][label] += 1
        by_paired[paired][label] += 1
        by_planner[planner][label] += 1
        if not _is_success(row):
            continue
        if row.get("objective_cost") is not None:
            planner_cost[planner].append(float(row["objective_cost"]))
        if row.get("query_time_s") is not None:
            planner_time[planner].append(float(row["query_time_s"]))

    return {
        "by_size": {k: dict(v) for k, v in sorted(by_size.items())},
        "by_paired": {k: dict(v) for k, v in sorted(by_paired.items())},
        "by_planner": {k: dict(v) for k, v in sorted(by_planner.items())},
        "planner_mean_cost": {
            k: (sum(v) / len(v) if v else None) for k, v in sorted(planner_cost.items())
        },
        "planner_mean_query_time_s": {
            k: (sum(v) / len(v) if v else None) for k, v in sorted(planner_time.items())
        },
        "n_success_by_planner": {k: len(v) for k, v in sorted(planner_cost.items())},
    }


def build_readme(
    *,
    manifest: dict[str, Any],
    summary: dict[str, Any],
) -> str:
    """Markdown README for the review package."""
    lines = [
        "# Version 3 review snapshot — V3.6 free-space evidence",
        "",
        "This directory is a **bounded free-space planner evidence package**, not a "
        "population study, Monte Carlo result, or obstacle campaign.",
        "",
        f"- Code revision: `{manifest.get('code_revision')}`",
        f"- Generated UTC: `{manifest.get('generated_at_utc')}`",
        f"- Bank: `{manifest.get('bank_id')}`",
        f"- Seed: `{manifest.get('seed')}`",
        f"- OMPL available: `{manifest.get('ompl_available')}`",
        f"- OMPL version: `{manifest.get('ompl_version')}`",
        f"- OMPL solve budget: `{manifest.get('ompl_solve_time_s')}` s",
        f"- Rows: `{manifest.get('n_rows')}` "
        f"({manifest.get('n_tasks')} tasks × {manifest.get('n_mechanisms')} mechanisms)",
        "",
        "## Reproducibility note",
        "",
        "Native stochastic planners reuse V3.4 `SMOKE_SEED` (7). OMPL adapters declare "
        "`reproducible_with_seed=False`: in-process seed setting is process-global "
        "best effort (RNG already started warnings are expected on multi-query runs). "
        "Frozen OMPL repetitions for strict comparison should use process isolation.",
        "",
        "## Status counts",
        "",
        "```json",
        json.dumps(manifest.get("status_counts", {}), indent=2, sort_keys=True),
        "```",
        "",
        "## Skip counts",
        "",
        "```json",
        json.dumps(manifest.get("skip_counts", {}), indent=2, sort_keys=True),
        "```",
        "",
        "## Planner success means (success rows only)",
        "",
        "| planner | n_success | mean objective_cost | mean query_time_s |",
        "| --- | ---: | ---: | ---: |",
    ]
    for planner, n_ok in summary["n_success_by_planner"].items():
        mean_c = summary["planner_mean_cost"].get(planner)
        mean_t = summary["planner_mean_query_time_s"].get(planner)
        lines.append(
            f"| `{planner}` | {n_ok} | "
            f"{'—' if mean_c is None else f'{mean_c:.4g}'} | "
            f"{'—' if mean_t is None else f'{mean_t:.3f}'} |"
        )
    lines.extend(
        [
            "",
            "Files:",
            "",
            "- `rows.json` — row-level evidence",
            "- `manifest.json` — run metadata",
            "- `summary.json` — stratum / planner aggregates",
            "- `V3_6_FREE_SPACE_EVIDENCE.html` — print-ready summary",
            "",
            "Regenerate with:",
            "",
            "```bash",
            "PYTHONPATH=src:. python scripts/run_v3_6_free_space_evidence.py",
            "```",
            "",
            "Prefer the OMPL-enabled interpreter (e.g. `.conda-ompl`) when publishing "
            "OMPL rows.",
            "",
        ]
    )
    return "\n".join(lines)


def build_html(
    *,
    manifest: dict[str, Any],
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
) -> str:
    """Print-ready HTML summary of free-space evidence."""
    planner_rows = []
    for planner, counts in summary["by_planner"].items():
        mean_c = summary["planner_mean_cost"].get(planner)
        mean_t = summary["planner_mean_query_time_s"].get(planner)
        n_ok = summary["n_success_by_planner"].get(planner, 0)
        planner_rows.append(
            "<tr>"
            f"<td><code>{_esc(planner)}</code></td>"
            f"<td>{_esc(counts)}</td>"
            f"<td>{n_ok}</td>"
            f"<td>{_fmt_cost(mean_c)}</td>"
            f"<td>{_fmt_time(mean_t)}</td>"
            "</tr>"
        )

    size_rows = [
        f"<tr><td>{_esc(size)}</td><td>{_esc(counts)}</td></tr>"
        for size, counts in summary["by_size"].items()
    ]
    paired_rows = [
        f"<tr><td>{_esc(paired)}</td><td>{_esc(counts)}</td></tr>"
        for paired, counts in summary["by_paired"].items()
    ]

    detail_rows = []
    for row in rows:
        detail_rows.append(
            "<tr>"
            f"<td>{_esc(row.get('task_id'))}</td>"
            f"<td>{_esc(row.get('mechanism'))}</td>"
            f"<td><code>{_esc(row.get('planner'))}</code></td>"
            f"<td>{_esc(row.get('task_class'))}</td>"
            f"<td>{_esc(row.get('size_stratum'))}</td>"
            f"<td>{_esc(row.get('paired_stratum'))}</td>"
            f"<td>{_esc(row.get('skipped') or row.get('status'))}</td>"
            f"<td>{_fmt_cost(row.get('objective_cost'))}</td>"
            f"<td>{_fmt_time(row.get('query_time_s'))}</td>"
            "</tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>V3.6 Free-Space Planner Evidence</title>
  <style>
    :root {{
      --ink: #122033; --muted: #5b6b7c; --line: #d7dee6;
      --paper: #f7f8fa; --card: #ffffff; --accent: #1f4e79;
      --warn: #8a5a00;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
      color: var(--ink); background: var(--paper); line-height: 1.45;
    }}
    header {{ background: var(--accent); color: #fff; padding: 1.6rem 2rem 1.4rem; }}
    header h1 {{ margin: 0 0 0.35rem; font-size: 1.55rem; font-weight: 650; }}
    header p {{ margin: 0; max-width: 78rem; color: #dbe7f3; }}
    .banner {{
      margin: 1rem 1.25rem 0; padding: 0.75rem 1rem;
      background: #fff4d9; border: 1px solid #f0d48a; color: var(--warn);
      border-radius: 10px; font-weight: 600;
    }}
    main {{ max-width: 78rem; margin: 0 auto; padding: 1.25rem 1.25rem 3rem; }}
    section {{
      background: var(--card); border: 1px solid var(--line);
      border-radius: 12px; padding: 1rem 1.1rem 1.15rem;
      margin-bottom: 1rem; break-inside: avoid;
    }}
    h2 {{ margin: 0 0 0.35rem; font-size: 1.12rem; }}
    p.note {{ color: var(--muted); font-size: 0.88rem; margin: 0 0 0.75rem; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.86rem; }}
    th, td {{
      border-bottom: 1px solid var(--line); text-align: left;
      padding: 0.35rem 0.4rem; vertical-align: top;
    }}
    th {{ color: var(--muted); font-weight: 600; }}
    code {{ background: #eef2f6; padding: 0.05rem 0.3rem; border-radius: 4px; font-size: 0.86em; }}
    .meta {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.75rem; }}
    .stat {{
      background: var(--card); border: 1px solid var(--line);
      border-radius: 10px; padding: 0.75rem 0.85rem;
    }}
    .stat .v {{ font-size: 1.2rem; font-weight: 700; color: var(--accent); }}
    .stat .l {{ color: var(--muted); font-size: 0.84rem; }}
    footer {{ color: var(--muted); font-size: 0.84rem; }}
    @media (max-width: 900px) {{ .meta {{ grid-template-columns: 1fr 1fr; }} }}
    @media print {{
      body {{ background: #fff; }}
      header {{
        background: #fff; color: #122033;
        border-bottom: 2px solid #1f4e79; padding: 0 0 0.8rem;
      }}
      header p {{ color: var(--muted); }}
      .banner {{ break-after: avoid; }}
      section {{ box-shadow: none; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Sprint V3.6 — Free-Space Planner Evidence</h1>
    <p>
      Frozen external Cartesian bank across delivered planner families under ADR-026
      pre-search classification and tip-distance size strata.
    </p>
  </header>
  <div class="banner">
    Not population evidence. Bounded hand-designed bank; do not treat means as
    estimands over a mechanism/task population.
  </div>
  <main>
    <div class="meta" style="margin: 1rem 0;">
      <div class="stat"><div class="v">{_esc(manifest.get('n_tasks'))}</div><div class="l">tasks</div></div>
      <div class="stat"><div class="v">{_esc(manifest.get('n_mechanisms'))}</div><div class="l">mechanisms</div></div>
      <div class="stat"><div class="v">{_esc(manifest.get('n_rows'))}</div><div class="l">rows</div></div>
      <div class="stat"><div class="v">{_esc(manifest.get('seed'))}</div><div class="l">seed</div></div>
    </div>

    <section>
      <h2>Run metadata</h2>
      <p class="note">
        Bank <code>{_esc(manifest.get('bank_id'))}</code> ·
        revision <code>{_esc(manifest.get('code_revision'))}</code> ·
        generated <code>{_esc(manifest.get('generated_at_utc'))}</code> ·
        OMPL available <code>{_esc(manifest.get('ompl_available'))}</code>
        (budget {_esc(manifest.get('ompl_solve_time_s'))}s)
      </p>
      <p class="note">Planners: {_esc(', '.join(manifest.get('planners') or []))}</p>
    </section>

    <section>
      <h2>Planner summary</h2>
      <p class="note">Status/skip counts and mean cost/time on success rows only.</p>
      <table>
        <thead>
          <tr>
            <th>planner</th><th>status/skip counts</th><th>n success</th>
            <th>mean cost</th><th>mean query_time_s</th>
          </tr>
        </thead>
        <tbody>
          {''.join(planner_rows)}
        </tbody>
      </table>
    </section>

    <section>
      <h2>Size strata</h2>
      <p class="note">Pre-search tip-separation bins only (not planner-outcome difficulty).</p>
      <table>
        <thead><tr><th>size_stratum</th><th>counts</th></tr></thead>
        <tbody>{''.join(size_rows)}</tbody>
      </table>
    </section>

    <section>
      <h2>Paired strata</h2>
      <p class="note">ADR-026 paired labels from both arms on the same external task.</p>
      <table>
        <thead><tr><th>paired_stratum</th><th>counts</th></tr></thead>
        <tbody>{''.join(paired_rows)}</tbody>
      </table>
    </section>

    <section>
      <h2>Row detail</h2>
      <p class="note">Full machine-readable rows are in <code>rows.json</code>.</p>
      <table>
        <thead>
          <tr>
            <th>task</th><th>mech</th><th>planner</th><th>class</th>
            <th>size</th><th>paired</th><th>status/skip</th><th>cost</th><th>query_s</th>
          </tr>
        </thead>
        <tbody>
          {''.join(detail_rows)}
        </tbody>
      </table>
    </section>

    <footer>
      Scope: Sprint V3.6 free-space evidence only. Obstacles, MoveIt, and Monte Carlo
      populations are out of scope.
    </footer>
  </main>
</body>
</html>
"""
