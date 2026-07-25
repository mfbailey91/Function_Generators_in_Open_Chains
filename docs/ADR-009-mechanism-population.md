# ADR-009 — Crank-Rocker Population and Four-Bar-Derived Limits

**Status:** Accepted

## Context

Paper §11–§12 describe a Monte Carlo pilot over randomly sampled crank-rocker
pairs, not a single fixed linkage. The Version-1 pilot initially hard-coded
`(a,b,c,d)=(1,2.5,2,2)` for both axes and a fixed output box
`[1.05, 2.2]²`. That confounds mechanism-population effects with one geometry
and one hand-tuned limit window.

Shared Q limits must still match gearbox and four-bar (ADR-004). For random
crank-rockers, absolute boxes starve many samples. The four-bar’s own follower
range is the natural task box.

## Decision

### Population filters (paper §12.1)

`inequality_mechanisms.mechanisms.population` samples planar crank-rockers with:

| Rule | Version-1 default |
| --- | --- |
| Ground length | `d = 1` |
| Length draws | `a,b,c ~ Uniform[0.2, 2.0]` |
| Strict Grashof crank-rocker | `s + l + margin < p + q`, shortest link is crank `a`, `margin = 0.05` |
| Branch | `+1` |
| Full crank cycle | `valid_input` on a dense `[0, 2π)` lattice |
| Minimum follower range | width `≥ 0.5` rad on the selected branch |
| Transmission bounds | finite Jacobian everywhere; `|dq/du| ≤ 20`; `max|dq/du| ≥ 0.05` (near-zero ratios at rocker extremes allowed) |

Two independent draws form an `IndependentFourBars` pair per trial.

### Shared limits from the four-bar

For `mechanisms.fourbar.mode: population`:

1. Sample the two bars.
2. Set `OutputJointLimits` to each bar’s selected-branch follower range
   (tiny numerical epsilon only so closed bounds stay well-defined).
3. Apply **the same** limit object to gearbox and four-bar graphs.

Do **not** use paper §12.2’s separate hand-chosen shared box for population
runs. Absolute `limits:` remain required only for `mode: fixed`.

### Pilot loop

Each population trial rebuilds both constrained graphs under that trial’s
limits, then samples matched `(q_start, q_goal)` as in ADR-006. Trial JSONL
records `fourbar_lengths` and `limits`.

### Config

`mechanisms.fourbar` is a discriminated source:

- `mode: fixed` — ADR-002 `independent_fourbars` dict (legacy bare dicts coerce
  to fixed); requires top-level `limits`.
- `mode: population` — sampler fields; `limits` must be omitted.

## Consequences

Benefits:

- Monte Carlo matches the paper’s mechanism-population intent;
- ADR-004 fairness preserved with mechanism-induced Q boxes;
- fixed mode keeps deterministic path demos and unit tests.

Costs:

- native `64×64` graph rebuilds dominate runtime;
- per-trial valid-node counts vary (graph-size confounding remains unless
  `graph.match_valid_nodes` is enabled; see ADR-010 / IM-018).
