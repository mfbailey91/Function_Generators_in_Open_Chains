"""HTML canvas consolidating a completed Sprint Five path-quality run.

Derived viewer: reads registry artifacts and writes ``index.html`` beside
them without mutating trial JSONL.
"""

from __future__ import annotations

import csv
import html
import io
import json
from pathlib import Path
from typing import Any

from inequality_mechanisms.experiments.canvas import (
    _figure_grid,
    _fmt_num,
    _paired_ratio_rows,
    _path_metric_summary,
    _path_sample_figures,
    _rel_if_exists,
    _summary_stats_rows,
    resolve_run_for_canvas,
)
from inequality_mechanisms.experiments.registry import (
    ExperimentRun,
    RunRegistryError,
)

_CANVAS_NAME = "index.html"

_PATH_QUALITY_FIGURES = (
    ("paired_path_length_u", "outputs/paired_path_length_u.png", "Paired L_U"),
    ("paired_path_length_q", "outputs/paired_path_length_q.png", "Paired L_Q"),
    ("paired_path_length_x", "outputs/paired_path_length_x.png", "Paired L_X"),
    ("paired_directness_q", "outputs/paired_directness_q.png", "Paired R_Q"),
    ("paired_directness_x", "outputs/paired_directness_x.png", "Paired R_X"),
    ("paired_turning_q", "outputs/paired_turning_q.png", "Paired T_Q"),
    ("paired_turning_x", "outputs/paired_turning_x.png", "Paired T_X"),
    (
        "self_intersections_x_hist",
        "outputs/self_intersections_x_hist.png",
        "X self-intersection histogram",
    ),
    (
        "near_revisit_x_hist",
        "outputs/near_revisit_x_hist.png",
        "X near-revisit distance histogram",
    ),
    (
        "expansions_vs_directness_x",
        "outputs/expansions_vs_directness_x.png",
        "Expansions vs R_X",
    ),
    (
        "expansions_vs_turning_x",
        "outputs/expansions_vs_turning_x.png",
        "Expansions vs T_X",
    ),
)

_EXPANSION_FIGURES = (
    ("expansions_raw", "outputs/expansions_raw.png", "Raw expansions"),
    (
        "expansions_normalized",
        "outputs/expansions_normalized.png",
        "Normalized expansions (ρ)",
    ),
    (
        "expansions_ratio",
        "outputs/expansions_ratio.png",
        "Paired log-ratio log(N₄ʀ / N_gear)",
    ),
)

_TABLE_OUTPUTS = (
    ("path_length_summary", "Path lengths"),
    ("directness_summary", "Directness ratios"),
    ("turning_summary", "Cumulative turning"),
    ("intersection_revisit_summary", "Intersections & near-revisits"),
    ("equal_cost_path_degeneracy_table", "Equal-cost Dijkstra/A*"),
)


def _collect_figures(
    run: ExperimentRun, catalog: tuple[tuple[str, str, str], ...]
) -> list[dict[str, str]]:
    figures: list[dict[str, str]] = []
    for name, fallback_rel, caption in catalog:
        rel = run.outputs.get(name)
        if rel is None:
            rel = _rel_if_exists(run, fallback_rel)
        if rel is None:
            continue
        figures.append({"name": name, "src": rel, "caption": caption})
    return figures


def _path_quality_cards(run: ExperimentRun) -> list[dict[str, str]]:
    root = run.path / "path_quality"
    if not root.is_dir():
        return []
    figures: list[dict[str, str]] = []
    meta_path = root / "representative_trials.json"
    captions: dict[str, str] = {}
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            meta = []
        if isinstance(meta, list):
            for item in meta:
                if not isinstance(item, dict):
                    continue
                fname = str(item.get("file") or "")
                reason = item.get("reason") or ""
                trial = item.get("trial_index")
                mech = item.get("mechanism")
                captions[fname] = (
                    f"trial {trial} / {mech} — {reason}"
                    if trial is not None
                    else fname
                )
    for png in sorted(root.glob("representative_trial_*.png")):
        rel = png.relative_to(run.path).as_posix()
        figures.append(
            {
                "src": rel,
                "caption": captions.get(png.name, png.stem),
            }
        )
    return figures


