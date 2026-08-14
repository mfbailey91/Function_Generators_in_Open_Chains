"""Native PRM/RRT trace geometry for synchronized U/Q/X panels (V3-635).

Parse opt-in planner trace events into vertices and edges, then reconstruct
displayed polylines through the declared connector. U is authoritative; Q and X
are projections of the same edge set. Failed connects never fall back to silent
endpoint chords.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

import numpy as np
from numpy.typing import NDArray

from inequality_mechanisms.audits.trajectory_evaluation import (
    TrajectorySegmentEvaluation,
    evaluate_trajectory_segment,
)
from inequality_mechanisms.core.local_motion import LocalMotionModel
from inequality_mechanisms.core.robot import RobotModel
from inequality_mechanisms.core.scene import PlanningScene
from inequality_mechanisms.core.state import PhysicalState


@dataclass(frozen=True, slots=True)
class TraceVertex:
    """One reconstructable roadmap/tree vertex."""

    key: str
    u: NDArray[np.float64]
    q: NDArray[np.float64]
    tree: str | None = None
    meta: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TraceEdge:
    """One reconstructable edge with endpoint states (no sample polylines)."""

    key: str
    kind: str
    start: PhysicalState
    end: PhysicalState
    meta: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TraceGeometry:
    """Parsed vertices/edges from a planner trace event stream."""

    family: str
    vertices: tuple[TraceVertex, ...]
    edges: tuple[TraceEdge, ...]
    expansion_keys: tuple[str, ...] = ()
    final_node_keys: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ReconstructedEdgeSamples:
    """Connector samples for one displayed edge, or a fail-closed skip."""

    edge: TraceEdge
    segment: TrajectorySegmentEvaluation
    sample_u: NDArray[np.float64] | None
    sample_q: NDArray[np.float64] | None
    sample_x: NDArray[np.float64] | None
    drawn: bool


def _arr(value: Any) -> NDArray[np.float64] | None:
    if value is None:
        return None
    a = np.asarray(value, dtype=np.float64)
    if a.ndim != 1 or a.size < 1 or not np.all(np.isfinite(a)):
        return None
    return a


def _state_from_uq(
    u: Any,
    q: Any,
    *,
    assembly: Mapping[str, Any] | None = None,
) -> PhysicalState | None:
    u_a = _arr(u)
    q_a = _arr(q)
    if u_a is None or q_a is None:
        return None
    return PhysicalState(u=u_a, q=q_a, assembly_state=dict(assembly or {}))


def _vertex(
    key: str,
    u: Any,
    q: Any,
    *,
    tree: str | None = None,
    meta: Mapping[str, Any] | None = None,
) -> TraceVertex | None:
    u_a = _arr(u)
    q_a = _arr(q)
    if u_a is None or q_a is None:
        return None
    return TraceVertex(
        key=key,
        u=u_a,
        q=q_a,
        tree=tree,
        meta=dict(meta or {}),
    )


def _edge(
    key: str,
    kind: str,
    start: PhysicalState | None,
    end: PhysicalState | None,
    *,
    meta: Mapping[str, Any] | None = None,
) -> TraceEdge | None:
    if start is None or end is None:
        return None
    return TraceEdge(
        key=key,
        kind=kind,
        start=start,
        end=end,
        meta=dict(meta or {}),
    )


def extract_prm_geometry(events: Sequence[Mapping[str, Any]]) -> TraceGeometry:
    """Build PRM vertices/edges from enriched audit events."""
    verts: dict[str, TraceVertex] = {}
    edges: list[TraceEdge] = []
    expansion_keys: list[str] = []
    final_keys: list[str] = []

    for ev in events:
        et = str(ev.get("event_type", ""))
        payload = dict(ev.get("payload") or {})
        if et in ("sample_accept", "sample_reject"):
            if not payload.get("accepted", et == "sample_accept"):
                continue
            key = f"sample:{int(payload['index'])}"
            v = _vertex(key, payload.get("u"), payload.get("q"), meta={"index": payload.get("index")})
            if v is not None:
                verts[key] = v
        elif et == "edge_accept":
            i = int(payload["i"])
            j = int(payload["j"])
            ki, kj = f"sample:{i}", f"sample:{j}"
            for key, u_key, q_key in (
                (ki, "u_i", "q_i"),
                (kj, "u_j", "q_j"),
            ):
                if key not in verts:
                    v = _vertex(key, payload.get(u_key), payload.get(q_key))
                    if v is not None:
                        verts[key] = v
            e = _edge(
                f"edge:{i}:{j}",
                "construction",
                _state_from_uq(payload.get("u_i"), payload.get("q_i")),
                _state_from_uq(payload.get("u_j"), payload.get("q_j")),
                meta={"i": i, "j": j},
            )
            if e is not None:
                edges.append(e)
        elif et == "attach_edge":
            src = int(payload["src"])
            dst = int(payload["dst"])
            ks, kd = f"node:{src}", f"node:{dst}"
            for key, u_key, q_key, idx in (
                (ks, "u_src", "q_src", src),
                (kd, "u_dst", "q_dst", dst),
            ):
                if key not in verts:
                    v = _vertex(
                        key,
                        payload.get(u_key),
                        payload.get(q_key),
                        meta={"node": idx},
                    )
                    if v is not None:
                        verts[key] = v
            e = _edge(
                f"attach:{src}:{dst}",
                "attach",
                _state_from_uq(payload.get("u_src"), payload.get("q_src")),
                _state_from_uq(payload.get("u_dst"), payload.get("q_dst")),
                meta={"src": src, "dst": dst},
            )
            if e is not None:
                edges.append(e)
        elif et == "query_attach":
            start_idx = payload.get("start_idx")
            if start_idx is not None:
                key = f"node:{int(start_idx)}"
                v = _vertex(
                    key,
                    payload.get("start_u"),
                    payload.get("start_q"),
                    meta={"role": "start", "node": int(start_idx)},
                )
                if v is not None:
                    verts[key] = v
            goals_u = list(payload.get("goals_u") or [])
            goals_q = list(payload.get("goals_q") or [])
            goal_indices = list(payload.get("goal_indices") or [])
            for gi, (gu, gq) in zip(goal_indices, zip(goals_u, goals_q)):
                key = f"node:{int(gi)}"
                v = _vertex(
                    key,
                    gu,
                    gq,
                    meta={"role": "goal", "node": int(gi)},
                )
                if v is not None:
                    verts[key] = v
        elif et == "dijkstra_expand":
            node = int(payload["node"])
            key = f"node:{node}"
            sample_key = f"sample:{node}"
            if key not in verts and sample_key not in verts:
                v = _vertex(
                    key,
                    payload.get("u"),
                    payload.get("q"),
                    meta={"node": node, "order": payload.get("order")},
                )
                if v is not None:
                    verts[key] = v
            if key in verts:
                expansion_keys.append(key)
            elif sample_key in verts:
                expansion_keys.append(sample_key)
        elif et == "final_path":
            path_u = list(payload.get("u") or [])
            path_q = list(payload.get("q") or [])
            node_ids = list(payload.get("node_ids") or [])
            for nid, uu, qq in zip(node_ids, path_u, path_q):
                node = int(nid)
                key = f"node:{node}"
                sample_key = f"sample:{node}"
                if key not in verts and sample_key not in verts:
                    v = _vertex(key, uu, qq, meta={"node": node})
                    if v is not None:
                        verts[key] = v
                if key in verts:
                    final_keys.append(key)
                elif sample_key in verts:
                    final_keys.append(sample_key)
                else:
                    final_keys.append(key)

    seen: set[str] = set()
    expansion_unique: list[str] = []
    for k in expansion_keys:
        if k in seen:
            continue
        seen.add(k)
        expansion_unique.append(k)

    return TraceGeometry(
        family="roadmap",
        vertices=tuple(verts.values()),
        edges=tuple(edges),
        expansion_keys=tuple(expansion_unique),
        final_node_keys=tuple(final_keys),
    )


def extract_rrt_geometry(events: Sequence[Mapping[str, Any]]) -> TraceGeometry:
    """Build RRTConnect vertices/parent edges from enriched audit events."""
    verts: dict[str, TraceVertex] = {}
    edges: list[TraceEdge] = []
    final_keys: list[str] = []

    for ev in events:
        et = str(ev.get("event_type", ""))
        payload = dict(ev.get("payload") or {})
        if et == "vertex_insert":
            tree = str(payload.get("tree", "start"))
            index = int(payload["index"])
            key = f"{tree}:{index}"
            v = _vertex(
                key,
                payload.get("u"),
                payload.get("q"),
                tree=tree,
                meta={
                    "index": index,
                    "parent": payload.get("parent"),
                    "goal_root_index": payload.get("goal_root_index"),
                    "provenance": payload.get("provenance"),
                },
            )
            if v is not None:
                verts[key] = v
            parent = payload.get("parent")
            if parent is not None:
                parent_key = f"{tree}:{int(parent)}"
                start = _state_from_uq(
                    payload.get("parent_u"),
                    payload.get("parent_q"),
                )
                if start is None and parent_key in verts:
                    pv = verts[parent_key]
                    start = PhysicalState(u=pv.u, q=pv.q)
                end = _state_from_uq(payload.get("u"), payload.get("q"))
                e = _edge(
                    f"parent:{tree}:{parent}:{index}",
                    "tree_parent",
                    start,
                    end,
                    meta={"tree": tree, "parent": int(parent), "child": index},
                )
                if e is not None:
                    edges.append(e)
        elif et == "final_path":
            path_u = list(payload.get("u") or [])
            path_q = list(payload.get("q") or [])
            for i, (uu, qq) in enumerate(zip(path_u, path_q)):
                key = f"path:{i}"
                v = _vertex(key, uu, qq, meta={"path_index": i})
                if v is not None:
                    verts[key] = v
                    final_keys.append(key)

    return TraceGeometry(
        family="tree",
        vertices=tuple(verts.values()),
        edges=tuple(edges),
        expansion_keys=(),
        final_node_keys=tuple(final_keys),
    )


def extract_trace_geometry(
    events: Sequence[Mapping[str, Any]],
    *,
    planner: str,
) -> TraceGeometry:
    """Dispatch PRM vs RRTConnect geometry extraction."""
    if planner == "prm":
        return extract_prm_geometry(events)
    if planner == "rrt_connect":
        return extract_rrt_geometry(events)
    raise ValueError(f"unsupported planner for native trace geometry: {planner!r}")


def reconstruct_edge_samples(
    edges: Sequence[TraceEdge],
    *,
    connector: LocalMotionModel,
    robot: RobotModel,
    scene: PlanningScene | None = None,
) -> list[ReconstructedEdgeSamples]:
    """Reconstruct connector samples for each edge; skip invalid connects."""
    out: list[ReconstructedEdgeSamples] = []
    for edge in edges:
        seg = evaluate_trajectory_segment(
            edge.start,
            edge.end,
            connector=connector,
            robot=robot,
            scene=scene,
        )
        drawn = bool(seg.valid and seg.sample_u is not None and seg.sample_q is not None)
        out.append(
            ReconstructedEdgeSamples(
                edge=edge,
                segment=seg,
                sample_u=seg.sample_u if drawn else None,
                sample_q=seg.sample_q if drawn else None,
                sample_x=seg.sample_x if drawn else None,
                drawn=drawn,
            )
        )
    return out


def final_path_samples_from_cte(
    planner_metrics: Mapping[str, Any] | None,
) -> tuple[NDArray[np.float64] | None, NDArray[np.float64] | None, NDArray[np.float64] | None]:
    """Concatenate packed CTE segment samples for the final path overlay.

    Returns ``(None, None, None)`` when CTE is absent or incomplete. Never
    invents waypoint chords.
    """
    if not planner_metrics:
        return None, None, None
    cte = planner_metrics.get("continuous_trajectory")
    if not isinstance(cte, Mapping):
        return None, None, None
    segments = list(cte.get("segments") or [])
    if not segments:
        return None, None, None
    us: list[NDArray[np.float64]] = []
    qs: list[NDArray[np.float64]] = []
    xs: list[NDArray[np.float64]] = []
    have_x = True
    for i, seg in enumerate(segments):
        if not seg.get("valid"):
            return None, None, None
        su = _arr_2d(seg.get("sample_u"))
        sq = _arr_2d(seg.get("sample_q"))
        if su is None or sq is None:
            return None, None, None
        if i == 0:
            us.append(su)
            qs.append(sq)
        else:
            us.append(su[1:])
            qs.append(sq[1:])
        sx = _arr_2d(seg.get("sample_x"))
        if sx is None:
            have_x = False
        elif i == 0:
            xs.append(sx)
        else:
            xs.append(sx[1:])
    sample_u = np.vstack(us) if us else None
    sample_q = np.vstack(qs) if qs else None
    sample_x = np.vstack(xs) if have_x and xs else None
    return sample_u, sample_q, sample_x


def _arr_2d(value: Any) -> NDArray[np.float64] | None:
    if value is None:
        return None
    a = np.asarray(value, dtype=np.float64)
    if a.ndim != 2 or a.shape[0] < 2 or not np.all(np.isfinite(a)):
        return None
    return a


def growth_events(
    events: Sequence[Mapping[str, Any]],
    *,
    planner: str,
) -> list[Mapping[str, Any]]:
    """Ordered construction/growth events used for animations."""
    if planner == "prm":
        kinds = {"sample_accept", "edge_accept", "attach_edge"}
    else:
        kinds = {"vertex_insert"}
    return [e for e in events if e.get("event_type") in kinds]


__all__ = [
    "ReconstructedEdgeSamples",
    "TraceEdge",
    "TraceGeometry",
    "TraceVertex",
    "extract_prm_geometry",
    "extract_rrt_geometry",
    "extract_trace_geometry",
    "final_path_samples_from_cte",
    "growth_events",
    "reconstruct_edge_samples",
]
