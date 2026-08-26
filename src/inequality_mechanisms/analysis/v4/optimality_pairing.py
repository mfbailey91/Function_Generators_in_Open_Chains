"""V4.2D index-matched pairing and final-gap decomposition (ADR-032)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from inequality_mechanisms.analysis.v4.optimality_reference import (
    OptimalityReferenceError,
)

PAIRING_LABEL = "index-matched, not CRN"
CHECKPOINT_GOAL_IDENTITY_NOTE = (
    "V4.2C checkpoints do not retain the selected goal candidate. "
    "Final-gap decomposition is the only certified split into "
    "goal-selection regret and path inefficiency."
)


def pair_mechanism_contrasts(
    final_rows: Sequence[Mapping[str, Any]],
    reference_rows: Sequence[Mapping[str, Any]],
    *,
    tau: float,
) -> list[dict[str, Any]]:
    """Pair four-bar and gearbox rows that share case/task/planner/repetition."""
    refs: dict[tuple[Any, Any], dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for row in reference_rows:
        refs[(row["case_id"], row["task_id"])][str(row["mechanism"])] = row
    grouped: dict[tuple[Any, ...], dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for row in final_rows:
        mechanism = str(row.get("mechanism"))
        if mechanism not in ("fourbar", "gearbox"):
            continue
        key = (
            row.get("case_id"),
            row.get("task_id"),
            row.get("planner_id"),
            row.get("repetition"),
        )
        grouped[key][mechanism] = row
    out: list[dict[str, Any]] = []
    for key, arms in sorted(grouped.items(), key=lambda item: str(item[0])):
        if "fourbar" not in arms or "gearbox" not in arms:
            raise OptimalityReferenceError(
                f"unpaired mechanism contrast for {key}: {sorted(arms)}"
            )
        ref_pair = refs[(key[0], key[1])]
        if "fourbar" not in ref_pair or "gearbox" not in ref_pair:
            raise OptimalityReferenceError(f"missing reference pair for {key[:2]}")
        j_f = float(ref_pair["fourbar"]["j_star_c"])
        j_g = float(ref_pair["gearbox"]["j_star_c"])
        delta_j = j_f - j_g
        eps_f = arms["fourbar"].get("final_epsilon_rel")
        eps_g = arms["gearbox"].get("final_epsilon_rel")
        delta_eps = None
        if eps_f is not None and eps_g is not None:
            delta_eps = float(eps_f) - float(eps_g)
        already = bool(arms["fourbar"].get("already_satisfied")) or bool(
            arms["gearbox"].get("already_satisfied")
        )
        out.append(
            {
                "case_id": key[0],
                "task_id": key[1],
                "planner_id": key[2],
                "repetition": key[3],
                "delta_j_star_c_fourbar_minus_gearbox": delta_j,
                "delta_epsilon_rel_fourbar_minus_gearbox": delta_eps,
                "j_star_c_fourbar": j_f,
                "j_star_c_gearbox": j_g,
                "already_satisfied": already,
                "pairing_label": PAIRING_LABEL,
                "fourbar_request_digest": arms["fourbar"].get("request_digest"),
                "gearbox_request_digest": arms["gearbox"].get("request_digest"),
                "numerical_tau": tau,
            }
        )
    return out


def decompose_final_gaps(
    final_rows: Sequence[Mapping[str, Any]],
    candidate_rows: Sequence[Mapping[str, Any]],
    *,
    tau: float,
) -> list[dict[str, Any]]:
    """Split final gap into goal-selection regret and path inefficiency."""
    candidates: dict[tuple[Any, ...], dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for row in candidate_rows:
        key = (row["case_id"], row["task_id"], row["mechanism"])
        candidates[key][str(row["candidate_key"])] = row
    out: list[dict[str, Any]] = []
    for row in final_rows:
        key = (row.get("case_id"), row.get("task_id"), row.get("mechanism"))
        pool = candidates.get(key, {})
        selected = row.get("selected_candidate_key")
        j_star = float(row["j_star_c"])
        planner_cost = row.get("objective_cost")
        already = bool(row.get("already_satisfied"))
        if already:
            out.append(
                {
                    **_decomposition_base(row),
                    "j_star_selected": 0.0,
                    "goal_selection_regret": 0.0,
                    "path_inefficiency": 0.0,
                    "total_gap": 0.0,
                    "decomposition_status": "already_satisfied",
                    "checkpoint_goal_identity": CHECKPOINT_GOAL_IDENTITY_NOTE,
                }
            )
            continue
        if not row.get("ompl_exact_solution") or planner_cost is None:
            out.append(
                {
                    **_decomposition_base(row),
                    "j_star_selected": None,
                    "goal_selection_regret": None,
                    "path_inefficiency": None,
                    "total_gap": None,
                    "decomposition_status": "no_exact_solution",
                    "checkpoint_goal_identity": CHECKPOINT_GOAL_IDENTITY_NOTE,
                }
            )
            continue
        if selected is None or selected not in pool:
            raise OptimalityReferenceError(
                f"selected final candidate {selected!r} is not a reconstructed "
                f"center-IK key for {key}"
            )
        chosen = pool[str(selected)]
        j_selected = chosen.get("direct_cost")
        if j_selected is None:
            raise OptimalityReferenceError(
                f"selected candidate {selected} has no reconstructed direct cost"
            )
        j_selected_f = float(j_selected)
        regret = j_selected_f - j_star
        inefficiency = float(planner_cost) - j_selected_f
        total = float(planner_cost) - j_star
        if abs((regret + inefficiency) - total) > tau:
            raise OptimalityReferenceError(
                "decomposition identity failed: "
                f"regret={regret} inefficiency={inefficiency} total={total}"
            )
        if regret < -tau or inefficiency < -tau:
            raise OptimalityReferenceError(
                f"negative decomposition term beyond tau for {key}/{selected}"
            )
        out.append(
            {
                **_decomposition_base(row),
                "j_star_selected": j_selected_f,
                "goal_selection_regret": regret,
                "path_inefficiency": inefficiency,
                "total_gap": total,
                "decomposition_status": "ok",
                "checkpoint_goal_identity": CHECKPOINT_GOAL_IDENTITY_NOTE,
            }
        )
    return out


def _decomposition_base(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "request_digest": row.get("request_digest"),
        "case_id": row.get("case_id"),
        "task_id": row.get("task_id"),
        "mechanism": row.get("mechanism"),
        "planner_id": row.get("planner_id"),
        "repetition": row.get("repetition"),
        "selected_candidate_key": row.get("selected_candidate_key"),
        "reference_candidate_key": row.get("reference_candidate_key"),
        "reference_goal_match": row.get("reference_goal_match"),
        "j_star_c": row.get("j_star_c"),
        "objective_cost": row.get("objective_cost"),
        "already_satisfied": row.get("already_satisfied"),
        "pairing_label": PAIRING_LABEL,
    }
