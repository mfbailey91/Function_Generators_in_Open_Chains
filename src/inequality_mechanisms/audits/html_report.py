"""Offline print-aware HTML report assembly for V3.6B (V3-627 / V3-628)."""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


PRINT_CSS = """
@media print {
  .anim-live { display: none !important; }
  .contact-sheet { display: block !important; }
  .section { break-before: page; page-break-before: always; }
  a[href]::after { content: ""; }
}
@media screen {
  .contact-sheet.fallback-only { display: none; }
}
body { font-family: Georgia, "Times New Roman", serif; margin: 1.2rem; color: #222; }
nav a { margin-right: 0.8rem; }
table { border-collapse: collapse; width: 100%; margin: 0.6rem 0 1.2rem; font-size: 0.92rem; }
th, td { border: 1px solid #bbb; padding: 0.35rem 0.45rem; vertical-align: top; }
th { background: #f3f3f3; }
img { max-width: 100%; height: auto; border: 1px solid #ddd; margin: 0.25rem 0; }
.muted { color: #555; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 0.8rem; }
code, pre { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 0.85rem; }
"""


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _img(rel: str, *, cls: str = "", alt: str = "") -> str:
    klass = f' class="{cls}"' if cls else ""
    return f'<img{klass} src="{_esc(rel)}" alt="{_esc(alt or rel)}" loading="lazy" />'


def _metrics(run: Mapping[str, Any]) -> dict[str, Any]:
    raw = run.get("planner_metrics") or {}
    return dict(raw) if isinstance(raw, Mapping) else {}


def _nested(metrics: Mapping[str, Any], key: str) -> dict[str, Any]:
    raw = metrics.get(key) or {}
    return dict(raw) if isinstance(raw, Mapping) else {}


