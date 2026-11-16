"""V4-309: closeout note and authorization reset consistency."""

from __future__ import annotations

import json
from pathlib import Path

from inequality_mechanisms.audits.v4_3_artifact import verify_v4_3_artifact
from inequality_mechanisms.audits.v4_artifact_guard import (
    CANONICAL_REPO_ROOT,
    canonical_v4_3_retained_root,
)

CLOSEOUT = (
    CANONICAL_REPO_ROOT
    / "docs"
    / "software"
    / "architecture"
    / "notes"
    / "V4_3_INTRINSIC_STATIC_WRENCH_CLOSEOUT.md"
)
ACTIVE_SPRINT = (
    CANONICAL_REPO_ROOT / "docs" / "software" / "planning" / "ACTIVE_SPRINT.md"
)


def test_closeout_records_verified_package_identities() -> None:
    text = CLOSEOUT.read_text(encoding="utf-8")
    assert "**Code authorization: none.**" in text or "Code authorization: none" in text
    assert "d275b4f2" in text
    assert "f4807260" in text
    assert "a7abec714721afa2e4f6551990e3532e5ad9a6234f72f93b2480344fcc5d4218" in text
    assert "55539" in text
    assert "v4_3_intrinsic_static_wrench" in text
    assert "ADR-028" in text


def test_active_sprint_has_no_code_authorization() -> None:
    active = ACTIVE_SPRINT.read_text(encoding="utf-8")
    auth = next(
        line
        for line in active.splitlines()
        if line.startswith("**Code authorization:**")
    )
    assert auth.startswith("**Code authorization:** none")
    assert "V4-300" not in auth
    assert "Sprint V4.3 is **completed**" in active
    assert "v4_3_intrinsic_static_wrench" in active


def test_retained_package_still_verifies() -> None:
    root = canonical_v4_3_retained_root()
    summary = verify_v4_3_artifact(root)
    assert summary["n_rows"] == 55539
    assert summary["n_cases"] == 17
    assert summary["files_digest"] == (
        "a7abec714721afa2e4f6551990e3532e5ad9a6234f72f93b2480344fcc5d4218"
    )
    manifest = json.loads((Path(root) / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["n_silent_drops"] == 0
    assert manifest["n_typed_failures"] == 0
