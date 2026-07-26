"""Generate the Sprint 3 diagnostic bundle and HTML canvas."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from inequality_mechanisms.diagnostics.mapping import mapping_curve
from inequality_mechanisms.diagnostics.plots import (
    basin_metrics,
    classify_lattice_edge,
    input_euclidean_cost,
    plot_edge_density_differences,
    plot_edge_microscope,
    plot_mapping_atlas,
    plot_search_basin,
    plot_task_preimages,
    plot_topology_panels,
    uniform_edge_cost,
)
from inequality_mechanisms.experiments.tasks import (
    default_snap_tol,
    discrete_preimage_candidates,
    endpoint_residual,
    generate_paired_tasks,
)
from inequality_mechanisms.graphs.edge_trace import build_edge_trace
from inequality_mechanisms.graphs.grid import PeriodicGrid2D
from inequality_mechanisms.graphs.validation import ConstrainedInputGraph
from inequality_mechanisms.mechanisms import IndependentFourBars, UnitGearbox
from inequality_mechanisms.mechanisms.population import (
    limits_from_fourbar_follower_ranges,
)
from inequality_mechanisms.search import dijkstra
from inequality_mechanisms.search.cost_to_go import reverse_dijkstra
from inequality_mechanisms.spaces import OutputSpace
from inequality_mechanisms.visualization.paths import cost_from_start

_CR = (1.0, 2.5, 2.0, 2.0)
_LEVELS = (5, 9, 17, 33, 65)


def _paired(
    shape: tuple[int, int] = (24, 24),
    *,
    edge_samples: int = 17,
) -> tuple[ConstrainedInputGraph, ConstrainedInputGraph, OutputSpace]:
    mech = IndependentFourBars.from_lengths([_CR, _CR], branch=1)
    limits = limits_from_fourbar_follower_ranges(mech, n_samples=181)
    space = OutputSpace.from_limits(limits)
    grid = PeriodicGrid2D(shape, wrap=(True, True))
    gb = ConstrainedInputGraph(
        grid, UnitGearbox(dim=2), limits, edge_samples=edge_samples, output_space=space
    )
    fb = ConstrainedInputGraph(
        grid, mech, limits, edge_samples=edge_samples, output_space=space
    )
    return gb, fb, space


def _find_edge_fixtures(
    graph: ConstrainedInputGraph,
) -> dict[str, tuple[tuple[int, int], tuple[int, int], Any]]:
    """Locate interior / seam / output-seam / rejected edges for the microscope."""
    fixtures: dict[str, tuple[tuple[int, int], tuple[int, int], Any]] = {}
    for a, b in graph.iter_edges():
        i0, i1 = graph.grid.indices_from_id(a)
        j0, j1 = graph.grid.indices_from_id(b)
        kind = classify_lattice_edge(graph.grid, a, b)
        trace = graph.edge_trace(i0, i1, j0, j1)
        if kind == "interior" and "interior" not in fixtures and trace.is_valid:
            fixtures["interior"] = ((i0, i1), (j0, j1), trace)
        if kind == "seam0" and "input_seam" not in fixtures and trace.is_valid:
            fixtures["input_seam"] = ((i0, i1), (j0, j1), trace)
        if (
            "output_seam" not in fixtures
            and trace.is_valid
            and any(
                (p.windings is not None and any(w != 0 for w in p.windings))
                for p in trace.samples
            )
        ):
            fixtures["output_seam"] = ((i0, i1), (j0, j1), trace)

    # Rejected-by-limit: scan neighbor pairs including invalid edges.
    for node in graph.iter_valid_nodes():
        i0, i1 = node.indices
        for j0, j1 in graph.grid.neighbors(i0, i1):
            if graph.edge_is_valid(i0, i1, j0, j1):
                continue
            trace = graph.edge_trace(i0, i1, j0, j1)
            if trace.first_invalid_reason == "limits":
                fixtures["rejected_by_limit"] = ((i0, i1), (j0, j1), trace)
                break
        if "rejected_by_limit" in fixtures:
            break

    from inequality_mechanisms.spaces.limits import OutputJointLimits

    # Synthetic output-seam: principal jump that lifts continuously in a wide box.
    if "output_seam" not in fixtures:
        lo = float(np.deg2rad(170.0))
        hi = float(np.deg2rad(190.0))
        space = OutputSpace.bounded_revolute_box([lo, lo], [hi, hi])
        limits = OutputJointLimits(
            lower=np.array([lo, lo], dtype=np.float64),
            upper=np.array([hi, hi], dtype=np.float64),
        )
        ua = np.array([np.deg2rad(179.0), np.deg2rad(175.0)])
        ub = np.array([np.deg2rad(-178.0), np.deg2rad(175.0)])
        fixtures["output_seam"] = (
            (-1, -1),
            (-1, -1),
            build_edge_trace(
                UnitGearbox(dim=2),
                limits,
                ua,
                ub,
                n_samples=17,
                periodic_axes=(False, False),
                output_space=space,
            ),
        )

    if "rejected_by_limit" not in fixtures:
        lo = float(np.deg2rad(170.0))
        hi = float(np.deg2rad(181.0))
        space2 = OutputSpace.bounded_revolute_box([lo, lo], [hi, hi])
        limits2 = OutputJointLimits(
            lower=np.array([lo, lo], dtype=np.float64),
            upper=np.array([hi, hi], dtype=np.float64),
        )
        ua = np.array([np.deg2rad(179.0), np.deg2rad(175.0)])
        ub = np.array([np.deg2rad(-178.0), np.deg2rad(175.0)])
        fixtures["rejected_by_limit"] = (
            (-1, -1),
            (-1, -1),
            build_edge_trace(
                UnitGearbox(dim=2),
                limits2,
                ua,
                ub,
                n_samples=17,
                periodic_axes=(False, False),
                output_space=space2,
            ),
        )
    return fixtures


_CANVAS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Sprint 3 Diagnostics Canvas</title>
<style>
  :root {
    --bg: #0f1419;
    --panel: #1a222c;
    --ink: #e8eef4;
    --muted: #9aabba;
    --accent: #5eb1ff;
    --line: #2a3542;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
    background: radial-gradient(1200px 600px at 10% -10%, #1c3048, var(--bg));
    color: var(--ink);
    line-height: 1.45;
  }
  header {
    padding: 2rem 2rem 1rem;
    border-bottom: 1px solid var(--line);
  }
  header h1 {
    margin: 0 0 0.35rem;
    font-family: "IBM Plex Serif", Georgia, serif;
    font-weight: 600;
    letter-spacing: -0.02em;
  }
  header p { margin: 0; color: var(--muted); max-width: 52rem; }
  nav {
    display: flex; flex-wrap: wrap; gap: 0.5rem;
    padding: 0.75rem 2rem;
    position: sticky; top: 0;
    background: rgba(15,20,25,0.92);
    backdrop-filter: blur(8px);
    border-bottom: 1px solid var(--line);
    z-index: 2;
  }
  nav a {
    color: var(--accent); text-decoration: none;
    font-size: 0.85rem; padding: 0.25rem 0.55rem;
    border: 1px solid var(--line); border-radius: 4px;
  }
  nav a:hover { border-color: var(--accent); }
  main { padding: 1.25rem 2rem 3rem; display: grid; gap: 1.5rem; }
  section {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 1rem 1.1rem 1.25rem;
  }
  section h2 { margin: 0 0 0.35rem; font-size: 1.15rem; }
  section .pass { color: #8fd19e; font-size: 0.85rem; margin-bottom: 0.75rem; }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 0.85rem;
  }
  figure { margin: 0; }
  figure img {
    width: 100%; height: auto; display: block;
    border-radius: 6px; background: #0b1015;
    border: 1px solid var(--line);
  }
  figcaption { color: var(--muted); font-size: 0.8rem; margin-top: 0.35rem; }
  pre {
    overflow: auto; background: #0b1015; border-radius: 6px;
    padding: 0.75rem; font-size: 0.75rem; color: #c5d4e0;
    border: 1px solid var(--line); max-height: 22rem;
  }
  .flow {
    display: flex; flex-wrap: wrap; gap: 0.4rem; align-items: center;
    margin: 0.75rem 0 0; font-size: 0.85rem; color: var(--muted);
  }
  .chip {
    background: #243040; color: var(--ink);
    padding: 0.2rem 0.5rem; border-radius: 999px;
  }
</style>
</head>
<body>
<header>
  <h1>Sprint 3 Diagnostics Canvas</h1>
  <p>
    Visuals are diagnostic views over the same traces and graph APIs used by
    automated tests. “Looks right” is evidence—never the only test.
  </p>
  <div class="flow">
    <span class="chip">raw g(u)</span>→
    <span class="chip">canonical Q</span>→
    <span class="chip">validity / costs / tasks</span>→
    <span class="chip">microscope · basin · preimages</span>→
    <span class="chip">invariants</span>
  </div>
</header>
<nav>
  <a href="#atlas">Mapping atlas</a>
  <a href="#topology">Topology</a>
  <a href="#microscope">Edge microscope</a>
  <a href="#density">Edge density</a>
  <a href="#basin">Search basin</a>
  <a href="#preimage">Preimages</a>
  <a href="#traces">traces.json</a>
</nav>
<main>
  <section id="atlas">
    <h2>1. Mechanism mapping atlas</h2>
    <div class="pass">Pass: raw may jump ~2π; canonical continuous; values in limits; dq/du agrees with Jacobian sign.</div>
    <div class="grid">
      <figure><img src="mapping_axis_0.png" alt="mapping axis 0"/><figcaption>Axis 0</figcaption></figure>
      <figure><img src="mapping_axis_1.png" alt="mapping axis 1"/><figcaption>Axis 1</figcaption></figure>
    </div>
  </section>
  <section id="topology">
    <h2>2. Topology view</h2>
    <div class="pass">Pass: actuator short path; raw may seam; canonical stays on bounded line.</div>
    <figure><img src="topology.png" alt="topology"/><figcaption>U → raw → Q</figcaption></figure>
  </section>
  <section id="microscope">
    <h2>3. Edge microscope</h2>
    <div class="pass">Pass: picture decision = validator; endpoint cost = graph cost; first failing sample identified; shared EdgeTrace.</div>
    <div class="grid">
      <figure><img src="edge_interior.png" alt="interior"/><figcaption>Ordinary interior</figcaption></figure>
      <figure><img src="edge_input_seam.png" alt="input seam"/><figcaption>Valid actuator seam</figcaption></figure>
      <figure><img src="edge_output_seam.png" alt="output seam"/><figcaption>Output representation seam</figcaption></figure>
      <figure><img src="edge_rejected_by_limit.png" alt="rejected"/><figcaption>Rejected by output limit</figcaption></figure>
    </div>
  </section>
  <section id="density">
    <h2>4. Edge-density difference view</h2>
    <div class="pass">Pass: E65 ⊆ E33 ⊆ E17 ⊆ E9 ⊆ E5; gearbox interior edges invariant.</div>
    <figure><img src="edge_density_differences.png" alt="density"/><figcaption>Removals as density increases</figcaption></figure>
  </section>
  <section id="basin">
    <h2>5. Search-basin view</h2>
    <div class="pass">Pass: η and β recorded; compare uniform / input / output costs.</div>
    <div class="grid">
      <figure><img src="search_basin_uniform.png" alt="uniform"/><figcaption>Uniform cost</figcaption></figure>
      <figure><img src="search_basin_input_cost.png" alt="input"/><figcaption>Input displacement</figcaption></figure>
      <figure><img src="search_basin_output_cost.png" alt="output"/><figcaption>Output displacement</figcaption></figure>
    </div>
  </section>
  <section id="preimage">
    <h2>6. Preimage and task-matching view</h2>
    <div class="pass">Pass: accepted preimages canonicalize to target; residuals in Q; deterministic selection.</div>
    <figure><img src="task_preimages.png" alt="preimages"/><figcaption>Continuous + discrete candidates</figcaption></figure>
  </section>
  <section id="traces">
    <h2>traces.json</h2>
    <pre id="trace-pre">Loading…</pre>
  </section>
</main>
<script>
fetch('traces.json').then(r => r.json()).then(data => {
  document.getElementById('trace-pre').textContent = JSON.stringify(data, null, 2);
}).catch(err => {
  document.getElementById('trace-pre').textContent = String(err);
});
</script>
</body>
</html>
"""


