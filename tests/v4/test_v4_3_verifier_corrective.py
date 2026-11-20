"""Corrective verifier: positive full-corpus path and adversarial transport."""

from __future__ import annotations

import copy
import gzip
import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from inequality_mechanisms.audits import v4_3_artifact as artifact
from inequality_mechanisms.audits.v4_artifact_guard import canonical_v4_3_retained_root
from inequality_mechanisms.experiments.v4.intrinsic_static_wrench import (
    consume_v4_2b_corpus,
    evaluate_restored_row,
    iter_retained_atlas_rows,
)
from inequality_mechanisms.experiments.v4.intrinsic_static_wrench_config import (
    MANIFEST_SCHEMA_VERSION,
    PACKAGE_SCHEMA_VERSION,
    load_intrinsic_static_wrench_config,
)
from inequality_mechanisms.experiments.v4.intrinsic_static_wrench_fields import (
    INHERITED_TOLERANCE_POLICY,
    paired_comparison_summary,
    retained_force_record,
)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(artifact.strict_json_dumps(value) + "\n", encoding="utf-8")


def _write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        for row in rows:
            stream.write(artifact.strict_json_dumps(row, indent=None) + "\n")


@pytest.fixture(scope="module")
def valid_row() -> dict[str, Any]:
    identity, source = next(iter_retained_atlas_rows("span_j1_095_j2_095"))
    return artifact.to_strict_jsonable(
        retained_force_record(evaluate_restored_row(identity, source))
    )


def test_complete_scientific_row_passes(valid_row: dict[str, Any]) -> None:
    artifact._validate_row(valid_row)


@pytest.mark.parametrize("key", ["hrep_a", "direction_vectors", "rank_reports"])
def test_missing_science_is_rejected(valid_row: dict[str, Any], key: str) -> None:
    row = copy.deepcopy(valid_row)
    del row[key]
    with pytest.raises(artifact.V4_3ArtifactError, match="missing scientific"):
        artifact._validate_row(row)


@pytest.mark.parametrize(
    "mutation,match",
    [
        (
            lambda r: r.update(source_failure_code="source_parse_failure"),
            "typed source",
        ),
        (lambda r: r.update(primary_eligible=False), "eligibility"),
        (lambda r: r.update(vertices=[]), "shape"),
        (lambda r: r.update(hrep_b=[2.0] * 4), "bounds"),
        (lambda r: r.update(grid_index=[True, 0]), "grid_index"),
        (
            lambda r: r["directional_fields"]["radial"].update(value=None),
            "finite number",
        ),
        (lambda r: r.update(isotropic_radius=999.0), "transport"),
    ],
)
def test_invalid_science_is_rejected(valid_row, mutation, match):
    row = copy.deepcopy(valid_row)
    mutation(row)
    with pytest.raises(artifact.V4_3ArtifactError, match=match):
        artifact._validate_row(row)


@pytest.mark.parametrize(
    "text",
    ['{"x":NaN}', '{"x":Infinity}', '{"x":-Infinity}', '{"x":1e999}', '{"x":1,"x":2}'],
)
def test_nonstandard_or_ambiguous_json_is_rejected(text: str) -> None:
    with pytest.raises(artifact.V4_3ArtifactError):
        artifact._strict_loads(text)


