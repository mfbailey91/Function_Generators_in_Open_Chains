"""V4.3 intrinsic static-wrench HTML atlas (V4-306) and methods packet (V4-307).

Browser code displays stored scientific values. It does not evaluate
geometry, recompute ranks, or invent force capacities.
"""

from __future__ import annotations

import gzip
import html
import json
import math
import shutil
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from inequality_mechanisms.audits import v4_artifact_guard as _v4_guard
from inequality_mechanisms.audits.v4_3_artifact import (
    MANIFEST_INVENTORY_RULE,
    MANIFEST_NAME,
    aggregate_vertex_diagnostics,
    case_wrench_rel,
    files_digest,
    inventory_package_files,
    schema_documentation,
    snapshot_predecessor_integrity,
    strict_json_dumps,
)
from inequality_mechanisms.audits.v4_artifact_guard import (
    CANONICAL_REPO_ROOT,
    V4_3_ALLOWED_PACKAGE,
    assert_v4_3_output_allowed,
    begin_v4_3_write,
)
from inequality_mechanisms.experiments.registry import capture_environment
from inequality_mechanisms.experiments.span_cases import (
    BIO_SPANS_DEG,
    CORE_SPANS_DEG,
    case_id_for,
)
from inequality_mechanisms.experiments.v4.intrinsic_static_wrench import (
    ConsumedSourceRow,
    PairedPhysicalSample,
    assert_v4_2b_source_lock,
    consume_v4_2b_corpus,
    load_v4_2b_cases,
    resolve_smoke_selection,
    smoke_selection_record,
)
from inequality_mechanisms.experiments.v4.intrinsic_static_wrench_config import (
    CASE_SUMMARY_SCHEMA_VERSION,
    DEFAULT_CONFIG_REL,
    FORCE_UNITS,
    FROZEN_MECHANISM_IDS,
    FROZEN_V4_2B_N_GEOMETRY_ROWS,
    MANIFEST_SCHEMA_VERSION,
    NO_INFERENCE_STATEMENT,
    PACKAGE_SCHEMA_VERSION,
    TORQUE_UNITS,
    load_intrinsic_static_wrench_config,
)
from inequality_mechanisms.experiments.v4.intrinsic_static_wrench_fields import (
    INHERITED_TOLERANCE_POLICY,
    NAMED_DIRECTIONS,
    PRIMARY_MECHANISM_PAIR,
    analytic_fixture_expectations,
    classify_directional_field,
    classify_scalar_field,
    paired_comparison_summary,
    regular_unit_arm_fixture,
    retained_force_record,
    status_mask,
    stretched_unit_arm_fixture,
    support_along,
)
from inequality_mechanisms.metrics.static_wrench import WrenchStateStatus

POLYGON_STRIDE = 8
METHOD_NOTE_REL = (
    Path("docs")
    / "software"
    / "architecture"
    / "notes"
    / "STATIC_WRENCH_KINEMATIC_GEOMETRY_METHOD.md"
)
BIO_TRACE_REL = (
    Path("docs")
    / "research"
    / "literature"
    / "BIOLOGICAL_JOINT_RANGE_REFERENCE_TRACE.md"
)
V4_2B_SOURCE_REL = (
    Path("results") / "v4_review" / "v4_2b_span_controlled_corrective_closeout"
)

_HTML_CSS = """
body {
  font-family: Georgia, "Times New Roman", serif;
  margin: 1.2rem; color: #222; max-width: 1100px;
}
table {
  border-collapse: collapse; width: 100%;
  margin: 0.6rem 0 1.2rem; font-size: 0.92rem;
}
th, td { border: 1px solid #bbb; padding: 0.35rem 0.45rem; vertical-align: top; }
th { background: #f3f3f3; }
img { max-width: 100%; height: auto; border: 1px solid #ddd; margin: 0.25rem 0; }
.muted { color: #555; }
code { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 0.85rem; }
.banner { background: #f7f1e8; border: 1px solid #d9c7a3; padding: 0.7rem 0.9rem; }
.stress { font-weight: bold; }
.cell-panels { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.8rem; }
.cell-panels svg { width: 100%; min-width: 0; }
.cell-panels svg text { font-size: 9px; }
.cell-panels h3 { overflow-wrap: anywhere; font-size: 0.95rem; }
.cell-panels p { font-size: 0.85rem; }
.warning { color: #8d2c12; font-weight: bold; }
pre { overflow: auto; max-height: 34rem; background: #f4f5f6; padding: 0.8rem; }
select { max-width: 100%; padding: 0.35rem; }
.panel { display: grid; grid-template-columns: 1fr 1fr; gap: 0.8rem; }
@media (max-width: 800px) { .panel, .cell-panels { grid-template-columns: 1fr; } }
"""

_ATLAS_JS = r"""
(function () {
  "use strict";
  const dataElement = document.getElementById("atlas-data");
  const viewSelect = document.getElementById("view-select");
  const cellSelect = document.getElementById("cell-select");
  if (!dataElement || !viewSelect || !cellSelect) return;
  const data = JSON.parse(dataElement.textContent);
  const image = document.getElementById("main-image");
  const caption = document.getElementById("main-caption");
  const readout = document.getElementById("cell-readout");
  const panels = document.getElementById("selected-polygons");
  const comparison = document.getElementById("cell-comparison");
  const identity = document.getElementById("selected-identity");
  const svgNS = "http://www.w3.org/2000/svg";

  function appendText(parent, tag, text, className) {
    const node = document.createElement(tag);
    node.textContent = text;
    if (className) node.className = className;
    parent.appendChild(node);
    return node;
  }
  function svgNode(parent, tag, attrs, text) {
    const node = document.createElementNS(svgNS, tag);
    Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
    if (text !== undefined) node.textContent = text;
    parent.appendChild(node);
    return node;
  }
  function numberText(value) {
    return value === null || value === undefined
      ? "unavailable" : Number(value).toPrecision(6);
  }
  function selectedFieldKey() {
    const diagnosticFields = {
      positive_x_diagnostic: "positive_x",
      positive_y_diagnostic: "positive_y",
      radial_diagnostic: "radial",
      tangential_diagnostic: "tangential"
    };
    return diagnosticFields[viewSelect.value] || viewSelect.value;
  }
  function displayedField(row, fieldKey) {
    const direction = row.directional_fields &&
      row.directional_fields[fieldKey];
    return direction || row.isotropic_radius_field;
  }
  function drawStoredPolygon(parent, row, bounds) {
    const svg = document.createElementNS(svgNS, "svg");
    svg.setAttribute("viewBox", "0 0 330 320");
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label",
      row.mechanism_id + " stored force polygon on common axes");
    parent.appendChild(svg);
    const [lo, hi] = bounds.xlim;
    // Only a display-coordinate transform of stored vertices; no scientific
    // map, rank, capacity, direction, or comparison is evaluated in the browser.
    const px = value => 50 + 240 * (value - lo) / (hi - lo);
    const py = value => 20 + 240 * (hi - value) / (hi - lo);
    svgNode(svg, "rect",
      {x:50, y:20, width:240, height:240, fill:"white", stroke:"#888"});
    svgNode(svg, "line", {x1:px(0), y1:20, x2:px(0), y2:260, stroke:"#bbb"});
    svgNode(svg, "line", {x1:50, y1:py(0), x2:290, y2:py(0), stroke:"#bbb"});
    svgNode(svg, "text", {x:50, y:278, "text-anchor":"start"}, numberText(lo));
    svgNode(svg, "text", {x:290, y:278, "text-anchor":"end"}, numberText(hi));
    svgNode(svg, "text", {x:45, y:25, "text-anchor":"end"}, numberText(hi));
    svgNode(svg, "text", {x:45, y:260, "text-anchor":"end"}, numberText(lo));
    svgNode(svg, "text", {x:170, y:303, "text-anchor":"middle"},
      "Fx (normalized torque/length)");
    svgNode(svg, "text",
      {x:9, y:150, transform:"rotate(-90 9 150)", "text-anchor":"middle"}, "Fy");
    if (row.vertices && row.vertices.length) {
      svgNode(svg, "polygon", {
        points: row.vertices.map(vertex =>
          px(vertex[0]) + "," + py(vertex[1])).join(" "),
        fill:"#1d4f9122", stroke:"#1d4f91", "stroke-width":1.5
      });
    } else {
      svgNode(svg, "text", {x:170, y:135, "text-anchor":"middle"}, "No closed polygon");
      svgNode(svg, "text", {x:170, y:155, "text-anchor":"middle"}, row.status);
    }
  }
  function renderCell() {
    const cell = data.cells[cellSelect.value];
    if (!cell) return;
    const selectedField = selectedFieldKey();
    identity.textContent = "Grid (" + cell.grid_index.join(", ") + ") · " +
      cell.q_sample_id;
    if (viewSelect.value === "true_scale_detail" && caption) {
      caption.textContent = "Selected-cell true-scale polygons below: " +
        cell.q_sample_id + ". All three panels share the stored force bounds.";
    }
    panels.replaceChildren();
    Object.values(cell.arms).forEach(row => {
      const panel = document.createElement("section");
      panels.appendChild(panel);
      appendText(panel, "h3", row.mechanism_id);
      appendText(panel, "p", "Whole-set status: " + row.status, "status-label");
      const field = displayedField(row, selectedField);
      const fieldName = row.directional_fields &&
        row.directional_fields[selectedField]
        ? selectedField + " ray" : "isotropic radius";
      appendText(panel, "p",
        fieldName + ": " + numberText(field.value) + " · " + field.status);
      appendText(panel, "p",
        "Unit actuator-effort box: " + JSON.stringify(row.torque_limits));
      if (row.status !== "regular") {
        appendText(panel, "p",
          "Diagnostic state; excluded from regular-only primary comparisons.",
          "warning");
      }
      if (row.low_gain_warning) {
        appendText(panel, "p",
          "Low-gain warning: inspect source rank reports.", "warning");
      }
      if (row.vertex_feasibility && !row.vertex_feasibility.ok) {
        appendText(panel, "p",
          "Unit-box corner residual exceeds tolerance; inspect diagnostics.",
          "warning");
      }
      drawStoredPolygon(panel, row, cell.force_bounds);
    });
    const fieldKey = cell.comparisons[selectedField]
      ? selectedField : "isotropic_radius";
    comparison.textContent = "Stored paired comparison (" + fieldKey + "):\n" +
      JSON.stringify(cell.comparisons[fieldKey] || null, null, 2);
    readout.textContent = JSON.stringify(
      {selected_view:viewSelect.value, ...cell}, null, 2);
  }
  function renderView() {
    const asset = data.assets[viewSelect.value];
    if (asset && image) {
      image.hidden = viewSelect.value === "true_scale_detail";
      image.src = asset.src;
      image.alt = asset.alt;
      if (caption) caption.textContent = asset.caption;
    }
    renderCell();
  }
  viewSelect.addEventListener("change", renderView);
  cellSelect.addEventListener("change", renderCell);
  renderView();
})();
"""


