"""Fresh-root guard and independent algebra checks for the V4.4 smoke package.

The reader never calls the velocity or differential-IK implementation. It
checks finite transport, source identity, the forward box image, directional
quantities, and each explicitly selected inverse/rate policy independently.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

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
    SMOKE_GRID_INDICES,
    SMOKE_SPAN_PAIRS,
    SourceLock,
)

CANONICAL_REPO_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = CANONICAL_REPO_ROOT
PACKAGE = "v4_4_velocity_ik_smoke"
OUTPUT_REL = Path("results/v4_review") / PACKAGE
DEFAULT_CONFIG_REL = Path("configs/v4/intrinsic_velocity_v1.json")
CONFIG_SCHEMA = "v4.4.intrinsic_velocity.config.v1"
ROW_SCHEMA = "v4.4.intrinsic_velocity.row.v1"
MANIFEST_SCHEMA = "v4.4.intrinsic_velocity.manifest.v1"
CASE_IDS = tuple(f"span_j1_{a:03d}_j2_{b:03d}" for a, b in SMOKE_SPAN_PAIRS)
DIRECTIONS = ("positive_x", "positive_y", "radial", "tangential")
POLICIES = ("exact", "minimum_norm", "damped_least_squares")
RATE_POLICIES = ("report_only", "uniform_scale")
RATE_TOLERANCE = 32.0 * np.finfo(float).eps
RANGE_TOLERANCE = 64.0 * np.finfo(float).eps
# Near-singular full-rank maps amplify inverse/product roundoff across BLAS
# builds. Keep regular checks tight; enlarge only when inherited status is
# near_singular and the discrepancy scales with eps * condition / rate size.
NEAR_SINGULAR_EPS = float(np.finfo(float).eps)
PACKAGE_FILES = frozenset(
    {
        "config.json",
        "source_lock.json",
        "selection.json",
        "velocity_samples.jsonl",
        "aggregate.json",
        "review.svg",
        "index.html",
    }
)


class V4_4ArtifactError(ValueError):
    """Invalid V4.4 configuration, output destination, or retained evidence."""

    failure_code = "v4_4_artifact_invalid"


class V4_4DirtySourceError(V4_4ArtifactError):
    """Production generation requires a committed, clean source tree."""

    failure_code = "v4_4_dirty_source"


def default_velocity_config() -> dict[str, Any]:
    """The bounded first V4.4 comparison contract, with no physical motor rating."""
    return {
        "schema_version": CONFIG_SCHEMA,
        "package": PACKAGE,
        "output_dir": OUTPUT_REL.as_posix(),
        "source": SourceLock().model_dump(mode="json"),
        "selection": {
            "case_ids": list(CASE_IDS),
            "grid_indices": [list(grid) for grid in SMOKE_GRID_INDICES],
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
            "Instantaneous intrinsic velocity and differential IK on frozen V4.2B "
            "snapshots. Unit actuator rates are a comparison convention, not motor "
            "ratings. No trajectory, tracking, dynamics, or application claims."
        ),
    }


def strict_json(payload: Any, *, indent: int | None = 2) -> str:
    """Serialize finite JSON without silently replacing invalid numeric fields."""
    try:
        return json.dumps(payload, sort_keys=True, indent=indent, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise V4_4ArtifactError(f"V4.4 requires finite JSON: {exc}") from exc


def _reject_constant(value: str) -> Any:
    raise V4_4ArtifactError(f"nonfinite JSON constant {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise V4_4ArtifactError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def read_json_text(text: str) -> Any:
    """Reject duplicate keys, NaN/Infinity, and overflowed JSON numbers."""
    try:
        payload = json.loads(
            text, parse_constant=_reject_constant, object_pairs_hook=_unique_object
        )
        strict_json(payload, indent=None)
        return payload
    except (TypeError, ValueError) as exc:
        raise V4_4ArtifactError(f"invalid V4.4 JSON: {exc}") from exc


def load_velocity_config(path: Path | None = None) -> dict[str, Any]:
    """Validate all fields against the fixed smoke contract before any write."""
    source = CANONICAL_REPO_ROOT / DEFAULT_CONFIG_REL if path is None else Path(path)
    payload = read_json_text(source.read_text(encoding="utf-8"))
    expected = default_velocity_config()
    # Exact serialized comparison also distinguishes booleans from numbers.
    if strict_json(payload) != strict_json(expected):
        raise V4_4ArtifactError("V4.4 config must match the frozen smoke contract")
    return expected


def allowed_velocity_output_root() -> Path:
    """Only tests may inject an isolated repository root; no CLI output override."""
    return REPO_ROOT.resolve() / OUTPUT_REL


def preflight_velocity_smoke(path: Path | None = None) -> tuple[Path, str]:
    """Refuse aliases, existing evidence, dirty source, and nonexact destinations."""
    repo = REPO_ROOT.resolve()
    canonical = CANONICAL_REPO_ROOT.resolve()
    if repo != canonical and (canonical in repo.parents or repo in canonical.parents):
        raise V4_4ArtifactError(
            "V4.4 test roots must be isolated from the canonical tree"
        )
    allowed = repo / OUTPUT_REL
    candidate = allowed if path is None else Path(path).expanduser().absolute()
    if candidate != allowed or candidate.resolve() != allowed:
        raise V4_4ArtifactError(f"V4.4 may write only the exact fresh root {allowed}")
    for part in (candidate, *candidate.parents):
        if part == repo:
            break
        if part.is_symlink():
            raise V4_4ArtifactError("V4.4 output paths may not contain symlinks")
    if candidate.exists() and (not candidate.is_dir() or any(candidate.iterdir())):
        raise V4_4ArtifactError(f"Refusing nonempty V4.4 output root {candidate}")
    status = git_status_porcelain()
    if status.strip():
        raise V4_4DirtySourceError(
            "V4.4 generation requires a clean committed source tree before mkdir"
        )
    revision = git_rev_parse_head()
    if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
        raise V4_4DirtySourceError(
            "V4.4 source HEAD must be a full hexadecimal revision"
        )
    return candidate, revision


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def inventory_digest(records: Sequence[Mapping[str, Any]]) -> str:
    payload = "".join(
        f"{item['path']}\0{item['sha256']}\n"
        for item in sorted(records, key=lambda item: str(item["path"]))
    )
    return sha256(payload.encode("utf-8"))


def selection_record(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    identities = [
        {
            key: row[key]
            for key in (
                "case_id",
                "q_sample_id",
                "mechanism_id",
                "grid_index",
                "source_relpath",
            )
        }
        for row in sorted(
            rows,
            key=lambda row: (row["case_id"], row["q_sample_id"], row["mechanism_id"]),
        )
    ]
    return {
        **default_velocity_config()["selection"],
        "n_rows": len(rows),
        "n_pairs": len({(row["case_id"], row["q_sample_id"]) for row in rows}),
        "identities": identities,
        "selection_digest": sha256(strict_json(identities, indent=None).encode()),
    }


def aggregate_velocity_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Count availability separately from physical, solver, and budget status."""
    physical = Counter(str(row["capability"]["status"]) for row in rows)
    requests = [request for row in rows for request in row["ik_requests"]]
    availability = Counter(str(request["status"]) for request in requests)
    solver = Counter(
        str(request["result"]["solver_status"])
        for request in requests
        if request["result"] is not None
    )
    policy_rows = []
    for policy in POLICIES:
        for rate_policy in RATE_POLICIES:
            selected = [
                request
                for request in requests
                if request["policy"] == policy and request["rate_policy"] == rate_policy
            ]
            available = [
                item["result"] for item in selected if item["result"] is not None
            ]
            policy_rows.append(
                {
                    "policy": policy,
                    "rate_policy": rate_policy,
                    "n_requests": len(selected),
                    "n_available": len(available),
                    "n_unavailable": len(selected) - len(available),
                    "requested_exceeding_budget": sum(
                        not r["requested_feasible"] for r in available
                    ),
                    "commanded_exceeding_budget": sum(
                        not r["commanded_feasible"] for r in available
                    ),
                    "scaled_commands": sum(r["applied_scale"] < 1.0 for r in available),
                    "max_residual_norm": max(
                        (r["residual_norm"] for r in available), default=0.0
                    ),
                }
            )
    return {
        "n_rows": len(rows),
        "n_pairs": len({(row["case_id"], row["q_sample_id"]) for row in rows}),
        "n_source_failures": sum(
            row["source_failure_code"] is not None for row in rows
        ),
        "n_silent_drops": 0,
        "n_ik_requests": len(requests),
        "physical_status_counts": dict(sorted(physical.items())),
        "ik_availability_counts": dict(sorted(availability.items())),
        "solver_status_counts": dict(sorted(solver.items())),
        "policy_summary": policy_rows,
    }


