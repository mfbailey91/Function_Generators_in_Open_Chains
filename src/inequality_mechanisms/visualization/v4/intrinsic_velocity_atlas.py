"""HTML atlas figures and assets for the V4.4 intrinsic velocity package."""

from __future__ import annotations

import html
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from inequality_mechanisms.audits.v4_4_artifact import DIRECTIONS, strict_json
from inequality_mechanisms.audits.v4_4_atlas_artifact import (
    ATLAS_FIGURES,
    PRIMARY_MECHANISM_PAIR,
)
from inequality_mechanisms.experiments.v4.intrinsic_static_wrench_config import (
    FROZEN_MECHANISM_IDS,
)

POLYGON_STRIDE = 4


def _require_matplotlib() -> Any:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def write_local_assets(root: Path) -> None:
    assets = root / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "atlas.css").write_text(
        """
body{font:16px/1.5 system-ui,sans-serif;color:#24324a;margin:0;padding:24px}
main{max-width:1100px;margin:0 auto}
h1,h2{line-height:1.2}
nav a{margin-right:12px;color:#176a94}
figure{margin:18px 0}
img{max-width:100%;height:auto}
select,button{font:inherit;margin:4px 6px 4px 0}
.table-scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{border:1px solid #d7dfe7;padding:6px;text-align:left}
th{background:#edf2f7}
#inspector{background:#f7fafc;border:1px solid #d7dfe7;padding:12px;margin-top:12px}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (assets / "atlas.js").write_text(
        """
(() => {
  const data = JSON.parse(document.getElementById('atlas-data').textContent);
  const sampleSelect = document.getElementById('sample-select');
  const viewSelect = document.getElementById('view-select');
  const out = document.getElementById('inspector');
  function render() {
    const row = data.rows.find(r => r.q_sample_id === sampleSelect.value
      && r.mechanism_id === 'fourbar') || data.rows[0];
    const view = viewSelect.value;
    const cap = row.capability;
    let value = null;
    if (view === 'isotropic_speed') value = cap.isotropic_speed;
    else if (cap.directional_ray_speed) value = cap.directional_ray_speed[view];
    const peers = data.rows.filter(r => r.q_sample_id === row.q_sample_id);
    out.innerHTML = '<pre>' + JSON.stringify({
      q_sample_id: row.q_sample_id,
      grid_index: row.grid_index,
      view, value,
      status_by_mechanism: Object.fromEntries(
        peers.map(p => [p.mechanism_id, p.capability.status])),
      primary_eligible: row.primary_eligible,
      directions: cap.directions,
      directional_support: cap.directional_support,
      directional_ray_speed: cap.directional_ray_speed,
      ik_positive_x: row.ik_positive_x
    }, null, 2) + '</pre>';
  }
  sampleSelect.addEventListener('change', render);
  viewSelect.addEventListener('change', render);
  render();
})();
""".strip()
        + "\n",
        encoding="utf-8",
    )


def finite_color_limits(values: np.ndarray) -> list[float]:
    finite = values[np.isfinite(values)]
    if not finite.size:
        return [0.0, 1.0]
    low, high = float(np.min(finite)), float(np.max(finite))
    if high <= low:
        high = low + max(abs(low) * 1e-12, 1e-12)
    return [low, high]


def _field_grid(
    records: Sequence[Mapping[str, Any]],
    *,
    mechanism_id: str,
    key: str,
    shape: tuple[int, int] = (33, 33),
    primary_only: bool = True,
) -> np.ndarray:
    grid = np.full(shape, np.nan, dtype=np.float64)
    for row in records:
        if row["mechanism_id"] != mechanism_id:
            continue
        if primary_only and not row.get("primary_eligible"):
            continue
        cap = row["capability"]
        if key == "isotropic_speed":
            value = cap.get("isotropic_speed")
        else:
            value = (cap.get("directional_ray_speed") or {}).get(key)
            status = (cap.get("direction_status") or {}).get(key)
            if status not in {None, "defined", "defined_in_inherited_range"}:
                value = None
        if value is None or not math.isfinite(float(value)):
            continue
        i, j = row["grid_index"]
        grid[int(i), int(j)] = float(value)
    return grid


def write_paired_heatmap(
    path: Path,
    *,
    qq1: np.ndarray,
    qq2: np.ndarray,
    grids: Mapping[str, np.ndarray],
    title: str,
    vmin: float,
    vmax: float,
) -> None:
    plt = _require_matplotlib()
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.6), squeeze=False)
    for ax, key in zip(axes[0], PRIMARY_MECHANISM_PAIR, strict=True):
        mesh = ax.pcolormesh(
            qq1,
            qq2,
            grids[key],
            shading="nearest",
            cmap="viridis",
            vmin=vmin,
            vmax=vmax,
        )
        ax.set_title(key)
        ax.set_xlabel("mounted-Q grid index i")
        ax.set_ylabel("mounted-Q grid index j")
        ax.set_aspect("equal")
        fig.colorbar(mesh, ax=ax, fraction=0.046, pad=0.04)
    fig.suptitle(title)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110)
    plt.close(fig)


def write_identity_heatmap(
    path: Path,
    *,
    qq1: np.ndarray,
    qq2: np.ndarray,
    grid: np.ndarray,
    title: str,
    vmin: float,
    vmax: float,
) -> None:
    plt = _require_matplotlib()
    fig, ax = plt.subplots(figsize=(4.2, 3.6))
    mesh = ax.pcolormesh(
        qq1, qq2, grid, shading="nearest", cmap="viridis", vmin=vmin, vmax=vmax
    )
    ax.set_title(title)
    ax.set_aspect("equal")
    fig.colorbar(mesh, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110)
    plt.close(fig)


def write_status_heatmap(
    path: Path,
    *,
    records: Sequence[Mapping[str, Any]],
    shape: tuple[int, int] = (33, 33),
) -> None:
    plt = _require_matplotlib()
    labels = {
        "regular": 0.0,
        "near_singular": 1.0,
        "bounded_rank_deficient": 2.0,
        "bounded_zero_rank": 3.0,
    }
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.6), squeeze=False)
    for ax, mech in zip(axes[0], PRIMARY_MECHANISM_PAIR, strict=True):
        grid = np.full(shape, np.nan)
        for row in records:
            if row["mechanism_id"] != mech:
                continue
            i, j = row["grid_index"]
            grid[int(i), int(j)] = labels.get(row["capability"]["status"], np.nan)
        mesh = ax.pcolormesh(
            np.arange(shape[0]),
            np.arange(shape[1]),
            grid,
            shading="nearest",
            cmap="tab10",
            vmin=0,
            vmax=3,
        )
        ax.set_title(mech)
        ax.set_aspect("equal")
        fig.colorbar(mesh, ax=ax, fraction=0.046, pad=0.04)
    fig.suptitle("Physical velocity status")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110)
    plt.close(fig)


def write_polygon_glyphs(
    path: Path, *, records: Sequence[Mapping[str, Any]], stride: int = POLYGON_STRIDE
) -> None:
    plt = _require_matplotlib()
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.6), squeeze=False)
    for ax, mech in zip(axes[0], PRIMARY_MECHANISM_PAIR, strict=True):
        for row in records:
            if row["mechanism_id"] != mech:
                continue
            i, j = row["grid_index"]
            if (i + j) % stride != 0 or not row.get("primary_eligible"):
                continue
            corners = np.asarray(row["capability"]["velocity_corners"], dtype=float)
            center = corners.mean(axis=0)
            centered = corners - center
            scale = np.max(np.linalg.norm(centered, axis=1))
            if scale <= 0:
                continue
            glyph = centered / scale * 0.35
            closed = np.vstack([glyph, glyph[0]])
            ax.plot(i + closed[:, 0], j + closed[:, 1], color="#176a94", linewidth=0.8)
        ax.set_title(mech)
        ax.set_aspect("equal")
    fig.suptitle("Shape-normalized velocity polygons")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110)
    plt.close(fig)


def write_true_scale_detail(
    path: Path, *, records: Sequence[Mapping[str, Any]], q_sample_id: str
) -> dict[str, Any] | None:
    selected = [row for row in records if row["q_sample_id"] == q_sample_id]
    if len(selected) < 2:
        return None
    selected = sorted(
        selected, key=lambda row: FROZEN_MECHANISM_IDS.index(row["mechanism_id"])
    )
    plt = _require_matplotlib()
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.6), squeeze=False)
    bound = 1.1 * max(
        float(np.max(np.abs(row["capability"]["velocity_corners"])))
        for row in selected[:2]
    )
    bound = max(bound, 1e-12)
    colors = ("#176a94", "#a13e62")
    for ax, row, color in zip(axes[0], selected[:2], colors, strict=True):
        verts = np.asarray(row["capability"]["velocity_corners"], float)
        closed = np.vstack([verts, verts[0]])
        ax.fill(verts[:, 0], verts[:, 1], color=color, alpha=0.15)
        ax.plot(closed[:, 0], closed[:, 1], color=color, linewidth=1.5)
        ax.set_xlim(-bound, bound)
        ax.set_ylim(-bound, bound)
        ax.set_aspect("equal")
        ax.set_title(row["mechanism_id"])
    fig.suptitle(f"True-scale velocity polygons · {q_sample_id}")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return {"force_bounds": {"xlim": [-bound, bound], "ylim": [-bound, bound]}}


def write_comparison_heatmaps(
    path_delta: Path,
    path_ratio: Path,
    *,
    records: Sequence[Mapping[str, Any]],
    shape: tuple[int, int] = (33, 33),
) -> None:
    left = {
        tuple(row["grid_index"]): row
        for row in records
        if row["mechanism_id"] == "fourbar" and row.get("primary_eligible")
    }
    right = {
        tuple(row["grid_index"]): row
        for row in records
        if row["mechanism_id"] == "span_matched_gearbox" and row.get("primary_eligible")
    }
    delta = np.full(shape, np.nan)
    ratio = np.full(shape, np.nan)
    for index, left_row in left.items():
        right_row = right.get(index)
        if right_row is None:
            continue
        va = left_row["capability"]["isotropic_speed"]
        vb = right_row["capability"]["isotropic_speed"]
        if va is None or vb is None:
            continue
        i, j = index
        delta[i, j] = float(va) - float(vb)
        ratio[i, j] = float(va) / float(vb) if float(vb) != 0 else np.nan
    qq1, qq2 = np.meshgrid(np.arange(shape[0]), np.arange(shape[1]), indexing="ij")
    panels: list[tuple[Path, np.ndarray, str]] = [
        (path_delta, delta, "Isotropic speed delta (fourbar - gearbox)"),
        (path_ratio, ratio, "Isotropic speed ratio (fourbar / gearbox)"),
    ]
    for path, field, title in panels:
        lim = finite_color_limits(field)
        write_identity_heatmap(
            path,
            qq1=qq1,
            qq2=qq2,
            grid=field,
            title=title,
            vmin=lim[0],
            vmax=lim[1],
        )


def write_case_figures(
    case_dir: Path, *, records: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    fig_dir = case_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    shape = (33, 33)
    qq1, qq2 = np.meshgrid(np.arange(shape[0]), np.arange(shape[1]), indexing="ij")
    assets: dict[str, Any] = {}
    color_limits: dict[str, list[float]] = {}

    primary = {
        mech: _field_grid(
            records, mechanism_id=mech, key="isotropic_speed", primary_only=True
        )
        for mech in PRIMARY_MECHANISM_PAIR
    }
    vals = np.concatenate(
        [primary[m][np.isfinite(primary[m])] for m in PRIMARY_MECHANISM_PAIR]
    )
    vmin, vmax = finite_color_limits(vals)
    color_limits["isotropic_speed"] = [vmin, vmax]
    write_paired_heatmap(
        fig_dir / "scalar.png",
        qq1=qq1,
        qq2=qq2,
        grids=primary,
        title="Isotropic speed (regular-finite)",
        vmin=vmin,
        vmax=vmax,
    )
    assets["scalar"] = {
        "src": "figures/scalar.png",
        "alt": "isotropic speed",
        "caption": "Primary isotropic speed on regular cells only.",
    }

    identity = _field_grid(
        records,
        mechanism_id="identity_on_shared_q",
        key="isotropic_speed",
        primary_only=False,
    )
    ilim = finite_color_limits(identity)
    color_limits["identity_isotropic_speed"] = ilim
    write_identity_heatmap(
        fig_dir / "identity_scalar.png",
        qq1=qq1,
        qq2=qq2,
        grid=identity,
        title="Identity isotropic speed",
        vmin=ilim[0],
        vmax=ilim[1],
    )
    assets["identity_scalar"] = {
        "src": "figures/identity_scalar.png",
        "alt": "identity isotropic speed",
        "caption": "Identity-on-shared-Q reference with its own full finite range.",
    }

    write_status_heatmap(fig_dir / "status.png", records=records)
    assets["status"] = {
        "src": "figures/status.png",
        "alt": "status",
        "caption": "Physical velocity status by mechanism.",
    }

    for direction in DIRECTIONS:
        grids = {
            mech: _field_grid(
                records, mechanism_id=mech, key=direction, primary_only=True
            )
            for mech in PRIMARY_MECHANISM_PAIR
        }
        lim = finite_color_limits(
            np.concatenate(
                [grids[m][np.isfinite(grids[m])] for m in PRIMARY_MECHANISM_PAIR]
            )
        )
        color_limits[direction] = lim
        write_paired_heatmap(
            fig_dir / f"{direction}.png",
            qq1=qq1,
            qq2=qq2,
            grids=grids,
            title=f"Ray speed: {direction}",
            vmin=lim[0],
            vmax=lim[1],
        )
        assets[direction] = {
            "src": f"figures/{direction}.png",
            "alt": direction,
            "caption": f"Primary ray speed ({direction}) on regular-finite cells.",
        }
        diag = {
            mech: _field_grid(
                records, mechanism_id=mech, key=direction, primary_only=False
            )
            for mech in PRIMARY_MECHANISM_PAIR
        }
        dlim = finite_color_limits(
            np.concatenate(
                [diag[m][np.isfinite(diag[m])] for m in PRIMARY_MECHANISM_PAIR]
            )
        )
        name = f"{direction}_diagnostic"
        write_paired_heatmap(
            fig_dir / f"{name}.png",
            qq1=qq1,
            qq2=qq2,
            grids=diag,
            title=f"Diagnostic full-finite ray speed: {direction}",
            vmin=dlim[0],
            vmax=dlim[1],
        )
        assets[name] = {
            "src": f"figures/{name}.png",
            "alt": name,
            "caption": (
                f"Diagnostic {direction} including near-singular finite values."
            ),
        }

    write_polygon_glyphs(fig_dir / "polygons.png", records=records)
    assets["polygons"] = {
        "src": "figures/polygons.png",
        "alt": "polygons",
        "caption": "Shape-normalized velocity polygons (not magnitude).",
    }

    detail_rows = sorted(
        (
            row
            for row in records
            if row["mechanism_id"] == "fourbar" and row.get("primary_eligible")
        ),
        key=lambda row: (
            sum(abs(int(v) - 16) for v in row["grid_index"]),
            tuple(row["grid_index"]),
        ),
    )
    if detail_rows:
        write_true_scale_detail(
            fig_dir / "true_scale_detail.png",
            records=records,
            q_sample_id=str(detail_rows[0]["q_sample_id"]),
        )
    else:
        # Placeholder empty figure for inventory completeness.
        plt = _require_matplotlib()
        fig, ax = plt.subplots()
        ax.set_axis_off()
        fig.savefig(fig_dir / "true_scale_detail.png", dpi=110)
        plt.close(fig)
    assets["true_scale_detail"] = {
        "src": "figures/true_scale_detail.png",
        "alt": "true scale detail",
        "caption": "True-scale paired velocity polygons near grid center.",
    }

    write_comparison_heatmaps(
        fig_dir / "delta.png", fig_dir / "ratio.png", records=records
    )
    assets["delta"] = {
        "src": "figures/delta.png",
        "alt": "delta",
        "caption": "Paired isotropic-speed difference on regular cells.",
    }
    assets["ratio"] = {
        "src": "figures/ratio.png",
        "alt": "ratio",
        "caption": "Paired isotropic-speed ratio on regular cells.",
    }
    if set(assets) != set(ATLAS_FIGURES):
        raise ValueError(f"figure inventory mismatch: {sorted(assets)}")
    return {"assets": assets, "color_limits": color_limits}


def _inspector_rows(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    compact = []
    for row in records:
        ik = []
        for request in row["ik_requests"]:
            if request["direction"] != "positive_x":
                continue
            result = request["result"]
            ik.append(
                {
                    "policy": request["policy"],
                    "rate_policy": request["rate_policy"],
                    "status": request["status"],
                    "failure_code": request["failure_code"],
                    "requested_peak": None
                    if result is None
                    else result["requested_peak_utilization"],
                    "commanded_peak": None
                    if result is None
                    else result["commanded_peak_utilization"],
                    "residual_norm": (
                        None if result is None else result["residual_norm"]
                    ),
                }
            )
        compact.append(
            {
                "q_sample_id": row["q_sample_id"],
                "grid_index": row["grid_index"],
                "mechanism_id": row["mechanism_id"],
                "primary_eligible": row["primary_eligible"],
                "capability": {
                    "status": row["capability"]["status"],
                    "isotropic_speed": row["capability"]["isotropic_speed"],
                    "directions": row["capability"]["directions"],
                    "directional_support": row["capability"]["directional_support"],
                    "directional_ray_speed": row["capability"]["directional_ray_speed"],
                    "velocity_corners": row["capability"]["velocity_corners"],
                },
                "ik_positive_x": ik,
            }
        )
    return compact


def write_case_package(
    case_dir: Path, *, case_id: str, rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    figures = write_case_figures(case_dir, records=rows)
    inspector = {"case_id": case_id, "rows": _inspector_rows(rows)}
    (case_dir / "inspector.json").write_text(
        strict_json(inspector) + "\n", encoding="utf-8"
    )
    samples = sorted({row["q_sample_id"] for row in rows})
    options = "".join(
        f'<option value="{html.escape(sample)}">{html.escape(sample)}</option>'
        for sample in samples
    )
    view_options = "".join(
        f'<option value="{html.escape(name)}">{html.escape(name)}</option>'
        for name in ("isotropic_speed", *DIRECTIONS)
    )
    figure_block = "".join(
        (
            f"<figure><img src='{html.escape(asset['src'])}' "
            f"alt='{html.escape(asset['alt'])}'>"
            f"<figcaption>{html.escape(asset['caption'])}</figcaption></figure>"
        )
        for asset in figures["assets"].values()
    )
    atlas_data = strict_json(inspector, indent=None)
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(case_id)} · V4.4 velocity atlas</title>
<link rel="stylesheet" href="../../assets/atlas.css">
</head><body><main>
<p><a href="../../index.html">All cases</a></p>
<h1>{html.escape(case_id)}</h1>
<p>{len(rows)} retained velocity records · three arms · stored-data inspector.</p>
<label>Sample <select id="sample-select">{options}</select></label>
<label>View <select id="view-select">{view_options}</select></label>
<div id="inspector"></div>
{figure_block}
<script id="atlas-data" type="application/json">{atlas_data}</script>
<script src="../../assets/atlas.js"></script>
</main></body></html>
"""
    (case_dir / "index.html").write_text(page, encoding="utf-8")
    summary = {
        "case_id": case_id,
        "n_records": len(rows),
        "assets": figures["assets"],
        "color_limits": figures["color_limits"],
        "samples_href": "velocity_samples.jsonl.gz",
    }
    (case_dir / "summary.json").write_text(
        strict_json(summary) + "\n", encoding="utf-8"
    )
    return {
        "assets": figures["assets"],
        "color_limits": figures["color_limits"],
        "n_records": len(rows),
    }


def write_index_html(
    root: Path,
    *,
    cases: Sequence[Mapping[str, Any]],
    aggregate: Mapping[str, Any],
    config: Mapping[str, Any],
) -> None:
    links = "".join(
        f"<li><a href='{html.escape(case['href'])}'>"
        f"{html.escape(case['case_id'])}</a> · {case['n_records']} records</li>"
        for case in cases
    )
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>V4.4 intrinsic velocity atlas</title>
<link rel="stylesheet" href="assets/atlas.css">
</head><body><main>
<h1>V4.4 intrinsic velocity atlas</h1>
<p>{html.escape(config["no_inference_statement"])}</p>
<p><strong>{aggregate["n_rows"]} rows · {aggregate["n_pairs"]} pairs ·
{aggregate["n_ik_requests"]} IK requests · {len(cases)} cases.</strong></p>
<nav>
<a href="aggregate.json">aggregate</a>
<a href="validation.json">validation</a>
<a href="manifest.json">manifest</a>
</nav>
<h2>Cases</h2>
<ul>{links}</ul>
</main></body></html>
"""
    (root / "index.html").write_text(page, encoding="utf-8")


__all__ = [
    "write_case_figures",
    "write_case_package",
    "write_index_html",
    "write_local_assets",
]
