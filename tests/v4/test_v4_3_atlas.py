"""V4-306/307: smoke atlas HTML, assets, methods, and biological pointer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from inequality_mechanisms.audits import v4_artifact_guard as guard
from inequality_mechanisms.audits.v4_artifact_guard import V4_3_FOLLOWUP_OUTPUT_REL


def test_smoke_atlas_writes_under_monkeypatched_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from inequality_mechanisms.visualization.v4.intrinsic_static_wrench import (
        write_intrinsic_static_wrench_smoke_atlas,
    )

    canonical = guard.canonical_v4_3_retained_root()
    before = guard.digest_directory_tree(canonical)
    monkeypatch.setattr(guard, "REPO_ROOT", tmp_path)
    root = write_intrinsic_static_wrench_smoke_atlas()
    expected = tmp_path / V4_3_FOLLOWUP_OUTPUT_REL
    assert root == expected.resolve()
    assert (root / "index.html").is_file()
    assert (root / "assets" / "atlas.css").is_file()
    assert (root / "assets" / "atlas.js").is_file()
    assert (root / "methods.md").is_file()
    assert (root / "biological_reference_pointer.md").is_file()
    assert (root / "biological_reference_trace.md").is_file()
    assert (root / "README.md").is_file()
    assert (root / "smoke_selection.json").is_file()
    assert (root / "fixtures" / "analytic_expectations.json").is_file()

    smoke = json.loads((root / "smoke_selection.json").read_text(encoding="utf-8"))
    assert smoke["n_records"] == 60
    cases = json.loads((root / "cases.json").read_text(encoding="utf-8"))
    case_ids = {case["case_id"] for case in cases}
    assert "span_j1_145_j2_145" in case_ids
    assert "span_j1_095_j2_145" in case_ids
    assert "span_j1_135_j2_150" in case_ids
    assert "span_j1_175_j2_145" in case_ids

    index = (root / "index.html").read_text(encoding="utf-8")
    assert "mounted" in index.lower()
    assert "boundary_stress_only" in index or "Boundary-stress" in index
    assert "span_j1_145_j2_145" in index
    assert "assets/atlas.css" in index
    assert "normalized_torque_per_length" in index or "torque/length" in index

    stress_page = (root / "cases" / "span_j1_175_j2_145" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "Boundary-stress-only" in stress_page
    assert "assets/atlas.js" in stress_page
    assert "view-select" in stress_page

    shared = root / "cases" / "span_j1_145_j2_145"
    cells = json.loads((shared / "cells.json").read_text(encoding="utf-8"))
    assert len(cells) == 15  # 5 grids × 3 arms
    summary = json.loads((shared / "summary.json").read_text(encoding="utf-8"))
    assert summary["axis_label"] == "mounted_q"
    assert "isotropic_radius" in summary["color_limits"]
    assert (shared / "figures" / "scalar.png").is_file()
    assert (shared / "figures" / "polygons.png").is_file()
    assert (shared / "figures" / "identity_scalar.png").is_file()
    for name in ("delta", "ratio", "status"):
        assert (shared / "figures" / f"{name}.png").is_file()
    assert set(summary["comparisons"]) == {
        "isotropic_radius",
        "positive_x",
        "positive_y",
        "radial",
        "tangential",
    }
    assert len(summary["comparisons"]["isotropic_radius"]["comparisons"]) == 5
    assert summary["color_scale_policy"]["display_clipped_values"] == 0
    assert {"hrep_a", "hrep_b", "rank_reports", "direction_vectors"} <= cells[0].keys()
    page = (shared / "index.html").read_text(encoding="utf-8")
    assert "Shape-normalized" in page or "shape-normalized" in page
    assert "identity" in page.lower()
    assert 'id="cell-select"' in page
    assert 'id="atlas-data" type="application/json"' in page

    methods = (root / "methods.md").read_text(encoding="utf-8")
    assert "ray capacity" in methods.lower() or "Ray capacity" in methods
    assert "v4_2b_span_controlled_corrective_closeout" in methods
    assert "isotropic" in methods.lower()
    pointer = (root / "biological_reference_pointer.md").read_text(encoding="utf-8")
    assert "does **not** introduce new biological" in pointer or "does not" in pointer
    assert "BIOLOGICAL_JOINT_RANGE_REFERENCE_TRACE.md" in pointer

    # Canonical retained target must remain untouched by the tmp smoke write.
    assert guard.digest_directory_tree(canonical) == before


def test_methods_packet_rejects_writing_outside_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from inequality_mechanisms.audits.v4_artifact_guard import (
        ArtifactPathForbiddenError,
    )
    from inequality_mechanisms.visualization.v4 import intrinsic_static_wrench as viz

    monkeypatch.setattr(guard, "REPO_ROOT", tmp_path)
    with pytest.raises(ArtifactPathForbiddenError):
        viz.write_intrinsic_static_wrench_smoke_atlas(tmp_path / "elsewhere")
