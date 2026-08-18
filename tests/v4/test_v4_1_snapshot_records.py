"""V4-103 snapshot-backed atlas rows."""

from __future__ import annotations

import numpy as np

from inequality_mechanisms.audits.v4_artifact_guard import REPO_ROOT
from inequality_mechanisms.experiments.v4.atlas_config import (
    DEFAULT_CONFIG_REL,
    load_atlas_config,
)
from inequality_mechanisms.experiments.v4.controls import build_atlas_arms
from inequality_mechanisms.experiments.v4.geometry_atlas import (
    AtlasRow,
    evaluate_atlas_sample,
)
from inequality_mechanisms.experiments.v4.shared_q_atlas import build_shared_q_bank
from inequality_mechanisms.transmission_geometry import geometry_snapshot


def test_rows_round_trip_and_share_q_x() -> None:
    config = load_atlas_config(REPO_ROOT / DEFAULT_CONFIG_REL)
    arms = build_atlas_arms(config)
    cert = arms["fourbar"].branch.certificate
    bank = build_shared_q_bank(
        cert.output_lower,
        cert.output_upper,
        shape=(3, 3),
        inset_fraction=config.grid.inset_fraction,
    )
    sample = bank.samples[4]
    rows = {
        mech: evaluate_atlas_sample(arm, sample, config=config, revision="test")
        for mech, arm in arms.items()
    }
    for row in rows.values():
        assert row.failure_code is None
        assert row.snapshot is not None
        restored = AtlasRow.from_dict(row.to_dict())
        assert restored.q_sample_id == row.q_sample_id
        np.testing.assert_allclose(restored.snapshot.q, row.snapshot.q)
        np.testing.assert_allclose(restored.snapshot.u, row.snapshot.u)
    q_vals = [np.asarray(row.snapshot.q) for row in rows.values()]
    x_vals = [np.asarray(row.snapshot.x) for row in rows.values()]
    np.testing.assert_allclose(q_vals[0], q_vals[1])
    np.testing.assert_allclose(q_vals[0], q_vals[2])
    np.testing.assert_allclose(x_vals[0], x_vals[1])
    np.testing.assert_allclose(x_vals[0], x_vals[2])
    u_fb = np.asarray(rows["fourbar"].snapshot.u)
    u_gb = np.asarray(rows["span_matched_gearbox"].snapshot.u)
    assert not np.allclose(u_fb, u_gb)
    j_g_fb = np.asarray(rows["fourbar"].snapshot.j_u_to_q)
    j_g_gb = np.asarray(rows["span_matched_gearbox"].snapshot.j_u_to_q)
    assert not np.allclose(j_g_fb, j_g_gb)
    np.testing.assert_allclose(
        rows["identity_on_shared_q"].snapshot.j_u_to_q, np.eye(2)
    )
    fresh = geometry_snapshot(
        arms["fourbar"].robot,
        arms["fourbar"].robot.states_from_output(np.asarray(sample.q))[0].state,
    )
    np.testing.assert_allclose(fresh.j_u_to_q, rows["fourbar"].snapshot.j_u_to_q)
