"""Fixed mechanism/task sample bank for Sprint Six (S6-19)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.random import Generator

from inequality_mechanisms.experiments.config import ExperimentConfig
from inequality_mechanisms.experiments.pilot import (
    _build_population_trial_graphs,
    _pair_found,
    _records_for_task,
    _shared_grid,
    _try_one_paired_task,
)
from inequality_mechanisms.experiments.setup import PairedGraphs, build_paired_graphs
from inequality_mechanisms.experiments.tasks import PairedTask
from inequality_mechanisms.mechanisms.base import Mechanism


@dataclass(frozen=True, slots=True)
class SampleBankTask:
    """One requested output task inside a mechanism entry."""

    task_id: str
    q_start: list[float]
    q_goal: list[float]
    seed: int


@dataclass(frozen=True, slots=True)
class SampleBankMechanism:
    """One independently sampled mechanism with nested tasks."""

    mechanism_id: str
    fourbar: dict[str, Any]
    limits: dict[str, Any] | None
    gearbox: dict[str, Any]
    baseline_label: str
    seed: int
    tasks: list[SampleBankTask]
    exclusions: list[dict[str, Any]]


@dataclass(frozen=True, slots=True)
class SampleBank:
    """Versioned reusable mechanism/task bank."""

    schema_version: str
    seed: int
    matching_rule: str | None
    mechanisms: list[SampleBankMechanism]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "seed": int(self.seed),
            "matching_rule": self.matching_rule,
            "mechanisms": [
                {
                    "mechanism_id": m.mechanism_id,
                    "fourbar": m.fourbar,
                    "limits": m.limits,
                    "gearbox": m.gearbox,
                    "baseline_label": m.baseline_label,
                    "seed": int(m.seed),
                    "tasks": [asdict(t) for t in m.tasks],
                    "exclusions": list(m.exclusions),
                }
                for m in self.mechanisms
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SampleBank:
        mechanisms: list[SampleBankMechanism] = []
        for raw in data.get("mechanisms", []):
            tasks = [
                SampleBankTask(
                    task_id=str(t["task_id"]),
                    q_start=[float(x) for x in t["q_start"]],
                    q_goal=[float(x) for x in t["q_goal"]],
                    seed=int(t["seed"]),
                )
                for t in raw.get("tasks", [])
            ]
            mechanisms.append(
                SampleBankMechanism(
                    mechanism_id=str(raw["mechanism_id"]),
                    fourbar=dict(raw["fourbar"]),
                    limits=None if raw.get("limits") is None else dict(raw["limits"]),
                    gearbox=dict(raw["gearbox"]),
                    baseline_label=str(raw["baseline_label"]),
                    seed=int(raw["seed"]),
                    tasks=tasks,
                    exclusions=list(raw.get("exclusions", [])),
                )
            )
        return cls(
            schema_version=str(data.get("schema_version", "6.0.0")),
            seed=int(data["seed"]),
            matching_rule=data.get("matching_rule"),
            mechanisms=mechanisms,
        )


def save_sample_bank(bank: SampleBank, path: Path | str) -> Path:
    """Write a sample bank JSON file."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bank.to_dict(), indent=2, sort_keys=False) + "\n")
    return out