def _csv_to_html_table(csv_text: str) -> str:
    if not csv_text.strip():
        return "<p class='muted'>No table data.</p>"
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)
    if not rows:
        return "<p class='muted'>No table data.</p>"
    parts = ["<table><thead><tr>"]
    for cell in rows[0]:
        parts.append(f"<th>{html.escape(cell)}</th>")
    parts.append("</tr></thead><tbody>")
    for row in rows[1:]:
        parts.append("<tr>")
        for cell in row:
            parts.append(f"<td>{html.escape(cell)}</td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "\n".join(parts)


def _quality_metric_summary(run: ExperimentRun) -> dict[str, Any]:
    """Mean path-quality scalars over found Dijkstra trials."""
    if "trials" not in run.outputs:
        return {}
    try:
        rows = run.read_jsonl("trials")
    except Exception:
        return {}
    found = [
        r
        for r in rows
        if isinstance(r, dict)
        and r.get("found")
        and str(r.get("algorithm")) == "dijkstra"
    ]
    if not found:
        return {"n_found": 0}

    def _mean(key: str) -> float | None:
        vals = []
        for r in found:
            v = r.get(key)
            if v is None:
                continue
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            vals.append(fv)
        if not vals:
            return None
        return float(sum(vals) / len(vals))

    n_def_x = sum(1 for r in found if r.get("directness_defined_x") is True)
    n_cross_x = sum(
        1 for r in found if int(r.get("self_intersections_x") or 0) > 0
    )
    return {
        "n_found": len(found),
        "mean_path_length_u": _mean("path_length_u"),
        "mean_path_length_q": _mean("path_length_q"),
        "mean_path_length_x": _mean("path_length_x"),
        "mean_directness_q": _mean("directness_ratio_q"),
        "mean_directness_x": _mean("directness_ratio_x"),
        "mean_turning_q": _mean("cumulative_turning_q"),
        "mean_turning_x": _mean("cumulative_turning_x"),
        "mean_near_revisit_x": _mean("near_revisit_distance_x"),
        "n_directness_defined_x": n_def_x,
        "n_with_x_intersection": n_cross_x,
    }


def collect_sprint5_canvas_payload(run: ExperimentRun) -> dict[str, Any]:
    """Collect Sprint Five artifacts for the HTML canvas."""
    if run.status != "completed":
        raise RunRegistryError(
            f"canvas requires a completed run; {run.run_id!r} status={run.status!r}"
        )

    summary: dict[str, Any] = {}
    if "summary" in run.outputs:
        loaded = run.read_json("summary")
        if isinstance(loaded, dict):
            summary = loaded

    config_text = ""
    if run.config_path.is_file():
        config_text = run.config_path.read_text(encoding="utf-8")

    tables: list[dict[str, str]] = []
    for name, caption in _TABLE_OUTPUTS:
        if name not in run.outputs:
            continue
        text = run.resolve_output(name).read_text(encoding="utf-8")
        tables.append({"name": name, "caption": caption, "csv": text})

    equal_cost: dict[str, Any] = {}
    if "equal_cost_path_degeneracy" in run.outputs:
        loaded = run.read_json("equal_cost_path_degeneracy")
        if isinstance(loaded, dict):
            equal_cost = loaded

    bootstrap: dict[str, Any] = {}
    if "bootstrap_cis" in run.outputs:
        loaded = run.read_json("bootstrap_cis")
        if isinstance(loaded, dict):
            bootstrap = loaded

    metric_cfg: dict[str, Any] = {}
    if "metric_configuration" in run.outputs:
        loaded = run.read_json("metric_configuration")
        if isinstance(loaded, dict):
            metric_cfg = loaded

    return {
        "run_id": run.run_id,
        "status": run.status,
        "seed": run.seed,
        "path": str(run.path),
        "revision": run.revision,
        "environment": {
            "python_version": run.environment.get("python_version"),
            "platform": run.environment.get("platform"),
        },
        "manifest": {
            "created_at": run._manifest.get("created_at"),
            "completed_at": run._manifest.get("completed_at"),
            "outputs": run.outputs,
        },
        "summary": summary,
        "config_yaml": config_text,
        "path_metrics": _path_metric_summary(run),
        "quality_metrics": _quality_metric_summary(run),
        "path_quality_figures": _collect_figures(run, _PATH_QUALITY_FIGURES),
        "expansion_figures": _collect_figures(run, _EXPANSION_FIGURES),
        "path_quality_cards": _path_quality_cards(run),
        "path_samples": _path_sample_figures(run),
        "tables": tables,
        "equal_cost": equal_cost,
        "bootstrap": bootstrap,
        "metric_configuration": metric_cfg,
        "result_schema_version": summary.get("result_schema_version"),
        "cost_types": summary.get("cost_types")
        or (summary.get("graph_meta") or {}).get("cost_types"),
    }


def _bootstrap_rows(bootstrap: dict[str, Any]) -> str:
    pq = bootstrap.get("path_quality") if isinstance(bootstrap, dict) else None
    if not isinstance(pq, dict):
        return "<tr><td colspan='5'>No path-quality bootstrap intervals.</td></tr>"
    intervals = pq.get("intervals") or []
    if not isinstance(intervals, list) or not intervals:
        return "<tr><td colspan='5'>No path-quality bootstrap intervals.</td></tr>"
    rows: list[str] = []
    for item in intervals:
        if not isinstance(item, dict):
            continue
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(item.get('metric')))}</td>"
            f"<td>{_fmt_num(item.get('estimate'))}</td>"
            f"<td>{_fmt_num(item.get('ci_low'))}</td>"
            f"<td>{_fmt_num(item.get('ci_high'))}</td>"
            f"<td>{_fmt_num(item.get('n_pairs'))}</td>"
            "</tr>"
        )
    return "\n".join(rows) if rows else (
        "<tr><td colspan='5'>No path-quality bootstrap intervals.</td></tr>"
    )


