"""V4.3 authorization follows its active and completed lifecycle states."""

from __future__ import annotations

from inequality_mechanisms.audits.v4_artifact_guard import CANONICAL_REPO_ROOT

PLANNING_ROOT = CANONICAL_REPO_ROOT / "docs" / "software" / "planning"
ACTIVE_SPRINT = PLANNING_ROOT / "ACTIVE_SPRINT.md"
SPRINT_V4_3 = (
    PLANNING_ROOT / "sprints" / "v4" / "SPRINT_V4_3_INTRINSIC_STATIC_WRENCH.md"
)


def test_v4_3_authorization_matches_lifecycle() -> None:
    active = ACTIVE_SPRINT.read_text(encoding="utf-8")
    sprint = SPRINT_V4_3.read_text(encoding="utf-8")
    authorization_lines = [
        line
        for line in active.splitlines()
        if line.startswith("**Code authorization:**")
    ]
    status_lines = [
        line for line in sprint.splitlines() if line.startswith("- **Status:**")
    ]
    assert len(authorization_lines) == 1
    assert len(status_lines) == 1
    authorization = authorization_lines[0]
    status = status_lines[0]

    if status.startswith("- **Status:** active;"):
        assert authorization == "**Code authorization:** V4-300–V4-309 only."
    else:
        assert status.startswith("- **Status:** completed")
        assert "V4-30" not in authorization
        assert "V4.3" not in authorization
