"""V4.2B Phase 1/8: corrective package root, freeze, and manifest integrity."""

from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from inequality_mechanisms.audits.v4_2b_artifact import (
    MANIFEST_INVENTORY_RULE,
    V4_2BArtifactError,
    files_digest,
    inventory_required_files,
    verify_v4_2b_artifact,
)
from inequality_mechanisms.audits.v4_artifact_guard import (
    CANONICAL_REPO_ROOT,
    FROZEN_V3_REVIEW_PACKAGES,
    REPO_ROOT,
    V4_0_ALLOWED_PACKAGE,
    V4_1_ALLOWED_PACKAGE,
    V4_2_ALLOWED_PACKAGE,
    V4_2A_ALLOWED_PACKAGE,
    ArtifactPathForbiddenError,
    canonical_v4_0_retained_root,
    canonical_v4_1_retained_root,
    canonical_v4_2_retained_root,
    canonical_v4_2a_retained_root,
    v4_2_git_tracked_package_digest,
    v4_2a_git_tracked_package_digest,
)
from inequality_mechanisms.experiments.v4.geometry_atlas import ATLAS_ROW_SCHEMA_VERSION
from inequality_mechanisms.experiments.v4.span_controlled_corrective_config import (
    SCHEMA_VERSION,
)

V4_2B_PACKAGE = "v4_2b_span_controlled_corrective_closeout"
V4_2B_OUTPUT_REL = Path("results") / "v4_review" / V4_2B_PACKAGE
VERIFY_SCRIPT = CANONICAL_REPO_ROOT / "scripts" / "verify_v4_2b_artifact.py"


def test_v4_2b_allowed_root_and_nested_paths() -> None:
    from inequality_mechanisms.audits.v4_artifact_guard import (
        V4_2B_ALLOWED_OUTPUT_REL,
        assert_v4_2b_output_allowed,
    )

    root = (REPO_ROOT / V4_2B_ALLOWED_OUTPUT_REL).resolve()
    assert V4_2B_ALLOWED_OUTPUT_REL == V4_2B_OUTPUT_REL
    assert assert_v4_2b_output_allowed(root) == root
    child = root / "geometry_atlas" / "cases" / "span_j1_145_j2_145" / "index.html"
    assert assert_v4_2b_output_allowed(child) == child.resolve()


@pytest.mark.parametrize(
    "path_fn, match",
    [
        (canonical_v4_0_retained_root, "frozen V4.0"),
        (canonical_v4_1_retained_root, "frozen V4.1"),
        (canonical_v4_2_retained_root, "frozen V4.2"),
        (canonical_v4_2a_retained_root, "frozen V4.2A"),
    ],
)
def test_v4_2b_refuses_historical_v4_packages(path_fn, match: str) -> None:
    from inequality_mechanisms.audits.v4_artifact_guard import assert_v4_2b_output_allowed

    path = path_fn()
    with pytest.raises(ArtifactPathForbiddenError, match=match):
        assert_v4_2b_output_allowed(path)
    with pytest.raises(ArtifactPathForbiddenError, match=match):
        assert_v4_2b_output_allowed(path / "manifest.json")


@pytest.mark.parametrize("package", sorted(FROZEN_V3_REVIEW_PACKAGES))
def test_v4_2b_refuses_frozen_v3(package: str) -> None:
    from inequality_mechanisms.audits.v4_artifact_guard import assert_v4_2b_output_allowed

    path = (REPO_ROOT / "results" / "v3_review" / package).resolve()
    with pytest.raises(ArtifactPathForbiddenError, match="frozen V3"):
        assert_v4_2b_output_allowed(path)


