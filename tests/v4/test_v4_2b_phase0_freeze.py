"""V4.2B Phase 0: freeze historical package digests before corrective code."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from inequality_mechanisms.audits.v4_artifact_guard import (
    CANONICAL_REPO_ROOT,
    V4_0_ALLOWED_PACKAGE,
    V4_1_ALLOWED_PACKAGE,
    V4_2_ALLOWED_PACKAGE,
    V4_2A_ALLOWED_PACKAGE,
    v4_0_smoke_package_digest,
    v4_1_atlas_package_digest,
    v4_2_git_tracked_package_digest,
    v4_2a_git_tracked_package_digest,
)
from inequality_mechanisms.experiments.v4.span_controlled_atlas_config import (
    FROZEN_V3_6D_DIGEST,
    FROZEN_V3_6D_REGISTRY_REL,
)
from inequality_mechanisms.mechanisms.span_registry import load_span_registry
from tests.v4.test_v4_009_closeout import test_frozen_v3_review_digests_are_unchanged

DATA = Path(__file__).resolve().parent / "data"
DIGEST_V4_0 = DATA / "frozen_v4_0_smoke_digests.json"
DIGEST_V4_1 = DATA / "frozen_v4_1_atlas_digests.json"
DIGEST_V4_2 = DATA / "frozen_v4_2_atlas_digests.json"
DIGEST_V4_2A = DATA / "frozen_v4_2a_audit_digests.json"


def _assert_lock(
    path: Path,
    *,
    schema_version: str,
    package: str,
    digest_fn: Callable[[], tuple[str, int]],
    digest_kind: str | None = None,
) -> None:
    lock = json.loads(path.read_text(encoding="utf-8"))
    assert lock["schema_version"] == schema_version
    assert lock["package"] == package
    if digest_kind is not None:
        assert lock["digest_kind"] == digest_kind
    sha, n_files = digest_fn()
    assert n_files == lock["n_files"], path.name
    assert sha == lock["sha256"], path.name


def test_v3_6d_registry_digest_is_frozen() -> None:
    payload = json.loads(
        (CANONICAL_REPO_ROOT / FROZEN_V3_6D_REGISTRY_REL).read_text(encoding="utf-8")
    )
    registry = load_span_registry(payload)
    assert payload["sha256"] == FROZEN_V3_6D_DIGEST
    assert registry.sha256 == FROZEN_V3_6D_DIGEST


def test_frozen_v3_review_digests_remain_unchanged() -> None:
    test_frozen_v3_review_digests_are_unchanged()


def test_v4_0_and_v4_1_git_tracked_digest_locks_match() -> None:
    _assert_lock(
        DIGEST_V4_0,
        schema_version="v4.0.frozen_v4_0_smoke_digests.v1",
        package=V4_0_ALLOWED_PACKAGE,
        digest_fn=v4_0_smoke_package_digest,
    )
    _assert_lock(
        DIGEST_V4_1,
        schema_version="v4.1.frozen_v4_1_atlas_digests.v1",
        package=V4_1_ALLOWED_PACKAGE,
        digest_fn=v4_1_atlas_package_digest,
    )


def test_v4_2_git_tracked_digest_lock_matches_committed_package() -> None:
    _assert_lock(
        DIGEST_V4_2,
        schema_version="v4.2b.frozen_v4_2_git_tracked_digests.v1",
        package=V4_2_ALLOWED_PACKAGE,
        digest_fn=v4_2_git_tracked_package_digest,
        digest_kind="git_tracked",
    )


def test_v4_2a_git_tracked_digest_lock_matches_committed_package() -> None:
    _assert_lock(
        DIGEST_V4_2A,
        schema_version="v4.2b.frozen_v4_2a_git_tracked_digests.v1",
        package=V4_2A_ALLOWED_PACKAGE,
        digest_fn=v4_2a_git_tracked_package_digest,
        digest_kind="git_tracked",
    )
