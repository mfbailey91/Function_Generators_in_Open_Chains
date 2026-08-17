"""V4-203/V4-204/V4-205 tiny-grid shared-Q snapshots and identity control."""

from __future__ import annotations

import numpy as np

from inequality_mechanisms.audits.v4_artifact_guard import CANONICAL_REPO_ROOT
from inequality_mechanisms.experiments.span_cases import case_id_for, generate_span_cases
from inequality_mechanisms.experiments.v4.geometry_atlas import AtlasRow
from inequality_mechanisms.experiments.v4.rank_fields import attribution_from_row
from inequality_mechanisms.experiments.v4.span_controlled_atlas import (
    evaluate_span_case,
    load_locked_v3_6d_registry,
)
from inequality_mechanisms.experiments.v4.span_controlled_atlas_config import (
    DEFAULT_CONFIG_REL,
    load_span_atlas_config,
)
from inequality_mechanisms.experiments.span_cases import realize_span_case
from inequality_mechanisms.transmission_geometry import geometry_snapshot
from inequality_mechanisms.transmission_geometry.snapshot import METRIC_STATUS_AVAILABLE


def _case_atlas(case_id: str, *, shape: tuple[int, int] = (3, 3)):
    config = load_span_atlas_config(CANONICAL_REPO_ROOT / DEFAULT_CONFIG_REL)
    registry = load_locked_v3_6d_registry(config)
    case = next(row for row in generate_span_cases() if row.case_id == case_id)
    realized = realize_span_case(case, registry)
    return config, evaluate_span_case(
        realized, config, shape=shape, revision="test"
    )


def test_tiny_grid_shares_q_and_identity_jg() -> None:
    config, atlas = _case_atlas(case_id_for(145.0, 145.0))
    assert atlas.bank.shape == (3, 3)
    assert len(atlas.bank.samples) == 9
    q = atlas.bank.q_array()
    lo = np.asarray(atlas.bank.q_lower)
    hi = np.asarray(atlas.bank.q_upper)
    assert np.all(q.min(axis=0) > lo)
    assert np.all(q.max(axis=0) < hi)
    assert atlas.bank.samples[0].q_sample_id.startswith("span_j1_145_j2_145__")
    again = evaluate_span_case(
        atlas.realized, config, shape=(3, 3), revision="test"
    )
    np.testing.assert_allclose(again.bank.q_array(), q)
    assert [row.q_sample_id for row in again.rows] == [
        row.q_sample_id for row in atlas.rows
    ]
    assert len(atlas.rows) == 27
    for sample in atlas.bank.samples:
        by_mech = {
            row.mechanism_id: row
            for row in atlas.rows
            if row.q_sample_id == sample.q_sample_id
        }
        assert set(by_mech) == {
            "fourbar",
            "span_matched_gearbox",
            "identity_on_shared_q",
        }
        qs = [np.asarray(row.snapshot.q) for row in by_mech.values()]
        xs = [np.asarray(row.snapshot.x) for row in by_mech.values()]
        np.testing.assert_allclose(qs[0], qs[1])
        np.testing.assert_allclose(qs[0], qs[2])
        np.testing.assert_allclose(xs[0], xs[1])
        np.testing.assert_allclose(xs[0], xs[2])
        ident = by_mech["identity_on_shared_q"]
        np.testing.assert_allclose(ident.snapshot.j_u_to_q, np.eye(2), atol=1e-12)
        attr = attribution_from_row(ident)
        assert attr.transmission_full_rank
        assert attr.failure_code is None
        assert attr.metric_status == METRIC_STATUS_AVAILABLE
    center = atlas.bank.samples[4]
    fourbar = next(
        row
        for row in atlas.rows
        if row.q_sample_id == center.q_sample_id and row.mechanism_id == "fourbar"
    )
    restored = AtlasRow.from_dict(fourbar.to_dict())
    np.testing.assert_allclose(restored.snapshot.j_u_to_q, fourbar.snapshot.j_u_to_q)
    fresh = geometry_snapshot(
        atlas.arms["fourbar"].robot,
        atlas.arms["fourbar"].robot.states_from_output(np.asarray(center.q))[0].state,
    )
    np.testing.assert_allclose(fresh.j_u_to_q, fourbar.snapshot.j_u_to_q)
    gearbox = next(
        row
        for row in atlas.rows
        if row.q_sample_id == center.q_sample_id
        and row.mechanism_id == "span_matched_gearbox"
    )
    assert not np.allclose(fourbar.snapshot.u, gearbox.snapshot.u)
    assert fourbar.snapshot.j_u_to_q is not None
    assert gearbox.snapshot.j_u_to_x is not None
    assert fourbar.snapshot.rank_u_to_q.rank >= 1


def test_boundary_stress_case_is_typed_not_dropped() -> None:
    _, atlas = _case_atlas(case_id_for(95.0, 175.0))
    assert atlas.realized.j2.status == "boundary_stress_only"
    assert len(atlas.rows) == 27
    assert all(row.failure_code is None for row in atlas.rows)
    ident = next(
        row for row in atlas.rows if row.mechanism_id == "identity_on_shared_q"
    )
    np.testing.assert_allclose(ident.snapshot.j_u_to_q, np.eye(2), atol=1e-12)
    attr = attribution_from_row(ident)
    assert attr.transmission_full_rank
