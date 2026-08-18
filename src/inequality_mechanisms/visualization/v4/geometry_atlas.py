"""Shared-scale static atlas figures from stored V4.0 snapshot values."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from numpy.typing import NDArray

from inequality_mechanisms.experiments.v4.atlas_config import (
    NO_INFERENCE_STATEMENT,
    Planar2RGeometryAtlasConfig,
)
from inequality_mechanisms.experiments.v4.controls import AtlasArm
from inequality_mechanisms.experiments.v4.geometry_atlas import AtlasRow
from inequality_mechanisms.experiments.v4.shared_q_atlas import SharedQSampleBank
from inequality_mechanisms.visualization.audit_mapping import write_mapping_panels

PAIRED_MECHANISMS = ("fourbar", "span_matched_gearbox")
NULL_CONTROL = "identity_on_shared_q"
EPS = 1e-12

_HTML_CSS = """
body { font-family: Georgia, "Times New Roman", serif; margin: 1.2rem; color: #222; }
table { border-collapse: collapse; width: 100%; margin: 0.6rem 0 1.2rem; font-size: 0.92rem; }
th, td { border: 1px solid #bbb; padding: 0.35rem 0.45rem; vertical-align: top; }
th { background: #f3f3f3; }
img { max-width: 100%; height: auto; border: 1px solid #ddd; margin: 0.25rem 0; }
.muted { color: #555; }
code { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 0.85rem; }
"""


def _require_matplotlib() -> Any:
    import matplotlib.pyplot as plt

    return plt


def descriptors_from_stored_matrix(
    matrix: Sequence[Sequence[float]] | None,
) -> dict[str, float] | None:
    """Ellipse descriptors from a stored metric or mobility matrix."""
    if matrix is None:
        return None
    arr = np.asarray(matrix, dtype=np.float64)
    evals = np.linalg.eigvalsh(arr)
    evals_pos = np.maximum(evals, EPS)
    lambda_min = float(evals_pos[0])
    lambda_max = float(evals_pos[-1])
    kappa = float(lambda_max / max(lambda_min, EPS))
    return {
        "lambda_min": lambda_min,
        "lambda_max": lambda_max,
        "kappa": kappa,
        "sqrt_kappa": float(np.sqrt(max(kappa, EPS))),
        "sqrt_det": float(np.sqrt(float(np.prod(evals_pos)))),
    }


def _field_grid(
    rows: Sequence[AtlasRow],
    *,
    mechanism_id: str,
    bank: SharedQSampleBank,
    getter,
) -> NDArray[np.float64]:
    n0, n1 = bank.shape
    grid = np.full((n0, n1), np.nan, dtype=np.float64)
    for row in rows:
        if row.mechanism_id != mechanism_id or row.snapshot is None:
            continue
        i, j = row.grid_index
        value = getter(row)
        if value is None:
            continue
        grid[i, j] = float(value)
    return grid


def _sigma_min(matrix: Sequence[Sequence[float]]) -> float:
    arr = np.asarray(matrix, dtype=np.float64)
    return float(np.linalg.svd(arr, compute_uv=False)[-1])


def _sigma_max(matrix: Sequence[Sequence[float]]) -> float:
    arr = np.asarray(matrix, dtype=np.float64)
    return float(np.linalg.svd(arr, compute_uv=False)[0])


def _shared_limits(*grids: NDArray[np.float64]) -> tuple[float, float]:
    vals = np.concatenate([g[np.isfinite(g)] for g in grids if np.any(np.isfinite(g))])
    if vals.size == 0:
        return 0.0, 1.0
    vmin = float(np.min(vals))
    vmax = float(np.max(vals))
    if vmax <= vmin:
        vmax = vmin + 1e-12
    return vmin, vmax


def _pcolor(
    path: Path,
    *,
    bank: SharedQSampleBank,
    grids: Mapping[str, NDArray[np.float64]],
    title: str,
    cmap: str = "viridis",
    paired_keys: Sequence[str] = PAIRED_MECHANISMS,
) -> None:
    plt = _require_matplotlib()
    q1 = np.unique([s.q[0] for s in bank.samples])
    q2 = np.unique([s.q[1] for s in bank.samples])
    qq1, qq2 = np.meshgrid(q1, q2, indexing="ij")
    keys = list(grids)
    fig, axes = plt.subplots(1, len(keys), figsize=(4.2 * len(keys), 3.6), squeeze=False)
    paired = [grids[k] for k in paired_keys if k in grids]
    vmin, vmax = _shared_limits(*paired) if paired else _shared_limits(*grids.values())
    for ax, key in zip(axes[0], keys):
        grid = grids[key]
        use_shared = key in paired_keys
        mesh = ax.pcolormesh(
            qq1,
            qq2,
            grid,
            shading="nearest",
            cmap=cmap,
            vmin=vmin if use_shared else None,
            vmax=vmax if use_shared else None,
        )
        label = key if key != NULL_CONTROL else "identity (null control)"
        ax.set_title(label)
        ax.set_xlabel(r"$q_1$")
        ax.set_ylabel(r"$q_2$")
        ax.set_aspect("equal")
        fig.colorbar(mesh, ax=ax, fraction=0.046, pad=0.04)
    fig.suptitle(title)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=120)
    plt.close(fig)


def write_atlas_figures(
    figures_dir: Path,
    *,
    arms: Mapping[str, AtlasArm],
    bank: SharedQSampleBank,
    rows: Sequence[AtlasRow],
) -> dict[str, Path]:
    """Write static print panels. Paired fields share color limits."""
    figures_dir = Path(figures_dir)
    figures_dir.mkdir(parents=True, exist_ok=True)
    assets: dict[str, Path] = {}
    mapping = write_mapping_panels(
        labeled_branches={
            "fourbar": arms["fourbar"].branch,
            "span_matched_gearbox": arms["span_matched_gearbox"].branch,
        },
        out_dir=figures_dir,
        task_id="atlas",
    )
    assets.update({f"mapping_{key}": path for key, path in mapping.items()})

    def _add(name: str, title: str, getter) -> None:
        grids = {
            mech: _field_grid(rows, mechanism_id=mech, bank=bank, getter=getter)
            for mech in (*PAIRED_MECHANISMS, NULL_CONTROL)
        }
        path = figures_dir / f"{name}.png"
        _pcolor(path, bank=bank, grids=grids, title=title)
        assets[name] = path

    _add(
        "sigma_min_jg",
        r"$\sigma_{\min}(J_g)$ (paired scales exclude identity null control)",
        lambda row: _sigma_min(row.snapshot.j_u_to_q),
    )
    _add(
        "sigma_max_jg",
        r"$\sigma_{\max}(J_g)$",
        lambda row: _sigma_max(row.snapshot.j_u_to_q),
    )
    _add(
        "sigma_min_jf",
        r"$\sigma_{\min}(J_f)$",
        lambda row: _sigma_min(row.snapshot.j_q_to_x),
    )
    _add(
        "sigma_max_jf",
        r"$\sigma_{\max}(J_f)$",
        lambda row: _sigma_max(row.snapshot.j_q_to_x),
    )
    _add(
        "sigma_min_jxu",
        r"$\sigma_{\min}(J_{xu})$",
        lambda row: _sigma_min(row.snapshot.j_u_to_x),
    )
    _add(
        "sigma_max_jxu",
        r"$\sigma_{\max}(J_{xu})$",
        lambda row: _sigma_max(row.snapshot.j_u_to_x),
    )

    def _metric_desc(row: AtlasRow, key: str) -> float | None:
        desc = descriptors_from_stored_matrix(row.snapshot.actuator_metric_on_q)
        if desc is None:
            return None
        return desc[key]

    def _mob_q_desc(row: AtlasRow, key: str) -> float | None:
        desc = descriptors_from_stored_matrix(row.snapshot.mobility_on_q)
        if desc is None:
            return None
        return desc[key]

    def _mob_x_desc(row: AtlasRow, key: str) -> float | None:
        desc = descriptors_from_stored_matrix(row.snapshot.mobility_on_x)
        if desc is None:
            return None
        return desc[key]

    for key, title in (
        ("lambda_min", r"$M_Q^{(U)}$ $\lambda_{\min}$"),
        ("lambda_max", r"$M_Q^{(U)}$ $\lambda_{\max}$"),
        ("sqrt_kappa", r"$M_Q^{(U)}$ $\sqrt{\kappa}$"),
        ("sqrt_det", r"$M_Q^{(U)}$ $\sqrt{\det}$"),
    ):
        _add(f"metric_{key}", title, lambda row, k=key: _metric_desc(row, k))
    for key, title in (
        ("lambda_min", r"$B_Q^{(U)}$ $\lambda_{\min}$"),
        ("sqrt_kappa", r"$B_Q^{(U)}$ $\sqrt{\kappa}$"),
    ):
        _add(f"mobility_q_{key}", title, lambda row, k=key: _mob_q_desc(row, k))
    _add(
        "mobility_x_sqrt_kappa",
        r"$B_X^{(U)}$ $\sqrt{\kappa}$",
        lambda row: _mob_x_desc(row, "sqrt_kappa"),
    )
    _add(
        "rank_jg",
        r"rank $(J_g)$ (transmission)",
        lambda row: float(row.snapshot.rank_u_to_q.rank),
    )
    _add(
        "rank_jf",
        r"rank $(J_f)$ (manipulator)",
        lambda row: float(row.snapshot.rank_q_to_x.rank),
    )
    _add(
        "rank_jxu",
        r"rank $(J_{xu})$ (composite)",
        lambda row: float(row.snapshot.rank_u_to_x.rank),
    )
    _add(
        "metric_available",
        "inverse-metric availability (1 = available)",
        lambda row: 1.0 if row.snapshot.actuator_metric_on_q is not None else 0.0,
    )
    return assets


def write_atlas_html(
    output: Path,
    *,
    config: Planar2RGeometryAtlasConfig,
    arms: Mapping[str, AtlasArm],
    bank: SharedQSampleBank,
    rows: Sequence[AtlasRow],
    manifest: Mapping[str, Any],
) -> Path:
    """Write index.html and figures. Identity is a null control, not a competitor."""
    figures = Path(output) / "figures"
    assets = write_atlas_figures(figures, arms=arms, bank=bank, rows=rows)
    n_failed = sum(1 for row in rows if row.failure_code is not None)

    def img(name: str, caption: str) -> str:
        rel = assets[name].relative_to(output)
        return (
            f"<figure><img src=\"{html.escape(rel.as_posix())}\" "
            f"alt=\"{html.escape(caption)}\"/>"
            f"<figcaption>{html.escape(caption)}</figcaption></figure>"
        )

    mapping_imgs = "".join(
        f"<figure><img src=\"{html.escape(path.relative_to(output).as_posix())}\" "
        f"alt=\"{html.escape(key)}\"/><figcaption>{html.escape(key)}</figcaption></figure>"
        for key, path in assets.items()
        if key.startswith("mapping_")
    )
    body = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>V4.1 Planar-2R Intrinsic Geometry Atlas</title>
<style>{_HTML_CSS}</style></head><body>
<h1>V4.1 Planar-2R Intrinsic Geometry Atlas</h1>
<p><strong>{html.escape(NO_INFERENCE_STATEMENT)}</strong></p>
<p class="muted">Git <code>{html.escape(str(manifest.get("git_revision")))}</code>
· schema <code>{html.escape(config.schema_version)}</code>
· grid {list(config.grid.shape)}
· samples {len(bank.samples)}
· failed rows {n_failed}
· config digest <code>{html.escape(config.digest())}</code></p>
<p>Identity-on-shared-Q is a <em>null control</em>, not a third ranked competitor.
Paired color limits are computed from the four-bar and span-matched gearbox only.</p>
<p><a href="manifest.json">manifest.json</a> ·
<a href="resolved_config.json">resolved_config.json</a> ·
<a href="geometry_samples.jsonl">geometry_samples.jsonl</a> ·
<a href="rank_fields.json">rank_fields.json</a></p>
<h2>Transmission maps</h2>
{mapping_imgs}
<h2>Singular values</h2>
{img("sigma_min_jg", "sigma_min J_g")}
{img("sigma_max_jg", "sigma_max J_g")}
{img("sigma_min_jf", "sigma_min J_f")}
{img("sigma_max_jf", "sigma_max J_f")}
{img("sigma_min_jxu", "sigma_min J_xu")}
{img("sigma_max_jxu", "sigma_max J_xu")}
<h2>Actuator metric on Q</h2>
{img("metric_lambda_min", "M_Q lambda_min")}
{img("metric_lambda_max", "M_Q lambda_max")}
{img("metric_sqrt_kappa", "M_Q sqrt_kappa")}
{img("metric_sqrt_det", "M_Q sqrt_det")}
<h2>Mobility</h2>
{img("mobility_q_lambda_min", "B_Q lambda_min")}
{img("mobility_q_sqrt_kappa", "B_Q sqrt_kappa")}
{img("mobility_x_sqrt_kappa", "B_X sqrt_kappa")}
<h2>Rank attribution</h2>
{img("rank_jg", "rank J_g")}
{img("rank_jf", "rank J_f")}
{img("rank_jxu", "rank J_xu")}
{img("metric_available", "inverse-metric availability")}
</body></html>
"""
    path = Path(output) / "index.html"
    path.write_text(body, encoding="utf-8")
    return path