def _equal(actual: Any, expected: Any, label: str) -> None:
    if isinstance(expected, (bool, np.bool_)):
        equal = type(actual) is bool and actual == bool(expected)
    elif isinstance(expected, int):
        equal = type(actual) is int and actual == expected
    elif isinstance(expected, (Mapping, list, tuple)):
        equal = strict_json(actual, indent=None) == strict_json(expected, indent=None)
    else:
        equal = actual == expected
    if not equal:
        raise V4_4ArtifactError(f"{label} mismatch")


def _close(
    actual: Any,
    expected: Any,
    label: str,
    *,
    rtol: float = 2e-9,
    atol: float = 2e-12,
) -> None:
    def has_boolean(value: Any) -> bool:
        if isinstance(value, (bool, np.bool_)):
            return True
        return isinstance(value, (tuple, list)) and any(has_boolean(v) for v in value)

    try:
        a = np.asarray(actual)
        b = np.asarray(expected, dtype=float)
    except (TypeError, ValueError) as exc:
        raise V4_4ArtifactError(f"{label} must be numeric") from exc
    if (
        has_boolean(actual)
        or a.dtype.kind not in "iuf"
        or a.shape != b.shape
        or not np.all(np.isfinite(a))
        or not np.allclose(a, b, rtol=rtol, atol=atol)
    ):
        raise V4_4ArtifactError(f"{label} disagrees with independent algebra")


