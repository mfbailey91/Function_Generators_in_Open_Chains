"""V4.3 consumer of frozen V4.2B snapshots through the V3.6E wrench API.

V4-300/301 only: source lock, retained-row restore, three-arm pairing, and
``static_wrench_from_snapshot``. No geometry evaluation, branch synthesis,
Q regridding, or new rank thresholds.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
from collections import Counter, defaultdict
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from inequality_mechanisms.audits.v4_2b_artifact import (
    expected_case_ids,
    verify_v4_2b_artifact,
)
from inequality_mechanisms.audits.v4_artifact_guard import canonical_v4_2b_retained_root
from inequality_mechanisms.experiments.v4.geometry_atlas import (
    AtlasRow,
    parse_retained_atlas_row,
)
from inequality_mechanisms.experiments.v4.intrinsic_static_wrench_config import (
    DEFAULT_TORQUE_LIMITS,
    FROZEN_MECHANISM_IDS,
    FROZEN_V3_6D_REGISTRY_DIGEST,
    FROZEN_V4_2B_CONFIG_DIGEST,
    FROZEN_V4_2B_FILES_DIGEST,
    FROZEN_V4_2B_GRID,
    FROZEN_V4_2B_N_CASES,
    FROZEN_V4_2B_N_FILES,
    FROZEN_V4_2B_N_GEOMETRY_ROWS,
    FROZEN_V4_2B_N_ROWS_PER_ARM,
    FROZEN_V4_2B_SOURCE_REVISION,
    REQUIRED_MECHANISM_TYPES,
    REQUIRED_OUTPUT_COORDINATE_KIND,
    ROW_SCHEMA_VERSION,
    SMOKE_GRID_INDICES,
    SMOKE_N_RECORDS,
    SMOKE_SPAN_PAIRS,
    IntrinsicStaticWrenchConfig,
    SourceLock,
)
from inequality_mechanisms.metrics.static_wrench import (
    StaticWrenchCapability2D,
    static_wrench_from_snapshot,
)

GEOMETRY_SAMPLES_REL = "geometry_atlas/cases/{case_id}/geometry_samples.jsonl.gz"


class V4_3SourceError(ValueError):
    """Raised when the V4.2B source contract fails for V4.3."""

    failure_code = "v4_3_source_contract_failed"


@dataclass(frozen=True, slots=True)
class SourceIdentity:
    """Composite retained-row identity (no invented snapshot_id field)."""

    case_id: str
    q_sample_id: str
    mechanism_id: str
    mechanism_pair_id: str
    grid_index: tuple[int, int]
    config_digest: str
    source_revision: str | None
    source_relpath: str

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.case_id, self.q_sample_id, self.mechanism_id)


@dataclass(frozen=True, slots=True)
class ConsumedSourceRow:
    """One restored atlas row plus optional wrench evaluation."""

    identity: SourceIdentity
    row: AtlasRow
    wrench: StaticWrenchCapability2D | None
    source_failure_code: str | None
    source_failure_message: str | None


@dataclass(frozen=True, slots=True)
class PairedPhysicalSample:
    """Three arms joined at one shared physical Q sample."""

    case_id: str
    q_sample_id: str
    grid_index: tuple[int, int]
    arms: Mapping[str, ConsumedSourceRow]


@dataclass(frozen=True, slots=True)
class SourceCoverage:
    """Exact row accounting for the frozen V4.2B corpus."""

    n_rows: int
    n_typed_failures: int
    n_silent_drops: int
    n_rows_per_arm: Mapping[str, int]
    n_cases: int
    n_pairs: int


@dataclass(frozen=True, slots=True)
class SmokeSelection:
    """Deterministic same-bank smoke subset resolved from the live source."""

    case_ids: tuple[str, ...]
    span_pairs: tuple[tuple[int, int], ...]
    grid_indices: tuple[tuple[int, int], ...]
    mechanisms: tuple[str, ...]
    identities: tuple[SourceIdentity, ...]
    selection_digest: str

    @property
    def n_records(self) -> int:
        return len(self.identities)


def assert_v4_2b_source_lock(
    source: SourceLock | None = None,
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    """Verify the canonical V4.2B package against the V4.3 freeze lock."""
    lock = source if source is not None else SourceLock()
    package_root = canonical_v4_2b_retained_root() if root is None else Path(root)
    summary = verify_v4_2b_artifact(package_root)
    manifest = json.loads((package_root / "manifest.json").read_text(encoding="utf-8"))

    checks = (
        ("files_digest", summary["files_digest"], lock.files_digest),
        ("n_files", int(summary["n_files"]), lock.n_files),
        ("n_geometry_rows", int(summary["n_geometry_rows"]), lock.n_geometry_rows),
        (
            "source_revision",
            str(manifest.get("source_git_revision") or manifest.get("git_revision")),
            lock.source_revision,
        ),
        ("config_digest", str(manifest["config_digest"]), lock.config_digest),
        (
            "v3_6d_registry_digest",
            str(manifest["v3_6d_registry_digest"]),
            lock.v3_6d_registry_digest,
        ),
        ("n_cases", int(manifest["n_cases"]), lock.n_cases),
        ("n_rows", int(manifest["n_rows"]), lock.n_geometry_rows),
        ("n_typed_failures", int(manifest["n_typed_failures"]), 0),
        ("n_silent_drops", int(manifest["n_silent_drops"]), 0),
    )
    for name, live, expected in checks:
        if live != expected:
            raise V4_3SourceError(
                f"V4.2B {name} mismatch: live={live!r} lock={expected!r}"
            )

    grid = tuple(int(v) for v in manifest["grid"])
    if grid != tuple(lock.grid):
        raise V4_3SourceError(f"V4.2B grid mismatch: live={grid} lock={lock.grid}")
    mechanisms = tuple(str(v) for v in manifest["mechanisms"])
    if mechanisms != tuple(lock.mechanisms):
        raise V4_3SourceError(
            f"V4.2B mechanisms mismatch: live={mechanisms} lock={lock.mechanisms}"
        )
    case_ids = tuple(str(v) for v in manifest["case_ids"])
    expected_ids = expected_case_ids()
    if case_ids != expected_ids:
        raise V4_3SourceError("V4.2B case_ids do not match expected_case_ids()")
    if len(case_ids) != FROZEN_V4_2B_N_CASES:
        raise V4_3SourceError(
            f"V4.2B case count mismatch: live={len(case_ids)} "
            f"lock={FROZEN_V4_2B_N_CASES}"
        )
    return {
        **summary,
        "source_revision": lock.source_revision,
        "config_digest": lock.config_digest,
        "v3_6d_registry_digest": lock.v3_6d_registry_digest,
        "case_ids": case_ids,
        "mechanisms": mechanisms,
        "grid": grid,
    }


def load_v4_2b_cases(*, root: Path | None = None) -> list[dict[str, Any]]:
    """Load and validate ``cases.json`` mounted-coordinate metadata."""
    package_root = canonical_v4_2b_retained_root() if root is None else Path(root)
    payload = json.loads((package_root / "cases.json").read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise V4_3SourceError("cases.json must be a JSON array")
    if len(payload) != FROZEN_V4_2B_N_CASES:
        raise V4_3SourceError(
            f"cases.json length {len(payload)} != {FROZEN_V4_2B_N_CASES}"
        )
    seen: set[str] = set()
    for case in payload:
        if not isinstance(case, Mapping):
            raise V4_3SourceError("each cases.json entry must be an object")
        case_id = str(case["case_id"])
        if case_id in seen:
            raise V4_3SourceError(f"duplicate case_id {case_id!r}")
        seen.add(case_id)
        kind = case.get("output_coordinate_kind")
        if kind != REQUIRED_OUTPUT_COORDINATE_KIND:
            raise V4_3SourceError(
                f"case {case_id}: output_coordinate_kind must be "
                f"{REQUIRED_OUTPUT_COORDINATE_KIND!r}, got {kind!r}"
            )
        if "native_output_offset_rad" not in case:
            raise V4_3SourceError(
                f"case {case_id}: missing native_output_offset_rad provenance"
            )
    expected = set(expected_case_ids())
    if seen != expected:
        raise V4_3SourceError("cases.json case_id set does not match freeze lock")
    return [dict(case) for case in payload]


def geometry_samples_path(case_id: str, *, root: Path | None = None) -> Path:
    """Return the retained compressed geometry bank for one case."""
    package_root = canonical_v4_2b_retained_root() if root is None else Path(root)
    return package_root / GEOMETRY_SAMPLES_REL.format(case_id=case_id)


def iter_retained_atlas_rows(
    case_id: str,
    *,
    root: Path | None = None,
) -> Iterator[tuple[SourceIdentity, AtlasRow]]:
    """Stream one case bank through ``parse_retained_atlas_row``."""
    path = geometry_samples_path(case_id, root=root)
    if not path.is_file():
        raise V4_3SourceError(f"missing geometry bank for case {case_id}: {path}")
    rel = path.relative_to(
        canonical_v4_2b_retained_root() if root is None else Path(root)
    ).as_posix()
    try:
        handle = gzip.open(path, "rt", encoding="utf-8")
    except OSError as exc:
        raise V4_3SourceError(f"failed to open {path}: {exc}") from exc
    with handle as stream:
        for line_no, line in enumerate(stream, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                raise V4_3SourceError(f"{rel}:{line_no}: invalid JSON: {exc}") from exc
            try:
                row = parse_retained_atlas_row(payload)
            except Exception as exc:  # noqa: BLE001 - wrap as source contract
                raise V4_3SourceError(
                    f"{rel}:{line_no}: atlas row restore failed: {exc}"
                ) from exc
            if row.mechanism_id not in FROZEN_MECHANISM_IDS:
                raise V4_3SourceError(
                    f"{rel}:{line_no}: unknown mechanism_id {row.mechanism_id!r}"
                )
            identity = SourceIdentity(
                case_id=case_id,
                q_sample_id=row.q_sample_id,
                mechanism_id=row.mechanism_id,
                mechanism_pair_id=row.mechanism_pair_id,
                grid_index=row.grid_index,
                config_digest=row.config_digest,
                source_revision=row.git_revision,
                source_relpath=rel,
            )
            yield identity, row


def _require_mounted_snapshot(row: AtlasRow, *, identity: SourceIdentity) -> None:
    """Require ADR-029 mounted case provenance and arm-specific type keys."""
    if row.snapshot is None:
        return
    expected = REQUIRED_MECHANISM_TYPES.get(identity.mechanism_id)
    if expected is None:
        raise V4_3SourceError(
            f"{identity.key}: unknown mechanism_id {identity.mechanism_id!r}"
        )
    mechanism_type = row.snapshot.provenance.get("mechanism_type")
    if mechanism_type != expected:
        raise V4_3SourceError(
            f"{identity.key}: snapshot mechanism_type must be "
            f"{expected!r}, got {mechanism_type!r}"
        )
    if identity.config_digest != FROZEN_V4_2B_CONFIG_DIGEST:
        raise V4_3SourceError(
            f"{identity.key}: config_digest mismatch "
            f"{identity.config_digest!r} != {FROZEN_V4_2B_CONFIG_DIGEST!r}"
        )


def _pose_tolerance(rows: Sequence[AtlasRow]) -> float:
    tolerances: list[float] = []
    for row in rows:
        if row.snapshot is None:
            continue
        raw = row.snapshot.provenance.get("state_tolerance")
        if raw is not None:
            tolerances.append(float(raw))
    if not tolerances:
        return 1e-12
    return max(tolerances)


def _vectors_close(
    left: Sequence[float],
    right: Sequence[float],
    *,
    atol: float,
) -> bool:
    a = np.asarray(left, dtype=np.float64).reshape(-1)
    b = np.asarray(right, dtype=np.float64).reshape(-1)
    if a.shape != b.shape:
        return False
    return bool(np.all(np.abs(a - b) <= atol))


def evaluate_restored_row(
    identity: SourceIdentity,
    row: AtlasRow,
    *,
    torque_limits: Sequence[float] = DEFAULT_TORQUE_LIMITS,
    evaluate_wrench: bool = True,
) -> ConsumedSourceRow:
    """Restore provenance checks and optionally call the V3.6E API."""
    _require_mounted_snapshot(row, identity=identity)
    if row.failure_code is not None or row.snapshot is None:
        return ConsumedSourceRow(
            identity=identity,
            row=row,
            wrench=None,
            source_failure_code=row.failure_code or "missing_snapshot",
            source_failure_message=row.failure_message,
        )
    wrench: StaticWrenchCapability2D | None = None
    if evaluate_wrench:
        wrench = static_wrench_from_snapshot(
            row.snapshot,
            torque_limits=torque_limits,
        )
    return ConsumedSourceRow(
        identity=identity,
        row=row,
        wrench=wrench,
        source_failure_code=None,
        source_failure_message=None,
    )


def pair_physical_samples(
    consumed: Sequence[ConsumedSourceRow],
) -> list[PairedPhysicalSample]:
    """Join the three arms at identical case/q_sample_id with matched Q/X."""
    buckets: dict[tuple[str, str], dict[str, ConsumedSourceRow]] = defaultdict(dict)
    for item in consumed:
        key = (item.identity.case_id, item.identity.q_sample_id)
        arm = item.identity.mechanism_id
        if arm in buckets[key]:
            raise V4_3SourceError(f"duplicate arm {arm!r} for case/q_sample {key}")
        buckets[key][arm] = item

    pairs: list[PairedPhysicalSample] = []
    for (case_id, q_sample_id), arms in sorted(buckets.items()):
        missing = [mech for mech in FROZEN_MECHANISM_IDS if mech not in arms]
        if missing:
            raise V4_3SourceError(
                f"case {case_id} q_sample {q_sample_id}: missing arms {missing}"
            )
        extras = sorted(set(arms) - set(FROZEN_MECHANISM_IDS))
        if extras:
            raise V4_3SourceError(
                f"case {case_id} q_sample {q_sample_id}: unexpected arms {extras}"
            )
        rows = [arms[mech].row for mech in FROZEN_MECHANISM_IDS]
        grids = {row.grid_index for row in rows}
        if len(grids) != 1:
            raise V4_3SourceError(
                f"case {case_id} q_sample {q_sample_id}: grid_index mismatch {grids}"
            )
        valid_snaps = [row for row in rows if row.snapshot is not None]
        if valid_snaps:
            atol = _pose_tolerance(valid_snaps)
            ref = valid_snaps[0].snapshot
            assert ref is not None
            for row in valid_snaps[1:]:
                snap = row.snapshot
                assert snap is not None
                if not _vectors_close(ref.q, snap.q, atol=atol):
                    raise V4_3SourceError(
                        f"case {case_id} q_sample {q_sample_id}: mounted Q mismatch"
                    )
                if not _vectors_close(ref.x, snap.x, atol=atol):
                    raise V4_3SourceError(
                        f"case {case_id} q_sample {q_sample_id}: endpoint X mismatch"
                    )
        pairs.append(
            PairedPhysicalSample(
                case_id=case_id,
                q_sample_id=q_sample_id,
                grid_index=next(iter(grids)),
                arms=dict(arms),
            )
        )
    return pairs


def consume_v4_2b_corpus(
    *,
    root: Path | None = None,
    torque_limits: Sequence[float] = DEFAULT_TORQUE_LIMITS,
    evaluate_wrench: bool = True,
    case_ids: Sequence[str] | None = None,
) -> tuple[list[ConsumedSourceRow], list[PairedPhysicalSample], SourceCoverage]:
    """Parse, provenance-check, pair, and optionally evaluate the corpus."""
    cases = load_v4_2b_cases(root=root)
    selected = (
        tuple(case_ids)
        if case_ids is not None
        else tuple(str(case["case_id"]) for case in cases)
    )
    unknown = sorted(set(selected) - {str(case["case_id"]) for case in cases})
    if unknown:
        raise V4_3SourceError(f"unknown case_ids requested: {unknown}")

    consumed: list[ConsumedSourceRow] = []
    seen_keys: set[tuple[str, str, str]] = set()
    for case_id in selected:
        for identity, row in iter_retained_atlas_rows(case_id, root=root):
            if identity.key in seen_keys:
                raise V4_3SourceError(f"duplicate source identity {identity.key}")
            seen_keys.add(identity.key)
            consumed.append(
                evaluate_restored_row(
                    identity,
                    row,
                    torque_limits=torque_limits,
                    evaluate_wrench=evaluate_wrench,
                )
            )

    pairs = pair_physical_samples(consumed)
    per_arm = Counter(item.identity.mechanism_id for item in consumed)
    n_typed = sum(1 for item in consumed if item.source_failure_code is not None)
    coverage = SourceCoverage(
        n_rows=len(consumed),
        n_typed_failures=n_typed,
        n_silent_drops=0,
        n_rows_per_arm={mech: int(per_arm[mech]) for mech in FROZEN_MECHANISM_IDS},
        n_cases=len(selected),
        n_pairs=len(pairs),
    )
    if case_ids is None:
        if coverage.n_rows != FROZEN_V4_2B_N_GEOMETRY_ROWS:
            raise V4_3SourceError(
                f"row count {coverage.n_rows} != {FROZEN_V4_2B_N_GEOMETRY_ROWS}"
            )
        for mech in FROZEN_MECHANISM_IDS:
            if coverage.n_rows_per_arm[mech] != FROZEN_V4_2B_N_ROWS_PER_ARM:
                raise V4_3SourceError(
                    f"arm {mech} row count "
                    f"{coverage.n_rows_per_arm[mech]} != {FROZEN_V4_2B_N_ROWS_PER_ARM}"
                )
        expected_pairs = FROZEN_V4_2B_N_GEOMETRY_ROWS // len(FROZEN_MECHANISM_IDS)
        if coverage.n_pairs != expected_pairs:
            raise V4_3SourceError(
                f"paired sample count {coverage.n_pairs} != {expected_pairs}"
            )
    return consumed, pairs, coverage


def resolve_smoke_case_ids(
    cases: Sequence[Mapping[str, Any]] | None = None,
    *,
    root: Path | None = None,
) -> tuple[str, ...]:
    """Resolve the four smoke span pairs to live case IDs."""
    records = list(cases) if cases is not None else load_v4_2b_cases(root=root)
    by_span: dict[tuple[int, int], str] = {}
    for case in records:
        key = (int(case["span_j1_deg"]), int(case["span_j2_deg"]))
        case_id = str(case["case_id"])
        if key in by_span and by_span[key] != case_id:
            raise V4_3SourceError(f"ambiguous case for span {key}")
        by_span[key] = case_id
    resolved: list[str] = []
    for span in SMOKE_SPAN_PAIRS:
        if span not in by_span:
            raise V4_3SourceError(f"smoke span pair {span} missing from cases.json")
        resolved.append(by_span[span])
    return tuple(resolved)


def resolve_smoke_selection(
    *,
    root: Path | None = None,
    torque_limits: Sequence[float] = DEFAULT_TORQUE_LIMITS,
) -> tuple[SmokeSelection, list[ConsumedSourceRow], list[PairedPhysicalSample]]:
    """Freeze the deterministic 60-row smoke subset from the stored bank."""
    case_ids = resolve_smoke_case_ids(root=root)
    wanted_grids = set(SMOKE_GRID_INDICES)
    consumed: list[ConsumedSourceRow] = []
    for case_id in case_ids:
        for identity, row in iter_retained_atlas_rows(case_id, root=root):
            if identity.grid_index not in wanted_grids:
                continue
            consumed.append(
                evaluate_restored_row(
                    identity,
                    row,
                    torque_limits=torque_limits,
                    evaluate_wrench=True,
                )
            )
    if len(consumed) != SMOKE_N_RECORDS:
        raise V4_3SourceError(
            f"smoke selection expected {SMOKE_N_RECORDS} records, got {len(consumed)}"
        )
    pairs = pair_physical_samples(consumed)
    identities = tuple(item.identity for item in consumed)
    digest = hashlib.sha256()
    for identity in sorted(identities, key=lambda item: item.key):
        digest.update(
            "|".join(
                [
                    identity.case_id,
                    identity.q_sample_id,
                    identity.mechanism_id,
                    f"{identity.grid_index[0]},{identity.grid_index[1]}",
                    identity.config_digest,
                    identity.source_relpath,
                ]
            ).encode("utf-8")
        )
        digest.update(b"\n")
    selection = SmokeSelection(
        case_ids=case_ids,
        span_pairs=SMOKE_SPAN_PAIRS,
        grid_indices=SMOKE_GRID_INDICES,
        mechanisms=FROZEN_MECHANISM_IDS,
        identities=identities,
        selection_digest=digest.hexdigest(),
    )
    return selection, consumed, pairs


def consumed_row_record(item: ConsumedSourceRow) -> dict[str, Any]:
    """Build a V4.3 row envelope without rewriting the V3.6E wrench schema."""
    record: dict[str, Any] = {
        "schema_version": ROW_SCHEMA_VERSION,
        "case_id": item.identity.case_id,
        "q_sample_id": item.identity.q_sample_id,
        "mechanism_id": item.identity.mechanism_id,
        "mechanism_pair_id": item.identity.mechanism_pair_id,
        "grid_index": [
            int(item.identity.grid_index[0]),
            int(item.identity.grid_index[1]),
        ],
        "config_digest": item.identity.config_digest,
        "source_revision": item.identity.source_revision,
        "source_relpath": item.identity.source_relpath,
        "source_failure_code": item.source_failure_code,
        "source_failure_message": item.source_failure_message,
        "atlas_row_schema_version": item.row.to_dict()["schema_version"],
        "wrench": None if item.wrench is None else item.wrench.to_dict(),
    }
    return record


def smoke_selection_record(selection: SmokeSelection) -> dict[str, Any]:
    """JSON object recording the frozen smoke subset."""
    return {
        "n_records": selection.n_records,
        "case_ids": list(selection.case_ids),
        "span_pairs": [list(pair) for pair in selection.span_pairs],
        "grid_indices": [list(idx) for idx in selection.grid_indices],
        "mechanisms": list(selection.mechanisms),
        "selection_digest": selection.selection_digest,
        "identities": [
            {
                "case_id": identity.case_id,
                "q_sample_id": identity.q_sample_id,
                "mechanism_id": identity.mechanism_id,
                "grid_index": list(identity.grid_index),
                "config_digest": identity.config_digest,
                "source_relpath": identity.source_relpath,
            }
            for identity in selection.identities
        ],
    }


def coverage_record(coverage: SourceCoverage) -> dict[str, Any]:
    """JSON object for corpus coverage accounting."""
    return {
        "n_rows": coverage.n_rows,
        "n_typed_failures": coverage.n_typed_failures,
        "n_silent_drops": coverage.n_silent_drops,
        "n_rows_per_arm": dict(coverage.n_rows_per_arm),
        "n_cases": coverage.n_cases,
        "n_pairs": coverage.n_pairs,
    }


def freeze_lock_constants() -> dict[str, Any]:
    """Expose the sprint-pinned freeze values for tests and manifests."""
    return {
        "source_revision": FROZEN_V4_2B_SOURCE_REVISION,
        "files_digest": FROZEN_V4_2B_FILES_DIGEST,
        "config_digest": FROZEN_V4_2B_CONFIG_DIGEST,
        "v3_6d_registry_digest": FROZEN_V3_6D_REGISTRY_DIGEST,
        "n_files": FROZEN_V4_2B_N_FILES,
        "n_geometry_rows": FROZEN_V4_2B_N_GEOMETRY_ROWS,
        "n_rows_per_arm": FROZEN_V4_2B_N_ROWS_PER_ARM,
        "n_cases": FROZEN_V4_2B_N_CASES,
        "grid": list(FROZEN_V4_2B_GRID),
        "mechanisms": list(FROZEN_MECHANISM_IDS),
    }


def config_source_lock(config: IntrinsicStaticWrenchConfig) -> SourceLock:
    """Return the config's source lock (typed helper for callers)."""
    return config.source


def is_finite_number(value: float) -> bool:
    """Return True when ``value`` is a finite float."""
    return bool(math.isfinite(float(value)))


__all__ = [
    "ConsumedSourceRow",
    "PairedPhysicalSample",
    "SmokeSelection",
    "SourceCoverage",
    "SourceIdentity",
    "V4_3SourceError",
    "assert_v4_2b_source_lock",
    "config_source_lock",
    "consume_v4_2b_corpus",
    "consumed_row_record",
    "coverage_record",
    "evaluate_restored_row",
    "freeze_lock_constants",
    "geometry_samples_path",
    "is_finite_number",
    "iter_retained_atlas_rows",
    "load_v4_2b_cases",
    "pair_physical_samples",
    "resolve_smoke_case_ids",
    "resolve_smoke_selection",
    "smoke_selection_record",
]
