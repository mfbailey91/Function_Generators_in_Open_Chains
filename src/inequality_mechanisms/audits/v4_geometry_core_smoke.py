"""Deterministic V4-008 geometry-core smoke artifact.

This writer inspects the kinematic-transmission kernel on one certified
planar-2R crank-rocker and its span-matched gearbox. It does not rank
mechanisms, run tasks, or expose reusable Jacobian finite-difference helpers.
"""

from __future__ import annotations

import html
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from numpy.typing import NDArray

from inequality_mechanisms.adapters import planar_2r_operating_branch_robot
from inequality_mechanisms.audits.v4_artifact_guard import (
    V4_0_ALLOWED_OUTPUT_REL,
    allowed_v4_0_output_root,
    assert_v4_0_output_allowed,
    prepare_v4_0_output_dir,
)
from inequality_mechanisms.kinematics.planar_2r import Planar2R
from inequality_mechanisms.mechanisms import (
    IndependentFourBars,
    PlanarFourBar,
    equivalent_gearbox_branch,
    select_fourbar_monotonic_branch,
)
from inequality_mechanisms.transmission_geometry import (
    METRIC_STATUS_AVAILABLE,
    composite_jacobian,
    geometry_snapshot,
    pullback_covector,
    pushforward_vector,
)
from inequality_mechanisms.visualization.audit_mapping import write_mapping_panels

SCHEMA_VERSION = "v4.0.geometry_core_smoke.v1"
NO_INFERENCE_STATEMENT = (
    "geometry-core verification; no mechanism performance inference."
)
GRID_N = 17
FD_STEP = 1e-6
Q_INSET_FRACTION = 0.01
TRANSMISSION_PLOT_SAMPLES = 201
CRANK_ROCKER = dict(a=1.0, b=2.5, c=2.0, d=2.0)
PLANAR_L1 = 1.0
PLANAR_L2 = 1.0
MECHANISM_IDS = ("fourbar", "span_matched_gearbox")
FORCE = np.asarray([1.0, -0.5], dtype=np.float64)
POTENTIAL_GOAL = np.asarray([1.2, 0.4], dtype=np.float64)
POTENTIAL_WEIGHT = np.diag([2.0, 0.5])
TANGENTS = (
    np.asarray([1.0, 0.0], dtype=np.float64),
    np.asarray([0.0, 1.0], dtype=np.float64),
    np.asarray([0.3, -0.7], dtype=np.float64),
)
REQUIRED_FILES = (
    "manifest.json",
    "resolved_config.json",
    "geometry_samples.jsonl",
    "identity_residuals.json",
    "index.html",
)

_HTML_CSS = """
body { font-family: Georgia, "Times New Roman", serif; margin: 1.2rem; color: #222; }
table { border-collapse: collapse; width: 100%; margin: 0.6rem 0 1.2rem; font-size: 0.92rem; }
th, td { border: 1px solid #bbb; padding: 0.35rem 0.45rem; vertical-align: top; }
th { background: #f3f3f3; }
img { max-width: 100%; height: auto; border: 1px solid #ddd; margin: 0.25rem 0; }
.muted { color: #555; }
code { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 0.85rem; }
"""


def _git_revision() -> str | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    value = proc.stdout.strip()
    return value or None


def _fourbar_branch():
    bars = [
        PlanarFourBar(**CRANK_ROCKER, branch=1, name="b0"),
        PlanarFourBar(**CRANK_ROCKER, branch=1, name="b1"),
    ]
    return select_fourbar_monotonic_branch(IndependentFourBars(bars))


def build_paired_arms() -> dict[str, Any]:
    """Return four-bar and span-matched gearbox robots sharing planar FK."""
    fk = Planar2R(L1=PLANAR_L1, L2=PLANAR_L2)
    fourbar = _fourbar_branch()
    gearbox = equivalent_gearbox_branch(fourbar, name="span_matched_gearbox")
    return {
        "fourbar": {
            "mechanism_id": "fourbar",
            "branch": fourbar,
            "robot": planar_2r_operating_branch_robot(fourbar, planar_fk=fk),
        },
        "span_matched_gearbox": {
            "mechanism_id": "span_matched_gearbox",
            "branch": gearbox,
            "robot": planar_2r_operating_branch_robot(gearbox, planar_fk=fk),
        },
    }


