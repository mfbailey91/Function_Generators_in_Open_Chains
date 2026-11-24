"""Consume 60 frozen V4.2B snapshots for the first V4.4 velocity/IK smoke.

No geometry evaluation, wrench evaluation, resampling, or trajectory claims.
All production writes pass the same exact-root and clean-source preflight.
"""

from __future__ import annotations

import html
from collections.abc import Mapping, Sequence
from io import StringIO
from pathlib import Path
from typing import Any, cast

import numpy as np

from inequality_mechanisms.audits.v4_4_artifact import (
    CASE_IDS,
    DIRECTIONS,
    MANIFEST_SCHEMA,
    PACKAGE,
    PACKAGE_FILES,
    POLICIES,
    RATE_POLICIES,
    ROW_SCHEMA,
    V4_4ArtifactError,
    aggregate_velocity_rows,
    inventory_digest,
    load_velocity_config,
    preflight_velocity_smoke,
    selection_record,
    sha256,
    strict_json,
    verify_velocity_record,
)
from inequality_mechanisms.experiments.v4.intrinsic_static_wrench import (
    ConsumedSourceRow,
    assert_v4_2b_source_lock,
    evaluate_restored_row,
    iter_retained_atlas_rows,
    pair_physical_samples,
)
from inequality_mechanisms.experiments.v4.intrinsic_static_wrench_config import (
    FROZEN_MECHANISM_IDS,
    SMOKE_GRID_INDICES,
    SourceLock,
)
from inequality_mechanisms.metrics.velocity import (
    differential_ik_from_snapshot,
    velocity_capability_from_snapshot,
)
from inequality_mechanisms.transmission_geometry.errors import (
    DifferentialSingularityError,
)


def consume_velocity_smoke() -> list[ConsumedSourceRow]:
    """Restore and pair the frozen deterministic subset without computing wrench."""
    consumed = []
    for case_id in CASE_IDS:
        for identity, row in iter_retained_atlas_rows(case_id):
            if identity.grid_index in SMOKE_GRID_INDICES:
                consumed.append(
                    evaluate_restored_row(identity, row, evaluate_wrench=False)
                )
    if len(consumed) != 60:
        raise V4_4ArtifactError(
            f"V4.4 smoke requires 60 retained rows, got {len(consumed)}"
        )
    pairs = pair_physical_samples(consumed)
    if len(pairs) != 20:
        raise V4_4ArtifactError("V4.4 smoke requires 20 complete three-arm pairs")
    if any(item.source_failure_code is not None for item in consumed):
        raise V4_4ArtifactError("The frozen V4.2B smoke contains a source failure")
    return [pair.arms[arm] for pair in pairs for arm in FROZEN_MECHANISM_IDS]


def velocity_smoke_record(
    item: ConsumedSourceRow,
    config: Mapping[str, Any],
    *,
    verify: bool = True,
) -> dict[str, Any]:
    """Retain raw snapshots, velocity geometry, and all 24 inverse-policy requests."""
    snapshot = item.row.snapshot
    if snapshot is None or item.source_failure_code is not None:
        raise V4_4ArtifactError(
            f"Unavailable frozen source snapshot: {item.identity.key}"
        )
    capability = velocity_capability_from_snapshot(
        snapshot, rate_limits=config["rate_limits"]
    ).to_dict()
    requests = []
    for name in DIRECTIONS:
        target = capability["directions"][name]
        for policy in POLICIES:
            for rate_policy in RATE_POLICIES:
                request: dict[str, Any] = {
                    "direction": name,
                    "policy": policy,
                    "rate_policy": rate_policy,
                    "target_velocity": target,
                    "status": "unavailable",
                    "failure_code": None,
                    "failure_detail": None,
                    "result": None,
                }
                if target is None:
                    request["failure_code"] = "undefined_direction"
                else:
                    try:
                        result = differential_ik_from_snapshot(
                            snapshot,
                            target,
                            policy=policy,
                            damping=config["damping"]
                            if policy == "damped_least_squares"
                            else None,
                            actuator_weight=config["actuator_weight"],
                            rate_limits=config["rate_limits"],
                            rate_policy=rate_policy,
                        )
                    except DifferentialSingularityError as exc:
                        request["failure_code"] = exc.failure_code
                        request["failure_detail"] = {
                            "operation": exc.operation,
                            "rank": exc.rank,
                            "required_rank": exc.required_rank,
                            "singular_values": list(exc.singular_values),
                            "tolerance": exc.tolerance,
                        }
                    else:
                        request.update(status="available", result=result.to_dict())
                requests.append(request)
    record = {
        "schema_version": ROW_SCHEMA,
        "case_id": item.identity.case_id,
        "q_sample_id": item.identity.q_sample_id,
        "mechanism_id": item.identity.mechanism_id,
        "mechanism_pair_id": item.identity.mechanism_pair_id,
        "grid_index": list(item.identity.grid_index),
        "source_relpath": item.identity.source_relpath,
        "source_config_digest": item.identity.config_digest,
        "source_revision": item.identity.source_revision,
        "source_failure_code": item.source_failure_code,
        "source_snapshot": snapshot.to_dict(),
        "capability": capability,
        "ik_requests": requests,
    }
    if verify:
        verify_velocity_record(record)
    return record


