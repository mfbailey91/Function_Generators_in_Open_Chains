"""V3.6F 17-case gravity-free static wrench atlas."""

from __future__ import annotations

import hashlib
import html
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from inequality_mechanisms.adapters import planar_2r_operating_branch_robot
from inequality_mechanisms.audits.static_wrench_plots import (
    PAIRED_MECHANISMS,
    field_grid,
    shared_limits,
    write_paired_heatmap,
    write_polygon_overlay,
)
from inequality_mechanisms.audits.v3_span_wrench_guard import (
    V3_6F_ALLOWED_PACKAGE,
    assert_v3_6f_output_allowed,
    prepare_v3_6f_output_dir,
)
from inequality_mechanisms.experiments.span_cases import realize_supported_cases
from inequality_mechanisms.experiments.span_wrench_config import DEFAULT_CONFIG_REL
from inequality_mechanisms.experiments.v4.shared_q_atlas import build_shared_q_bank
from inequality_mechanisms.kinematics.planar_2r import Planar2R
from inequality_mechanisms.mechanisms.span_registry import load_span_registry
from inequality_mechanisms.metrics.static_wrench import (
    DEFAULT_TORQUE_LIMITS,
    SCHEMA_VERSION as WRENCH_SCHEMA,
    evaluate_static_wrench_grid,
    grid_cache_key,
)

SCHEMA_VERSION = "v3.6f.static_wrench_atlas.v1"
GRID_SHAPE = (11, 11)
INSET_FRACTION = 0.02
POLYGON_STRIDE = 2
PLANAR = Planar2R(L1=1.0, L2=1.0)
D_REGISTRY = Path("results") / "v3_review" / "v3_6d_span_corpus" / "registry.json"
METHOD_NOTE = Path("docs") / "software" / "architecture" / "notes" / "STATIC_WRENCH_KINEMATIC_GEOMETRY_METHOD.md"
BIO_TRACE = Path("docs") / "research" / "literature" / "BIOLOGICAL_JOINT_RANGE_REFERENCE_TRACE.md"
DIRECTION_KEYS = ("positive_x", "positive_y", "radial", "tangential")

_HTML_CSS = """
body { font-family: Georgia, "Times New Roman", serif; margin: 1.2rem; color: #222; }
table { border-collapse: collapse; width: 100%; margin: 0.6rem 0 1.2rem; font-size: 0.92rem; }
th, td { border: 1px solid #bbb; padding: 0.35rem 0.45rem; vertical-align: top; }
th { background: #f3f3f3; }
img { max-width: 100%; height: auto; border: 1px solid #ddd; margin: 0.25rem 0; }
.muted { color: #555; }
code { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 0.85rem; }
.banner { background: #f7f1e8; border: 1px solid #d9c7a3; padding: 0.7rem 0.9rem; }
.js-only { display: none; }
@media print {
  .no-print { display: none !important; }
  .print-only { display: block !important; }
}
"""


def _git_revision() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def _write_json(path: Path, payload: Any) -> str:
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    data = text.encode("utf-8")
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _cell_record(sample, mechanism_id: str, cap) -> dict[str, Any]:
    payload = cap.to_dict()
    return {
        "q_sample_id": sample.q_sample_id,
        "grid_index": list(sample.grid_index),
        "mechanism_id": mechanism_id,
        "q": list(sample.q),
        "u": payload["u"],
        "x": payload["x"],
        "status": payload["status"],
        "rank": payload["rank"],
        "isotropic_radius": payload["isotropic_radius"],
        "directional_capacity": payload["directional_capacity"],
        "undefined_directions": payload["undefined_directions"],
        "vertices": payload["vertices"],
        "rank_attribution": payload["rank_attribution"],
        "j_g": payload["j_g"],
        "j_f": payload["j_f"],
        "j_xu": payload["j_xu"],
        "joint_torque_amplification": payload["joint_torque_amplification"],
    }