def shared_q_axes(
    branch,
    *,
    n: int = GRID_N,
    inset_fraction: float = Q_INSET_FRACTION,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return inset shared-Q linspaces from a certified output box."""
    cert = branch.certificate
    lo = np.asarray(cert.output_lower, dtype=np.float64)
    hi = np.asarray(cert.output_upper, dtype=np.float64)
    span = hi - lo
    inset = np.maximum(inset_fraction * span, 2.0 * FD_STEP)
    inner_lo = lo + inset
    inner_hi = hi - inset
    if np.any(inner_hi <= inner_lo):
        raise ValueError(
            "shared-Q inset emptied the certified output box: "
            f"lower={lo.tolist()}, upper={hi.tolist()}, inset={inset.tolist()}"
        )
    q1 = np.linspace(float(inner_lo[0]), float(inner_hi[0]), int(n))
    q2 = np.linspace(float(inner_lo[1]), float(inner_hi[1]), int(n))
    return q1, q2


def _phi(x: NDArray[np.float64]) -> float:
    delta = x - POTENTIAL_GOAL
    return 0.5 * float(delta @ (POTENTIAL_WEIGHT @ delta))


def _tip(robot, u: NDArray[np.float64]) -> NDArray[np.float64]:
    state = robot.state_from_input(u)
    return np.asarray(robot.forward_kinematics(state).position, dtype=np.float64)


def _assert_stencil_inside(robot, u: NDArray[np.float64], *, h: float) -> None:
    cert = robot.branch.certificate
    lo = np.asarray(cert.input_lower, dtype=np.float64)
    hi = np.asarray(cert.input_upper, dtype=np.float64)
    if np.any(u - h < lo) or np.any(u + h > hi):
        raise ValueError(
            "finite-difference stencil leaves the certified input box: "
            f"u={u.tolist()}, h={h}, lower={lo.tolist()}, upper={hi.tolist()}"
        )


def _finite_difference_j_xu(
    robot,
    u: NDArray[np.float64],
    *,
    h: float,
) -> NDArray[np.float64]:
    n_u = int(u.shape[0])
    eye = np.eye(n_u, dtype=np.float64)
    columns: list[NDArray[np.float64]] = []
    for i in range(n_u):
        x_plus = _tip(robot, u + h * eye[i])
        x_minus = _tip(robot, u - h * eye[i])
        columns.append((x_plus - x_minus) / (2.0 * h))
    return np.column_stack(columns)


def _potential_fd(
    robot,
    u: NDArray[np.float64],
    *,
    h: float,
) -> NDArray[np.float64]:
    n_u = int(u.shape[0])
    eye = np.eye(n_u, dtype=np.float64)
    fd = np.empty(n_u, dtype=np.float64)
    for i in range(n_u):
        phi_plus = _phi(_tip(robot, u + h * eye[i]))
        phi_minus = _phi(_tip(robot, u - h * eye[i]))
        fd[i] = (phi_plus - phi_minus) / (2.0 * h)
    return fd


def evaluate_sample(
    robot,
    *,
    mechanism_id: str,
    q_sample_id: str,
    grid_i: int,
    grid_j: int,
    q: NDArray[np.float64],
    h: float = FD_STEP,
) -> dict[str, Any]:
    """Return one geometry-core sample row, or raise on kernel/FD failure."""
    candidates = robot.states_from_output(q)
    if not candidates:
        raise ValueError(
            "unique inverse missing for smoke sample: "
            f"mechanism={mechanism_id}, q_sample_id={q_sample_id}, q={q.tolist()}"
        )
    state = candidates[0].state
    u = np.asarray(state.u, dtype=np.float64)
    _assert_stencil_inside(robot, u, h=h)
    snapshot = geometry_snapshot(robot, state)
    if snapshot.metric_status != METRIC_STATUS_AVAILABLE:
        raise ValueError(
            "inverse metric unavailable on smoke grid: "
            f"mechanism={mechanism_id}, q_sample_id={q_sample_id}, "
            f"metric_status={snapshot.metric_status}"
        )
    j_g = np.asarray(snapshot.j_u_to_q, dtype=np.float64)
    j_f = np.asarray(snapshot.j_q_to_x, dtype=np.float64)
    j_xu = np.asarray(snapshot.j_u_to_x, dtype=np.float64)
    metric = np.asarray(snapshot.actuator_metric_on_q, dtype=np.float64)
    mobility = np.asarray(snapshot.mobility_on_q, dtype=np.float64)
    composed = composite_jacobian(j_f, j_g)
    if not np.allclose(composed, j_xu, atol=1e-14, rtol=1e-12):
        raise ValueError(
            "snapshot J_xu disagrees with composite_jacobian: "
            f"mechanism={mechanism_id}, q_sample_id={q_sample_id}"
        )

    j_xu_fd = _finite_difference_j_xu(robot, u, h=h)
    fd_residual = float(np.max(np.abs(j_xu - j_xu_fd)))

    tau_q = pullback_covector(j_f, FORCE)
    tau_u = pullback_covector(j_g, tau_q)
    power_gaps: list[float] = []
    for du in TANGENTS:
        dq = pushforward_vector(j_g, du)
        dx = pushforward_vector(j_f, dq)
        power_u = float(tau_u @ du)
        power_q = float(tau_q @ dq)
        power_x = float(FORCE @ dx)
        power_gaps.append(abs(power_u - power_q))
        power_gaps.append(abs(power_q - power_x))
    virtual_power_residual = float(max(power_gaps))

    x = np.asarray(snapshot.x, dtype=np.float64)
    grad_x = POTENTIAL_WEIGHT @ (x - POTENTIAL_GOAL)
    analytic_grad_u = pullback_covector(j_xu, grad_x)
    potential_fd = _potential_fd(robot, u, h=h)
    potential_residual = float(np.max(np.abs(analytic_grad_u - potential_fd)))

    identity = np.eye(metric.shape[0], dtype=np.float64)
    metric_mobility_residual = float(np.linalg.norm(metric @ mobility - identity, ord="fro"))

    if fd_residual > 1e-5:
        raise ValueError(
            "finite-difference residual exceeds bound: "
            f"mechanism={mechanism_id}, q_sample_id={q_sample_id}, h={h}, "
            f"analytic={j_xu.tolist()}, finite_difference={j_xu_fd.tolist()}"
        )
    if potential_residual > 1e-5:
        raise ValueError(
            "potential-gradient pullback mismatch: "
            f"mechanism={mechanism_id}, q_sample_id={q_sample_id}, h={h}, "
            f"analytic={analytic_grad_u.tolist()}, "
            f"finite_difference={potential_fd.tolist()}"
        )

    metric_eigs = np.linalg.eigvalsh(metric)
    mobility_eigs = np.linalg.eigvalsh(mobility)
    return {
        "mechanism_id": mechanism_id,
        "q_sample_id": q_sample_id,
        "grid_i": int(grid_i),
        "grid_j": int(grid_j),
        "snapshot": snapshot.to_dict(),
        "residuals": {
            "metric_mobility": metric_mobility_residual,
            "finite_difference": fd_residual,
            "virtual_power": virtual_power_residual,
            "potential_gradient": potential_residual,
        },
        "singular_values": {
            "j_u_to_q": [float(v) for v in snapshot.rank_u_to_q.singular_values],
            "j_q_to_x": [float(v) for v in snapshot.rank_q_to_x.singular_values],
            "j_u_to_x": [float(v) for v in snapshot.rank_u_to_x.singular_values],
        },
        "eigenvalues": {
            "actuator_metric_on_q": [float(v) for v in metric_eigs],
            "mobility_on_q": [float(v) for v in mobility_eigs],
        },
    }


def collect_sample_rows(
    arms: Mapping[str, Any],
    q1: NDArray[np.float64],
    q2: NDArray[np.float64],
    *,
    h: float = FD_STEP,
) -> list[dict[str, Any]]:
    """Evaluate every shared-Q sample on both mechanism arms."""
    rows: list[dict[str, Any]] = []
    for mechanism_id in MECHANISM_IDS:
        robot = arms[mechanism_id]["robot"]
        for i, q_i in enumerate(q1):
            for j, q_j in enumerate(q2):
                q = np.asarray([q_i, q_j], dtype=np.float64)
                q_sample_id = f"{i:02d}_{j:02d}"
                rows.append(
                    evaluate_sample(
                        robot,
                        mechanism_id=mechanism_id,
                        q_sample_id=q_sample_id,
                        grid_i=i,
                        grid_j=j,
                        q=q,
                        h=h,
                    )
                )
    expected = int(q1.size * q2.size * len(MECHANISM_IDS))
    if len(rows) != expected:
        raise ValueError(
            f"expected {expected} geometry samples, got {len(rows)}"
        )
    return rows


def _span_ratios(branch) -> NDArray[np.float64]:
    cert = branch.certificate
    u_lo = np.asarray(cert.input_lower, dtype=np.float64)
    u_hi = np.asarray(cert.input_upper, dtype=np.float64)
    q_lo = np.asarray(cert.output_lower, dtype=np.float64)
    q_hi = np.asarray(cert.output_upper, dtype=np.float64)
    return (q_hi - q_lo) / (u_hi - u_lo)


def _max_residual(
    rows: list[dict[str, Any]],
    key: str,
    *,
    mechanism_id: str | None = None,
) -> float:
    values = [
        float(row["residuals"][key])
        for row in rows
        if mechanism_id is None or row["mechanism_id"] == mechanism_id
    ]
    return float(max(values))


def build_identity_residuals(
    rows: list[dict[str, Any]],
    arms: Mapping[str, Any],
) -> dict[str, Any]:
    """Aggregate grid-max residuals and the gearbox §7.1 analytic check."""
    gearbox_rows = [
        row for row in rows if row["mechanism_id"] == "span_matched_gearbox"
    ]
    ratios = _span_ratios(arms["span_matched_gearbox"]["branch"])
    j_expected = np.diag(ratios)
    m_expected = np.diag(1.0 / (ratios**2))
    j_gaps: list[float] = []
    m_gaps: list[float] = []
    for row in gearbox_rows:
        j_g = np.asarray(row["snapshot"]["jacobians"]["j_u_to_q"], dtype=np.float64)
        metric = np.asarray(
            row["snapshot"]["metrics"]["actuator_metric_on_q"], dtype=np.float64
        )
        j_gaps.append(float(np.max(np.abs(j_g - j_expected))))
        m_gaps.append(float(np.max(np.abs(metric - m_expected))))
    residual_keys = (
        "metric_mobility",
        "finite_difference",
        "virtual_power",
        "potential_gradient",
    )
    maxima = {
        key: {
            "fourbar": _max_residual(rows, key, mechanism_id="fourbar"),
            "span_matched_gearbox": _max_residual(
                rows, key, mechanism_id="span_matched_gearbox"
            ),
            "all": _max_residual(rows, key),
        }
        for key in residual_keys
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "no_inference_statement": NO_INFERENCE_STATEMENT,
        "maxima": maxima,
        "gearbox_analytic": {
            "ratios": [float(v) for v in ratios],
            "max_jacobian_residual": float(max(j_gaps)),
            "max_metric_residual": float(max(m_gaps)),
        },
    }


def _field_grid(
    rows: list[dict[str, Any]],
    *,
    mechanism_id: str,
    n: int,
    getter,
) -> NDArray[np.float64]:
    grid = np.full((n, n), np.nan, dtype=np.float64)
    for row in rows:
        if row["mechanism_id"] != mechanism_id:
            continue
        grid[int(row["grid_i"]), int(row["grid_j"])] = float(getter(row))
    if not np.all(np.isfinite(grid)):
        raise ValueError(
            f"non-finite field values for mechanism {mechanism_id!r}"
        )
    return grid


def _shared_pcolor(
    axes_row,
    q1: NDArray[np.float64],
    q2: NDArray[np.float64],
    fields: Mapping[str, NDArray[np.float64]],
    *,
    title: str,
    colorbar_ax=None,
):
    import matplotlib.pyplot as plt

    q1m, q2m = np.meshgrid(q1, q2, indexing="ij")
    stacked = np.concatenate([fields[mid].ravel() for mid in MECHANISM_IDS])
    vmin = float(np.min(stacked))
    vmax = float(np.max(stacked))
    if vmin == vmax:
        vmax = vmin + 1e-15
    images = []
    for ax, mechanism_id in zip(axes_row, MECHANISM_IDS, strict=True):
        image = ax.pcolormesh(
            q1m,
            q2m,
            fields[mechanism_id],
            vmin=vmin,
            vmax=vmax,
            shading="auto",
        )
        ax.set_title(f"{title} / {mechanism_id}")
        ax.set_xlabel(r"$q_1$")
        ax.set_ylabel(r"$q_2$")
        ax.set_aspect("equal", adjustable="box")
        images.append(image)
    plt.colorbar(images[-1], ax=list(axes_row) if colorbar_ax is None else colorbar_ax)
    return images


def write_field_figures(
    *,
    rows: list[dict[str, Any]],
    q1: NDArray[np.float64],
    q2: NDArray[np.float64],
    figures_dir: Path,
) -> dict[str, Path]:
    """Write shared-scale field panels for both mechanisms."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figures_dir.mkdir(parents=True, exist_ok=True)
    n = int(q1.size)
    assets: dict[str, Path] = {}

    def grids(getter) -> dict[str, NDArray[np.float64]]:
        return {
            mid: _field_grid(rows, mechanism_id=mid, n=n, getter=getter)
            for mid in MECHANISM_IDS
        }

    singular_specs = (
        ("j_g_min", "min σ(J_g)", lambda row: row["singular_values"]["j_u_to_q"][-1]),
        ("j_g_max", "max σ(J_g)", lambda row: row["singular_values"]["j_u_to_q"][0]),
        ("j_f_min", "min σ(J_f)", lambda row: row["singular_values"]["j_q_to_x"][-1]),
        ("j_f_max", "max σ(J_f)", lambda row: row["singular_values"]["j_q_to_x"][0]),
        ("j_xu_min", "min σ(J_xu)", lambda row: row["singular_values"]["j_u_to_x"][-1]),
        ("j_xu_max", "max σ(J_xu)", lambda row: row["singular_values"]["j_u_to_x"][0]),
    )
    fig, axes = plt.subplots(len(singular_specs), 2, figsize=(9.5, 18.0), constrained_layout=True)
    for ax_row, (_key, title, getter) in zip(axes, singular_specs, strict=True):
        _shared_pcolor(ax_row, q1, q2, grids(getter), title=title)
    path = figures_dir / "singular_values.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)
    assets["singular_values"] = path

    eigen_specs = (
        ("m_min", r"min λ(M_Q^{(U)})", lambda row: row["eigenvalues"]["actuator_metric_on_q"][0]),
        ("m_max", r"max λ(M_Q^{(U)})", lambda row: row["eigenvalues"]["actuator_metric_on_q"][-1]),
        ("b_min", r"min λ(B_Q^{(U)})", lambda row: row["eigenvalues"]["mobility_on_q"][0]),
        ("b_max", r"max λ(B_Q^{(U)})", lambda row: row["eigenvalues"]["mobility_on_q"][-1]),
    )
    fig, axes = plt.subplots(len(eigen_specs), 2, figsize=(9.5, 12.0), constrained_layout=True)
    for ax_row, (_key, title, getter) in zip(axes, eigen_specs, strict=True):
        _shared_pcolor(ax_row, q1, q2, grids(getter), title=title)
    path = figures_dir / "metric_mobility_eigenvalues.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)
    assets["metric_mobility_eigenvalues"] = path

    residual_specs = (
        ("metric_mobility", "metric–mobility residual"),
        ("finite_difference", "finite-difference residual"),
        ("virtual_power", "virtual-power residual"),
        ("potential_gradient", "potential-gradient residual"),
    )
    fig, axes = plt.subplots(len(residual_specs), 2, figsize=(9.5, 12.0), constrained_layout=True)
    for ax_row, (key, title) in zip(axes, residual_specs, strict=True):
        _shared_pcolor(
            ax_row,
            q1,
            q2,
            grids(lambda row, residual_key=key: row["residuals"][residual_key]),
            title=title,
        )
    path = figures_dir / "identity_residuals.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)
    assets["identity_residuals"] = path
    return assets


def write_index_html(
    *,
    out_path: Path,
    manifest: Mapping[str, Any],
    identity_residuals: Mapping[str, Any],
    figure_rels: Mapping[str, str],
) -> Path:
    """Write the non-inferential geometry-core HTML report."""
    maxima = identity_residuals["maxima"]
    gearbox = identity_residuals["gearbox_analytic"]
    rows_html = "".join(
        "<tr>"
        f"<td>{html.escape(key)}</td>"
        f"<td>{maxima[key]['fourbar']:.3e}</td>"
        f"<td>{maxima[key]['span_matched_gearbox']:.3e}</td>"
        f"<td>{maxima[key]['all']:.3e}</td>"
        "</tr>"
        for key in (
            "metric_mobility",
            "finite_difference",
            "virtual_power",
            "potential_gradient",
        )
    )

    def img(key: str, caption: str) -> str:
        rel = figure_rels[key]
        return (
            f"<figure><img src=\"{html.escape(rel)}\" alt=\"{html.escape(caption)}\"/>"
            f"<figcaption>{html.escape(caption)}</figcaption></figure>"
        )

    body = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>V4.0 Kinematic Geometry Core Smoke</title>
<style>{_HTML_CSS}</style></head><body>
<h1>V4.0 Kinematic Geometry Core Smoke</h1>
<p><strong>{html.escape(NO_INFERENCE_STATEMENT)}</strong></p>
<p class="muted">Git <code>{html.escape(str(manifest.get("git_revision")))}</code>
· schema <code>{html.escape(str(manifest.get("schema_version")))}</code>
· grid {html.escape(str(manifest.get("grid")))}
· W_u identity</p>
<p><a href="manifest.json">manifest.json</a> ·
<a href="resolved_config.json">resolved_config.json</a> ·
<a href="geometry_samples.jsonl">geometry_samples.jsonl</a> ·
<a href="identity_residuals.json">identity_residuals.json</a></p>
<h2>Transmission maps</h2>
<p class="muted">Shared-axis q_i(u_i) and dq_i/du_i for the certified crank-rocker
and its span-matched gearbox. These panels inspect the maps; they do not rank them.</p>
{img("q_of_u", "q_i(u_i) by axis")}
{img("dqdu", "dq_i/du_i and u_i(q_i) by axis")}
<h2>Singular values</h2>
{img("singular_values", "Singular values of J_g, J_f, and J_xu on shared scales")}
<h2>Metric and mobility eigenvalues</h2>
{img("metric_mobility_eigenvalues", "Eigenvalues of M_Q^(U) and B_Q^(U) on shared scales")}
<h2>Identity residuals</h2>
<table>
<tr><th>residual</th><th>fourbar max</th><th>span-matched gearbox max</th><th>all max</th></tr>
{rows_html}
</table>
<p>Gearbox analytic check: ratios {html.escape(str(gearbox["ratios"]))};
max Jacobian residual {gearbox["max_jacobian_residual"]:.3e};
max metric residual {gearbox["max_metric_residual"]:.3e}.</p>
{img("identity_residuals", "Metric-mobility, finite-difference, virtual-power, and potential-gradient residuals")}
</body></html>
"""
    out_path.write_text(body, encoding="utf-8")
    return out_path


def resolved_config(
    *,
    q1: NDArray[np.float64],
    q2: NDArray[np.float64],
    arms: Mapping[str, Any],
) -> dict[str, Any]:
    fourbar = arms["fourbar"]["branch"]
    gearbox = arms["span_matched_gearbox"]["branch"]
    return {
        "schema_version": SCHEMA_VERSION,
        "no_inference_statement": NO_INFERENCE_STATEMENT,
        "robot": {
            "type": "Planar2R",
            "L1": PLANAR_L1,
            "L2": PLANAR_L2,
        },
        "mechanisms": {
            "fourbar": {
                "crank_rocker": dict(CRANK_ROCKER),
                "branch": 1,
                "branch_id": str(fourbar.branch_id),
            },
            "span_matched_gearbox": {
                "matching_rule": "span",
                "branch_id": str(gearbox.branch_id),
                "ratios": [float(v) for v in _span_ratios(gearbox)],
            },
        },
        "grid": {
            "n": GRID_N,
            "shape": [GRID_N, GRID_N],
            "inset_fraction": Q_INSET_FRACTION,
            "q1": [float(v) for v in q1],
            "q2": [float(v) for v in q2],
        },
        "actuator_weight": "identity",
        "finite_difference_step": FD_STEP,
        "duality_probes": {
            "force": [float(v) for v in FORCE],
            "potential_goal": [float(v) for v in POTENTIAL_GOAL],
            "potential_weight_diag": [float(v) for v in np.diag(POTENTIAL_WEIGHT)],
            "tangents": [[float(v) for v in du] for du in TANGENTS],
        },
    }


def generate_geometry_core_smoke(output: Path) -> Path:
    """Write the V4-008 smoke package under the allowed V4.0 output root.

    Parameters
    ----------
    output :
        Candidate output directory. Must pass the V4.0 artifact guard.

    Returns
    -------
    pathlib.Path
        Resolved output directory after writing the package.
    """
    resolved = assert_v4_0_output_allowed(Path(output))
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved = prepare_v4_0_output_dir(resolved)
    figures_dir = resolved / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    arms = build_paired_arms()
    q1, q2 = shared_q_axes(arms["fourbar"]["branch"])
    rows = collect_sample_rows(arms, q1, q2)
    identity = build_identity_residuals(rows, arms)
    config = resolved_config(q1=q1, q2=q2, arms=arms)

    mapping = write_mapping_panels(
        labeled_branches={
            "fourbar": arms["fourbar"]["branch"],
            "span_matched_gearbox": arms["span_matched_gearbox"]["branch"],
        },
        out_dir=figures_dir,
        task_id="geometry_core",
        n_samples=TRANSMISSION_PLOT_SAMPLES,
    )
    field_assets = write_field_figures(
        rows=rows, q1=q1, q2=q2, figures_dir=figures_dir
    )

    samples_path = resolved / "geometry_samples.jsonl"
    with samples_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")

    config_path = resolved / "resolved_config.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    identity_path = resolved / "identity_residuals.json"
    identity_path.write_text(json.dumps(identity, indent=2) + "\n", encoding="utf-8")

    figure_files = {
        "q_of_u": mapping["q_of_u"],
        "dqdu": mapping["dqdu_u_of_q"],
        **field_assets,
    }
    figure_rels = {
        key: path.resolve().relative_to(resolved).as_posix()
        for key, path in figure_files.items()
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "package": "v4_0_kinematic_geometry_core",
        "git_revision": _git_revision(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "no_inference_statement": NO_INFERENCE_STATEMENT,
        "grid": [GRID_N, GRID_N],
        "n_samples": len(rows),
        "mechanism_ids": list(MECHANISM_IDS),
        "files": list(REQUIRED_FILES),
        "figures": figure_rels,
        "allowed_output": str(allowed_v4_0_output_root()),
    }
    manifest_path = resolved / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    write_index_html(
        out_path=resolved / "index.html",
        manifest=manifest,
        identity_residuals=identity,
        figure_rels=figure_rels,
    )
    missing = [name for name in REQUIRED_FILES if not (resolved / name).is_file()]
    if missing:
        raise FileNotFoundError(f"smoke package missing required files: {missing}")
    return resolved


def default_output_path() -> Path:
    """Return the documented V4.0 smoke output directory."""
    return allowed_v4_0_output_root()


__all__ = [
    "FD_STEP",
    "GRID_N",
    "MECHANISM_IDS",
    "NO_INFERENCE_STATEMENT",
    "REQUIRED_FILES",
    "SCHEMA_VERSION",
    "V4_0_ALLOWED_OUTPUT_REL",
    "build_identity_residuals",
    "build_paired_arms",
    "collect_sample_rows",
    "default_output_path",
    "evaluate_sample",
    "generate_geometry_core_smoke",
    "shared_q_axes",
]
