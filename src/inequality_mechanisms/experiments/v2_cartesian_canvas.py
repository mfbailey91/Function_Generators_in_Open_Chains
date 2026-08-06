"""HTML printout for Experiment B Cartesian goal-region run packages.

Derived viewer: reads smoke or calibration artifacts and writes ``index.html``
beside them without mutating trials, candidates, or decision JSON.
"""

from __future__ import annotations

import html
import json
import math
import statistics
from pathlib import Path
from typing import Any

from inequality_mechanisms.experiments.registry import default_results_root

_CANVAS_NAME = "index.html"


class CartesianCanvasError(ValueError):
    """Raised when an Experiment B run package cannot be rendered."""


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise CartesianCanvasError(f"expected JSON object in {path}")
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


def _fmt(value: Any, *, digits: int = 4) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not math.isfinite(number):
        return str(value)
    return f"{number:.{digits}g}"


def is_cartesian_goal_region_run_dir(path: Path | str) -> bool:
    """Return True when ``path`` looks like an Experiment B package."""
    run_dir = Path(path)
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.is_file():
        return False
    try:
        manifest = _read_json(manifest_path)
    except (OSError, json.JSONDecodeError, CartesianCanvasError):
        return False
    if int(manifest.get("experiment_b_schema_version", -1)) != 1:
        return False
    if "cartesian_domain" not in manifest:
        return False
    return True


def resolve_cartesian_run_for_canvas(
    run_id_or_path: str | Path | None = None,
    *,
    results_root: Path | str | None = None,
) -> Path:
    """Resolve an Experiment B run directory for canvas generation."""
    root = Path(results_root) if results_root is not None else default_results_root()
    if run_id_or_path is None:
        if not root.is_dir():
            raise FileNotFoundError(f"no results directory at {root}")
        candidates = [
            p for p in root.iterdir() if p.is_dir() and is_cartesian_goal_region_run_dir(p)
        ]
        if not candidates:
            raise FileNotFoundError(f"no Experiment B runs under {root}")

        def _recency(path: Path) -> tuple[str, float]:
            created = ""
            try:
                created = str(_read_json(path / "manifest.json").get("created_at") or "")
            except (OSError, json.JSONDecodeError, CartesianCanvasError):
                created = ""
            return (created, path.stat().st_mtime)

        return max(candidates, key=_recency).resolve()

    path = Path(run_id_or_path)
    if not path.is_dir():
        candidate = root / str(run_id_or_path)
        if candidate.is_dir():
            path = candidate
        else:
            raise FileNotFoundError(f"Experiment B run not found: {run_id_or_path}")
    path = path.resolve()
    if not is_cartesian_goal_region_run_dir(path):
        raise CartesianCanvasError(f"not an Experiment B run package: {path}")
    return path


def _mean(values: list[float]) -> float | None:
    return float(statistics.fmean(values)) if values else None


