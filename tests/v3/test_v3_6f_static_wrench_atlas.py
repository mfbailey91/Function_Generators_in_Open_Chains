"""V3.6F gravity-free static wrench atlas tests."""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from pathlib import Path

import numpy as np
import pytest

from inequality_mechanisms.adapters import planar_2r_operating_branch_robot
from inequality_mechanisms.audits import v3_span_wrench_guard
from inequality_mechanisms.audits.static_wrench_atlas import (
    DIRECTION_KEYS,
    _evaluate_case,
    export_static_wrench_atlas,
)
from inequality_mechanisms.audits.v3_span_wrench_guard import (
    REPO_ROOT,
    ArtifactPathForbiddenError,
    assert_v3_6f_output_allowed,
)
from inequality_mechanisms.experiments.span_cases import generate_span_cases, realize_span_case
from inequality_mechanisms.kinematics.planar_2r import Planar2R
from inequality_mechanisms.mechanisms.span_registry import load_span_registry
from inequality_mechanisms.metrics.static_wrench import DEFAULT_TORQUE_LIMITS, static_wrench_at_q

V4_1_MANIFEST = (
    REPO_ROOT / "results" / "v4_review" / "v4_1_planar2r_geometry_atlas" / "manifest.json"
)
V4_1_INDEX = REPO_ROOT / "results" / "v4_review" / "v4_1_planar2r_geometry_atlas" / "index.html"
V4_1_MANIFEST_SHA = "566089bb22f4303992c855ebd3725eaf6f811c6460c9d66de05b429ac9e9a8e5"
V4_1_INDEX_SHA = "7a88312dc720550b2c54a03059d8f8f32a8829dd4aa6f50f0d7641516014dc5d"
D_REGISTRY = REPO_ROOT / "results" / "v3_review" / "v3_6d_span_corpus" / "registry.json"
PLANAR = Planar2R(L1=1.0, L2=1.0)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def atlas_root() -> Path:
    patch = pytest.MonkeyPatch()
    tmp = Path(tempfile.mkdtemp())
    patch.setattr(v3_span_wrench_guard, "REPO_ROOT", tmp)
    try:
        root = tmp / "results" / "v3_review" / "v3_6f_static_wrench_atlas"
        yield export_static_wrench_atlas(output=root, trace=False)
    finally:
        patch.undo()


def test_v3_6f_refuses_v4_and_e() -> None:
    with pytest.raises(ArtifactPathForbiddenError):
        assert_v3_6f_output_allowed(
            REPO_ROOT / "results" / "v4_review" / "v4_1_planar2r_geometry_atlas"
        )
    with pytest.raises(ArtifactPathForbiddenError):
        assert_v3_6f_output_allowed(
            REPO_ROOT / "results" / "v3_review" / "v3_6e_static_wrench_core"
        )


def test_seventeen_cases_linked_once(atlas_root: Path) -> None:
    index = (atlas_root / "index.html").read_text(encoding="utf-8")
    cases = json.loads((atlas_root / "cases.json").read_text(encoding="utf-8"))
    expected = [row.case_id for row in generate_span_cases()]
    assert [row["case_id"] for row in cases] == expected
    assert len(cases) == 17
    for case_id in expected:
        assert index.count(f"cases/{case_id}/index.html") == 1


