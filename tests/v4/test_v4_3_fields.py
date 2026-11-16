"""V4-302–305: force records, scalar/directional fields, and status transport."""

from __future__ import annotations

import json
import math
from dataclasses import replace

import numpy as np
import pytest

from inequality_mechanisms.audits.v4_3_artifact import strict_json_dumps
from inequality_mechanisms.experiments.v4.geometry_atlas import AtlasRow
from inequality_mechanisms.experiments.v4.intrinsic_static_wrench import (
    ConsumedSourceRow,
    PairedPhysicalSample,
    SourceIdentity,
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
    feas = vertex_feasibility(wrench)
    assert feas.ok
    assert feas.n_vertices == 4
    assert primary_eligible(wrench)


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
    records = [build_force_record(item) for item in consumed]
    assert len(records) == 60
    assert all(rec["vertex_feasibility"] is not None for rec in records)
    mask = status_mask(pairs)
    assert mask["n_cells"] == 20
    assert sum(mask["status_counts"].values()) == 60
    summary = paired_comparison_summary(pairs, key="isotropic_radius")
    assert summary["n_pairs"] == 20
    assert summary["n_eligible"] + sum(summary["exclusion_counts"].values()) == 20
    # Directional comparison remains independent.
    dir_summary = paired_comparison_summary(pairs, key="positive_x")
    assert dir_summary["n_pairs"] == 20
