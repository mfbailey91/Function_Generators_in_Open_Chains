"""Guards, config, and independent verification for the V4.4 velocity atlas.

The smoke package remains frozen. Atlas writers may only create
``results/v4_review/v4_4_intrinsic_velocity_atlas/`` from a clean source into
an empty root. Per-row algebra reuses ``verify_velocity_record``.
"""

from __future__ import annotations

import gzip
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from inequality_mechanisms.audits.v4_2b_artifact import expected_case_ids
from inequality_mechanisms.audits.v4_4_artifact import (
    DIRECTIONS,
    POLICIES,
    RATE_POLICIES,
    V4_4ArtifactError,
    V4_4DirtySourceError,
    aggregate_velocity_rows,
    inventory_digest,
    read_json_text,
    sha256,
    strict_json,
    verify_velocity_record,
)
from inequality_mechanisms.audits.v4_artifact_guard import (
    git_rev_parse_head,
    git_status_porcelain,
)
from inequality_mechanisms.experiments.v4.intrinsic_static_wrench import (
    assert_v4_2b_source_lock,
    iter_retained_atlas_rows,
)
from inequality_mechanisms.experiments.v4.intrinsic_static_wrench_config import (
    FROZEN_MECHANISM_IDS,
    FROZEN_V4_2B_N_GEOMETRY_ROWS,
    FROZEN_V4_2B_N_ROWS_PER_ARM,
    SourceLock,
)

CANONICAL_REPO_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = CANONICAL_REPO_ROOT

SMOKE_PACKAGE = "v4_4_velocity_ik_smoke"
SMOKE_OUTPUT_REL = Path("results/v4_review") / SMOKE_PACKAGE
ATLAS_PACKAGE = "v4_4_intrinsic_velocity_atlas"
ATLAS_OUTPUT_REL = Path("results/v4_review") / ATLAS_PACKAGE
DEFAULT_ATLAS_CONFIG_REL = Path("configs/v4/intrinsic_velocity_atlas_v1.json")
ATLAS_CONFIG_SCHEMA = "v4.4.intrinsic_velocity.atlas.config.v1"
ATLAS_ROW_SCHEMA = "v4.4.intrinsic_velocity.row.v1"
ATLAS_MANIFEST_SCHEMA = "v4.4.intrinsic_velocity.atlas.manifest.v1"
ATLAS_CASE_IDS = expected_case_ids()
GRID_SHAPE = (33, 33)
PRIMARY_MECHANISM_PAIR = ("fourbar", "span_matched_gearbox")
ATLAS_FIGURES = (
    "scalar",
    "identity_scalar",
    "status",
    *DIRECTIONS,
    *(f"{name}_diagnostic" for name in DIRECTIONS),
    "polygons",
    "true_scale_detail",
    "delta",
    "ratio",
)
ROOT_FILES = frozenset(
    {
        "README.md",
        "config.json",
        "source_lock.json",
        "schema.json",
        "coverage.json",
        "validation.json",
        "aggregate.json",
        "cases.json",
        "assets/atlas.css",
        "assets/atlas.js",
        "index.html",
    }
)


def default_velocity_atlas_config() -> dict[str, Any]:
    """Fixed full-corpus atlas contract; scientific knobs match the smoke."""
    return {
        "schema_version": ATLAS_CONFIG_SCHEMA,
        "package": ATLAS_PACKAGE,
        "output_dir": ATLAS_OUTPUT_REL.as_posix(),
        "source": SourceLock().model_dump(mode="json"),
        "selection": {
            "mode": "full_corpus",
            "grid": list(GRID_SHAPE),
            "mechanisms": list(FROZEN_MECHANISM_IDS),
        },
        "rate_limits": [1.0, 1.0],
        "rate_units": "normalized_actuator_coordinate_rate",
        "velocity_units": "length_per_normalized_time",
        "actuator_weight": [[1.0, 0.0], [0.0, 1.0]],
        "directions": list(DIRECTIONS),
        "target_speed": 1.0,
        "ik_policies": list(POLICIES),
        "rate_policies": list(RATE_POLICIES),
        "damping": 0.05,
        "no_inference_statement": (
            "Full intrinsic velocity and differential IK atlas on frozen V4.2B "
            "snapshots. Unit actuator rates are a comparison convention, not motor "
            "ratings. No trajectory, tracking, dynamics, or application claims."
        ),
    }


def load_velocity_atlas_config(path: Path | None = None) -> dict[str, Any]:
    """Require an exact match to the frozen atlas contract."""
    source = (
        CANONICAL_REPO_ROOT / DEFAULT_ATLAS_CONFIG_REL if path is None else Path(path)
    )
    payload = read_json_text(source.read_text(encoding="utf-8"))
    expected = default_velocity_atlas_config()
    if strict_json(payload) != strict_json(expected):
        raise V4_4ArtifactError("V4.4 atlas config must match the frozen contract")
    return expected


