"""V4-102 deterministic shared-Q bank."""

from __future__ import annotations

import numpy as np
import pytest

from inequality_mechanisms.audits.v4_artifact_guard import REPO_ROOT
from inequality_mechanisms.experiments.v4.atlas_config import (
    DEFAULT_CONFIG_REL,
    load_atlas_config,
)
from inequality_mechanisms.experiments.v4.controls import build_atlas_arms
from inequality_mechanisms.experiments.v4.shared_q_atlas import (
    SharedQDomainError,
    build_shared_q_bank,
    q_sample_id,
)


def test_shared_q_ids_and_inset_exclude_endpoints() -> None:
    config = load_atlas_config(REPO_ROOT / DEFAULT_CONFIG_REL)
    arms = build_atlas_arms(config)
    cert = arms["fourbar"].branch.certificate
    bank = build_shared_q_bank(
        cert.output_lower,
        cert.output_upper,
        shape=config.grid.shape,
        inset_fraction=config.grid.inset_fraction,
    )
    assert bank.shape == (33, 33)
    assert len(bank.samples) == 1089
    assert bank.samples[0].q_sample_id == "q_0000_0000"
    assert bank.samples[-1].q_sample_id == "q_0032_0032"
    assert q_sample_id(16, 16) == "q_0016_0016"
    q = bank.q_array()
    lo = np.asarray(bank.q_lower)
    hi = np.asarray(bank.q_upper)
    assert np.all(q.min(axis=0) > lo)
    assert np.all(q.max(axis=0) < hi)
    again = build_shared_q_bank(
        cert.output_lower,
        cert.output_upper,
        shape=config.grid.shape,
        inset_fraction=config.grid.inset_fraction,
    )
    np.testing.assert_allclose(again.q_array(), q)
    assert [s.q_sample_id for s in again.samples] == [s.q_sample_id for s in bank.samples]


def test_all_arms_receive_identical_q() -> None:
    config = load_atlas_config(REPO_ROOT / DEFAULT_CONFIG_REL)
    arms = build_atlas_arms(config)
    cert = arms["fourbar"].branch.certificate
    bank = build_shared_q_bank(
        cert.output_lower,
        cert.output_upper,
        shape=(3, 3),
        inset_fraction=config.grid.inset_fraction,
    )
    for sample in bank.samples:
        qs = []
        for arm in arms.values():
            cands = arm.robot.states_from_output(np.asarray(sample.q))
            assert cands
            qs.append(np.asarray(cands[0].state.q, dtype=np.float64))
        np.testing.assert_allclose(qs[0], qs[1])
        np.testing.assert_allclose(qs[0], qs[2])


def test_inset_that_empties_domain_fails() -> None:
    with pytest.raises(SharedQDomainError, match="emptied"):
        build_shared_q_bank([0.0, 0.0], [1.0, 1.0], shape=(3, 3), inset_fraction=0.5)