def _evaluate_case(realized, *, torque_limits, trace: bool) -> dict[str, Any]:
    cert = realized.fourbar.certificate
    bank = build_shared_q_bank(
        cert.output_lower,
        cert.output_upper,
        shape=GRID_SHAPE,
        inset_fraction=INSET_FRACTION,
    )
    robots = {
        "fourbar": planar_2r_operating_branch_robot(realized.fourbar, planar_fk=PLANAR),
        "gearbox": planar_2r_operating_branch_robot(realized.gearbox, planar_fk=PLANAR),
    }
    qs = bank.q_array()
    records: list[dict[str, Any]] = []
    for mech, robot in robots.items():
        key = grid_cache_key(
            registry_hash="atlas",
            case_id=realized.case.case_id,
            mechanism_id=mech,
            q_samples=qs,
            torque_limits=torque_limits,
        )
        if trace:
            key = key + "|trace"
        caps = evaluate_static_wrench_grid(robot, qs, torque_limits=torque_limits, cache_key=key)
        for sample, cap in zip(bank.samples, caps):
            records.append(_cell_record(sample, mech, cap))
    iso = {
        mech: field_grid(records, mechanism_id=mech, bank=bank, key="isotropic_radius")
        for mech in PAIRED_MECHANISMS
    }
    vmin, vmax = shared_limits(*iso.values())
    center = bank.samples[len(bank.samples) // 2]
    center_rows = [row for row in records if row["q_sample_id"] == center.q_sample_id]
    return {
        "case": realized.case.to_dict(),
        "j1_status": realized.j1.status,
        "j2_status": realized.j2.status,
        "q_lower": list(bank.q_lower),
        "q_upper": list(bank.q_upper),
        "grid_shape": list(bank.shape),
        "color_limits": {"isotropic_radius": [vmin, vmax]},
        "center_sample": center.q_sample_id,
        "center_readout": center_rows,
        "bank": bank,
        "records": records,
        "trace": bool(trace),
    }


def _write_case_figures(case_dir: Path, payload: Mapping[str, Any]) -> dict[str, str]:
    bank = payload["bank"]
    records = payload["records"]
    fig_dir = case_dir / "figures"
    assets: dict[str, str] = {}
    iso = {
        mech: field_grid(records, mechanism_id=mech, bank=bank, key="isotropic_radius")
        for mech in PAIRED_MECHANISMS
    }
    vmin, vmax = payload["color_limits"]["isotropic_radius"]
    write_paired_heatmap(
        fig_dir / "scalar.png",
        bank=bank,
        grids=iso,
        title="isotropic force capacity (paired scale, unclipped source)",
        vmin=vmin,
        vmax=vmax,
    )
    assets["scalar"] = "figures/scalar.png"
    for direction in DIRECTION_KEYS:
        grids = {}
        for mech in PAIRED_MECHANISMS:
            grid = np.full(bank.shape, np.nan, dtype=np.float64)
            for row in records:
                if row["mechanism_id"] != mech:
                    continue
                if direction in row.get("undefined_directions", []):
                    continue
                value = row["directional_capacity"].get(direction)
                if value is None or not np.isfinite(value):
                    continue
                i, j = row["grid_index"]
                grid[int(i), int(j)] = float(value)
            grids[mech] = grid
        dmin, dmax = shared_limits(*grids.values())
        write_paired_heatmap(
            fig_dir / f"{direction}.png",
            bank=bank,
            grids=grids,
            title=f"directional capacity {direction}",
            vmin=dmin,
            vmax=dmax,
        )
        assets[direction] = f"figures/{direction}.png"
    write_polygon_overlay(
        fig_dir / "polygons.png",
        bank=bank,
        records=records,
        stride=POLYGON_STRIDE,
        title="sparse exact force polygons (X = non-polygon status)",
    )
    assets["polygons"] = "figures/polygons.png"
    return assets


def _case_html(payload: Mapping[str, Any], assets: Mapping[str, str]) -> str:
    case = payload["case"]
    case_id = html.escape(case["case_id"])
    options = "".join(
        f'<option value="{html.escape(key)}">{html.escape(label)}</option>'
        for key, label in (
            ("scalar", "isotropic capacity (default)"),
            ("positive_x", "+x"),
            ("positive_y", "+y"),
            ("radial", "radial"),
            ("tangential", "tangential"),
            ("polygons", "sparse exact polygons"),
        )
    )
    readout = json.dumps(payload["center_readout"], indent=2)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>{case_id}</title>
<style>{_HTML_CSS}</style></head><body>
<p><a href="../../index.html">Index</a></p>
<h1>{case_id}</h1>
<p class="muted">J1 {html.escape(str(payload["j1_status"]))} · J2 {html.escape(str(payload["j2_status"]))}
· memberships {html.escape(", ".join(case["memberships"]))}
· grid {payload["grid_shape"]}</p>
<p>Paired color limits (isotropic): {payload["color_limits"]["isotropic_radius"]}.
Source values are unclipped. Gravity is excluded, not an option.</p>
<label class="no-print">View
<select id="view-select">{options}</select>
</label>
<figure id="main-figure">
<img id="main-image" src="{html.escape(assets["scalar"])}" alt="isotropic capacity"/>
<figcaption>Default view: isotropic capacity heatmap.</figcaption>
</figure>
<h2>Sparse polygons</h2>
<figure><img src="{html.escape(assets["polygons"])}" alt="polygons"/></figure>
<h2>Center-cell readout</h2>
<pre>{html.escape(readout)}</pre>
<p><a href="cells.jsonl">cells.jsonl</a> · <a href="summary.json">summary.json</a></p>
<script>
const images = {json.dumps(assets)};
const select = document.getElementById("view-select");
const img = document.getElementById("main-image");
select.addEventListener("change", () => {{
  const key = select.value;
  img.src = images[key];
  img.alt = key;
}});
</script>
</body></html>
"""


def _index_html(cases: list[dict[str, Any]]) -> str:
    rows = []
    thumbs = []
    for row in cases:
        cid = html.escape(row["case_id"])
        href = html.escape(f"cases/{row['case_id']}/index.html")
        img = html.escape(f"cases/{row['case_id']}/figures/scalar.png")
        rows.append(
            f"<tr><td><a href=\"{href}\">{cid}</a></td>"
            f"<td>{row['span_j1_deg']:.0f}</td><td>{row['span_j2_deg']:.0f}</td>"
            f"<td>{html.escape(', '.join(row['memberships']))}</td>"
            f"<td>{html.escape(row['j1_status'])}</td>"
            f"<td>{html.escape(row['j2_status'])}</td></tr>"
        )
        thumbs.append(
            f"<figure><img src=\"{img}\" alt=\"{cid} scalar\"/>"
            f"<figcaption>{cid}</figcaption></figure>"
        )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>V3.6F Gravity-Free Static Wrench Atlas</title>
<style>{_HTML_CSS}</style></head><body>
<h1>V3.6F Gravity-Free Static Wrench Atlas</h1>
<div class="banner">
<p><strong>Intrinsic kinematic geometry plus ideal virtual work.</strong>
Normalized actuator torque box <code>[1, 1]</code>. Gravity, payload, inertia,
and structural limits are excluded; they are not implemented options.
This package does not overwrite V4.1 and is not Sprint V4.3.</p>
<p>Default view: isotropic-capacity heatmap. Directional maps and exact polygons
are secondary. Paired four-bar/gearbox panels share color limits and Q samples.</p>
</div>
<p class="muted"><a href="print.html">Print fallback</a> ·
<a href="methods.md">Methods</a> ·
<a href="biological_trace.md">Biological range trace</a> ·
<a href="manifest.json">manifest.json</a></p>
<h2>Seventeen-case matrix</h2>
<table>
<tr><th>case</th><th>J1</th><th>J2</th><th>membership</th><th>J1 status</th><th>J2 status</th></tr>
{''.join(rows)}
</table>
<h2>Default scalar heatmaps</h2>
{''.join(thumbs)}
</body></html>
"""


def _print_html(cases: list[dict[str, Any]]) -> str:
    blocks = []
    for row in cases:
        cid = html.escape(row["case_id"])
        img = html.escape(f"cases/{row['case_id']}/figures/scalar.png")
        blocks.append(f"<h2>{cid}</h2><img src=\"{img}\" alt=\"{cid} scalar\"/>")
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>V3.6F print fallback</title>
<style>{_HTML_CSS}</style></head><body>
<h1>V3.6F print fallback</h1>
<p>Gravity-free static wrench atlas. Default scalar (isotropic) maps only.
Normalized torque box [1, 1]. Gravity is excluded.</p>
{''.join(blocks)}
</body></html>
"""


def export_static_wrench_atlas(
    *,
    output: Path | None = None,
    trace: bool = False,
) -> Path:
    """Write the 17-case atlas package. Trace metadata does not change values."""
    target = output
    if target is None:
        target = Path("results") / "v3_review" / V3_6F_ALLOWED_PACKAGE
    root = prepare_v3_6f_output_dir(assert_v3_6f_output_allowed(target))
    registry = load_span_registry(json.loads(D_REGISTRY.read_text(encoding="utf-8")))
    realized = realize_supported_cases(registry)
    if len(realized) != 17:
        raise ValueError(f"expected 17 realized cases, got {len(realized)}")
    case_summaries: list[dict[str, Any]] = []
    files: dict[str, str] = {}
    for item in realized:
        evaluated = _evaluate_case(item, torque_limits=DEFAULT_TORQUE_LIMITS, trace=trace)
        case_dir = root / "cases" / item.case.case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        assets = _write_case_figures(case_dir, evaluated)
        serializable = {
            key: value
            for key, value in evaluated.items()
            if key not in {"bank", "records"}
        }
        serializable["assets"] = assets
        files[f"cases/{item.case.case_id}/summary.json"] = _write_json(
            case_dir / "summary.json", serializable
        )
        lines = "".join(json.dumps(row, sort_keys=True) + "\n" for row in evaluated["records"])
        (case_dir / "cells.jsonl").write_text(lines, encoding="utf-8")
        (case_dir / "index.html").write_text(_case_html(evaluated, assets), encoding="utf-8")
        case_summaries.append(
            {
                **item.case.to_dict(),
                "j1_status": item.j1.status,
                "j2_status": item.j2.status,
                "href": f"cases/{item.case.case_id}/index.html",
                "scalar_image": f"cases/{item.case.case_id}/figures/scalar.png",
                "color_limits": evaluated["color_limits"],
                "q_samples": [list(s.q) for s in evaluated["bank"].samples],
            }
        )
    files["cases.json"] = _write_json(root / "cases.json", case_summaries)
    (root / "index.html").write_text(_index_html(case_summaries), encoding="utf-8")
    (root / "print.html").write_text(_print_html(case_summaries), encoding="utf-8")
    shutil.copyfile(METHOD_NOTE, root / "methods.md")
    shutil.copyfile(BIO_TRACE, root / "biological_trace.md")
    files["schema.json"] = _write_json(
        root / "schema.json",
        {
            "schema_version": SCHEMA_VERSION,
            "wrench_schema": WRENCH_SCHEMA,
            "config": str(DEFAULT_CONFIG_REL),
            "grid_shape": list(GRID_SHAPE),
            "inset_fraction": INSET_FRACTION,
            "polygon_stride": POLYGON_STRIDE,
            "default_view": "scalar_heatmap",
            "gravity_implemented": False,
            "trace": bool(trace),
        },
    )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_revision": _git_revision(),
        "package": V3_6F_ALLOWED_PACKAGE,
        "n_cases": len(case_summaries),
        "trace": bool(trace),
        "no_inference": "gravity-free static wrench atlas; no mechanism ranking.",
        "files": files,
    }
    _write_json(root / "manifest.json", manifest)
    return root
