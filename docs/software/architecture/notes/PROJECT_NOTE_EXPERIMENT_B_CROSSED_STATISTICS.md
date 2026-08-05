# Project note — Experiment B crossed statistical design

**Status:** prerequisite placeholder; not accepted; not an implementation contract  
**Blocks:** Sprint V2.12 activation and any Experiment B production stop rule  
**Related:** [`EXPERIMENT_B_CARTESIAN_GOAL_REGION.md`](../../experiments/protocols/EXPERIMENT_B_CARTESIAN_GOAL_REGION.md)

## Why this note exists

Experiment A reused eight designed tasks inside each mechanism pair and
estimated a mechanism-level average over that suite. Sequential precision,
hierarchical bootstrap, and confirmation stratification in V2.10/V2.11 all
treat the mechanism pair as the clustering unit with nested tasks.

Experiment B freezes external Cartesian tasks and evaluates them across
mechanisms. That is a crossed structure, not a nested one:

\[
\Delta_{mk}
=
\mu+\alpha_m+\beta_k+\varepsilon_{mk}.
\]

Copying pair-nested bootstrap or stopping logic would overstate precision.

## Required decisions before activation

An accepted design, or a later ADR if the analysis becomes architectural, must
specify:

1. the primary estimand for coverage,
   \(P(\text{task admissible/reachable})\);
2. the primary conditional search estimand,
   \(\mathbb E[\text{search metric}\mid\text{task admissible/reachable}]\);
3. how structural missingness from reachability enters inference;
4. whether \(\alpha_m\) and \(\beta_k\) are random, fixed, or mixed;
5. a two-way cluster, crossed bootstrap, or hierarchical procedure that
   preserves both mechanism and task dependence;
6. sequential-precision stopping units that do not treat task rows as iid;
7. confirmation-subset stratification that is not silently inherited from
   Experiment A's `mean_log_gain_var` rule;
8. separate reporting for the pair-local workspace control, never merged into
   the external-domain primary mean.

## Non-decisions

This note does not choose a software package, sample size, or stop threshold.
Those wait until ADR-019 has frozen the task bank schema and a calibration
campaign exists.

## Return condition

Promote this note into a contract or ADR only when the crossed design is
specific enough to implement and test. Until then, V2.12 remains held.
