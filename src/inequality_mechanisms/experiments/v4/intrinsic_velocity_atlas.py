"""Full-corpus V4.4 intrinsic velocity atlas consumer and package writer."""

from __future__ import annotations

import gzip
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from inequality_mechanisms.audits.v4_4_artifact import (
    V4_4ArtifactError,
    aggregate_velocity_rows,
    inventory_digest,
    sha256,
    strict_json,
)
from inequality_mechanisms.audits.v4_4_atlas_artifact import (
    ATLAS_CASE_IDS,
    ATLAS_MANIFEST_SCHEMA,
    ATLAS_PACKAGE,
    ATLAS_ROW_SCHEMA,
    inventory_atlas_files,
    load_velocity_atlas_config,
    preflight_velocity_atlas,
    primary_eligible,
    schema_documentation,
)
from inequality_mechanisms.experiments.v4.intrinsic_static_wrench import (
    ConsumedSourceRow,
    assert_v4_2b_source_lock,
    evaluate_restored_row,
    iter_retained_atlas_rows,
    pair_physical_samples,
)
from inequality_mechanisms.experiments.v4.intrinsic_static_wrench_config import (
    FROZEN_MECHANISM_IDS,
    FROZEN_V4_2B_N_GEOMETRY_ROWS,
    SourceLock,
)
from inequality_mechanisms.experiments.v4.intrinsic_velocity import (
    velocity_smoke_record,
)
from inequality_mechanisms.visualization.v4 import intrinsic_velocity_atlas as viz


def consume_velocity_atlas() -> list[ConsumedSourceRow]:
    """Restore every frozen V4.2B geometry row without computing wrench."""
    consumed: list[ConsumedSourceRow] = []
    for case_id in ATLAS_CASE_IDS:
        for identity, row in iter_retained_atlas_rows(case_id):
            consumed.append(evaluate_restored_row(identity, row, evaluate_wrench=False))
    if len(consumed) != FROZEN_V4_2B_N_GEOMETRY_ROWS:
        raise V4_4ArtifactError(
            f"V4.4 atlas requires {FROZEN_V4_2B_N_GEOMETRY_ROWS} rows, "
            f"got {len(consumed)}"
        )
    pairs = pair_physical_samples(consumed)
    if len(pairs) != FROZEN_V4_2B_N_GEOMETRY_ROWS // 3:
        raise V4_4ArtifactError("V4.4 atlas pairing is incomplete")
    if any(item.source_failure_code is not None for item in consumed):
        raise V4_4ArtifactError("Frozen V4.2B corpus contains a source failure")
    return [pair.arms[arm] for pair in pairs for arm in FROZEN_MECHANISM_IDS]


def velocity_atlas_record(
    item: ConsumedSourceRow, config: Mapping[str, Any]
) -> dict[str, Any]:
    """Build one atlas row; defer package-wide verification to the reader."""
    record = velocity_smoke_record(item, config, verify=False)
    record["schema_version"] = ATLAS_ROW_SCHEMA
    record["primary_eligible"] = primary_eligible(record["capability"])
    return record


def _group_by_case(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["case_id"])].append(dict(row))
    return grouped


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(strict_json(payload) + "\n", encoding="utf-8")


