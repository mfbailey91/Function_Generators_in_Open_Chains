"""HTML for the V4.2B common-physical planning audit.

Static panels are authoritative. Task pages live at
``cases/<case_id>/tasks/<task_id>.html``.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any, Mapping, Sequence

from inequality_mechanisms.audits.html_report import PRINT_CSS, family_metrics_html
from inequality_mechanisms.experiments.span_cases import (
    BIO_SPANS_DEG,
    CORE_SPANS_DEG,
    RealizedSpanCase,
    case_id_for,
)
from inequality_mechanisms.experiments.v4.span_controlled_atlas_config import (
    SPAN_175_STATUS,
)
from inequality_mechanisms.experiments.v4.span_controlled_corrective_audit_config import (
    NO_INFERENCE_STATEMENT,
    SpanControlledCorrectiveAuditConfig,
)
from inequality_mechanisms.mechanisms.span_registry import SpanRegistry


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _img(rel: str, *, alt: str = "") -> str:
    return f'<img src="{_esc(rel)}" alt="{_esc(alt or rel)}" loading="lazy" />'


def _asset(assets: Mapping[str, str], key: str) -> str:
    rel = assets.get(key)
    if not rel:
        return f'<p class="muted">missing asset: {_esc(key)}</p>'
    return _img(rel, alt=key)


def _status_cell(registry: SpanRegistry, span_deg: float) -> str:
    status = registry.record_for(span_deg).status
    label = f"{int(round(span_deg))}° {status}"
    if status == SPAN_175_STATUS:
        return f"<strong>{_esc(label)}</strong>"
    return _esc(label)


def _matrix_table(
    *,
    title: str,
    spans: Sequence[float],
    realized_by_id: Mapping[str, RealizedSpanCase],
    registry: SpanRegistry,
) -> str:
    header = "".join(f"<th>{_status_cell(registry, span)}</th>" for span in spans)
    rows = []
    for j1 in spans:
        cells = [f"<th>{_status_cell(registry, j1)}</th>"]
        for j2 in spans:
            case_id = case_id_for(j1, j2)
            realized = realized_by_id[case_id]
            memberships = ", ".join(realized.case.memberships)
            href = f"cases/{_esc(case_id)}/index.html"
            cells.append(
                f"<td><a href=\"{href}\">{_esc(case_id)}</a>"
                f"<div class=\"muted\">{_esc(memberships)}</div></td>"
            )
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return (
        f"<h2>{_esc(title)}</h2>"
        "<table><thead><tr><th>J1 \\ J2</th>"
        f"{header}</tr></thead><tbody>{''.join(rows)}</tbody></table>"
    )


def write_planning_audit_root_html(
    output: Path,
    *,
    config: SpanControlledCorrectiveAuditConfig,
    registry: SpanRegistry,
    realized: Sequence[RealizedSpanCase],
    manifest: Mapping[str, Any],
) -> Path:
    """Write the two-matrix planning-audit index."""
    output = Path(output)
    by_id = {row.case.case_id: row for row in realized}
    core = _matrix_table(
        title="Core span sweep (95°, 145°, 175°)",
        spans=CORE_SPANS_DEG,
        realized_by_id=by_id,
        registry=registry,
    )
    bio = _matrix_table(
        title="Biological refinement (135°, 145°, 150°)",
        spans=BIO_SPANS_DEG,
        realized_by_id=by_id,
        registry=registry,
    )
    statement = str(manifest.get("no_inference_statement") or NO_INFERENCE_STATEMENT)
    body = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>V4.2B Common-Physical Planning Audit</title>
<style>{PRINT_CSS}</style></head><body>
<h1>V4.2B Common-Physical Planning Audit</h1>
<p><strong>No-inference:</strong> {_esc(statement)}</p>
<p class="muted">Git <code>{_esc(manifest.get("source_git_revision"))}</code>
· schema <code>{_esc(config.schema_version)}</code>
· cases {len(realized)}
· seed {_esc(manifest.get("seed"))}
· lattice {_esc(manifest.get("lattice_shape"))}
· V3.6D digest <code>{_esc(manifest.get("v3_6d_registry_digest"))}</code>
· task-bank digest <code>{_esc(manifest.get("common_task_bank_digest"))}</code>
· config digest <code>{_esc(config.digest())}</code></p>
<p>175° remains <code>{_esc(SPAN_175_STATUS)}</code>. Starts and Cartesian
disks are shared across the pair from the frozen common-physical bank.
The primary topology assertion is the jointly compiled lattice family.
Identity-on-shared-Q is not a planner arm. Animations are skipped.</p>
<p><a href="manifest.json">manifest.json</a> ·
<a href="summary.json">summary.json</a> ·
<a href="failures.json">failures.json</a></p>
{core}
{bio}
</body></html>
"""
    path = output / "index.html"
    path.write_text(body, encoding="utf-8")
    return path