def _close_near_singular(
    actual: Any,
    expected: Any,
    label: str,
    *,
    condition: float | None,
    rate_scale: float = 1.0,
) -> None:
    """Compare quantities that grow with near-singular inverse amplification."""
    cond = 1.0 if condition is None else max(float(condition), 1.0)
    scale = max(float(rate_scale), 1.0)
    rtol = max(2e-9, 64.0 * NEAR_SINGULAR_EPS * cond)
    atol = max(2e-12, 64.0 * NEAR_SINGULAR_EPS * cond * scale)
    _close(actual, expected, label, rtol=rtol, atol=atol)


def _physical_status(report: Mapping[str, Any]) -> str:
    rank = report["rank"]
    if rank == 0:
        return "bounded_zero_rank"
    if rank == 1:
        return "bounded_rank_deficient"
    condition = report["condition_number"]
    return "near_singular" if condition is not None and condition >= 1e6 else "regular"


def _directions(x: Any) -> dict[str, Any]:
    point = np.asarray(x, dtype=float)
    radius = float(np.linalg.norm(point))
    radial = None if radius <= 1e-12 else point / radius
    return {
        "positive_x": np.array([1.0, 0.0]),
        "positive_y": np.array([0.0, 1.0]),
        "radial": radial,
        "tangential": None if radial is None else np.array([-radial[1], radial[0]]),
    }


def _verify_source_fields(
    result: Mapping[str, Any], snapshot: Mapping[str, Any]
) -> None:
    for key in ("u", "q", "x", "rank_reports"):
        _equal(result[key], snapshot[key], f"stored {key}")
    for field, key in (("j_g", "j_u_to_q"), ("j_f", "j_q_to_x"), ("j_xu", "j_u_to_x")):
        _equal(result[field], snapshot["jacobians"][key], field)
    _equal(
        result["provenance"]["source_snapshot"], snapshot["provenance"], "provenance"
    )
    _equal(
        result["provenance"]["rank_policy"],
        "inherited_from_geometry_snapshot",
        "rank policy",
    )
    _equal(result["provenance"]["physical_motor_limits"], False, "physical motor claim")
    _equal(result["rate_limits"], [1.0, 1.0], "rate limits")


def verify_velocity_record(row: Mapping[str, Any]) -> None:
    """Recompute a stored row without importing the velocity/IK solver."""
    try:
        _verify_velocity_record(row)
    except (KeyError, TypeError, IndexError, np.linalg.LinAlgError) as exc:
        raise V4_4ArtifactError(f"malformed V4.4 scientific record: {exc}") from exc


