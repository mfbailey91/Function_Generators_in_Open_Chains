"""V4.2B Phase 1: mounted-Q geometry atlas export contract (V4-223)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from inequality_mechanisms.audits.v4_artifact_guard import (
    CANONICAL_REPO_ROOT,
    V4_0_ALLOWED_OUTPUT_REL,
    V4_1_ALLOWED_OUTPUT_REL,
    V4_2_ALLOWED_OUTPUT_REL,
    V4_2A_ALLOWED_OUTPUT_REL,
)
from inequality_mechanisms.experiments.span_cases import generate_span_cases

EXPECTED_CASES = 17
EXPECTED_GRID = (33, 33)
EXPECTED_ARMS = 3
EXPECTED_ROWS = EXPECTED_CASES * EXPECTED_GRID[0] * EXPECTED_GRID[1] * EXPECTED_ARMS
HISTORICAL_ROOTS = (
    CANONICAL_REPO_ROOT / V4_0_ALLOWED_OUTPUT_REL,
    CANONICAL_REPO_ROOT / V4_1_ALLOWED_OUTPUT_REL,
    CANONICAL_REPO_ROOT / V4_2_ALLOWED_OUTPUT_REL,
    CANONICAL_REPO_ROOT / V4_2A_ALLOWED_OUTPUT_REL,
)


def test_corrective_export_contract_constants() -> None:
    from inequality_mechanisms.experiments.v4.span_controlled_corrective import (
        EXPECTED_GEOMETRY_ROWS,
        GEOMETRY_ARMS,
        GRID_SHAPE,
        N_SPAN_CASES,
    )

    assert N_SPAN_CASES == EXPECTED_CASES
    assert GRID_SHAPE == EXPECTED_GRID
    assert GRID_SHAPE[0] % 2 == 1 and GRID_SHAPE[1] % 2 == 1
    assert GEOMETRY_ARMS == EXPECTED_ARMS
    assert EXPECTED_GEOMETRY_ROWS == EXPECTED_ROWS
    assert EXPECTED_ROWS == 55539
    assert len(generate_span_cases()) == EXPECTED_CASES


def test_corrective_generator_within_case_q_x_and_identity_jg(tmp_path: Path) -> None:
    from inequality_mechanisms.experiments.v4.span_controlled_corrective import (
        generate_span_controlled_corrective_atlas,
    )

    output = tmp_path / "results" / "v4_review" / "v4_2b_span_controlled_corrective_closeout"
    package = generate_span_controlled_corrective_atlas(output=output)
    n_rows = int(package["n_rows"])
    n_typed = int(package.get("n_typed_failures", 0))
    assert n_rows + n_typed == EXPECTED_ROWS
    assert int(package["n_silent_drops"]) == 0
    sample = package["rows"][0]
    np.testing.assert_allclose(sample["q_fourbar"], sample["q_gearbox"], atol=1e-12)
    np.testing.assert_allclose(sample["q_fourbar"], sample["q_identity"], atol=1e-12)
    np.testing.assert_allclose(sample["x_fourbar"], sample["x_gearbox"], atol=1e-12)
    np.testing.assert_allclose(sample["x_fourbar"], sample["x_identity"], atol=1e-12)
    identity_jg = np.asarray(sample["identity_j_g"], dtype=np.float64)
    np.testing.assert_allclose(identity_jg, np.eye(identity_jg.shape[0]), atol=1e-12)
    manifest = json.loads(
        (Path(package["output"]) / "manifest.json").read_text(encoding="utf-8")
    )
    listed = {row["path"] for row in manifest["files"]}
    assert "manifest.json" not in listed
    assert manifest["manifest_inventory_rule"] == "exclude_self"
    assert "files_digest" in manifest
    assert len(manifest["files"]) == EXPECTED_CASES + 5
    for root in HISTORICAL_ROOTS:
        marker = root / ".v4_2b_must_not_write"
        assert not marker.exists()
