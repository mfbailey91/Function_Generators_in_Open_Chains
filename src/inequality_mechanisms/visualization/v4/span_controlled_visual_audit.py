"""Two-matrix HTML root for the V4.2A span-controlled visual audit."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any, Mapping, Sequence

from inequality_mechanisms.audits.html_report import PRINT_CSS
from inequality_mechanisms.experiments.span_cases import (
    BIO_SPANS_DEG,
    CORE_SPANS_DEG,
    RealizedSpanCase,
    case_id_for,
)
from inequality_mechanisms.experiments.v4.span_controlled_atlas_config import SPAN_175_STATUS
from inequality_mechanisms.experiments.v4.span_controlled_visual_audit_config import (
    NO_INFERENCE_STATEMENT,
    SpanControlledVisualAuditConfig,
)
from inequality_mechanisms.mechanisms.span_registry import SpanRegistry


def _status_cell(registry: SpanRegistry, span_deg: float) -> str:
    status = registry.record_for(span_deg).status
    label = f"{int(round(span_deg))}° {status}"
    if status == SPAN_175_STATUS:
        return f"<strong>{html.escape(label)}</strong>"
    return html.escape(label)


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
            href = f"cases/{html.escape(case_id)}/index.html"
            cells.append(
                f"<td><a href=\"{href}\">{html.escape(case_id)}</a>"
                f"<div class=\"muted\">{html.escape(memberships)}</div></td>"
            )
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return (
        f"<h2>{html.escape(title)}</h2>"
        "<table><thead><tr><th>J1 \\ J2</th>"
        f"{header}</tr></thead><tbody>{''.join(rows)}</tbody></table>"
    )


def write_span_visual_audit_root_html(
    output: Path,
    *,
    config: SpanControlledVisualAuditConfig,
    registry: SpanRegistry,
    realized: Sequence[RealizedSpanCase],
    manifest: Mapping[str, Any],
) -> Path:
    """Write the two-matrix root index linking to per-case visual audits."""
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
    dual = by_id[case_id_for(145.0, 145.0)]
    statement = str(manifest.get("no_inference_statement") or NO_INFERENCE_STATEMENT)
    body = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>V4.2A Span-Controlled Visual Planning Audit</title>
<style>{PRINT_CSS}</style></head><body>
<h1>V4.2A Span-Controlled Visual Planning Audit</h1>
<p><strong>No-inference:</strong> {html.escape(statement)}</p>
<p class="muted">Git <code>{html.escape(str(manifest.get("git_revision")))}</code>
· schema <code>{html.escape(config.schema_version)}</code>
· cases {len(realized)}
· seed {html.escape(str(manifest.get("seed")))}
· lattice {html.escape(str(manifest.get("lattice_shape")))}
· V3.6D digest <code>{html.escape(str(manifest.get("v3_6d_digest")))}</code>
· config digest <code>{html.escape(config.digest())}</code></p>
<p>175° remains <code>{html.escape(SPAN_175_STATUS)}</code>. It is a typed
near-limit case, not a retuned primary certificate. The cell
<code>{html.escape(dual.case.case_id)}</code> has dual membership
({html.escape(", ".join(dual.case.memberships))}) and one physical record.</p>
<p>The audit pair is four-bar versus span-matched gearbox. Identity-on-shared-Q
is a geometry null control from V4.2 and is <em>not</em> a planner arm.
Each case page is a V3.6B-style trial-scoped audit. Starts are re-resolved
per case from the frozen <code>start_u_frac</code>; Cartesian disks stay the
frozen V3.6 v2 bank.</p>
<p><a href="architecture.html">Architecture / provenance</a> ·
<a href="manifest.json">manifest.json</a> ·
<a href="summary.json">summary.json</a></p>
{core}
{bio}
</body></html>
"""
    path = output / "index.html"
    path.write_text(body, encoding="utf-8")
    return path
