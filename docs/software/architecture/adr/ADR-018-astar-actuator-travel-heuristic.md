# ADR-018 — A* heuristic for actuator-travel production campaigns

**Status:** Accepted for Sprint V2.11

## Context

V2.10 used Dijkstra with the `actuator_travel` objective on the shared output
lattice. V2.11 must change only the solver while retaining exact optimality and
the frozen V2.10 scientific basis.

## Decision

A* uses the input-Euclidean heuristic

\[
h(u)=\lVert u-u_g\rVert_2.
\]

The production branch chart is bounded and nonperiodic. Each graph edge is
weighted by Euclidean actuator displacement. By the triangle inequality, the
straight-line actuator displacement to the goal is no greater than the cost of
any graph path to the goal. The heuristic is admissible and consistent.

The configuration contract is strict:

- `dijkstra` permits only `zero` or an omitted heuristic;
- `astar` requires `input_euclidean`;
- solver lists remain forbidden;
- A* pilot and production require a Dijkstra reference run;
- A* confirmation requires the frozen V2.10 confirmation-subset file.

## Consequences

- A* may be compared with Dijkstra on identical graphs, tasks, costs, and IDs.
- Closed nodes do not need reopening under the consistent heuristic.
- A* and Dijkstra must return identical optimal costs; any disagreement blocks
  the campaign.
- The A* campaign replays the completed Dijkstra population and does not use an
  independent sequential stop.
