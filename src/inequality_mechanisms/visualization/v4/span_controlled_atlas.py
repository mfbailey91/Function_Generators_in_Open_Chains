"""Two-matrix HTML for the V4.2 span-controlled geometry atlas."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any, Mapping, Sequence

from inequality_mechanisms.experiments.span_cases import (
    BIO_SPANS_DEG,
    CORE_SPANS_DEG,
    case_id_for,
)
from inequality_mechanisms.experiments.v4.atlas_config import NO_INFERENCE_STATEMENT
from inequality_mechanisms.experiments.v4.span_controlled_atlas_config import (
    SPAN_175_STATUS,
    SpanControlledAtlasConfig,
)
from inequality_mechanisms.mechanisms.span_registry import SpanRegistry
from inequality_mechanisms.visualization.v4.geometry_atlas import (
    _HTML_CSS,
    write_atlas_figures,
)

_FIGURE_CAPTIONS = (
    ("sigma_min_jg", "sigma_min J_g"),
    ("sigma_max_jg", "sigma_max J_g"),
    ("sigma_min_jf", "sigma_min J_f"),
    ("sigma_max_jf", "sigma_max J_f"),
    ("sigma_min_jxu", "sigma_min J_xu"),
    ("sigma_max_jxu", "sigma_max J_xu"),
    ("metric_lambda_min", "M_Q lambda_min"),
    ("metric_lambda_max", "M_Q lambda_max"),
    ("metric_sqrt_kappa", "M_Q sqrt_kappa"),
    ("metric_sqrt_det", "M_Q sqrt_det"),
    ("mobility_q_lambda_min", "B_Q lambda_min"),
    ("mobility_q_sqrt_kappa", "B_Q sqrt_kappa"),
    ("mobility_x_sqrt_kappa", "B_X sqrt_kappa"),
    ("rank_jg", "rank J_g"),
    ("rank_jf", "rank J_f"),
    ("rank_jxu", "rank J_xu"),
    ("metric_available", "inverse-metric availability"),
)


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
    header = "".join(
        f"<th>{_status_cell(registry, span)}</th>" for span in spans
    )
    rows = []
    for j1 in spans:
        cells = [f"<th>{_status_cell(registry, j1)}</th>"]
        for j2 in spans:
            case_id = case_id_for(j1, j2)
            atlas = atlases_by_id[case_id]
            memberships = ", ".join(atlas.realized.case.memberships)
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


def _write_case_page(output: Path, atlas: Any, *, manifest: Mapping[str, Any]) -> Path:
    case_dir = output / "cases" / atlas.realized.case.case_id
    figures = case_dir / "figures"
    assets = write_atlas_figures(
        figures, arms=atlas.arms, bank=atlas.bank, rows=atlas.rows
    )
    n_failed = sum(1 for row in atlas.rows if row.failure_code is not None)
    case = atlas.realized.case

    def img(name: str, caption: str) -> str:
        rel = assets[name].relative_to(case_dir)
        return (
            f"<figure><img src=\"{html.escape(rel.as_posix())}\" "
            f"alt=\"{html.escape(caption)}\"/>"
            f"<figcaption>{html.escape(caption)}</figcaption></figure>"
        )

    mapping_imgs = "".join(
        f"<figure><img src=\"{html.escape(path.relative_to(case_dir).as_posix())}\" "
        f"alt=\"{html.escape(key)}\"/><figcaption>{html.escape(key)}</figcaption></figure>"
        for key, path in assets.items()
        if key.startswith("mapping_")
    )
    body = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>{html.escape(case.case_id)}</title>
<style>{_HTML_CSS}</style></head><body>
<p><a href="../../index.html">Back to V4.2 index</a></p>
<h1>{html.escape(case.case_id)}</h1>
<p><strong>{html.escape(NO_INFERENCE_STATEMENT)}</strong></p>
<p class="muted">J1 {case.span_j1_deg:g}° ({html.escape(atlas.realized.j1.status)})
· J2 {case.span_j2_deg:g}° ({html.escape(atlas.realized.j2.status)})
· memberships {html.escape(", ".join(case.memberships))}
· samples {len(atlas.bank.samples)}
· failed rows {n_failed}
· git <code>{html.escape(str(manifest.get("git_revision")))}</code></p>
<p>Identity-on-shared-Q is a <em>null control</em>, not a third ranked competitor.
Paired color limits are computed from the four-bar and span-matched gearbox only.</p>
<h2>Transmission maps</h2>
{mapping_imgs}
<h2>Singular values</h2>
{"".join(img(name, caption) for name, caption in _FIGURE_CAPTIONS[:6])}
<h2>Actuator metric on Q</h2>
{"".join(img(name, caption) for name, caption in _FIGURE_CAPTIONS[6:10])}
<h2>Mobility</h2>
{"".join(img(name, caption) for name, caption in _FIGURE_CAPTIONS[10:13])}
<h2>Rank attribution</h2>
{"".join(img(name, caption) for name, caption in _FIGURE_CAPTIONS[13:])}
</body></html>
"""
    path = case_dir / "index.html"
    path.write_text(body, encoding="utf-8")
    return path


def write_span_controlled_atlas_html(
    output: Path,
    *,
    config: SpanControlledAtlasConfig,
    registry: SpanRegistry,
    atlases: Sequence[Any],
    manifest: Mapping[str, Any],
) -> Path:
    """Write the two-matrix index and per-case figure pages."""
    output = Path(output)
    atlases_by_id = {atlas.realized.case.case_id: atlas for atlas in atlases}
    for atlas in atlases:
        _write_case_page(output, atlas, manifest=manifest)
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
<title>V4.2 Span-Controlled Geometry Atlas</title>
<style>{_HTML_CSS}</style></head><body>
<h1>V4.2 Span-Controlled Geometry Atlas</h1>
<p><strong>{html.escape(NO_INFERENCE_STATEMENT)}</strong></p>
<p class="muted">Git <code>{html.escape(str(manifest.get("git_revision")))}</code>
· schema <code>{html.escape(config.schema_version)}</code>
· cases {len(atlases)}
· grid {list(manifest.get("grid", config.grid.shape))}
· rows {manifest.get("n_rows")}
· failed rows {n_failed}
· V3.6D digest <code>{html.escape(str(manifest.get("v3_6d_digest")))}</code>
· config digest <code>{html.escape(config.digest())}</code></p>
<p>175° remains <code>{html.escape(SPAN_175_STATUS)}</code>. It is a typed
near-limit case, not a retuned primary certificate. The cell
<code>{html.escape(dual.realized.case.case_id)}</code> has dual membership
({html.escape(", ".join(dual.realized.case.memberships))}) and one physical record.</p>
<p>Identity-on-shared-Q is a <em>null control</em>, not a ranked competitor.
Paired color limits on case pages use the four-bar and span-matched gearbox only.</p>
<p><a href="manifest.json">manifest.json</a> ·
<a href="resolved_config.json">resolved_config.json</a> ·
<a href="cases.json">cases.json</a> ·
<a href="geometry_samples.jsonl">geometry_samples.jsonl</a> ·
<a href="rank_fields.json">rank_fields.json</a></p>
{core}
{bio}
</body></html>
"""
    path = output / "index.html"
    path.write_text(body, encoding="utf-8")
    return path