def _smoke_summary(
    trial_rows: list[dict[str, Any]],
    failure_rows: list[dict[str, Any]],
    task_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    n_tasks = len(task_rows) if task_rows else (
        len({str(r.get("task_id")) for r in trial_rows + failure_rows})
    )
    accepted_tasks = sorted({str(r.get("task_id")) for r in trial_rows if r.get("found")})
    rejection_counts: dict[str, int] = {}
    for row in failure_rows:
        reason = str(row.get("failure_or_exclusion_reason") or "unknown")
        rejection_counts[reason] = rejection_counts.get(reason, 0) + 1

    agreement_rows = 0
    disagreement = 0
    by_task_mech: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    for row in trial_rows:
        key = (str(row.get("task_id")), str(row.get("mechanism_id")))
        by_task_mech.setdefault(key, {})[str(row.get("algorithm"))] = row
    for pair in by_task_mech.values():
        if "dijkstra" in pair and "astar" in pair:
            agreement_rows += 1
            d = pair["dijkstra"]
            a = pair["astar"]
            same_found = bool(d.get("found")) == bool(a.get("found"))
            same_cost = False
            if d.get("cost") is not None and a.get("cost") is not None:
                same_cost = abs(float(d["cost"]) - float(a["cost"])) <= 1e-10
            same_goal = d.get("selected_goal_node_id") == a.get("selected_goal_node_id")
            if not (same_found and same_cost and same_goal):
                disagreement += 1

    dijkstra = [r for r in trial_rows if r.get("algorithm") == "dijkstra" and r.get("found")]
    astar = [r for r in trial_rows if r.get("algorithm") == "astar" and r.get("found")]
    return {
        "n_tasks": n_tasks,
        "n_accepted_tasks": len(accepted_tasks),
        "n_failure_rows": len(failure_rows),
        "n_trial_rows": len(trial_rows),
        "attachment_rate": (
            float(len(accepted_tasks)) / float(n_tasks) if n_tasks else 0.0
        ),
        "rejection_counts": rejection_counts,
        "oracle_pairs": agreement_rows,
        "oracle_disagreements": disagreement,
        "mean_expanded_dijkstra": _mean([float(r["n_expanded"]) for r in dijkstra]),
        "mean_expanded_astar": _mean([float(r["n_expanded"]) for r in astar]),
        "mean_cost_dijkstra": _mean([float(r["cost"]) for r in dijkstra]),
        "mean_selected_goal_residual": _mean(
            [
                float(r["selected_goal_residual_x"])
                for r in trial_rows
                if r.get("selected_goal_residual_x") is not None
            ]
        ),
        "start_ik_families": sorted(
            {
                str(r.get("selected_start_ik_family"))
                for r in trial_rows
                if r.get("selected_start_ik_family")
            }
        ),
    }


def _calibration_summary(
    candidate_rows: list[dict[str, Any]],
    radius_decision: dict[str, Any],
    resolution_decision: dict[str, Any],
    attachment_decision: dict[str, Any],
    chosen: dict[str, Any],
) -> dict[str, Any]:
    return {
        "n_candidate_rows": len(candidate_rows),
        "chosen": chosen,
        "radius_reason": radius_decision.get("reason"),
        "resolution_reason": resolution_decision.get("reason"),
        "attachment_decision": attachment_decision.get("decision"),
        "attachment_policy": attachment_decision.get("policy_id"),
        "chosen_attachment_rate": radius_decision.get("chosen_attachment_rate"),
    }


def load_cartesian_canvas_payload(run_dir: Path | str) -> dict[str, Any]:
    """Load a smoke or calibration Experiment B package into a canvas payload."""
    path = resolve_cartesian_run_for_canvas(run_dir)
    manifest = _read_json(path / "manifest.json")
    config = _read_json(path / "config.json") if (path / "config.json").is_file() else {}
    stage = str(manifest.get("stage") or config.get("stage") or "smoke")
    trial_rows = _read_jsonl(path / "trials.jsonl")
    failure_rows = _read_jsonl(path / "failures.jsonl")
    candidate_rows = _read_jsonl(path / "candidate_rows.jsonl")
    task_rows: list[dict[str, Any]] = []
    tasks_path = path / "tasks.json"
    if tasks_path.is_file():
        raw_tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
        if isinstance(raw_tasks, list):
            task_rows = [t for t in raw_tasks if isinstance(t, dict)]

    radius_decision = (
        _read_json(path / "cartesian_radius_decision.json")
        if (path / "cartesian_radius_decision.json").is_file()
        else {}
    )
    resolution_decision = (
        _read_json(path / "cartesian_resolution_decision.json")
        if (path / "cartesian_resolution_decision.json").is_file()
        else {}
    )
    attachment_decision = (
        _read_json(path / "cartesian_start_attachment_decision.json")
        if (path / "cartesian_start_attachment_decision.json").is_file()
        else {}
    )
    chosen = (
        manifest.get("chosen")
        if isinstance(manifest.get("chosen"), dict)
        else (config.get("chosen") if isinstance(config.get("chosen"), dict) else {})
    )

    payload: dict[str, Any] = {
        "run_dir": str(path),
        "run_id": manifest.get("run_id", path.name),
        "stage": stage,
        "manifest": manifest,
        "config": config,
        "domain": manifest.get("cartesian_domain")
        if isinstance(manifest.get("cartesian_domain"), dict)
        else {},
        "trial_rows": trial_rows,
        "failure_rows": failure_rows,
        "task_rows": task_rows,
        "candidate_rows": candidate_rows,
        "radius_decision": radius_decision,
        "resolution_decision": resolution_decision,
        "attachment_decision": attachment_decision,
        "chosen": chosen,
    }
    if stage == "calibration":
        payload["summary"] = _calibration_summary(
            candidate_rows,
            radius_decision,
            resolution_decision,
            attachment_decision,
            chosen,
        )
    else:
        payload["summary"] = _smoke_summary(trial_rows, failure_rows, task_rows)
    return payload


def _kv_html(items: list[tuple[str, Any]]) -> str:
    rows = []
    for key, value in items:
        rows.append(
            "<div class='k'>"
            f"{html.escape(key)}</div><div>{html.escape(_fmt(value) if not isinstance(value, str) else value)}</div>"
        )
    return "<div class='kv'>" + "".join(rows) + "</div>"


def _table_html(
    headers: list[str],
    rows: list[list[Any]],
    *,
    empty: str,
) -> str:
    if not rows:
        return f"<p class='muted'>{html.escape(empty)}</p>"
    head = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    body_parts: list[str] = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(_fmt(c) if not isinstance(c, str) else c)}</td>" for c in row)
        body_parts.append(f"<tr>{cells}</tr>")
    return (
        "<div class='table-wrap'><table><thead><tr>"
        f"{head}</tr></thead><tbody>{''.join(body_parts)}</tbody></table></div>"
    )