def _equal_cost_kv(equal_cost: dict[str, Any]) -> str:
    if not equal_cost:
        return "<p class='muted'>No equal-cost report.</p>"
    by_cost = equal_cost.get("by_cost_type") or {}
    rows = [
        "<dl class='kv'>",
        f"<dt>matched pairs</dt><dd>{_fmt_num(equal_cost.get('n_matched_pairs'))}</dd>",
        f"<dt>same optimal cost</dt><dd>{_fmt_num(equal_cost.get('n_same_optimal_cost'))}</dd>",
        f"<dt>same node path</dt><dd>{_fmt_num(equal_cost.get('n_same_node_path'))}</dd>",
        (
            "<dt>diff path (same cost)</dt>"
            f"<dd>{_fmt_num(equal_cost.get('n_diff_node_path_same_cost'))}</dd>"
        ),
        (
            "<dt>tie-breaking</dt>"
            f"<dd>{html.escape(str(equal_cost.get('tie_breaking_policy') or '—'))}</dd>"
        ),
        "</dl>",
    ]
    if isinstance(by_cost, dict) and by_cost:
        rows.append("<table><thead><tr>")
        rows.append(
            "<th>cost_type</th><th>n_pairs</th><th>same cost</th>"
            "<th>same path</th><th>diff path</th></tr></thead><tbody>"
        )
        for cost_type in sorted(by_cost):
            stats = by_cost[cost_type]
            if not isinstance(stats, dict):
                continue
            rows.append(
                "<tr>"
                f"<td>{html.escape(str(cost_type))}</td>"
                f"<td>{_fmt_num(stats.get('n_pairs'))}</td>"
                f"<td>{_fmt_num(stats.get('n_same_optimal_cost'))}</td>"
                f"<td>{_fmt_num(stats.get('n_same_node_path'))}</td>"
                f"<td>{_fmt_num(stats.get('n_diff_node_path_same_cost'))}</td>"
                "</tr>"
            )
        rows.append("</tbody></table>")
    return "\n".join(rows)