def family_metrics_html(runs: Sequence[Mapping[str, Any]]) -> str:
    """Compact family-specific metric tables (sprint V3.6C §7)."""
    lattice_rows: list[str] = []
    prm_rows: list[str] = []
    rrt_rows: list[str] = []
    sq_rows: list[str] = []
    for r in runs:
        mech = r.get("mechanism")
        planner = str(r.get("planner") or "")
        pm = _metrics(r)
        if planner in ("lattice_dijkstra", "lattice_astar"):
            g = _nested(pm, "graph")
            path = g.get("path_node_ids") or []
            n_edges = max(0, len(path) - 1) if isinstance(path, list) else None
            unique_goal_nodes = g.get(
                "unique_goal_node_count", g.get("goal_set_cardinality")
            )
            lattice_rows.append(
                "<tr>"
                f"<td>{_esc(mech)}</td><td>{_esc(planner)}</td>"
                f"<td>{_esc(g.get('expansions'))}</td>"
                f"<td>{_esc(g.get('generated'))}</td>"
                f"<td>{_esc(g.get('reopened_or_stale'))}</td>"
                f"<td>{_esc(g.get('requested_goal_count'))}</td>"
                f"<td>{_esc(g.get('attached_goal_candidate_count'))}</td>"
                f"<td>{_esc(unique_goal_nodes)}</td>"
                f"<td>{_esc(g.get('goal_set_attachment_complete'))}</td>"
                f"<td>{_esc(n_edges)}</td>"
                f"<td>{_esc(g.get('expansions_are_total_query_work'))}</td>"
                "</tr>"
            )
        elif planner == "prm":
            rd = _nested(pm, "roadmap")
            start_attachment_count = rd.get(
                "start_attachment_count", rd.get("start_attached")
            )
            goal_attachment_count = rd.get(
                "goal_attachment_count", rd.get("goal_candidate_count")
            )
            prm_rows.append(
                "<tr>"
                f"<td>{_esc(mech)}</td>"
                f"<td>{_esc(rd.get('n_samples_requested'))}</td>"
                f"<td>{_esc(rd.get('vertices'))}</td>"
                f"<td>{_esc(rd.get('attempted_edges'))}</td>"
                f"<td>{_esc(rd.get('accepted_edges'))}</td>"
                f"<td>{_esc(start_attachment_count)}</td>"
                f"<td>{_esc(goal_attachment_count)}</td>"
                f"<td>{_esc(rd.get('query_unique_edges_attempted'))}</td>"
                f"<td>{_esc(rd.get('query_unique_edges_accepted'))}</td>"
                f"<td>{_esc(rd.get('query_duplicate_edge_reuses'))}</td>"
                f"<td>{_esc(rd.get('expansions'))}</td>"
                "</tr>"
            )
        elif planner == "rrt_connect":
            tree = _nested(pm, "tree")
            rrt_rows.append(
                "<tr>"
                f"<td>{_esc(mech)}</td>"
                f"<td>{_esc(tree.get('iterations'))}</td>"
                f"<td>{_esc(tree.get('extensions'))}</td>"
                f"<td>{_esc(tree.get('nn_ops'))}</td>"
                f"<td>{_esc(tree.get('start_tree_size'))}</td>"
                f"<td>{_esc(tree.get('goal_tree_size'))}</td>"
                f"<td>{_esc(tree.get('goal_root_count'))}</td>"
                f"<td>{_esc(tree.get('selected_goal_root_index'))}</td>"
                "</tr>"
            )
        elif planner.startswith("shared_q_sampled"):
            sq = _nested(pm, "shared_q_sampled_roadmap")
            sq_rows.append(
                "<tr>"
                f"<td>{_esc(mech)}</td><td>{_esc(planner)}</td>"
                f"<td>{_esc(sq.get('n_samples'))}</td>"
                f"<td>{_esc(sq.get('vertices'))}</td>"
                f"<td>{_esc(sq.get('edges'))}</td>"
                f"<td>{_esc(sq.get('start_attached'))}</td>"
                f"<td>{_esc(sq.get('goal_attachment_count') or sq.get('goal_candidate_count'))}</td>"
                f"<td>{_esc(sq.get('bank_mode'))}</td>"
                f"<td>{_esc(sq.get('diagnostic_label'))}</td>"
                "</tr>"
            )

    parts: list[str] = []
    if lattice_rows:
        parts.append(
            "<h3>Lattice</h3>"
            "<table><tr><th>mech</th><th>planner</th><th>expansions</th>"
            "<th>generated</th><th>stale/reopened</th><th>requested goals</th>"
            "<th>attached candidates</th><th>unique goal nodes</th>"
            "<th>attachment complete</th><th>path edges</th>"
            "<th>expansions_are_total_query_work</th></tr>"
            + "".join(lattice_rows)
            + "</table>"
        )
    if prm_rows:
        parts.append(
            "<h3>PRM (native roadmap-family control)</h3>"
            "<table><tr><th>mech</th><th>requested samples</th><th>vertices</th>"
            "<th>attempted edges</th><th>accepted edges</th>"
            "<th>start attachments</th>"
            "<th>goal attachments</th><th>query unique attempted</th>"
            "<th>query unique accepted</th><th>duplicate pair reuses</th>"
            "<th>expansions</th></tr>"
            + "".join(prm_rows)
            + "</table>"
        )
    if rrt_rows:
        parts.append(
            "<h3>RRTConnect</h3>"
            "<table><tr><th>mech</th><th>iterations</th><th>extensions</th>"
            "<th>nearest-neighbor ops</th><th>start tree</th><th>goal tree</th>"
            "<th>goal-root count</th><th>selected root</th></tr>"
            + "".join(rrt_rows)
            + "</table>"
        )
    if sq_rows:
        parts.append(
            "<h3>Frozen shared-Q sampled roadmap (metric-isolation diagnostic; not native PRM)</h3>"
            "<table><tr><th>mech</th><th>planner</th><th>n_samples</th>"
            "<th>vertices</th><th>edges</th><th>start attached</th>"
            "<th>goal attachments</th><th>bank_mode</th><th>label</th></tr>"
            + "".join(sq_rows)
            + "</table>"
        )
    return "\n".join(parts)


