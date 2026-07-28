"""Tests for affine equivalent gearbox and gain-matching (S6-01–S6-05)."""

from __future__ import annotations

import numpy as np
import pytest

from inequality_mechanisms.mechanisms import (
    BASELINE_LABELS,
    EquivalentGearbox,
    IndependentFourBars,
    Mechanism,
    UnitGearbox,
    baseline_label_for_mechanism,
    match_equivalent_gearbox,
    verify_rms_match,
    verify_span_match,
    verify_tv_match,
)


def _central_jacobian(
    mech: Mechanism, u: np.ndarray, *, eps: float = 1e-6
) -> np.ndarray:
    n = mech.input_dim
    m = mech.output_dim
    J = np.zeros((m, n), dtype=np.float64)
    for j in range(n):
        e = np.zeros(n, dtype=np.float64)
        e[j] = eps
        qp = mech.input_to_output(u + e)
        qm = mech.input_to_output(u - e)
        J[:, j] = (qp - qm) / (2.0 * eps)
    return J


def _demo_fourbar() -> IndependentFourBars:
    return IndependentFourBars.from_lengths(
        [(1.0, 2.5, 2.0, 2.0), (1.0, 2.5, 2.0, 2.0)],
        branch=1,
        name="demo_fb",
    )


class TestEquivalentGearbox:
    def test_affine_map_and_jacobian(self) -> None:
        gb = EquivalentGearbox(
            [2.0, -0.5],
            u_ref=[0.1, 0.2],
            q_ref=[1.0, -1.0],
            matching_rule="span",
        )
        u = np.array([1.1, 2.2])
        expected = np.array([1.0 + 2.0 * 1.0, -1.0 + (-0.5) * 2.0])
        assert gb.input_to_output(u) == pytest.approx(expected)
        assert gb.output_jacobian(u) == pytest.approx(np.diag([2.0, -0.5]))

    def test_inverse_round_trip(self) -> None:
        gb = EquivalentGearbox(
            [1.5, 0.75],
            u_ref=[0.0, 0.0],
            q_ref=[0.2, -0.3],
            matching_rule="rms_gain",
        )
        q = np.array([1.0, -0.5])
        pre = gb.inverse_output(q)
        assert len(pre) == 1
        assert gb.input_to_output(pre[0]) == pytest.approx(q)

    def test_jacobian_matches_fd(self) -> None:
        gb = EquivalentGearbox(
            [1.2, 0.8],
            u_ref=[0.3, -0.1],
            q_ref=[0.0, 0.5],
            matching_rule="total_variation",
        )
        u = np.array([0.4, 0.6])
        assert gb.output_jacobian(u) == pytest.approx(
            _central_jacobian(gb, u), abs=1e-8
        )

    def test_serialization_round_trip(self) -> None:
        gb = EquivalentGearbox(
            [1.1, 0.9],
            u_ref=[0.0, 0.0],
            q_ref=[0.1, 0.2],
            matching_rule="span",
            name="eq_a",
            provenance={"note": "test"},
        )
        restored = Mechanism.from_dict(gb.to_dict())
        assert isinstance(restored, EquivalentGearbox)
        assert restored.matching_rule == "span"
        assert restored.name == "eq_a"
        u = np.array([0.5, -0.25])
        assert restored.input_to_output(u) == pytest.approx(gb.input_to_output(u))

    def test_zero_ratio_rejected(self) -> None:
        with pytest.raises(ValueError, match="nonzero"):
            EquivalentGearbox(
                [0.0, 1.0],
                u_ref=[0.0, 0.0],
                q_ref=[0.0, 0.0],
                matching_rule="span",
            )

    def test_invalid_rule_rejected(self) -> None:
        with pytest.raises(ValueError, match="matching_rule"):
            EquivalentGearbox(
                [1.0, 1.0],
                u_ref=[0.0, 0.0],
                q_ref=[0.0, 0.0],
                matching_rule="mean_gain",
            )


class TestMatchingFactory:
    def test_span_match_invariants(self) -> None:
        fb = _demo_fourbar()
        gb = match_equivalent_gearbox(fb, matching_rule="span")
        assert gb.matching_rule == "span"
        assert baseline_label_for_mechanism(gb) == "span_matched_gearbox"
        report = verify_span_match(gb, fb)
        assert report["ok"] is True

    def test_tv_match_invariants(self) -> None:
        fb = _demo_fourbar()
        gb = match_equivalent_gearbox(fb, matching_rule="total_variation")
        assert baseline_label_for_mechanism(gb) == "tv_matched_gearbox"
        report = verify_tv_match(gb, fb)
        assert report["ok"] is True

    def test_rms_match_invariants(self) -> None:
        fb = _demo_fourbar()
        gb = match_equivalent_gearbox(fb, matching_rule="rms_gain")
        assert baseline_label_for_mechanism(gb) == "rms_matched_gearbox"
        report = verify_rms_match(gb, fb)
        assert report["ok"] is True

    def test_unit_baseline_label(self) -> None:
        assert baseline_label_for_mechanism(UnitGearbox(dim=2)) == "unit_gearbox"
        assert "unit_gearbox" in BASELINE_LABELS
        assert "fourbar" in BASELINE_LABELS

    def test_deterministic_under_fixed_samples(self) -> None:
        fb = _demo_fourbar()
        a = match_equivalent_gearbox(fb, matching_rule="rms_gain", n_samples=181)
        b = match_equivalent_gearbox(fb, matching_rule="rms_gain", n_samples=181)
        assert a.ratios == pytest.approx(b.ratios)
        assert a.u_ref == pytest.approx(b.u_ref)
        assert a.q_ref == pytest.approx(b.q_ref)
