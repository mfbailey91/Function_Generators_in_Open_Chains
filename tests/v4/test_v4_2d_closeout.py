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

ACTIVE_SPRINT = (
    CANONICAL_REPO_ROOT / "docs" / "software" / "planning" / "ACTIVE_SPRINT.md"
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
SPRINT_V4_3 = (
    CANONICAL_REPO_ROOT
    / "docs"
    / "software"
    / "planning"
    / "sprints"
    / "v4"
    / "SPRINT_V4_3_INTRINSIC_STATIC_WRENCH.md"
)


def test_v4_2d_closeout_resets_authorization() -> None:
    text = ACTIVE_SPRINT.read_text(encoding="utf-8")
    assert "**Code authorization:** none." in text
    assert "Sprint V4.2D is **completed**" in text
    assert "Sprint V4.3 remains **drafted / blocked**" in text
    assert "Do not implement V4.3 / V4-300+" in text
    sprint_d = SPRINT_V4_2D.read_text(encoding="utf-8")
    assert "**Status:** completed; canonical evidence retained" in sprint_d
    sprint = SPRINT_V4_3.read_text(encoding="utf-8")
    assert "drafted / blocked" in sprint


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