def _domain_section(domain: dict[str, Any]) -> str:
    return (
        "<section><h2>Cartesian domain</h2>"
        + _kv_html(
            [
                ("domain_id", str(domain.get("domain_id", "—"))),
                ("radial", f"[{_fmt(domain.get('radial_min'))}, {_fmt(domain.get('radial_max'))}]"),
                ("angle", f"[{_fmt(domain.get('angle_min'))}, {_fmt(domain.get('angle_max'))}]"),
                ("start_tolerance", domain.get("start_tolerance")),
                ("goal_radius", domain.get("goal_radius")),
                ("min_start_goal_separation", domain.get("min_start_goal_separation")),
                ("L1 / L2", f"{_fmt(domain.get('L1'))} / {_fmt(domain.get('L2'))}"),
            ]
        )
        + "</section>"
    )


def _smoke_sections(payload: dict[str, Any]) -> str:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    rejection = summary.get("rejection_counts") if isinstance(summary.get("rejection_counts"), dict) else {}
    reject_rows = [[k, v] for k, v in sorted(rejection.items(), key=lambda kv: (-int(kv[1]), kv[0]))]
    trial_rows = payload.get("trial_rows") if isinstance(payload.get("trial_rows"), list) else []
    display_trials: list[list[Any]] = []
    for row in trial_rows:
        display_trials.append(
            [
                str(row.get("task_id", "")),
                str(row.get("mechanism_id", "")),
                str(row.get("algorithm", "")),
                bool(row.get("found")),
                row.get("cost"),
                row.get("n_expanded"),
                row.get("goal_set_size"),
                row.get("selected_goal_node_id"),
                row.get("selected_goal_residual_x"),
                str(row.get("selected_start_ik_family") or "—"),
            ]
        )
    oracle_ok = int(summary.get("oracle_disagreements") or 0) == 0
    oracle_label = "PASS" if oracle_ok else "FAIL"
    oracle_class = "pass" if oracle_ok else "fail"
    return f"""
<section>
  <h2>Smoke coverage</h2>
  <p class="muted">Correctness package only — not population inference.</p>
  {_kv_html([
      ("tasks", summary.get("n_tasks")),
      ("accepted tasks", summary.get("n_accepted_tasks")),
      ("attachment rate", summary.get("attachment_rate")),
      ("trial rows", summary.get("n_trial_rows")),
      ("failure rows", summary.get("n_failure_rows")),
      ("Dijkstra/A* oracle pairs", summary.get("oracle_pairs")),
      ("oracle disagreements", summary.get("oracle_disagreements")),
      ("mean expanded (Dijkstra)", summary.get("mean_expanded_dijkstra")),
      ("mean expanded (A*)", summary.get("mean_expanded_astar")),
      ("mean selected-goal residual", summary.get("mean_selected_goal_residual")),
      ("start IK families", ", ".join(summary.get("start_ik_families") or []) or "—"),
  ])}
  <p>Dijkstra/A* cost+goal agreement: <span class="{oracle_class}">{html.escape(oracle_label)}</span></p>
</section>
<section>
  <h2>Rejection taxonomy</h2>
  {_table_html(["reason", "count"], reject_rows, empty="No rejection rows.")}
</section>
<section>
  <h2>Trials</h2>
  {_table_html(
      ["task", "mechanism", "algorithm", "found", "cost", "expanded", "goal set", "selected goal", "goal residual", "start IK"],
      display_trials,
      empty="No trial rows.",
  )}
</section>
"""


