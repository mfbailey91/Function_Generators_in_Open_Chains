"""V4-302–305: force records, scalar/directional fields, and status transport."""

from __future__ import annotations

import gzip
import json
import math
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from inequality_mechanisms.audits.v4_3_artifact import (
    V4_3ArtifactError,
    strict_json_dumps,
    to_strict_jsonable,
)
from inequality_mechanisms.audits.v4_artifact_guard import canonical_v4_2b_retained_root
from inequality_mechanisms.experiments.v4.geometry_atlas import (
    AtlasRow,
    parse_retained_atlas_row,
)
from inequality_mechanisms.experiments.v4.intrinsic_static_wrench import (
    ConsumedSourceRow,
    PairedPhysicalSample,
    SourceIdentity,
    evaluate_restored_row,
    resolve_smoke_selection,
)
from inequality_mechanisms.experiments.v4.intrinsic_static_wrench_fields import (
    INHERITED_TOLERANCE_POLICY,
    NAMED_DIRECTIONS,
    analytic_fixture_expectations,
    build_force_record,
    classify_directional_field,
    classify_scalar_field,
    direction_status_mask,
    paired_comparison_summary,
    paired_eligible,
    primary_eligible,
    rank_attribution_summary,
    regular_unit_arm_fixture,
    retained_force_record,
    status_mask,
    stretched_unit_arm_fixture,
    support_along,
    vertex_feasibility,
)
from inequality_mechanisms.metrics.static_wrench import (
    WrenchStateStatus,
    directional_capacity,
)
from inequality_mechanisms.metrics.wrench_directions import named_task_directions
from inequality_mechanisms.transmission_geometry import (
    METRIC_STATUS_AVAILABLE,
    KinematicGeometrySnapshot,
    rank_report,
)


def _vertex_set(vertices: np.ndarray) -> set[tuple[float, float]]:
    return {(round(float(x), 12), round(float(y), 12)) for x, y in vertices}


def _synthetic_item(
    wrench,
    *,
    mechanism_id: str = "fourbar",
    source_failure_code: str | None = None,
) -> ConsumedSourceRow:
    identity = SourceIdentity(
        case_id="synthetic",
        q_sample_id="q0",
        mechanism_id=mechanism_id,
        mechanism_pair_id="pair",
        grid_index=(0, 0),
        config_digest="c" * 64,
        source_revision=None,
        source_relpath="synthetic.jsonl",
    )
    row = AtlasRow(
        q_sample_id="q0",
        mechanism_id=mechanism_id,
        mechanism_pair_id="pair",
        grid_index=(0, 0),
        snapshot=None,
        config_digest="c" * 64,
        git_revision=None,
        failure_code=source_failure_code,
        failure_message=None,
    )
    return ConsumedSourceRow(
        identity=identity,
        row=row,
        wrench=wrench,
        source_failure_code=source_failure_code,
        source_failure_message=None,
    )


def test_directional_capacity_docstring_is_ray_not_support() -> None:
    doc = directional_capacity.__doc__ or ""
    assert "ray" in doc.lower()
    assert "support function" in doc.lower() or "not the support" in doc.lower()