def render_sprint5_canvas_html(payload: dict[str, Any]) -> str:
    """Render a dark diagnostic HTML canvas for Sprint Five outputs."""
    run_id = html.escape(str(payload.get("run_id", "")))
    seed = html.escape(str(payload.get("seed", "")))
    status = html.escape(str(payload.get("status", "")))
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    revision = payload.get("revision") if isinstance(payload.get("revision"), dict) else {}
    manifest = payload.get("manifest") if isinstance(payload.get("manifest"), dict) else {}
    environment = (
        payload.get("environment")
        if isinstance(payload.get("environment"), dict)
        else {}
    )
    graph_meta = (
        summary.get("graph_meta")
        if isinstance(summary.get("graph_meta"), dict)
        else {}
    )
    quality = (
        payload.get("quality_metrics")
        if isinstance(payload.get("quality_metrics"), dict)
        else {}
    )
    equal_cost = (
        payload.get("equal_cost") if isinstance(payload.get("equal_cost"), dict) else {}
    )
    bootstrap = (
        payload.get("bootstrap") if isinstance(payload.get("bootstrap"), dict) else {}
    )
    metric_cfg = (
        payload.get("metric_configuration")
        if isinstance(payload.get("metric_configuration"), dict)
        else {}
    )

    cost_types = payload.get("cost_types") or graph_meta.get("cost_types") or []
    if isinstance(cost_types, list) and cost_types:
        cost_label = ", ".join(str(c) for c in cost_types)
    else:
        cost_label = "—"
    schema = (
        payload.get("result_schema_version")
        or summary.get("result_schema_version")
        or "—"
    )
    git_describe = revision.get("git_describe") or "—"
    git_dirty = revision.get("git_dirty")
    dirty_label = (
        "dirty"
        if git_dirty is True
        else ("clean" if git_dirty is False else "unknown")
    )

    pq_figures = (
        payload.get("path_quality_figures")
        if isinstance(payload.get("path_quality_figures"), list)
        else []
    )
    expansion_figures = (
        payload.get("expansion_figures")
        if isinstance(payload.get("expansion_figures"), list)
        else []
    )
    cards = (
        payload.get("path_quality_cards")
        if isinstance(payload.get("path_quality_cards"), list)
        else []
    )
    path_samples = (
        payload.get("path_samples")
        if isinstance(payload.get("path_samples"), list)
        else []
    )
    tables = payload.get("tables") if isinstance(payload.get("tables"), list) else []
    table_sections = []
    for table in tables:
        if not isinstance(table, dict):
            continue
        table_sections.append(
            f"<h3>{html.escape(str(table.get('caption') or table.get('name')))}</h3>"
            f"{_csv_to_html_table(str(table.get('csv') or ''))}"
        )
    tables_html = (
        "\n".join(table_sections)
        if table_sections
        else "<p class='muted'>No summary tables registered.</p>"
    )

    pq_cfg = metric_cfg.get("path_quality") if isinstance(metric_cfg, dict) else {}
    if not isinstance(pq_cfg, dict):
        pq_cfg = graph_meta.get("path_quality") or {}
    if not isinstance(pq_cfg, dict):
        pq_cfg = {}

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Sprint Five Path Quality — {run_id}</title>
<style>
  :root {{
    --bg: #0f1419;
    --panel: #1a222c;
    --ink: #e8eef4;
    --muted: #9aabba;
    --accent: #5eb1ff;
    --line: #2a3542;
    --ok: #8fd19e;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
    background: radial-gradient(1200px 600px at 10% -10%, #1c3048, var(--bg));
    color: var(--ink);
    line-height: 1.45;
  }}
  header {{
    padding: 2rem 2rem 1rem;
    border-bottom: 1px solid var(--line);
  }}
  header h1 {{
    margin: 0 0 0.35rem;
    font-family: "IBM Plex Serif", Georgia, serif;
    font-weight: 600;
    letter-spacing: -0.02em;
  }}
  header p {{ margin: 0; color: var(--muted); max-width: 56rem; }}
  nav {{
    display: flex; flex-wrap: wrap; gap: 0.5rem;
    padding: 0.75rem 2rem;
    position: sticky; top: 0;
    background: rgba(15,20,25,0.92);
    backdrop-filter: blur(8px);
    border-bottom: 1px solid var(--line);
    z-index: 2;
  }}
  nav a {{
    color: var(--accent); text-decoration: none;
    font-size: 0.85rem; padding: 0.25rem 0.55rem;
    border: 1px solid var(--line); border-radius: 4px;
  }}
  nav a:hover {{ border-color: var(--accent); }}
  main {{ padding: 1.25rem 2rem 3rem; display: grid; gap: 1.5rem; }}
  section {{
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 1rem 1.1rem 1.25rem;
  }}
  section h2 {{ margin: 0 0 0.35rem; font-size: 1.15rem; }}
  section h3 {{ margin: 1rem 0 0.4rem; font-size: 0.95rem; color: var(--muted); }}
  .muted {{ color: var(--muted); font-size: 0.85rem; margin: 0 0 0.75rem; }}
  .ok {{ color: var(--ok); }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 0.85rem;
  }}
  figure {{ margin: 0; }}
  figure img {{
    width: 100%; height: auto; display: block;
    border-radius: 6px; background: #0b1015;
    border: 1px solid var(--line);
  }}
  figcaption {{ color: var(--muted); font-size: 0.8rem; margin-top: 0.35rem; }}
  table {{
    width: 100%; border-collapse: collapse; font-size: 0.85rem;
    margin-bottom: 0.75rem;
  }}
  th, td {{
    text-align: left; padding: 0.4rem 0.55rem;
    border-bottom: 1px solid var(--line);
  }}
  th {{ color: var(--muted); font-weight: 500; }}
  pre {{
    overflow: auto; background: #0b1015; border-radius: 6px;
    padding: 0.75rem; font-size: 0.75rem; color: #c5d4e0;
    border: 1px solid var(--line); max-height: 22rem;
  }}
  .flow {{
    display: flex; flex-wrap: wrap; gap: 0.4rem; align-items: center;
    margin: 0.75rem 0 0; font-size: 0.85rem; color: var(--muted);
  }}
  .chip {{
    background: #243040; color: var(--ink);
    padding: 0.2rem 0.5rem; border-radius: 999px;
  }}
  dl.kv {{
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 0.25rem 1rem;
    margin: 0 0 0.85rem;
    font-size: 0.85rem;
  }}
  dl.kv dt {{ color: var(--muted); }}
  dl.kv dd {{ margin: 0; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
</style>
</head>
<body>
<header>
  <h1>Sprint Five — Path Quality</h1>
  <p>
    Consolidated viewer for a paired gearbox / four-bar path-quality study.
    Length, directness, turning, crossings, and revisits are shown separately
    in U, Q, and X — no composite score.
  </p>
  <div class="flow">
    <span class="chip">run {run_id}</span>
    <span class="chip">seed {seed}</span>
    <span class="chip">{status}</span>
    <span class="chip">schema {html.escape(str(schema))}</span>
    <span class="chip">costs {html.escape(cost_label)}</span>
    <span class="chip">trials {html.escape(str(summary.get('n_trials_config', '—')))}</span>
    <span class="chip">git {html.escape(str(git_describe))} ({dirty_label})</span>
  </div>
</header>
<nav>
  <a href="#provenance">Provenance</a>
  <a href="#quality">Path quality</a>
  <a href="#equal-cost">Equal-cost</a>
  <a href="#figures">Figures</a>
  <a href="#paths">Path samples</a>
  <a href="#cards">Cards</a>
  <a href="#tables">Tables</a>
  <a href="#bootstrap">Bootstrap</a>
  <a href="#expansions">Expansions</a>
  <a href="#config">Config</a>
</nav>
<main>
  <section id="provenance">
    <h2>Provenance</h2>
    <p class="muted ok">Pass: seed, frozen config, and revision recorded with the run (ADR-007).</p>
    <dl class="kv">
      <dt>run_id</dt><dd>{run_id}</dd>
      <dt>seed</dt><dd>{seed}</dd>
      <dt>status</dt><dd>{status}</dd>
      <dt>study</dt><dd>{html.escape(str(summary.get('study') or 'sprint5_path_quality'))}</dd>
      <dt>result_schema_version</dt><dd>{html.escape(str(schema))}</dd>
      <dt>cost_types</dt><dd>{html.escape(cost_label)}</dd>
      <dt>created_at</dt><dd>{html.escape(str(manifest.get('created_at') or '—'))}</dd>
      <dt>completed_at</dt><dd>{html.escape(str(manifest.get('completed_at') or '—'))}</dd>
      <dt>git_commit</dt><dd>{html.escape(str(revision.get('git_commit') or '—'))}</dd>
      <dt>platform</dt><dd>{html.escape(str(environment.get('platform') or '—'))}</dd>
      <dt>revisit_exclusion_steps</dt><dd>{html.escape(str(pq_cfg.get('revisit_exclusion_steps', '—')))}</dd>
      <dt>revisit_threshold_q</dt><dd>{html.escape(str(pq_cfg.get('revisit_threshold_q', '—')))}</dd>
      <dt>revisit_threshold_x</dt><dd>{html.escape(str(pq_cfg.get('revisit_threshold_x', '—')))}</dd>
    </dl>
  </section>

  <section id="quality">
    <h2>Path-quality overview (Dijkstra found trials)</h2>
    <p class="muted">Means over found Dijkstra rows. Directness may be undefined for coincident endpoints.</p>
    <table>
      <thead>
        <tr>
          <th>n_found</th>
          <th>mean L_U</th><th>mean L_Q</th><th>mean L_X</th>
          <th>mean R_Q</th><th>mean R_X</th>
          <th>mean T_Q</th><th>mean T_X</th>
          <th>X crossings</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>{_fmt_num(quality.get('n_found'))}</td>
          <td>{_fmt_num(quality.get('mean_path_length_u'))}</td>
          <td>{_fmt_num(quality.get('mean_path_length_q'))}</td>
          <td>{_fmt_num(quality.get('mean_path_length_x'))}</td>
          <td>{_fmt_num(quality.get('mean_directness_q'))}</td>
          <td>{_fmt_num(quality.get('mean_directness_x'))}</td>
          <td>{_fmt_num(quality.get('mean_turning_q'))}</td>
          <td>{_fmt_num(quality.get('mean_turning_x'))}</td>
          <td>{_fmt_num(quality.get('n_with_x_intersection'))}</td>
        </tr>
      </tbody>
    </table>
    <h3>Search summary</h3>
    <table>
      <thead>
        <tr>
          <th>algorithm</th><th>mechanism</th><th>found</th>
          <th>median N_expanded</th><th>mean ρ</th><th>unreachable</th>
        </tr>
      </thead>
      <tbody>
{_summary_stats_rows(summary)}
      </tbody>
    </table>
  </section>

  <section id="equal-cost">
    <h2>Equal-cost Dijkstra vs A*</h2>
    <p class="muted">Same optimal cost does not imply the same path; secondary qualities may differ.</p>
{_equal_cost_kv(equal_cost)}
  </section>

  <section id="figures">
    <h2>Path-quality figures</h2>
    <p class="muted">Paired gearbox vs four-bar comparisons and effort-vs-quality scatters.</p>
{_figure_grid(pq_figures, empty="No path-quality PNGs found under outputs/.")}
  </section>

  <section id="paths">
    <h2>Path samples (start → goal)</h2>
    <p class="muted">
      U / Q / Cartesian path overlays for the first
      <code>trials.n_path_samples</code> kept trials. Fresh
      <code>--seed</code> draws new start/goal pairs each smoke run.
    </p>
{_figure_grid(path_samples, empty="No path-sample figures in this run (set trials.n_path_samples &gt; 0).")}
  </section>

  <section id="cards">
    <h2>Representative path-quality cards</h2>
    <p class="muted">Deterministic selection (median Δ expansions, max R_X / T_X Δ, intersections, revisits).</p>
{_figure_grid(cards, empty="No representative cards in path_quality/.")}
  </section>

  <section id="tables">
    <h2>Summary tables</h2>
    <p class="muted">Mechanism × cost means from registered CSV artifacts.</p>
{tables_html}
  </section>

  <section id="bootstrap">
    <h2>Paired bootstrap CIs (path quality)</h2>
    <p class="muted">Four-bar − gearbox mean differences; percentile intervals.</p>
    <table>
      <thead>
        <tr><th>metric</th><th>estimate</th><th>ci_low</th><th>ci_high</th><th>n_pairs</th></tr>
      </thead>
      <tbody>
{_bootstrap_rows(bootstrap)}
      </tbody>
    </table>
  </section>

  <section id="expansions">
    <h2>Search-effort figures</h2>
    <p class="muted">Sprint Four expansion comparisons retained for effort-vs-quality context.</p>
{_figure_grid(expansion_figures, empty="No expansion PNGs found under outputs/.")}
    <h3>Paired log-ratios</h3>
    <table>
      <thead>
        <tr><th>algorithm</th><th>n_pairs</th><th>median</th><th>mean</th></tr>
      </thead>
      <tbody>
{_paired_ratio_rows(summary)}
      </tbody>
    </table>
  </section>

  <section id="config">
    <h2>Frozen config.yaml</h2>
    <pre>{html.escape(str(payload.get('config_yaml') or '')) if payload.get('config_yaml') else 'config.yaml missing'}</pre>
    <h3>summary.json</h3>
    <pre>{html.escape(json.dumps(summary, indent=2, sort_keys=True))}</pre>
  </section>
</main>
</body>
</html>
"""


def write_sprint5_canvas(
    run: ExperimentRun | str | Path,
    *,
    results_root: Path | str | None = None,
    filename: str = _CANVAS_NAME,
) -> Path:
    """Write ``index.html`` consolidating a completed Sprint Five run."""
    if isinstance(run, ExperimentRun):
        handle = run
        if handle.status != "completed":
            raise RunRegistryError(
                f"canvas requires a completed run; "
                f"{handle.run_id!r} status={handle.status!r}"
            )
    else:
        handle = resolve_run_for_canvas(run, results_root=results_root)

    payload = collect_sprint5_canvas_payload(handle)
    html_text = render_sprint5_canvas_html(payload)
    out = handle.path / filename
    out.write_text(html_text, encoding="utf-8")
    if handle.status != "completed":
        try:
            handle.register_output("canvas", filename)
        except Exception:
            pass
    return out.resolve()