@pytest.fixture(scope="module")
def corrected_packet(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build current scientific rows while reusing images as test assets.

    This is a test packet, not newly retained evidence. Rendering has separate
    atlas tests; here the full unmodified verifier must accept actual 55,539-row
    source joins, schema, comparisons, provenance and predecessor integrity.
    """
    root = tmp_path_factory.mktemp("corrective-verifier") / "packet"
    shutil.copytree(canonical_v4_3_retained_root(), root)
    manifest = json.loads((root / "manifest.json").read_text())
    config = load_intrinsic_static_wrench_config()
    cases = json.loads((root / "cases.json").read_text())
    statuses: Counter[str] = Counter()
    diagnostic_rows: list[dict[str, Any]] = []
    for case in cases:
        cid = case["case_id"]
        consumed, pairs, _ = consume_v4_2b_corpus(case_ids=[cid])
        rows = [
            artifact.to_strict_jsonable(retained_force_record(row)) for row in consumed
        ]
        statuses.update(row["status"] for row in rows)
        diagnostic_rows.extend(
            {key: row[key] for key in ("status", "case_id", "vertex_feasibility")}
            for row in rows
        )
        _write_rows(root / artifact.case_wrench_rel(cid), rows)
        summary_path = root / f"cases/{cid}/summary.json"
        summary = json.loads(summary_path.read_text())
        # Placeholders are intentionally test-only. This fixture verifies data
        # and link coverage; actual rendering is covered by atlas tests.
        for name in artifact.FOLLOWUP_REQUIRED_FIGURES:
            figure = root / f"cases/{cid}/figures/{name}.png"
            if not figure.exists():
                shutil.copyfile(figure.with_name("scalar.png"), figure)
            summary["assets"].setdefault(
                name,
                {
                    "src": f"figures/{name}.png",
                    "alt": f"test-only {name} placeholder",
                    "caption": "Test-only placeholder; not retained evidence.",
                },
            )
        summary["comparisons"] = {
            key: paired_comparison_summary(pairs, key=key)
            for key in ("isotropic_radius", *artifact.DIRECTIONS)
        }
        _write_json(summary_path, summary)
        case.update(summary)
    _write_json(root / "cases.json", cases)
    _write_json(root / "schema.json", artifact.schema_documentation())
    _write_json(
        root / "config_resolved.json",
        {
            "schema_version": PACKAGE_SCHEMA_VERSION,
            "config": config.model_dump(mode="json"),
            "config_digest": config.digest(),
            "config_path": "configs/v4/intrinsic_static_wrench_v1.json",
        },
    )
    _write_json(
        root / "predecessor_integrity.json", artifact.snapshot_predecessor_integrity()
    )
    for name in ("source_lock.json", "validation.json"):
        payload = json.loads((root / name).read_text())
        key = (
            "inherited_tolerance_policy"
            if name == "source_lock.json"
            else "inherited_tolerances"
        )
        payload[key] = INHERITED_TOLERANCE_POLICY
        if name == "validation.json":
            payload.update(artifact.aggregate_vertex_diagnostics(diagnostic_rows))
        _write_json(root / name, payload)
    manifest["schema_version"] = MANIFEST_SCHEMA_VERSION
    manifest["config_digest"] = config.digest()
    manifest["status_counts"] = dict(statuses)
    manifest["files"] = artifact.inventory_package_files(root, manifest["case_ids"])
    manifest["files_digest"] = artifact.files_digest(manifest["files"])
    _write_json(root / "manifest.json", manifest)
    return root


def test_positive_full_corrective_packet(corrected_packet: Path) -> None:
    summary = artifact.verify_v4_3_artifact(corrected_packet)
    assert summary["verification_profile"] == "followup_v3"
    assert summary["n_rows"] == 55539
    assert summary["n_cases"] == 17
    assert summary["n_typed_failures"] == summary["n_silent_drops"] == 0


def test_extra_case_is_detected_without_manifest_edit(corrected_packet: Path) -> None:
    extra = corrected_packet / "cases/unexpected_case"
    extra.mkdir()
    (extra / "index.html").write_text("undeclared")
    try:
        with pytest.raises(artifact.V4_3ArtifactError, match="case-directory"):
            artifact.verify_v4_3_artifact(corrected_packet)
    finally:
        shutil.rmtree(extra)


def test_rehashed_duplicate_source_identity_is_rejected(corrected_packet: Path) -> None:
    path = corrected_packet / artifact.case_wrench_rel("span_j1_095_j2_095")
    manifest_path = corrected_packet / "manifest.json"
    original_rows, original_manifest = path.read_bytes(), manifest_path.read_bytes()
    try:
        with gzip.open(path, "rt") as stream:
            rows = [json.loads(line) for line in stream]
        replacement = next(
            row for row in rows[1:] if row["mechanism_id"] == rows[0]["mechanism_id"]
        )
        rows[0] = copy.deepcopy(replacement)
        _write_rows(path, rows)
        manifest = json.loads(original_manifest)
        rel = path.relative_to(corrected_packet).as_posix()
        manifest["files"] = [
            artifact.inventory_file(corrected_packet, rel)
            if item["path"] == rel
            else item
            for item in manifest["files"]
        ]
        manifest["files_digest"] = artifact.files_digest(manifest["files"])
        _write_json(manifest_path, manifest)
        with pytest.raises(
            artifact.V4_3ArtifactError, match="duplicate or unknown retained"
        ):
            artifact.verify_v4_3_artifact(corrected_packet)
    finally:
        path.write_bytes(original_rows)
        manifest_path.write_bytes(original_manifest)


def test_legacy_downgrade_is_rejected(corrected_packet: Path) -> None:
    path = corrected_packet / "manifest.json"
    original = path.read_bytes()
    try:
        manifest = json.loads(original)
        manifest["schema_version"] = artifact.LEGACY_MANIFEST_SCHEMA_VERSION
        _write_json(path, manifest)
        with pytest.raises(artifact.V4_3ArtifactError, match="pinned historical"):
            artifact.verify_v4_3_artifact(corrected_packet)
    finally:
        path.write_bytes(original)


@pytest.mark.parametrize(
    "changes,match",
    [
        ({"source_git_dirty": True}, "Boolean false"),
        ({"source_git_revision": "not-a-git-revision"}, "hexadecimal revision"),
        ({"n_typed_failures": 1}, "n_typed_failures"),
    ],
)
def test_manifest_provenance_and_counters_fail_closed(corrected_packet, changes, match):
    path = corrected_packet / "manifest.json"
    original = path.read_bytes()
    try:
        manifest = json.loads(original)
        manifest.update(changes)
        _write_json(path, manifest)
        with pytest.raises(artifact.V4_3ArtifactError, match=match):
            artifact.verify_v4_3_artifact(corrected_packet)
    finally:
        path.write_bytes(original)


@pytest.mark.parametrize(
    "mutation,match",
    [
        (
            lambda r: r.update(source_failure_code="source_parse_failure"),
            "typed source",
        ),
        (lambda r: r.pop("hrep_a"), "missing scientific"),
    ],
)
def test_rehashed_invalid_scientific_row_is_rejected(corrected_packet, mutation, match):
    path = corrected_packet / artifact.case_wrench_rel("span_j1_095_j2_095")
    manifest_path = corrected_packet / "manifest.json"
    original_rows, original_manifest = path.read_bytes(), manifest_path.read_bytes()
    try:
        with gzip.open(path, "rt") as stream:
            rows = [json.loads(line) for line in stream]
        mutation(rows[0])
        _write_rows(path, rows)
        manifest = json.loads(original_manifest)
        rel = path.relative_to(corrected_packet).as_posix()
        manifest["files"] = [
            artifact.inventory_file(corrected_packet, rel)
            if item["path"] == rel
            else item
            for item in manifest["files"]
        ]
        manifest["files_digest"] = artifact.files_digest(manifest["files"])
        _write_json(manifest_path, manifest)
        with pytest.raises(artifact.V4_3ArtifactError, match=match):
            artifact.verify_v4_3_artifact(corrected_packet)
    finally:
        path.write_bytes(original_rows)
        manifest_path.write_bytes(original_manifest)


def test_missing_v2_view_rejected_even_with_manifest_entry_removed(corrected_packet):
    path = corrected_packet / "cases/span_j1_095_j2_095/figures/delta.png"
    manifest_path = corrected_packet / "manifest.json"
    original_image, original_manifest = path.read_bytes(), manifest_path.read_bytes()
    try:
        path.unlink()
        manifest = json.loads(original_manifest)
        rel = path.relative_to(corrected_packet).as_posix()
        manifest["files"] = [item for item in manifest["files"] if item["path"] != rel]
        manifest["files_digest"] = artifact.files_digest(manifest["files"])
        _write_json(manifest_path, manifest)
        with pytest.raises(artifact.V4_3ArtifactError, match="missing required files"):
            artifact.verify_v4_3_artifact(corrected_packet)
    finally:
        path.write_bytes(original_image)
        manifest_path.write_bytes(original_manifest)


def test_rehashed_escaping_case_asset_link_is_rejected(corrected_packet):
    path = corrected_packet / "cases/span_j1_095_j2_095/summary.json"
    manifest_path = corrected_packet / "manifest.json"
    original_summary, original_manifest = path.read_bytes(), manifest_path.read_bytes()
    try:
        summary = json.loads(original_summary)
        summary["assets"]["delta"]["src"] = "../other-case/figures/delta.png"
        _write_json(path, summary)
        manifest = json.loads(original_manifest)
        rel = path.relative_to(corrected_packet).as_posix()
        manifest["files"] = [
            artifact.inventory_file(corrected_packet, rel)
            if item["path"] == rel
            else item
            for item in manifest["files"]
        ]
        manifest["files_digest"] = artifact.files_digest(manifest["files"])
        _write_json(manifest_path, manifest)
        with pytest.raises(artifact.V4_3ArtifactError, match="unsafe inventory path"):
            artifact.verify_v4_3_artifact(corrected_packet)
    finally:
        path.write_bytes(original_summary)
        manifest_path.write_bytes(original_manifest)
