"""Two-matrix HTML for the V4.2B mounted-Q geometry atlas.

Does not generate matplotlib heatmaps. Case cells link to per-case
compressed sample files.
"""

from __future__ import annotations

import html
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from inequality_mechanisms.experiments.span_cases import (
    BIO_SPANS_DEG,
    CORE_SPANS_DEG,
    case_id_for,
)
from inequality_mechanisms.experiments.v4.atlas_config import NO_INFERENCE_STATEMENT
from inequality_mechanisms.experiments.v4.span_controlled_atlas_config import (
    SPAN_175_STATUS,
)
from inequality_mechanisms.experiments.v4.span_controlled_corrective_config import (
    SpanControlledCorrectiveConfig,
)
from inequality_mechanisms.mechanisms.span_registry import SpanRegistry
from inequality_mechanisms.visualization.v4.geometry_atlas import _HTML_CSS


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
    atlases_by_id: Mapping[str, Any],
    registry: SpanRegistry,
) -> str:
    header = "".join(f"<th>{_status_cell(registry, span)}</th>" for span in spans)
    rows = []
    for j1 in spans:
        cells = [f"<th>{_status_cell(registry, j1)}</th>"]
        for j2 in spans:
            case_id = case_id_for(j1, j2)
            atlas = atlases_by_id[case_id]
            memberships = ", ".join(atlas.realized.case.memberships)
            href = (
                f"geometry_atlas/cases/{html.escape(case_id)}/geometry_samples.jsonl.gz"
            )
            cells.append(
                f'<td><a href="{href}">{html.escape(case_id)}</a>'
                f'<div class="muted">{html.escape(memberships)}</div></td>'
            )
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return (
        f"<h2>{html.escape(title)}</h2>"
        "<table><thead><tr><th>J1 \\ J2</th>"
        f"{header}</tr></thead><tbody>{''.join(rows)}</tbody></table>"
    )


def write_span_controlled_corrective_html(
    output: Path,
    *,
    config: SpanControlledCorrectiveConfig,
    registry: SpanRegistry,
    atlases: Sequence[Any],
    manifest: Mapping[str, Any],
) -> Path:
    """Write the two-matrix index. Does not emit per-case figures."""
    output = Path(output)
    atlases_by_id = {atlas.realized.case.case_id: atlas for atlas in atlases}
    n_failed = sum(
        1 for atlas in atlases for row in atlas.rows if row.failure_code is not None
    )
    core = _matrix_table(
        title="Core span sweep (95°, 145°, 175°)",
        spans=CORE_SPANS_DEG,
        atlases_by_id=atlases_by_id,
        registry=registry,
    )
    bio = _matrix_table(
        title="Biological refinement (135°, 145°, 150°)",
        spans=BIO_SPANS_DEG,
        atlases_by_id=atlases_by_id,
        registry=registry,
    )
    dual = atlases_by_id[case_id_for(145.0, 145.0)]
    body = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>V4.2B Span-Controlled Corrective Geometry Atlas</title>
<style>{_HTML_CSS}</style></head><body>
<h1>V4.2B Span-Controlled Corrective Geometry Atlas</h1>
<p><strong>{html.escape(NO_INFERENCE_STATEMENT)}</strong></p>
<p class="muted">Git <code>{html.escape(str(manifest.get("git_revision")))}</code>
· schema <code>{html.escape(config.schema_version)}</code>
· cases {len(atlases)}
· grid {list(manifest.get("grid", config.grid.shape))}
· rows {manifest.get("n_rows")}
· typed failures {n_failed}
· V3.6D digest <code>{html.escape(str(manifest.get("v3_6d_digest")))}</code>
· config digest <code>{html.escape(config.digest())}</code></p>
<p>Mounted robot joint coordinates are authoritative. Native follower
intervals remain provenance only. 175° remains
<code>{html.escape(SPAN_175_STATUS)}</code>. The cell
<code>{html.escape(dual.realized.case.case_id)}</code> has dual membership
({html.escape(", ".join(dual.realized.case.memberships))}) and one physical record.</p>
<p>Identity-on-shared-Q is a <em>null control</em>, not a ranked competitor.
Compare cases through stable grid/eta identities; Q boxes differ by span.</p>
<p><a href="manifest.json">manifest.json</a> ·
<a href="resolved_config.json">resolved_config.json</a> ·
<a href="cases.json">cases.json</a> ·
<a href="rank_fields.json">rank_fields.json</a></p>
{core}
{bio}
</body></html>
"""
    path = output / "index.html"
    path.write_text(body, encoding="utf-8")
    return path
