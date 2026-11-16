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
    assert_v4_3_output_root_empty,
    assert_v4_3_source_clean,
    canonical_v4_3_retained_root,
    git_rev_parse_head,
    prepare_v4_3_output_dir,
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
    ROW_SCHEMA_VERSION,
    TORQUE_UNITS,
    load_intrinsic_static_wrench_config,
)
from inequality_mechanisms.experiments.v4.intrinsic_static_wrench_fields import (
    INHERITED_TOLERANCE_POLICY,
    NAMED_DIRECTIONS,
    PRIMARY_MECHANISM_PAIR,
    analytic_fixture_expectations,
    build_force_record,
    classify_directional_field,
    classify_scalar_field,
    paired_comparison_summary,
    regular_unit_arm_fixture,
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
.panel { display: grid; grid-template-columns: 1fr 1fr; gap: 0.8rem; }
@media (max-width: 800px) { .panel { grid-template-columns: 1fr; } }
"""

_ATLAS_JS = """
(function () {
  const select = document.getElementById("view-select");
  const img = document.getElementById("main-image");
  const caption = document.getElementById("main-caption");
  if (!select || !img || typeof ATLAS_ASSETS === "undefined") return;
  select.addEventListener("change", function () {
    const key = select.value;
    const entry = ATLAS_ASSETS[key];
    if (!entry) return;
    img.src = entry.src;
    img.alt = entry.alt;
    if (caption) caption.textContent = entry.caption;
  });
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
    """Flatten consumed rows into figure/HTML cell records."""
    out: list[dict[str, Any]] = []
    for item in items:
        force = build_force_record(item)
        wrench = force.get("wrench") or {}
        iso_field = force["isotropic_radius_field"]
        out.append(
            {
                "schema_version": ROW_SCHEMA_VERSION,
                "case_id": item.identity.case_id,
                "q_sample_id": item.identity.q_sample_id,
                "mechanism_id": item.identity.mechanism_id,
                "mechanism_pair_id": item.identity.mechanism_pair_id,
                "grid_index": list(item.identity.grid_index),
                "config_digest": item.identity.config_digest,
                "source_revision": item.identity.source_revision,
                "source_relpath": item.identity.source_relpath,
                "status": force.get("status") or "source_failure",
                "primary_eligible": bool(force.get("primary_eligible")),
                "q": wrench.get("q"),
                "u": wrench.get("u"),
                "x": wrench.get("x"),
                "isotropic_radius": iso_field.get("value"),
                "isotropic_radius_field": iso_field,
                "directional_fields": force.get("directional_fields"),
                "directional_capacity": wrench.get("directional_capacity"),
                "undefined_directions": wrench.get("undefined_directions") or [],
                "vertices": wrench.get("vertices"),
                "rank_attribution": force.get("rank_attribution"),
                "singular_values": force.get("singular_values"),
                "low_gain_warning": bool(force.get("low_gain_warning")),
                "j_g": wrench.get("j_g"),
                "j_f": wrench.get("j_f"),
                "j_xu": wrench.get("j_xu"),
                "torque_limits": wrench.get("torque_limits"),
                "vertex_feasibility": force.get("vertex_feasibility"),
                "source_failure_code": item.source_failure_code,
                "source_failure_message": item.source_failure_message,
            }
        )
    return out


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


def write_polygon_glyphs(
    path: Path,
    *,
    records: Sequence[Mapping[str, Any]],
    stride: int = POLYGON_STRIDE,
    title: str = "Shape-normalized force polygons (not magnitude)",
) -> None:
    """Sparse shape-normalized polygon glyphs on mounted Q."""
    plt = _require_matplotlib()
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.6), squeeze=False)
    qs = [
        np.asarray(row["q"], dtype=np.float64)
        for row in records
        if row.get("q") is not None
    ]
    if qs:
        q_arr = np.vstack(qs)
        q_span = float(np.max(q_arr[:, 0]) - np.min(q_arr[:, 0]))
        q_span = max(q_span, float(np.max(q_arr[:, 1]) - np.min(q_arr[:, 1])), 1e-6)
    else:
        q_span = 1.0
    glyph = 0.22 * q_span
    shown = []
    for row in records:
        if row.get("status") != WrenchStateStatus.REGULAR.value:
            continue
        verts = row.get("vertices")
        if not verts:
            continue
        i, j = row["grid_index"]
        if int(i) % stride != 0 or int(j) % stride != 0:
            continue
        shown.append(np.asarray(verts, dtype=np.float64))
    scale = 1.0
    if shown:
        max_r = max(float(np.max(np.linalg.norm(v, axis=1))) for v in shown)
        if max_r > 0.0:
            scale = glyph / max_r
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
                poly = q_arr + scale * np.asarray(verts, dtype=np.float64)
                closed = np.vstack([poly, poly[0]])
                ax.plot(closed[:, 0], closed[:, 1], color="#1d4f91", lw=0.8)
            else:
                ax.plot(q_arr[0], q_arr[1], marker="x", color="#a31f34", ms=5)
        ax.set_title(mech)
        ax.set_xlabel("mounted $q_1$ (rad)")
        ax.set_ylabel("mounted $q_2$ (rad)")
        ax.set_aspect("equal")
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
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.6), squeeze=False)
    detail: dict[str, Any] = {"q_sample_id": q_sample_id, "arms": {}}
    for ax, mech in zip(axes[0], PRIMARY_MECHANISM_PAIR, strict=True):
        row = next((r for r in chosen if r["mechanism_id"] == mech), None)
        ax.set_title(mech)
        ax.set_xlabel(r"$F_x$ (normalized torque/length)")
        ax.set_ylabel(r"$F_y$ (normalized torque/length)")
        ax.set_aspect("equal")
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
            detail["arms"][mech] = {
                "vertices": None,
                "status": None if row is None else row.get("status"),
            }
            continue
        verts = np.asarray(row["vertices"], dtype=np.float64)
        closed = np.vstack([verts, verts[0]])
        ax.plot(closed[:, 0], closed[:, 1], color="#1d4f91", lw=1.4)
        ax.fill(closed[:, 0], closed[:, 1], color="#1d4f91", alpha=0.12)
        detail["arms"][mech] = {
            "vertices": verts.tolist(),
            "status": row.get("status"),
            "isotropic_radius": row.get("isotropic_radius"),
            "source_identity": {
                "case_id": row["case_id"],
                "q_sample_id": row["q_sample_id"],
                "mechanism_id": row["mechanism_id"],
                "grid_index": row["grid_index"],
            },
        }
    fig.suptitle(title)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return detail


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
    if paired_vals.size:
        vmin = float(np.min(paired_vals))
        vmax = float(np.max(paired_vals))
        if vmax <= vmin:
            vmax = vmin + 1e-12
    else:
        vmin, vmax = 0.0, 1.0

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
        title="Identity reference isotropic radius",
        vmin=vmin,
        vmax=vmax,
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
        "caption": "Identity-on-shared-Q reference panel (not a ranked competitor).",
    }

    for direction in NAMED_DIRECTIONS:
        grids = {
            mech: _field_grid(
                records,
                mechanism_id=mech,
                key=direction,
                shape=shape,
                primary_only=False,
            )
            for mech in PRIMARY_MECHANISM_PAIR
        }
        vals = np.concatenate(
            [grids[m][np.isfinite(grids[m])] for m in PRIMARY_MECHANISM_PAIR]
        )
        if vals.size:
            d_vmin = float(np.min(vals))
            d_vmax = float(np.max(vals))
            if d_vmax <= d_vmin:
                d_vmax = d_vmin + 1e-12
        else:
            d_vmin, d_vmax = 0.0, 1.0
        write_paired_heatmap(
            fig_dir / f"{direction}.png",
            qq1=qq1,
            qq2=qq2,
            grids=grids,
            title=f"Ray capacity: {direction}",
            vmin=d_vmin,
            vmax=d_vmax,
        )
        assets[direction] = {
            "src": f"figures/{direction}.png",
            "alt": direction,
            "caption": (
                f"Directional ray capacity ({direction}). "
                "Undefined/unbounded cells are masked; Cartesian and "
                "radial/tangential statuses are independent."
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

    # Prefer a regular center-ish sample for true-scale detail.
    detail_id = None
    for row in records:
        if (
            row["mechanism_id"] == "fourbar"
            and row.get("primary_eligible")
            and row.get("vertices")
        ):
            detail_id = row["q_sample_id"]
            if tuple(row["grid_index"]) == (16, 16):
                break
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
        "color_limits": {"isotropic_radius": [vmin, vmax]},
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


def _case_html(
    *,
    case: Mapping[str, Any],
    assets: Mapping[str, Any],
    summary: Mapping[str, Any],
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
        ("polygons", "shape-normalized polygons"),
        ("true_scale_detail", "true-scale detail"),
        ("identity_scalar", "identity reference"),
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
<h2>Selected-cell contract</h2>
<p class="muted">Tooltips and detail panels display stored values only.
Configuration/branch identity is retained; distinct configurations are never
merged into an unlabeled workspace-capacity claim.</p>
<pre>{
        html.escape(strict_json_dumps(summary.get("detail_readout") or {{}}, indent=2))
    }</pre>
<p><a href="{html.escape(str(summary.get("samples_href") or "cells.json"))}">
samples</a> · <a href="summary.json">summary.json</a> ·
<a href="../../methods.md">methods.md</a></p>
<script>const ATLAS_ASSETS = {json.dumps(assets)};</script>
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
    comparison = paired_comparison_summary(pairs, key="isotropic_radius")
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
        "assets": figure_info["assets"],
        "n_eligible_comparisons": comparison["n_eligible"],
        "comparison_exclusions": comparison["exclusion_counts"],
        "status_mask": status_mask(pairs),
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
    _write_text(
        case_dir / "index.html",
        _case_html(
            case=case,
            assets=figure_info["assets"],
            summary=summary,
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
    the production allowlist and does not populate the real canonical
    retained package unless ``output`` points there deliberately.
    """
    config = load_intrinsic_static_wrench_config()
    if output is not None:
        target = Path(output)
    else:
        # Resolve through monkeypatchable REPO_ROOT so smoke tests can inject
        # a temporary repository without widening the allowlist.
        target = _v4_guard.REPO_ROOT / config.output_dir
    root = prepare_v4_3_output_dir(assert_v4_3_output_allowed(target))
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


def _is_canonical_v4_3_write(resolved: Path) -> bool:
    """True only for the never-monkeypatched retained package root."""
    return resolved.resolve() == canonical_v4_3_retained_root()


def _begin_v4_3_write(output: Path) -> tuple[str, bool]:
    """Clean-source + empty-root preflight for canonical V4.3 writes."""
    resolved = assert_v4_3_output_allowed(output)
    if _is_canonical_v4_3_write(resolved):
        sha = assert_v4_3_source_clean()
        assert_v4_3_output_root_empty(resolved)
        prepare_v4_3_output_dir(resolved)
        return sha, False
    if resolved.exists():
        shutil.rmtree(resolved)
    prepare_v4_3_output_dir(resolved)
    return git_rev_parse_head(), True


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
    Temporary roots used by tests may be dirty and are recreated.
    """
    config = load_intrinsic_static_wrench_config(config_path)
    if output is not None:
        target = Path(output)
    else:
        target = _v4_guard.REPO_ROOT / config.output_dir
    source_sha, source_dirty = _begin_v4_3_write(target)
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
                (
                    "python scripts/verify_v4_3_artifact.py "
                    "results/v4_review/v4_3_intrinsic_static_wrench"
                ),
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
