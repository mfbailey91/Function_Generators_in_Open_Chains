"""V4.2B closeout contracts (V4-228). Canonical evidence may still be absent."""

from __future__ import annotations

import gzip
import json
from dataclasses import fields
from pathlib import Path

import pytest

from inequality_mechanisms.audits.v4_2b_artifact import (
    REQUIRED_MANIFEST_KEYS,
    SHA256_RE,
    SOURCE_GIT_REVISION_RE,
    expected_case_ids,
    frozen_common_task_bank_digest,
    verify_v4_2b_artifact,
)
from inequality_mechanisms.audits.v4_artifact_guard import (
    CANONICAL_REPO_ROOT,
    REPO_ROOT,
    ArtifactPathForbiddenError,
    assert_v4_2b_output_allowed,
    canonical_v4_2b_retained_root,
)
from inequality_mechanisms.experiments.span_cases import generate_span_cases
from inequality_mechanisms.experiments.v4 import (
    span_controlled_corrective_audit_config as audit_cfg,
)
from inequality_mechanisms.experiments.v4.span_controlled_atlas_config import (
    FROZEN_V3_6D_DIGEST,
)
from inequality_mechanisms.experiments.v4.span_controlled_corrective import (
    EXPECTED_GEOMETRY_ROWS,
    GEOMETRY_ARMS,
    GRID_SHAPE,
    N_SPAN_CASES,
)
from inequality_mechanisms.graphs.paired_edge_admission import PairedCompiledSearchGraph

FROZEN_BANK_DIGEST = audit_cfg.FROZEN_BANK_DIGEST

