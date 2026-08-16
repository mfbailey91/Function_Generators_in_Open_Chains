# Post-V3.6C Program — Canonical Joint Spans and Gravity-Free Static Wrench Geometry

**Status:** drafted; blocked. V3.6C Gate A closeout is accepted. This branch has since closed V4.0 and V4.1. Do not start V3-650–V3-679 until `ACTIVE_SPRINT.md` separately authorizes a named sprint.
**Program:** V3.6D–V3.6F
**Reserved work packages:** V3-650–V3-679
**Prepared against repository main:** `db967ab31af8acab83d113812bab748384374234`
**Applied on:** `Version_4_Kinematic_Transmission_Geometry` after V4.1 closeout
**Required predecessor:** V3-644 no-authorization return (satisfied)
**Code authorization granted by this document:** none
**Kernel rule if later activated:** consume V4.0 `transmission_geometry`; do not fork a second Jacobian/wrench implementation. V4.3 remains the Version 4 wrench column.

## Program intent

Replace the single representative 78-degree four-bar used in the frozen V3.6 audit lineage with a new, explicitly synthesized family of certified monotonic transmission modules organized around joint-output span. Then add a gravity-free, actuator-limited static wrench formulation and a readable configuration-space atlas that exposes how the transmission and serial-arm geometry combine.

The program keeps the central architecture

\[
\mathcal U \xrightarrow{g_m} \mathcal Q \xrightarrow{f} \mathcal X
\]

and adds a dual static mapping

\[
\mathbf w
\xrightarrow{J_f(\mathbf q)^\mathsf T}
\boldsymbol\tau_q
\xrightarrow{J_g(\mathbf u)^\mathsf T}
\boldsymbol\tau_u.
\]

The scientific question is no longer only how mechanism geometry reshapes motion-planning distance. It is also:

> How does intrinsic kinematic geometry redistribute normalized actuator effort into joint torque and Cartesian static wrench capability across configuration space?

## Why this is inserted before architecture-final V3.7

The 2R case remains the most inspectable environment in which to validate the transmission map, arm Jacobian, exact force polygon, singularity semantics, and visualization contract. Completing this work before the 3R reconciliation gives the later planar-arm study a validated span registry and a capability model rather than forcing both concepts into the dimensionality jump.

The sequence becomes:

\[
\boxed{
\text{V3.6C Gate A corrective closeout}
\rightarrow
\text{V3.6D span corpus}
\rightarrow
\text{V3.6E wrench core}
\rightarrow
\text{V3.6F atlas/docs}
\rightarrow
\text{architecture-final V3.7}
}
\]

This planning package may be committed before activation, but `ACTIVE_SPRINT.md` must remain unchanged until V3-644 has returned the repository to no authorization. Each sprint is activated separately.

## Frozen-lineage rule

The following remain historical evidence and may not be overwritten or silently regenerated:

```text
results/v3_review/v3_6_free_space/
results/v3_review/v3_6_free_space_v2/
results/v3_review/v3_6b_planar2r_visual_audit/
results/v3_review/v3_6c_planar2r_closeout/
results/v3_review/v3_7_3r_free_space/
results/v4_review/v4_0_kinematic_geometry_core/
results/v4_review/v4_1_planar2r_geometry_atlas/
```

The old four-bar

\[
a=1.0,\quad b=2.5,\quad c=2.0,\quad d=2.0
\]

remains a regression fixture and legacy visual reference. It is not a member of the new scientific span corpus and must not be relabeled as a 95-degree mechanism.

## Experimental span design

### Core span sweep

\[
\mathcal R_{\mathrm{core}}=\{95^\circ,145^\circ,175^\circ\}.
\]

Interpretation:

- `95`: deliberately restricted-range control;
- `145`: central elbow/knee-like hinge anchor;
- `175`: near-limit boundary-stress span, retained because its low-gain end regions may expose large ideal torque amplification and fine output resolution.

### Biological refinement

\[
\mathcal R_{\mathrm{bio}}=\{135^\circ,145^\circ,150^\circ\}.
\]

This is a complete ordered 3×3 refinement, not a hand-picked subset. It resolves the elbow/knee/wrist band while preserving proximal/distal placement as a factor.

### Unique 2R corpus

The two ordered factorials share only `(145,145)`, producing

\[
9+9-1=17
\]

unique span assignments. The case registry is generated, never manually duplicated.

| Study | J1 span set | J2 span set | Ordered cells |
|---|---:|---:|---:|
| Core | 95, 145, 175 | 95, 145, 175 | 9 |
| Biological refinement | 135, 145, 150 | 135, 145, 150 | 9 |
| Union | — | — | 17 unique |

Joint order remains meaningful. `(95,175)` and `(175,95)` are separate physical arms.

## Range semantics

Every axis records three nested intervals:

\[
Q_{\mathrm{task}}
\subseteq
Q_{\mathrm{usable}}
\subseteq
Q_{\mathrm{mechanical}}.
\]

- `mechanical`: complete selected-assembly rocker stroke;
- `usable`: certified monotonic interval used by the robot and all comparisons;
- `task`: subset exercised by a particular task bank.

The target span is the width of `Q_usable`, not the dead-center-to-dead-center mechanical stroke. Canonical V1 intervals are centered at zero so that span is isolated from neutral-offset effects:

\[
q_i\in[-R_i/2,R_i/2].
\]

