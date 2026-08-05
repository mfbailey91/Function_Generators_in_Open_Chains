"""Post-run HTML canvas for Dijkstra production packages."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def render_production_canvas_html(payload: dict[str, Any]) -> str:
    """Render a local HTML summary from merged production artifacts."""
    summary = _as_dict(payload.get("summary"))
    analysis = _as_dict(summary.get("analysis"))
    env = _as_dict(payload.get("environment"))
    hci = _as_dict(analysis.get("hierarchical_bootstrap"))
    precision = _as_dict(analysis.get("precision"))
    variance = _as_dict(analysis.get("variance"))
    categories = _as_dict(analysis.get("task_category_effects"))
    batch_rows = ""
    for batch in precision.get("batches") or []:
        batch_rows += (
            "<tr>"
            f"<td>{html.escape(str(batch.get('n_mechanisms')))}</td>"
            f"<td>{html.escape(str(batch.get('estimate')))}</td>"
            f"<td>{html.escape(str(batch.get('ci_low')))}</td>"
            f"<td>{html.escape(str(batch.get('ci_high')))}</td>"
            f"<td>{html.escape(str(batch.get('ci_half_width')))}</td>"
            f"<td>{html.escape(str(batch.get('relative_change')))}</td>"
            "</tr>"
        )
    if not batch_rows:
        batch_rows = "<tr><td colspan='6'>No sequential batches yet.</td></tr>"
    cat_rows = ""
    for name, stats in categories.items():
        cat_rows += (
            "<tr>"
            f"<td>{html.escape(str(name))}</td>"
            f"<td>{html.escape(str(stats.get('n')))}</td>"
            f"<td>{html.escape(str(stats.get('mean')))}</td>"
            "</tr>"
        )
    if not cat_rows:
        cat_rows = "<tr><td colspan='3'>No category effects.</td></tr>"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>V2 production Monte Carlo — Dijkstra</title>
  <style>
    body {{ font-family: sans-serif; margin: 2rem; color: #122; }}
    code, pre {{ background: #f4f6f8; padding: 0.1rem 0.3rem; }}
    table {{ border-collapse: collapse; margin: 1rem 0; }}
    th, td {{ border: 1px solid #ccd; padding: 0.4rem 0.6rem; text-align: left; }}
    .chip {{
      display: inline-block; background: #e8eef5;
      padding: 0.2rem 0.5rem; margin-right: 0.4rem;
    }}
  </style>
</head>
<body>
  <h1>Production Monte Carlo — Dijkstra campaign</h1>
  <p>
    <span class="chip">solver=dijkstra</span>
    <span class="chip">objective=actuator_travel</span>
    <span class="chip">mechanisms={
        html.escape(str(summary.get("n_mechanisms", "—")))
    }</span>
    <span class="chip">trials={html.escape(str(summary.get("n_trials", "—")))}</span>
  </p>
  <p>This report is generated after search.
     Visualization is not part of the worker loop.</p>

  <h2>Primary hierarchical effect</h2>
  <dl>
    <dt>metric</dt><dd>{html.escape(str(hci.get("metric", "log_expansion_ratio")))}</dd>
    <dt>estimate</dt><dd>{html.escape(str(hci.get("estimate")))}</dd>
    <dt>CI</dt><dd>[{html.escape(str(hci.get("ci_low")))}, {
        html.escape(str(hci.get("ci_high")))
    }]</dd>
    <dt>n_mechanisms</dt><dd>{html.escape(str(hci.get("n_mechanisms")))}</dd>
  </dl>

  <h2>Variance</h2>
  <dl>
    <dt>between mechanisms</dt><dd>{
        html.escape(str(variance.get("between_mechanism_variance")))
    }</dd>
    <dt>within mechanisms</dt><dd>{
        html.escape(str(variance.get("within_mechanism_variance")))
    }</dd>
  </dl>

  <h2>Sequential precision</h2>
  <p>stop={html.escape(str(precision.get("stop")))} reason={
        html.escape(str(precision.get("stop_reason")))
    }</p>
  <table>
    <thead>
      <tr>
        <th>M</th><th>estimate</th><th>ci_low</th><th>ci_high</th>
        <th>half-width</th><th>rel change</th>
      </tr>
    </thead>
    <tbody>{batch_rows}</tbody>
  </table>

  <h2>Task-category effects</h2>
  <table>
    <thead><tr><th>category</th><th>n</th><th>mean log expansion ratio</th></tr></thead>
    <tbody>{cat_rows}</tbody>
  </table>

  <h2>Runtime environment</h2>
  <pre>{
        html.escape(
            json.dumps(
                {
                    "macos_version": env.get("macos_version"),
                    "physical_cpu": env.get("physical_cpu"),
                    "logical_cpu": env.get("logical_cpu"),
                    "total_memory_bytes": env.get("total_memory_bytes"),
                    "runner_workers": env.get("runner_workers"),
                    "numerical_thread_environment": env.get(
                        "numerical_thread_environment"
                    ),
                    "hardware_chip": (env.get("hardware") or {}).get("chip")
                    if isinstance(env.get("hardware"), dict)
                    else None,
                },
                indent=2,
            )
        )
    }</pre>
</body>
</html>
"""


def write_production_canvas(run_dir: Path | str, payload: dict[str, Any]) -> Path:
    """Write ``reports/index.html`` and a top-level convenience copy."""
    root = Path(run_dir)
    reports = root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    html_text = render_production_canvas_html(payload)
    target = reports / "index.html"
    target.write_text(html_text, encoding="utf-8")
    (root / "index.html").write_text(html_text, encoding="utf-8")
    return target


def is_v2_production_run_dir(path: Path | str) -> bool:
    """Return whether ``path`` is a Dijkstra production Monte Carlo package."""
    root = Path(path)
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(manifest, dict):
        return False
    if manifest.get("package_kind") == "production_monte_carlo":
        return True
    return manifest.get("production_schema_version") is not None


def refresh_production_canvas(run_dir: Path | str) -> Path:
    """Merge shards if needed and rewrite the production HTML report."""
    from inequality_mechanisms.experiments.v2_production_config import (
        load_v2_production_config,
    )
    from inequality_mechanisms.experiments.v2_production_merge import (
        merge_production_run,
    )

    root = Path(run_dir)
    config = load_v2_production_config(root / "config.snapshot.yaml")
    summary = merge_production_run(root, config)
    env: dict[str, Any] = {}
    env_path = root / "environment.json"
    if env_path.is_file():
        env = json.loads(env_path.read_text(encoding="utf-8"))
        if not isinstance(env, dict):
            env = {}
    return write_production_canvas(
        root,
        {"summary": summary, "environment": env},
    )