def _require_matplotlib() -> Any:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: Any) -> None:
    _write_text(path, strict_json_dumps(payload, indent=2) + "\n")


def plottable_records(
    items: Sequence[ConsumedSourceRow],
) -> list[dict[str, Any]]:
    """Use complete scientific records for retention and display alike.

    Plotting must never strip H-representations, direction vectors, or the
    inherited source rank reports from the canonical machine-readable bank.
    """
    return [retained_force_record(item) for item in items]


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
        if key == "isotropic_radius":
            value = row.get("isotropic_radius")
        else:
            caps = row.get("directional_capacity") or {}
            value = caps.get(key)
            field = (row.get("directional_fields") or {}).get(key) or {}
            if field.get("status") != "finite":
                value = None
        if value is None or not math.isfinite(float(value)):
            continue
        i, j = row["grid_index"]
        grid[int(i), int(j)] = float(value)
    return grid


def _index_mesh(shape: tuple[int, int] = (33, 33)) -> tuple[np.ndarray, np.ndarray]:
    """Finite grid-index mesh for heatmaps (works for sparse smoke subsets)."""
    ii, jj = np.meshgrid(
        np.arange(shape[0], dtype=np.float64),
        np.arange(shape[1], dtype=np.float64),
        indexing="ij",
    )
    return ii, jj


def write_paired_heatmap(
    path: Path,
    *,
    qq1: np.ndarray,
    qq2: np.ndarray,
    grids: Mapping[str, np.ndarray],
    title: str,
    vmin: float,
    vmax: float,
    xlabel: str = "mounted-Q grid index $i$",
    ylabel: str = "mounted-Q grid index $j$",
) -> None:
    """Write paired four-bar/gearbox heatmaps with shared colour limits."""
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
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
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
    """Write the separate identity-on-shared-Q reference panel."""
    plt = _require_matplotlib()
    fig, ax = plt.subplots(1, 1, figsize=(4.2, 3.6))
    mesh = ax.pcolormesh(
        qq1,
        qq2,
        grid,
        shading="nearest",
        cmap="viridis",
        vmin=vmin,
        vmax=vmax,
    )
    ax.set_title("identity_on_shared_q (reference)")
    ax.set_xlabel("mounted-Q grid index $i$")
    ax.set_ylabel("mounted-Q grid index $j$")
    ax.set_aspect("equal")
    fig.colorbar(mesh, ax=ax, fraction=0.046, pad=0.04)
    fig.suptitle(title)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110)
    plt.close(fig)


def normalized_polygon_glyph(vertices: Any, *, radius: float) -> np.ndarray:
    """Normalize each polygon independently; radius is a display length."""
    polygon = np.asarray(vertices, dtype=np.float64)
    if polygon.ndim != 2 or polygon.shape[1] != 2 or not np.isfinite(polygon).all():
        raise ValueError("glyph vertices must be a finite N by 2 array")
    extent = float(np.max(np.linalg.norm(polygon, axis=1))) if polygon.size else 0.0
    if extent <= 0.0:
        raise ValueError("a polygon glyph needs a positive radius")
    return polygon * (float(radius) / extent)