def _write_rows(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        for row in rows:
            stream.write(strict_json(row, indent=None) + "\n")


def _status_histogram(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        counts[str(row["capability"]["status"])] += 1
    return dict(sorted(counts.items()))


def generate_velocity_atlas(*, config_path: Path | None = None) -> dict[str, Any]:
    """Generate the full atlas once into the empty authorized root."""
    config = load_velocity_atlas_config(config_path)
    # Scientific knobs match smoke; only package/selection differ.
    smoke_like = {
        **config,
        "rate_limits": config["rate_limits"],
        "damping": config["damping"],
        "actuator_weight": config["actuator_weight"],
    }
    target, revision = preflight_velocity_atlas()
    source = {
        key: value
        for key, value in assert_v4_2b_source_lock(
            SourceLock(**config["source"])
        ).items()
        if key != "root"
    }
    consumed = consume_velocity_atlas()
    rows = [velocity_atlas_record(item, smoke_like) for item in consumed]
    if any(row.get("source_failure_code") is not None for row in rows):
        raise V4_4ArtifactError("typed source failure in atlas rows")
    grouped = _group_by_case(rows)
    if set(grouped) != set(ATLAS_CASE_IDS):
        raise V4_4ArtifactError("atlas case coverage incomplete")

    checked_target, checked_revision = preflight_velocity_atlas()
    if checked_target != target or checked_revision != revision:
        raise V4_4ArtifactError("V4.4 atlas source or destination changed mid-run")
    target.mkdir(parents=True, exist_ok=True)
    viz.write_local_assets(target)

    case_summaries: list[dict[str, Any]] = []
    for case_id in ATLAS_CASE_IDS:
        case_rows = grouped[case_id]
        case_dir = target / "cases" / case_id
        _write_rows(case_dir / "velocity_samples.jsonl.gz", case_rows)
        summary = viz.write_case_package(case_dir, case_id=case_id, rows=case_rows)
        case_summaries.append(
            {
                "case_id": case_id,
                "n_records": len(case_rows),
                "href": f"cases/{case_id}/index.html",
                **summary,
            }
        )

    aggregate = aggregate_velocity_rows(rows)
    status_counts = _status_histogram(rows)
    _write_json(target / "config.json", config)
    _write_json(
        target / "source_lock.json",
        {
            "schema_version": "v4.4.intrinsic_velocity.atlas.source_lock.v1",
            "generation_git_revision": revision,
            "frozen_source": config["source"],
            "verified_source": source,
        },
    )
    _write_json(target / "schema.json", schema_documentation())
    _write_json(target / "aggregate.json", aggregate)
    _write_json(target / "cases.json", case_summaries)
    _write_json(
        target / "coverage.json",
        {
            "mode": "canonical",
            "n_rows": aggregate["n_rows"],
            "n_cases": len(ATLAS_CASE_IDS),
            "n_pairs": aggregate["n_pairs"],
            "n_ik_requests": aggregate["n_ik_requests"],
            "n_typed_failures": 0,
            "n_silent_drops": 0,
            "n_rows_per_arm": {
                mech: sum(1 for row in rows if row["mechanism_id"] == mech)
                for mech in FROZEN_MECHANISM_IDS
            },
            "mechanisms": list(FROZEN_MECHANISM_IDS),
            "status_counts": status_counts,
        },
    )
    _write_json(
        target / "validation.json",
        {
            "source_lock": source,
            "no_inference_statement": config["no_inference_statement"],
            "n_typed_failures": 0,
            "n_silent_drops": 0,
            "status_counts": status_counts,
            "require_full_corpus": True,
            "n_ik_requests": aggregate["n_ik_requests"],
        },
    )
    (target / "README.md").write_text(
        (
            f"# {ATLAS_PACKAGE}\n\n"
            f"{config['no_inference_statement']}\n\n"
            f"- rows: {aggregate['n_rows']}\n"
            f"- pairs: {aggregate['n_pairs']}\n"
            f"- IK requests: {aggregate['n_ik_requests']}\n"
            f"- generation revision: `{revision}`\n"
        ),
        encoding="utf-8",
    )
    viz.write_index_html(
        target, cases=case_summaries, aggregate=aggregate, config=config
    )

    inventory = inventory_atlas_files(target, ATLAS_CASE_IDS)
    digest = inventory_digest(inventory)
    manifest = {
        "schema_version": ATLAS_MANIFEST_SCHEMA,
        "package": ATLAS_PACKAGE,
        "source_git_revision": revision,
        "source_git_dirty": False,
        "config_digest": sha256(strict_json(config, indent=None).encode()),
        "case_ids": list(ATLAS_CASE_IDS),
        "n_rows": aggregate["n_rows"],
        "n_pairs": aggregate["n_pairs"],
        "n_ik_requests": aggregate["n_ik_requests"],
        "n_cases": len(ATLAS_CASE_IDS),
        "n_typed_failures": 0,
        "n_silent_drops": 0,
        "n_files": len(inventory),
        "files": inventory,
        "files_digest": digest,
    }
    _write_json(target / "manifest.json", manifest)
    return {
        "output": str(target),
        "files_digest": digest,
        "source_git_revision": revision,
        **aggregate,
    }


__all__ = [
    "consume_velocity_atlas",
    "generate_velocity_atlas",
    "velocity_atlas_record",
]
