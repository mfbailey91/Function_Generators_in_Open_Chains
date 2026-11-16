"""V4-249 closeout: authorization reset and retained V4.2D package."""

from __future__ import annotations

import json

from inequality_mechanisms.analysis.v4.optimality_reference import (
    FROZEN_STAGE_C_ROWS,
    FROZEN_V4_2C_FILES_DIGEST,
    PRIMARY_REFERENCE_COUNT,
)
from inequality_mechanisms.audits.v4_artifact_guard import (
    CANONICAL_REPO_ROOT,
    canonical_v4_2d_retained_root,
)
from inequality_mechanisms.experiments.v4.ompl_planner_portfolio_config import (
    FROZEN_V4_2B_FILES_DIGEST,
)

CLOSEOUT_V4_2D = (
    CANONICAL_REPO_ROOT
    / "docs"
    / "software"
    / "architecture"
    / "notes"
    / "V4_2D_OPTIMALITY_REFERENCE_CLOSEOUT.md"
)
SPRINT_V4_2D = (
    CANONICAL_REPO_ROOT
    / "docs"
    / "software"
    / "planning"
    / "sprints"
    / "v4"
    / "SPRINT_V4_2D_OPTIMALITY_REFERENCE_AND_GEARBOX_CONTROL_REPORT.md"
)


def test_v4_2d_closeout_did_not_auto_activate_v4_3() -> None:
    text = " ".join(CLOSEOUT_V4_2D.read_text(encoding="utf-8").split())
    assert "**Code authorization: none.**" in text
    assert "or activate V4.3." in text
    assert "Sprint V4.3 remains drafted / blocked." in text
    sprint_d = SPRINT_V4_2D.read_text(encoding="utf-8")
    assert "**Status:** completed; canonical evidence retained" in sprint_d


def test_v4_2d_retained_package_matches_closeout_counts() -> None:
    root = canonical_v4_2d_retained_root()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["package"] == "v4_2d_optimality_reference_report"
    assert int(manifest["n_reference_rows"]) == PRIMARY_REFERENCE_COUNT
    assert int(manifest["n_stage_c_rows"]) == FROZEN_STAGE_C_ROWS
    assert int(manifest["n_orphans"]) == 0
    assert manifest["v4_2b_files_digest"] == FROZEN_V4_2B_FILES_DIGEST
    assert manifest["v4_2c_files_digest"] == FROZEN_V4_2C_FILES_DIGEST
    assert (root / "index.html").is_file()
    figures = root / "figures"
    assert len(list(figures.glob("*.png"))) == 12


def test_v4_2d_source_manifests_unchanged() -> None:
    v4_2b = json.loads(
        (
            CANONICAL_REPO_ROOT
            / "results"
            / "v4_review"
            / "v4_2b_span_controlled_corrective_closeout"
            / "manifest.json"
        ).read_text(encoding="utf-8")
    )
    v4_2c = json.loads(
        (
            CANONICAL_REPO_ROOT
            / "results"
            / "v4_review"
            / "v4_2c_ompl_planner_portfolio"
            / "manifest.json"
        ).read_text(encoding="utf-8")
    )
    assert v4_2b["files_digest"] == FROZEN_V4_2B_FILES_DIGEST
    assert v4_2c["files_digest"] == FROZEN_V4_2C_FILES_DIGEST
