# ADR-010 — Equal Valid-Node Mode (IM-018)

**Status:** Accepted

## Context

Native Monte Carlo (ADR-009) shares one actuator lattice and takes shared Q
limits from each trial’s four-bar follower ranges. Under that protocol the
unit gearbox occupies only the limit box on a full-period lattice, so
\(N_{\mathrm{valid}}\) is typically much smaller than the four-bar’s nearly
full crank grid. Raw expansion counts then confound morphology with graph
cardinality (paper §11.2 / §12.3).

## Decision

### Two explicit modes

| Mode | Config | Lattice policy |
| --- | --- | --- |
| **Native** | `graph.match_valid_nodes: false` (default) | One shared `PeriodicGrid2D` for gearbox and four-bar. |
| **Equal valid-node** | `graph.match_valid_nodes: true` | Four-bar stays on the baseline crank lattice; gearbox gets a separate U lattice over the **same** Q box with square shape chosen so \(N_{\mathrm{valid}}^{\mathrm{gear}} \approx N_{\mathrm{valid}}^{4R}\). |

Search identity remains in \(U\) (ADR-001). Shared closed Q limits remain
identical for both mechanisms (ADR-004). Duplicate four-bar preimages remain
distinct. Output-Euclidean edge costs are unchanged (ADR-005).

### Gearbox lattice construction

For equal-node trials:

1. Sample the independent crank-rockers and derive follower-range limits
   (ADR-009).
2. Build the four-bar graph on `graph.shape` / full crank ranges / wrap.
3. Place a gearbox lattice with axis ranges equal to that Q box and
   `wrap=(False, False)` (bounded joint window, not a full \(S^1\)).
4. Choose square shape near \(\sqrt{N_{4R}}\) (search up to
   `match_shape_hi`) until
   \(|N_{\mathrm{gear}}-N_{4R}| / N_{4R} \le\) `match_relative_tol`.

Implementation: `inequality_mechanisms.experiments.equal_nodes`.

### Reporting

Trial JSONL records `gearbox_grid_shape`, `fourbar_grid_shape`, and
`match_meta` when matching is active. Expansion plots stay the same; raw
\(N_{\mathrm{expanded}}\) becomes the fairer size-controlled comparison, with
\(\rho = N / N_{\mathrm{valid}}\) still reported.

Optional `trials.n_path_samples` writes U / Q / Cartesian path PNGs for the
first \(k\) kept trials under `outputs/paths/`.

## Consequences

Benefits:

- disentangles cardinality from mechanism-induced metric/topology effects;
- native mode remains the “real shared lattice” baseline;
- config flag keeps reproduction auditable.

Costs:

- gearbox and four-bar U panels no longer share the same visual lattice;
- matching failure (no shape within tolerance) aborts the trial build loudly.

## Related

- IM-018 in `docs/BACKLOG.md`
- ADR-009 population limits
- Paper §12.3 “Equal valid-node count”
