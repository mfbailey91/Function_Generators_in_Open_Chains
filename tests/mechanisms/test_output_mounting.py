"""V4.2B Phase 1: serializable mounted-output adapter contract (V4-221)."""

from __future__ import annotations

from typing import Any

import numpy as np

from inequality_mechanisms.mechanisms.operating_branch import (
    OperatingBranch,
    unit_gearbox_branch,
)


def _central_jacobian(branch: OperatingBranch, u: np.ndarray, *, eps: float = 1e-6) -> np.ndarray:
    n = int(u.size)
    j = np.zeros((n, n), dtype=np.float64)
    for axis in range(n):
        step = np.zeros(n, dtype=np.float64)
        step[axis] = eps
        qp = branch.forward(u + step)
        qm = branch.forward(u - step)
        j[:, axis] = (qp - qm) / (2.0 * eps)
    return j


def _provenance(branch: OperatingBranch) -> dict[str, Any]:
    selector = dict(branch.to_dict().get("selector") or {})
    kind = getattr(branch, "output_coordinate_kind", None) or selector.get(
        "output_coordinate_kind"
    ) or branch.to_dict().get("output_coordinate_kind")
    offset = getattr(branch, "native_output_offset_rad", None)
    if offset is None:
        offset = selector.get("native_output_offset_rad") or branch.to_dict().get(
            "native_output_offset_rad"
        )
    count = getattr(branch, "mounting_application_count", None)
    if count is None:
        count = selector.get("mounting_application_count") or branch.to_dict().get(
            "mounting_application_count"
        )
    return {
        "output_coordinate_kind": kind,
        "native_output_offset_rad": offset,
        "mounting_application_count": count,
    }


def test_scalar_offset_forward_inverse_and_jacobian() -> None:
    from inequality_mechanisms.mechanisms.output_mounting import mount_operating_branch

    native = unit_gearbox_branch(1, input_lower=[-1.0], input_upper=[1.0])
    offset = np.asarray([0.4], dtype=np.float64)
    mounted = mount_operating_branch(native, offset)
    u = np.asarray([0.25], dtype=np.float64)
    q_joint = mounted.forward(u)
    np.testing.assert_allclose(q_joint, native.forward(u) - offset, atol=1e-12)
    np.testing.assert_allclose(mounted.inverse(q_joint), u, atol=1e-12)
    np.testing.assert_allclose(
        mounted.inverse(q_joint), native.inverse(q_joint + offset), atol=1e-12
    )
    np.testing.assert_allclose(mounted.jacobian(u), native.jacobian(u), atol=1e-12)
    np.testing.assert_allclose(
        mounted.jacobian(u), _central_jacobian(mounted, u), atol=1e-8
    )


def test_two_axis_offset_round_trip() -> None:
    from inequality_mechanisms.mechanisms.output_mounting import mount_operating_branch

    native = unit_gearbox_branch(
        2, input_lower=[-1.0, -2.0], input_upper=[1.0, 2.0]
    )
    offset = np.asarray([0.4, -0.25], dtype=np.float64)
    mounted = mount_operating_branch(native, offset)
    u = np.asarray([0.3, -0.8], dtype=np.float64)
    q_joint = mounted.forward(u)
    np.testing.assert_allclose(q_joint, native.forward(u) - offset, atol=1e-12)
    np.testing.assert_allclose(mounted.inverse(q_joint), u, atol=1e-12)
    np.testing.assert_allclose(mounted.jacobian(u), native.jacobian(u), atol=1e-12)
    np.testing.assert_allclose(
        mounted.certificate.input_lower, native.certificate.input_lower, atol=1e-12
    )
    np.testing.assert_allclose(mounted.certificate.input_upper, native.certificate.input_upper, atol=1e-12)
    np.testing.assert_allclose(
        mounted.certificate.output_lower,
        np.asarray(native.certificate.output_lower) - offset,
        atol=1e-12,
    )
    np.testing.assert_allclose(
        mounted.certificate.output_upper,
        np.asarray(native.certificate.output_upper) - offset,
        atol=1e-12,
    )
    np.testing.assert_allclose(
        mounted.certificate.min_abs_gain, native.certificate.min_abs_gain, atol=1e-12
    )
    np.testing.assert_allclose(
        mounted.certificate.monotonic_sign, native.certificate.monotonic_sign, atol=1e-12
    )


def test_zero_offset_is_identity() -> None:
    from inequality_mechanisms.mechanisms.output_mounting import mount_operating_branch

    native = unit_gearbox_branch(
        2, input_lower=[-1.0, -1.0], input_upper=[1.0, 1.0]
    )
    mounted = mount_operating_branch(native, np.zeros(2))
    u = np.asarray([0.2, -0.3], dtype=np.float64)
    np.testing.assert_allclose(mounted.forward(u), native.forward(u), atol=1e-12)
    np.testing.assert_allclose(mounted.inverse(native.forward(u)), u, atol=1e-12)
    np.testing.assert_allclose(mounted.jacobian(u), native.jacobian(u), atol=1e-12)


def test_serialization_round_trip_and_provenance() -> None:
    from inequality_mechanisms.mechanisms.output_mounting import mount_operating_branch

    native = unit_gearbox_branch(
        2, input_lower=[-1.0, -1.0], input_upper=[1.0, 1.0]
    )
    offset = np.asarray([0.15, -0.05], dtype=np.float64)
    mounted = mount_operating_branch(native, offset)
    provenance = _provenance(mounted)
    assert provenance["output_coordinate_kind"] == "mounted_joint"
    np.testing.assert_allclose(provenance["native_output_offset_rad"], offset, atol=1e-12)
    assert int(provenance["mounting_application_count"]) == 1

    restored = OperatingBranch.from_dict(mounted.to_dict())
    u = np.asarray([0.1, 0.2], dtype=np.float64)
    np.testing.assert_allclose(restored.forward(u), mounted.forward(u), atol=1e-12)
    restored_prov = _provenance(restored)
    assert restored_prov["output_coordinate_kind"] == "mounted_joint"
    np.testing.assert_allclose(
        restored_prov["native_output_offset_rad"], offset, atol=1e-12
    )
    assert int(restored_prov["mounting_application_count"]) == 1


def test_double_application_is_detectable() -> None:
    from inequality_mechanisms.mechanisms.output_mounting import mount_operating_branch

    native = unit_gearbox_branch(1, input_lower=[-1.0], input_upper=[1.0])
    offset = np.asarray([0.3], dtype=np.float64)
    once = mount_operating_branch(native, offset)
    try:
        twice = mount_operating_branch(once, offset)
    except ValueError:
        return
    assert int(_provenance(twice)["mounting_application_count"]) == 2
