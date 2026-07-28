"""HTML canvas consolidating a completed Sprint Six study run.

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

_STABILITY_FIGURES = (
    (
        "gain_matching",
        "outputs/figures/gain_matching.png",
        "Four-bar gain vs matched linear baseline",
    ),
    (
        "resolution_stability",
        "outputs/figures/resolution_stability.png",
        "Resolution stability (nodes / runtime / effect)",
    ),
    (
        "monte_carlo_stability",
        "outputs/figures/monte_carlo_stability.png",
        "Monte Carlo precision vs mechanism count",
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
    ("trials_table", "Trial rows"),
    ("resolution_table", "Resolution sweep"),
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


def _json_table(
    rows: list[Any],
    *,
    columns: list[tuple[str, str]],
    empty: str,
) -> str:
    if not rows:
        return f"<p class='muted'>{html.escape(empty)}</p>"
    parts = ["<table><thead><tr>"]
    for _, label in columns:
        parts.append(f"<th>{html.escape(label)}</th>")
    parts.append("</tr></thead><tbody>")
    for row in rows:
        if not isinstance(row, dict):
            continue
        parts.append("<tr>")
        for key, _ in columns:
            parts.append(f"<td>{_fmt_num(row.get(key))}</td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "\n".join(parts)


def _read_json_dict(run: ExperimentRun, name: str) -> dict[str, Any]:
    if name not in run.outputs:
        return {}
    loaded = run.read_json(name)
    return loaded if isinstance(loaded, dict) else {}


def collect_sprint6_canvas_payload(run: ExperimentRun) -> dict[str, Any]:
    """Collect Sprint Six artifacts for the HTML canvas."""
    if run.status != "completed":
        raise RunRegistryError(
            f"canvas requires a completed run; {run.run_id!r} status={run.status!r}"
        )

    summary = _read_json_dict(run, "summary")
    config_text = ""
    if run.config_path.is_file():
        config_text = run.config_path.read_text(encoding="utf-8")

    tables: list[dict[str, str]] = []
    for name, caption in _TABLE_OUTPUTS:
        if name not in run.outputs:
            continue
        text = run.resolve_output(name).read_text(encoding="utf-8")
        tables.append({"name": name, "caption": caption, "csv": text})

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
        "equivalence": _read_json_dict(run, "equivalence"),
        "equivalence_summary": _read_json_dict(run, "equivalence_summary"),
        "resolution_sweep": _read_json_dict(run, "resolution_sweep"),
        "production_resolution": _read_json_dict(run, "production_resolution"),
        "mechanism_effects": _read_json_dict(run, "mechanism_effects"),
        "hierarchical_bootstrap": _read_json_dict(run, "hierarchical_bootstrap"),
        "sample_size_plan": _read_json_dict(run, "sample_size_plan"),
        "sequential_precision": _read_json_dict(run, "sequential_precision"),
        "high_resolution_confirmation": _read_json_dict(
            run, "high_resolution_confirmation"
        ),
        "exclusions": _read_json_dict(run, "exclusions"),
        "sample_bank": _read_json_dict(run, "sample_bank"),
        "stability_figures": _collect_figures(run, _STABILITY_FIGURES),
        "expansion_figures": _collect_figures(run, _EXPANSION_FIGURES),
        "path_samples": _path_sample_figures(run),
        "path_metrics": _path_metric_summary(run),
        "tables": tables,
        "result_schema_version": summary.get("result_schema_version"),
    }


def _equiv_kv(equivalence: dict[str, Any]) -> str:
    if not equivalence:
        return "<p class='muted'>No equivalence report.</p>"
    graph = equivalence.get("graph_match")
    graph_ok = graph.get("ok") if isinstance(graph, dict) else None
    rows = [
        "<dl class='kv'>",
        (
            "<dt>matching_rule</dt>"
            f"<dd>{html.escape(str(equivalence.get('matching_rule') or '—'))}</dd>"
        ),
        (
            "<dt>baseline_label</dt>"
            f"<dd>{html.escape(str(equivalence.get('baseline_label') or '—'))}</dd>"
        ),
        (
            "<dt>ratios</dt>"
            f"<dd>{html.escape(str(equivalence.get('ratios') or '—'))}</dd>"
        ),
        f"<dt>graph_match.ok</dt><dd>{_fmt_num(graph_ok)}</dd>",
        "</dl>",
    ]
    for rule_key in ("span", "total_variation", "rms_gain"):
        sub = equivalence.get(rule_key)
        if not isinstance(sub, dict):
            continue
        rows.append(f"<h3>{html.escape(rule_key)} invariant</h3>")
        rows.append(
            f"<p class='muted'>ok={html.escape(str(sub.get('ok')))}</p>"
        )
        axes = sub.get("axes") if isinstance(sub.get("axes"), list) else []
        rows.append(
            _json_table(
                axes,
                columns=[
                    ("axis", "axis"),
                    ("delta_u_gb", "ΔU_gb"),
                    ("delta_u_fb", "ΔU_fb"),
                    ("delta_q_gb", "ΔQ_gb"),
                    ("delta_q_fb", "ΔQ_fb"),
                    ("r_tv_du", "r·Δu"),
                    ("tv_fb", "TV"),
                    ("r_rms", "r_RMS"),
                    ("rms_fb", "RMS"),
                    ("ok", "ok"),
                ],
                empty="No axis rows.",
            )
        )
    return "\n".join(rows)


def render_sprint6_canvas_html(payload: dict[str, Any]) -> str:
    """Render a dark diagnostic HTML canvas for Sprint Six outputs."""
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

    equivalence = (
        payload.get("equivalence") if isinstance(payload.get("equivalence"), dict) else {}
    )
    equiv_summary = (
        payload.get("equivalence_summary")
        if isinstance(payload.get("equivalence_summary"), dict)
        else {}
    )
    resolution = (
        payload.get("resolution_sweep")
        if isinstance(payload.get("resolution_sweep"), dict)
        else {}
    )
    production = (
        payload.get("production_resolution")
        if isinstance(payload.get("production_resolution"), dict)
        else {}
    )
    mech_effects = (
        payload.get("mechanism_effects")
        if isinstance(payload.get("mechanism_effects"), dict)
        else {}
    )
    hci = (
        payload.get("hierarchical_bootstrap")
        if isinstance(payload.get("hierarchical_bootstrap"), dict)
        else {}
    )
    sample_size = (
        payload.get("sample_size_plan")
        if isinstance(payload.get("sample_size_plan"), dict)
        else {}
    )
    precision = (
        payload.get("sequential_precision")
        if isinstance(payload.get("sequential_precision"), dict)
        else {}
    )
    confirmation = (
        payload.get("high_resolution_confirmation")
        if isinstance(payload.get("high_resolution_confirmation"), dict)
        else {}
    )
    exclusions = (
        payload.get("exclusions") if isinstance(payload.get("exclusions"), dict) else {}
    )
    sample_bank = (
        payload.get("sample_bank") if isinstance(payload.get("sample_bank"), dict) else {}
    )
    figures = (
        payload.get("stability_figures")
        if isinstance(payload.get("stability_figures"), list)
        else []
    )
    expansion_figures = (
        payload.get("expansion_figures")
        if isinstance(payload.get("expansion_figures"), list)
        else []
    )
    path_samples = (
        payload.get("path_samples")
        if isinstance(payload.get("path_samples"), list)
        else []
    )
    path_metrics = (
        payload.get("path_metrics")
        if isinstance(payload.get("path_metrics"), dict)
        else {}
    )
    cartesian_samples = [
        f
        for f in path_samples
        if isinstance(f, dict) and "cartesian" in str(f.get("caption", "")).lower()
    ]
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

    matched_rows = (
        equiv_summary.get("rows") if isinstance(equiv_summary.get("rows"), list) else []
    )
    resolution_rows = (
        resolution.get("rows") if isinstance(resolution.get("rows"), list) else []
    )
    effect_rows = (
        mech_effects.get("rows") if isinstance(mech_effects.get("rows"), list) else []
    )
    batch_rows = (
        precision.get("batches") if isinstance(precision.get("batches"), list) else []
    )
    exclusion_rows = (
        exclusions.get("rows") if isinstance(exclusions.get("rows"), list) else []
    )
    bank_mechs = (
        sample_bank.get("mechanisms")
        if isinstance(sample_bank.get("mechanisms"), list)
        else []
    )
    n_bank_tasks = sum(
        len(m.get("tasks") or [])
        for m in bank_mechs
        if isinstance(m, dict)
    )

    anisotropy = html.escape(
        str(summary.get("grid_anisotropy_limitation") or "—")
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Project Printout — Sprint Six — {run_id}</title>
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
  <h1>Inequality Mechanisms — Project Printout (through Sprint Six)</h1>
  <p>
    End-to-end viewer: matched linear baselines, search on the input-space
    graph, U / Q / Cartesian path samples, expansion effort, resolution
    calibration, and hierarchical Monte Carlo trust. Search identity lives in
    <em>U</em>; Q and Cartesian are attached data.
  </p>
  <div class="flow">
    <span class="chip">run {run_id}</span>
    <span class="chip">seed {seed}</span>
    <span class="chip">{status}</span>
    <span class="chip">schema {html.escape(str(schema))}</span>
    <span class="chip">mode {html.escape(str(summary.get('mode') or '—'))}</span>
    <span class="chip">M={html.escape(str(summary.get('n_mechanisms', '—')))}</span>
    <span class="chip">n={html.escape(str(summary.get('production_shape_n', '—')))}</span>
    <span class="chip">git {html.escape(str(git_describe))} ({dirty_label})</span>
  </div>
</header>
<nav>
  <a href="#pipeline">Pipeline</a>
  <a href="#provenance">Provenance</a>
  <a href="#equivalence">Equivalence</a>
  <a href="#paths">Path samples</a>
  <a href="#metrics">Path metrics</a>
  <a href="#expansions">Expansions</a>
  <a href="#resolution">Resolution</a>
  <a href="#hierarchy">Hierarchy</a>
  <a href="#precision">Precision</a>
  <a href="#confirmation">Confirmation</a>
  <a href="#figures">Figures</a>
  <a href="#tables">Tables</a>
  <a href="#exclusions">Exclusions</a>
  <a href="#config">Config</a>
</nav>
<main>
  <section id="pipeline">
    <h2>How the project works (through Sprint Six)</h2>
    <p class="muted">
      Mechanism map <code>U → Q → X</code>. Dijkstra / A* search on a constrained
      input lattice. Sprint Four attributes search effort; Sprint Five scores
      path quality; Sprint Six matches linear baselines, calibrates resolution,
      and earns hierarchical statistical trust.
    </p>
    <div class="flow">
      <span class="chip">U input lattice</span>
      <span class="chip">g_m : U → Q</span>
      <span class="chip">f : Q → X (2R plant)</span>
      <span class="chip">shared Q limits</span>
      <span class="chip">matched tasks</span>
      <span class="chip">Dijkstra / A*</span>
      <span class="chip">equivalent gearbox</span>
      <span class="chip">hierarchical MC</span>
    </div>
  </section>
  <section id="provenance">
    <h2>Provenance</h2>
    <p class="muted ok">Pass: seed, frozen config, and revision recorded with the run (ADR-007).</p>
    <dl class="kv">
      <dt>run_id</dt><dd>{run_id}</dd>
      <dt>seed</dt><dd>{seed}</dd>
      <dt>status</dt><dd>{status}</dd>
      <dt>study</dt><dd>{html.escape(str(summary.get('study') or 'sprint6'))}</dd>
      <dt>result_schema_version</dt><dd>{html.escape(str(schema))}</dd>
      <dt>mode</dt><dd>{html.escape(str(summary.get('mode') or '—'))}</dd>
      <dt>equivalence_baseline</dt><dd>{html.escape(str(summary.get('equivalence_baseline') or '—'))}</dd>
      <dt>production_shape_n</dt><dd>{_fmt_num(summary.get('production_shape_n'))}</dd>
      <dt>primary_effect</dt><dd>{_fmt_num(summary.get('primary_effect'))}</dd>
      <dt>hierarchical_ci</dt><dd>{html.escape(str(summary.get('hierarchical_ci') or '—'))}</dd>
      <dt>n_trial_rows</dt><dd>{_fmt_num(summary.get('n_trial_rows'))}</dd>
      <dt>n_mechanisms</dt><dd>{_fmt_num(summary.get('n_mechanisms'))}</dd>
      <dt>sample_bank</dt><dd>{_fmt_num(len(bank_mechs))} mechanisms / {_fmt_num(n_bank_tasks)} tasks</dd>
      <dt>created_at</dt><dd>{html.escape(str(manifest.get('created_at') or '—'))}</dd>
      <dt>completed_at</dt><dd>{html.escape(str(manifest.get('completed_at') or '—'))}</dd>
      <dt>git_commit</dt><dd>{html.escape(str(revision.get('git_commit') or '—'))}</dd>
      <dt>platform</dt><dd>{html.escape(str(environment.get('platform') or '—'))}</dd>
      <dt>grid_anisotropy</dt><dd>{anisotropy}</dd>
    </dl>
  </section>

  <section id="equivalence">
    <h2>Baseline equivalence (ADR-012)</h2>
    <p class="muted">
      Matching rule must be named explicitly. Unit gearbox remains a separate
      identity baseline.
    </p>
{_equiv_kv(equivalence)}
    <h3>Matched vs unmatched quantities (S6-18)</h3>
{_json_table(
    matched_rows,
    columns=[
        ("comparison", "comparison"),
        ("input_span", "input span"),
        ("output_span", "output span"),
        ("mean_absolute_gain", "mean |gain|"),
        ("rms_gain", "RMS gain"),
        ("topology", "topology"),
    ],
    empty="No equivalence summary table.",
)}
  </section>

  <section id="paths">
    <h2>Sample searches — U / Q / Cartesian (n={_fmt_num(summary.get('n_path_samples'))})</h2>
    <p class="muted">
      Five kept start→goal trials with search graphs in actuator space (U),
      output space (Q), and Cartesian workspace via the 2R plant. Gearbox and
      four-bar share requested Q endpoints.
    </p>
    <h3>Cartesian paths</h3>
{_figure_grid(cartesian_samples, empty="No Cartesian path PNGs (set trials.n_path_samples &gt; 0).")}
    <h3>All path-sample figures</h3>
{_figure_grid(path_samples, empty="No path-sample figures under outputs/paths/.")}
  </section>

  <section id="metrics">
    <h2>Path metrics overview</h2>
    <p class="muted">Means over found Dijkstra trials with recorded path lengths.</p>
    <dl class="kv">
      <dt>n_found_with_lengths</dt><dd>{_fmt_num(path_metrics.get('n_found_with_lengths'))}</dd>
      <dt>mean L_U</dt><dd>{_fmt_num(path_metrics.get('mean_path_length_u'))}</dd>
      <dt>mean L_Q</dt><dd>{_fmt_num(path_metrics.get('mean_path_length_q'))}</dd>
      <dt>mean L_X</dt><dd>{_fmt_num(path_metrics.get('mean_path_length_x'))}</dd>
      <dt>mean optimal cost</dt><dd>{_fmt_num(path_metrics.get('mean_optimal_cost'))}</dd>
      <dt>mean path edges</dt><dd>{_fmt_num(path_metrics.get('mean_n_path_edges'))}</dd>
    </dl>
    <h3>Search summary by algorithm × mechanism</h3>
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

  <section id="expansions">
    <h2>Search-effort figures</h2>
    <p class="muted">Node expansions and paired log-ratios (Sprint Four lineage).</p>
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

  <section id="resolution">
    <h2>Graph-resolution calibration (ADR-013)</h2>
    <p class="muted">
      Coarsest n×n that satisfies configured sign / effect / component /
      feasibility stability against the next higher candidate.
    </p>
    <dl class="kv">
      <dt>production_shape_n</dt><dd>{_fmt_num(production.get('production_shape_n'))}</dd>
      <dt>reason</dt><dd>{html.escape(str(production.get('reason') or '—'))}</dd>
      <dt>max_relative_effect_change</dt><dd>{_fmt_num((production.get('criteria') or {}).get('max_relative_effect_change') if isinstance(production.get('criteria'), dict) else None)}</dd>
    </dl>
    <h3>Sweep</h3>
{_json_table(
    resolution_rows,
    columns=[
        ("shape_n", "n"),
        ("valid_nodes", "valid nodes"),
        ("valid_edges", "valid edges"),
        ("n_components", "components"),
        ("task_acceptance_rate", "acceptance"),
        ("primary_effect", "primary effect"),
        ("search_runtime_s", "runtime (s)"),
    ],
    empty="No resolution sweep rows.",
)}
    <h3>Pairwise comparisons</h3>
{_json_table(
    production.get("comparisons") if isinstance(production.get("comparisons"), list) else [],
    columns=[
        ("shape_n", "n"),
        ("next_shape_n", "next n"),
        ("effect", "effect"),
        ("next_effect", "next effect"),
        ("relative_effect_change", "rel Δ"),
        ("sign_stable", "sign"),
        ("effect_stable", "effect"),
        ("accepted", "accepted"),
    ],
    empty="No resolution comparisons (single candidate).",
)}
  </section>

  <section id="hierarchy">
    <h2>Hierarchical Monte Carlo</h2>
    <p class="muted">
      Mechanism-level effects first; hierarchical bootstrap resamples
      mechanisms then tasks. Tasks are not treated as iid.
    </p>
    <dl class="kv">
      <dt>metric</dt><dd>{html.escape(str(hci.get('metric') or '—'))}</dd>
      <dt>estimate</dt><dd>{_fmt_num(hci.get('estimate'))}</dd>
      <dt>ci_low</dt><dd>{_fmt_num(hci.get('ci_low'))}</dd>
      <dt>ci_high</dt><dd>{_fmt_num(hci.get('ci_high'))}</dd>
      <dt>n_mechanisms</dt><dd>{_fmt_num(hci.get('n_mechanisms'))}</dd>
      <dt>n_tasks</dt><dd>{_fmt_num(hci.get('n_tasks'))}</dd>
      <dt>cluster_definition</dt><dd>{html.escape(str(hci.get('cluster_definition') or '—'))}</dd>
      <dt>treats_tasks_as_iid</dt><dd>{html.escape(str(hci.get('treats_tasks_as_iid')))}</dd>
      <dt>interval_method</dt><dd>{html.escape(str(hci.get('interval_method') or '—'))}</dd>
      <dt>m_required (pilot)</dt><dd>{_fmt_num(sample_size.get('m_required'))}</dd>
      <dt>s_d</dt><dd>{_fmt_num(sample_size.get('mechanism_effect_std'))}</dd>
      <dt>target half-width</dt><dd>{_fmt_num(sample_size.get('target_ci_half_width'))}</dd>
    </dl>
    <h3>Mechanism-level effects</h3>
{_json_table(
    effect_rows,
    columns=[
        ("mechanism_id", "mechanism"),
        ("metric", "metric"),
        ("n_accepted_tasks", "K"),
        ("effect", "d_m"),
        ("effect_std", "std"),
    ],
    empty="No mechanism-level summaries.",
)}
  </section>

  <section id="precision">
    <h2>Sequential precision</h2>
    <p class="muted">
      Cumulative hierarchical CI after each mechanism batch. Stopping rule is
      fixed before examining the final batch.
    </p>
    <dl class="kv">
      <dt>stop</dt><dd>{html.escape(str(precision.get('stop')))}</dd>
      <dt>stop_reason</dt><dd>{html.escape(str(precision.get('stop_reason') or '—'))}</dd>
      <dt>final_n_mechanisms</dt><dd>{_fmt_num(precision.get('final_n_mechanisms'))}</dd>
      <dt>target_ci_half_width</dt><dd>{_fmt_num(precision.get('target_ci_half_width'))}</dd>
    </dl>
{_json_table(
    batch_rows,
    columns=[
        ("n_mechanisms", "M"),
        ("estimate", "estimate"),
        ("ci_low", "ci_low"),
        ("ci_high", "ci_high"),
        ("ci_half_width", "half-width"),
        ("sign_stable", "sign stable"),
        ("relative_change", "rel Δ"),
    ],
    empty="No sequential precision batches.",
)}
  </section>

  <section id="confirmation">
    <h2>High-resolution confirmation</h2>
    <p class="muted">Representative subset at the next higher practical resolution.</p>
    <dl class="kv">
      <dt>ran</dt><dd>{html.escape(str(confirmation.get('ran')))}</dd>
      <dt>confirmation_shape_n</dt><dd>{_fmt_num(confirmation.get('confirmation_shape_n'))}</dd>
      <dt>production_estimate</dt><dd>{_fmt_num(confirmation.get('production_estimate'))}</dd>
      <dt>confirmation_estimate</dt><dd>{_fmt_num(confirmation.get('confirmation_estimate'))}</dd>
      <dt>sign_reversed</dt><dd>{html.escape(str(confirmation.get('sign_reversed')))}</dd>
      <dt>n_mechanisms</dt><dd>{_fmt_num(confirmation.get('n_mechanisms'))}</dd>
    </dl>
  </section>

  <section id="figures">
    <h2>Equivalence &amp; stability figures</h2>
    <p class="muted">Gain matching, resolution scaling, and Monte Carlo precision.</p>
{_figure_grid(figures, empty="No stability PNGs found under outputs/figures/.")}
  </section>

  <section id="tables">
    <h2>Summary tables</h2>
    <p class="muted">Registered CSV / TXT artifacts from the Sprint Six runner.</p>
{tables_html}
  </section>

  <section id="exclusions">
    <h2>Exclusions</h2>
    <p class="muted">Coded failure reasons for mechanisms and tasks (S6-21).</p>
{_json_table(
    exclusion_rows,
    columns=[
        ("mechanism_id", "mechanism"),
        ("task_id", "task"),
        ("reason_code", "reason"),
        ("shape_n", "n"),
        ("n_accepted_tasks", "accepted"),
        ("min_accepted_tasks", "min"),
    ],
    empty="No exclusions recorded.",
)}
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


def write_sprint6_canvas(
    run: ExperimentRun | str | Path,
    *,
    results_root: Path | str | None = None,
    filename: str = _CANVAS_NAME,
) -> Path:
    """Write ``index.html`` consolidating a completed Sprint Six run."""
    if isinstance(run, ExperimentRun):
        handle = run
        if handle.status != "completed":
            raise RunRegistryError(
                f"canvas requires a completed run; "
                f"{handle.run_id!r} status={handle.status!r}"
            )
    else:
        handle = resolve_run_for_canvas(run, results_root=results_root)

    payload = collect_sprint6_canvas_payload(handle)
    html_text = render_sprint6_canvas_html(payload)
    out = handle.path / filename
    out.write_text(html_text, encoding="utf-8")
    return out.resolve()
