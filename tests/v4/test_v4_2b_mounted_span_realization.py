"""V4.2B Phase 1: native-offset defect and mounted span-realization invariants."""

from __future__ import annotations

import numpy as np
import pytest

from inequality_mechanisms.audits.v4_artifact_guard import CANONICAL_REPO_ROOT
from inequality_mechanisms.experiments.span_cases import (
    generate_span_cases,
    realize_span_case,
)
from inequality_mechanisms.experiments.v4.span_controlled_atlas import (
    load_locked_v3_6d_registry,
)
from inequality_mechanisms.experiments.v4.span_controlled_atlas_config import (
    DEFAULT_CONFIG_REL,
    SPAN_175_STATUS,
    load_span_atlas_config,
)
from inequality_mechanisms.mechanisms.span_registry import TARGET_SPANS_DEG, SpanRegistry
from inequality_mechanisms.mechanisms.span_synthesis import PRIMARY_CERTIFICATE

_ATOL = 1e-9
_OFFSET_ATOL = 1e-12


def _block_synthesis(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("span synthesis must not run on the V4.2B path")

    monkeypatch.setattr(
        "inequality_mechanisms.mechanisms.span_registry.build_span_registry",
        boom,
    )
    monkeypatch.setattr(
        "inequality_mechanisms.mechanisms.span_synthesis.synthesize_span_family",
        boom,
    )


def _locked_registry() -> SpanRegistry:
    config = load_span_atlas_config(CANONICAL_REPO_ROOT / DEFAULT_CONFIG_REL)
    return load_locked_v3_6d_registry(config)


def _midpoint(lo: float, hi: float) -> float:
    return 0.5 * (float(lo) + float(hi))


def _interior_u(branch: object) -> np.ndarray:
    cert = branch.certificate  # type: ignore[attr-defined]
    lo = np.asarray(cert.input_lower, dtype=np.float64)
    hi = np.asarray(cert.input_upper, dtype=np.float64)
    return 0.5 * (lo + hi)


def test_current_realization_uses_native_not_mounted_q(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _block_synthesis(monkeypatch)
    before = PRIMARY_CERTIFICATE.to_dict()
    registry = _locked_registry()
    cases = generate_span_cases()
    for span_deg in TARGET_SPANS_DEG:
        record = registry.record_for(span_deg)
        assert record.range_definition is not None
        record.range_definition.assert_zero_centered()
        usable = record.range_definition.usable_interval_rad
        registry_mid = _midpoint(usable[0], usable[1])
        assert registry_mid == pytest.approx(0.0, abs=_ATOL)

        assert record.q_native_interval_rad is not None
        native_mid = _midpoint(*record.q_native_interval_rad)
        offset = float(record.q_offset_rad or 0.0)
        if abs(offset) > _OFFSET_ATOL:
            assert native_mid != pytest.approx(0.0, abs=_ATOL)
        assert native_mid != pytest.approx(registry_mid, abs=_ATOL)

        case = next(row for row in cases if row.span_j1_deg == float(span_deg))
        realized = realize_span_case(case, registry)
        axis_mid = _midpoint(
            realized.fourbar.certificate.output_lower[0],
            realized.fourbar.certificate.output_upper[0],
        )
        assert axis_mid == pytest.approx(native_mid, abs=1e-6)
        assert axis_mid != pytest.approx(registry_mid, abs=1e-6)
    assert PRIMARY_CERTIFICATE.to_dict() == before


def test_mounted_realization_matches_registry_usable_interval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from inequality_mechanisms.experiments.span_cases import realize_mounted_span_case

    _block_synthesis(monkeypatch)
    before = PRIMARY_CERTIFICATE.to_dict()
    registry = _locked_registry()
    assert registry.record_for(175.0).status == SPAN_175_STATUS

    for case in generate_span_cases():
        native = realize_span_case(case, registry)
        mounted = realize_mounted_span_case(case, registry)
        j1 = registry.record_for(case.span_j1_deg)
        j2 = registry.record_for(case.span_j2_deg)
        assert j1.range_definition is not None
        assert j2.range_definition is not None
        usable = (
            j1.range_definition.usable_interval_rad,
            j2.range_definition.usable_interval_rad,
        )
        fb = mounted.fourbar.certificate
        gb = mounted.gearbox.certificate
        for axis, interval in enumerate(usable):
            assert fb.output_lower[axis] == pytest.approx(interval[0], abs=_ATOL)
            assert fb.output_upper[axis] == pytest.approx(interval[1], abs=_ATOL)
            mid = _midpoint(fb.output_lower[axis], fb.output_upper[axis])
            assert mid == pytest.approx(0.0, abs=_ATOL)
            width = float(fb.output_upper[axis] - fb.output_lower[axis])
            assert width == pytest.approx(interval[1] - interval[0], abs=_ATOL)

        np.testing.assert_allclose(gb.input_lower, fb.input_lower, atol=_ATOL)
        np.testing.assert_allclose(gb.input_upper, fb.input_upper, atol=_ATOL)
        np.testing.assert_allclose(gb.output_lower, fb.output_lower, atol=_ATOL)
        np.testing.assert_allclose(gb.output_upper, fb.output_upper, atol=_ATOL)

        u = _interior_u(native.fourbar)
        np.testing.assert_allclose(
            mounted.fourbar.jacobian(u),
            native.fourbar.jacobian(u),
            atol=1e-12,
        )
        if case.span_j1_deg == 175.0:
            assert mounted.j1.status == SPAN_175_STATUS
        if case.span_j2_deg == 175.0:
            assert mounted.j2.status == SPAN_175_STATUS

    assert PRIMARY_CERTIFICATE.to_dict() == before
    assert registry.record_for(175.0).status == SPAN_175_STATUS
