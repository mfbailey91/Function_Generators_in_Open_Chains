"""V4-231: OMPL-free capability matrix, typed child failures, optional PDST."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from inequality_mechanisms.adapters.ompl._availability import is_ompl_available
from inequality_mechanisms.adapters.ompl.capabilities import (
    FEATURE_IDS,
    FEATURE_SPECS,
    OPTIONAL_FEATURE_IDS,
    REQUIRED_FEATURE_IDS,
    SCHEMA_VERSION,
    STATUS_CHILD_TIMEOUT,
    STATUS_CRASHED,
    STATUS_SUPPORTED,
    STATUS_UNAVAILABLE_DEPENDENCY,
    STATUS_UNSUPPORTED,
    STATUSES,
    FeatureSpec,
    injected_crash_probe,
    injected_hang_probe,
    probe_ompl_capabilities,
    required_rows_complete,
    run_isolated_probe,
)
from inequality_mechanisms.audits.v4_artifact_guard import ArtifactPathForbiddenError

REPO_ROOT = Path(__file__).resolve().parents[2]
PROBE_SCRIPT = REPO_ROOT / "scripts" / "probe_v4_2c_ompl_capabilities.py"


def _script_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = "src"
    return env


def test_capabilities_import_does_not_import_ompl() -> None:
    code = (
        "import sys\n"
        "from inequality_mechanisms.adapters import ompl as ompl_pkg\n"
        "from inequality_mechanisms.adapters.ompl import capabilities\n"
        "assert 'ompl' not in sys.modules\n"
        "assert capabilities.SCHEMA_VERSION\n"
        "assert ompl_pkg.is_ompl_available is not None\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        env=_script_env(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr


def test_missing_ompl_returns_complete_unavailable_matrix() -> None:
    matrix = probe_ompl_capabilities(ompl_available=False)
    assert matrix["schema_version"] == SCHEMA_VERSION
    assert matrix["ompl_available"] is False
    assert matrix["ompl_version"] is None
    assert matrix["catalog"] == list(FEATURE_IDS)
    assert [row["feature_id"] for row in matrix["rows"]] == list(FEATURE_IDS)
    assert {row["status"] for row in matrix["rows"]} == {STATUS_UNAVAILABLE_DEPENDENCY}
    assert required_rows_complete(matrix)
    required = {spec.feature_id for spec in FEATURE_SPECS if spec.required}
    assert required == set(REQUIRED_FEATURE_IDS)
    optional = {spec.feature_id for spec in FEATURE_SPECS if not spec.required}
    assert optional == set(OPTIONAL_FEATURE_IDS)
    assert "planner_pdst" in OPTIONAL_FEATURE_IDS
    assert "sampler_precomputed" in OPTIONAL_FEATURE_IDS
    assert "sampler_deterministic" in OPTIONAL_FEATURE_IDS


def test_isolated_hang_is_child_timeout() -> None:
    payload = run_isolated_probe(injected_hang_probe, timeout_s=0.4)
    assert payload["status"] == STATUS_CHILD_TIMEOUT
    assert payload["elapsed_s"] >= 0.3


def test_isolated_crash_is_typed_failure() -> None:
    payload = run_isolated_probe(injected_crash_probe, timeout_s=5.0)
    assert payload["status"] in {STATUS_CRASHED, "binding_exception"}
    assert "injected probe crash" in payload["detail"]


def test_probe_continues_after_hang_and_crash() -> None:
    seen: list[str] = []

    def runner(spec: FeatureSpec) -> dict[str, str | float | bool]:
        seen.append(spec.feature_id)
        if spec.feature_id == FEATURE_IDS[0]:
            return run_isolated_probe(injected_hang_probe, timeout_s=0.3)
        if spec.feature_id == FEATURE_IDS[1]:
            return run_isolated_probe(injected_crash_probe, timeout_s=5.0)
        return {
            "status": STATUS_UNSUPPORTED,
            "detail": "injected skip",
            "elapsed_s": 0.0,
        }

    matrix = probe_ompl_capabilities(ompl_available=True, probe_runner=runner)
    assert seen == list(FEATURE_IDS)
    by_id = {row["feature_id"]: row for row in matrix["rows"]}
    assert by_id[FEATURE_IDS[0]]["status"] == STATUS_CHILD_TIMEOUT
    assert by_id[FEATURE_IDS[1]]["status"] in {STATUS_CRASHED, "binding_exception"}
    later = [row["status"] for row in matrix["rows"][2:]]
    assert later
    assert all(status == STATUS_UNSUPPORTED for status in later)
    assert required_rows_complete(matrix)


def test_optional_pdst_and_samplers_do_not_block_required_completeness() -> None:
    def runner(spec: FeatureSpec) -> dict[str, str | float | bool]:
        if spec.feature_id in OPTIONAL_FEATURE_IDS:
            return {
                "status": STATUS_UNSUPPORTED,
                "detail": "optional omission",
                "elapsed_s": 0.0,
            }
        return {
            "status": STATUS_SUPPORTED,
            "detail": "required stub",
            "elapsed_s": 0.0,
        }

    matrix = probe_ompl_capabilities(ompl_available=True, probe_runner=runner)
    by_id = {row["feature_id"]: row for row in matrix["rows"]}
    assert by_id["planner_pdst"]["status"] == STATUS_UNSUPPORTED
    assert by_id["sampler_precomputed"]["status"] == STATUS_UNSUPPORTED
    assert by_id["sampler_deterministic"]["status"] == STATUS_UNSUPPORTED
    assert required_rows_complete(matrix)
    assert all(
        by_id[feature_id]["status"] == STATUS_SUPPORTED
        for feature_id in REQUIRED_FEATURE_IDS
    )


def test_probe_script_stdout_and_refuses_arbitrary_output(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, str(PROBE_SCRIPT)],
        cwd=REPO_ROOT,
        env=_script_env(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    matrix = json.loads(proc.stdout)
    assert matrix["catalog"] == list(FEATURE_IDS)
    assert required_rows_complete(matrix)
    forbidden = tmp_path / "elsewhere.json"
    denied = subprocess.run(
        [sys.executable, str(PROBE_SCRIPT), "--output", str(forbidden)],
        cwd=REPO_ROOT,
        env=_script_env(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert denied.returncode == 2
    assert not forbidden.exists()
    assert "not under the allowed root" in denied.stderr
    with pytest.raises(ArtifactPathForbiddenError, match="not under the allowed root"):
        from inequality_mechanisms.audits.v4_artifact_guard import (
            assert_v4_2c_output_allowed,
        )

        assert_v4_2c_output_allowed(forbidden)


@pytest.mark.ompl
@pytest.mark.skipif(
    not is_ompl_available(),
    reason="OMPL Python bindings not installed",
)
def test_ompl_present_records_version_and_required_rows() -> None:
    matrix = probe_ompl_capabilities()
    assert matrix["ompl_available"] is True
    assert matrix["ompl_version"]
    assert required_rows_complete(matrix)
    by_id = {row["feature_id"]: row for row in matrix["rows"]}
    for feature_id in REQUIRED_FEATURE_IDS:
        assert by_id[feature_id]["status"] in STATUSES
        assert by_id[feature_id]["status"] != STATUS_UNAVAILABLE_DEPENDENCY