def _verify_velocity_record(row: Mapping[str, Any]) -> None:
    strict_json(row)
    _equal(row["schema_version"], ROW_SCHEMA, "row schema")
    _equal(row["source_failure_code"], None, "frozen source failure")
    snapshot = row["source_snapshot"]
    cap = row["capability"]
    _verify_source_fields(cap, snapshot)
    _equal(cap["schema_version"], "v4.4.velocity_capability.v1", "capability schema")
    jacobian = np.asarray(snapshot["jacobians"]["j_u_to_x"], dtype=float)
    _close(jacobian, np.asarray(cap["j_f"]) @ np.asarray(cap["j_g"]), "J_xu")
    report = snapshot["rank_reports"]["u_to_x"]
    rank = report["rank"]
    if type(rank) is not int or rank not in (0, 1, 2):
        raise V4_4ArtifactError("invalid inherited rank")
    left, singulars, right_t = np.linalg.svd(jacobian, full_matrices=False)
    _close(report["singular_values"], singulars, "inherited singular values")
    _equal(
        int(np.count_nonzero(singulars > report["tolerance"])),
        rank,
        "inherited rank cutoff",
    )
    _equal(report["full_rank"], rank == 2, "full-rank flag")
    _equal(cap["rank"], rank, "capability rank")
    physical_status = _physical_status(report)
    _equal(cap["status"], physical_status, "physical status")
    corners = np.array([[-1.0, -1.0], [1.0, -1.0], [1.0, 1.0], [-1.0, 1.0]])
    velocity_corners = corners @ jacobian.T
    _close(cap["actuator_corners"], corners, "actuator corners")
    _close(cap["velocity_corners"], velocity_corners, "velocity corners")
    ray_model = (
        jacobian if rank == 2 else (left[:, :rank] * singulars[:rank]) @ right_t[:rank]
    )
    model_name = (
        "raw_stored_jacobian" if rank == 2 else "explicit_inherited_rank_svd_truncation"
    )
    _equal(cap["ray_model"], model_name, "ray model label")
    _equal(cap["isotropic_speed_model"], model_name, "isotropic model label")
    _equal(
        cap["support_model"],
        "raw_stored_jacobian_rate_box_image",
        "support model label",
    )
    _close(cap["ray_jacobian"], ray_model, "ray model")
    _close(cap["ray_velocity_corners"], corners @ ray_model.T, "ray corners")
    expected_isotropic = 0.0
    if rank == 2:
        inverse = np.linalg.solve(jacobian, np.eye(2))
        expected_isotropic = float(np.min(1.0 / np.linalg.norm(inverse, axis=1)))
    _close(cap["isotropic_speed"], expected_isotropic, "isotropic speed")
    directions = _directions(snapshot["x"])
    for field in (
        "directions",
        "directional_support",
        "directional_ray_speed",
        "direction_status",
    ):
        _equal(set(cap[field]), set(DIRECTIONS), field + " keys")
    for name, direction in directions.items():
        if direction is None:
            for field in ("directions", "directional_support", "directional_ray_speed"):
                _equal(cap[field][name], None, f"undefined {name} {field}")
            _equal(
                cap["direction_status"][name], "undefined_direction", name + " status"
            )
            continue
        _close(
            cap["directions"][name],
            direction,
            name + " direction",
            rtol=8.0 * np.finfo(float).eps,
            atol=8.0 * np.finfo(float).eps,
        )
        # Algebra is checked against the actual serialized unit target. A second
        # equivalent normalization can change its last bit, which is amplified
        # by an explicitly near-singular full-rank inverse.
        direction = np.asarray(cap["directions"][name], dtype=float)
        directions[name] = direction
        _close(
            cap["directional_support"][name],
            max(velocity_corners @ direction),
            name + " support",
        )
        if rank == 2:
            speed = 1.0 / float(np.max(np.abs(np.linalg.solve(jacobian, direction))))
            status = "defined"
        elif rank == 1:
            off_axis = direction - (left[:, 0] @ direction) * left[:, 0]
            in_range = float(np.linalg.norm(off_axis)) <= RANGE_TOLERANCE
            speed = float(max((corners @ ray_model.T) @ direction)) if in_range else 0.0
            status = (
                "defined_in_inherited_range" if in_range else "outside_inherited_range"
            )
        else:
            speed, status = 0.0, "zero_inherited_range"
        if physical_status == "near_singular":
            _close_near_singular(
                cap["directional_ray_speed"][name],
                speed,
                name + " ray speed",
                condition=report.get("condition_number"),
            )
        else:
            _close(cap["directional_ray_speed"][name], speed, name + " ray speed")
        _equal(cap["direction_status"][name], status, name + " status")
    expected_keys = {
        (d, p, r) for d in DIRECTIONS for p in POLICIES for r in RATE_POLICIES
    }
    keys = [(r["direction"], r["policy"], r["rate_policy"]) for r in row["ik_requests"]]
    if len(keys) != 24 or set(keys) != expected_keys:
        raise V4_4ArtifactError(
            "IK requests must cover all 24 direction/policy/rate choices"
        )
    for request in row["ik_requests"]:
        _verify_ik_request(
            request,
            snapshot,
            directions[request["direction"]],
            ray_model,
            physical_status=physical_status,
        )