def _calibration_sections(payload: dict[str, Any]) -> str:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    chosen = payload.get("chosen") if isinstance(payload.get("chosen"), dict) else {}
    candidates = (
        payload.get("candidate_rows")
        if isinstance(payload.get("candidate_rows"), list)
        else []
    )
    radius_decision = (
        payload.get("radius_decision")
        if isinstance(payload.get("radius_decision"), dict)
        else {}
    )
    resolution_decision = (
        payload.get("resolution_decision")
        if isinstance(payload.get("resolution_decision"), dict)
        else {}
    )

    finest = max((int(r.get("shape_n", 0)) for r in candidates), default=0)
    radius_rows: list[list[Any]] = []
    for row in sorted(
        [r for r in candidates if int(r.get("shape_n", -1)) == finest],
        key=lambda r: float(r.get("goal_radius", 0.0)),
    ):
        radius_rows.append(
            [
                row.get("goal_radius"),
                row.get("attachment_rate"),
                row.get("empty_start_rate"),
                row.get("empty_goal_rate"),
                row.get("n_paired_search_outcomes"),
                row.get("mean_paired_delta_expansions"),
            ]
        )

    chosen_radius = float(chosen.get("goal_radius", float("nan")))
    resolution_rows: list[list[Any]] = []
    for row in sorted(
        [
            r
            for r in candidates
            if abs(float(r.get("goal_radius", -1.0)) - chosen_radius) < 1e-12
        ],
        key=lambda r: int(r.get("shape_n", 0)),
    ):
        card = row.get("goal_set_cardinality") if isinstance(row.get("goal_set_cardinality"), dict) else {}
        resolution_rows.append(
            [
                row.get("shape_n"),
                row.get("attachment_rate"),
                row.get("mean_paired_delta_expansions"),
                row.get("mean_paired_delta_cost"),
                card.get("mean"),
                card.get("max"),
                row.get("n_paired_search_outcomes"),
            ]
        )

    all_candidate_rows = [
        [
            r.get("goal_radius"),
            r.get("shape_n"),
            r.get("attachment_rate"),
            r.get("empty_start_rate"),
            r.get("empty_goal_rate"),
            r.get("mean_paired_delta_expansions"),
            r.get("n_paired_search_outcomes"),
        ]
        for r in sorted(
            candidates,
            key=lambda row: (float(row.get("goal_radius", 0.0)), int(row.get("shape_n", 0))),
        )
    ]

    return f"""
<section>
  <h2>Calibration decisions</h2>
  <p class="muted">V2B-005 tooling output — production population inference still held on crossed statistics.</p>
  {_kv_html([
      ("chosen goal_radius", chosen.get("goal_radius")),
      ("chosen start_tolerance", chosen.get("start_tolerance")),
      ("chosen separation", chosen.get("min_start_goal_separation")),
      ("chosen shape_n", chosen.get("production_shape_n")),
      ("start attachment", chosen.get("start_attachment_decision")),
      ("radius reason", str(summary.get("radius_reason") or "—")),
      ("resolution reason", str(summary.get("resolution_reason") or "—")),
      ("attachment at chosen radius", summary.get("chosen_attachment_rate")),
      ("candidate rows", summary.get("n_candidate_rows")),
      ("attachment policy", str(summary.get("attachment_policy") or "—")),
  ])}
</section>
<section>
  <h2>Radius ladder (finest grid n={html.escape(str(finest))})</h2>
  {_table_html(
      ["goal_radius", "attachment", "empty start", "empty goal", "paired searches", "mean Δ expansions"],
      radius_rows,
      empty="No radius ladder rows.",
  )}
</section>
<section>
  <h2>Resolution ladder (chosen radius={html.escape(_fmt(chosen_radius))})</h2>
  {_table_html(
      ["shape_n", "attachment", "mean Δ expansions", "mean Δ cost", "mean |VG|", "max |VG|", "paired searches"],
      resolution_rows,
      empty="No resolution ladder rows.",
  )}
</section>
<section>
  <h2>All candidates</h2>
  {_table_html(
      ["goal_radius", "shape_n", "attachment", "empty start", "empty goal", "mean Δ expansions", "paired searches"],
      all_candidate_rows,
      empty="No candidate rows.",
  )}
</section>
<section>
  <h2>Decision artifacts</h2>
  <details open><summary>cartesian_radius_decision.json</summary>
  <pre>{html.escape(json.dumps(radius_decision, indent=2, sort_keys=True))}</pre></details>
  <details><summary>cartesian_resolution_decision.json</summary>
  <pre>{html.escape(json.dumps(resolution_decision, indent=2, sort_keys=True))}</pre></details>
  <details><summary>cartesian_start_attachment_decision.json</summary>
  <pre>{html.escape(json.dumps(payload.get("attachment_decision") or dict(), indent=2, sort_keys=True))}</pre></details>
</section>
"""


