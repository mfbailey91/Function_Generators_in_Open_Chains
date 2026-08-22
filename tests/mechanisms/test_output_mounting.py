"""V4.2B mounted-output adapter proof contract (V4-221)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from inequality_mechanisms.mechanisms.operating_branch import (
    OperatingBranch,
    unit_gearbox_branch,
)
from inequality_mechanisms.mechanisms.output_mounting import (
    MountedOutputMechanism,
    mount_operating_branch,
)

_ATOL = 1e-12
_FD_ATOL = 1e-8
_FOURBAR_ATOL = 1e-9


def _central_jacobian(
    branch: OperatingBranch, u: np.ndarray, *, eps: float = 1e-6
) -> np.ndarray:
    n = int(u.size)
    j = np.zeros((n, n), dtype=np.float64)
    for axis in range(n):
        step = np.zeros(n, dtype=np.float64)
        step[axis] = eps
        qp = branch.forward(u + step)
        qm = branch.forward(u - step)
        j[:, axis] = (qp - qm) / (2.0 * eps)
    return j


def _u_samples(branch: OperatingBranch) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    cert = branch.certificate
    lo = np.asarray(cert.input_lower, dtype=np.float64)
    hi = np.asarray(cert.input_upper, dtype=np.float64)
    return lo.copy(), 0.5 * (lo + hi), hi.copy()


def _provenance(branch: OperatingBranch) -> dict[str, Any]:
    selector = dict(branch.selector)
    return {
        "output_coordinate_kind": selector.get("output_coordinate_kind"),
        "native_output_offset_rad": selector.get("native_output_offset_rad"),
        "mounting_application_count": selector.get("mounting_application_count"),
    }


def _assert_round_trip(
    native: OperatingBranch,
    mounted: OperatingBranch,
    offset: np.ndarray,
    samples: tuple[np.ndarray, ...],
    *,
    atol: float = _ATOL,
) -> None:
    for u in samples:
        q_joint = mounted.forward(u)
        np.testing.assert_allclose(q_joint, native.forward(u) - offset, atol=atol)
        np.testing.assert_allclose(mounted.inverse(q_joint), u, atol=atol)


def _assert_axis_inverses_shifted(
    native: OperatingBranch,
    mounted: OperatingBranch,
    offset: np.ndarray,
) -> None:
    native_axes = native.to_dict()["axis_inverses"]
    mounted_axes = mounted.to_dict()["axis_inverses"]
    assert len(native_axes) == len(mounted_axes) == int(offset.size)
    for i, (before, after) in enumerate(zip(native_axes, mounted_axes, strict=True)):
        delta = float(offset[i])
        assert after["kind"] == before["kind"]
        if before["kind"] == "affine":
            assert after["q_ref"] == pytest.approx(float(before["q_ref"]) - delta)
            assert after["ratio"] == pytest.approx(before["ratio"])
            assert after["u_ref"] == pytest.approx(before["u_ref"])
        elif before["kind"] == "monotone_table":
            expected = [float(q) - delta for q in before["q_table"]]
            np.testing.assert_allclose(after["q_table"], expected, atol=_ATOL)
            np.testing.assert_allclose(after["u_table"], before["u_table"], atol=_ATOL)
            assert after["sign"] == before["sign"]
        else:
            raise AssertionError(f"unexpected axis inverse kind {before['kind']!r}")


def _assert_preserved_certificate_and_selector(
    native: OperatingBranch,
    mounted: OperatingBranch,
    offset: np.ndarray,
) -> None:
    np.testing.assert_allclose(
        mounted.certificate.input_lower, native.certificate.input_lower, atol=_ATOL
    )
    np.testing.assert_allclose(
        mounted.certificate.input_upper, native.certificate.input_upper, atol=_ATOL
    )
    np.testing.assert_allclose(
        mounted.certificate.min_abs_gain, native.certificate.min_abs_gain, atol=_ATOL
    )
    np.testing.assert_allclose(
        mounted.certificate.monotonic_sign,
        native.certificate.monotonic_sign,
        atol=_ATOL,
    )
    assert mounted.residual_tol == pytest.approx(native.residual_tol)
    assert mounted.mechanism.periodic_axes() == native.mechanism.periodic_axes()
    assert isinstance(mounted.mechanism, MountedOutputMechanism)
    assert mounted.mechanism.native.name == native.mechanism.name
    provenance = _provenance(mounted)
    assert provenance["output_coordinate_kind"] == "mounted_joint"
    np.testing.assert_allclose(
        provenance["native_output_offset_rad"], offset, atol=_ATOL
    )
    assert int(provenance["mounting_application_count"]) == 1


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


def _locked_registry():
    from inequality_mechanisms.audits.v4_artifact_guard import CANONICAL_REPO_ROOT
    from inequality_mechanisms.experiments.v4.span_controlled_atlas import (
        load_locked_v3_6d_registry,
    )
    from inequality_mechanisms.experiments.v4.span_controlled_atlas_config import (
        DEFAULT_CONFIG_REL,
        load_span_atlas_config,
    )

    config = load_span_atlas_config(CANONICAL_REPO_ROOT / DEFAULT_CONFIG_REL)
    return load_locked_v3_6d_registry(config)


def _midpoint(lo: float, hi: float) -> float:
    return 0.5 * (float(lo) + float(hi))


def test_scalar_offset_forward_inverse_and_jacobian() -> None:
    native = unit_gearbox_branch(1, input_lower=[-1.0], input_upper=[1.0])
    offset = np.asarray([0.4], dtype=np.float64)
    mounted = mount_operating_branch(native, offset)
    lo, mid, hi = _u_samples(native)
    _assert_round_trip(native, mounted, offset, (lo, mid, hi))
    np.testing.assert_allclose(mounted.jacobian(mid), native.jacobian(mid), atol=_ATOL)
    np.testing.assert_allclose(
        mounted.jacobian(mid), _central_jacobian(mounted, mid), atol=_FD_ATOL
    )
    _assert_axis_inverses_shifted(native, mounted, offset)


def test_two_axis_offset_round_trip() -> None:
    native = unit_gearbox_branch(2, input_lower=[-1.0, -2.0], input_upper=[1.0, 2.0])
    offset = np.asarray([0.4, -0.25], dtype=np.float64)
    mounted = mount_operating_branch(native, offset)
    lo, mid, hi = _u_samples(native)
    _assert_round_trip(native, mounted, offset, (lo, mid, hi))
    np.testing.assert_allclose(mounted.jacobian(mid), native.jacobian(mid), atol=_ATOL)
    np.testing.assert_allclose(
        mounted.jacobian(mid), _central_jacobian(mounted, mid), atol=_FD_ATOL
    )
    np.testing.assert_allclose(
        mounted.certificate.output_lower,
        np.asarray(native.certificate.output_lower) - offset,
        atol=_ATOL,
    )
    np.testing.assert_allclose(
        mounted.certificate.output_upper,
        np.asarray(native.certificate.output_upper) - offset,
        atol=_ATOL,
    )
    _assert_preserved_certificate_and_selector(native, mounted, offset)
    _assert_axis_inverses_shifted(native, mounted, offset)


def test_zero_offset_is_identity() -> None:
    native = unit_gearbox_branch(2, input_lower=[-1.0, -1.0], input_upper=[1.0, 1.0])
    offset = np.zeros(2, dtype=np.float64)
    mounted = mount_operating_branch(native, offset)
    lo, mid, hi = _u_samples(native)
    _assert_round_trip(native, mounted, offset, (lo, mid, hi))
    np.testing.assert_allclose(mounted.jacobian(mid), native.jacobian(mid), atol=_ATOL)
    provenance = _provenance(mounted)
    assert provenance["output_coordinate_kind"] == "mounted_joint"
    assert int(provenance["mounting_application_count"]) == 1
    np.testing.assert_allclose(
        provenance["native_output_offset_rad"], offset, atol=_ATOL
    )


def test_serialization_round_trip_and_provenance() -> None:
    native = unit_gearbox_branch(2, input_lower=[-1.0, -1.0], input_upper=[1.0, 1.0])
    offset = np.asarray([0.15, -0.05], dtype=np.float64)
    mounted = mount_operating_branch(native, offset)
    provenance = _provenance(mounted)
    assert provenance["output_coordinate_kind"] == "mounted_joint"
    np.testing.assert_allclose(
        provenance["native_output_offset_rad"], offset, atol=_ATOL
    )
    assert int(provenance["mounting_application_count"]) == 1

    restored = OperatingBranch.from_dict(mounted.to_dict())
    _, mid, _ = _u_samples(native)
    np.testing.assert_allclose(restored.forward(mid), mounted.forward(mid), atol=_ATOL)
    restored_prov = _provenance(restored)
    assert restored_prov["output_coordinate_kind"] == "mounted_joint"
    np.testing.assert_allclose(
        restored_prov["native_output_offset_rad"], offset, atol=_ATOL
    )
    assert int(restored_prov["mounting_application_count"]) == 1
    _assert_preserved_certificate_and_selector(native, restored, offset)


def test_double_application_raises() -> None:
    native = unit_gearbox_branch(1, input_lower=[-1.0], input_upper=[1.0])
    offset = np.asarray([0.3], dtype=np.float64)
    once = mount_operating_branch(native, offset)
    with pytest.raises(ValueError, match="already applied"):
        mount_operating_branch(once, offset)
    with pytest.raises(ValueError, match="already applied"):
        MountedOutputMechanism(once.mechanism, offset)


def test_one_fourbar_span_record(monkeypatch: pytest.MonkeyPatch) -> None:
    from inequality_mechanisms.experiments.span_cases import (
        generate_span_cases,
        realize_span_case,
    )
    from inequality_mechanisms.mechanisms.span_synthesis import PRIMARY_CERTIFICATE

    _block_synthesis(monkeypatch)
    before = PRIMARY_CERTIFICATE.to_dict()
    registry = _locked_registry()
    case = next(
        row
        for row in generate_span_cases()
        if row.span_j1_deg == 145.0 and row.span_j2_deg == 145.0
    )
    native_case = realize_span_case(case, registry)
    j1 = registry.record_for(145.0)
    j2 = registry.record_for(145.0)
    offset = np.asarray(
        [float(j1.q_offset_rad or 0.0), float(j2.q_offset_rad or 0.0)],
        dtype=np.float64,
    )
    native = native_case.fourbar
    mounted = mount_operating_branch(native, offset)
    lo, mid, hi = _u_samples(native)
    _assert_round_trip(native, mounted, offset, (lo, mid, hi), atol=_FOURBAR_ATOL)
    np.testing.assert_allclose(mounted.jacobian(mid), native.jacobian(mid), atol=_ATOL)
    np.testing.assert_allclose(
        mounted.jacobian(mid), _central_jacobian(mounted, mid), atol=1e-6
    )
    _assert_axis_inverses_shifted(native, mounted, offset)
    _assert_preserved_certificate_and_selector(native, mounted, offset)
    for axis in range(2):
        lo_q = float(mounted.certificate.output_lower[axis])
        hi_q = float(mounted.certificate.output_upper[axis])
        assert _midpoint(lo_q, hi_q) == pytest.approx(0.0, abs=_FOURBAR_ATOL)
    restored = OperatingBranch.from_dict(mounted.to_dict())
    np.testing.assert_allclose(restored.forward(mid), mounted.forward(mid), atol=_ATOL)
    assert PRIMARY_CERTIFICATE.to_dict() == before


def test_all_span_cases_match_registry_usable_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from inequality_mechanisms.experiments.span_cases import (
        generate_span_cases,
        realize_mounted_span_case,
        realize_span_case,
    )
    from inequality_mechanisms.experiments.v4.span_controlled_atlas_config import (
        SPAN_175_STATUS,
    )
    from inequality_mechanisms.mechanisms.span_registry import TARGET_SPANS_DEG
    from inequality_mechanisms.mechanisms.span_synthesis import PRIMARY_CERTIFICATE

    _block_synthesis(monkeypatch)
    before = PRIMARY_CERTIFICATE.to_dict()
    registry = _locked_registry()
    cases = generate_span_cases()
    assert len(cases) == 17
    seen_spans = {float(row.span_j1_deg) for row in cases} | {
        float(row.span_j2_deg) for row in cases
    }
    assert seen_spans == set(float(span) for span in TARGET_SPANS_DEG)
    assert registry.record_for(175.0).status == SPAN_175_STATUS

    for case in cases:
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
        fb = mounted.fourbar
        gb = mounted.gearbox
        for axis, interval in enumerate(usable):
            assert fb.certificate.output_lower[axis] == pytest.approx(
                interval[0], abs=_FOURBAR_ATOL
            )
            assert fb.certificate.output_upper[axis] == pytest.approx(
                interval[1], abs=_FOURBAR_ATOL
            )
            assert gb.certificate.output_lower[axis] == pytest.approx(
                interval[0], abs=_FOURBAR_ATOL
            )
            assert gb.certificate.output_upper[axis] == pytest.approx(
                interval[1], abs=_FOURBAR_ATOL
            )
            mid_q = _midpoint(
                fb.certificate.output_lower[axis],
                fb.certificate.output_upper[axis],
            )
            assert mid_q == pytest.approx(0.0, abs=_FOURBAR_ATOL)
        _, mid_u, _ = _u_samples(native.fourbar)
        np.testing.assert_allclose(
            fb.jacobian(mid_u), native.fourbar.jacobian(mid_u), atol=_ATOL
        )
        assert int(_provenance(fb)["mounting_application_count"]) == 1
        if case.span_j1_deg == 175.0:
            assert mounted.j1.status == SPAN_175_STATUS
        if case.span_j2_deg == 175.0:
            assert mounted.j2.status == SPAN_175_STATUS

    assert PRIMARY_CERTIFICATE.to_dict() == before
    assert registry.record_for(175.0).status == SPAN_175_STATUS