def test_regular_unit_arm_fixture_matches_sprint_table() -> None:
    expected = analytic_fixture_expectations()["regular_unit_arm"]
    wrench = regular_unit_arm_fixture()
    assert wrench.status == WrenchStateStatus.REGULAR
    np.testing.assert_allclose(wrench.q, [0.0, math.pi / 2.0])
    np.testing.assert_allclose(wrench.x, [1.0, 1.0])
    assert wrench.vertices is not None
    assert _vertex_set(wrench.vertices) == _vertex_set(
        np.asarray(expected["vertices_ccw"], dtype=np.float64)
    )
    assert wrench.isotropic_radius == pytest.approx(expected["isotropic_radius"])
    assert wrench.directional_capacity["positive_x"] == pytest.approx(
        expected["positive_x_ray"]
    )
    assert wrench.directional_capacity["positive_y"] == pytest.approx(
        expected["positive_y_ray"]
    )
    support_y = support_along(wrench.vertices, [0.0, 1.0])
    assert support_y == pytest.approx(expected["positive_y_support_diagnostic"])
    assert support_y == pytest.approx(2.0)
    assert wrench.directional_capacity["positive_y"] == pytest.approx(1.0)
    assert wrench.directional_capacity["radial"] == pytest.approx(math.sqrt(2.0))
    assert wrench.directional_capacity["tangential"] == pytest.approx(
        1.0 / math.sqrt(2.0)
    )
    assert expected["radial_ray"] == pytest.approx(math.sqrt(2.0))
    assert expected["tangential_ray"] == pytest.approx(1.0 / math.sqrt(2.0))
    feas = vertex_feasibility(wrench)
    assert feas.ok
    assert feas.n_vertices == 4
    assert primary_eligible(wrench)


@pytest.mark.parametrize(
    "vertices",
    [
        np.zeros((4, 2)),
        np.zeros((0, 2)),
        np.zeros((3, 2)),
        np.zeros((4, 3)),
        np.full((4, 2), np.nan),
        np.full((4, 2), np.inf),
        None,
    ],
)
def test_full_rank_polygon_requires_four_finite_corner_vertices(vertices) -> None:
    wrench = replace(regular_unit_arm_fixture(), vertices=vertices)
    feasibility = vertex_feasibility(wrench)
    assert not feasibility.ok
    assert feasibility.failure_code is not None
    assert json.loads(strict_json_dumps(feasibility.details)) is not None


def test_interior_polygon_is_feasible_but_does_not_reach_effort_box_corners() -> None:
    wrench = regular_unit_arm_fixture()
    assert wrench.vertices is not None
    interior = replace(wrench, vertices=wrench.vertices / 2.0)
    feasibility = vertex_feasibility(interior)
    assert feasibility.max_hrep_residual is not None
    assert feasibility.max_hrep_residual < 0.0
    assert feasibility.max_corner_saturation_residual == pytest.approx(0.5)
    assert not feasibility.ok


def test_four_repetitions_of_one_valid_corner_do_not_form_complete_polygon() -> None:
    wrench = regular_unit_arm_fixture()
    assert wrench.vertices is not None
    duplicate = replace(wrench, vertices=np.repeat(wrench.vertices[:1], 4, axis=0))
    feasibility = vertex_feasibility(duplicate)
    assert feasibility.max_corner_saturation_residual == pytest.approx(0.0)
    assert feasibility.details["n_distinct_actuator_corners"] == 1
    assert not feasibility.ok


def test_near_singular_residual_failure_remains_diagnostic() -> None:
    wrench = regular_unit_arm_fixture()
    assert wrench.vertices is not None
    diagnostic = replace(
        wrench,
        status=WrenchStateStatus.NEAR_SINGULAR,
        vertices=wrench.vertices * (1.0 - 2e-6),
    )
    record = retained_force_record(_synthetic_item(diagnostic))
    assert record["vertex_feasibility"]["ok"] is False
    assert record["status"] == "near_singular"
    assert record["source_failure_code"] is None
    assert record["isotropic_radius_field"]["value"] is not None
    assert record["primary_eligible"] is False


def test_stretched_unit_arm_fixture_matches_sprint_table() -> None:
    expected = analytic_fixture_expectations()["stretched_unit_arm"]
    wrench = stretched_unit_arm_fixture()
    assert wrench.status == WrenchStateStatus.UNBOUNDED_IDEAL_DIRECTION
    assert wrench.vertices is None
    assert wrench.rank < 2
    assert wrench.isotropic_radius == pytest.approx(expected["isotropic_radius"])
    assert math.isinf(wrench.directional_capacity["positive_x"])
    assert wrench.directional_capacity["positive_y"] == pytest.approx(
        expected["positive_y_ray"]
    )
    scalar = classify_scalar_field(wrench)
    assert scalar["status"] == "masked_nonregular"
    assert scalar["value"] == pytest.approx(0.5)
    assert not primary_eligible(wrench)
    px = classify_directional_field(wrench, "positive_x")
    py = classify_directional_field(wrench, "positive_y")
    assert px["status"] == "unbounded"
    assert px["value"] is None
    assert py["status"] == "finite"
    assert py["value"] == pytest.approx(0.5)