def render_cartesian_canvas_html(payload: dict[str, Any]) -> str:
    """Render a dark HTML printout for an Experiment B package."""
    run_id = html.escape(str(payload.get("run_id", "")))
    stage = str(payload.get("stage") or "smoke")
    manifest = payload.get("manifest") if isinstance(payload.get("manifest"), dict) else {}
    domain = payload.get("domain") if isinstance(payload.get("domain"), dict) else {}
    revision = manifest.get("revision") if isinstance(manifest.get("revision"), dict) else {}
    git_commit = revision.get("git_commit") or revision.get("git_describe") or "—"
    created = html.escape(str(manifest.get("created_at", "—")))
    experiment_id = html.escape(str(manifest.get("experiment_id", "—")))
    solver_policy = html.escape(str(manifest.get("solver_policy", "—")))
    algorithms = html.escape(", ".join(str(a) for a in (manifest.get("algorithms") or [])))
    stage_esc = html.escape(stage)

    body = _domain_section(domain)
    if stage == "calibration":
        body += _calibration_sections(payload)
        title = f"Experiment B calibration — {run_id}"
    else:
        body += _smoke_sections(payload)
        title = f"Experiment B smoke — {run_id}"

    body += f"""
<section>
  <h2>Manifest</h2>
  <details><summary>manifest.json</summary>
  <pre>{html.escape(json.dumps(manifest, indent=2, sort_keys=True))}</pre></details>
  <details><summary>config.json</summary>
  <pre>{html.escape(json.dumps(payload.get("config") or dict(), indent=2, sort_keys=True))}</pre></details>
</section>
"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>{html.escape(title)}</title>
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
.muted {{ color: var(--muted); }}
.kv {{ display: grid; grid-template-columns: 14rem 1fr; gap: 0.35rem 1rem; }}
.kv div {{ border-bottom: 1px solid var(--line); padding: 0.2rem 0; }}
.kv .k {{ color: var(--muted); }}
.table-wrap {{ overflow: auto; }}
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
  <h1>{html.escape(title)}</h1>
  <div class="meta">
    stage={stage_esc} · experiment={experiment_id} · created={created}<br/>
    solver_policy={solver_policy} · algorithms={algorithms} · git={html.escape(str(git_commit))}
  </div>
</header>
<main>
{body}
</main>
</body>
</html>
"""


def write_cartesian_canvas(run_dir: Path | str) -> Path:
    """Write ``index.html`` beside an Experiment B smoke or calibration package."""
    path = resolve_cartesian_run_for_canvas(run_dir)
    payload = load_cartesian_canvas_payload(path)
    out = path / _CANVAS_NAME
    out.write_text(render_cartesian_canvas_html(payload), encoding="utf-8")
    return out
