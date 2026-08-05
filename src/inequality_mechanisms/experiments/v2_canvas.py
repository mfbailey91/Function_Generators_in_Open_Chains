"""HTML printout for a completed Version 2 run package.

Derived viewer: reads ``manifest.json``, trial/failure rows, branch and
diagnostic JSON, and ``figures/`` PNGs, then writes ``index.html`` beside
them without mutating ``trials.jsonl``.
"""

from __future__ import annotations

import html
import json
import math
from pathlib import Path
from typing import Any

from inequality_mechanisms.experiments.canvas import _figure_grid, _fmt_num
from inequality_mechanisms.experiments.registry import default_results_root

_CANVAS_NAME = "index.html"
_NULL_CONTROL_COSTS = frozenset({"uniform", "output_euclidean", "q_u_blend"})
_GEARBOX_IDS = (
    "equivalent_affine_gearbox",
    "span_matched_gearbox",
    "unit_gearbox",
)
_TRIAL_COLUMNS: tuple[tuple[str, str], ...] = (
    ("trial_index", "Trial"),
    ("pair_id", "Pair"),
    ("task_set_id", "Task"),
    ("alpha", "Alpha"),
    ("mechanism_id", "Mechanism"),
    ("algorithm", "Algorithm"),
    ("found", "Found"),
    ("optimal_cost", "Cost"),
    ("n_expanded", "Expanded"),
    ("n_generated", "Generated"),
    ("cost_norm_q", "Norm Q"),
    ("cost_norm_u", "Norm U"),
    ("path_length_u", "Path U"),
    ("path_length_q", "Path Q"),
    ("path_length_x", "Path X"),
)


class V2CanvasError(ValueError):
    """Raised when a Version 2 run package cannot be resolved or rendered."""


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise V2CanvasError(f"expected JSON object in {path}")
    return data


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _is_v2_run_dir(path: Path) -> bool:
    manifest_path = path / "manifest.json"
    if not manifest_path.is_file():
        return False
    try:
        manifest = _read_json(manifest_path)
    except (OSError, json.JSONDecodeError, V2CanvasError):
        return False
    if int(manifest.get("architecture_version", 0)) != 2:
        return False
    if manifest.get("package_kind") == "production_monte_carlo":
        return False
    return manifest.get("production_schema_version") is None


def resolve_v2_run_for_canvas(
    run_id_or_path: str | Path | None = None,
    *,
    results_root: Path | str | None = None,
) -> Path:
    """Resolve a Version 2 run directory for canvas generation.

    Parameters
    ----------
    run_id_or_path :
        Run directory, run id under ``results_root``, or ``None`` to select
        the latest Version 2 run.
    results_root :
        Parent of run directories (default: repository ``results/``).

    Returns
    -------
    Path
        Absolute path to a directory containing a Version 2 ``manifest.json``.

    Raises
    ------
    FileNotFoundError
        If no matching Version 2 run exists.
    V2CanvasError
        If the path exists but is not a Version 2 package.
    """
    root = Path(results_root) if results_root is not None else default_results_root()

    if run_id_or_path is None:
        if not root.is_dir():
            raise FileNotFoundError(f"no results directory at {root}")
        candidates = [p for p in root.iterdir() if p.is_dir() and _is_v2_run_dir(p)]
        if not candidates:
            raise FileNotFoundError(f"no Version 2 runs under {root}")

        def _recency(path: Path) -> tuple[str, float]:
            try:
                created_raw = _read_json(path / "manifest.json").get("created_at")
                created = str(created_raw or "")
            except (OSError, json.JSONDecodeError, V2CanvasError):
                created = ""
            return (created, path.stat().st_mtime)

        return max(candidates, key=_recency).resolve()

    path = Path(run_id_or_path)
    if not path.is_dir():
        candidate = root / str(run_id_or_path)
        if candidate.is_dir():
            path = candidate
        else:
            raise FileNotFoundError(f"Version 2 run not found: {run_id_or_path}")
    path = path.resolve()
    if not _is_v2_run_dir(path):
        raise V2CanvasError(
            f"not a Version 2 run package (missing architecture_version: 2 "
            f"manifest): {path}"
        )
    return path


