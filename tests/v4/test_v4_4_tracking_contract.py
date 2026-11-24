"""V4-405 frozen Cartesian tracking task/integration contract checks."""

from __future__ import annotations

from pathlib import Path

import pytest

from inequality_mechanisms.audits.v4_4_artifact import V4_4ArtifactError, strict_json
from inequality_mechanisms.experiments.v4 import velocity_tracking_contract as contract


def test_frozen_config_matches_default_contract() -> None:
    loaded = contract.load_tracking_contract()
    assert loaded == contract.default_tracking_contract()
    assert loaded["schema_version"] == contract.CONTRACT_SCHEMA
    assert loaded["adr"] == "ADR-034"
    assert loaded["output_dir"] == contract.RESERVED_OUTPUT_REL.as_posix()
    assert loaded["v4_405_forbids_writing_output_dir"] is True


def test_path_bank_and_timing_are_locked() -> None:
    payload = contract.default_tracking_contract()
    assert tuple(payload["paths"]["ids"]) == contract.PATH_IDS
    assert set(payload["paths"]["definitions"]) == set(contract.PATH_IDS)
    assert payload["paths"]["definitions"]["circle_ccw"]["orientation"] == "ccw"
    assert payload["timing"]["dt"] == contract.BASE_DT
    assert tuple(payload["timing"]["refinement_dt"]) == contract.REFINEMENT_DT
    assert payload["timing"]["integrator"] == "explicit_euler_actuator_rate"
    assert payload["control"]["kp"] == contract.FEEDBACK_GAIN
    assert payload["start"]["initial_actuator_rate"] == [0.0, 0.0]


def test_failure_catalog_and_metrics_are_closed() -> None:
    payload = contract.default_tracking_contract()
    assert tuple(payload["failure_codes"]) == contract.FAILURE_CODES
    assert tuple(payload["declared_metrics"]) == contract.DECLARED_METRICS
    assert "task_ineligible" in payload["failure_codes"]
    assert "refinement_diverged" in payload["failure_codes"]


def test_documented_factorial_size() -> None:
    # exact×2 + minimum_norm×2 + damped_least_squares×3×2 = 10
    assert contract.documented_factorial_size() == 10


def test_tampered_contract_is_rejected(tmp_path: Path) -> None:
    payload = contract.default_tracking_contract()
    payload["control"]["kp"] = 6.0
    path = tmp_path / "bad.json"
    path.write_text(strict_json(payload) + "\n", encoding="utf-8")
    with pytest.raises(V4_4ArtifactError, match="frozen|mismatch|gain"):
        contract.load_tracking_contract(path)


def test_validate_rejects_open_write_flag() -> None:
    payload = contract.default_tracking_contract()
    payload["v4_405_forbids_writing_output_dir"] = False
    with pytest.raises(V4_4ArtifactError, match="forbid"):
        contract.validate_tracking_contract(payload)


def test_no_tracking_generator_entrypoint_and_no_result_tree() -> None:
    contract.assert_no_tracking_generator_entrypoint()
    reserved = contract.CANONICAL_REPO_ROOT / contract.RESERVED_OUTPUT_REL
    assert not reserved.exists()
    tracking_roots = list(
        (contract.CANONICAL_REPO_ROOT / "results" / "v4_review").glob(
            "v4_4_velocity_tracking*"
        )
    )
    assert tracking_roots == []