def common_force_bounds(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Stored display bounds shared by every selected force panel.

    Symmetric square axes preserve the same force-to-pixel scale in both
    directions and across all panels. This changes display bounds only.
    """
    extent = 0.0
    for row in records:
        vertices = row.get("vertices")
        if vertices:
            values = np.asarray(vertices, dtype=np.float64)
            if np.isfinite(values).all():
                extent = max(extent, float(np.max(np.abs(values))))
    limit = 1.1 * extent if extent > 0.0 else 1.0
    return {
        "xlim": [-limit, limit],
        "ylim": [-limit, limit],
        "policy": "symmetric_square_union_10_percent_margin",
        "force_units": FORCE_UNITS,
    }


def finite_color_limits(values: np.ndarray) -> list[float]:
    """Full finite range, with deterministic padding for a constant field."""
    finite = values[np.isfinite(values)]
    if not finite.size:
        return [0.0, 1.0]
    low, high = float(np.min(finite)), float(np.max(finite))
    if high <= low:
        high = low + max(abs(low) * 1e-12, 1e-12)
    return [low, high]


def write_polygon_glyphs(
    path: Path,
    *,
    records: Sequence[Mapping[str, Any]],
    stride: int = POLYGON_STRIDE,
    title: str = "Shape-normalized force polygons (not magnitude)",
) -> None:
    """Sparse shape-normalized polygon glyphs on mounted Q."""
    plt = _require_matplotlib()
    fig, axes = plt.subplots(
        1, 2, figsize=(8.4, 3.6), squeeze=False, sharex=True, sharey=True
    )
    qs = [
        np.asarray(row["q"], dtype=np.float64)
        for row in records
        if row.get("q") is not None
    ]
    if qs:
        q_arr = np.vstack(qs)
        spans = np.ptp(q_arr, axis=0)
        indices = np.asarray([row["grid_index"] for row in records], dtype=float)
        index_spans = np.ptp(indices, axis=0)
        spacings = [
            float(spans[k]) * stride / float(index_spans[k])
            for k in range(2)
            if spans[k] > 0 and index_spans[k] > 0
        ]
        glyph = 0.4 * min(spacings) if spacings else 0.1
    else:
        glyph = 0.1
    q_limits = (
        [
            [float(np.min(q_arr[:, k])) - glyph, float(np.max(q_arr[:, k])) + glyph]
            for k in range(2)
        ]
        if qs
        else [[-1.0, 1.0], [-1.0, 1.0]]
    )
    for ax, mech in zip(axes[0], PRIMARY_MECHANISM_PAIR, strict=True):
        for row in records:
            if row["mechanism_id"] != mech:
                continue
            i, j = row["grid_index"]
            if int(i) % stride != 0 or int(j) % stride != 0:
                continue
            q = row.get("q")
            if q is None:
                continue
            q_arr = np.asarray(q, dtype=np.float64)
            verts = row.get("vertices")
            if row.get("status") == WrenchStateStatus.REGULAR.value and verts:
                poly = q_arr + normalized_polygon_glyph(verts, radius=glyph)
                closed = np.vstack([poly, poly[0]])
                ax.plot(closed[:, 0], closed[:, 1], color="#1d4f91", lw=0.8)
            else:
                ax.plot(q_arr[0], q_arr[1], marker="x", color="#a31f34", ms=5)
        ax.set_title(mech)
        ax.set_xlabel("mounted $q_1$ (rad)")
        ax.set_ylabel("mounted $q_2$ (rad)")
        ax.set_aspect("equal")
        ax.set_xlim(q_limits[0])
        ax.set_ylim(q_limits[1])
    fig.suptitle(title)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110)
    plt.close(fig)


def write_true_scale_detail(
    path: Path,
    *,
    records: Sequence[Mapping[str, Any]],
    q_sample_id: str,
    title: str,
) -> dict[str, Any] | None:
    """True-scale polygon detail for one shared physical sample."""
    chosen = [
        row
        for row in records
        if row["q_sample_id"] == q_sample_id
        and row["mechanism_id"] in PRIMARY_MECHANISM_PAIR
    ]
    if not chosen:
        return None
    plt = _require_matplotlib()
    fig, axes = plt.subplots(
        1, 2, figsize=(8.4, 3.6), squeeze=False, sharex=True, sharey=True
    )
    bounds = common_force_bounds(chosen)
    detail: dict[str, Any] = {
        "q_sample_id": q_sample_id,
        "arms": {},
        "force_bounds": bounds,
    }
    for ax, mech in zip(axes[0], PRIMARY_MECHANISM_PAIR, strict=True):
        row = next((r for r in chosen if r["mechanism_id"] == mech), None)
        ax.set_title(mech)
        ax.set_xlabel(r"$F_x$ (normalized torque/length)")
        ax.set_ylabel(r"$F_y$ (normalized torque/length)")
        ax.set_aspect("equal")
        ax.set_xlim(bounds["xlim"])
        ax.set_ylim(bounds["ylim"])
        ax.axhline(0.0, color="#999", lw=0.6)
        ax.axvline(0.0, color="#999", lw=0.6)
        if row is None or not row.get("vertices"):
            ax.text(
                0.5,
                0.5,
                "no closed polygon",
                ha="center",
                transform=ax.transAxes,
            )
            detail["arms"][mech] = None if row is None else dict(row)
            continue
        verts = np.asarray(row["vertices"], dtype=np.float64)
        closed = np.vstack([verts, verts[0]])
        ax.plot(closed[:, 0], closed[:, 1], color="#1d4f91", lw=1.4)
        ax.fill(closed[:, 0], closed[:, 1], color="#1d4f91", alpha=0.12)
        detail["arms"][mech] = dict(row)
    fig.suptitle(title)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return detail


def comparison_grids(
    comparisons: Sequence[Mapping[str, Any]],
    *,
    shape: tuple[int, int] = (33, 33),
) -> dict[str, np.ndarray]:
    """Project stored eligible comparisons; unavailable cells stay masked."""
    grids = {name: np.full(shape, np.nan) for name in ("delta", "ratio")}
    for cell in comparisons:
        if not cell["eligible"]:
            continue
        i, j = (int(v) for v in cell["grid_index"])
        for name, grid in grids.items():
            field = cell[name]
            if field["status"] == "finite" and field["value"] is not None:
                grid[i, j] = float(field["value"])
    return grids


def write_comparison_figures(
    case_dir: Path,
    *,
    records: Sequence[Mapping[str, Any]],
    comparisons: Sequence[Mapping[str, Any]],
    shape: tuple[int, int] = (33, 33),
) -> dict[str, Any]:
    """Render retained paired deltas/ratios and categorical whole-set status."""
    from matplotlib.colors import BoundaryNorm, ListedColormap

    plt = _require_matplotlib()
    qq1, qq2 = _index_mesh(shape)
    fig_dir = case_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    assets: dict[str, Any] = {}
    limits: dict[str, list[float]] = {}
    for key, grid in comparison_grids(comparisons, shape=shape).items():
        bounds = finite_color_limits(grid)
        if key == "delta":
            magnitude = max(abs(bounds[0]), abs(bounds[1]), 1e-12)
            bounds = [-magnitude, magnitude]
        limits[key] = bounds
        fig, ax = plt.subplots(figsize=(5.2, 4.0))
        mesh = ax.pcolormesh(
            qq1,
            qq2,
            grid,
            shading="nearest",
            cmap="coolwarm" if key == "delta" else "viridis",
            vmin=bounds[0],
            vmax=bounds[1],
        )
        relation = "fourbar − gearbox" if key == "delta" else "fourbar / gearbox"
        ax.set_title(f"Isotropic radius: {relation}")
        ax.set_xlabel("mounted-Q grid index $i$")
        ax.set_ylabel("mounted-Q grid index $j$")
        ax.set_aspect("equal")
        fig.colorbar(mesh, ax=ax, label=FORCE_UNITS if key == "delta" else "ratio")
        fig.tight_layout()
        fig.savefig(fig_dir / f"{key}.png", dpi=110)
        plt.close(fig)
        assets[key] = {
            "src": f"figures/{key}.png",
            "alt": f"paired isotropic {key}",
            "caption": (
                f"Stored paired isotropic {key} ({relation}); only regular finite "
                "eligible pairs are shown. Unavailable pairs remain blank and "
                "their exclusion reasons are available in the cell inspector."
            ),
        }

    labels = [status.value for status in WrenchStateStatus] + ["source_failure"]
    colors = ["#287c8e", "#f2a541", "#bc5090", "#7a5195", "#c1121f", "#7b8b8e", "#222"]
    cmap = ListedColormap(colors)
    norm = BoundaryNorm(np.arange(len(labels) + 1) - 0.5, len(labels))
    fig, axes = plt.subplots(1, 3, figsize=(11.8, 4.0), squeeze=False)
    for ax, mechanism in zip(axes[0], FROZEN_MECHANISM_IDS, strict=True):
        grid = np.full(shape, np.nan)
        for row in records:
            if row["mechanism_id"] == mechanism:
                i, j = (int(v) for v in row["grid_index"])
                grid[i, j] = labels.index(str(row["status"]))
        mesh = ax.pcolormesh(qq1, qq2, grid, shading="nearest", cmap=cmap, norm=norm)
        ax.set_title(mechanism, fontsize=9)
        ax.set_xlabel("mounted-Q grid index $i$")
        ax.set_ylabel("mounted-Q grid index $j$")
        ax.set_aspect("equal")
    fig.subplots_adjust(right=0.79, wspace=0.35)
    legend_ax = fig.add_axes((0.82, 0.18, 0.02, 0.65))
    colorbar = fig.colorbar(mesh, cax=legend_ax, ticks=np.arange(len(labels)))
    colorbar.ax.set_yticklabels(
        [label.replace("_", "\n") for label in labels], fontsize=7
    )
    fig.suptitle("Whole-set status (separate from per-direction field status)")
    fig.savefig(fig_dir / "status.png", dpi=110)
    plt.close(fig)
    assets["status"] = {
        "src": "figures/status.png",
        "alt": "whole-set status per arm",
        "caption": (
            "Categorical stored whole-set status for all three arms. A set can "
            "be unbounded while some directional capacities remain finite; "
            "inspect their separate field statuses below. Blank cells were not sampled."
        ),
    }
    return {"assets": assets, "color_limits": limits, "status_legend": labels}


def write_case_figures(
    case_dir: Path,
    records: Sequence[Mapping[str, Any]],
    *,
    shape: tuple[int, int] = (33, 33),
) -> dict[str, Any]:
    """Write scalar, directional, polygon, and detail figures for one case."""
    fig_dir = case_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    # Index mesh stays finite for sparse smoke subsets; cell JSON retains
    # exact mounted-Q coordinates for each sample.
    qq1, qq2 = _index_mesh(shape)
    assets: dict[str, Any] = {}

    iso_grids = {
        mech: _field_grid(
            records, mechanism_id=mech, key="isotropic_radius", shape=shape
        )
        for mech in FROZEN_MECHANISM_IDS
    }
    paired_vals = np.concatenate(
        [
            iso_grids[PRIMARY_MECHANISM_PAIR[0]][
                np.isfinite(iso_grids[PRIMARY_MECHANISM_PAIR[0]])
            ],
            iso_grids[PRIMARY_MECHANISM_PAIR[1]][
                np.isfinite(iso_grids[PRIMARY_MECHANISM_PAIR[1]])
            ],
        ]
    )
    vmin, vmax = finite_color_limits(paired_vals)
    identity_limits = finite_color_limits(iso_grids["identity_on_shared_q"])
    color_limits = {
        "isotropic_radius": [vmin, vmax],
        "identity_isotropic_radius": identity_limits,
    }

    write_paired_heatmap(
        fig_dir / "scalar.png",
        qq1=qq1,
        qq2=qq2,
        grids={
            PRIMARY_MECHANISM_PAIR[0]: iso_grids[PRIMARY_MECHANISM_PAIR[0]],
            PRIMARY_MECHANISM_PAIR[1]: iso_grids[PRIMARY_MECHANISM_PAIR[1]],
        },
        title="Primary isotropic radius (regular finite only)",
        vmin=vmin,
        vmax=vmax,
    )
    write_identity_heatmap(
        fig_dir / "identity_scalar.png",
        qq1=qq1,
        qq2=qq2,
        grid=iso_grids["identity_on_shared_q"],
        title="Identity reference isotropic radius (separate scale)",
        vmin=identity_limits[0],
        vmax=identity_limits[1],
    )
    assets["scalar"] = {
        "src": "figures/scalar.png",
        "alt": "isotropic radius",
        "caption": (
            "Primary view: isotropic radius on the retained mounted-Q grid "
            "(axes show grid indices; cell JSON stores exact Q). "
            f"Paired colour limits [{vmin:.6g}, {vmax:.6g}]. "
            f"Force units: {FORCE_UNITS}."
        ),
    }
    assets["identity_scalar"] = {
        "src": "figures/identity_scalar.png",
        "alt": "identity isotropic radius",
        "caption": (
            "Identity-on-shared-Q reference uses its own full finite range "
            f"[{identity_limits[0]:.6g}, {identity_limits[1]:.6g}], "
            "with no clipped values. Compare numeric values using the inspector; "
            "this scale differs from the primary paired scale."
        ),
    }

    for direction in NAMED_DIRECTIONS:
        primary_grids = {
            mech: _field_grid(
                records,
                mechanism_id=mech,
                key=direction,
                shape=shape,
                primary_only=True,
            )
            for mech in PRIMARY_MECHANISM_PAIR
        }
        primary_vals = np.concatenate(
            [
                primary_grids[m][np.isfinite(primary_grids[m])]
                for m in PRIMARY_MECHANISM_PAIR
            ]
        )
        d_vmin, d_vmax = finite_color_limits(primary_vals)
        color_limits[direction] = [d_vmin, d_vmax]
        write_paired_heatmap(
            fig_dir / f"{direction}.png",
            qq1=qq1,
            qq2=qq2,
            grids=primary_grids,
            title=f"Ray capacity: {direction}",
            vmin=d_vmin,
            vmax=d_vmax,
        )
        assets[direction] = {
            "src": f"figures/{direction}.png",
            "alt": direction,
            "caption": (
                f"Primary directional ray capacity ({direction}) on regular-finite "
                "cells only, with shared colour limits from those values. "
                "Undefined/unbounded and near-singular cells are masked here."
            ),
        }
        diagnostic_grids = {
            mech: _field_grid(
                records,
                mechanism_id=mech,
                key=direction,
                shape=shape,
                primary_only=False,
            )
            for mech in PRIMARY_MECHANISM_PAIR
        }
        diagnostic_vals = np.concatenate(
            [
                diagnostic_grids[m][np.isfinite(diagnostic_grids[m])]
                for m in PRIMARY_MECHANISM_PAIR
            ]
        )
        diag_vmin, diag_vmax = finite_color_limits(diagnostic_vals)
        diagnostic_name = f"{direction}_diagnostic"
        write_paired_heatmap(
            fig_dir / f"{diagnostic_name}.png",
            qq1=qq1,
            qq2=qq2,
            grids=diagnostic_grids,
            title=f"Diagnostic full-finite ray capacity: {direction}",
            vmin=diag_vmin,
            vmax=diag_vmax,
        )
        assets[diagnostic_name] = {
            "src": f"figures/{diagnostic_name}.png",
            "alt": f"{direction} diagnostic",
            "caption": (
                f"Diagnostic view for {direction}: all finite ray capacities "
                "including near-singular cells. Scale may be dominated by "
                "ill-conditioned outliers; use the primary figure for comparison."
            ),
        }

    write_polygon_glyphs(fig_dir / "polygons.png", records=records)
    assets["polygons"] = {
        "src": "figures/polygons.png",
        "alt": "shape-normalized polygons",
        "caption": (
            "Shape-normalized polygon glyphs only. Glyph size is not force magnitude."
        ),
    }

    # Select the regular sample nearest the grid center deterministically.
    detail_rows = sorted(
        (
            row
            for row in records
            if row["mechanism_id"] == "fourbar"
            and row.get("primary_eligible")
            and row.get("vertices")
        ),
        key=lambda row: (
            sum(abs(int(v) - 16) for v in row["grid_index"]),
            tuple(row["grid_index"]),
        ),
    )
    detail_id = str(detail_rows[0]["q_sample_id"]) if detail_rows else None
    detail = None
    if detail_id is not None:
        detail = write_true_scale_detail(
            fig_dir / "true_scale_detail.png",
            records=records,
            q_sample_id=detail_id,
            title=f"True-scale force polygons at {detail_id}",
        )
        assets["true_scale_detail"] = {
            "src": "figures/true_scale_detail.png",
            "alt": "true-scale detail",
            "caption": (
                "True-scale force polygons with common force axes. "
                f"Selected q_sample_id={detail_id}."
            ),
        }
    return {
        "assets": assets,
        "color_limits": color_limits,
        "color_scale_policy": {
            "primary": "full_finite_paired_range",
            "identity": "separate_full_finite_reference_range",
            "display_clipped_values": 0,
        },
        "true_scale_detail": detail,
    }


def write_local_assets(root: Path) -> None:
    """Write shared offline CSS/JS assets."""
    assets = root / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    _write_text(assets / "atlas.css", _HTML_CSS)
    _write_text(assets / "atlas.js", _ATLAS_JS)


def write_methods_and_pointers(root: Path) -> None:
    """Write V4-307 methods, biological pointer, and package README."""
    repo = CANONICAL_REPO_ROOT
    method_src = repo / METHOD_NOTE_REL
    bio_src = repo / BIO_TRACE_REL
    methods = f"""# V4.3 Intrinsic Gravity-Free Static Wrench — Methods

This package evaluates the accepted ideal static-wrench model on frozen
corrected V4.2B mounted-Q geometry snapshots. It does not recompute
Jacobians, resynthesize branches, or retune rank thresholds.

## Scientific contract

Normalized actuator torque box \\(\\bar\\tau_u = (1, 1)\\) with units
`{TORQUE_UNITS}`. Force values use `{FORCE_UNITS}`. Gravity, payload,
dynamics, friction, compliance, structural limits, and contact are absent.

This **unit actuator-effort box** fixes a common scale for the theoretical
comparison. It is not a real motor rating. Scaling both effort bounds by the
same positive factor scales every force polygon and finite ray capacity by
that factor; paired ratios remain unchanged. The independent box chooses an
L-infinity effort budget. An L2 budget would define a different comparison
and would produce ellipsoidal force sets at nonsingular configurations.

The unit-box corner residual checks that a computed polygon vertex maps back
to an effort-box corner under virtual work. It is a numerical consistency
check, not a prediction of physical actuator saturation. Near-singular
diagnostic residuals remain visible and do not change inherited rank policy.

Virtual work uses the stored maps

\\[
J_{{xu}} = J_f J_g,\\qquad
\\tau_u = J_{{xu}}^\\mathsf T F,\\qquad
\\mathcal F(q) = \\{{ F :
-\\bar\\tau_u \\le J_{{xu}}^\\mathsf T F \\le \\bar\\tau_u \\}}.
\\]

`directional_capacity` is **ray capacity** along a unit direction \\(d\\),
not the support function. The isotropic radius \\(\\rho_{{\\mathrm{{iso}}}}\\)
is the largest origin-centered disk inside \\(\\mathcal F\\).

## Snapshot source and sampling

Canonical input: `{V4_2B_SOURCE_REL.as_posix()}` (mounted-coordinate V4.2B
closeout). Rows are restored through `parse_retained_atlas_row` and evaluated
with `static_wrench_from_snapshot`. Sampling measure: uniform mounted-Q grid
retained by V4.2B (33 × 33 per case). Summaries are descriptive over that
grid, not workspace-uniform or application-frequency estimates.

Primary heatmap cells require status `regular` and a finite isotropic radius.
Finite near-singular or singular diagnostics remain in detail records and are
masked from the primary view. An unbounded strip may still report finite
directional capacities along constrained axes.

## Inherited tolerances

```json
{json.dumps(INHERITED_TOLERANCE_POLICY, indent=2, sort_keys=True)}
```

## Authoritative method note

See also the accepted kinematic-geometry method contract copied from:

`{METHOD_NOTE_REL.as_posix()}`

Full upstream note begins:

> {
        method_src.read_text(encoding="utf-8").splitlines()[0]
        if method_src.is_file()
        else "STATIC_WRENCH_KINEMATIC_GEOMETRY_METHOD.md"
    }

## Nonclaims

- Not an application load rating or structural strength certificate.
- Not a general ranking of mechanisms.
- Biological span memberships motivate experimental ranges only; they do not
  claim biological force capability.
- Historical V4.2 / V4.2A / V3.6F packages are provenance links only.
"""
    _write_text(root / "methods.md", methods)

    pointer = f"""# Biological reference pointer (V4.3)

V4.3 does **not** introduce new biological constants or capability claims.

Span memberships such as biological-refinement cells are range-inspired
experimental factors from the existing literature trace:

`{BIO_TRACE_REL.as_posix()}`

Interpret those spans as corpus design choices for planar-2R experiments.
Do not infer human joint force capacity, anatomical equivalence, or medical
guidance from normalized torque-box force maps in this package.

The full trace is retained next to this pointer as
`biological_reference_trace.md` for offline reading.
"""
    _write_text(root / "biological_reference_pointer.md", pointer)
    if bio_src.is_file():
        shutil.copyfile(bio_src, root / "biological_reference_trace.md")
    if method_src.is_file():
        shutil.copyfile(method_src, root / "STATIC_WRENCH_KINEMATIC_GEOMETRY_METHOD.md")

    readme = f"""# V4.3 Intrinsic Static Wrench Atlas

{NO_INFERENCE_STATEMENT}

- **Source:** frozen V4.2B mounted-Q snapshots under `{V4_2B_SOURCE_REL.as_posix()}`
- **Primary view:** isotropic radius on mounted Q (regular finite only)
- **Units:** torque `{TORQUE_UNITS}`; force `{FORCE_UNITS}`
- **Controls:** paired four-bar vs span-matched gearbox;
  identity-on-shared-Q is a reference, not a ranked competitor
- **Stress-only:** 175° cases remain boundary-stress-only and are labeled
- **Docs:** [methods.md](methods.md),
  [biological_reference_pointer.md](biological_reference_pointer.md)

Historical packages (V4.2, V4.2A, V3.6F) are not the snapshot source.
"""
    _write_text(root / "README.md", readme)


def inspector_payload(
    records: Sequence[Mapping[str, Any]],
    *,
    comparisons: Mapping[str, Mapping[str, Any]],
    assets: Mapping[str, Any],
    selected_q_sample_id: str | None = None,
) -> dict[str, Any]:
    """Build offline cell records and shared display bounds in Python.

    The browser selects these packets and projects stored polygon vertices
    into pixels. Scientific values and paired comparisons are never derived
    in JavaScript.
    """
    grouped: dict[tuple[int, int], list[Mapping[str, Any]]] = defaultdict(list)
    for row in records:
        i, j = row["grid_index"]
        grouped[(int(i), int(j))].append(row)
    comparison_lookup = {
        name: {tuple(cell["grid_index"]): cell for cell in packet["comparisons"]}
        for name, packet in comparisons.items()
    }
    cells: dict[str, Any] = {}
    selected_key = None
    for grid, rows in sorted(grouped.items()):
        key = ",".join(str(v) for v in grid)
        sample_id = str(rows[0]["q_sample_id"])
        cells[key] = {
            "case_id": rows[0]["case_id"],
            "q_sample_id": sample_id,
            "grid_index": list(grid),
            "arms": {str(row["mechanism_id"]): dict(row) for row in rows},
            "force_bounds": common_force_bounds(rows),
            "comparisons": {
                name: lookup.get(grid) for name, lookup in comparison_lookup.items()
            },
        }
        if sample_id == selected_q_sample_id:
            selected_key = key
    return {
        "assets": dict(assets),
        "cells": cells,
        "default_cell": selected_key or next(iter(cells), None),
    }


def _script_json(payload: Any) -> str:
    """Keep JSON inert even if a stored string contains an HTML script end tag."""
    return (
        strict_json_dumps(payload, indent=None)
        .replace("<", r"\u003c")
        .replace(">", r"\u003e")
        .replace("&", r"\u0026")
    )


def _case_html(
    *,
    case: Mapping[str, Any],
    assets: Mapping[str, Any],
    summary: Mapping[str, Any],
    inspector: Mapping[str, Any],
    stress_only: bool,
) -> str:
    case_id = html.escape(str(case["case_id"]))
    options = []
    for key, label in (
        ("scalar", "isotropic capacity (default)"),
        ("positive_x", "+x ray"),
        ("positive_y", "+y ray"),
        ("radial", "radial ray"),
        ("tangential", "tangential ray"),
        ("positive_x_diagnostic", "+x ray — full finite diagnostics"),
        ("positive_y_diagnostic", "+y ray — full finite diagnostics"),
        ("radial_diagnostic", "radial ray — full finite diagnostics"),
        ("tangential_diagnostic", "tangential ray — full finite diagnostics"),
        ("polygons", "shape-normalized polygons"),
        ("true_scale_detail", "selected-cell true-scale detail"),
        ("identity_scalar", "identity reference"),
        ("delta", "paired isotropic difference"),
        ("ratio", "paired isotropic ratio"),
        ("status", "whole-set status masks"),
    ):
        if key not in assets:
            continue
        options.append(
            f'<option value="{html.escape(key)}">{html.escape(label)}</option>'
        )
    stress = (
        '<p class="stress">Boundary-stress-only case (175° membership). '
        "Exclude from primary-certified-family aggregates.</p>"
        if stress_only
        else ""
    )
    exclusions = summary.get("comparison_exclusions") or {}
    cell_options = []
    for key, cell in inspector["cells"].items():
        selected = ' selected="selected"' if key == inspector["default_cell"] else ""
        label = f"Grid ({key}) · {cell['q_sample_id']}"
        cell_options.append(
            f'<option value="{html.escape(key)}"{selected}>'
            f"{html.escape(label)}</option>"
        )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>{case_id}</title>
<link rel="stylesheet" href="../../assets/atlas.css"/>
</head><body>
<p><a href="../../index.html">Index</a></p>
<h1>{case_id}</h1>
{stress}
<p class="muted">Mounted-Q axes · memberships
{html.escape(", ".join(case.get("memberships", [])))} ·
J1 {html.escape(str(case.get("j1_status")))} ·
J2 {html.escape(str(case.get("j2_status")))}</p>
<p>Force units: <code>{html.escape(FORCE_UNITS)}</code>.
Paired isotropic colour limits:
{html.escape(str(summary.get("color_limits", {}).get("isotropic_radius")))}.
Eligible paired comparisons:
{html.escape(str(summary.get("n_eligible_comparisons")))};
exclusions {html.escape(json.dumps(exclusions, sort_keys=True))}.</p>
<label>View <select id="view-select">{"".join(options)}</select></label>
<figure>
<img id="main-image"
 src="{html.escape(assets["scalar"]["src"])}"
 alt="isotropic radius"/>
<figcaption id="main-caption">
{html.escape(assets["scalar"]["caption"])}
</figcaption>
</figure>
<h2>Inspect a configuration</h2>
<p>Choose a mounted-Q grid cell to inspect all three arms at the same physical
configuration. Values, named directions, rank reports, and comparisons below
come from the retained records.</p>
<label>Grid cell <select id="cell-select">{"".join(cell_options)}</select></label>
<p id="selected-identity" aria-live="polite"></p>
<p class="muted">The unit actuator-effort box is a common normalization for this
theoretical comparison. It is not a motor specification or physical load rating.
Selected polygons use identical force axes across all three panels.</p>
<div id="selected-polygons" class="cell-panels"></div>
<h3>Selected paired comparison</h3>
<pre id="cell-comparison"></pre>
<details><summary>Stored Q/U/X, signed maps, effort box, H-representation,
direction vectors, rank reports, residuals, and source identities</summary>
<pre id="cell-readout"></pre></details>
<noscript>Enable JavaScript for the offline cell inspector, or read the linked
machine-readable samples and summary. Scientific calculations are performed
in Python.</noscript>
<p><a href="{html.escape(str(summary.get("samples_href") or "cells.json"))}">
samples</a> · <a href="summary.json">summary.json</a> ·
<a href="../../methods.md">methods.md</a></p>
<script id="atlas-data" type="application/json">{_script_json(inspector)}</script>
<script src="../../assets/atlas.js"></script>
</body></html>
"""


def _status_label(case: Mapping[str, Any], span_deg: float, which: str) -> str:
    key = "j1_status" if which == "j1" else "j2_status"
    status = str(case.get(key, ""))
    label = f"{int(round(span_deg))}° {status}"
    if status == "boundary_stress_only":
        return f'<strong class="stress">{html.escape(label)}</strong>'
    return html.escape(label)


def _matrix_table(
    *,
    title: str,
    spans: Sequence[float],
    cases_by_id: Mapping[str, Mapping[str, Any]],
) -> str:
    header_cells = []
    for span in spans:
        sample = next(
            (
                cases_by_id[case_id_for(j1, span)]
                for j1 in spans
                if case_id_for(j1, span) in cases_by_id
            ),
            {"j2_status": ""},
        )
        header_cells.append(f"<th>{_status_label(sample, span, 'j2')}</th>")
    rows = []
    for j1 in spans:
        sample_j1 = next(
            (
                cases_by_id[case_id_for(j1, j2)]
                for j2 in spans
                if case_id_for(j1, j2) in cases_by_id
            ),
            {"j1_status": ""},
        )
        cells = [f"<th>{_status_label(sample_j1, j1, 'j1')}</th>"]
        for j2 in spans:
            cid = case_id_for(j1, j2)
            if cid not in cases_by_id:
                cells.append('<td class="muted">n/a</td>')
                continue
            case = cases_by_id[cid]
            href = f"cases/{html.escape(cid)}/index.html"
            memberships = ", ".join(case.get("memberships", []))
            stress = (
                ' class="stress"'
                if "boundary_stress_only"
                in (case.get("j1_status"), case.get("j2_status"))
                else ""
            )
            cells.append(
                f'<td{stress}><a href="{href}">{html.escape(cid)}</a>'
                f'<div class="muted">{html.escape(memberships)}</div></td>'
            )
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return (
        f"<h2>{html.escape(title)}</h2>"
        "<table><thead><tr><th>J1 \\ J2</th>"
        f"{''.join(header_cells)}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def write_index_html(
    root: Path,
    *,
    cases: Sequence[Mapping[str, Any]],
    package_meta: Mapping[str, Any],
) -> None:
    """Write the scalar-first two-matrix index."""
    cases_by_id = {str(case["case_id"]): case for case in cases}
    dual_id = case_id_for(145.0, 145.0)
    dual = cases_by_id.get(dual_id, {})
    core = _matrix_table(
        title="Core span sweep (95°, 145°, 175°)",
        spans=CORE_SPANS_DEG,
        cases_by_id=cases_by_id,
    )
    bio = _matrix_table(
        title="Biological-range refinement (135°, 145°, 150°)",
        spans=BIO_SPANS_DEG,
        cases_by_id=cases_by_id,
    )
    thumbs = []
    for case in cases:
        cid = html.escape(str(case["case_id"]))
        img = html.escape(f"cases/{case['case_id']}/figures/scalar.png")
        href = html.escape(f"cases/{case['case_id']}/index.html")
        thumbs.append(
            f'<figure><a href="{href}"><img src="{img}" alt="{cid} scalar"/></a>'
            f"<figcaption>{cid}</figcaption></figure>"
        )
    body = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>V4.3 Intrinsic Static Wrench Atlas</title>
<link rel="stylesheet" href="assets/atlas.css"/>
</head><body>
<h1>V4.3 Intrinsic Static Wrench Atlas</h1>
<div class="banner">
<p><strong>{html.escape(NO_INFERENCE_STATEMENT)}</strong></p>
<p>Primary view: isotropic radius on <em>mounted</em> Q.
Paired four-bar / span-matched gearbox panels share colour limits.
Identity-on-shared-Q is a separate reference. Force units:
<code>{html.escape(FORCE_UNITS)}</code>.</p>
<p>Snapshot source:
<code>{html.escape(V4_2B_SOURCE_REL.as_posix())}</code>.
Historical V4.2 / V4.2A / V3.6F packages are provenance only.</p>
</div>
<p class="muted">Mode {html.escape(str(package_meta.get("mode")))} ·
cases {len(cases)} ·
records {html.escape(str(package_meta.get("n_records")))} ·
<a href="README.md">README</a> ·
<a href="methods.md">methods.md</a> ·
<a href="biological_reference_pointer.md">biological pointer</a> ·
<a href="smoke_selection.json">smoke_selection.json</a> ·
<a href="schema.json">schema.json</a></p>
<p>Shared display cell <code>{html.escape(dual_id)}</code> has memberships
{html.escape(", ".join(dual.get("memberships", [])))} and one physical
evaluation reused by both matrices. 175° cells remain
<code>boundary_stress_only</code>.</p>
{core}
{bio}
<h2>Default scalar heatmaps</h2>
<div class="panel">{"".join(thumbs)}</div>
</body></html>
"""
    _write_text(root / "index.html", body)


def _group_by_case(
    items: Sequence[ConsumedSourceRow],
) -> dict[str, list[ConsumedSourceRow]]:
    grouped: dict[str, list[ConsumedSourceRow]] = defaultdict(list)
    for item in items:
        grouped[item.identity.case_id].append(item)
    return dict(grouped)


def _pairs_for_case(
    pairs: Sequence[PairedPhysicalSample], case_id: str
) -> list[PairedPhysicalSample]:
    return [pair for pair in pairs if pair.case_id == case_id]


def _write_jsonl_gz(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for row in rows:
            handle.write(strict_json_dumps(row, indent=None))
            handle.write("\n")


def write_case_package(
    root: Path,
    *,
    case: Mapping[str, Any],
    items: Sequence[ConsumedSourceRow],
    pairs: Sequence[PairedPhysicalSample],
    retain_wrench_samples: bool = False,
) -> dict[str, Any]:
    """Write one case directory: figures, samples, summary, HTML."""
    case_id = str(case["case_id"])
    case_dir = root / "cases" / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    records = plottable_records(items)
    figure_info = write_case_figures(case_dir, records)
    comparisons = {
        key: paired_comparison_summary(pairs, key=key)
        for key in ("isotropic_radius", *NAMED_DIRECTIONS)
    }
    comparison = comparisons["isotropic_radius"]
    comparison_figures = write_comparison_figures(
        case_dir, records=records, comparisons=comparison["comparisons"]
    )
    figure_info["assets"].update(comparison_figures["assets"])
    figure_info["color_limits"].update(comparison_figures["color_limits"])
    detail_readout = None
    if figure_info.get("true_scale_detail"):
        detail_readout = figure_info["true_scale_detail"]
    elif records:
        detail_readout = {
            "sample": records[0],
            "note": "First available record; true-scale figure unavailable.",
        }
    stress_only = "boundary_stress_only" in (
        case.get("j1_status"),
        case.get("j2_status"),
    )
    samples_href = (
        Path(case_wrench_rel(case_id)).name if retain_wrench_samples else "cells.json"
    )
    summary = {
        "schema_version": CASE_SUMMARY_SCHEMA_VERSION,
        "case_id": case_id,
        "memberships": list(case.get("memberships", [])),
        "j1_status": case.get("j1_status"),
        "j2_status": case.get("j2_status"),
        "stress_only": stress_only,
        "n_records": len(records),
        "color_limits": figure_info["color_limits"],
        "color_scale_policy": figure_info["color_scale_policy"],
        "assets": figure_info["assets"],
        "n_eligible_comparisons": comparison["n_eligible"],
        "comparison_exclusions": comparison["exclusion_counts"],
        "comparisons": comparisons,
        "status_mask": status_mask(pairs),
        "status_legend": comparison_figures["status_legend"],
        "detail_readout": detail_readout,
        "force_units": FORCE_UNITS,
        "torque_units": TORQUE_UNITS,
        "axis_label": "mounted_q",
        "samples_href": samples_href,
    }
    if retain_wrench_samples:
        _write_jsonl_gz(case_dir / Path(case_wrench_rel(case_id)).name, records)
    else:
        _write_json(case_dir / "cells.json", records)
    _write_json(case_dir / "summary.json", summary)
    inspector = inspector_payload(
        records,
        comparisons=comparisons,
        assets=figure_info["assets"],
        selected_q_sample_id=(detail_readout or {}).get("q_sample_id"),
    )
    _write_text(
        case_dir / "index.html",
        _case_html(
            case=case,
            assets=figure_info["assets"],
            summary=summary,
            inspector=inspector,
            stress_only=stress_only,
        ),
    )
    return summary


def _fixture_result_payload(name: str, wrench: Any) -> dict[str, Any]:
    iso = classify_scalar_field(wrench)
    directions = {
        key: classify_directional_field(wrench, key)
        for key in (wrench.directional_capacity or {})
    }
    support: dict[str, float | None] = {"positive_y": None}
    if wrench.vertices is not None:
        support["positive_y"] = support_along(
            wrench.vertices, np.array([0.0, 1.0], dtype=np.float64)
        )
    return {
        "fixture": name,
        "status": wrench.status.value,
        "isotropic_radius_field": iso,
        "directional_fields": directions,
        "vertices": None if wrench.vertices is None else wrench.vertices.tolist(),
        "support_diagnostic": support,
        "rank": int(wrench.rank),
        "singular_values": [float(v) for v in wrench.singular_values],
        "rank_attribution": dict(wrench.rank_attribution),
    }


def write_fixtures(root: Path) -> None:
    """Write analytic fixture expectations and evaluated results."""
    fixtures = root / "fixtures"
    fixtures.mkdir(parents=True, exist_ok=True)
    expectations = analytic_fixture_expectations()
    _write_json(fixtures / "analytic_expectations.json", expectations)
    results = {
        "regular_unit_arm": _fixture_result_payload(
            "regular_unit_arm", regular_unit_arm_fixture()
        ),
        "stretched_unit_arm": _fixture_result_payload(
            "stretched_unit_arm", stretched_unit_arm_fixture()
        ),
    }
    _write_json(fixtures / "analytic_results.json", results)


def write_intrinsic_static_wrench_smoke_atlas(
    output: Path | None = None,
) -> Path:
    """Render the deterministic 60-row smoke atlas under the V4.3 root.

    Intended for tests with a monkeypatched ``REPO_ROOT``. Does not widen
    the production allowlist. Production destinations use the same clean-source
    and empty-root preflight as full generation; existing evidence is frozen.
    """
    config = load_intrinsic_static_wrench_config()
    if config.torque.limits != (1.0, 1.0):
        raise ValueError("V4.3 atlases require the common unit actuator-effort box")
    if output is not None:
        target = Path(output)
    else:
        # Resolve through monkeypatchable REPO_ROOT so smoke tests can inject
        # a temporary repository without widening the allowlist.
        target = _v4_guard.REPO_ROOT / config.output_dir
    begin_v4_3_write(target)
    root = assert_v4_3_output_allowed(target)
    assert_v4_2b_source_lock(config.source)
    cases = load_v4_2b_cases()
    selection, consumed, pairs = resolve_smoke_selection(
        torque_limits=config.torque.limits
    )
    write_local_assets(root)
    write_methods_and_pointers(root)
    write_fixtures(root)

    cases_by_id = {str(case["case_id"]): case for case in cases}
    smoke_cases = [cases_by_id[cid] for cid in selection.case_ids]
    grouped = _group_by_case(consumed)
    case_summaries = []
    for case in smoke_cases:
        cid = str(case["case_id"])
        summary = write_case_package(
            root,
            case=case,
            items=grouped[cid],
            pairs=_pairs_for_case(pairs, cid),
        )
        case_summaries.append({**case, **summary, "href": f"cases/{cid}/index.html"})

    package_meta = {
        "mode": "smoke",
        "n_records": len(consumed),
        "n_cases": len(smoke_cases),
        "selection_digest": selection.selection_digest,
    }
    write_index_html(root, cases=case_summaries, package_meta=package_meta)
    _write_json(root / "cases.json", case_summaries)
    _write_json(root / "smoke_selection.json", smoke_selection_record(selection))
    _write_json(root / "schema.json", schema_documentation())
    _write_json(
        root / "coverage.json",
        {
            "mode": "smoke",
            "n_records": len(consumed),
            "n_cases": len(smoke_cases),
            "n_pairs": len(pairs),
            "mechanisms": list(FROZEN_MECHANISM_IDS),
        },
    )
    _write_json(
        root / "validation.json",
        {
            "source_lock": assert_v4_2b_source_lock(config.source),
            "inherited_tolerances": INHERITED_TOLERANCE_POLICY,
            "no_inference_statement": NO_INFERENCE_STATEMENT,
        },
    )
    return root


def _status_histogram(
    items: Sequence[ConsumedSourceRow],
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for item in items:
        if item.source_failure_code is not None:
            counts["source_failure"] += 1
            continue
        if item.wrench is None:
            counts["missing_wrench"] += 1
            continue
        counts[item.wrench.status.value] += 1
    return dict(sorted(counts.items()))


def generate_intrinsic_static_wrench_package(
    *,
    config_path: Path | str | None = None,
    output: Path | None = None,
    case_ids: Sequence[str] | None = None,
    require_full_corpus: bool = True,
) -> dict[str, Any]:
    """Generate the V4.3 intrinsic static-wrench retained package.

    Canonical writes require a clean git tree and an empty allowed root.
    Explicitly injected test roots may be dirty but must also be empty.
    Existing evidence is never deleted or recreated.
    """
    config = load_intrinsic_static_wrench_config(config_path)
    if config.torque.limits != (1.0, 1.0):
        raise ValueError("V4.3 atlases require the common unit actuator-effort box")
    if output is not None:
        target = Path(output)
    else:
        target = _v4_guard.REPO_ROOT / config.output_dir
    source_sha, source_dirty = begin_v4_3_write(target)
    root = assert_v4_3_output_allowed(target)

    source_lock = assert_v4_2b_source_lock(config.source)
    predecessor = snapshot_predecessor_integrity()
    cases = load_v4_2b_cases()
    selected_ids = (
        tuple(case_ids)
        if case_ids is not None
        else tuple(str(case["case_id"]) for case in cases)
    )
    consumed, pairs, coverage = consume_v4_2b_corpus(
        torque_limits=config.torque.limits,
        evaluate_wrench=True,
        case_ids=selected_ids,
    )
    if require_full_corpus:
        if coverage.n_rows != FROZEN_V4_2B_N_GEOMETRY_ROWS:
            raise ValueError(
                f"full corpus required: n_rows={coverage.n_rows} "
                f"!= {FROZEN_V4_2B_N_GEOMETRY_ROWS}"
            )
        if coverage.n_typed_failures != 0:
            raise ValueError(
                "canonical package refuses typed source failures: "
                f"n_typed_failures={coverage.n_typed_failures}"
            )
        if coverage.n_silent_drops != 0:
            raise ValueError("n_silent_drops must be 0")

    write_local_assets(root)
    write_methods_and_pointers(root)
    write_fixtures(root)

    cases_by_id = {str(case["case_id"]): case for case in cases}
    selected_cases = [cases_by_id[cid] for cid in selected_ids]
    grouped = _group_by_case(consumed)
    case_summaries = []
    for case in selected_cases:
        cid = str(case["case_id"])
        summary = write_case_package(
            root,
            case=case,
            items=grouped[cid],
            pairs=_pairs_for_case(pairs, cid),
            retain_wrench_samples=True,
        )
        case_summaries.append({**case, **summary, "href": f"cases/{cid}/index.html"})

    selection, _smoke_rows, _smoke_pairs = resolve_smoke_selection(
        torque_limits=config.torque.limits
    )
    package_meta = {
        "mode": "canonical" if require_full_corpus else "subset",
        "n_records": coverage.n_rows,
        "n_cases": coverage.n_cases,
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "package": V4_3_ALLOWED_PACKAGE,
    }
    write_index_html(root, cases=case_summaries, package_meta=package_meta)
    _write_json(root / "cases.json", case_summaries)
    _write_json(root / "smoke_selection.json", smoke_selection_record(selection))
    _write_json(root / "schema.json", schema_documentation())
    _write_json(
        root / "config_resolved.json",
        {
            "schema_version": PACKAGE_SCHEMA_VERSION,
            "config": config.model_dump(mode="json"),
            "config_digest": config.digest(),
            "config_path": str(
                Path(config_path) if config_path is not None else DEFAULT_CONFIG_REL
            ),
        },
    )
    _write_json(
        root / "source_lock.json",
        {
            **source_lock,
            "generation_git_revision": source_sha,
            "generation_git_dirty": source_dirty,
            "activation_baseline_note": (
                "V4.2B freeze lock; V4.3 generation revision is separate."
            ),
            "inherited_tolerance_policy": INHERITED_TOLERANCE_POLICY,
        },
    )
    _write_json(root / "predecessor_integrity.json", predecessor)
    status_counts = _status_histogram(consumed)
    retained = [retained_force_record(item) for item in consumed]
    diagnostics = aggregate_vertex_diagnostics(retained)
    _write_json(
        root / "coverage.json",
        {
            "mode": package_meta["mode"],
            "n_rows": coverage.n_rows,
            "n_cases": coverage.n_cases,
            "n_pairs": coverage.n_pairs,
            "n_typed_failures": coverage.n_typed_failures,
            "n_silent_drops": coverage.n_silent_drops,
            "n_rows_per_arm": dict(coverage.n_rows_per_arm),
            "mechanisms": list(FROZEN_MECHANISM_IDS),
            "status_counts": status_counts,
        },
    )
    _write_json(
        root / "validation.json",
        {
            "source_lock": source_lock,
            "inherited_tolerances": INHERITED_TOLERANCE_POLICY,
            "no_inference_statement": NO_INFERENCE_STATEMENT,
            "n_typed_failures": coverage.n_typed_failures,
            "n_silent_drops": coverage.n_silent_drops,
            "status_counts": status_counts,
            "require_full_corpus": require_full_corpus,
            "vertex_diagnostic_failures_by_status": diagnostics[
                "vertex_diagnostic_failures_by_status"
            ],
            "vertex_diagnostic_failures_by_case": diagnostics[
                "vertex_diagnostic_failures_by_case"
            ],
            "max_corner_residual": diagnostics["max_corner_residual"],
            "max_hrep_residual": diagnostics["max_hrep_residual"],
        },
    )
    environment = capture_environment()
    environment.update(
        {
            "reproduction_commands": [
                (
                    "python scripts/generate_v4_3_intrinsic_static_wrench.py "
                    "--config configs/v4/intrinsic_static_wrench_v1.json"
                ),
                (f"python scripts/verify_v4_3_artifact.py {config.output_dir}"),
            ],
            "generation_git_revision": source_sha,
            "generation_git_dirty": source_dirty,
            "numpy_version": environment.get("packages", {}).get("numpy"),
        }
    )
    _write_json(root / "environment.json", environment)

    inventory = inventory_package_files(root, selected_ids)
    digest = files_digest(inventory)
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "package": V4_3_ALLOWED_PACKAGE,
        "manifest_inventory_rule": MANIFEST_INVENTORY_RULE,
        "source_git_revision": source_sha,
        "source_git_dirty": source_dirty,
        "config_digest": config.digest(),
        "case_ids": list(selected_ids),
        "n_rows": coverage.n_rows,
        "n_typed_failures": coverage.n_typed_failures,
        "n_silent_drops": coverage.n_silent_drops,
        "n_cases": coverage.n_cases,
        "n_pairs": coverage.n_pairs,
        "n_rows_per_arm": dict(coverage.n_rows_per_arm),
        "status_counts": status_counts,
        "files": inventory,
        "files_digest": digest,
    }
    _write_json(root / MANIFEST_NAME, manifest)
    return {
        "output": str(root),
        "files_digest": digest,
        "n_rows": coverage.n_rows,
        "n_cases": coverage.n_cases,
        "n_typed_failures": coverage.n_typed_failures,
        "n_silent_drops": coverage.n_silent_drops,
        "source_git_revision": source_sha,
        "source_git_dirty": source_dirty,
        "config_digest": config.digest(),
    }


__all__ = [
    "generate_intrinsic_static_wrench_package",
    "plottable_records",
    "write_case_figures",
    "write_case_package",
    "write_index_html",
    "write_intrinsic_static_wrench_smoke_atlas",
    "write_local_assets",
    "write_methods_and_pointers",
    "write_paired_heatmap",
    "write_polygon_glyphs",
    "write_true_scale_detail",
]