def load_sample_bank(path: Path | str) -> SampleBank:
    """Load a sample bank JSON file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("sample bank root must be a mapping")
    return SampleBank.from_dict(data)


def _baseline_label(gearbox: Mechanism) -> str:
    from inequality_mechanisms.mechanisms.equivalence import baseline_label_for_mechanism

    return baseline_label_for_mechanism(gearbox)


def build_sample_bank_from_config(
    config: ExperimentConfig,
    *,
    n_mechanisms: int | None = None,
    tasks_per_mechanism: int | None = None,
    rng: Generator | None = None,
) -> SampleBank:
    """Materialize a fixed M×K sample bank from an experiment config.

    Fixed four-bar mode yields one mechanism entry (reused) with K tasks.
    Population mode samples M independent four-bars each with K tasks.
    """
    s6 = config.sprint6
    m_target = int(n_mechanisms if n_mechanisms is not None else s6.n_mechanisms)
    k_target = int(
        tasks_per_mechanism
        if tasks_per_mechanism is not None
        else s6.tasks_per_mechanism
    )
    master = np.random.default_rng(config.seed) if rng is None else rng
    matching_rule = None
    if str(config.mechanisms.gearbox.get("type")) == "equivalent_gearbox":
        matching_rule = str(config.mechanisms.gearbox.get("matching_rule"))

    mechanisms: list[SampleBankMechanism] = []
    mode = config.mechanisms.fourbar_mode

    if mode == "fixed":
        paired = build_paired_graphs(config)
        mech_seed = int(master.integers(0, 2**31 - 1))
        tasks, exclusions = _sample_tasks_for_pair(
            paired,
            config,
            master,
            mechanism_id="m0000",
            k_target=k_target,
        )
        mechanisms.append(
            SampleBankMechanism(
                mechanism_id="m0000",
                fourbar=paired.fourbar_mechanism.to_dict(),
                limits={
                    "lower": paired.limits.lower.tolist(),
                    "upper": paired.limits.upper.tolist(),
                },
                gearbox=paired.gearbox_mechanism.to_dict(),
                baseline_label=_baseline_label(paired.gearbox_mechanism),
                seed=mech_seed,
                tasks=tasks,
                exclusions=exclusions,
            )
        )
    else:
        grid = _shared_grid(config)
        for mi in range(m_target):
            mech_seed = int(master.integers(0, 2**31 - 1))
            mech_rng = np.random.default_rng(mech_seed)
            paired = _build_population_trial_graphs(config, mech_rng, grid=grid)
            mechanism_id = f"m{mi:04d}"
            tasks, exclusions = _sample_tasks_for_pair(
                paired,
                config,
                master,
                mechanism_id=mechanism_id,
                k_target=k_target,
            )
            mechanisms.append(
                SampleBankMechanism(
                    mechanism_id=mechanism_id,
                    fourbar=paired.fourbar_mechanism.to_dict(),
                    limits={
                        "lower": paired.limits.lower.tolist(),
                        "upper": paired.limits.upper.tolist(),
                    },
                    gearbox=paired.gearbox_mechanism.to_dict(),
                    baseline_label=_baseline_label(paired.gearbox_mechanism),
                    seed=mech_seed,
                    tasks=tasks,
                    exclusions=exclusions,
                )
            )

    return SampleBank(
        schema_version="6.0.0",
        seed=int(config.seed),
        matching_rule=matching_rule,
        mechanisms=mechanisms,
    )


def _sample_tasks_for_pair(
    paired: PairedGraphs,
    config: ExperimentConfig,
    rng: Generator,
    *,
    mechanism_id: str,
    k_target: int,
) -> tuple[list[SampleBankTask], list[dict[str, Any]]]:
    tasks: list[SampleBankTask] = []
    exclusions: list[dict[str, Any]] = []
    attempts = 0
    max_attempts = int(config.trials.max_sample_attempts)
    while len(tasks) < k_target and attempts < max_attempts:
        attempts += 1
        task_seed = int(rng.integers(0, 2**31 - 1))
        task_rng = np.random.default_rng(task_seed)
        remaining = max_attempts - attempts + 1
        candidate = _try_one_paired_task(
            paired, task_rng, config, remaining_attempts=remaining
        )
        if candidate is None:
            exclusions.append(
                {
                    "mechanism_id": mechanism_id,
                    "reason_code": "task_sample_failed",
                    "attempt": attempts,
                }
            )
            continue
        if bool(config.trials.require_reachable):
            algorithms = list(config.algorithms.names)
            reach_algo = "dijkstra" if "dijkstra" in algorithms else algorithms[0]
            probe = PairedTask(
                trial_index=0,
                q_start=candidate.q_start,
                q_goal=candidate.q_goal,
                gearbox=candidate.gearbox,
                fourbar=candidate.fourbar,
                output_residual_tol=candidate.output_residual_tol,
            )
            trial_rows = _records_for_task(
                probe,
                paired,
                algorithms=[reach_algo],
                cost_type=str(config.cost.type),
                validate_h=False,
            )
            if not _pair_found(trial_rows, algorithm=reach_algo):
                exclusions.append(
                    {
                        "mechanism_id": mechanism_id,
                        "reason_code": "unreachable",
                        "attempt": attempts,
                    }
                )
                continue
        task_id = f"{mechanism_id}_t{len(tasks):04d}"
        tasks.append(
            SampleBankTask(
                task_id=task_id,
                q_start=candidate.q_start.tolist(),
                q_goal=candidate.q_goal.tolist(),
                seed=task_seed,
            )
        )
    if len(tasks) < k_target:
        exclusions.append(
            {
                "mechanism_id": mechanism_id,
                "reason_code": "insufficient_tasks",
                "n_accepted_tasks": len(tasks),
                "n_requested_tasks": k_target,
            }
        )
    return tasks, exclusions