def test_force_record_retains_hrep_and_rank_attribution() -> None:
    wrench = regular_unit_arm_fixture()
    item = _synthetic_item(wrench)
    record = build_force_record(item)
    assert record["status"] == "regular"
    assert record["wrench"]["hrep_a"] is not None
    assert record["vertex_feasibility"]["ok"] is True
    assert record["rank_attribution"]["j_xu"] == "full_rank"
    assert record["primary_eligible"] is True
    text = strict_json_dumps(record)
    assert "NaN" not in text
    assert "Infinity" not in text


def test_retained_row_copies_complete_scientific_record_without_rank_recompute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from inequality_mechanisms.experiments.v4 import intrinsic_static_wrench_fields

    wrench = regular_unit_arm_fixture()
    reports = {
        "u_to_q": rank_report(wrench.j_g, tolerance=1e-7),
        "q_to_x": rank_report(wrench.j_f, tolerance=2e-7),
        "u_to_x": rank_report(wrench.j_xu, tolerance=3e-7),
    }
    policy = {"mode": "absolute", "value": 1e-7, "origin": "source_fixture"}
    tolerances = {name: report.tolerance for name, report in reports.items()}
    snapshot = KinematicGeometrySnapshot(
        q=tuple(wrench.q),
        u=tuple(wrench.u),
        x=tuple(wrench.x),
        j_u_to_q=tuple(tuple(row) for row in wrench.j_g),
        j_q_to_x=tuple(tuple(row) for row in wrench.j_f),
        j_u_to_x=tuple(tuple(row) for row in wrench.j_xu),
        rank_u_to_q=reports["u_to_q"],
        rank_q_to_x=reports["q_to_x"],
        rank_u_to_x=reports["u_to_x"],
        actuator_weight=((1.0, 0.0), (0.0, 1.0)),
        actuator_metric_on_q=((1.0, 0.0), (0.0, 1.0)),
        mobility_on_q=((1.0, 0.0), (0.0, 1.0)),
        mobility_on_x=((2.0, -1.0), (-1.0, 1.0)),
        metric_status=METRIC_STATUS_AVAILABLE,
        provenance={"rank_tolerance_policy": policy, "rank_tolerances": tolerances},
    )
    item = _synthetic_item(wrench)
    item = replace(item, row=replace(item.row, snapshot=snapshot))

    def forbidden_rank_recompute(*args, **kwargs):
        pytest.fail("retaining a source rank report must not recompute rank")

    monkeypatch.setattr(
        intrinsic_static_wrench_fields, "rank_report", forbidden_rank_recompute
    )
    record = retained_force_record(item)
    original = wrench.to_dict()
    assert record["wrench_schema_version"] == original["schema_version"]
    for key, value in original.items():
        if key != "schema_version":
            assert record[key] == value
    assert record["rank_reports"] == {
        name: report.to_dict() for name, report in reports.items()
    }
    assert record["rank_tolerance_policy"] == policy
    assert record["rank_tolerances"] == tolerances
    np.testing.assert_allclose(
        record["direction_vectors"]["radial"], [1 / math.sqrt(2)] * 2
    )
    # Returned metadata cannot mutate the inherited source provenance.
    record["rank_tolerance_policy"]["value"] = 99
    assert snapshot.provenance["rank_tolerance_policy"]["value"] == 1e-7
    decoded = json.loads(strict_json_dumps(record))
    assert decoded["hrep_a"] == original["hrep_a"]


