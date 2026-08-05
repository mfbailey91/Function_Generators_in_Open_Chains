"""Hierarchical Version 2 mechanism/task sample bank (V2-903).

Mechanism generation is separated from expensive Dijkstra execution.
Descriptors are computed from certified operating branches before search.
Task templates live in normalized output coordinates and are versioned
independently of mechanisms.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

import numpy as np
from numpy.random import Generator

from inequality_mechanisms.experiments.v2_config import (
    FourBarLinkConfig,
    V2ExperimentConfig,
    V2MechanismsConfig,
    V2ObjectiveConfig,
    V2OutputPair,
    V2TasksConfig,
)
from inequality_mechanisms.experiments.v2_production_config import V2ProductionConfig
from inequality_mechanisms.experiments.v2_runner import (
    FOURBAR_MECHANISM_ID,
    build_mechanism_branches,
)
from inequality_mechanisms.experiments.v2_shared_q_fixtures import (
    FROZEN_MECHANISM_PAIRS,
)
from inequality_mechanisms.mechanisms.operating_branch import (
    BranchCertificationError,
    OperatingBranch,
)
from inequality_mechanisms.mechanisms.population import (
    CrankRockerPopulationSpec,
    sample_crank_rocker,
)

SAMPLE_BANK_SCHEMA_VERSION = "v2_production_1"

PRODUCTION_TASK_LIBRARY: tuple[dict[str, Any], ...] = (
    {
        "task_id": "short_interior",
        "start_fraction": [0.40, 0.42],
        "goal_fraction": [0.55, 0.58],
        "category": "short",
        "purpose": "short interior displacement",
    },
    {
        "task_id": "short_joint1",
        "start_fraction": [0.35, 0.50],
        "goal_fraction": [0.60, 0.52],
        "category": "short_joint1",
        "purpose": "short joint-1 dominant motion",
    },
    {
        "task_id": "medium_diagonal",
        "start_fraction": [0.25, 0.30],
        "goal_fraction": [0.70, 0.72],
        "category": "medium_diagonal",
        "purpose": "medium diagonal through both axes",
    },
    {
        "task_id": "long_cross_range",
        "start_fraction": [0.15, 0.20],
        "goal_fraction": [0.85, 0.80],
        "category": "long_diagonal",
        "purpose": "long diagonal movement through both axes",
    },
    {
        "task_id": "joint1_dominant",
        "start_fraction": [0.15, 0.45],
        "goal_fraction": [0.85, 0.55],
        "category": "joint1_dominant",
        "purpose": "expose joint-1 transmission structure",
    },
    {
        "task_id": "joint2_dominant",
        "start_fraction": [0.45, 0.15],
        "goal_fraction": [0.55, 0.85],
        "category": "joint2_dominant",
        "purpose": "expose joint-2 transmission structure",
    },
    {
        "task_id": "near_boundary",
        "start_fraction": [0.08, 0.12],
        "goal_fraction": [0.90, 0.88],
        "category": "near_boundary",
        "purpose": "near-boundary endpoints",
    },
    {
        "task_id": "reverse_diagonal",
        "start_fraction": [0.80, 0.20],
        "goal_fraction": [0.20, 0.80],
        "category": "diagonal",
        "purpose": "reverse diagonal through the output box",
    },
    {
        "task_id": "medium_joint2",
        "start_fraction": [0.48, 0.20],
        "goal_fraction": [0.52, 0.75],
        "category": "joint2_dominant",
        "purpose": "medium joint-2 dominant motion",
    },
    {
        "task_id": "interior_anti_diag",
        "start_fraction": [0.30, 0.70],
        "goal_fraction": [0.70, 0.30],
        "category": "diagonal",
        "purpose": "interior anti-diagonal",
    },
    {
        "task_id": "long_joint1",
        "start_fraction": [0.10, 0.48],
        "goal_fraction": [0.90, 0.52],
        "category": "joint1_dominant",
        "purpose": "long joint-1 dominant motion",
    },
    {
        "task_id": "long_joint2",
        "start_fraction": [0.48, 0.10],
        "goal_fraction": [0.52, 0.90],
        "category": "joint2_dominant",
        "purpose": "long joint-2 dominant motion",
    },
    {
        "task_id": "short_boundary_j1",
        "start_fraction": [0.10, 0.50],
        "goal_fraction": [0.28, 0.54],
        "category": "short",
        "purpose": "short near-boundary joint-1 step",
    },
    {
        "task_id": "short_boundary_j2",
        "start_fraction": [0.50, 0.10],
        "goal_fraction": [0.54, 0.28],
        "category": "short",
        "purpose": "short near-boundary joint-2 step",
    },
    {
        "task_id": "medium_offset",
        "start_fraction": [0.20, 0.60],
        "goal_fraction": [0.65, 0.35],
        "category": "medium_diagonal",
        "purpose": "medium offset diagonal",
    },
    {
        "task_id": "center_to_corner",
        "start_fraction": [0.48, 0.50],
        "goal_fraction": [0.88, 0.86],
        "category": "long_diagonal",
        "purpose": "center toward far corner",
    },
)


@dataclass(frozen=True, slots=True)
class V2SampleBankTask:
    """One normalized output-space task template."""

    task_id: str
    start_fraction: list[float]
    goal_fraction: list[float]
    category: str
    purpose: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> V2SampleBankTask:
        return cls(
            task_id=str(data["task_id"]),
            start_fraction=[float(x) for x in data["start_fraction"]],
            goal_fraction=[float(x) for x in data["goal_fraction"]],
            category=str(data.get("category", "")),
            purpose=str(data.get("purpose", "")),
        )


@dataclass(frozen=True, slots=True)
class V2SampleBankMechanism:
    """One certified four-bar pair with pre-search descriptors."""

    mechanism_id: str
    fourbars: list[dict[str, Any]]
    descriptors: dict[str, Any]
    seed: int
    branch_summary: dict[str, Any]
    exclusions: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mechanism_id": self.mechanism_id,
            "fourbars": list(self.fourbars),
            "descriptors": dict(self.descriptors),
            "seed": int(self.seed),
            "branch_summary": dict(self.branch_summary),
            "exclusions": list(self.exclusions),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> V2SampleBankMechanism:
        return cls(
            mechanism_id=str(data["mechanism_id"]),
            fourbars=[dict(x) for x in data["fourbars"]],
            descriptors=dict(data.get("descriptors", {})),
            seed=int(data["seed"]),
            branch_summary=dict(data.get("branch_summary", {})),
            exclusions=list(data.get("exclusions", [])),
        )

    def link_configs(self) -> list[FourBarLinkConfig]:
        return [FourBarLinkConfig.model_validate(fb) for fb in self.fourbars]


@dataclass(frozen=True, slots=True)
class V2SampleBank:
    """Versioned reusable mechanism/task bank for production campaigns."""

    schema_version: str
    seed: int
    matching_rule: str
    objective_id: str
    tasks: list[V2SampleBankTask]
    mechanisms: list[V2SampleBankMechanism]
    digest: str
    provenance: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "seed": int(self.seed),
            "matching_rule": self.matching_rule,
            "objective_id": self.objective_id,
            "tasks": [t.to_dict() for t in self.tasks],
            "mechanisms": [m.to_dict() for m in self.mechanisms],
            "digest": self.digest,
            "provenance": dict(self.provenance),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> V2SampleBank:
        return cls(
            schema_version=str(data.get("schema_version", SAMPLE_BANK_SCHEMA_VERSION)),
            seed=int(data["seed"]),
            matching_rule=str(data.get("matching_rule", "span")),
            objective_id=str(data.get("objective_id", "actuator_travel")),
            tasks=[V2SampleBankTask.from_dict(t) for t in data.get("tasks", [])],
            mechanisms=[
                V2SampleBankMechanism.from_dict(m) for m in data.get("mechanisms", [])
            ],
            digest=str(data.get("digest", "")),
            provenance=dict(data.get("provenance", {})),
        )


def sample_bank_digest_payload(bank: V2SampleBank | dict[str, Any]) -> str:
    """Canonical digest excluding the digest field itself."""
    payload = bank.to_dict() if isinstance(bank, V2SampleBank) else dict(bank)
    payload = {k: v for k, v in payload.items() if k != "digest"}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def save_v2_sample_bank(bank: V2SampleBank, path: Path | str) -> Path:
    """Write a sample-bank JSON file."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bank.to_dict(), indent=2, sort_keys=False) + "\n")
    return out


