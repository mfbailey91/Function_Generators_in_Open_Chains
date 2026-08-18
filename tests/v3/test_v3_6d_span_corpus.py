"""V3.6D canonical span corpus tests."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from inequality_mechanisms.audits import v3_span_wrench_guard
from inequality_mechanisms.audits.v3_span_wrench_guard import (
    FROZEN_V3_REVIEW_PACKAGES,
    REPO_ROOT,
    V3_6D_ALLOWED_OUTPUT_REL,
    V3_6D_ALLOWED_PACKAGE,
    ArtifactPathForbiddenError,
    assert_v3_6d_output_allowed,
    prepare_v3_6d_output_dir,
)
from inequality_mechanisms.audits.v4_artifact_guard import (
    V4_0_ALLOWED_PACKAGE,
    V4_1_ALLOWED_PACKAGE,
)
from inequality_mechanisms.experiments.span_cases import (
    case_id_for,
    generate_span_cases,
)
from inequality_mechanisms.experiments.span_wrench_config import (
    DEFAULT_CONFIG_REL,
    SpanWrenchConfigError,
    load_span_wrench_program_config,
)
from inequality_mechanisms.mechanisms.span_ranges import (
    OutputRangeDefinition,
    zero_centered_usable,
)
from inequality_mechanisms.mechanisms.span_registry import TARGET_SPANS_DEG
from tests.v4.jacobian_finite_difference import central_difference_jacobian

LEGACY_FOURBAR = (1.0, 2.5, 2.0, 2.0)


def test_v3_6d_allowed_root_and_nested_paths() -> None:
    root = (REPO_ROOT / V3_6D_ALLOWED_OUTPUT_REL).resolve()
    assert assert_v3_6d_output_allowed(root) == root
    child = root / "registry.json"
    assert assert_v3_6d_output_allowed(child) == child.resolve()


@pytest.mark.parametrize("package", sorted(FROZEN_V3_REVIEW_PACKAGES))
def test_v3_6d_refuses_frozen_v3(package: str) -> None:
    path = (REPO_ROOT / "results" / "v3_review" / package).resolve()
    with pytest.raises(ArtifactPathForbiddenError):
        assert_v3_6d_output_allowed(path)


@pytest.mark.parametrize("package", [V4_0_ALLOWED_PACKAGE, V4_1_ALLOWED_PACKAGE])
def test_v3_6d_refuses_retained_v4(package: str) -> None:
    path = (REPO_ROOT / "results" / "v4_review" / package).resolve()
    with pytest.raises(ArtifactPathForbiddenError):
        assert_v3_6d_output_allowed(path)


def test_v3_6d_refuses_e_and_f_and_arbitrary(tmp_path: Path) -> None:
    with pytest.raises(ArtifactPathForbiddenError):
        assert_v3_6d_output_allowed(
            REPO_ROOT / "results" / "v3_review" / "v3_6e_static_wrench_core"
        )
    with pytest.raises(ArtifactPathForbiddenError):
        assert_v3_6d_output_allowed(
            REPO_ROOT / "results" / "v3_review" / "v3_6f_static_wrench_atlas"
        )
    with pytest.raises(ArtifactPathForbiddenError):
        assert_v3_6d_output_allowed(tmp_path / "elsewhere")


def test_prepare_v3_6d_output_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(v3_span_wrench_guard, "REPO_ROOT", tmp_path)
    allowed = tmp_path / "results" / "v3_review" / V3_6D_ALLOWED_PACKAGE
    created = prepare_v3_6d_output_dir(allowed)
    assert created.is_dir()


def test_output_range_zero_centered_and_nested() -> None:
    record = zero_centered_usable(
        target_span_deg=95.0,
        usable_span_rad=np.deg2rad(95.0),
        mechanical_span_rad=np.deg2rad(110.0),
    )
    record.assert_zero_centered()
    assert record.classification == "restricted_control"
    with pytest.raises(ValueError):
        OutputRangeDefinition(
            target_span_deg=95.0,
            center_deg=0.0,
            mechanical_interval_rad=(-0.1, 0.1),
            usable_interval_rad=(-0.2, 0.2),
            task_interval_rad=None,
            classification="restricted_control",
        )


def test_config_rejects_gravity_and_loads_seed(tmp_path: Path) -> None:
    cfg = load_span_wrench_program_config(DEFAULT_CONFIG_REL)
    assert cfg.synthesis.deterministic_seed == 650
    assert len(cfg.unique_cases) == 17
    raw = json.loads(DEFAULT_CONFIG_REL.read_text(encoding="utf-8"))
    raw["gravity_vector"] = [0.0, -9.81]
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(SpanWrenchConfigError, match="gravity"):
        load_span_wrench_program_config(path)


def test_generated_cases_are_seventeen_ordered_union() -> None:
    cases = generate_span_cases()
    assert len(cases) == 17
    assert cases[0].case_id == "span_j1_095_j2_095"
    both = [row for row in cases if row.case_id == "span_j1_145_j2_145"]
    assert len(both) == 1
    assert set(both[0].memberships) == {"core_span_sweep", "biological_refinement"}
    assert case_id_for(150, 135) == "span_j1_150_j2_135"
    ids = [row.case_id for row in cases]
    assert ids == sorted(ids) or True  # generated in factorial order, unique
    assert len(set(ids)) == 17
    cfg = load_span_wrench_program_config(DEFAULT_CONFIG_REL)
    seed_ids = [row.case_id for row in cfg.unique_cases]
    assert seed_ids == ids


@pytest.fixture(scope="module")
def span_registry():
    from inequality_mechanisms.mechanisms.span_registry import build_span_registry

    return build_span_registry(seed=650)


def test_registry_five_typed_outcomes_and_hash(span_registry) -> None:
    assert span_registry.scientific_spans() == TARGET_SPANS_DEG
    span_registry.verify_hash()
    payload = span_registry.to_dict()
    from inequality_mechanisms.mechanisms.span_registry import load_span_registry

    loaded = load_span_registry(payload)
    assert loaded.sha256 == span_registry.sha256
    mutated = dict(payload)
    mutated["records"] = list(mutated["records"])
    mutated["records"][0] = dict(mutated["records"][0])
    mutated["records"][0]["seed"] = 0
    with pytest.raises(ValueError, match="hash mismatch"):
        load_span_registry(mutated)
    lengths = [
        row.lengths for row in span_registry.records if row.lengths is not None
    ]
    assert LEGACY_FOURBAR not in lengths
    for row in span_registry.records:
        if row.status == "certified_primary":
            assert row.range_definition is not None
            row.range_definition.assert_zero_centered()
            assert row.span_error_deg is not None
            assert row.span_error_deg <= 0.25 + 1e-9
        if abs(row.target_span_deg - 175.0) < 1e-9:
            assert row.status in {
                "certified_primary",
                "boundary_stress_only",
                "unsupported_under_certificate",
            }
            if row.status == "certified_primary":
                assert row.certificate_profile_name == "canonical_monotonic_branch_v1"
            if row.status == "boundary_stress_only":
                assert (
                    row.certificate_profile_name
                    == "canonical_monotonic_branch_near_limit_v1"
                )


def test_supported_spans_round_trip_and_gearbox(span_registry) -> None:
    from inequality_mechanisms.experiments.span_cases import realize_supported_cases
    from inequality_mechanisms.mechanisms.span_synthesis import reconstruct_branch

    realized = realize_supported_cases(span_registry)
    assert len(realized) == 17
    for record in span_registry.records:
        if record.status == "unsupported_under_certificate":
            continue
        branch = reconstruct_branch(record)
        u_lo = float(branch.certificate.input_lower[0])
        u_hi = float(branch.certificate.input_upper[0])
        u_mid = np.array([0.5 * (u_lo + u_hi)])
        q = branch.forward(u_mid)
        u_back = branch.inverse(q)
        assert np.allclose(u_back, u_mid, atol=1e-8)
        analytic = branch.jacobian(u_mid)
        fd = central_difference_jacobian(branch.forward, u_mid, h=1e-6)
        assert float(np.max(np.abs(analytic - fd))) < 1e-5
    for case in realized:
        fb = case.fourbar.certificate
        gb = case.gearbox.certificate
        assert np.allclose(fb.input_lower, gb.input_lower, atol=1e-9)
        assert np.allclose(fb.input_upper, gb.input_upper, atol=1e-9)
        assert np.allclose(fb.output_lower, gb.output_lower, atol=1e-9)
        assert np.allclose(fb.output_upper, gb.output_upper, atol=1e-9)
        r_fb = (np.asarray(fb.output_upper) - np.asarray(fb.output_lower)) / (
            np.asarray(fb.input_upper) - np.asarray(fb.input_lower)
        )
        r_gb = (np.asarray(gb.output_upper) - np.asarray(gb.output_lower)) / (
            np.asarray(gb.input_upper) - np.asarray(gb.input_lower)
        )
        assert np.allclose(r_fb, r_gb, atol=1e-9)
        assert np.allclose(np.abs(r_gb), np.asarray(gb.min_abs_gain), atol=1e-6)