def test_tmp_v4_2b_prepare_leaves_historical_git_tracked_digests_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from inequality_mechanisms.audits import v4_artifact_guard
    from inequality_mechanisms.audits.v4_artifact_guard import prepare_v4_2b_output_dir

    sha_2, n_2 = v4_2_git_tracked_package_digest()
    sha_2a, n_2a = v4_2a_git_tracked_package_digest()
    monkeypatch.setattr(v4_artifact_guard, "REPO_ROOT", tmp_path)
    output = tmp_path / "results" / "v4_review" / V4_2B_PACKAGE
    prepared = prepare_v4_2b_output_dir(output)
    (prepared / "placeholder.txt").write_text("tmp", encoding="utf-8")
    sha_2_after, n_2_after = v4_2_git_tracked_package_digest()
    sha_2a_after, n_2a_after = v4_2a_git_tracked_package_digest()
    assert (sha_2_after, n_2_after) == (sha_2, n_2)
    assert (sha_2a_after, n_2a_after) == (sha_2a, n_2a)
    assert V4_0_ALLOWED_PACKAGE != V4_2B_PACKAGE
    assert V4_1_ALLOWED_PACKAGE != V4_2B_PACKAGE
    assert V4_2_ALLOWED_PACKAGE != V4_2B_PACKAGE
    assert V4_2A_ALLOWED_PACKAGE != V4_2B_PACKAGE


def test_v4_2b_refuses_sibling_v4_packages() -> None:
    from inequality_mechanisms.audits.v4_artifact_guard import assert_v4_2b_output_allowed

    path = (REPO_ROOT / "results" / "v4_review" / "v4_3_intrinsic_static_wrench").resolve()
    with pytest.raises(ArtifactPathForbiddenError, match="unauthorized V4 package"):
        assert_v4_2b_output_allowed(path)


def test_v4_2b_refuses_arbitrary_path(tmp_path: Path) -> None:
    from inequality_mechanisms.audits.v4_artifact_guard import assert_v4_2b_output_allowed

    with pytest.raises(ArtifactPathForbiddenError, match="not under the allowed root"):
        assert_v4_2b_output_allowed(tmp_path / "elsewhere")


