"""Scientific display invariants and executable offline cell-inspector checks."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from inequality_mechanisms.experiments.v4.intrinsic_static_wrench_config import (
    FROZEN_MECHANISM_IDS,
)
from inequality_mechanisms.visualization.v4 import intrinsic_static_wrench as viz


def _row(
    mechanism: str, *, scale: float = 1.0, grid: tuple[int, int] = (0, 0)
) -> dict[str, Any]:
    """Deliberately simple stored display data, independent of the force solver."""
    vertices = (scale * np.array([[-1, -2], [1, -2], [1, 2], [-1, 2]])).tolist()
    return {
        "case_id": "fixture",
        "q_sample_id": f"fixture__q_{grid[0]:04d}_{grid[1]:04d}",
        "grid_index": list(grid),
        "mechanism_id": mechanism,
        "status": "regular",
        "primary_eligible": True,
        "vertices": vertices,
        "isotropic_radius": scale,
        "isotropic_radius_field": {"status": "finite", "value": scale},
        "directional_capacity": {name: scale for name in viz.NAMED_DIRECTIONS},
        "directional_fields": {
            name: {"status": "finite", "value": scale} for name in viz.NAMED_DIRECTIONS
        },
        "q": list(grid),
        "u": [0.25, 0.5],
        "x": [1.0, 1.0],
        "j_g": [[1, 0], [0, 1]],
        "j_f": [[-1, -1], [1, 0]],
        "j_xu": [[-1, -1], [1, 0]],
        "torque_limits": [1.0, 1.0],
        "hrep_a": [[-1, 1], [-1, 0], [1, -1], [1, 0]],
        "hrep_b": [1, 1, 1, 1],
        "direction_vectors": {"radial": [0.707, 0.707]},
        "rank_reports": {"u_to_q": {"rank": 2, "tolerance": 1e-15}},
        "low_gain_warning": False,
        "vertex_feasibility": {"ok": True},
    }


def _capture_figures(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    plt = viz._require_matplotlib()
    figures: list[Any] = []
    close = plt.close

    def capture(figure: Any = None) -> None:
        if hasattr(figure, "axes"):
            figures.append(figure)
        close(figure)

    monkeypatch.setattr(plt, "close", capture)
    return figures


def test_true_scale_panels_preserve_tenfold_force_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    figures = _capture_figures(monkeypatch)
    rows = [_row(FROZEN_MECHANISM_IDS[0]), _row(FROZEN_MECHANISM_IDS[1], scale=10)]
    detail = viz.write_true_scale_detail(
        tmp_path / "detail.png",
        records=rows,
        q_sample_id=rows[0]["q_sample_id"],
        title="Scale test",
    )
    left, right = figures[-1].axes
    assert left.get_xlim() == right.get_xlim() == (-22.0, 22.0)
    assert left.get_ylim() == right.get_ylim() == (-22.0, 22.0)
    assert left.get_aspect() == right.get_aspect() == 1.0
    # Check the actual data-to-pixel transform, not just a metadata promise.
    left_px = left.transData.transform([[0, 0], [0, 2]])
    right_px = right.transData.transform([[0, 0], [0, 20]])
    assert (right_px[1, 1] - right_px[0, 1]) / (
        left_px[1, 1] - left_px[0, 1]
    ) == pytest.approx(10.0)
    assert detail is not None
    assert detail["force_bounds"]["xlim"] == [-22.0, 22.0]


def test_shape_glyphs_remove_force_multiplier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    figures = _capture_figures(monkeypatch)
    rows = [_row(FROZEN_MECHANISM_IDS[0]), _row(FROZEN_MECHANISM_IDS[1], scale=10)]
    viz.write_polygon_glyphs(tmp_path / "glyphs.png", records=rows)
    left, right = figures[-1].axes
    np.testing.assert_allclose(left.lines[0].get_xydata(), right.lines[0].get_xydata())
    assert left.get_xlim() == right.get_xlim()
    assert left.get_ylim() == right.get_ylim()


def test_identity_scale_covers_its_values_independently(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}
    monkeypatch.setattr(viz, "write_paired_heatmap", lambda *args, **kwargs: None)
    monkeypatch.setattr(viz, "write_polygon_glyphs", lambda *args, **kwargs: None)
    monkeypatch.setattr(viz, "write_true_scale_detail", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        viz, "write_identity_heatmap", lambda *args, **kwargs: captured.update(kwargs)
    )
    rows = [
        _row(mech, scale=scale)
        for mech, scale in zip(FROZEN_MECHANISM_IDS, (10.0, 20.0, 0.5), strict=True)
    ]
    rows.append(_row("identity_on_shared_q", scale=0.6, grid=(1, 1)))
    result = viz.write_case_figures(tmp_path, rows)
    assert result["color_limits"]["isotropic_radius"] == [10.0, 20.0]
    assert result["color_limits"]["identity_isotropic_radius"] == [0.5, 0.6]
    assert captured["vmin"] == 0.5 and captured["vmax"] == 0.6
    finite = captured["grid"][np.isfinite(captured["grid"])]
    assert np.all((finite >= captured["vmin"]) & (finite <= captured["vmax"]))
    assert "separate" in result["assets"]["identity_scalar"]["caption"].lower() or (
        "own full finite range" in result["assets"]["identity_scalar"]["caption"]
    )
    assert "positive_x_diagnostic" in result["assets"]


def test_primary_directional_scales_exclude_near_singular_outlier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regular-finite primary limits must ignore huge near-singular outliers."""
    paired_calls: list[dict[str, Any]] = []

    def capture_paired(*args: Any, **kwargs: Any) -> None:
        paired_calls.append(kwargs)

    monkeypatch.setattr(viz, "write_paired_heatmap", capture_paired)
    monkeypatch.setattr(viz, "write_polygon_glyphs", lambda *args, **kwargs: None)
    monkeypatch.setattr(viz, "write_true_scale_detail", lambda *args, **kwargs: None)
    monkeypatch.setattr(viz, "write_identity_heatmap", lambda *args, **kwargs: None)

    rows = [
        _row(mech, scale=scale, grid=(i, 0))
        for i, (mech, scale) in enumerate(
            zip(FROZEN_MECHANISM_IDS, (1.0, 2.0, 0.5), strict=True)
        )
    ]
    rows.append(_row("fourbar", scale=3.0, grid=(2, 0)))
    rows.append(_row("span_matched_gearbox", scale=4.0, grid=(2, 0)))
    outlier = _row("fourbar", scale=1e12, grid=(3, 0))
    outlier.update(status="near_singular", primary_eligible=False)
    outlier["isotropic_radius_field"] = {"status": "finite", "value": 1e12}
    for name in viz.NAMED_DIRECTIONS:
        outlier["directional_capacity"][name] = 1e12
        outlier["directional_fields"][name] = {"status": "finite", "value": 1e12}
    rows.append(outlier)

    result = viz.write_case_figures(tmp_path, rows)
    assert result["color_limits"]["positive_x"] == [1.0, 4.0]
    assert result["color_limits"]["radial"] == [1.0, 4.0]
    primary = next(
        call for call in paired_calls if call["title"] == "Ray capacity: positive_x"
    )
    diagnostic = next(
        call
        for call in paired_calls
        if call["title"].startswith("Diagnostic") and "positive_x" in call["title"]
    )
    assert primary["vmax"] == 4.0
    assert diagnostic["vmax"] >= 1e12
    primary_finite = np.concatenate(
        [
            primary["grids"][mech][np.isfinite(primary["grids"][mech])]
            for mech in ("fourbar", "span_matched_gearbox")
        ]
    )
    assert len(np.unique(np.round(primary_finite, 12))) > 1


