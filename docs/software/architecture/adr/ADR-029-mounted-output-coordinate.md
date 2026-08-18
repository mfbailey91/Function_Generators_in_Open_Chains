# ADR-029 — Mounted Output Coordinates Are the Robot Joint Coordinates

**Status:** Accepted

**Applies to:** V3.6D span-registry consumers, V4.2B, and all downstream Version 4 span-family columns

**Related:** ADR-011 output-space semantics; ADR-027 kinematic transmission geometry

## Context

The V3.6D registry intentionally stores two descriptions of each synthesized follower range:

1. a **native follower interval** produced by the four-bar geometry;
2. a zero-centered **mounted output interval** plus the constant mounting offset relating them.

For one axis,

\[
q_{\mathrm{joint}}=q_{\mathrm{native}}-q_{\mathrm{offset}}.
\]

The frozen registry therefore contains the native mechanism geometry without requiring the robot joint zero to coincide with the mechanism solver's angular zero.

The original V4.2/V4.2A realization path reconstructed the native four-bar and selected its operating branch, but did not apply the stored output offset before passing `q` to the planar robot. Cross-span results consequently changed both output span and nominal robot posture.

## Decision

The coordinate carried by `PhysicalState.q`, consumed by robot forward kinematics, and sampled by shared-Q atlases is the **mounted robot joint coordinate**:

\[
\boxed{q=q_{\mathrm{joint}}=q_{\mathrm{native}}-q_{\mathrm{offset}}.}
\]

The conversion is applied exactly once at the registry-consumption boundary.

For a native mechanism map \(q_n=g_n(u)\), the mounted map is

\[
g_m(u)=g_n(u)-q_{\mathrm{offset}}.
\]

Its inverse and derivative are

\[
g_m^{-1}(q)=g_n^{-1}(q+q_{\mathrm{offset}}),
\qquad
\frac{dg_m}{du}=\frac{dg_n}{du}.
\]

Implementation must provide a serializable output-offset mechanism/branch adapter. The mounted operating-branch certificate, output space, inverse table, samples, plots, and equivalent gearbox all use mounted coordinates. Native coordinates and offsets remain available only as provenance and mechanism-debugging fields.

The V3.6D registry, native link lengths, branch sign, input interval, certificate profile, and digest remain frozen. V4.2B is a consumer correction, not a resynthesis.

## Consequences

### Benefits

- all span cases share the intended physical zero convention;
- cross-span changes in `J_f(q)` no longer arise from an accidental native-angle offset;
- the span-matched gearbox and identity control operate on the same mounted Q interval;
- the mechanism Jacobian `J_g` and gain descriptors remain unchanged by the constant offset;
- downstream wrench, velocity, planning, and flow columns consume one physical joint coordinate.

### Costs and compatibility

- V4.2 and V4.2A retained artifacts remain historically reproducible but are not canonical downstream span evidence;
- consumers that assumed the native follower angle was the robot joint coordinate must migrate to the mounted adapter;
- serialization must distinguish `q_joint`, `q_native`, and `q_offset` to prevent double application.

## Required invariants

For every supported span axis:

```text
mounted_output_bounds == registry.range_definition.usable_interval_rad
midpoint(mounted_output_bounds) == 0
width(mounted_output_bounds) == registry usable width
mounted_forward(u) + q_offset == native_forward(u)
mounted_inverse(mounted_forward(u)) == u
mounted_jacobian(u) == native_jacobian(u)
```

For every paired case:

```text
fourbar.q_bounds == gearbox.q_bounds == shared_q_bounds
robot FK and J_f consume q_joint, never q_native
q_offset is applied exactly once
```