def write_case_audit_html(
    out_path: Path,
    *,
    realized: RealizedSpanCase,
    task_ids: Sequence[str],
    summary_rows: Sequence[Mapping[str, Any]],
    admitted_topology_digest: str,
    candidate_edge_count: int,
    admitted_edge_count: int,
    no_inference_statement: str,
) -> Path:
    """Write one case index listing task pages."""
    nav = "".join(
        f'<li><a href="tasks/{_esc(tid)}.html">{_esc(tid)}</a></li>'
        for tid in task_ids
    )
    rows = "".join(
        "<tr>"
        f"<td>{_esc(r.get('task_id'))}</td>"
        f"<td>{_esc(r.get('planner'))}</td>"
        f"<td>{_esc(r.get('fourbar_status'))}</td>"
        f"<td>{_esc(r.get('gearbox_status'))}</td>"
        f"<td>{_esc(r.get('delta_L_U'))}</td>"
        "</tr>"
        for r in summary_rows
    )
    body = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>{_esc(realized.case.case_id)}</title>
<style>{PRINT_CSS}</style></head><body>
<nav><a href="../../index.html">Audit</a></nav>
<h1>{_esc(realized.case.case_id)}</h1>
<p class="muted">{_esc(no_inference_statement)}</p>
<p>J1 {realized.case.span_j1_deg:g}° ({_esc(realized.j1.status)}) ·
J2 {realized.case.span_j2_deg:g}° ({_esc(realized.j2.status)}) ·
memberships {_esc(", ".join(realized.case.memberships))}</p>
<p>Admitted topology digest <code>{_esc(admitted_topology_digest)}</code>
· candidate edges {int(candidate_edge_count)}
· admitted edges {int(admitted_edge_count)}</p>
<h2>Tasks</h2>
<ul>{nav}</ul>
<h2>Paired planner summary</h2>
<table>
<tr><th>task</th><th>planner</th><th>fourbar</th><th>gearbox</th><th>Δ L_U</th></tr>
{rows}
</table>
</body></html>
"""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(body, encoding="utf-8")
    return out_path


def write_task_audit_html(
    out_path: Path,
    *,
    trial: Mapping[str, Any],
    assets: Mapping[str, str],
    runs: Sequence[Mapping[str, Any]],
    deltas: Sequence[Mapping[str, Any]],
) -> Path:
    """Write one task page with static panels."""
    task_id = trial["task_id"]
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
        f"<td>{_esc(r.get('selected_goal_sample_id'))}</td>"
        f"<td>{_esc(r.get('final_goal_residual'))}</td>"
        "</tr>"
        for r in runs
    )
    family_html = family_metrics_html(runs)
    delta_rows = "".join(
        f"<tr><td>{_esc(d.get('planner'))}</td><td>{_esc(d.get('field'))}</td>"
        f"<td>{_esc(d.get('delta'))}</td><td>{_esc(d.get('abs_delta'))}</td></tr>"
        for d in deltas
    )
    body = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>Task {_esc(task_id)}</title>
<style>{PRINT_CSS}</style></head><body>
<nav><a href="../index.html">Case</a> <a href="../../index.html">Audit</a></nav>
<h1>Task {_esc(task_id)}</h1>
<p class="muted">Paired four-bar / gearbox review unit. Static panels are
authoritative. Animations are skipped. Shared start/goal from the frozen
common-physical bank; lattice search uses the jointly compiled topology.</p>
<p>Admitted topology digest
<code>{_esc(trial.get("admitted_topology_digest"))}</code>
· candidates { _esc(trial.get("candidate_edge_count")) }
· admitted { _esc(trial.get("admitted_edge_count")) }</p>

<div class="section">
<h2>1. Shared task definition</h2>
<table>
<tr><th>start_q</th><td><code>{_esc(trial.get("start_q"))}</code></td></tr>
<tr><th>start_x</th><td><code>{_esc(trial.get("start_tip"))}</code></td></tr>
<tr><th>goal_center</th><td><code>{_esc(trial.get("goal_center"))}</code></td></tr>
<tr><th>goal_radius</th><td>{_esc(trial.get("goal_radius"))}</td></tr>
<tr><th>goal_point_ids</th><td><code>{_esc(trial.get("goal_point_ids"))}</code></td></tr>
<tr><th>start_u fourbar</th><td><code>{_esc(trial.get("start_u_fourbar"))}</code></td></tr>
<tr><th>start_u gearbox</th><td><code>{_esc(trial.get("start_u_gearbox"))}</code></td></tr>
</table>
</div>

<div class="section">
<h2>2. Mechanism transmission maps</h2>
<div class="grid2">
{_asset(assets, "q_of_u")}
{_asset(assets, "dqdu_u_of_q")}
{_asset(assets, "fourbar_operating_branch")}
{_asset(assets, "gearbox_operating_branch")}
</div>
</div>

<div class="section">
<h2>3. Q, U, and X embeddings</h2>
<div class="grid2">
{_asset(assets, "fourbar_embed_q")}{_asset(assets, "gearbox_embed_q")}
{_asset(assets, "fourbar_embed_u")}{_asset(assets, "gearbox_embed_u")}
{_asset(assets, "fourbar_embed_x")}{_asset(assets, "gearbox_embed_x")}
</div>
</div>

<div class="section">
<h2>4. Direct planner paths</h2>
{_asset(assets, "path_lengths")}
<div class="grid2">
{_asset(assets, "fourbar_input_linear_path_u")}{_asset(assets, "gearbox_input_linear_path_u")}
{_asset(assets, "fourbar_output_linear_path_u")}{_asset(assets, "gearbox_output_linear_path_u")}
</div>
</div>

<div class="section">
<h2>5. Lattice Dijkstra/A* traces</h2>
<div class="grid2">
{_asset(assets, "fourbar_lattice_dijkstra_expansion")}{_asset(assets, "gearbox_lattice_dijkstra_expansion")}
{_asset(assets, "fourbar_lattice_astar_expansion")}{_asset(assets, "gearbox_lattice_astar_expansion")}
</div>
</div>

<div class="section">
<h2>6. Native roadmap/tree traces</h2>
<div class="grid2">
{_asset(assets, "fourbar_prm_final_trace_u")}{_asset(assets, "gearbox_prm_final_trace_u")}
{_asset(assets, "fourbar_prm_final_trace_q")}{_asset(assets, "gearbox_prm_final_trace_q")}
{_asset(assets, "fourbar_prm_final_trace_x")}{_asset(assets, "gearbox_prm_final_trace_x")}
{_asset(assets, "fourbar_rrt_connect_final_trace_u")}{_asset(assets, "gearbox_rrt_connect_final_trace_u")}
{_asset(assets, "fourbar_rrt_connect_final_trace_q")}{_asset(assets, "gearbox_rrt_connect_final_trace_q")}
{_asset(assets, "fourbar_rrt_connect_final_trace_x")}{_asset(assets, "gearbox_rrt_connect_final_trace_x")}
</div>
</div>

<div class="section">
<h2>7. Optional OMPL</h2>
<p class="muted">OMPL absence is typed as unavailable, not omitted.</p>
<div class="grid2">
{_asset(assets, "fourbar_ompl_prm_path_u")}{_asset(assets, "gearbox_ompl_prm_path_u")}
{_asset(assets, "fourbar_ompl_rrt_connect_path_u")}{_asset(assets, "gearbox_ompl_rrt_connect_path_u")}
{_asset(assets, "fourbar_ompl_prm_unavailable")}{_asset(assets, "gearbox_ompl_prm_unavailable")}
</div>
</div>

<div class="section">
<h2>8. Common and family metrics</h2>
<table>
<tr><th>mech</th><th>planner</th><th>status</th><th>skipped</th><th>cost</th>
<th>L_U</th><th>L_Q</th><th>L_X</th><th>goal_id</th>
<th>physical residual</th></tr>
{run_rows}
</table>
{family_html}
</div>

<div class="section">
<h2>9. Paired differences (Δz = z_F − z_G)</h2>
<table><tr><th>planner</th><th>field</th><th>delta</th><th>|delta|</th></tr>{delta_rows}</table>
</div>
</body></html>
"""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(body, encoding="utf-8")
    return out_path