def test_v4_2b_verifier_script_exists_and_loads() -> None:
    assert VERIFY_SCRIPT.is_file()
    spec = importlib.util.spec_from_file_location("verify_v4_2b_artifact", VERIFY_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert callable(getattr(module, "verify_v4_2b_artifact"))


_MINI_CASE_ID = "span_j1_145_j2_145"
_MINI_ROW_COUNT = 3


def _mini_rows(n: int = _MINI_ROW_COUNT) -> list[dict[str, str]]:
    return [
        {
            "schema_version": ATLAS_ROW_SCHEMA_VERSION,
            "q_sample_id": f"q_{index}",
            "mechanism_id": "fourbar",
        }
        for index in range(n)
    ]


def _write_mini_package(root: Path, *, n_rows: int = _MINI_ROW_COUNT) -> Path:
    """Write a tiny valid V4.2B package (not the 55,539-row atlas)."""
    gz = root / "geometry_atlas" / "cases" / _MINI_CASE_ID / "geometry_samples.jsonl.gz"
    gz.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(gz, "wt", encoding="utf-8") as handle:
        for row in _mini_rows(n_rows):
            handle.write(json.dumps(row) + "\n")
    (root / "cases.json").write_text(
        json.dumps([{"case_id": _MINI_CASE_ID}]), encoding="utf-8"
    )
    (root / "resolved_config.json").write_text(
        json.dumps({"n_cases": 1}), encoding="utf-8"
    )
    (root / "rank_fields.json").write_text("[]", encoding="utf-8")
    (root / "README.md").write_text("# mini V4.2B package\n", encoding="utf-8")
    (root / "index.html").write_text("<html></html>", encoding="utf-8")
    files = inventory_required_files(root, [_MINI_CASE_ID])
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "package": V4_2B_PACKAGE,
        "manifest_inventory_rule": MANIFEST_INVENTORY_RULE,
        "case_ids": [_MINI_CASE_ID],
        "n_rows": n_rows,
        "n_typed_failures": 0,
        "source_git_revision": "a" * 40,
        "source_git_dirty": False,
        "files": files,
        "files_digest": files_digest(files),
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return root


def _manifest(root: Path) -> dict:
    return json.loads((root / "manifest.json").read_text(encoding="utf-8"))


def _write_manifest(root: Path, payload: dict) -> None:
    (root / "manifest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _geometry_rel() -> str:
    return f"geometry_atlas/cases/{_MINI_CASE_ID}/geometry_samples.jsonl.gz"


def test_valid_mini_package_passes(tmp_path: Path) -> None:
    root = _write_mini_package(tmp_path / "pkg")
    summary = verify_v4_2b_artifact(root)
    assert summary["n_geometry_rows"] == _MINI_ROW_COUNT
    assert summary["n_files"] == 6
    assert "manifest.json" not in {
        row["path"] for row in _manifest(root)["files"]
    }


def test_missing_listed_file_fails(tmp_path: Path) -> None:
    root = _write_mini_package(tmp_path / "pkg")
    (root / "README.md").unlink()
    with pytest.raises(V4_2BArtifactError, match="missing listed file"):
        verify_v4_2b_artifact(root)


def test_mutated_bytes_fail_hash(tmp_path: Path) -> None:
    root = _write_mini_package(tmp_path / "pkg")
    readme = root / "README.md"
    payload = bytearray(readme.read_bytes())
    payload[0] ^= 0xFF
    readme.write_bytes(bytes(payload))
    with pytest.raises(V4_2BArtifactError, match="sha256 mismatch"):
        verify_v4_2b_artifact(root)


def test_mutated_bytes_fail_byte_count(tmp_path: Path) -> None:
    root = _write_mini_package(tmp_path / "pkg")
    readme = root / "README.md"
    readme.write_bytes(readme.read_bytes() + b"\nextra")
    manifest = _manifest(root)
    new_bytes = readme.read_bytes()
    for record in manifest["files"]:
        if record["path"] == "README.md":
            record["sha256"] = hashlib.sha256(new_bytes).hexdigest()
    _write_manifest(root, manifest)
    with pytest.raises(V4_2BArtifactError, match="byte_count mismatch"):
        verify_v4_2b_artifact(root)


def test_truncated_gzip_fails(tmp_path: Path) -> None:
    root = _write_mini_package(tmp_path / "pkg")
    gz = root / _geometry_rel()
    payload = gz.read_bytes()
    assert len(payload) > 8
    truncated = payload[:-8]
    gz.write_bytes(truncated)
    manifest = _manifest(root)
    for record in manifest["files"]:
        if record["path"] == _geometry_rel():
            record["sha256"] = hashlib.sha256(truncated).hexdigest()
            record["byte_count"] = len(truncated)
    _write_manifest(root, manifest)
    with pytest.raises(V4_2BArtifactError, match="decompression failure"):
        verify_v4_2b_artifact(root)


def test_wrong_row_count_fails(tmp_path: Path) -> None:
    root = _write_mini_package(tmp_path / "pkg")
    manifest = _manifest(root)
    for record in manifest["files"]:
        if record["path"] == _geometry_rel():
            record["row_count"] = int(record["row_count"]) + 1
    _write_manifest(root, manifest)
    with pytest.raises(V4_2BArtifactError, match="row_count mismatch"):
        verify_v4_2b_artifact(root)


def test_recoverable_jsonl_row_count_matches_table(tmp_path: Path) -> None:
    root = _write_mini_package(tmp_path / "pkg")
    summary = verify_v4_2b_artifact(root)
    jsonl = next(
        row for row in _manifest(root)["files"] if str(row["path"]).endswith(".jsonl.gz")
    )
    assert jsonl["row_count"] == _MINI_ROW_COUNT
    assert jsonl["row_count"] == summary["n_geometry_rows"]
    assert jsonl["compression"] == "gzip"


def test_required_file_omission_fails(tmp_path: Path) -> None:
    root = _write_mini_package(tmp_path / "pkg")
    manifest = _manifest(root)
    manifest["files"] = [
        row for row in manifest["files"] if row["path"] != "index.html"
    ]
    manifest["files_digest"] = files_digest(manifest["files"])
    _write_manifest(root, manifest)
    with pytest.raises(V4_2BArtifactError, match="required-file omission"):
        verify_v4_2b_artifact(root)


def test_source_git_dirty_true_fails(tmp_path: Path) -> None:
    root = _write_mini_package(tmp_path / "pkg")
    manifest = _manifest(root)
    manifest["source_git_dirty"] = True
    _write_manifest(root, manifest)
    with pytest.raises(V4_2BArtifactError, match="source_git_dirty must be false"):
        verify_v4_2b_artifact(root)


def test_malformed_source_git_revision_fails(tmp_path: Path) -> None:
    root = _write_mini_package(tmp_path / "pkg")
    manifest = _manifest(root)
    manifest["source_git_revision"] = "not-a-sha"
    _write_manifest(root, manifest)
    with pytest.raises(V4_2BArtifactError, match="40-char hex SHA"):
        verify_v4_2b_artifact(root)