def allowed_velocity_atlas_output_root() -> Path:
    return REPO_ROOT.resolve() / ATLAS_OUTPUT_REL


def canonical_v4_4_smoke_root() -> Path:
    return CANONICAL_REPO_ROOT.resolve() / SMOKE_OUTPUT_REL


def canonical_v4_4_atlas_root() -> Path:
    return CANONICAL_REPO_ROOT.resolve() / ATLAS_OUTPUT_REL


def preflight_velocity_atlas(path: Path | None = None) -> tuple[Path, str]:
    """Refuse smoke/frozen aliases, occupied atlas roots, and dirty source."""
    repo = REPO_ROOT.resolve()
    canonical = CANONICAL_REPO_ROOT.resolve()
    if repo != canonical and (canonical in repo.parents or repo in canonical.parents):
        raise V4_4ArtifactError(
            "V4.4 atlas test roots must be isolated from the canonical tree"
        )
    smoke = repo / SMOKE_OUTPUT_REL
    allowed = repo / ATLAS_OUTPUT_REL
    candidate = allowed if path is None else Path(path).expanduser().absolute()
    if candidate == smoke or smoke in candidate.parents or candidate in smoke.parents:
        raise V4_4ArtifactError(
            f"Refusing to write into frozen V4.4 smoke evidence at {candidate}"
        )
    real_smoke = canonical_v4_4_smoke_root()
    if candidate == real_smoke or real_smoke in candidate.parents:
        raise V4_4ArtifactError(
            f"Refusing to write into frozen V4.4 smoke evidence at {candidate}"
        )
    if candidate != allowed or candidate.resolve() != allowed:
        raise V4_4ArtifactError(
            f"V4.4 atlas may write only the exact fresh root {allowed}"
        )
    for part in (candidate, *candidate.parents):
        if part == repo:
            break
        if part.is_symlink():
            raise V4_4ArtifactError("V4.4 atlas output paths may not contain symlinks")
    if candidate.exists() and (not candidate.is_dir() or any(candidate.iterdir())):
        raise V4_4ArtifactError(f"Refusing nonempty V4.4 atlas output root {candidate}")
    status = git_status_porcelain()
    if status.strip():
        raise V4_4DirtySourceError(
            "V4.4 atlas generation requires a clean committed source tree before mkdir"
        )
    revision = git_rev_parse_head()
    if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
        raise V4_4DirtySourceError(
            "V4.4 atlas source HEAD must be a full hexadecimal revision"
        )
    return candidate, revision


def case_velocity_rel(case_id: str) -> str:
    return f"cases/{case_id}/velocity_samples.jsonl.gz"


