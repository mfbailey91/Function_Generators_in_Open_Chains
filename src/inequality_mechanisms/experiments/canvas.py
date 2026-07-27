"""HTML canvas over a completed Monte Carlo / pilot run.

The canvas is a derived viewer: it reads registry artifacts (summary, plots,
provenance) and writes ``index.html`` beside them. Regenerating the canvas
does not mutate trial JSONL or other raw result files.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from inequality_mechanisms.experiments.registry import (
    ExperimentRun,
    RunRegistryError,
    default_results_root,
    list_runs,
    load_run,
)

_CANVAS_NAME = "index.html"

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


def resolve_run_for_canvas(
    run_id_or_path: str | Path | None = None,
    *,
    results_root: Path | str | None = None,
) -> ExperimentRun:
    """Load a run by id/path, or the latest completed run under results_root.

    Parameters
    ----------
    run_id_or_path :
        Run directory, run id, or ``None`` to select the latest completed run.
    results_root :
        Results parent used for bare ids and ``--latest`` selection.

    Returns
    -------
    ExperimentRun

    Raises
    ------
    FileNotFoundError
        If no matching run exists.
    RunRegistryError
        If the run is not completed.
    """
    if run_id_or_path is None:
        root = Path(results_root) if results_root is not None else default_results_root()
        completed = list_runs(root, status="completed")
        if not completed:
            raise FileNotFoundError(f"no completed runs under {root}")

        def _recency(run: ExperimentRun) -> tuple[str, str]:
            completed_at = str(run._manifest.get("completed_at") or "")
            created_at = str(run._manifest.get("created_at") or "")
            return (completed_at or created_at, run.run_id)

        return max(completed, key=_recency)

    run = load_run(run_id_or_path, results_root=results_root)
    if run.status != "completed":
        raise RunRegistryError(
            f"canvas requires a completed run; {run.run_id!r} status={run.status!r}"
        )
    return run


def _rel_if_exists(run: ExperimentRun, relative: str) -> str | None:
    path = run.path / relative
    return relative if path.is_file() else None


def _path_sample_figures(run: ExperimentRun) -> list[dict[str, str]]:
    """Discover path-sample PNGs under ``outputs/paths/``."""
    root = run.outputs_dir / "paths"
    if not root.is_dir():
        return []
    figures: list[dict[str, str]] = []
    for trial_dir in sorted(root.iterdir()):
        if not trial_dir.is_dir():
            continue
        for png in sorted(trial_dir.glob("*.png")):
            rel = png.relative_to(run.path).as_posix()
            figures.append(
                {
                    "src": rel,
                    "caption": f"{trial_dir.name} / {png.stem}",
                }
            )
    return figures


def collect_canvas_payload(run: ExperimentRun) -> dict[str, Any]:
    """Collect provenance, summary, and figure paths for the canvas.

    Parameters
    ----------
    run :
        Completed experiment run handle.

    Returns
    -------
    dict
        JSON-serializable payload used by ``render_monte_carlo_canvas_html``.
    """
    if run.status != "completed":
        raise RunRegistryError(
            f"canvas requires a completed run; {run.run_id!r} status={run.status!r}"
        )

    summary: dict[str, Any] = {}
    if "summary" in run.outputs:
        loaded = run.read_json("summary")
        if isinstance(loaded, dict):
            summary = loaded

    summary_table = ""
    if "summary_table" in run.outputs:
        summary_table = run.resolve_output("summary_table").read_text(encoding="utf-8")

    config_text = ""
    if run.config_path.is_file():
        config_text = run.config_path.read_text(encoding="utf-8")

    figures: list[dict[str, str]] = []
    for name, fallback_rel, caption in _EXPANSION_FIGURES:
        rel = run.outputs.get(name)
        if rel is None:
            rel = _rel_if_exists(run, fallback_rel)
        if rel is None:
            continue
        figures.append({"name": name, "src": rel, "caption": caption})

    return {
        "run_id": run.run_id,
        "status": run.status,
        "seed": run.seed,
        "path": str(run.path),
        "revision": run.revision,
        "environment": {
            "python_version": run.environment.get("python_version"),
            "platform": run.environment.get("platform"),
            "packages": run.environment.get("packages"),
        },
        "manifest": {
            "created_at": run._manifest.get("created_at"),
            "started_at": run._manifest.get("started_at"),
            "completed_at": run._manifest.get("completed_at"),
            "outputs": run.outputs,
        },
        "summary": summary,
        "summary_table_csv": summary_table,
        "config_yaml": config_text,
        "figures": figures,
        "path_samples": _path_sample_figures(run),
    }


def _fmt_num(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        if abs(value) >= 100 or abs(value) < 0.01:
            return f"{value:.4g}"
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return html.escape(str(value))


def _summary_stats_rows(summary: dict[str, Any]) -> str:
    by_group = summary.get("by_group") or {}
    if not isinstance(by_group, dict) or not by_group:
        return "<tr><td colspan='6'>No group summary</td></tr>"
    rows: list[str] = []
    for label in sorted(by_group.keys()):
        g = by_group[label]
        if not isinstance(g, dict):
            continue
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(g.get('algorithm')))}</td>"
            f"<td>{html.escape(str(g.get('mechanism')))}</td>"
            f"<td>{_fmt_num(g.get('n_found'))}/{_fmt_num(g.get('n_trials'))}</td>"
            f"<td>{_fmt_num(g.get('median_n_expanded'))}</td>"
            f"<td>{_fmt_num(g.get('mean_rho_expanded'))}</td>"
            f"<td>{_fmt_num(g.get('n_unreachable'))}</td>"
            "</tr>"
        )
    return "\n".join(rows) if rows else "<tr><td colspan='6'>No group summary</td></tr>"


def _paired_ratio_rows(summary: dict[str, Any]) -> str:
    ratios = summary.get("paired_log_ratios") or {}
    if not isinstance(ratios, dict) or not ratios:
        return "<tr><td colspan='4'>No paired ratios</td></tr>"
    rows: list[str] = []
    for algo in sorted(ratios.keys()):
        r = ratios[algo]
        if not isinstance(r, dict):
            continue
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(r.get('algorithm', algo)))}</td>"
            f"<td>{_fmt_num(r.get('n_pairs'))}</td>"
            f"<td>{_fmt_num(r.get('median'))}</td>"
            f"<td>{_fmt_num(r.get('mean'))}</td>"
            "</tr>"
        )
    return "\n".join(rows) if rows else "<tr><td colspan='4'>No paired ratios</td></tr>"


def _figure_grid(figures: list[dict[str, Any]], *, empty: str) -> str:
    if not figures:
        return f"<p class='muted'>{html.escape(empty)}</p>"
    parts: list[str] = ['<div class="grid">']
    for fig in figures:
        src = html.escape(str(fig["src"]))
        caption = html.escape(str(fig.get("caption", fig.get("name", ""))))
        parts.append(
            "<figure>"
            f'<img src="{src}" alt="{caption}"/>'
            f"<figcaption>{caption}</figcaption>"
            "</figure>"
        )
    parts.append("</div>")
    return "\n".join(parts)


def render_monte_carlo_canvas_html(payload: dict[str, Any]) -> str:
    """Render a dark diagnostic-style HTML canvas from a payload dict."""
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

    git_commit = revision.get("git_commit") or "—"
    git_describe = revision.get("git_describe") or "—"
    git_dirty = revision.get("git_dirty")
    dirty_label = (
        "dirty"
        if git_dirty is True
        else ("clean" if git_dirty is False else "unknown")
    )

    n_trials = summary.get("n_trials_config", "—")
    n_discarded = summary.get("n_discarded_unreachable", "—")
    n_attempts = summary.get("n_sample_attempts", "—")
    graph_meta = summary.get("graph_meta") if isinstance(summary.get("graph_meta"), dict) else {}

    figures = payload.get("figures") if isinstance(payload.get("figures"), list) else []
    path_samples = (
        payload.get("path_samples")
        if isinstance(payload.get("path_samples"), list)
        else []
    )
    config_yaml = str(payload.get("config_yaml") or "")
    summary_csv = str(payload.get("summary_table_csv") or "")
    summary_json = json.dumps(summary, indent=2, sort_keys=True)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Monte Carlo Canvas — {run_id}</title>
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
  header p {{ margin: 0; color: var(--muted); max-width: 52rem; }}
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
    margin: 0;
    font-size: 0.85rem;
  }}
  dl.kv dt {{ color: var(--muted); }}
  dl.kv dd {{ margin: 0; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
</style>
</head>
<body>
<header>
  <h1>Monte Carlo Canvas</h1>
  <p>
    Derived viewer over a completed paired gearbox / four-bar pilot run.
    Expansion plots and summary stats come from registry artifacts; this HTML
    can be regenerated without rewriting trial records.
  </p>
  <div class="flow">
    <span class="chip">run {run_id}</span>
    <span class="chip">seed {seed}</span>
    <span class="chip">{status}</span>
    <span class="chip">trials {html.escape(str(n_trials))}</span>
    <span class="chip">git {html.escape(str(git_describe))} ({dirty_label})</span>
  </div>
</header>
<nav>
  <a href="#provenance">Provenance</a>
  <a href="#summary">Summary</a>
  <a href="#expansions">Expansions</a>
  <a href="#paths">Path samples</a>
  <a href="#config">Config</a>
  <a href="#raw">Raw summary</a>
</nav>
<main>
  <section id="provenance">
    <h2>Provenance</h2>
    <p class="muted ok">Pass: seed, frozen config, and revision are recorded with the run (ADR-007).</p>
    <dl class="kv">
      <dt>run_id</dt><dd>{run_id}</dd>
      <dt>seed</dt><dd>{seed}</dd>
      <dt>status</dt><dd>{status}</dd>
      <dt>created_at</dt><dd>{html.escape(str(manifest.get("created_at") or "—"))}</dd>
      <dt>completed_at</dt><dd>{html.escape(str(manifest.get("completed_at") or "—"))}</dd>
      <dt>git_commit</dt><dd>{html.escape(str(git_commit))}</dd>
      <dt>git_describe</dt><dd>{html.escape(str(git_describe))}</dd>
      <dt>git_dirty</dt><dd>{html.escape(dirty_label)}</dd>
      <dt>package_version</dt><dd>{html.escape(str(revision.get("package_version") or "—"))}</dd>
      <dt>platform</dt><dd>{html.escape(str(environment.get("platform") or "—"))}</dd>
      <dt>fourbar_mode</dt><dd>{html.escape(str(graph_meta.get("fourbar_mode") or "—"))}</dd>
      <dt>match_valid_nodes</dt><dd>{html.escape(str(graph_meta.get("match_valid_nodes", "—")))}</dd>
      <dt>n_discarded_unreachable</dt><dd>{html.escape(str(n_discarded))}</dd>
      <dt>n_sample_attempts</dt><dd>{html.escape(str(n_attempts))}</dd>
    </dl>
  </section>

  <section id="summary">
    <h2>Key summary stats</h2>
    <p class="muted">Per-(algorithm, mechanism) medians and mean ρ from <code>outputs/summary.json</code>.</p>
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
    <h2 style="margin-top:1.25rem;font-size:1.05rem">Paired log-ratios</h2>
    <table>
      <thead>
        <tr><th>algorithm</th><th>n_pairs</th><th>median</th><th>mean</th></tr>
      </thead>
      <tbody>
{_paired_ratio_rows(summary)}
      </tbody>
    </table>
  </section>

  <section id="expansions">
    <h2>Expansion comparisons</h2>
    <p class="muted">Raw counts, normalized ρ = N_expanded / N_valid, and paired log-ratios.</p>
{_figure_grid(figures, empty="No expansion PNGs found under outputs/.")}
  </section>

  <section id="paths">
    <h2>Path samples</h2>
    <p class="muted">Optional U / Q / Cartesian path PNGs for early kept trials.</p>
{_figure_grid(path_samples, empty="No path-sample figures in this run.")}
  </section>

  <section id="config">
    <h2>Frozen config.yaml</h2>
    <pre>{html.escape(config_yaml) if config_yaml else "config.yaml missing"}</pre>
  </section>

  <section id="raw">
    <h2>summary.json</h2>
    <pre>{html.escape(summary_json)}</pre>
    <h2 style="margin-top:1rem;font-size:1.05rem">summary_table.csv</h2>
    <pre>{html.escape(summary_csv) if summary_csv else "(missing)"}</pre>
  </section>
</main>
</body>
</html>
"""


def write_monte_carlo_canvas(
    run: ExperimentRun | str | Path,
    *,
    results_root: Path | str | None = None,
    filename: str = _CANVAS_NAME,
) -> Path:
    """Write ``index.html`` for a completed Monte Carlo run.

    Parameters
    ----------
    run :
        Completed ``ExperimentRun``, run id, or run directory path.
    results_root :
        Used when ``run`` is a bare run id.
    filename :
        Canvas basename (default ``index.html``).

    Returns
    -------
    Path
        Absolute path of the written HTML file.
    """
    if isinstance(run, ExperimentRun):
        handle = run
        if handle.status != "completed":
            raise RunRegistryError(
                f"canvas requires a completed run; "
                f"{handle.run_id!r} status={handle.status!r}"
            )
    else:
        handle = resolve_run_for_canvas(run, results_root=results_root)

    payload = collect_canvas_payload(handle)
    html_text = render_monte_carlo_canvas_html(payload)
    out = handle.path / filename
    out.write_text(html_text, encoding="utf-8")
    return out.resolve()