@pytest.fixture(scope="module")
def real_regular_scientific_record():
    """One frozen source row, independently restored through the accepted API."""
    case_id = "span_j1_095_j2_095"
    source_rel = f"geometry_atlas/cases/{case_id}/geometry_samples.jsonl.gz"
    path = canonical_v4_2b_retained_root() / Path(source_rel)
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        source = json.loads(next(handle))
    row = parse_retained_atlas_row(source)
    identity = SourceIdentity(
        case_id=case_id,
        q_sample_id=row.q_sample_id,
        mechanism_id=row.mechanism_id,
        mechanism_pair_id=row.mechanism_pair_id,
        grid_index=row.grid_index,
        config_digest=row.config_digest,
        source_revision=row.git_revision,
        source_relpath=source_rel,
    )
    record = to_strict_jsonable(
        retained_force_record(evaluate_restored_row(identity, row))
    )
    assert record["status"] == "regular"
    return record, source


def test_strict_scientific_validator_accepts_actual_regular_source_row(
    real_regular_scientific_record,
) -> None:
    from inequality_mechanisms.audits.v4_3_artifact import (
        _validate_row,
        _verify_source_record,
    )

    record, source = real_regular_scientific_record
    _validate_row(record)
    _verify_source_record(record, source, legacy=False)


@pytest.mark.parametrize(
    "corruption", ["isotropic_scale", "named_direction", "status", "duplicate_corner"]
)
def test_strict_scientific_validator_rejects_internally_consistent_corruption(
    real_regular_scientific_record, corruption: str
) -> None:
    from inequality_mechanisms.audits.v4_3_artifact import (
        _validate_row,
        _verify_source_record,
    )

    original, source = real_regular_scientific_record
    record = deepcopy(original)
    if corruption == "isotropic_scale":
        record["isotropic_radius"] *= 10.0
        record["isotropic_radius_field"]["value"] = record["isotropic_radius"]
    elif corruption == "named_direction":
        record["direction_vectors"]["positive_x"] = [0.0, 1.0]
    elif corruption == "status":
        record["status"] = "near_singular"
        record["primary_eligible"] = False
        record["isotropic_radius_field"].update(
            status="masked_nonregular", reason="near_singular"
        )
    else:
        record["vertices"] = [record["vertices"][0]] * 4
    with pytest.raises(V4_3ArtifactError):
        _validate_row(record)
        _verify_source_record(record, source, legacy=False)


def test_origin_undefined_directions_do_not_suppress_cartesian() -> None:
    wrench = regular_unit_arm_fixture()
    # Move endpoint to the origin so radial/tangential become undefined.
    origin_wrench = replace(
        wrench,
        x=np.array([0.0, 0.0], dtype=np.float64),
        directional_capacity={
            "positive_x": wrench.directional_capacity["positive_x"],
            "positive_y": wrench.directional_capacity["positive_y"],
            "radial": float("nan"),
            "tangential": float("nan"),
        },
        undefined_directions=("radial", "tangential"),
    )
    # Recompute capacities with origin directions for realism.
    named = named_task_directions([0.0, 0.0])
    assert named["radial"] is None
    fields = direction_status_mask(_synthetic_item(origin_wrench))
    assert fields["positive_x"]["status"] == "finite"
    assert fields["positive_y"]["status"] == "finite"
    assert fields["radial"]["status"] == "undefined"
    assert fields["tangential"]["status"] == "undefined"
    text = strict_json_dumps(fields)
    decoded = json.loads(text)
    assert decoded["radial"]["value"] is None