ACTIVE_SPRINT = (
    CANONICAL_REPO_ROOT / "docs" / "software" / "planning" / "ACTIVE_SPRINT.md"
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
V4_3_OUTPUT = REPO_ROOT / "results" / "v4_review" / "v4_3_intrinsic_static_wrench"
SRC_ROOT = CANONICAL_REPO_ROOT / "src" / "inequality_mechanisms"
CASE_ID = "span_j1_145_j2_145"


def _canonical_manifest() -> Path:
    return canonical_v4_2b_retained_root() / "manifest.json"


def _require_canonical_package() -> Path:
    manifest = _canonical_manifest()
    if not manifest.is_file():
        pytest.skip("canonical V4.2B package is not generated")
    return canonical_v4_2b_retained_root()


def test_exact_case_set_is_the_frozen_seventeen() -> None:
    cases = generate_span_cases()
    ids = expected_case_ids()
    assert len(cases) == 17
    assert len(ids) == 17
    assert ids == tuple(case.case_id for case in cases)
    assert CASE_ID in ids


def test_expected_geometry_row_total_is_frozen() -> None:
    assert N_SPAN_CASES == 17
    assert GRID_SHAPE == (33, 33)
    assert GEOMETRY_ARMS == 3
    assert EXPECTED_GEOMETRY_ROWS == 17 * 33 * 33 * 3
    assert EXPECTED_GEOMETRY_ROWS == 55539


def test_silent_drops_are_fail_closed_in_the_manifest_contract() -> None:
    keys = REQUIRED_MANIFEST_KEYS
    assert "n_silent_drops" in keys
    assert keys.index("n_silent_drops") > keys.index("n_typed_failures")


def test_one_final_topology_digest_is_shared_by_the_pair() -> None:
    from inequality_mechanisms.experiments.span_cases import realize_mounted_span_case
    from inequality_mechanisms.experiments.v4.span_controlled_atlas import (
        load_locked_v3_6d_registry,
    )
    from inequality_mechanisms.experiments.v4.span_controlled_atlas_config import (
        DEFAULT_CONFIG_REL,
        load_span_atlas_config,
    )
    from inequality_mechanisms.experiments.v4.span_controlled_corrective_audit import (
        compile_mounted_paired_search,
        sampling_arms_for_mounted,
    )

    names = {item.name for item in fields(PairedCompiledSearchGraph)}
    assert "admitted_topology_digest" in names
    assert "admitted_topology_digests" not in names
    config = load_span_atlas_config(CANONICAL_REPO_ROOT / DEFAULT_CONFIG_REL)
    registry = load_locked_v3_6d_registry(config)
    case = next(item for item in generate_span_cases() if item.case_id == CASE_ID)
    realized = realize_mounted_span_case(case, registry)
    arms = sampling_arms_for_mounted(realized, L1=1.0, L2=1.0)
    _paired, compiled = compile_mounted_paired_search(
        realized,
        lattice_shape=(3, 3),
        inset_fraction=0.01,
        edge_n_samples=8,
        sampling_arms=arms,
    )
    digest = compiled.admitted_topology_digest
    assert SHA256_RE.fullmatch(digest) is not None
    assert set(compiled.edge_costs) == {"fourbar", "gearbox"}
    for edge in compiled.admitted_edge_ids:
        compiled.edge_costs["fourbar"](*edge)
        compiled.edge_costs["gearbox"](*edge)


def test_task_bank_digest_matches_frozen_lock() -> None:
    assert frozen_common_task_bank_digest() == FROZEN_BANK_DIGEST
    assert FROZEN_BANK_DIGEST == (
        "1416240cdf71bcba44a1962ed7510430608b5bd8f4d9923a4dbc118a4735d487"
    )


def test_required_manifest_fields_are_exact() -> None:
    assert REQUIRED_MANIFEST_KEYS == (
        "schema_version",
        "package",
        "manifest_inventory_rule",
        "source_git_revision",
        "source_git_dirty",
        "config_digest",
        "v3_6d_registry_digest",
        "common_task_bank_digest",
        "case_ids",
        "n_rows",
        "n_typed_failures",
        "n_silent_drops",
        "files",
        "files_digest",
    )


@pytest.mark.parametrize(
    ("value", "ok"),
    [
        ("a" * 40, True),
        ("0123456789abcdef" * 2 + "abcdabcd", True),
        ("A" * 40, False),
        ("abc", False),
        ("", False),
        ("g" * 40, False),
        ("a" * 39, False),
        ("a" * 41, False),
    ],
)
def test_source_git_revision_format(value: str, ok: bool) -> None:
    matched = SOURCE_GIT_REVISION_RE.fullmatch(value) is not None
    assert matched is ok


def test_historical_package_digests_unchanged() -> None:
    from tests.v4 import test_v4_2b_phase0_freeze as freeze

    freeze.test_v3_6d_registry_digest_is_frozen()
    freeze.test_frozen_v3_review_digests_remain_unchanged()
    freeze.test_v4_0_and_v4_1_git_tracked_digest_locks_match()
    freeze.test_v4_2_git_tracked_digest_lock_matches_committed_package()
    freeze.test_v4_2a_git_tracked_digest_lock_matches_committed_package()


def test_v4_3_remains_blocked() -> None:
    text = ACTIVE_SPRINT.read_text(encoding="utf-8")
    assert "V4-220" in text and "V4-229" in text
    assert "V4-300" not in text
    assert "Do not implement V4.3" in text
    with pytest.raises(ArtifactPathForbiddenError, match="unauthorized V4 package"):
        assert_v4_2b_output_allowed(V4_3_OUTPUT)
    hits = [
        path
        for path in SRC_ROOT.rglob("*")
        if "v4_3" in path.name and " 2" not in path.name
    ]
    assert hits == []
    sprint = SPRINT_V4_3.read_text(encoding="utf-8")
    assert "drafted / blocked" in sprint
    assert "V4.2B" in sprint
    assert "V4.2/V4.2A" in sprint or "historical V4.2/V4.2A" in sprint


def test_canonical_package_closeout_when_present() -> None:
    root = _require_canonical_package()
    summary = verify_v4_2b_artifact(root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    n_rows = int(manifest["n_rows"])
    n_typed = int(manifest["n_typed_failures"])
    n_silent = int(manifest["n_silent_drops"])
    assert n_silent == 0
    assert n_rows + n_typed == EXPECTED_GEOMETRY_ROWS
    assert summary["n_geometry_rows"] == EXPECTED_GEOMETRY_ROWS
    assert manifest["common_task_bank_digest"] == FROZEN_BANK_DIGEST
    assert manifest["v3_6d_registry_digest"] == FROZEN_V3_6D_DIGEST
    assert manifest["source_git_dirty"] is False
    assert SOURCE_GIT_REVISION_RE.fullmatch(str(manifest["source_git_revision"]))
    topology = root / "planning_audit" / "data" / "topology.jsonl.gz"
    assert topology.is_file()
    rows: list[dict[str, object]] = []
    with gzip.open(topology, "rt", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            assert isinstance(payload, dict)
            rows.append(payload)
    expected = expected_case_ids()
    assert tuple(row["case_id"] for row in rows) == expected
    for row in rows:
        digest = row["admitted_topology_digest"]
        assert isinstance(digest, str)
        assert SHA256_RE.fullmatch(digest) is not None
        assert "admitted_topology_digests" not in row