def iter_case_rows(path: Path) -> Iterator[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield read_json_text(line)


def primary_eligible(capability: Mapping[str, Any]) -> bool:
    return capability.get("status") == "regular"


def schema_documentation() -> dict[str, Any]:
    return {
        "schemas": {
            "config": ATLAS_CONFIG_SCHEMA,
            "row": ATLAS_ROW_SCHEMA,
            "manifest": ATLAS_MANIFEST_SCHEMA,
            "package": "v4.4.intrinsic_velocity.atlas.package.v1",
        },
        "directions": list(DIRECTIONS),
        "ik_policies": list(POLICIES),
        "rate_policies": list(RATE_POLICIES),
        "figures": list(ATLAS_FIGURES),
        "primary_eligibility": "capability.status == regular",
    }


def inventory_atlas_files(root: Path, case_ids: Sequence[str]) -> list[dict[str, Any]]:
    """Inventory every file except the root manifest; enforce required set."""
    root = Path(root)
    actual: set[str] = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise V4_4ArtifactError(f"symlink in atlas package: {path}")
        if path.is_file() and path != root / "manifest.json":
            actual.add(path.relative_to(root).as_posix())
    required = set(ROOT_FILES)
    for case_id in case_ids:
        required.update(
            {
                case_velocity_rel(case_id),
                f"cases/{case_id}/summary.json",
                f"cases/{case_id}/inspector.json",
                f"cases/{case_id}/index.html",
                *(f"cases/{case_id}/figures/{name}.png" for name in ATLAS_FIGURES),
            }
        )
    if missing := required - actual:
        raise V4_4ArtifactError(f"missing required atlas files: {sorted(missing)}")
    cases_dir = root / "cases"
    actual_cases = {path.name for path in cases_dir.iterdir() if path.is_dir()}
    if actual_cases != set(case_ids):
        raise V4_4ArtifactError("atlas case-directory set disagrees with case_ids")
    return [
        {
            "path": rel,
            "sha256": sha256((root / rel).read_bytes()),
            "byte_count": (root / rel).stat().st_size,
        }
        for rel in sorted(actual)
    ]


def verify_v4_4_atlas_artifact(root: Path | str) -> dict[str, Any]:
    """Verify full-corpus inventory, source joins, and per-row algebra."""
    package_root = Path(root).expanduser().resolve()
    if package_root.is_symlink():
        raise V4_4ArtifactError("V4.4 atlas package root cannot be a symlink")
    if not (package_root / "manifest.json").is_file():
        raise V4_4ArtifactError("missing atlas manifest.json")
    manifest = read_json_text((package_root / "manifest.json").read_text())
    if manifest.get("schema_version") != ATLAS_MANIFEST_SCHEMA:
        raise V4_4ArtifactError("atlas manifest schema mismatch")
    if manifest.get("package") != ATLAS_PACKAGE:
        raise V4_4ArtifactError("atlas manifest package mismatch")
    if manifest.get("source_git_dirty") is not False:
        raise V4_4ArtifactError("atlas source_git_dirty must be false")
    revision = manifest.get("source_git_revision")
    if (
        not isinstance(revision, str)
        or len(revision) != 40
        or any(c not in "0123456789abcdef" for c in revision)
    ):
        raise V4_4ArtifactError("invalid atlas generation revision")
    case_ids = tuple(manifest.get("case_ids") or ())
    if case_ids != ATLAS_CASE_IDS:
        raise V4_4ArtifactError("atlas case_ids disagree with frozen V4.2B order")
    inventory = inventory_atlas_files(package_root, case_ids)
    declared = {item["path"]: item for item in manifest.get("files", [])}
    live = {item["path"]: item for item in inventory}
    if set(declared) != set(live):
        raise V4_4ArtifactError("atlas files[] path set mismatch")
    for rel, record in live.items():
        if declared[rel].get("sha256") != record["sha256"]:
            raise V4_4ArtifactError(f"sha256 mismatch for {rel}")
    digest = inventory_digest(inventory)
    if manifest.get("files_digest") != digest:
        raise V4_4ArtifactError("atlas files_digest mismatch")
    config = load_velocity_atlas_config(package_root / "config.json")
    if manifest.get("config_digest") != sha256(
        strict_json(config, indent=None).encode()
    ):
        raise V4_4ArtifactError("atlas config digest mismatch")
    source_lock = read_json_text((package_root / "source_lock.json").read_text())
    if source_lock.get("frozen_source") != config["source"]:
        raise V4_4ArtifactError("atlas source freeze lock mismatch")
    if source_lock.get("generation_git_revision") != revision:
        raise V4_4ArtifactError("atlas generation revision mismatch")
    live_source = {
        key: value for key, value in assert_v4_2b_source_lock().items() if key != "root"
    }
    if strict_json(source_lock.get("verified_source")) != strict_json(live_source):
        raise V4_4ArtifactError("atlas verified source identity mismatch")
    schemas = read_json_text((package_root / "schema.json").read_text())
    if schemas != schema_documentation():
        raise V4_4ArtifactError("atlas schema catalog mismatch")

    per_arm: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    n_pairs = 0
    n_ik = 0
    retained: list[dict[str, Any]] = []
    for case_id in case_ids:
        source_rows = {
            (identity.q_sample_id, identity.mechanism_id): (identity, atlas_row)
            for identity, atlas_row in iter_retained_atlas_rows(case_id)
        }
        if len(source_rows) != 33 * 33 * 3:
            raise V4_4ArtifactError("frozen source identity coverage mismatch")
        rows = list(iter_case_rows(package_root / case_velocity_rel(case_id)))
        grid_arms: dict[tuple[int, int], dict[str, dict[str, Any]]] = {}
        for row in rows:
            if row.get("schema_version") != ATLAS_ROW_SCHEMA:
                raise V4_4ArtifactError("atlas row schema mismatch")
            if row.get("case_id") != case_id:
                raise V4_4ArtifactError("case_id mismatch inside atlas rows")
            identity_key = (row["q_sample_id"], row["mechanism_id"])
            source = source_rows.pop(identity_key, None)
            if source is None:
                raise V4_4ArtifactError("duplicate or unknown atlas source identity")
            identity, atlas_row = source
            if row["source_relpath"] != identity.source_relpath:
                raise V4_4ArtifactError("source_relpath mismatch")
            if row["source_snapshot"] != atlas_row.to_dict()["snapshot"]:
                raise V4_4ArtifactError("frozen snapshot mismatch")
            verify_velocity_record(row)
            if primary_eligible(row["capability"]) != bool(row.get("primary_eligible")):
                raise V4_4ArtifactError("primary_eligible disagrees with capability")
            grid = tuple(row["grid_index"])
            grid_arms.setdefault(grid, {})[row["mechanism_id"]] = row
            per_arm[row["mechanism_id"]] += 1
            statuses[row["capability"]["status"]] += 1
            n_ik += len(row["ik_requests"])
            retained.append(row)
        if source_rows:
            raise V4_4ArtifactError("silent drop: frozen source identities missing")
        if set(grid_arms) != {(i, j) for i in range(33) for j in range(33)}:
            raise V4_4ArtifactError("per-case grid coverage mismatch")
        for arms in grid_arms.values():
            if set(arms) != set(FROZEN_MECHANISM_IDS):
                raise V4_4ArtifactError("incomplete three-arm pair")
            reference = arms["fourbar"]
            for row in arms.values():
                for key in ("q", "x"):
                    if not np.allclose(
                        row["source_snapshot"][key],
                        reference["source_snapshot"][key],
                        rtol=0,
                        atol=1e-9,
                    ):
                        raise V4_4ArtifactError("paired arms do not share physical Q/X")
        n_pairs += len(grid_arms)
        summary = read_json_text(
            (package_root / f"cases/{case_id}/summary.json").read_text()
        )
        if summary.get("case_id") != case_id or summary.get("n_records") != len(rows):
            raise V4_4ArtifactError("case summary identity/count mismatch")
        assets = summary.get("assets") or {}
        if set(assets) != set(ATLAS_FIGURES):
            raise V4_4ArtifactError("case assets must expose every atlas figure")
        for name in ATLAS_FIGURES:
            rel = assets[name].get("src")
            if rel != f"figures/{name}.png":
                raise V4_4ArtifactError("case asset link must name local figure")
            if not (package_root / "cases" / case_id / rel).is_file():
                raise V4_4ArtifactError("case asset targets a missing figure")

    n_rows = sum(per_arm.values())
    expected_per_arm = {
        mech: FROZEN_V4_2B_N_ROWS_PER_ARM for mech in FROZEN_MECHANISM_IDS
    }
    if dict(per_arm) != expected_per_arm or n_rows != FROZEN_V4_2B_N_GEOMETRY_ROWS:
        raise V4_4ArtifactError("atlas row/arm counts disagree with frozen corpus")
    if n_pairs != FROZEN_V4_2B_N_ROWS_PER_ARM:
        raise V4_4ArtifactError("atlas pair count mismatch")
    if n_ik != n_rows * 24:
        raise V4_4ArtifactError("atlas IK request accounting mismatch")
    aggregate = aggregate_velocity_rows(retained)
    stored_aggregate = read_json_text((package_root / "aggregate.json").read_text())
    if stored_aggregate != aggregate:
        raise V4_4ArtifactError("root aggregate disagrees with retained rows")
    coverage = read_json_text((package_root / "coverage.json").read_text())
    validation = read_json_text((package_root / "validation.json").read_text())
    for document in (manifest, coverage):
        if document.get("n_rows") != n_rows or document.get("n_pairs") != n_pairs:
            raise V4_4ArtifactError("coverage/manifest counts mismatch")
    if validation.get("status_counts") != dict(statuses):
        raise V4_4ArtifactError("validation status_counts mismatch")
    if validation.get("n_typed_failures") != 0 or validation.get("n_silent_drops") != 0:
        raise V4_4ArtifactError("atlas typed failures / silent drops must be zero")
    return {
        "package": ATLAS_PACKAGE,
        "root": str(package_root),
        "n_files": len(inventory),
        "n_rows": n_rows,
        "n_cases": len(case_ids),
        "n_pairs": n_pairs,
        "n_ik_requests": n_ik,
        "files_digest": digest,
        "n_rows_per_arm": dict(per_arm),
        "status_counts": dict(statuses),
        "n_typed_failures": 0,
        "n_silent_drops": 0,
        "source_git_revision": revision,
        "verification_profile": "atlas_v1",
    }


__all__ = [
    "ATLAS_CASE_IDS",
    "ATLAS_FIGURES",
    "ATLAS_MANIFEST_SCHEMA",
    "ATLAS_OUTPUT_REL",
    "ATLAS_PACKAGE",
    "ATLAS_ROW_SCHEMA",
    "DEFAULT_ATLAS_CONFIG_REL",
    "SMOKE_OUTPUT_REL",
    "SMOKE_PACKAGE",
    "allowed_velocity_atlas_output_root",
    "canonical_v4_4_atlas_root",
    "canonical_v4_4_smoke_root",
    "case_velocity_rel",
    "default_velocity_atlas_config",
    "inventory_atlas_files",
    "iter_case_rows",
    "load_velocity_atlas_config",
    "preflight_velocity_atlas",
    "primary_eligible",
    "schema_documentation",
    "verify_v4_4_atlas_artifact",
]