def _representative_pairs(
    rows: Sequence[Mapping[str, Any]],
) -> list[list[Mapping[str, Any]]]:
    pairs = []
    for case in CASE_IDS:
        for grid in ((0, 0), (16, 16)):
            selected = [
                row
                for row in rows
                if row["case_id"] == case and tuple(row["grid_index"]) == grid
            ]
            pairs.append(
                sorted(
                    selected,
                    key=lambda row: FROZEN_MECHANISM_IDS.index(row["mechanism_id"]),
                )
            )
    return pairs


def _review_svg(rows: Sequence[Mapping[str, Any]]) -> str:
    """Render stored corner images with common equal axes using Matplotlib."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    pairs = _representative_pairs(rows)
    colors = ("#176a94", "#a13e62", "#52645d")
    with plt.rc_context({"svg.hashsalt": PACKAGE, "font.size": 9}):
        figure = plt.figure(figsize=(12, 3.5 * len(pairs) + 0.7), layout="constrained")
        figure.suptitle(
            "Velocity sets · raw image of the normalized unit rate box\n"
            "Shared equal axes within each three-arm row; "
            "scales differ between samples.",
            fontsize=13,
        )
        subfigures = cast(Sequence[Any], figure.subfigures(len(pairs), 1))
        for subfigure, pair in zip(subfigures, pairs, strict=True):
            subfigure.suptitle(
                f"{pair[0]['case_id']} · grid {pair[0]['grid_index']}", fontsize=11
            )
            axes = subfigure.subplots(1, 3)
            bound = 1.10 * max(
                float(np.max(np.abs(row["capability"]["velocity_corners"])))
                for row in pair
            )
            bound = max(bound, 1e-12)
            for axis, row, color in zip(axes, pair, colors, strict=True):
                vertices = np.asarray(row["capability"]["velocity_corners"])
                closed = np.vstack([vertices, vertices[0]])
                axis.fill(vertices[:, 0], vertices[:, 1], color=color, alpha=0.13)
                axis.plot(closed[:, 0], closed[:, 1], color=color, linewidth=1.5)
                axis.axhline(0, color="#cbd5df", linewidth=0.6, zorder=0)
                axis.axvline(0, color="#cbd5df", linewidth=0.6, zorder=0)
                axis.set_xlim(-bound, bound)
                axis.set_ylim(-bound, bound)
                axis.set_aspect("equal", adjustable="box")
                axis.set_title(
                    row["mechanism_id"] + "\n" + row["capability"]["status"],
                    fontsize=10,
                )
                axis.set_xlabel("x velocity (length / normalized time)")
                axis.set_ylabel("y velocity")
        output = StringIO()
        figure.savefig(output, format="svg", metadata={"Date": None})
        plt.close(figure)
        return output.getvalue()


def _review_html(
    rows: Sequence[Mapping[str, Any]],
    aggregate: Mapping[str, Any],
    config: Mapping[str, Any],
) -> str:
    def text(value: Any) -> str:
        return html.escape(str(value))

    summary_rows = []
    for item in aggregate["policy_summary"]:
        summary_rows.append(
            "<tr>"
            + "".join(
                f"<td>{text(item[key])}</td>"
                for key in (
                    "policy",
                    "rate_policy",
                    "n_available",
                    "n_unavailable",
                    "requested_exceeding_budget",
                    "commanded_exceeding_budget",
                    "scaled_commands",
                )
            )
            + "</tr>"
        )
    details = []
    for pair in _representative_pairs(rows):
        table_rows = []
        for row in pair:
            for request in row["ik_requests"]:
                if request["direction"] != "positive_x":
                    continue
                result = request["result"]
                values = [
                    row["mechanism_id"],
                    request["policy"],
                    request["rate_policy"],
                ]
                values.extend(
                    [
                        f"{result[key]:.6g}"
                        for key in (
                            "requested_peak_utilization",
                            "commanded_peak_utilization",
                            "applied_scale",
                            "residual_norm",
                        )
                    ]
                    if result is not None
                    else ["unavailable"] * 4
                )
                values.append(
                    request["failure_code"]
                    if result is None
                    else result["solver_status"] + " / " + result["command_status"]
                )
                table_rows.append(
                    "<tr>"
                    + "".join(f"<td>{text(value)}</td>" for value in values)
                    + "</tr>"
                )
        details.append(
            f"<details><summary>{text(pair[0]['case_id'])} · "
            f"grid {text(pair[0]['grid_index'])} · unit +x target</summary>"
            '<div class="table-scroll"><table><thead><tr><th>Arm</th>'
            "<th>Inverse policy</th><th>Rate policy</th><th>Requested peak</th>"
            "<th>Commanded peak</th><th>Scale</th><th>Residual norm</th>"
            "<th>Solver / command status</th></tr></thead><tbody>"
            + "".join(table_rows)
            + "</tbody></table></div></details>"
        )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>V4.4 velocity and differential IK smoke</title>
<style>
body{{font:16px/1.55 system-ui,sans-serif;color:#24324a;max-width:1180px;
margin:32px auto;padding:0 20px}}h1,h2{{line-height:1.2}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
th,td{{padding:8px;border:1px solid #d7dfe7;text-align:left}}
th{{background:#edf2f7}}.table-scroll{{overflow-x:auto}}
img{{display:block;width:100%;height:auto}}
summary{{cursor:pointer;padding:12px;background:#f1f5f8;margin-top:10px}}
a{{color:#176a94}}code{{background:#f1f5f8;padding:2px 4px}}</style></head>
<body><h1>V4.4 velocity and differential IK smoke</h1>
<p><strong>60 retained snapshots · 20 matched physical samples · 3 arms ·
1,440 explicit inverse-policy requests.</strong></p>
<p>{text(config["no_inference_statement"])}</p>
<p>The velocity set is the forward image of
<code>|u̇₁| ≤ 1, |u̇₂| ≤ 1</code>. Directional <em>support</em> measures the largest
projection, while directional <em>ray speed</em> measures motion along the specified
ray. These are retained as separate quantities. Rank-deficient ray values explicitly
identify the inherited-rank model; raw corner images and support remain available.</p>
<p>The three inverse policies are exact, minimum norm with <code>W = I</code>, and
damped least squares with <code>λ = 0.05</code>. Exact inversion at inherited rank loss
is unavailable. Minimum norm projects into the inherited range. Damping introduces
a residual while keeping the physical status unchanged. <code>report_only</code>
retains rate demand; <code>uniform_scale</code> scales the entire command into the
unit budget and records the resulting motion and residual.</p>
<nav><a href="velocity_samples.jsonl">All scientific records</a> ·
<a href="config.json">Configuration</a> ·
<a href="source_lock.json">Source lock</a> ·
<a href="selection.json">Selection</a> ·
<a href="aggregate.json">Accounting</a> ·
<a href="manifest.json">SHA manifest</a></nav>
<h2>Policy and rate-budget accounting</h2><p>Physical status counts:
<code>{text(aggregate["physical_status_counts"])}</code>.
Budget exceedance is distinct from saturation at exactly one.</p>
<p>An available policy has produced a numerical result. Its achieved velocity
and residual show how closely it realizes the requested target.</p>
<div class="table-scroll"><table><thead><tr><th>Inverse policy</th>
<th>Rate policy</th><th>Available</th><th>Unavailable</th>
<th>Requested over budget</th><th>Commanded over budget</th>
<th>Scaled commands</th></tr></thead><tbody>
{"".join(summary_rows)}</tbody></table></div>
<p>Scaled-command counts include roundoff-sized boundary adjustments;
budget exceedance uses the recorded feasibility tolerance.</p>
<h2>Paired velocity geometry</h2><p>Regular corner and center samples for each
selected case. Each three-arm row uses common equal axes; full-set magnitudes
are preserved.</p>
<p>The retained center snapshots classify the fourbar as near-singular and the
gearbox and identity controls as rank-deficient. Tiny retained coordinate
differences and inherited rank thresholds remain diagnostic; these labels do not
establish that a transmission removes the robot singularity.</p>
<img src="review.svg"
alt="Paired raw velocity sets for four smoke cases at regular and center samples">
<h2>Inspect unit +x commands</h2><p>These tables illustrate all policies on the
plotted samples. Every named target and all 60 rows are retained in the
downloadable scientific records.</p>{"".join(details)}
</body></html>\n"""


