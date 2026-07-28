# ADR-012 — Equivalent-Gain Gearbox Matching

**Status:** Accepted

## Context

Sprint Four and Five compare a four-bar against a **unit gearbox**
\(q = u\). That identity baseline is scientifically important, but when the
four-bar has a different average gain or output span the comparison confounds
scale with nonlinearity. Sprint Six adds **equivalent-gain** linear controls
that match an explicit scalar criterion while preserving the unit gearbox as a
separate baseline.

## Decision

### Affine gearbox

An equivalent gearbox is the affine map

\[
q = q_{\mathrm{ref}} + r_{\mathrm{eq}} \odot (u - u_{\mathrm{ref}})
\]

with Jacobian \(\mathrm{diag}(r_{\mathrm{eq}})\). Registry key:
`equivalent_gearbox`. This is distinct from `fixed_ratio_gearbox` (\(q = r \odot u\)).

### Matching rules

| Rule | Key | Applicability | Definition |
| --- | --- | --- | --- |
| Span | `span` | Monotonic branch / sector | \(r = \Delta q / \Delta u\) |
| Total variation | `total_variation` | Full cycle | \(r_{\mathrm{TV}} = \mathrm{TV}(q)/\Delta u\) |
| RMS gain | `rms_gain` | Full cycle | \(r_{\mathrm{RMS}} = \sqrt{\mathrm{mean}((dq/du)^2)}\) |

Signed average gain over a full crank-rocker cycle is zero; span matching is
therefore **not** used as a full-cycle equivalent. TV and RMS are the explicit
full-cycle alternatives.

### Numerical policy

- Dense crank samples default to \(n = 361\) on the configured input interval
  (full cycle: \([0, 2\pi)\)).
- Per-axis matching for `IndependentFourBars` uses each `PlanarFourBar` factor.
- Span matching uses the primary monotonic sector when available
  (`mechanisms.monotonic`); otherwise the configured \(u\) interval and the
  continuous (unwrapped) follower image.
- Integration of \(\lvert dq/du \rvert\) and \((dq/du)^2\) uses trapezoidal
  quadrature on the sample grid.
- Zero or non-finite ratios are rejected.

### Baseline labels

Comparisons must name the criterion explicitly:

```text
unit_gearbox
span_matched_gearbox
tv_matched_gearbox
rms_matched_gearbox
fourbar
```

The generic label “equivalent gearbox” without a matching rule is forbidden in
plots and tables.

### Configuration

YAML may supply explicit `ratios`, `u_ref`, `q_ref`, and `matching_rule`, or
omit ratios and set `matching_rule` so setup derives the gearbox from the paired
four-bar at materialization time. Provenance (rule, intervals, source
parameters, monotonic vs full-cycle) is stored on the mechanism and in run
metadata.

## Consequences

- Unit gearbox remains available and is never replaced by equivalent-gain
  controls.
- Matched vs unmatched quantities must be reported per comparison (Sprint Six
  S6-18).
- Graph identity remains in \(U\) (ADR-001); shared Q limits remain ADR-004.