def _verify_ik_request(
    request: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    direction: Any,
    rank_model: Any,
    *,
    physical_status: str,
) -> None:
    rank = snapshot["rank_reports"]["u_to_x"]["rank"]
    condition = snapshot["rank_reports"]["u_to_x"].get("condition_number")
    policy, rate_policy = request["policy"], request["rate_policy"]

    def compare(
        actual: Any, expected: Any, label: str, rate_scale: float = 1.0
    ) -> None:
        if physical_status == "near_singular":
            _close_near_singular(
                actual,
                expected,
                label,
                condition=condition,
                rate_scale=rate_scale,
            )
        else:
            _close(actual, expected, label)

    if direction is None or (policy == "exact" and rank < 2):
        _equal(request["status"], "unavailable", "IK availability")
        _equal(request["result"], None, "unavailable IK result")
        reason = (
            "undefined_direction"
            if direction is None
            else "transmission_rank_deficient"
        )
        _equal(request["failure_code"], reason, "IK unavailable reason")
        if direction is None:
            _equal(request["target_velocity"], None, "undefined target")
            _equal(request["failure_detail"], None, "undefined target detail")
        else:
            _equal(
                request["target_velocity"],
                direction.tolist(),
                "unavailable exact target",
            )
            report = snapshot["rank_reports"]["u_to_x"]
            _equal(
                request["failure_detail"],
                {
                    "operation": "differential_ik_exact",
                    "rank": rank,
                    "required_rank": 2,
                    "singular_values": report["singular_values"],
                    "tolerance": report["tolerance"],
                },
                "exact unavailable rank detail",
            )
        return
    _equal(request["status"], "available", "IK availability")
    _equal(request["failure_code"], None, "available IK failure")
    _equal(request["failure_detail"], None, "available IK failure detail")
    result = request["result"]
    _verify_source_fields(result, snapshot)
    _equal(result["schema_version"], "v4.4.differential_ik.v1", "IK schema")
    _equal(
        result["physical_status"],
        _physical_status(snapshot["rank_reports"]["u_to_x"]),
        "IK physical status",
    )
    _equal(result["policy"], policy, "IK policy")
    _equal(result["rate_policy"], rate_policy, "IK rate policy")
    _equal(result["actuator_weight"], [[1.0, 0.0], [0.0, 1.0]], "IK weight")
    _equal(request["target_velocity"], direction.tolist(), "request target")
    _equal(result["target_velocity"], direction.tolist(), "IK target")
    jacobian = np.asarray(result["j_xu"], dtype=float)
    if policy == "damped_least_squares":
        _equal(result["damping"], 0.05, "IK damping")
        expected_rates = np.linalg.solve(
            jacobian.T @ jacobian + 0.05**2 * np.eye(2), jacobian.T @ direction
        )
        model, solver_status, rank_policy = (
            jacobian,
            "regularized",
            "positive_damping_no_rank_truncation",
        )
    elif policy == "exact" or rank == 2:
        _equal(result["damping"], None, "undamped IK")
        expected_rates = np.linalg.solve(jacobian, direction)
        model, solver_status = jacobian, "exact"
        rank_policy = (
            "raw_full_rank_exact_solve"
            if policy == "exact"
            else "explicit_inherited_rank_weighted_minimum_norm"
        )
    else:
        _equal(result["damping"], None, "undamped IK")
        left, singulars, right_t = np.linalg.svd(jacobian, full_matrices=False)
        expected_rates = right_t[:rank].T @ (
            (left[:, :rank].T @ direction) / singulars[:rank]
        )
        model, solver_status, rank_policy = (
            rank_model,
            "projected",
            "explicit_inherited_rank_weighted_minimum_norm",
        )
    _equal(result["solver_status"], solver_status, "IK solver status")
    _equal(result["solver_rank_policy"], rank_policy, "IK solver rank policy")
    compare(result["solver_jacobian"], model, "IK solver Jacobian")
    rate_scale = float(np.linalg.norm(expected_rates)) + 1.0
    compare(result["requested_rates"], expected_rates, "requested IK rates", rate_scale)
    requested = np.asarray(result["requested_rates"], dtype=float)
    peak = float(np.max(np.abs(requested)))
    scale = (
        min(1.0, 1.0 / peak) if rate_policy == "uniform_scale" and peak > 0.0 else 1.0
    )
    compare(result["applied_scale"], scale, "uniform scale", rate_scale)
    commanded = requested * scale
    compare(result["commanded_rates"], commanded, "commanded IK rates", rate_scale)
    _equal(
        result["residual_convention"],
        "target_minus_raw_stored_jacobian_command",
        "residual convention",
    )
    for prefix, rates, achieved_key, residual_key, norm_key, utilization_key in (
        (
            "requested",
            requested,
            "requested_achieved_velocity",
            "requested_residual",
            "requested_residual_norm",
            "utilization_requested",
        ),
        (
            "commanded",
            commanded,
            "achieved_velocity",
            "residual",
            "residual_norm",
            "utilization_commanded",
        ),
    ):
        achieved = jacobian @ rates
        residual = direction - achieved
        utilization = np.abs(rates)
        compare(result[achieved_key], achieved, achieved_key, rate_scale)
        compare(result[residual_key], residual, residual_key, rate_scale)
        compare(result[norm_key], np.linalg.norm(residual), norm_key, rate_scale)
        compare(result[utilization_key], utilization, utilization_key, rate_scale)
        compare(
            result[prefix + "_weighted_rate_norm"],
            np.linalg.norm(rates),
            "weighted norm",
            rate_scale,
        )
        peak = float(np.max(utilization))
        compare(
            result[prefix + "_peak_utilization"],
            peak,
            "peak utilization",
            rate_scale,
        )
        _equal(
            result[prefix + "_feasible"],
            peak <= 1.0 + RATE_TOLERANCE,
            "rate feasibility",
        )
        saturated = np.flatnonzero(np.abs(utilization - 1.0) <= RATE_TOLERANCE).tolist()
        exceeding = np.flatnonzero(utilization > 1.0 + RATE_TOLERANCE).tolist()
        _equal(result[prefix + "_saturated_channels"], saturated, "saturated channels")
        _equal(result[prefix + "_exceeding_channels"], exceeding, "exceeding channels")
    command_status = (
        "uniformly_scaled_to_rate_box"
        if scale < 1.0
        else ("within_rate_box" if result["commanded_feasible"] else "outside_rate_box")
    )
    _equal(result["command_status"], command_status, "command status")


