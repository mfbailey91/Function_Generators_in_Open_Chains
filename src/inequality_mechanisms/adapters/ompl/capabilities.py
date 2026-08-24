"""V4-231: OMPL Python-binding capability matrix.

The parent process never imports ``ompl``. Construction, method-presence,
and binding-behavior probes run in spawn children so a hang or crash
becomes a typed row instead of taking down the parent.

Missing OMPL fills the frozen catalog with ``unavailable_dependency``
and does not spawn children.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from multiprocessing import Queue, get_context
from typing import Any, Final

from inequality_mechanisms.adapters.ompl._availability import (
    is_ompl_available,
    ompl_version_string,
)

STATUS_SUPPORTED: Final = "supported"
STATUS_UNSUPPORTED: Final = "unsupported"
STATUS_UNAVAILABLE_DEPENDENCY: Final = "unavailable_dependency"
STATUS_CRASHED: Final = "crashed"
STATUS_CHILD_TIMEOUT: Final = "child_timeout"
STATUS_MISSING_SYMBOL: Final = "missing_symbol"
STATUS_BINDING_EXCEPTION: Final = "binding_exception"

STATUSES: Final[frozenset[str]] = frozenset(
    {
        STATUS_SUPPORTED,
        STATUS_UNSUPPORTED,
        STATUS_UNAVAILABLE_DEPENDENCY,
        STATUS_CRASHED,
        STATUS_CHILD_TIMEOUT,
        STATUS_MISSING_SYMBOL,
        STATUS_BINDING_EXCEPTION,
    }
)

SCHEMA_VERSION: Final = "v4.2c.ompl_capability_matrix.v1"
DEFAULT_TIMEOUT_S: Final = 8.0
MULTI_GOAL_TIMEOUT_S: Final = 12.0


@dataclass(frozen=True, slots=True)
class FeatureSpec:
    """One frozen capability-catalog entry."""

    feature_id: str
    required: bool
    timeout_s: float
    summary: str


FEATURE_SPECS: Final[tuple[FeatureSpec, ...]] = (
    FeatureSpec("planner_prm", True, DEFAULT_TIMEOUT_S, "construct ompl.geometric.PRM"),
    FeatureSpec(
        "planner_rrtconnect",
        True,
        DEFAULT_TIMEOUT_S,
        "construct ompl.geometric.RRTConnect",
    ),
    FeatureSpec(
        "planner_rrtstar", True, DEFAULT_TIMEOUT_S, "construct ompl.geometric.RRTstar"
    ),
    FeatureSpec(
        "planner_bitstar", True, DEFAULT_TIMEOUT_S, "construct ompl.geometric.BITstar"
    ),
    FeatureSpec("planner_fmt", True, DEFAULT_TIMEOUT_S, "construct ompl.geometric.FMT"),
    FeatureSpec(
        "planner_kpiece1", True, DEFAULT_TIMEOUT_S, "construct ompl.geometric.KPIECE1"
    ),
    FeatureSpec(
        "planner_pdst", False, DEFAULT_TIMEOUT_S, "construct ompl.geometric.PDST"
    ),
    FeatureSpec(
        "methods_rrtstar",
        True,
        DEFAULT_TIMEOUT_S,
        "RRTstar setRange / setGoalBias",
    ),
    FeatureSpec(
        "methods_bitstar",
        True,
        DEFAULT_TIMEOUT_S,
        "BITstar setSamplesPerBatch / setRewireFactor",
    ),
    FeatureSpec(
        "methods_fmt",
        True,
        DEFAULT_TIMEOUT_S,
        "FMT sample-count and heuristic setters",
    ),
    FeatureSpec(
        "methods_kpiece1",
        True,
        DEFAULT_TIMEOUT_S,
        "KPIECE1 range, goal bias, projection evaluator",
    ),
    FeatureSpec(
        "methods_pdst",
        False,
        DEFAULT_TIMEOUT_S,
        "PDST setProjectionEvaluator",
    ),
    FeatureSpec(
        "multi_goal_rrtstar",
        True,
        MULTI_GOAL_TIMEOUT_S,
        "RRTstar true multi-GoalStates solve",
    ),
    FeatureSpec(
        "multi_goal_bitstar",
        True,
        MULTI_GOAL_TIMEOUT_S,
        "BITstar true multi-GoalStates solve",
    ),
    FeatureSpec(
        "multi_goal_fmt",
        True,
        MULTI_GOAL_TIMEOUT_S,
        "FMT true multi-GoalStates solve",
    ),
    FeatureSpec(
        "multi_goal_kpiece1",
        True,
        MULTI_GOAL_TIMEOUT_S,
        "KPIECE1 true multi-GoalStates solve",
    ),
    FeatureSpec(
        "multi_goal_prm",
        True,
        MULTI_GOAL_TIMEOUT_S,
        "PRM true multi-GoalStates solve (typed hang evidence)",
    ),
    FeatureSpec(
        "repeated_solve",
        True,
        DEFAULT_TIMEOUT_S,
        "repeated solve() continuation",
    ),
    FeatureSpec(
        "projection_evaluator",
        True,
        DEFAULT_TIMEOUT_S,
        "Python ProjectionEvaluator subclass",
    ),
    FeatureSpec(
        "projection_cell_sizes",
        True,
        DEFAULT_TIMEOUT_S,
        "explicit projection cell sizes / bounds",
    ),
    FeatureSpec(
        "planner_data",
        True,
        DEFAULT_TIMEOUT_S,
        "PlannerData / getPlannerData",
    ),
    FeatureSpec(
        "sampler_allocator",
        True,
        DEFAULT_TIMEOUT_S,
        "state sampler allocator",
    ),
    FeatureSpec(
        "sampler_precomputed",
        False,
        DEFAULT_TIMEOUT_S,
        "precomputed state sampler",
    ),
    FeatureSpec(
        "sampler_deterministic",
        False,
        DEFAULT_TIMEOUT_S,
        "deterministic state sampler",
    ),
    FeatureSpec(
        "exact_solution_api",
        True,
        DEFAULT_TIMEOUT_S,
        "hasSolution / hasExactSolution",
    ),
)

FEATURE_IDS: Final[tuple[str, ...]] = tuple(spec.feature_id for spec in FEATURE_SPECS)
REQUIRED_FEATURE_IDS: Final[tuple[str, ...]] = tuple(
    spec.feature_id for spec in FEATURE_SPECS if spec.required
)
OPTIONAL_FEATURE_IDS: Final[tuple[str, ...]] = tuple(
    spec.feature_id for spec in FEATURE_SPECS if not spec.required
)

_PLANNER_CLASSES: Final[dict[str, str]] = {
    "planner_prm": "PRM",
    "planner_rrtconnect": "RRTConnect",
    "planner_rrtstar": "RRTstar",
    "planner_bitstar": "BITstar",
    "planner_fmt": "FMT",
    "planner_kpiece1": "KPIECE1",
    "planner_pdst": "PDST",
}

_PLANNER_METHODS: Final[dict[str, tuple[str, tuple[str, ...]]]] = {
    "methods_rrtstar": ("RRTstar", ("setRange", "setGoalBias")),
    "methods_bitstar": ("BITstar", ("setSamplesPerBatch", "setRewireFactor")),
    "methods_fmt": (
        "FMT",
        (
            "setNumSamples",
            "setNearestK",
            "setRadiusMultiplier",
            "setHeuristics",
            "setExtendedFMT",
        ),
    ),
    "methods_kpiece1": (
        "KPIECE1",
        ("setRange", "setGoalBias", "setProjectionEvaluator"),
    ),
    "methods_pdst": ("PDST", ("setProjectionEvaluator",)),
}

_MULTI_GOAL_PLANNERS: Final[dict[str, str]] = {
    "multi_goal_rrtstar": "RRTstar",
    "multi_goal_bitstar": "BITstar",
    "multi_goal_fmt": "FMT",
    "multi_goal_kpiece1": "KPIECE1",
    "multi_goal_prm": "PRM",
}

ProbeRunner = Callable[[FeatureSpec], Mapping[str, Any]]


def _row(
    feature_id: str,
    status: str,
    *,
    detail: str,
    elapsed_s: float,
    required: bool,
) -> dict[str, Any]:
    if status not in STATUSES:
        raise ValueError(f"unknown capability status {status!r}")
    return {
        "feature_id": feature_id,
        "status": status,
        "detail": detail,
        "elapsed_s": float(elapsed_s),
        "required": required,
    }


def _status_for_exception(exc: BaseException) -> str:
    if isinstance(exc, TimeoutError):
        return STATUS_CHILD_TIMEOUT
    if isinstance(exc, AttributeError):
        return STATUS_MISSING_SYMBOL
    module = type(exc).__module__ or ""
    if module.startswith("ompl"):
        return STATUS_BINDING_EXCEPTION
    return STATUS_CRASHED


def injected_hang_probe() -> dict[str, Any]:
    """Test helper: block until the parent kill timeout fires."""
    time.sleep(3600.0)
    return {"status": STATUS_SUPPORTED, "detail": "unexpected wake"}


def injected_crash_probe() -> dict[str, Any]:
    """Test helper: raise in the child process."""
    raise RuntimeError("injected probe crash")


def _call_target(target: Callable[[], Any], queue: Queue[Any]) -> None:
    try:
        payload = target()
        queue.put(("ok", payload))
    except Exception as exc:
        queue.put(
            (
                "err",
                _status_for_exception(exc),
                f"{type(exc).__name__}: {exc}",
            )
        )


def run_isolated_probe(
    target: Callable[[], Any],
    *,
    timeout_s: float,
) -> dict[str, Any]:
    """Run ``target`` in a spawn child and type hangs, crashes, and returns.

    Parameters
    ----------
    target :
        Importable zero-argument callable. Return a mapping with ``status``
        and ``detail``, or any JSON-friendly payload (treated as supported).
    timeout_s :
        Join timeout. The child is terminated, then killed, if it outlives
        this bound.

    Returns
    -------
    dict
        ``status``, ``detail``, and ``elapsed_s``.
    """
    ctx = get_context("spawn")
    queue: Queue[Any] = ctx.Queue()
    proc = ctx.Process(target=_call_target, args=(target, queue))
    started = time.perf_counter()
    proc.start()
    proc.join(timeout_s)
    elapsed = time.perf_counter() - started
    if proc.is_alive():
        proc.terminate()
        proc.join(1.0)
        if proc.is_alive():
            proc.kill()
            proc.join(1.0)
        return {
            "status": STATUS_CHILD_TIMEOUT,
            "detail": f"child exceeded {timeout_s:.3f}s",
            "elapsed_s": elapsed,
        }
    if not queue.empty():
        message = queue.get_nowait()
        if message[0] == "ok":
            payload = message[1]
            if isinstance(payload, Mapping) and "status" in payload:
                status = str(payload["status"])
                if status not in STATUSES:
                    status = STATUS_CRASHED
                return {
                    "status": status,
                    "detail": str(payload.get("detail", "")),
                    "elapsed_s": elapsed,
                }
            return {
                "status": STATUS_SUPPORTED,
                "detail": repr(payload),
                "elapsed_s": elapsed,
            }
        return {
            "status": str(message[1]),
            "detail": str(message[2]),
            "elapsed_s": elapsed,
        }
    exitcode = proc.exitcode
    if exitcode not in (0, None):
        return {
            "status": STATUS_CRASHED,
            "detail": f"child exit code {exitcode}",
            "elapsed_s": elapsed,
        }
    return {
        "status": STATUS_CRASHED,
        "detail": "child returned no payload",
        "elapsed_s": elapsed,
    }


def _tiny_space_information(ob: Any) -> tuple[Any, Any]:
    space = ob.RealVectorStateSpace(1)
    bounds = ob.RealVectorBounds(1)
    bounds.setLow(-1.0)
    bounds.setHigh(1.0)
    space.setBounds(bounds)
    si = ob.SpaceInformation(space)
    if hasattr(ob, "StateValidityCheckerFn"):
        si.setStateValidityChecker(ob.StateValidityCheckerFn(lambda _state: True))
    si.setup()
    return space, si


def _assign_u(state: Any, value: float) -> None:
    try:
        state[0] = float(value)
        return
    except Exception:
        pass
    try:
        state[0] = float(value)
    except Exception as exc:
        raise RuntimeError("cannot write 1-D RealVector state") from exc


def _construct_planner(og: Any, si: Any, class_name: str) -> Any:
    cls = getattr(og, class_name, None)
    if cls is None:
        raise AttributeError(f"ompl.geometric.{class_name}")
    return cls(si)


def _probe_construct(class_name: str) -> dict[str, Any]:
    import ompl.base as ob  # type: ignore[import-not-found, unused-ignore]
    import ompl.geometric as og  # type: ignore[import-not-found, unused-ignore]

    _space, si = _tiny_space_information(ob)
    planner = _construct_planner(og, si, class_name)
    return {
        "status": STATUS_SUPPORTED,
        "detail": type(planner).__name__,
    }


def _probe_methods(class_name: str, methods: Sequence[str]) -> dict[str, Any]:
    import ompl.base as ob  # type: ignore[import-not-found, unused-ignore]
    import ompl.geometric as og  # type: ignore[import-not-found, unused-ignore]

    _space, si = _tiny_space_information(ob)
    planner = _construct_planner(og, si, class_name)
    missing = [name for name in methods if not hasattr(planner, name)]
    if missing:
        return {
            "status": STATUS_MISSING_SYMBOL,
            "detail": "missing " + ", ".join(missing),
        }
    return {
        "status": STATUS_SUPPORTED,
        "detail": ", ".join(methods),
    }


def _probe_multi_goal(class_name: str) -> dict[str, Any]:
    import ompl.base as ob  # type: ignore[import-not-found, unused-ignore]
    import ompl.geometric as og  # type: ignore[import-not-found, unused-ignore]

    space, si = _tiny_space_information(ob)
    planner = _construct_planner(og, si, class_name)
    pdef = ob.ProblemDefinition(si)
    start = space.allocState()
    _assign_u(start, -0.8)
    pdef.addStartState(start)
    goal = ob.GoalStates(si)
    g1 = space.allocState()
    g2 = space.allocState()
    _assign_u(g1, -0.2)
    _assign_u(g2, 0.6)
    goal.addState(g1)
    goal.addState(g2)
    pdef.setGoal(goal)
    planner.setProblemDefinition(pdef)
    planner.setup()
    solved = bool(planner.solve(0.15))
    n_goals = int(goal.getStateCount()) if hasattr(goal, "getStateCount") else 2
    if n_goals < 2:
        return {
            "status": STATUS_UNSUPPORTED,
            "detail": f"GoalStates count {n_goals}",
        }
    return {
        "status": STATUS_SUPPORTED,
        "detail": f"solved={solved} n_goals={n_goals}",
    }


def _probe_repeated_solve() -> dict[str, Any]:
    import ompl.base as ob  # type: ignore[import-not-found, unused-ignore]
    import ompl.geometric as og  # type: ignore[import-not-found, unused-ignore]

    space, si = _tiny_space_information(ob)
    planner = _construct_planner(og, si, "RRTConnect")
    pdef = ob.ProblemDefinition(si)
    start = space.allocState()
    goal_state = space.allocState()
    _assign_u(start, -0.5)
    _assign_u(goal_state, 0.5)
    pdef.addStartState(start)
    pdef.setGoalState(goal_state)
    planner.setProblemDefinition(pdef)
    planner.setup()
    first = bool(planner.solve(0.05))
    second = bool(planner.solve(0.05))
    return {
        "status": STATUS_SUPPORTED,
        "detail": f"first={first} second={second}",
    }


def _make_identity_projection(ob: Any, space: Any) -> Any:
    class _IdentityProjection(ob.ProjectionEvaluator):  # type: ignore[misc]
        def getDimension(self) -> int:  # noqa: N802
            return 1

        def project(self, state: Any, projection: Any) -> None:
            projection[0] = float(state[0])

    return _IdentityProjection(space)


def _probe_projection_evaluator() -> dict[str, Any]:
    import ompl.base as ob  # type: ignore[import-not-found, unused-ignore]

    space, _si = _tiny_space_information(ob)
    if not hasattr(ob, "ProjectionEvaluator"):
        return {
            "status": STATUS_MISSING_SYMBOL,
            "detail": "ompl.base.ProjectionEvaluator",
        }
    evaluator = _make_identity_projection(ob, space)
    dim = int(evaluator.getDimension()) if hasattr(evaluator, "getDimension") else 0
    if dim != 1:
        return {
            "status": STATUS_UNSUPPORTED,
            "detail": f"projection dimension {dim}",
        }
    return {
        "status": STATUS_SUPPORTED,
        "detail": type(evaluator).__name__,
    }


def _probe_projection_cell_sizes() -> dict[str, Any]:
    import ompl.base as ob  # type: ignore[import-not-found, unused-ignore]

    space, _si = _tiny_space_information(ob)
    if not hasattr(ob, "ProjectionEvaluator"):
        return {
            "status": STATUS_MISSING_SYMBOL,
            "detail": "ompl.base.ProjectionEvaluator",
        }
    evaluator = _make_identity_projection(ob, space)
    from inequality_mechanisms.adapters.ompl.binding import apply_projection_cell_sizes

    record = apply_projection_cell_sizes(evaluator, [0.25])
    return {
        "status": STATUS_SUPPORTED,
        "detail": f"{record['method']}:{record['signature']}",
    }


def _probe_planner_data() -> dict[str, Any]:
    import ompl.base as ob  # type: ignore[import-not-found, unused-ignore]
    import ompl.geometric as og  # type: ignore[import-not-found, unused-ignore]

    _space, si = _tiny_space_information(ob)
    planner = _construct_planner(og, si, "RRTConnect")
    if not hasattr(planner, "getPlannerData"):
        return {
            "status": STATUS_MISSING_SYMBOL,
            "detail": "getPlannerData",
        }
    if not hasattr(ob, "PlannerData"):
        return {
            "status": STATUS_MISSING_SYMBOL,
            "detail": "ompl.base.PlannerData",
        }
    data = ob.PlannerData(si)
    planner.getPlannerData(data)
    n_vertices = int(data.numVertices()) if hasattr(data, "numVertices") else -1
    return {
        "status": STATUS_SUPPORTED,
        "detail": f"numVertices={n_vertices}",
    }


def _probe_sampler_allocator() -> dict[str, Any]:
    import ompl.base as ob  # type: ignore[import-not-found, unused-ignore]

    space, _si = _tiny_space_information(ob)
    if not hasattr(space, "setStateSamplerAllocator"):
        return {
            "status": STATUS_MISSING_SYMBOL,
            "detail": "setStateSamplerAllocator",
        }
    return {
        "status": STATUS_SUPPORTED,
        "detail": "setStateSamplerAllocator",
    }


def _probe_sampler_precomputed() -> dict[str, Any]:
    import ompl.base as ob  # type: ignore[import-not-found, unused-ignore]

    names = (
        "PrecomputedStateSampler",
        "PrecomputedSampler",
        "CachedStateSampler",
    )
    present = [name for name in names if hasattr(ob, name)]
    if not present:
        return {
            "status": STATUS_UNSUPPORTED,
            "detail": "no precomputed sampler class",
        }
    return {
        "status": STATUS_SUPPORTED,
        "detail": ", ".join(present),
    }


def _probe_sampler_deterministic() -> dict[str, Any]:
    import ompl.util as ou  # type: ignore[import-not-found, unused-ignore]

    rng = getattr(ou, "RNG", None)
    if rng is None or not hasattr(rng, "setSeed"):
        return {
            "status": STATUS_UNSUPPORTED,
            "detail": "ompl.util.RNG.setSeed",
        }
    return {
        "status": STATUS_SUPPORTED,
        "detail": "RNG.setSeed",
    }


def _probe_exact_solution_api() -> dict[str, Any]:
    import ompl.base as ob  # type: ignore[import-not-found, unused-ignore]

    _space, si = _tiny_space_information(ob)
    pdef = ob.ProblemDefinition(si)
    has_solution = hasattr(pdef, "hasSolution")
    has_exact = hasattr(pdef, "hasExactSolution")
    if not has_solution:
        return {
            "status": STATUS_MISSING_SYMBOL,
            "detail": "hasSolution",
        }
    if not has_exact:
        return {
            "status": STATUS_MISSING_SYMBOL,
            "detail": "hasExactSolution",
        }
    return {
        "status": STATUS_SUPPORTED,
        "detail": "hasSolution,hasExactSolution",
    }


def _execute_ompl_feature(feature_id: str) -> dict[str, Any]:
    if feature_id in _PLANNER_CLASSES:
        return _probe_construct(_PLANNER_CLASSES[feature_id])
    if feature_id in _PLANNER_METHODS:
        class_name, methods = _PLANNER_METHODS[feature_id]
        return _probe_methods(class_name, methods)
    if feature_id in _MULTI_GOAL_PLANNERS:
        return _probe_multi_goal(_MULTI_GOAL_PLANNERS[feature_id])
    dispatch = {
        "repeated_solve": _probe_repeated_solve,
        "projection_evaluator": _probe_projection_evaluator,
        "projection_cell_sizes": _probe_projection_cell_sizes,
        "planner_data": _probe_planner_data,
        "sampler_allocator": _probe_sampler_allocator,
        "sampler_precomputed": _probe_sampler_precomputed,
        "sampler_deterministic": _probe_sampler_deterministic,
        "exact_solution_api": _probe_exact_solution_api,
    }
    probe = dispatch.get(feature_id)
    if probe is None:
        return {
            "status": STATUS_UNSUPPORTED,
            "detail": f"unknown feature {feature_id}",
        }
    return probe()


class _SpawnFeature:
    """Picklable zero-arg callable that runs one catalog probe in the child."""

    __slots__ = ("feature_id",)

    def __init__(self, feature_id: str) -> None:
        self.feature_id = feature_id

    def __call__(self) -> dict[str, Any]:
        return _execute_ompl_feature(self.feature_id)


def _default_runner(spec: FeatureSpec) -> Mapping[str, Any]:
    return run_isolated_probe(
        _SpawnFeature(spec.feature_id),
        timeout_s=spec.timeout_s,
    )


def probe_ompl_capabilities(
    *,
    ompl_available: bool | None = None,
    probe_runner: ProbeRunner | None = None,
) -> dict[str, Any]:
    """Return the frozen V4-231 capability matrix.

    Parameters
    ----------
    ompl_available :
        Override the parent-side availability gate. ``None`` uses
        :func:`is_ompl_available`. When false, every catalog row is
        ``unavailable_dependency`` and no children are spawned.
    probe_runner :
        Optional per-feature runner. Tests inject hang/crash runners here.
        The default spawn-isolates :func:`_execute_ompl_feature`.

    Returns
    -------
    dict
        Schema version, availability, version string, catalog, and rows.
    """
    available = is_ompl_available() if ompl_available is None else bool(ompl_available)
    version = ompl_version_string() if available else None
    runner = probe_runner if probe_runner is not None else _default_runner
    rows: list[dict[str, Any]] = []
    for spec in FEATURE_SPECS:
        started = time.perf_counter()
        if not available:
            rows.append(
                _row(
                    spec.feature_id,
                    STATUS_UNAVAILABLE_DEPENDENCY,
                    detail="OMPL Python bindings are not importable",
                    elapsed_s=time.perf_counter() - started,
                    required=spec.required,
                )
            )
            continue
        try:
            payload = dict(runner(spec))
        except Exception as exc:
            rows.append(
                _row(
                    spec.feature_id,
                    _status_for_exception(exc),
                    detail=f"{type(exc).__name__}: {exc}",
                    elapsed_s=time.perf_counter() - started,
                    required=spec.required,
                )
            )
            continue
        status = str(payload.get("status", STATUS_CRASHED))
        if status not in STATUSES:
            status = STATUS_CRASHED
        elapsed = payload.get("elapsed_s", time.perf_counter() - started)
        rows.append(
            _row(
                spec.feature_id,
                status,
                detail=str(payload.get("detail", "")),
                elapsed_s=float(elapsed),
                required=spec.required,
            )
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "ompl_available": available,
        "ompl_version": version,
        "catalog": list(FEATURE_IDS),
        "required_feature_ids": list(REQUIRED_FEATURE_IDS),
        "optional_feature_ids": list(OPTIONAL_FEATURE_IDS),
        "rows": rows,
    }


def required_rows_complete(matrix: Mapping[str, Any]) -> bool:
    """Return True when every required catalog id has a typed row."""
    by_id = {row["feature_id"]: row for row in matrix.get("rows", [])}
    return all(
        feature_id in by_id and by_id[feature_id]["status"] in STATUSES
        for feature_id in REQUIRED_FEATURE_IDS
    )


__all__ = [
    "DEFAULT_TIMEOUT_S",
    "FEATURE_IDS",
    "FEATURE_SPECS",
    "MULTI_GOAL_TIMEOUT_S",
    "OPTIONAL_FEATURE_IDS",
    "REQUIRED_FEATURE_IDS",
    "SCHEMA_VERSION",
    "STATUSES",
    "STATUS_BINDING_EXCEPTION",
    "STATUS_CHILD_TIMEOUT",
    "STATUS_CRASHED",
    "STATUS_MISSING_SYMBOL",
    "STATUS_SUPPORTED",
    "STATUS_UNAVAILABLE_DEPENDENCY",
    "STATUS_UNSUPPORTED",
    "FeatureSpec",
    "injected_crash_probe",
    "injected_hang_probe",
    "probe_ompl_capabilities",
    "required_rows_complete",
    "run_isolated_probe",
]