def generate_velocity_smoke(*, config_path: Path | None = None) -> dict[str, Any]:
    """Generate once at the exact authorized root after all preflight checks."""
    config = load_velocity_config(config_path)
    target, revision = preflight_velocity_smoke()
    source = {
        key: value
        for key, value in assert_v4_2b_source_lock(
            SourceLock(**config["source"])
        ).items()
        if key != "root"
    }
    rows = [velocity_smoke_record(item, config) for item in consume_velocity_smoke()]
    selection = selection_record(rows)
    aggregate = aggregate_velocity_rows(rows)
    documents = {
        "config.json": strict_json(config) + "\n",
        "source_lock.json": strict_json(
            {
                "schema_version": "v4.4.intrinsic_velocity.source_lock.v1",
                "generation_git_revision": revision,
                "frozen_source": config["source"],
                "verified_source": source,
            }
        )
        + "\n",
        "selection.json": strict_json(selection) + "\n",
        "aggregate.json": strict_json(aggregate) + "\n",
        "velocity_samples.jsonl": "".join(
            strict_json(row, indent=None) + "\n" for row in rows
        ),
        "review.svg": _review_svg(rows),
        "index.html": _review_html(rows, aggregate, config),
    }
    if set(documents) != PACKAGE_FILES:
        raise V4_4ArtifactError("Internal V4.4 inventory mismatch")
    files = [
        {"path": name, "sha256": sha256(content.encode())}
        for name, content in sorted(documents.items())
    ]
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "package": PACKAGE,
        "source_git_revision": revision,
        "source_git_dirty": False,
        "config_digest": sha256(strict_json(config, indent=None).encode()),
        "selection_digest": selection["selection_digest"],
        "n_rows": aggregate["n_rows"],
        "n_pairs": aggregate["n_pairs"],
        "n_ik_requests": aggregate["n_ik_requests"],
        "n_files": len(files),
        "files": files,
        "files_digest": inventory_digest(files),
    }
    documents["manifest.json"] = strict_json(manifest) + "\n"
    checked_target, checked_revision = preflight_velocity_smoke()
    if checked_target != target or checked_revision != revision:
        raise V4_4ArtifactError("V4.4 source or destination changed during evaluation")
    target.mkdir(parents=True, exist_ok=True)
    for name, contents in documents.items():
        with (target / name).open("x", encoding="utf-8") as stream:
            stream.write(contents)
    return {
        "output": str(target),
        "files_digest": manifest["files_digest"],
        **aggregate,
    }