def load_v2_sample_bank(path: Path | str) -> V2SampleBank:
    """Load a Version 2 production sample bank."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("sample bank root must be a mapping")
    bank = V2SampleBank.from_dict(data)
    expected = sample_bank_digest_payload(bank)
    if bank.digest and bank.digest != expected:
        raise ValueError(
            f"sample-bank digest mismatch: stored {bank.digest} computed {expected}"
        )
    return bank


def select_task_templates(n_tasks: int) -> list[V2SampleBankTask]:
    """Return the first ``n_tasks`` versioned production task templates."""
    if int(n_tasks) < 1:
        raise ValueError("n_tasks must be >= 1")
    if int(n_tasks) > len(PRODUCTION_TASK_LIBRARY):
        raise ValueError(
            f"requested {n_tasks} tasks but library has {len(PRODUCTION_TASK_LIBRARY)}"
        )
    return [
        V2SampleBankTask.from_dict(row) for row in PRODUCTION_TASK_LIBRARY[:n_tasks]
    ]


def _fourbar_dict(bar: Any) -> dict[str, Any]:
    a, b, c, d = bar.lengths
    return {
        "a": float(a),
        "b": float(b),
        "c": float(c),
        "d": float(d),
        "branch": int(bar.branch),
    }


def _link_config(bar: Any) -> FourBarLinkConfig:
    a, b, c, d = bar.lengths
    branch: Literal[1, -1] = 1 if int(bar.branch) == 1 else -1
    return FourBarLinkConfig(
        a=float(a), b=float(b), c=float(c), d=float(d), branch=branch
    )


def _axis_gain_descriptors(
    branch: OperatingBranch, n_samples: int = 33
) -> dict[str, Any]:
    cert = branch.certificate
    u_lo = np.asarray(cert.input_lower, dtype=np.float64)
    u_hi = np.asarray(cert.input_upper, dtype=np.float64)
    q_lo = np.asarray(cert.output_lower, dtype=np.float64)
    q_hi = np.asarray(cert.output_upper, dtype=np.float64)
    dim = int(u_lo.size)
    per_axis: list[dict[str, Any]] = []
    log_vars: list[float] = []
    for i in range(dim):
        u_axis = np.linspace(u_lo[i], u_hi[i], int(n_samples))
        gains: list[float] = []
        for u_i in u_axis:
            u = np.array(u_lo, dtype=np.float64)
            u[i] = float(u_i)
            jac = np.asarray(branch.jacobian(u), dtype=np.float64)
            gains.append(abs(float(jac[i, i])))
        g = np.asarray(gains, dtype=np.float64)
        g = g[np.isfinite(g) & (g > 0.0)]
        if g.size == 0:
            stats = {
                "span_q": float(q_hi[i] - q_lo[i]),
                "span_u": float(u_hi[i] - u_lo[i]),
                "gain_min": float("nan"),
                "gain_max": float("nan"),
                "gain_mean": float("nan"),
                "gain_var": float("nan"),
                "log_gain_var": float("nan"),
                "low_gain_fraction": float("nan"),
            }
        else:
            log_g = np.log(g)
            stats = {
                "span_q": float(q_hi[i] - q_lo[i]),
                "span_u": float(u_hi[i] - u_lo[i]),
                "gain_min": float(np.min(g)),
                "gain_max": float(np.max(g)),
                "gain_mean": float(np.mean(g)),
                "gain_var": float(np.var(g)),
                "log_gain_var": float(np.var(log_g)),
                "low_gain_fraction": float(np.mean(g < 0.2)),
            }
            log_vars.append(float(stats["log_gain_var"]))
        per_axis.append(stats)
    asymmetry = (
        abs(per_axis[0]["gain_mean"] - per_axis[1]["gain_mean"])
        if dim >= 2
        and np.isfinite(per_axis[0]["gain_mean"])
        and np.isfinite(per_axis[1]["gain_mean"])
        else 0.0
    )
    return {
        "per_axis": per_axis,
        "mean_log_gain_var": float(np.mean(log_vars)) if log_vars else float("nan"),
        "gain_asymmetry": float(asymmetry),
        "q_span_norm": float(np.linalg.norm(q_hi - q_lo)),
        "u_span_norm": float(np.linalg.norm(u_hi - u_lo)),
        "conditioning_margin": float(
            min(ax["gain_min"] for ax in per_axis if np.isfinite(ax["gain_min"]))
            if any(np.isfinite(ax["gain_min"]) for ax in per_axis)
            else float("nan")
        ),
    }


def _probe_config(
    config: V2ProductionConfig,
    fourbars: list[FourBarLinkConfig],
) -> V2ExperimentConfig:
    return V2ExperimentConfig(
        architecture_version=2,
        result_schema_version=2,
        planning_space="output",
        mechanisms=V2MechanismsConfig(
            comparison="fourbar_vs_equivalent_affine_gearbox",
            dim=2,
            fourbar=fourbars[0],
            fourbars=list(fourbars),
            matching_rule=config.matching_rule,
            gearbox_mechanism_id="span_matched_gearbox",
        ),
        branch=config.branch,
        sampling=config.sampling,
        objective=V2ObjectiveConfig(cost="actuator_travel", heuristic="zero"),
        edge_validation=config.edge_validation,
        tasks=V2TasksConfig(
            source="fixed_output_pairs",
            output_tolerance=config.tasks_output_tolerance,
            use_query_overlays=True,
            pairs=[V2OutputPair(start_q=[0.0, 0.0], goal_q=[1.0, 1.0])],
        ),
        algorithms=["dijkstra"],
        seed=config.seed,
        trials=1,
    )


def _try_certify_pair(
    config: V2ProductionConfig,
    fourbars: list[FourBarLinkConfig],
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    try:
        branches = build_mechanism_branches(_probe_config(config, fourbars))
    except (BranchCertificationError, ValueError, TypeError):
        return None
    fourbar_branch = branches[FOURBAR_MECHANISM_ID]
    descriptors = _axis_gain_descriptors(fourbar_branch)
    if not np.isfinite(descriptors["mean_log_gain_var"]):
        return None
    if not np.isfinite(descriptors["conditioning_margin"]):
        return None
    cert = fourbar_branch.certificate
    summary = {
        "branch_id": str(fourbar_branch.mechanism.name),
        "input_lower": [float(x) for x in cert.input_lower],
        "input_upper": [float(x) for x in cert.input_upper],
        "output_lower": [float(x) for x in cert.output_lower],
        "output_upper": [float(x) for x in cert.output_upper],
        "min_abs_gain": [float(x) for x in cert.min_abs_gain],
        "max_abs_gain": [float(x) for x in cert.max_abs_gain],
    }
    return descriptors, summary


def _stratified_select(
    candidates: list[V2SampleBankMechanism],
    n_keep: int,
) -> list[V2SampleBankMechanism]:
    if len(candidates) <= n_keep:
        return list(candidates)
    ordered = sorted(
        candidates,
        key=lambda m: float(m.descriptors.get("mean_log_gain_var", 0.0)),
    )
    if n_keep == 1:
        return [ordered[len(ordered) // 2]]
    indexes = np.linspace(0, len(ordered) - 1, n_keep)
    chosen_idx = sorted({int(round(float(i))) for i in indexes})
    while len(chosen_idx) < n_keep:
        for i in range(len(ordered)):
            if i not in chosen_idx:
                chosen_idx.append(i)
            if len(chosen_idx) >= n_keep:
                break
    return [ordered[i] for i in chosen_idx[:n_keep]]


def build_v2_sample_bank(
    config: V2ProductionConfig,
    *,
    n_mechanisms: int,
    n_tasks: int,
    rng: Generator | None = None,
    include_frozen_seed_pairs: bool = True,
) -> V2SampleBank:
    """Generate a frozen hierarchical sample bank without running Dijkstra."""
    master = np.random.default_rng(config.seed) if rng is None else rng
    tasks = select_task_templates(n_tasks)
    pop = CrankRockerPopulationSpec(
        periodic=True,
        n_crank_samples=max(64, int(config.branch.n_samples)),
        min_follower_range=0.5,
        min_abs_transmission_ratio=float(config.branch.minimum_abs_gain),
        max_abs_transmission_ratio=float(config.branch.max_abs_gain or 20.0),
        max_draw_attempts=20_000,
    )
    target_pool = max(
        int(n_mechanisms) * int(config.population.candidate_pool_multiplier),
        int(n_mechanisms),
    )
    candidates: list[V2SampleBankMechanism] = []
    exclusions: list[dict[str, Any]] = []

    if include_frozen_seed_pairs:
        for pair in FROZEN_MECHANISM_PAIRS:
            links = list(pair.fourbars)
            certified = _try_certify_pair(config, links)
            if certified is None:
                exclusions.append(
                    {
                        "mechanism_id": pair.pair_id,
                        "reason_code": "frozen_pair_certification_failed",
                    }
                )
                continue
            descriptors, summary = certified
            candidates.append(
                V2SampleBankMechanism(
                    mechanism_id=f"seed_{pair.pair_id}",
                    fourbars=[
                        {
                            "a": fb.a,
                            "b": fb.b,
                            "c": fb.c,
                            "d": fb.d,
                            "branch": fb.branch,
                        }
                        for fb in links
                    ],
                    descriptors=descriptors,
                    seed=int(config.seed),
                    branch_summary=summary,
                    exclusions=[],
                )
            )

    attempts = 0
    max_attempts = max(target_pool * 20, 50)
    need_random = len(candidates) < int(n_mechanisms)
    while need_random and len(candidates) < target_pool and attempts < max_attempts:
        attempts += 1
        mech_seed = int(master.integers(0, 2**31 - 1))
        mech_rng = np.random.default_rng(mech_seed)
        try:
            bar0 = sample_crank_rocker(mech_rng, pop, name="bar0")
            bar1 = sample_crank_rocker(mech_rng, pop, name="bar1")
        except ValueError:
            exclusions.append(
                {"reason_code": "crank_rocker_sample_failed", "attempt": attempts}
            )
            continue
        links = [_link_config(bar0), _link_config(bar1)]
        certified = _try_certify_pair(config, links)
        if certified is None:
            exclusions.append(
                {
                    "reason_code": "branch_certification_failed",
                    "attempt": attempts,
                    "seed": mech_seed,
                }
            )
            continue
        descriptors, summary = certified
        candidates.append(
            V2SampleBankMechanism(
                mechanism_id=f"cand_{len(candidates):06d}",
                fourbars=[_fourbar_dict(bar0), _fourbar_dict(bar1)],
                descriptors=descriptors,
                seed=mech_seed,
                branch_summary=summary,
                exclusions=[],
            )
        )

    selected = _stratified_select(candidates, int(n_mechanisms))
    mechanisms: list[V2SampleBankMechanism] = []
    for i, mech in enumerate(selected):
        mechanisms.append(
            V2SampleBankMechanism(
                mechanism_id=f"m{i:06d}",
                fourbars=list(mech.fourbars),
                descriptors=dict(mech.descriptors),
                seed=int(mech.seed),
                branch_summary=dict(mech.branch_summary),
                exclusions=list(mech.exclusions),
            )
        )

    provenance = {
        "n_requested_mechanisms": int(n_mechanisms),
        "n_candidate_pool": len(candidates),
        "n_selected": len(mechanisms),
        "n_tasks": int(n_tasks),
        "n_generation_exclusions": len(exclusions),
        "generation_exclusions_head": exclusions[:50],
        "include_frozen_seed_pairs": bool(include_frozen_seed_pairs),
        "selection_rule": "stratified_mean_log_gain_var",
        "population_spec": pop.to_dict(),
        "branch": config.branch.model_dump(mode="json"),
    }
    draft = V2SampleBank(
        schema_version=SAMPLE_BANK_SCHEMA_VERSION,
        seed=int(config.seed),
        matching_rule=str(config.matching_rule),
        objective_id=str(config.study.objective_cost),
        tasks=tasks,
        mechanisms=mechanisms,
        digest="",
        provenance=provenance,
    )
    digest = sample_bank_digest_payload(draft)
    return V2SampleBank(
        schema_version=draft.schema_version,
        seed=draft.seed,
        matching_rule=draft.matching_rule,
        objective_id=draft.objective_id,
        tasks=draft.tasks,
        mechanisms=draft.mechanisms,
        digest=digest,
        provenance=draft.provenance,
    )


def select_confirmation_subset(
    bank: V2SampleBank,
    *,
    n_mechanisms: int,
    seed: int,
) -> list[V2SampleBankMechanism]:
    """Return a descriptor-stratified confirmation subset, independent of outcomes."""
    del seed  # selection is deterministic from bank order + stratified rule
    return _stratified_select(list(bank.mechanisms), int(n_mechanisms))


def subset_sample_bank(
    bank: V2SampleBank,
    *,
    n_mechanisms: int | None = None,
    n_tasks: int | None = None,
    mechanism_ids: list[str] | None = None,
) -> V2SampleBank:
    """Return a digest-refreshing subset of an existing bank."""
    mechs = list(bank.mechanisms)
    if mechanism_ids is not None:
        wanted = set(mechanism_ids)
        mechs = [m for m in mechs if m.mechanism_id in wanted]
    if n_mechanisms is not None:
        mechs = mechs[: int(n_mechanisms)]
    tasks = list(bank.tasks)
    if n_tasks is not None:
        tasks = tasks[: int(n_tasks)]
    draft = V2SampleBank(
        schema_version=bank.schema_version,
        seed=bank.seed,
        matching_rule=bank.matching_rule,
        objective_id=bank.objective_id,
        tasks=tasks,
        mechanisms=mechs,
        digest="",
        provenance={
            **dict(bank.provenance),
            "subset_of_digest": bank.digest,
            "subset_n_mechanisms": len(mechs),
            "subset_n_tasks": len(tasks),
        },
    )
    return V2SampleBank(
        schema_version=draft.schema_version,
        seed=draft.seed,
        matching_rule=draft.matching_rule,
        objective_id=draft.objective_id,
        tasks=draft.tasks,
        mechanisms=draft.mechanisms,
        digest=sample_bank_digest_payload(draft),
        provenance=draft.provenance,
    )