def _comparison(grid: list[int], *, eligible: bool) -> dict[str, Any]:
    return {
        "case_id": "fixture",
        "q_sample_id": "fixture",
        "grid_index": grid,
        "eligible": eligible,
        "exclusion_reason": None if eligible else "left_unbounded_ideal_direction",
        "delta": {
            "status": "finite" if eligible else "invalid",
            "value": -9.0 if eligible else None,
        },
        "ratio": {
            "status": "finite" if eligible else "invalid",
            "value": 0.1 if eligible else None,
        },
    }


def test_comparison_grid_keeps_excluded_pair_unavailable() -> None:
    grids = viz.comparison_grids(
        [_comparison([0, 0], eligible=True), _comparison([1, 1], eligible=False)]
    )
    assert grids["delta"][0, 0] == -9.0
    assert grids["ratio"][0, 0] == 0.1
    assert np.isnan(grids["delta"][1, 1])
    assert np.isnan(grids["ratio"][1, 1])


def test_offline_inspector_executes_cell_and_view_selection(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js required to execute offline atlas JavaScript")
    rows = [
        _row(mech, scale=scale)
        for mech, scale in zip(FROZEN_MECHANISM_IDS, (1.0, 10.0, 0.5), strict=True)
    ]
    for mechanism in FROZEN_MECHANISM_IDS:
        row = _row(mechanism, grid=(16, 16))
        row.update(
            status="unbounded_ideal_direction",
            vertices=None,
            primary_eligible=False,
            low_gain_warning=True,
        )
        row["directional_fields"]["radial"] = {"status": "unbounded", "value": None}
        rows.append(row)
    comparisons = {
        key: {
            "comparisons": [
                _comparison([0, 0], eligible=True),
                _comparison([16, 16], eligible=False),
            ]
        }
        for key in ("isotropic_radius", *viz.NAMED_DIRECTIONS)
    }
    assets = {
        name: {"src": f"{name}.png", "alt": name, "caption": name}
        for name in (
            "scalar",
            "radial",
            "delta",
            "ratio",
            "status",
            "true_scale_detail",
        )
    }
    payload = viz.inspector_payload(rows, comparisons=comparisons, assets=assets)
    assert (
        payload["cells"]["0,0"]["arms"]["fourbar"]["rank_reports"]
        == (rows[0]["rank_reports"])
    )
    harness = r"""
const assert = require("node:assert/strict");
class Element {
  constructor(tag) { this.tag=tag; this.children=[]; this.events={}; this.attrs={}; }
  appendChild(node) { this.children.push(node); return node; }
  replaceChildren() { this.children=[]; }
  setAttribute(name,value) { this.attrs[name]=String(value); }
  addEventListener(name,handler) { this.events[name]=handler; }
}
const ids = Object.fromEntries([
  "atlas-data", "view-select", "cell-select", "main-image", "main-caption",
  "cell-readout", "selected-polygons", "cell-comparison", "selected-identity"
].map(id=>[id,new Element(id)]));
global.document = {
  getElementById: id=>ids[id], createElement: tag=>new Element(tag),
  createElementNS: (_,tag)=>new Element(tag)
};
ids["atlas-data"].textContent=JSON.stringify(PAYLOAD);
ids["view-select"].value="scalar";
ids["cell-select"].value="0,0";
"""
    assertions = r"""
let packet=JSON.parse(ids["cell-readout"].textContent);
assert.equal(packet.q_sample_id,"fixture__q_0000_0000");
assert.deepEqual(packet.arms.fourbar.u,[0.25,0.5]);
assert.equal(packet.arms.fourbar.rank_reports.u_to_q.rank,2);
assert.equal(ids["selected-polygons"].children.length,3);
function nodes(root,tag) {
  return root.children.flatMap(child=>[
    ...(child.tag===tag ? [child] : []), ...nodes(child,tag)
  ]);
}
const polygons=nodes(ids["selected-polygons"],"polygon");
assert.equal(polygons.length,3);
const y0=Number(polygons[0].attrs.points.split(" ")[0].split(",")[1]);
const y1=Number(polygons[1].attrs.points.split(" ")[0].split(",")[1]);
assert.ok(Math.abs((y1-140)/(y0-140)-10)<1e-12);
ids["cell-select"].value="16,16";
ids["cell-select"].events.change();
packet=JSON.parse(ids["cell-readout"].textContent);
assert.deepEqual(packet.grid_index,[16,16]);
assert.equal(packet.arms.fourbar.status,"unbounded_ideal_direction");
assert.equal(packet.comparisons.isotropic_radius.delta.value,null);
assert.equal(nodes(ids["selected-polygons"],"polygon").length,0);
ids["view-select"].value="radial";
ids["view-select"].events.change();
packet=JSON.parse(ids["cell-readout"].textContent);
assert.equal(packet.selected_view,"radial");
assert.deepEqual(packet.grid_index,[16,16]);
assert.equal(packet.arms.fourbar.directional_fields.radial.value,null);
assert.equal(ids["main-image"].src,"radial.png");
assert.ok(ids["cell-comparison"].textContent.includes("left_unbounded"));
ids["view-select"].value="true_scale_detail";
ids["view-select"].events.change();
assert.equal(ids["main-image"].hidden,true);
assert.ok(ids["main-caption"].textContent.includes("fixture__q_0016_0016"));
ids["view-select"].value="scalar";
ids["view-select"].events.change();
assert.equal(ids["main-image"].hidden,false);
console.log("cell/view selection, status transport, raw fields and force scale passed");
"""
    script = tmp_path / "inspector-test.js"
    script.write_text(
        "const PAYLOAD="
        + json.dumps(payload)
        + ";\n"
        + harness
        + viz._ATLAS_JS
        + assertions,
        encoding="utf-8",
    )
    completed = subprocess.run([node, str(script)], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr


def test_embedded_data_cannot_end_script() -> None:
    packet = {"identity": "</script><script>alert(1)</script>"}
    escaped = viz._script_json(packet)
    assert "</script>" not in escaped
    assert json.loads(escaped) == packet


@pytest.mark.parametrize("smoke", [True, False])
def test_atlas_writers_reject_changed_effort_budget_before_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, smoke: bool
) -> None:
    config = viz.load_intrinsic_static_wrench_config()
    config = config.model_copy(
        update={"torque": config.torque.model_copy(update={"limits": (2.0, 2.0)})}
    )
    monkeypatch.setattr(viz, "load_intrinsic_static_wrench_config", lambda *a: config)
    target = tmp_path / "must-not-exist"
    with pytest.raises(ValueError, match="unit actuator-effort"):
        if smoke:
            viz.write_intrinsic_static_wrench_smoke_atlas(target)
        else:
            viz.generate_intrinsic_static_wrench_package(output=target)
    assert not target.exists()