def test_paired_eligibility_excludes_unbounded_and_nonpositive() -> None:
    regular = regular_unit_arm_fixture()
    stretch = stretched_unit_arm_fixture()
    ok, reason = paired_eligible(regular, stretch, key="isotropic_radius")
    assert ok is False
    assert reason is not None
    ok2, reason2 = paired_eligible(regular, regular, key="isotropic_radius")
    assert ok2 is True
    assert reason2 is None

    left = _synthetic_item(regular, mechanism_id="fourbar")
    right = _synthetic_item(regular, mechanism_id="span_matched_gearbox")
    # Nonpositive denominator: force right isotropic to zero via replace.
    zero_right = replace(regular, isotropic_radius=0.0)
    right_zero = _synthetic_item(zero_right, mechanism_id="span_matched_gearbox")
    pair = PairedPhysicalSample(
        case_id="synthetic",
        q_sample_id="q0",
        grid_index=(0, 0),
        arms={
            "fourbar": left,
            "span_matched_gearbox": right_zero,
            "identity_on_shared_q": _synthetic_item(
                regular, mechanism_id="identity_on_shared_q"
            ),
        },
    )
    summary = paired_comparison_summary([pair])
    assert summary["n_eligible"] == 0
    assert summary["exclusion_counts"]["nonpositive_denominator"] == 1

    pair_ok = PairedPhysicalSample(
        case_id="synthetic",
        q_sample_id="q0",
        grid_index=(0, 0),
        arms={
            "fourbar": left,
            "span_matched_gearbox": right,
            "identity_on_shared_q": _synthetic_item(
                regular, mechanism_id="identity_on_shared_q"
            ),
        },
    )
    summary_ok = paired_comparison_summary([pair_ok])
    assert summary_ok["n_eligible"] == 1
    cmp0 = summary_ok["comparisons"][0]
    assert cmp0["eligible"] is True
    assert cmp0["ratio"]["value"] == pytest.approx(1.0)
    assert summary_ok["shared_color_limits"]["vmin"] is not None


def test_all_status_classes_survive_strict_json() -> None:
    regular = regular_unit_arm_fixture()
    stretch = stretched_unit_arm_fixture()
    payloads = [
        classify_scalar_field(regular),
        classify_scalar_field(stretch),
        classify_directional_field(stretch, "positive_x"),
        classify_directional_field(stretch, "positive_y"),
        classify_scalar_field(None, source_failure_code="missing_snapshot"),
        build_force_record(_synthetic_item(regular)),
        build_force_record(_synthetic_item(stretch)),
        rank_attribution_summary(_synthetic_item(stretch)),
        {"named_directions": list(NAMED_DIRECTIONS)},
        {"tolerances": INHERITED_TOLERANCE_POLICY},
    ]
    for payload in payloads:
        text = strict_json_dumps(payload)
        decoded = json.loads(text)
        assert decoded is not None


def test_smoke_pairs_produce_status_mask_and_comparisons() -> None:
    selection, consumed, pairs = resolve_smoke_selection()
    assert selection.n_records == 60
    assert all(item.wrench is not None for item in consumed)
    records = [retained_force_record(item) for item in consumed]
    assert len(records) == 60
    assert all(rec["vertex_feasibility"] is not None for rec in records)
    for item, record in zip(consumed, records, strict=True):
        assert item.row.snapshot is not None
        snapshot = item.row.snapshot.to_dict()
        assert record["rank_reports"] == snapshot["rank_reports"]
        assert (
            record["rank_tolerance_policy"]
            == (snapshot["provenance"]["rank_tolerance_policy"])
        )
        assert record["rank_tolerances"] == (snapshot["provenance"]["rank_tolerances"])
        assert record["hrep_a"] is not None
        assert set(record["direction_vectors"]) == set(NAMED_DIRECTIONS)
    mask = status_mask(pairs)
    assert mask["n_cells"] == 20
    assert sum(mask["status_counts"].values()) == 60
    summary = paired_comparison_summary(pairs, key="isotropic_radius")
    assert summary["n_pairs"] == 20
    assert summary["n_eligible"] + sum(summary["exclusion_counts"].values()) == 20
    # Directional comparison remains independent.
    dir_summary = paired_comparison_summary(pairs, key="positive_x")
    assert dir_summary["n_pairs"] == 20
