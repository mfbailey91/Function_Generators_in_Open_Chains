"""V4-104 identity and span-matched controls."""

from __future__ import annotations

import numpy as np

from inequality_mechanisms.audits.v4_artifact_guard import REPO_ROOT
from inequality_mechanisms.experiments.v4.atlas_config import (
    DEFAULT_CONFIG_REL,
    load_atlas_config,
)
from inequality_mechanisms.experiments.v4.controls import (
    AtlasControlError,
    build_atlas_arms,
    fourbar_branch,
    span_matched_ratios,
)
from inequality_mechanisms.experiments.v4.geometry_atlas import evaluate_atlas_sample
from inequality_mechanisms.experiments.v4.shared_q_atlas import build_shared_q_bank
from inequality_mechanisms.mechanisms.operating_branch import unit_gearbox_branch


def test_span_ratios_and_identity_jg() -> None:
    config = load_atlas_config(REPO_ROOT / DEFAULT_CONFIG_REL)
    arms = build_atlas_arms(config)
    ratios = span_matched_ratios(arms["fourbar"].branch)
    assert ratios == tuple(arms["span_matched_gearbox"].provenance["ratios"])
    cert = arms["fourbar"].branch.certificate
    np.testing.assert_allclose(
        arms["identity_on_shared_q"].branch.certificate.output_lower,
        cert.output_lower,
    )
    np.testing.assert_allclose(
        arms["identity_on_shared_q"].branch.certificate.output_upper,
        cert.output_upper,
    )
    bank = build_shared_q_bank(
        cert.output_lower,
        cert.output_upper,
        shape=(3, 3),
        inset_fraction=0.01,
    )
    sample = bank.samples[4]
    gb = evaluate_atlas_sample(
        arms["span_matched_gearbox"], sample, config=config, revision="test"
    )
    ident = evaluate_atlas_sample(
        arms["identity_on_shared_q"], sample, config=config, revision="test"
    )
    assert gb.snapshot is not None and ident.snapshot is not None
    np.testing.assert_allclose(
        gb.snapshot.j_u_to_q, np.diag(ratios), atol=1e-12, rtol=0.0
    )
    np.testing.assert_allclose(ident.snapshot.j_u_to_q, np.eye(2))
    np.testing.assert_allclose(ident.snapshot.actuator_metric_on_q, np.eye(2), atol=1e-12)
    np.testing.assert_allclose(ident.snapshot.mobility_on_q, np.eye(2), atol=1e-12)


def test_tiny_unit_gearbox_does_not_cover_fourbar_q_box() -> None:
    config = load_atlas_config(REPO_ROOT / DEFAULT_CONFIG_REL)
    fourbar = fourbar_branch(config)
    tiny = unit_gearbox_branch(
        2, input_lower=[0.0, 0.0], input_upper=[0.05, 0.05], name="tiny"
    )
    q_span = np.asarray(fourbar.certificate.output_upper) - np.asarray(
        fourbar.certificate.output_lower
    )
    tiny_span = np.asarray(tiny.certificate.output_upper) - np.asarray(
        tiny.certificate.output_lower
    )
    assert np.any(tiny_span + 1e-12 < q_span)
    with np.testing.assert_raises(AssertionError):
        np.testing.assert_allclose(
            tiny.certificate.output_lower, fourbar.certificate.output_lower
        )
    try:
        if not (
            np.allclose(tiny.certificate.output_lower, fourbar.certificate.output_lower)
            and np.allclose(
                tiny.certificate.output_upper, fourbar.certificate.output_upper
            )
        ):
            raise AtlasControlError("span mismatch")
    except AtlasControlError as exc:
        assert exc.failure_code == "span_match_failed"
    else:
        raise AssertionError("expected AtlasControlError")