def _null_control_status(
    *,
    sampling_domain: str,
    cost_type: str,
    trial_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compare fourbar vs gearbox rows when null-control conditions apply."""
    applicable = sampling_domain == "output" and str(cost_type) in _NULL_CONTROL_COSTS
    if cost_type == "q_u_blend":
        # Only alpha=1 rows are pure-Q null controls.
        trial_rows = [
            row
            for row in trial_rows
            if row.get("alpha") is None or float(row.get("alpha", -1.0)) == 1.0
        ]
        if not trial_rows:
            return {
                "applicable": True,
                "passed": None,
                "detail": "No alpha=1 q_u_blend rows found for null-control check.",
            }
    if not applicable:
        return {
            "applicable": False,
            "passed": None,
            "detail": (
                "Null-control equality applies only for shared uniform-Q "
                "sampling with output_euclidean, uniform, or q_u_blend(alpha=1)."
            ),
        }

    by_key: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in trial_rows:
        key = (
            row.get("pair_id"),
            row.get("task_set_id"),
            row.get("trial_index"),
            row.get("algorithm"),
            row.get("alpha"),
            row.get("mechanism_id"),
        )
        by_key[key] = row

    trial_algos = {
        (
            row.get("pair_id"),
            row.get("task_set_id"),
            row.get("trial_index"),
            row.get("algorithm"),
            row.get("alpha"),
        )
        for row in trial_rows
    }
    mismatches: list[str] = []
    compared = 0
    for pair_id, task_set_id, trial_index, algorithm, alpha in sorted(
        trial_algos,
        key=lambda x: (str(x[0]), str(x[1]), str(x[2]), str(x[3]), str(x[4])),
    ):
        a = by_key.get((pair_id, task_set_id, trial_index, algorithm, alpha, "fourbar"))
        if a is None:
            continue
        for gearbox_id in _GEARBOX_IDS:
            b = by_key.get(
                (pair_id, task_set_id, trial_index, algorithm, alpha, gearbox_id)
            )
            if b is None:
                continue
            compared += 1
            label = f"trial {trial_index} {algorithm} vs {gearbox_id}"
            checks = (
                ("found", a.get("found"), b.get("found")),
                ("start_node_id", a.get("start_node_id"), b.get("start_node_id")),
                ("goal_node_id", a.get("goal_node_id"), b.get("goal_node_id")),
                ("path_node_ids", a.get("path_node_ids"), b.get("path_node_ids")),
                (
                    "expanded_node_ids",
                    a.get("expanded_node_ids"),
                    b.get("expanded_node_ids"),
                ),
                ("n_expanded", a.get("n_expanded"), b.get("n_expanded")),
                ("n_generated", a.get("n_generated"), b.get("n_generated")),
                ("n_stale", a.get("n_stale"), b.get("n_stale")),
            )
            for name, va, vb in checks:
                if va != vb:
                    mismatches.append(f"{label}: {name} mismatch")
            ca = a.get("optimal_cost")
            cb = b.get("optimal_cost")
            if isinstance(ca, (int, float)) and isinstance(cb, (int, float)):
                if not (math.isfinite(float(ca)) and math.isfinite(float(cb))):
                    mismatches.append(f"{label}: non-finite optimal_cost")
                elif abs(float(ca) - float(cb)) > 1e-12:
                    mismatches.append(f"{label}: optimal_cost mismatch")
            elif ca != cb:
                mismatches.append(f"{label}: optimal_cost mismatch")

    if compared == 0:
        return {
            "applicable": True,
            "passed": None,
            "detail": "No paired fourbar/gearbox rows found to compare.",
        }
    if mismatches:
        return {
            "applicable": True,
            "passed": False,
            "detail": "; ".join(mismatches[:8]),
            "n_compared": compared,
            "n_mismatches": len(mismatches),
        }
    return {
        "applicable": True,
        "passed": True,
        "detail": (
            f"Paired rows match on cost, path, and expansions "
            f"({compared} four-bar×partner pairs)."
        ),
        "n_compared": compared,
        "n_mismatches": 0,
    }


def _pair_comparisons_html(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p class='muted'>No pair comparison rows.</p>"
    cols = (
        ("pair_id", "Pair"),
        ("task_set_id", "Task"),
        ("mechanism_b", "Partner"),
        ("alpha", "Alpha"),
        ("cost_delta", "Cost Δ"),
        ("expansion_delta", "Exp Δ"),
        ("node_jaccard", "Node Jac"),
        ("edge_jaccard", "Edge Jac"),
        ("identical_path", "Same path"),
        ("actuator_travel_ratio", "U ratio"),
        ("max_separation", "Max X sep"),
        ("null_control_equal", "Null α=1"),
    )
    parts = ["<table><thead><tr>"]
    for _, label in cols:
        parts.append(f"<th>{html.escape(label)}</th>")
    parts.append("</tr></thead><tbody>")
    for row in rows:
        parts.append("<tr>")
        for key, _ in cols:
            parts.append(f"<td>{_fmt_num(row.get(key))}</td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "\n".join(parts)


def _identity_control_html(trial_rows: list[dict[str, Any]]) -> str:
    """Summarize unit-gearbox invariance across alphas."""
    unit_rows = [
        r
        for r in trial_rows
        if isinstance(r, dict) and r.get("mechanism_id") == "unit_gearbox"
    ]
    if not unit_rows:
        return ""
    by_key: dict[tuple[Any, Any], list[dict[str, Any]]] = {}
    for row in unit_rows:
        key = (row.get("pair_id"), row.get("task_set_id"))
        by_key.setdefault(key, []).append(row)
    parts = [
        "<section>",
        "<h2>Identity control (unit gearbox)</h2>",
        "<p class='muted'>For q=u, edge integrals satisfy d_U=d_Q so blended "
        "cost is a positive scalar times d_Q. Expansions and d_U=d_Q must hold "
        "at every alpha; selected paths may differ among equal-cost optima.</p>",
        "<table><thead><tr>",
        "<th>Pair</th><th>Task</th><th>Alphas</th>"
        "<th>d_U=d_Q</th><th>Expansions invariant</th>"
        "<th>Paths</th>",
        "</tr></thead><tbody>",
    ]
    for (pair_id, task_set_id), rows in sorted(
        by_key.items(), key=lambda item: (str(item[0][0]), str(item[0][1]))
    ):
        found = [r for r in rows if r.get("found")]
        paths = {tuple(r.get("path_node_ids") or ()) for r in found}
        exps = {r.get("n_expanded") for r in found}
        alphas = sorted({float(r.get("alpha", -1)) for r in rows})
        du_eq = True
        for r in found:
            dq = r.get("cost_d_q")
            du = r.get("cost_d_u")
            if not isinstance(dq, (int, float)) or not isinstance(du, (int, float)):
                du_eq = False
                break
            if abs(float(dq) - float(du)) > 1e-9:
                du_eq = False
                break
        if len(paths) <= 1:
            path_label = "identical"
        else:
            path_label = "equal-cost ties"
        parts.append(
            "<tr>"
            f"<td>{html.escape(str(pair_id))}</td>"
            f"<td>{html.escape(str(task_set_id))}</td>"
            f"<td>{html.escape(', '.join(str(a) for a in alphas))}</td>"
            f"<td>{'yes' if du_eq else 'NO'}</td>"
            f"<td>{'yes' if len(exps) <= 1 else 'NO'}</td>"
            f"<td>{html.escape(path_label)}</td>"
            "</tr>"
        )
    parts.append("</tbody></table></section>")
    return "\n".join(parts)


_TASK_DISPLAY_NAMES: dict[str, str] = {
    "cross_range": "Cross-range",
}


def _filter_figures(
    figures: list[dict[str, Any]],
    *,
    kind: str,
) -> list[dict[str, Any]]:
    """Filter discovered figures by dashboard section kind."""
    out: list[dict[str, Any]] = []
    for fig in figures:
        src = str(fig.get("src") or "")
        name = str(fig.get("name") or "")
        if kind == "expansions":
            if "expansions" in name or "expansions" in src:
                out.append(fig)
        elif kind == "lattices":
            if "/paths/" in src:
                continue
            if "expansions" in name:
                continue
            if name.startswith("qu_"):
                continue
            if (
                name.endswith("q_lattice")
                or name.endswith("u_fourbar")
                or name.endswith("u_span_matched_gearbox")
                or name.endswith("u_unit_gearbox")
                or name.startswith("u_")
                or "/pair_" in src
            ):
                out.append(fig)
        elif kind == "transmission":
            if name == "qu_axis_maps":
                out.append(fig)
        elif kind == "paths_q":
            if "/paths/" in src and name.endswith("_q"):
                out.append(fig)
        elif kind == "paths_u":
            if "/paths/" in src and name.endswith("_u"):
                out.append(fig)
        elif kind == "paths_x":
            if "/paths/" in src and name.endswith("_x"):
                out.append(fig)
    return out


def _study_sections_html(payload: dict[str, Any]) -> str:
    """Render pair / task cards for the active shared-Q study."""
    manifest = (
        payload.get("manifest") if isinstance(payload.get("manifest"), dict) else {}
    )
    study = manifest.get("study") if isinstance(manifest.get("study"), dict) else None
    if study is None:
        return ""
    trial_rows = (
        payload.get("trial_rows") if isinstance(payload.get("trial_rows"), list) else []
    )
    objective = (
        manifest.get("objective") if isinstance(manifest.get("objective"), dict) else {}
    )
    u_only = str(objective.get("cost", "")) == "actuator_travel"
    task_ids = [str(x) for x in (study.get("task_template_ids") or [])]
    if not u_only:
        # V2.8 blend dashboard historically showed cross-range only.
        filtered = [
            tid
            for tid in task_ids
            if tid not in {"joint1_dominant", "joint2_dominant"}
        ]
        if filtered:
            task_ids = filtered
        elif "cross_range" in task_ids:
            task_ids = ["cross_range"]
    if not task_ids:
        task_ids = ["cross_range"]
    pair_ids = [str(x) for x in (study.get("mechanism_pair_ids") or [])]
    alphas = [float(a) for a in (study.get("alphas") or [])]
    if u_only:
        blurb = (
            "Hold output motions fixed; compare four-bar vs span-matched "
            "gearbox under raw actuator travel only (no Q term, alpha, or "
            "cost sweep)."
        )
    else:
        blurb = (
            "Hold output motions fixed; compare four-bar vs "
            "span-matched gearbox under normalized Q/U cost. When enabled, a "
            "unit-gearbox identity arm is the all-alpha sanity control."
        )
    parts = [
        "<section>",
        "<h2>Shared-Q paired study</h2>",
        f"<p class='muted'>{html.escape(blurb)}</p>",
        "<div class='kv'>",
        f"<div class='k'>Study</div><div>{html.escape(str(study.get('name', '')))}</div>",
        f"<div class='k'>Pairs</div><div>{html.escape(', '.join(pair_ids))}</div>",
        (
            "<div class='k'>Task</div><div>"
            f"{html.escape(', '.join(_TASK_DISPLAY_NAMES.get(t, t) for t in task_ids))}"
            "</div>"
        ),
        (
            "<div class='k'>Objective</div><div>"
            f"{html.escape('actuator travel only' if u_only else 'q_u_blend')}"
            "</div>"
        ),
    ]
    if not u_only:
        parts.append(
            "<div class='k'>Alphas</div><div>"
            f"{html.escape(', '.join(str(a) for a in alphas))}"
            "</div>"
        )
        parts.append(
            "<div class='k'>Unit gearbox</div><div>"
            f"{'included' if study.get('include_unit_gearbox', True) else 'off'}"
            "</div>"
        )
    parts.append("</div>")
    table_headers = (
        ("Mech", "Cost", "Exp", "Path U", "Norm U", "Path Q", "Path X")
        if u_only
        else ("α", "Mech", "Cost", "Exp", "Path U", "Path Q", "Path X")
    )
    for task_id in task_ids:
        display = _TASK_DISPLAY_NAMES.get(task_id, task_id)
        parts.append(f"<h3>Task: {html.escape(display)}</h3>")
        parts.append("<div class='grid'>")
        for pair_id in pair_ids:
            rows = [
                r
                for r in trial_rows
                if r.get("task_set_id") == task_id and r.get("pair_id") == pair_id
            ]
            if not rows:
                rows = [
                    r
                    for r in trial_rows
                    if r.get("pair_id") == pair_id
                    and (
                        r.get("task_set_id") in (None, task_id)
                        or r.get("task_set_id") == task_id
                    )
                ]
            if not rows:
                continue
            parts.append("<div>")
            parts.append(f"<h3>{html.escape(pair_id)}</h3>")
            parts.append("<table><thead><tr>")
            for label in table_headers:
                parts.append(f"<th>{label}</th>")
            parts.append("</tr></thead><tbody>")
            for row in sorted(
                rows,
                key=lambda r: (
                    float(r.get("alpha") if r.get("alpha") is not None else -1),
                    str(r.get("mechanism_id")),
                ),
            ):
                if u_only:
                    parts.append(
                        "<tr>"
                        f"<td>{html.escape(str(row.get('mechanism_id', '')))}</td>"
                        f"<td>{_fmt_num(row.get('optimal_cost'))}</td>"
                        f"<td>{_fmt_num(row.get('n_expanded'))}</td>"
                        f"<td>{_fmt_num(row.get('path_length_u'))}</td>"
                        f"<td>{_fmt_num(row.get('cost_norm_u'))}</td>"
                        f"<td>{_fmt_num(row.get('path_length_q'))}</td>"
                        f"<td>{_fmt_num(row.get('path_length_x'))}</td>"
                        "</tr>"
                    )
                else:
                    parts.append(
                        "<tr>"
                        f"<td>{_fmt_num(row.get('alpha'))}</td>"
                        f"<td>{html.escape(str(row.get('mechanism_id', '')))}</td>"
                        f"<td>{_fmt_num(row.get('optimal_cost'))}</td>"
                        f"<td>{_fmt_num(row.get('n_expanded'))}</td>"
                        f"<td>{_fmt_num(row.get('path_length_u'))}</td>"
                        f"<td>{_fmt_num(row.get('path_length_q'))}</td>"
                        f"<td>{_fmt_num(row.get('path_length_x'))}</td>"
                        "</tr>"
                    )
            parts.append("</tbody></table></div>")
        parts.append("</div>")
    parts.append("</section>")
    return "\n".join(parts)


def _trial_table_html(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p class='muted'>No trial rows.</p>"
    parts = ["<table><thead><tr>"]
    for _, label in _TRIAL_COLUMNS:
        parts.append(f"<th>{html.escape(label)}</th>")
    parts.append("</tr></thead><tbody>")
    for row in rows:
        parts.append("<tr>")
        for key, _ in _TRIAL_COLUMNS:
            parts.append(f"<td>{_fmt_num(row.get(key))}</td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "\n".join(parts)


def _failures_html(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p class='muted'>No rejected tasks.</p>"
    parts = [
        "<table><thead><tr>",
        "<th>Trial</th><th>Mechanism</th><th>Reason</th>"
        "<th>Start resid</th><th>Goal resid</th>",
        "</tr></thead><tbody>",
    ]
    for row in rows:
        parts.append(
            "<tr>"
            f"<td>{_fmt_num(row.get('trial_index'))}</td>"
            f"<td>{html.escape(str(row.get('mechanism_id', '')))}</td>"
            f"<td>{html.escape(str(row.get('rejection_reason', '')))}</td>"
            f"<td>{_fmt_num(row.get('start_residual_norm'))}</td>"
            f"<td>{_fmt_num(row.get('goal_residual_norm'))}</td>"
            "</tr>"
        )
    parts.append("</tbody></table>")
    return "\n".join(parts)


def _branch_sections(branches: dict[str, Any]) -> str:
    if not branches:
        return "<p class='muted'>No branch payloads.</p>"
    parts: list[str] = []
    for mechanism_id in sorted(branches.keys()):
        data = branches[mechanism_id]
        cert = data.get("certificate") if isinstance(data, dict) else None
        if not isinstance(cert, dict):
            cert = {}
        parts.append(f"<h3>{html.escape(mechanism_id)}</h3>")
        parts.append("<table>")
        for label, key in (
            ("branch_id", "branch_id"),
            ("method", "certification_method"),
            ("samples/axis", "certification_samples_per_axis"),
            ("min |gain|", "min_abs_gain"),
            ("max fwd-inv residual", "max_forward_inverse_residual"),
            ("max inv-fwd residual", "max_inverse_forward_residual"),
        ):
            if key == "branch_id":
                value = data.get("branch_id") if isinstance(data, dict) else None
                if value is None and isinstance(data, dict):
                    # branch_id may only live on the OperatingBranch object;
                    # serialize often stores it separately in manifest.
                    value = "(see manifest)"
            else:
                value = cert.get(key)
            parts.append(
                f"<tr><th>{html.escape(label)}</th><td>{_fmt_num(value)}</td></tr>"
            )
        if isinstance(data, dict) and "branch_id" not in data:
            # Prefer short hash from certificate file name context later.
            pass
        parts.append("</table>")
        parts.append(
            "<details><summary>Branch JSON</summary>"
            f"<pre>{html.escape(json.dumps(data, indent=2, sort_keys=True))}</pre>"
            "</details>"
        )
    return "\n".join(parts)


def _diagnostics_sections(diagnostics: dict[str, Any]) -> str:
    if not diagnostics:
        return "<p class='muted'>No diagnostics payloads.</p>"
    parts: list[str] = []
    for mechanism_id in sorted(diagnostics.keys()):
        data = diagnostics[mechanism_id]
        parts.append(f"<h3>{html.escape(mechanism_id)}</h3>")
        parts.append(
            f"<pre>{html.escape(json.dumps(data, indent=2, sort_keys=True))}</pre>"
        )
    return "\n".join(parts)


def collect_v2_canvas_payload(run_dir: Path | str) -> dict[str, Any]:
    """Collect Version 2 run artifacts into a render payload."""
    path = Path(run_dir).resolve()
    if not _is_v2_run_dir(path):
        raise V2CanvasError(f"not a Version 2 run package: {path}")

    manifest = _read_json(path / "manifest.json")
    trial_rows = _read_jsonl(path / "trials.jsonl")
    failure_rows = _read_jsonl(path / "failures.jsonl")
    pair_comparisons = _read_jsonl(path / "pair_comparisons.jsonl")
    pair_invariants: list[dict[str, Any]] = []
    inv_path = path / "pair_invariants.json"
    if inv_path.is_file():
        raw_inv = json.loads(inv_path.read_text(encoding="utf-8"))
        if isinstance(raw_inv, list):
            pair_invariants = [x for x in raw_inv if isinstance(x, dict)]

    branches: dict[str, Any] = {}
    branches_dir = path / "branches"
    if branches_dir.is_dir():
        for file in sorted(branches_dir.glob("*.json")):
            branches[file.stem] = _read_json(file)

    diagnostics: dict[str, Any] = {}
    diagnostics_dir = path / "diagnostics"
    if diagnostics_dir.is_dir():
        for file in sorted(diagnostics_dir.glob("*.json")):
            diagnostics[file.stem] = _read_json(file)

    figures: list[dict[str, str]] = []
    figures_dir = path / "figures"
    if figures_dir.is_dir():
        for file in sorted(figures_dir.rglob("*.png")):
            rel = file.relative_to(path).as_posix()
            figures.append(
                {
                    "name": file.stem,
                    "src": rel,
                    "caption": file.stem.replace("_", " "),
                }
            )

    raw_objective = manifest.get("objective")
    objective = raw_objective if isinstance(raw_objective, dict) else {}
    cost_type = str(objective.get("cost") or "")
    sampling_domain = str(manifest.get("sampling_domain") or "")
    if trial_rows and not cost_type:
        cost_type = str(trial_rows[0].get("cost_type") or "")

    # Attach branch_id from manifest when branch JSON lacks it.
    mech_manifest = manifest.get("mechanisms")
    if isinstance(mech_manifest, dict):
        for mechanism_id, meta in mech_manifest.items():
            if mechanism_id in branches and isinstance(branches[mechanism_id], dict):
                if "branch_id" not in branches[mechanism_id] and isinstance(meta, dict):
                    if "branch_id" in meta:
                        branches[mechanism_id] = {
                            **branches[mechanism_id],
                            "branch_id": meta["branch_id"],
                        }

    config_text = ""
    config_path = path / "config.yaml"
    if config_path.is_file():
        config_text = config_path.read_text(encoding="utf-8")

    return {
        "run_dir": str(path),
        "run_id": manifest.get("run_id", path.name),
        "manifest": manifest,
        "config_yaml": config_text,
        "trial_rows": trial_rows,
        "failure_rows": failure_rows,
        "pair_comparisons": pair_comparisons,
        "pair_invariants": pair_invariants,
        "branches": branches,
        "diagnostics": diagnostics,
        "figures": figures,
        "null_control": _null_control_status(
            sampling_domain=sampling_domain,
            cost_type=cost_type,
            trial_rows=trial_rows,
        ),
    }


def render_v2_canvas_html(payload: dict[str, Any]) -> str:
    """Render a dark diagnostic HTML printout for a Version 2 run."""
    raw_manifest = payload.get("manifest")
    manifest = raw_manifest if isinstance(raw_manifest, dict) else {}
    run_id = html.escape(str(payload.get("run_id", "")))
    revision = (
        manifest.get("revision") if isinstance(manifest.get("revision"), dict) else {}
    )
    objective = (
        manifest.get("objective") if isinstance(manifest.get("objective"), dict) else {}
    )
    null_control = (
        payload.get("null_control")
        if isinstance(payload.get("null_control"), dict)
        else {}
    )
    trial_rows = (
        payload.get("trial_rows") if isinstance(payload.get("trial_rows"), list) else []
    )
    failure_rows = (
        payload.get("failure_rows")
        if isinstance(payload.get("failure_rows"), list)
        else []
    )
    figures = payload.get("figures") if isinstance(payload.get("figures"), list) else []
    branches = (
        payload.get("branches") if isinstance(payload.get("branches"), dict) else {}
    )
    diagnostics = (
        payload.get("diagnostics")
        if isinstance(payload.get("diagnostics"), dict)
        else {}
    )

    passed = null_control.get("passed")
    if passed is True:
        null_class = "pass"
        null_label = "PASS"
    elif passed is False:
        null_class = "fail"
        null_label = "FAIL"
    else:
        null_class = "muted"
        null_label = "N/A"

    git_commit = revision.get("git_commit") or revision.get("git_describe") or "—"
    dirty = revision.get("git_dirty")
    dirty_label = (
        "dirty" if dirty is True else ("clean" if dirty is False else "unknown")
    )

    arch_v = html.escape(str(manifest.get("architecture_version", 2)))
    schema_v = html.escape(str(manifest.get("result_schema_version", "—")))
    sampling = html.escape(str(manifest.get("sampling_domain", "—")))
    cost = html.escape(str(objective.get("cost", "—")))
    heuristic = html.escape(str(objective.get("heuristic", "—")))
    algorithms = html.escape(
        ", ".join(str(a) for a in (manifest.get("algorithms") or []))
    )
    created = html.escape(str(manifest.get("created_at", "—")))
    commit_esc = html.escape(str(git_commit))
    dirty_esc = html.escape(dirty_label)
    null_detail = html.escape(str(null_control.get("detail", "")))
    config_yaml = html.escape(str(payload.get("config_yaml") or ""))
    manifest_json = html.escape(json.dumps(manifest, indent=2, sort_keys=True))
    trials_html = _trial_table_html(trial_rows)
    failures_html = _failures_html(failure_rows)
    branches_html = _branch_sections(branches)
    diagnostics_html = _diagnostics_sections(diagnostics)
    study_html = _study_sections_html(payload)
    pair_rows = (
        payload.get("pair_comparisons")
        if isinstance(payload.get("pair_comparisons"), list)
        else []
    )
    pair_html = _pair_comparisons_html(pair_rows)
    u_only = str(objective.get("cost", "")) == "actuator_travel"
    identity_html = "" if u_only else _identity_control_html(trial_rows)
    onset = manifest.get("divergence_onset_by_alpha")
    if u_only:
        onset_html = (
            "<p class='muted'>No alpha sweep — path divergence onset vs alpha "
            "does not apply for actuator-travel-only runs.</p>"
        )
    elif isinstance(onset, dict):
        onset_html = (
            f"<pre>{html.escape(json.dumps(onset, indent=2, sort_keys=True))}</pre>"
        )
    else:
        onset_html = "<p class='muted'>No divergence-onset summary.</p>"

    expansions_html = _figure_grid(
        _filter_figures(figures, kind="expansions"),
        empty="No expansion figures.",
    )
    lattices_html = _figure_grid(
        _filter_figures(figures, kind="lattices"),
        empty="No shared Q/U lattice figures.",
    )
    transmission_html = _figure_grid(
        _filter_figures(figures, kind="transmission"),
        empty="No transmission q(u) figures.",
    )
    paths_q_html = _figure_grid(
        _filter_figures(figures, kind="paths_q"),
        empty="No Q-path overlays.",
    )
    paths_u_html = _figure_grid(
        _filter_figures(figures, kind="paths_u"),
        empty="No U-path overlays.",
    )
    paths_x_html = _figure_grid(
        _filter_figures(figures, kind="paths_x"),
        empty="No Cartesian path figures.",
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>Version 2 run — {run_id}</title>
<style>
:root {{
  --bg: #0f1419;
  --panel: #1a2332;
  --text: #e7ecf3;
  --muted: #9aa7b8;
  --accent: #6cb6ff;
  --pass: #3dd68c;
  --fail: #f07178;
  --line: #2a3545;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.45;
}}
header {{
  padding: 1.5rem 2rem;
  border-bottom: 1px solid var(--line);
  background: linear-gradient(180deg, #162033, var(--bg));
}}
header h1 {{ margin: 0 0 0.35rem; font-size: 1.6rem; }}
header .meta {{ color: var(--muted); font-size: 0.95rem; }}
main {{ padding: 1.25rem 2rem 3rem; max-width: 1400px; }}
section {{
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 1rem 1.25rem;
  margin: 1rem 0;
}}
h2 {{ margin: 0 0 0.75rem; font-size: 1.15rem; color: var(--accent); }}
h3 {{ margin: 1rem 0 0.5rem; font-size: 1rem; }}
.muted {{ color: var(--muted); }}
.kv {{ display: grid; grid-template-columns: 12rem 1fr; gap: 0.35rem 1rem; }}
.kv div {{ border-bottom: 1px solid var(--line); padding: 0.2rem 0; }}
.kv .k {{ color: var(--muted); }}
table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}}
th, td {{
  border-bottom: 1px solid var(--line);
  text-align: left;
  padding: 0.35rem 0.5rem;
  vertical-align: top;
}}
th {{ color: var(--muted); font-weight: 600; }}
.pass {{ color: var(--pass); font-weight: 700; }}
.fail {{ color: var(--fail); font-weight: 700; }}
.grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 1rem;
}}
figure {{
  margin: 0;
  background: #0c1118;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 0.5rem;
}}
figure img {{ width: 100%; height: auto; display: block; }}
figcaption {{ color: var(--muted); font-size: 0.85rem; margin-top: 0.4rem; }}
pre {{
  overflow: auto;
  background: #0c1118;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 0.75rem;
  font-size: 0.8rem;
}}
details {{ margin-top: 0.75rem; }}
summary {{ cursor: pointer; color: var(--accent); }}
</style>
</head>
<body>
<header>
  <h1>Version 2 experiment printout</h1>
  <div class="meta">
    run_id=<strong>{run_id}</strong>
    · architecture_version={arch_v}
    · result_schema_version={schema_v}
  </div>
</header>
<main>
  <section>
    <h2>Run summary</h2>
    <div class="kv">
      <div class="k">Seed</div><div>{_fmt_num(manifest.get("seed"))}</div>
      <div class="k">Sampling domain</div><div>{sampling}</div>
      <div class="k">Objective cost</div><div>{cost}</div>
      <div class="k">Heuristic</div><div>{heuristic}</div>
      <div class="k">Algorithms</div><div>{algorithms}</div>
      <div class="k">Trial rows</div>
      <div>{_fmt_num(manifest.get("n_trial_rows"))}</div>
      <div class="k">Failure rows</div>
      <div>{_fmt_num(manifest.get("n_failure_rows"))}</div>
      <div class="k">Created</div><div>{created}</div>
      <div class="k">Revision</div>
      <div>{commit_esc} ({dirty_esc})</div>
    </div>
  </section>

  {study_html}

  <section>
    <h2>Expansions</h2>
    <p class="muted">Node expansions across pairs for four-bar, span-matched gearbox, and unit gearbox when present.</p>
    {expansions_html}
  </section>

  <section>
    <h2>Shared Q and U lattices</h2>
    <p class="muted">Common output graph and mechanism-specific actuator embeddings.</p>
    {lattices_html}
  </section>

  <section>
    <h2>Transmission maps q(u)</h2>
    <p class="muted">Per-pair axis transmission: for each arm, q_i(u_i) over its
    own certified u extent (map is fixed per pair; independent of alpha/task).</p>
    {transmission_html}
  </section>

  <section>
    <h2>Q paths</h2>
    <p class="muted">Selected paths and expansions on the shared output lattice.</p>
    {paths_q_html}
  </section>

  <section>
    <h2>U paths</h2>
    <p class="muted">Selected paths in each mechanism's actuator embedding.</p>
    {paths_u_html}
  </section>

  <section>
    <h2>Cartesian paths</h2>
    <p class="muted">End-effector trajectories with start and goal poses.</p>
    {paths_x_html}
  </section>

  <section>
    <h2>Null-control gate</h2>
    <p class="{null_class}">{null_label}</p>
    <p class="muted">{null_detail}</p>
  </section>

  {identity_html}

  <section>
    <h2>Paired comparisons</h2>
    {pair_html}
    <h3>{"Path notes" if u_only else "Path divergence onset vs alpha"}</h3>
    {onset_html}
  </section>

  <section>
    <h2>Trials</h2>
    {trials_html}
  </section>

  <section>
    <h2>Failures</h2>
    {failures_html}
  </section>

  <section>
    <h2>Branch certificates</h2>
    {branches_html}
  </section>

  <section>
    <h2>Diagnostics</h2>
    {diagnostics_html}
  </section>

  <section>
    <h2>Config</h2>
    <details>
      <summary>config.yaml</summary>
      <pre>{config_yaml}</pre>
    </details>
  </section>

  <section>
    <h2>Manifest</h2>
    <details>
      <summary>manifest.json</summary>
      <pre>{manifest_json}</pre>
    </details>
  </section>
</main>
</body>
</html>
"""


def write_v2_canvas(
    run_dir: Path | str,
    *,
    results_root: Path | str | None = None,
    filename: str = _CANVAS_NAME,
) -> Path:
    """Write ``index.html`` consolidating a Version 2 run package.

    Regenerating the canvas does not mutate ``trials.jsonl`` or other raw
    result files.
    """
    del results_root  # Reserved for CLI symmetry; run_dir is authoritative.
    path = Path(run_dir).resolve()
    payload = collect_v2_canvas_payload(path)
    html_text = render_v2_canvas_html(payload)
    out = path / filename
    out.write_text(html_text, encoding="utf-8")
    return out.resolve()