def write_architecture_html(
    out_path: Path,
    *,
    provenance: Mapping[str, Any],
    ownership: Sequence[Mapping[str, str]],
    report_title: str = "V3.6B Architecture",
) -> Path:
    """Write architecture/provenance page."""
    rows = "".join(
        f"<tr><td>{_esc(r.get('concern'))}</td><td>{_esc(r.get('owner'))}</td>"
        f"<td>{_esc(r.get('module'))}</td></tr>"
        for r in ownership
    )
    body = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/><title>{_esc(report_title)}</title>
<style>{PRINT_CSS}</style></head><body>
<nav><a href="index.html">Index</a></nav>
<h1>Architecture and provenance</h1>
<p class="muted">{_esc(provenance.get("no_inference_statement"))}</p>
<h2>Call chain</h2>
<pre>config → audits.planar2r_visual.resolve/run
 → audits.metrics (w_U/w_Q/w_X, fields)
 → audits.traces (opt-in PlannerTraceSink)
 → visualization.audit_* panels/animations
 → audits.html_report</pre>
<h2>Config / environment</h2>
<table>
<tr><th>Field</th><th>Value</th></tr>
<tr><td>audit_id</td><td>{_esc(provenance.get("audit_id"))}</td></tr>
<tr><td>config_path</td><td>{_esc(provenance.get("config_path"))}</td></tr>
<tr><td>git_revision</td><td>{_esc(provenance.get("git_revision"))}</td></tr>
<tr><td>python</td><td>{_esc(provenance.get("python_version"))}</td></tr>
<tr><td>numpy</td><td>{_esc((provenance.get("dependency_versions") or {}).get("numpy"))}</td></tr>
<tr><td>ompl_available</td><td>{_esc(provenance.get("ompl_available"))}</td></tr>
<tr><td>ompl_version</td><td>{_esc(provenance.get("ompl_version"))}</td></tr>
<tr><td>seed</td><td>{_esc(provenance.get("seed"))}</td></tr>
<tr><td>delta</td><td>{_esc((provenance.get("delta_convention") or {}).get("expression"))}</td></tr>
</table>
<h2>Source ownership</h2>
<table><tr><th>Concern</th><th>Owner</th><th>Module</th></tr>{rows}</table>
</body></html>"""
    out_path = Path(out_path)
    out_path.write_text(body, encoding="utf-8")
    return out_path


def write_trial_html(
    out_path: Path,
    *,
    trial: Mapping[str, Any],
    assets: Mapping[str, str],
    runs: Sequence[Mapping[str, Any]],
    deltas: Sequence[Mapping[str, Any]],
) -> Path:
    """Write one self-contained trial page."""
    task_id = trial["task_id"]

    def asset(key: str, *, anim: bool = False) -> str:
        rel = assets.get(key)
        if not rel:
            return f'<p class="muted">missing asset: {_esc(key)}</p>'
        if anim:
            contact = assets.get(key.replace("__anim.gif", "__contact.png").replace("_anim", "_contact"))
            # Prefer explicit contact key naming.
            contact = assets.get(key + "_contact") or assets.get(key.replace("anim", "contact")) or contact
            parts = [_img(rel, cls="anim-live", alt=key)]
            if contact:
                parts.append(_img(contact, cls="contact-sheet", alt=f"{key} contact"))
            return "\n".join(parts)
        return _img(rel, alt=key)

    run_rows = "".join(
        "<tr>"
        f"<td>{_esc(r.get('mechanism'))}</td>"
        f"<td>{_esc(r.get('planner'))}</td>"
        f"<td>{_esc(r.get('status'))}</td>"
        f"<td>{_esc(r.get('skipped'))}</td>"
        f"<td>{_esc(r.get('objective_cost'))}</td>"
        f"<td>{_esc(r.get('path_length_u'))}</td>"
        f"<td>{_esc(r.get('path_length_q'))}</td>"
        f"<td>{_esc(r.get('path_length_x'))}</td>"
        f"<td>{_esc((r.get('composite') or {}).get('J_alpha'))}</td>"
        f"<td>{_esc(r.get('selected_goal_sample_id'))}</td>"
        f"<td>{_esc(r.get('final_goal_residual'))}</td>"
        "</tr>"
        for r in runs
    )
    family_html = family_metrics_html(runs)
    has_shared_q = any(
        str(r.get("planner") or "").startswith("shared_q_sampled") for r in runs
    )
    delta_rows = "".join(
        f"<tr><td>{_esc(d.get('planner'))}</td><td>{_esc(d.get('field'))}</td>"
        f"<td>{_esc(d.get('delta'))}</td><td>{_esc(d.get('abs_delta'))}</td></tr>"
        for d in deltas
    )

    body = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/><title>Trial {_esc(task_id)}</title>
<style>{PRINT_CSS}</style></head><body>
<nav><a href="../../index.html">Index</a> <a href="../../architecture.html">Architecture</a></nav>
<h1>Trial {_esc(task_id)}</h1>
<p class="muted">Paired four-bar / gearbox review unit. Static panels are authoritative.</p>

<div class="section">
<h2>1. Task definition and candidates</h2>
<table>
<tr><th>start_q</th><td><code>{_esc(trial.get('start_q'))}</code></td></tr>
<tr><th>start_tip</th><td><code>{_esc(trial.get('start_tip'))}</code></td></tr>
<tr><th>goal_center</th><td><code>{_esc(trial.get('goal_center'))}</code></td></tr>
<tr><th>goal_radius</th><td>{_esc(trial.get('goal_radius'))}</td></tr>
<tr><th>goal_point_ids</th><td><code>{_esc(trial.get('goal_point_ids'))}</code></td></tr>
</table>
</div>

<div class="section">
<h2>2. Code/dataflow architecture</h2>
<p>See <a href="../../architecture.html">architecture.html</a>. Shared Q lattice and frozen Cartesian disk candidates are pair-invariant; U realizations are mechanism-specific.</p>
</div>

<div class="section">
<h2>3. Mechanism transmission maps</h2>
<div class="grid2">
{asset('q_of_u')}
{asset('dqdu_u_of_q')}
{asset('fourbar_operating_branch')}
{asset('gearbox_operating_branch')}
</div>
</div>

<div class="section">
<h2>4. Q, U, and X graph embeddings</h2>
<div class="grid2">
{asset('fourbar_embed_q')}{asset('gearbox_embed_q')}
{asset('fourbar_embed_u')}{asset('gearbox_embed_u')}
{asset('fourbar_embed_x')}{asset('gearbox_embed_x')}
</div>
</div>

<div class="section">
<h2>5. w_U, w_Q, w_X, and actuator metric on Q</h2>
<p class="muted">
<code>actuator_metric_on_q</code> is the actuator-travel metric expressed in Q
(<code>M = J_inv.T @ J_inv</code>). Paired panels share one logarithmic color scale.
Primary field: <code>sqrt_kappa</code> (directional actuator-cost ratio).
Anisotropy is not Cartesian dexterity and is not path cost.
</p>
<div class="grid2">
{asset('fourbar_w_u')}{asset('gearbox_w_u')}
{asset('fourbar_w_q')}{asset('gearbox_w_q')}
{asset('fourbar_w_x')}{asset('gearbox_w_x')}
{asset('fourbar_actuator_metric_sqrt_kappa')}{asset('gearbox_actuator_metric_sqrt_kappa')}
{asset('fourbar_actuator_metric_kappa')}{asset('gearbox_actuator_metric_kappa')}
{asset('fourbar_actuator_metric_lambda_min')}{asset('gearbox_actuator_metric_lambda_min')}
{asset('fourbar_actuator_metric_lambda_max')}{asset('gearbox_actuator_metric_lambda_max')}
{asset('fourbar_actuator_metric_sqrt_det')}{asset('gearbox_actuator_metric_sqrt_det')}
</div>
</div>

<div class="section">
<h2>6. Direct planner paths</h2>
{asset('path_lengths')}
<div class="grid2">
{asset('fourbar_input_linear_path_u')}{asset('gearbox_input_linear_path_u')}
{asset('fourbar_output_linear_path_u')}{asset('gearbox_output_linear_path_u')}
</div>
</div>

<div class="section">
<h2>7. Lattice Dijkstra/A* traces and animation</h2>
<div class="grid2">
{asset('fourbar_lattice_dijkstra_expansion')}{asset('gearbox_lattice_dijkstra_expansion')}
{asset('fourbar_lattice_astar_expansion')}{asset('gearbox_lattice_astar_expansion')}
</div>
{asset('lattice_combined_anim', anim=True)}
</div>

<div class="section">
<h2>8. Native roadmap/tree traces</h2>
<p class="muted">Synchronized U/Q/X panels; edges reconstructed through the declared connector. Projected crossings do not invent adjacency.</p>
<div class="grid2">
{asset('fourbar_prm_final_trace_u')}{asset('gearbox_prm_final_trace_u')}
{asset('fourbar_prm_final_trace_q')}{asset('gearbox_prm_final_trace_q')}
{asset('fourbar_prm_final_trace_x')}{asset('gearbox_prm_final_trace_x')}
{asset('fourbar_rrt_connect_final_trace_u')}{asset('gearbox_rrt_connect_final_trace_u')}
{asset('fourbar_rrt_connect_final_trace_q')}{asset('gearbox_rrt_connect_final_trace_q')}
{asset('fourbar_rrt_connect_final_trace_x')}{asset('gearbox_rrt_connect_final_trace_x')}
</div>
{asset('growth_anims', anim=True)}
</div>
"""
    shared_q_section = ""
    if has_shared_q:
        shared_q_section = f"""
<div class="section">
<h2>8b. Frozen shared-Q sampled-roadmap diagnostic</h2>
<p class="muted">Same frozen Q samples and adjacency; mechanism-specific integrated actuator weights. Metric-isolation diagnostic; not native PRM and not primary performance evidence.</p>
<div class="grid2">
{asset('fourbar_shared_q_sampled_dijkstra_expansion')}{asset('gearbox_shared_q_sampled_dijkstra_expansion')}
{asset('fourbar_shared_q_sampled_astar_expansion')}{asset('gearbox_shared_q_sampled_astar_expansion')}
</div>
</div>
"""
    body = body + shared_q_section + f"""
<div class="section">
<h2>9. Optional OMPL final graph/path</h2>
<p class="muted">Stepwise OMPL history is unavailable; final PlannerData snapshot only when bindings exist.</p>
<div class="grid2">
{asset('fourbar_ompl_prm_path_u')}{asset('gearbox_ompl_prm_path_u')}
{asset('fourbar_ompl_rrt_connect_path_u')}{asset('gearbox_ompl_rrt_connect_path_u')}
{asset('fourbar_ompl_prm_unavailable')}{asset('gearbox_ompl_prm_unavailable')}
</div>
</div>

<div class="section">
<h2>10. Common and family metrics</h2>
<table>
<tr><th>mech</th><th>planner</th><th>status</th><th>skipped</th><th>cost</th>
<th>L_U</th><th>L_Q</th><th>L_X</th><th>J_alpha</th><th>goal_id</th>
<th>physical residual</th></tr>
{run_rows}
</table>
{family_html}
</div>

<div class="section">
<h2>11. Paired differences (Δz = z_F − z_G)</h2>
<table><tr><th>planner</th><th>field</th><th>delta</th><th>|delta|</th></tr>{delta_rows}</table>
</div>

<div class="section">
<h2>12. Raw records and asset manifest</h2>
<p><a href="trial.json">trial.json</a> · <a href="runs.json">runs.json</a> · <a href="../../manifest.json">manifest.json</a></p>
</div>
</body></html>"""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(body, encoding="utf-8")
    return out_path