def test_paired_q_and_color_limits(atlas_root: Path) -> None:
    cases = json.loads((atlas_root / "cases.json").read_text(encoding="utf-8"))
    for row in cases:
        cells = [
            json.loads(line)
            for line in (atlas_root / "cases" / row["case_id"] / "cells.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line
        ]
        q_four = [tuple(c["q"]) for c in cells if c["mechanism_id"] == "fourbar"]
        q_gear = [tuple(c["q"]) for c in cells if c["mechanism_id"] == "gearbox"]
        assert q_four == q_gear
        assert q_four == [tuple(q) for q in row["q_samples"]]
        lo, hi = row["color_limits"]["isotropic_radius"]
        assert hi >= lo


def test_index_default_is_scalar_heatmap(atlas_root: Path) -> None:
    index = (atlas_root / "index.html").read_text(encoding="utf-8")
    assert "Default view: isotropic-capacity heatmap" in index
    assert "scalar.png" in index
    case = (atlas_root / "cases" / "span_j1_145_j2_145" / "index.html").read_text(
        encoding="utf-8"
    )
    assert 'id="main-image" src="figures/scalar.png"' in case
    assert 'value="positive_x"' in case
    for key in DIRECTION_KEYS:
        assert (atlas_root / "cases" / "span_j1_145_j2_145" / "figures" / f"{key}.png").is_file()


def test_polygon_vertices_match_e_core(atlas_root: Path) -> None:
    case_id = "span_j1_095_j2_095"
    cells = [
        json.loads(line)
        for line in (atlas_root / "cases" / case_id / "cells.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line
    ]
    regular = next(
        row
        for row in cells
        if row["mechanism_id"] == "fourbar" and row["status"] == "regular" and row["vertices"]
    )
    registry = load_span_registry(json.loads(D_REGISTRY.read_text(encoding="utf-8")))
    case = next(row for row in generate_span_cases() if row.case_id == case_id)
    realized = realize_span_case(case, registry)
    robot = planar_2r_operating_branch_robot(realized.fourbar, planar_fk=PLANAR)
    fresh = static_wrench_at_q(robot, regular["q"])
    np.testing.assert_allclose(fresh.vertices, np.asarray(regular["vertices"]), atol=1e-9)


def test_singular_statuses_never_ordinary_polygons(atlas_root: Path) -> None:
    for case_dir in (atlas_root / "cases").iterdir():
        for line in (case_dir / "cells.jsonl").read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row["status"] in {
                "rank_deficient",
                "unbounded_ideal_direction",
                "invalid_mechanism_state",
            }:
                assert row["vertices"] is None


def test_assets_and_print_fallback_resolve(atlas_root: Path) -> None:
    index = (atlas_root / "index.html").read_text(encoding="utf-8")
    print_page = (atlas_root / "print.html").read_text(encoding="utf-8")
    assert (atlas_root / "methods.md").is_file()
    assert (atlas_root / "biological_trace.md").is_file()
    assert (atlas_root / "print.html").is_file()
    assert "print fallback" in print_page.lower()
    assert "isotropic" in print_page.lower()
    for href in re.findall(r'href="([^"]+)"', index):
        if href.startswith("http") or href.startswith("#"):
            continue
        assert (atlas_root / href).exists(), href
    for src in re.findall(r'src="([^"]+)"', index):
        assert (atlas_root / src).is_file(), src


def test_trace_mode_does_not_alter_calculations() -> None:
    registry = load_span_registry(json.loads(D_REGISTRY.read_text(encoding="utf-8")))
    case = next(row for row in generate_span_cases() if row.case_id == "span_j1_145_j2_145")
    realized = realize_span_case(case, registry)
    plain = _evaluate_case(realized, torque_limits=DEFAULT_TORQUE_LIMITS, trace=False)
    traced = _evaluate_case(realized, torque_limits=DEFAULT_TORQUE_LIMITS, trace=True)
    assert [row["isotropic_radius"] for row in plain["records"]] == [
        row["isotropic_radius"] for row in traced["records"]
    ]
    assert [row["status"] for row in plain["records"]] == [
        row["status"] for row in traced["records"]
    ]
    assert traced["trace"] is True
    assert plain["trace"] is False


def test_no_gravity_as_implemented_option(atlas_root: Path) -> None:
    text = (atlas_root / "index.html").read_text(encoding="utf-8").lower()
    assert "not implemented options" in text
    assert "gravity compensation" not in text
    schema = json.loads((atlas_root / "schema.json").read_text(encoding="utf-8"))
    assert schema["gravity_implemented"] is False


def test_frozen_v4_1_hashes_unchanged() -> None:
    assert _sha(V4_1_MANIFEST) == V4_1_MANIFEST_SHA
    assert _sha(V4_1_INDEX) == V4_1_INDEX_SHA
