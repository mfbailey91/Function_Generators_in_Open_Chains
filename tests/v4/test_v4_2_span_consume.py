"""V4-201/V4-202 consume frozen D and generate the 17-case union."""

from __future__ import annotations

import json

import numpy as np
import pytest

from inequality_mechanisms.audits.v4_artifact_guard import CANONICAL_REPO_ROOT
from inequality_mechanisms.experiments.span_cases import (
    case_id_for,
    generate_span_cases,
    realize_span_case,
)
from inequality_mechanisms.experiments.v4.span_controlled_atlas import (
    arms_for_realized,
    load_locked_v3_6d_registry,
)
from inequality_mechanisms.experiments.v4.span_controlled_atlas_config import (
    DEFAULT_CONFIG_REL,
    FROZEN_V3_6D_DIGEST,
    SPAN_175_STATUS,
    load_span_atlas_config,
)
from inequality_mechanisms.mechanisms.span_registry import load_span_registry
from inequality_mechanisms.mechanisms.span_synthesis import PRIMARY_CERTIFICATE


def test_committed_registry_matches_frozen_digest() -> None:
    config = load_span_atlas_config(CANONICAL_REPO_ROOT / DEFAULT_CONFIG_REL)
    payload = json.loads(
        (CANONICAL_REPO_ROOT / config.v3_6d_registry).read_text(encoding="utf-8")
    )
    registry = load_span_registry(payload)
    assert registry.sha256 == FROZEN_V3_6D_DIGEST
    assert payload["sha256"] == FROZEN_V3_6D_DIGEST
    locked = load_locked_v3_6d_registry(config)
    assert locked.sha256 == registry.sha256
    expected = {
        95.0: "certified_primary",
        135.0: "certified_primary",
        145.0: "certified_primary",
        150.0: "certified_primary",
        175.0: SPAN_175_STATUS,
    }
    for span, status in expected.items():
        assert locked.record_for(span).status == status


def test_synthesis_is_not_called_on_v4_2_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("span synthesis must not run on the V4.2 path")

    monkeypatch.setattr(
        "inequality_mechanisms.mechanisms.span_registry.build_span_registry",
        boom,
    )
    monkeypatch.setattr(
        "inequality_mechanisms.mechanisms.span_synthesis.synthesize_span_family",
        boom,
    )
    before = PRIMARY_CERTIFICATE.to_dict()
    config = load_span_atlas_config(CANONICAL_REPO_ROOT / DEFAULT_CONFIG_REL)
    registry = load_locked_v3_6d_registry(config)
    cases = generate_span_cases()
    realized = realize_span_case(cases[0], registry)
    assert realized.fourbar.certificate is not None
    assert PRIMARY_CERTIFICATE.to_dict() == before


def test_seventeen_generated_ids_and_dual_membership() -> None:
    cases = generate_span_cases()
    ids = [case.case_id for case in cases]
    assert len(cases) == 17
    assert len(set(ids)) == 17
    labeled = sum(len(case.memberships) for case in cases)
    assert labeled == 18
    dual = next(case for case in cases if case.case_id == case_id_for(145.0, 145.0))
    assert dual.memberships == ("core_span_sweep", "biological_refinement")
    assert case_id_for(95.0, 175.0) != case_id_for(175.0, 95.0)
    left = next(case for case in cases if case.case_id == case_id_for(95.0, 175.0))
    right = next(case for case in cases if case.case_id == case_id_for(175.0, 95.0))
    assert left.span_j1_deg == 95.0 and left.span_j2_deg == 175.0
    assert right.span_j1_deg == 175.0 and right.span_j2_deg == 95.0
    assert "span_j1_095_j2_175" in ids
    assert "span_j1_175_j2_095" in ids


def test_gearbox_endpoints_match_fourbar() -> None:
    config = load_span_atlas_config(CANONICAL_REPO_ROOT / DEFAULT_CONFIG_REL)
    registry = load_locked_v3_6d_registry(config)
    cases = {case.case_id: case for case in generate_span_cases()}
    for case_id in (
        case_id_for(145.0, 145.0),
        case_id_for(95.0, 175.0),
        case_id_for(175.0, 95.0),
    ):
        realized = realize_span_case(cases[case_id], registry)
        arms = arms_for_realized(
            realized, L1=config.planar2r.L1, L2=config.planar2r.L2
        )
        fb = arms["fourbar"].branch.certificate
        gb = arms["span_matched_gearbox"].branch.certificate
        np.testing.assert_allclose(gb.input_lower, fb.input_lower, atol=1e-12)
        np.testing.assert_allclose(gb.input_upper, fb.input_upper, atol=1e-12)
        np.testing.assert_allclose(gb.output_lower, fb.output_lower, atol=1e-12)
        np.testing.assert_allclose(gb.output_upper, fb.output_upper, atol=1e-12)
        ident = arms["identity_on_shared_q"].branch.certificate
        np.testing.assert_allclose(ident.output_lower, fb.output_lower, atol=1e-12)
        np.testing.assert_allclose(ident.output_upper, fb.output_upper, atol=1e-12)