Anatomically asymmetric limits are deferred to the later planar-arm morphology experiment.

## Canonical mechanism rule

Synthesize one deterministic canonical crank-rocker per target span:

\[
R\in\{95,135,145,150,175\}\text{ degrees}.
\]

All five candidates use the same frozen certification profile and synthesis objective. The synthesis must record:

- normalized link lengths and assembly convention;
- full physical rocker stroke;
- certified usable Q interval;
- selected U interval;
- target-span error;
- minimum, maximum, mean, and variance of `abs(dq/du)`;
- inverse-gain statistics;
- endpoint gain;
- change-point and branch margins;
- optimizer, seed, objective terms, and implementation revision.

The selection objective is lexicographic:

1. satisfy the requested usable span within tolerance;
2. satisfy the common branch and singularity certificate;
3. maximize the worst certified margin;
4. minimize a declared gain-shape regularizer only after the first three conditions are met.

No mechanism may be tuned using planner or wrench outcomes.

### The 175-degree rule

`175` remains in the registry, but it may not force the certificate to move. Outcomes are typed:

- `certified_primary`: passes the same profile as the other spans;
- `boundary_stress_only`: requires a separately frozen near-limit certificate and is excluded from pooled primary inference;
- `unsupported_under_certificate`: no accepted candidate; report the failure rather than relaxing thresholds after inspection.

This is a scientific result, not a software failure.

## Matched gearbox control

For each certified four-bar usable branch, build a span-matched constant transmission over the identical U and Q endpoints:

\[
r_{\mathrm{eq}}
=
\frac{q_{\max}-q_{\min}}{u_{\max}-u_{\min}},
\qquad
q_G(u)=q_{\min}+r_{\mathrm{eq}}(u-u_{\min}).
\]

The pair shares:

- Q limits and Q center;
- U interval endpoints;
- average transmission ratio;
- normalized actuator torque limits;
- robot link lengths;
- Q grid and task definitions.

The four-bar differs only through its configuration-dependent map.

## Gravity-free static wrench scope

For this program, gravity is not an option that defaults to zero. It is outside the model.

Included:

- rigid kinematic mechanism map;
- rigid serial-arm Jacobian;
- ideal virtual work;
- declared symmetric actuator torque box;
- exact 2D force polygon and scalar/directional summaries.

Excluded:

- gravity and payload weight;
- inertia, Coriolis, acceleration, and impact;
- friction, backlash, compliance, and losses;
- passive tissue or spring forces;
- thermal, structural, buckling, bearing, and safe-contact limits.

A future gravity-aware formulation requires a new ADR, new schema name, and new result lineage. It may not be introduced as a hidden boolean in this program.

## Primary visualization decision

The initial atlas uses a scalar configuration-space heatmap as the primary view:

\[
r_{\mathrm{iso}}(q)
=
\text{radius of the largest origin-centered Euclidean force disk inside }\mathcal W(q).
\]

Secondary views are:

- directional capacity heatmaps for `+x`, `+y`, radial, and tangential force;
- sparse exact force-polygon glyphs on a decimated grid;
- rank, singularity, and near-limit masks;
- local decomposition of `J_g`, `J_f`, and `J_{xu}` on selection/hover.

The polygon field is a diagnostic overlay, not the only view and not drawn at every cell.

## Program deliverables

| Sprint | Deliverable | Artifact target |
|---|---|---|
| V3.6D | Five-span canonical mechanism registry and 17-case corpus | `results/v3_review/v3_6d_span_corpus/` |
| V3.6E | Tested gravity-free static wrench API and analytic fixtures | `results/v3_review/v3_6e_static_wrench_core/` |
| V3.6F | HTML atlas, scalar/directional maps, polygon diagnostics, methods, and biological trace | `results/v3_review/v3_6f_static_wrench_atlas/` |

## Program-level exit criteria

1. V3-644 is closed and `ACTIVE_SPRINT` was returned to no authorization before V3.6D activation.
2. Five target spans have deterministic typed synthesis outcomes with no post-outcome certificate changes.
3. The 17-case registry is exact, ordered, deduplicated, and reproducible.
4. Every four-bar has a matched constant-transmission control over identical U/Q endpoints.
5. The gravity-free wrench mapping passes analytic, finite-difference, polygon, directional, scaling, and singularity tests.
6. The atlas uses shared paired scales, exposes singular/unbounded ideal-model cases honestly, and does not equate normalized ideal capability with safe force or biological strength.
7. Paper/method docs explain the wrench map as a consequence of kinematic geometry and virtual work.
8. Biological sources and the provenance of 95/135/145/150/175 are traceable, with 175 explicitly not labeled as ordinary wrist flexion-extension.
9. Fresh artifacts are generated from clean implementation commits; all frozen V3.6/V3.7 evidence remains byte-unchanged.
10. V3.6F returns `ACTIVE_SPRINT` to no authorization. V3.7 requires a separate activation change.

## Explicit non-goals

- biological force prediction or muscle modeling;
- anatomical mechanism identification from ROM alone;
- claiming the selected spans are universal human constants;
- gravity compensation or payload maps;
- contact/friction cones;
- structural force limits;
- force-aware planning objectives in this first atlas;
- 3R wrench polytopes or force/moment unit normalization;
- mechanism populations beyond one canonical representative per span;
- changing or reinterpreting frozen V3.6 conclusions.