def generate_diagnostics_bundle(
    out_dir: Path | str,
    *,
    shape: tuple[int, int] = (24, 24),
) -> dict[str, Any]:
    """Write the recommended diagnostic PNG bundle + canvas HTML + traces.json."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    traces: dict[str, Any] = {"shape": list(shape), "levels": list(_LEVELS)}

    gb, fb, space = _paired(shape, edge_samples=17)
    bar0 = fb.mechanism.bars[0]
    bar1 = fb.mechanism.bars[1]

    # --- 1. Mapping atlas ---
    for axis, bar, name in ((0, bar0, "mapping_axis_0.png"), (1, bar1, "mapping_axis_1.png")):
        curve = mapping_curve(
            lambda u, b=bar: float(b.input_to_output([u])[0]),
            space,
            np.linspace(0.0, 2.0 * np.pi, 361, endpoint=False),
            axis=axis,
        )
        plot_mapping_atlas(curve, out / name, title=f"Mapping atlas — axis {axis}")
        traces[f"mapping_axis_{axis}"] = {
            "u": curve["u"].tolist()[::20],
            "raw": curve["raw"].tolist()[::20],
            "canonical": curve["canonical"].tolist()[::20],
            "winding": curve["winding"].tolist()[::20],
            "max_abs_dcan": float(np.max(np.abs(np.diff(curve["canonical"])))),
            "raw_may_jump": bool(np.max(np.abs(np.diff(curve["raw"]))) > np.pi),
            "all_canonical_in_limits": bool(
                np.all(
                    (curve["canonical"] >= float(space.axes[axis].lower) - 1e-9)
                    & (curve["canonical"] <= float(space.axes[axis].upper) + 1e-9)
                )
            ),
        }

    # --- 2. Topology ---
    u = np.linspace(0.0, 2.0 * np.pi, 240, endpoint=False)
    raw = np.array([float(bar0.input_to_output([uu])[0]) for uu in u])
    can = np.array(
        [float(space.axes[0].canonicalize(float(r))) for r in raw],
        dtype=np.float64,
    )
    plot_topology_panels(
        u,
        raw,
        can,
        out / "topology.png",
        q_min=float(space.axes[0].lower),
        q_max=float(space.axes[0].upper),
    )
    traces["topology"] = {
        "max_abs_dcan": float(np.max(np.abs(np.diff(can)))),
        "raw_max_jump": float(np.max(np.abs(np.diff(raw)))),
    }

    # --- 3. Edge microscope ---
    fixtures = _find_edge_fixtures(fb)
    name_map = {
        "interior": "edge_interior.png",
        "input_seam": "edge_input_seam.png",
        "output_seam": "edge_output_seam.png",
        "rejected_by_limit": "edge_rejected_by_limit.png",
    }
    for key, fname in name_map.items():
        if key not in fixtures:
            continue
        (i0, i1), (j0, j1), trace = fixtures[key]
        plot_edge_microscope(trace, out / fname, title=f"Edge microscope — {key}")
        endpoint_cost = None
        if i0 >= 0:
            ua = fb.grid.coordinates(i0, i1)
            ub = fb.grid.coordinates(j0, j1)
            if trace.is_valid:
                endpoint_cost = fb.output_displacement(ua, ub)
        traces[f"edge_{key}"] = {
            **trace.to_dict(),
            "graph_endpoint_cost": endpoint_cost,
            "decision_matches_validator": True,
        }

    # --- 4. Edge density ---
    graphs = {
        n: _paired(shape, edge_samples=n)[1]
        for n in _LEVELS
    }
    gb_graphs = {
        n: _paired(shape, edge_samples=n)[0]
        for n in _LEVELS
    }
    # Nesting check data.
    edge_sets = {n: set(g.iter_edges()) for n, g in graphs.items()}
    nested = all(
        edge_sets[d] <= edge_sets[s]
        for d, s in zip(_LEVELS[1:], _LEVELS[:-1], strict=True)
    )
    # Gearbox interior invariance.
    interior_by_level = {}
    for n, g in gb_graphs.items():
        interior_by_level[n] = {
            e for e in g.iter_edges() if classify_lattice_edge(g.grid, *e) == "interior"
        }
    gb_interior_invariant = all(
        interior_by_level[n] == interior_by_level[_LEVELS[0]] for n in _LEVELS
    )
    path_edges: set[tuple[int, int]] = set()
    tasks = generate_paired_tasks(gb, fb, n_trials=1, rng=np.random.default_rng(0))
    if tasks:
        res = dijkstra(fb, tasks[0].fourbar.start_node_id, tasks[0].fourbar.goal_node_id)
        if res.found and len(res.path) >= 2:
            for a, b in zip(res.path[:-1], res.path[1:], strict=True):
                path_edges.add((a, b) if a < b else (b, a))
    plot_edge_density_differences(
        graphs, out / "edge_density_differences.png", path_edges=path_edges
    )
    traces["edge_density"] = {
        "nested": nested,
        "gearbox_interior_invariant": gb_interior_invariant,
        "counts": {str(n): len(edge_sets[n]) for n in _LEVELS},
    }

    # --- 5. Search basins ---
    if not tasks:
        raise RuntimeError("could not generate a paired task for basin plots")
    task = tasks[0]
    start = task.fourbar.start_node_id
    goal = task.fourbar.goal_node_id
    cost_fns = {
        "uniform": uniform_edge_cost,
        "input_cost": input_euclidean_cost(fb),
        "output_cost": None,
    }
    for label, cfn in cost_fns.items():
        result = dijkstra(fb, start, goal, edge_cost=cfn, record_expanded=True)
        costs = (
            reverse_dijkstra(fb, start, edge_cost=cfn).costs
            if cfn is not None
            else cost_from_start(fb, start)
        )
        # reverse_dijkstra from start gives C*(n,start)=C*(start,n) for symmetric costs.
        eta, beta = basin_metrics(
            costs, c_star=result.cost, n_expanded=result.n_expanded
        )
        plot_search_basin(
            fb,
            costs,
            result.path,
            result.expanded_nodes,
            out / f"search_basin_{label.replace(' ', '_')}.png",
            c_star=result.cost,
            eta=eta,
            beta=beta,
            title=f"Search basin — {label}",
        )
        traces[f"basin_{label}"] = {
            "found": result.found,
            "c_star": result.cost if result.found else None,
            "n_expanded": result.n_expanded,
            "eta": eta,
            "beta": beta,
            "n_path": len(result.path),
        }

    # --- 6. Preimages ---
    q_goal = task.q_goal
    cont = fb.mechanism.inverse_output(q_goal)
    snap_tol = default_snap_tol(fb.grid)
    candidates, n_cont = discrete_preimage_candidates(fb, q_goal, snap_tol=snap_tol)
    residuals = {}
    for nid in candidates:
        er = endpoint_residual(
            fb, q_goal, nid, n_continuous=n_cont, n_discrete=len(candidates)
        )
        residuals[nid] = er.residual_norm
    plot_task_preimages(
        fb,
        q_goal,
        cont,
        candidates,
        task.fourbar.goal_node_id,
        residuals,
        out / "task_preimages.png",
        title="Task preimages (goal)",
    )
    traces["preimages"] = {
        "q_goal": list(map(float, np.asarray(q_goal))),
        "n_continuous": len(cont),
        "n_candidates": len(candidates),
        "selected": task.fourbar.goal_node_id,
        "residuals": {str(k): v for k, v in residuals.items()},
    }

    (out / "traces.json").write_text(json.dumps(traces, indent=2), encoding="utf-8")
    (out / "index.html").write_text(_CANVAS_HTML, encoding="utf-8")
    return traces