def write_index_html(
    out_path: Path,
    *,
    provenance: Mapping[str, Any],
    summary_rows: Sequence[Mapping[str, Any]],
    task_ids: Sequence[str],
    report_title: str = "V3.6B Planar 2R Visual Audit",
) -> Path:
    """Write audit index with navigation and compact paired summary."""
    nav = "".join(f'<li><a href="trials/{_esc(t)}/index.html">{_esc(t)}</a></li>' for t in task_ids)
    rows = "".join(
        "<tr>"
        f"<td>{_esc(r.get('task_id'))}</td>"
        f"<td>{_esc(r.get('planner'))}</td>"
        f"<td>{_esc(r.get('delta_L_U'))}</td>"
        f"<td>{_esc(r.get('fourbar_status'))}</td>"
        f"<td>{_esc(r.get('gearbox_status'))}</td>"
        "</tr>"
        for r in summary_rows
    )
    body = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/><title>{_esc(report_title)}</title>
<style>{PRINT_CSS}</style></head><body>
<h1>{_esc(report_title)}</h1>
<p><strong>No-inference:</strong> {_esc(provenance.get("no_inference_statement"))}</p>
<p>Git <code>{_esc(provenance.get("git_revision"))}</code> · seed {_esc(provenance.get("seed"))} ·
OMPL {_esc(provenance.get("ompl_available"))} ({_esc(provenance.get("ompl_version"))})</p>
<p><a href="architecture.html">Architecture / provenance</a> ·
<a href="manifest.json">manifest.json</a> · <a href="summary.json">summary.json</a></p>
<h2>Trials</h2>
<ul>{nav}</ul>
<h2>Compact paired metric summary (Δ L_U)</h2>
<table>
<tr><th>task</th><th>planner</th><th>Δ L_U</th><th>fourbar</th><th>gearbox</th></tr>
{rows}
</table>
</body></html>"""
    out_path = Path(out_path)
    out_path.write_text(body, encoding="utf-8")
    return out_path


def build_manifest(
    *,
    provenance: Mapping[str, Any],
    task_ids: Sequence[str],
    assets: Sequence[Mapping[str, Any]],
    root: Path,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble manifest.json payload."""
    payload: dict[str, Any] = {
        "audit_id": provenance.get("audit_id"),
        "schema_version": 1,
        "git_revision": provenance.get("git_revision"),
        "dependency_versions": provenance.get("dependency_versions"),
        "ompl_available": provenance.get("ompl_available"),
        "ompl_version": provenance.get("ompl_version"),
        "config_path": provenance.get("config_path"),
        "task_ids": list(task_ids),
        "seed": provenance.get("seed"),
        "assets": list(assets),
        "trials": [f"trials/{t}/index.html" for t in task_ids],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
    }
    if extra:
        payload.update(dict(extra))
    return payload


DEFAULT_OWNERSHIP = (
    {"concern": "task semantics / shared start_q", "owner": "free_space_bank_v2", "module": "benchmarks/free_space_bank_v2.py"},
    {"concern": "physical state / FK", "owner": "OperatingBranchRobotModel", "module": "adapters/operating_branch_robot.py"},
    {"concern": "local motion / edge weights", "owner": "audits.metrics + lattice_edge_cost", "module": "audits/metrics.py"},
    {"concern": "planner traces", "owner": "audits.traces", "module": "audits/traces.py"},
    {"concern": "metrics / composite diagnostic", "owner": "audits.metrics", "module": "audits/metrics.py"},
    {"concern": "HTML assembly", "owner": "audits.html_report", "module": "audits/html_report.py"},
)


__all__ = [
    "DEFAULT_OWNERSHIP",
    "PRINT_CSS",
    "build_manifest",
    "family_metrics_html",
    "write_architecture_html",
    "write_index_html",
    "write_trial_html",
]