def verify_v4_4_artifact(root: Path) -> dict[str, Any]:
    """Verify exact inventory, source pairing, all 60 rows, and 1,440 requests."""
    try:
        return _verify_v4_4_artifact(Path(root))
    except (KeyError, TypeError, IndexError, OSError) as exc:
        raise V4_4ArtifactError(f"malformed V4.4 smoke package: {exc}") from exc


def _verify_v4_4_artifact(root: Path) -> dict[str, Any]:
    if root.is_symlink():
        raise V4_4ArtifactError("V4.4 package root cannot be a symlink")
    paths = list(root.rglob("*"))
    if any(path.is_symlink() for path in paths):
        raise V4_4ArtifactError("V4.4 packages cannot contain symlinks")
    actual = {path.relative_to(root).as_posix() for path in paths if path.is_file()}
    _equal(actual, PACKAGE_FILES | {"manifest.json"}, "package inventory")
    manifest = read_json_text((root / "manifest.json").read_text())
    _equal(manifest["schema_version"], MANIFEST_SCHEMA, "manifest schema")
    _equal(manifest["package"], PACKAGE, "manifest package")
    _equal(manifest["source_git_dirty"], False, "clean source")
    revision = manifest["source_git_revision"]
    if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
        raise V4_4ArtifactError("invalid generation revision")
    files = [
        {"path": name, "sha256": sha256((root / name).read_bytes())}
        for name in sorted(PACKAGE_FILES)
    ]
    _equal(manifest["files"], files, "manifest file hashes")
    _equal(manifest["n_files"], len(files), "file count")
    _equal(manifest["files_digest"], inventory_digest(files), "file inventory digest")
    config = load_velocity_config(root / "config.json")
    _equal(
        manifest["config_digest"],
        sha256(strict_json(config, indent=None).encode()),
        "config digest",
    )
    source_lock = read_json_text((root / "source_lock.json").read_text())
    _equal(
        source_lock["schema_version"],
        "v4.4.intrinsic_velocity.source_lock.v1",
        "source lock schema",
    )
    _equal(source_lock["frozen_source"], config["source"], "source freeze lock")
    _equal(
        source_lock["generation_git_revision"], revision, "source generation revision"
    )
    live_source = {
        key: value for key, value in assert_v4_2b_source_lock().items() if key != "root"
    }
    _equal(
        strict_json(source_lock["verified_source"]),
        strict_json(live_source),
        "verified source identity",
    )
    rows = [
        read_json_text(line)
        for line in (root / "velocity_samples.jsonl").read_text().splitlines()
        if line.strip()
    ]
    _equal(len(rows), 60, "smoke row count")
    keys = [
        (row["case_id"], tuple(row["grid_index"]), row["mechanism_id"]) for row in rows
    ]
    expected_keys = {
        (case, grid, arm)
        for case in CASE_IDS
        for grid in SMOKE_GRID_INDICES
        for arm in FROZEN_MECHANISM_IDS
    }
    if len(set(keys)) != 60 or set(keys) != expected_keys:
        raise V4_4ArtifactError("smoke selection is incomplete or duplicated")
    source_rows = {}
    for case in CASE_IDS:
        for identity, atlas_row in iter_retained_atlas_rows(case):
            if identity.grid_index in SMOKE_GRID_INDICES:
                source_rows[(case, identity.grid_index, identity.mechanism_id)] = (
                    identity,
                    atlas_row,
                )
    paired: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for key, row in zip(keys, rows, strict=True):
        identity, source_row = source_rows[key]
        _equal(row["q_sample_id"], identity.q_sample_id, "source sample identity")
        _equal(row["source_relpath"], identity.source_relpath, "source relative path")
        _equal(
            row["source_config_digest"],
            identity.config_digest,
            "source config identity",
        )
        _equal(
            row["source_revision"], identity.source_revision, "source revision identity"
        )
        _equal(
            row["mechanism_pair_id"],
            identity.mechanism_pair_id,
            "mechanism pair identity",
        )
        _equal(
            row["source_snapshot"], source_row.to_dict()["snapshot"], "frozen snapshot"
        )
        verify_velocity_record(row)
        paired.setdefault((row["case_id"], row["q_sample_id"]), []).append(row)
    for pair in paired.values():
        pose_tolerance = max(
            float(row["source_snapshot"]["provenance"].get("state_tolerance", 1e-12))
            for row in pair
        )
        for row in pair[1:]:
            for field in ("q", "x"):
                delta = np.asarray(row["source_snapshot"][field]) - np.asarray(
                    pair[0]["source_snapshot"][field]
                )
                if np.any(np.abs(delta) > pose_tolerance):
                    raise V4_4ArtifactError(
                        f"paired {field} exceeds inherited source state tolerance"
                    )
    selection = selection_record(rows)
    _equal(
        read_json_text((root / "selection.json").read_text()),
        selection,
        "selection metadata",
    )
    _equal(
        manifest["selection_digest"], selection["selection_digest"], "selection digest"
    )
    aggregate = aggregate_velocity_rows(rows)
    _equal(
        read_json_text((root / "aggregate.json").read_text()),
        aggregate,
        "aggregate accounting",
    )
    for field in ("n_rows", "n_pairs", "n_ik_requests"):
        _equal(manifest[field], aggregate[field], field)
    return {"output": str(root), "files_digest": manifest["files_digest"], **aggregate}
