"""Graph-resolution selection diagnostics for Sprint Six (S6-06–S6-08)."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np

GRID_ANISOTROPY_LIMITATION = (
    "Grid refinement improves spatial resolution but does not make a "
    "four-connected graph isotropic."
)


def select_production_resolution(
    resolution_rows: Sequence[Mapping[str, Any]],
    *,
    max_relative_effect_change: float = 0.05,
    require_sign_stability: bool = True,
    require_component_stability: bool = True,
    require_task_feasibility_stability: bool = True,
    effect_key: str = "primary_effect",
    shape_key: str = "shape_n",
) -> dict[str, Any]:
    """Choose the coarsest resolution satisfying convergence criteria.

    Parameters
    ----------
    resolution_rows :
        One row per grid size, sorted ascending by ``shape_n``. Each row
        should include ``primary_effect``, ``n_components``, and
        ``task_acceptance_rate`` when the corresponding stability checks
        are enabled.
    """
    rows = sorted(resolution_rows, key=lambda r: int(r[shape_key]))
    if not rows:
        raise ValueError("resolution_rows must be non-empty")
    if len(rows) == 1:
        return {
            "production_shape_n": int(rows[0][shape_key]),
            "reason": "single_candidate",
            "criteria": {
                "max_relative_effect_change": float(max_relative_effect_change),
                "require_sign_stability": bool(require_sign_stability),
                "require_component_stability": bool(require_component_stability),
                "require_task_feasibility_stability": bool(
                    require_task_feasibility_stability
                ),
            },
            "comparisons": [],
        }

    comparisons: list[dict[str, Any]] = []
    chosen = int(rows[-1][shape_key])
    reason = "fallback_finest"

    for i in range(len(rows) - 1):
        cur = rows[i]
        nxt = rows[i + 1]
        e0 = float(cur[effect_key])
        e1 = float(nxt[effect_key])
        rel = (
            float("inf")
            if abs(e1) < 1e-12
            else abs(e0 - e1) / max(abs(e1), 1e-12)
        )
        sign_ok = (not require_sign_stability) or (
            np.sign(e0) == np.sign(e1) or (e0 == 0.0 and e1 == 0.0)
        )
        effect_ok = rel <= float(max_relative_effect_change)
        comp_ok = True
        if require_component_stability:
            comp_ok = int(cur.get("n_components", -1)) == int(
                nxt.get("n_components", -2)
            )
        feas_ok = True
        if require_task_feasibility_stability:
            a0 = float(cur.get("task_acceptance_rate", 0.0))
            a1 = float(nxt.get("task_acceptance_rate", 1.0))
            feas_ok = abs(a0 - a1) <= 0.05
        ok = bool(sign_ok and effect_ok and comp_ok and feas_ok)
        comparisons.append(
            {
                "shape_n": int(cur[shape_key]),
                "next_shape_n": int(nxt[shape_key]),
                "effect": e0,
                "next_effect": e1,
                "relative_effect_change": rel,
                "sign_stable": bool(sign_ok),
                "effect_stable": bool(effect_ok),
                "component_stable": bool(comp_ok),
                "feasibility_stable": bool(feas_ok),
                "accepted": ok,
            }
        )
        if ok:
            chosen = int(cur[shape_key])
            reason = "coarsest_stable"
            break

    return {
        "production_shape_n": chosen,
        "reason": reason,
        "criteria": {
            "max_relative_effect_change": float(max_relative_effect_change),
            "require_sign_stability": bool(require_sign_stability),
            "require_component_stability": bool(require_component_stability),
            "require_task_feasibility_stability": bool(
                require_task_feasibility_stability
            ),
        },
        "comparisons": comparisons,
    }
