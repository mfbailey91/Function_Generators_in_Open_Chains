# Post-V4.1 Program — Span-Controlled Geometry Atlas and Intrinsic Static Wrench

**Status:** drafted / blocked. Do not implement until `ACTIVE_SPRINT.md` separately authorizes V4-200–V4-208.
**Program:** V4.2 then V4.3
**Reserved work packages:** V4-200–V4-208 (V4.2); V4-300–V4-309 (V4.3, blocked until V4.2 closes)
**Prepared against:** `9b49dba` on `Version_4_Kinematic_Transmission_Geometry`
**Required predecessors:** closed V4.0 kernel; closed V4.1 atlas; completed V3.6D–F; no-authorization `ACTIVE_SPRINT.md`
**Code authorization granted by this document:** none
**Kernel rule:** consume V4.0 `transmission_geometry` and the V3.6E wrench API. Do not fork a second Jacobian or force-set implementation.

## V4.1 historical disposition

Shipped Sprint V4.1 is closed and frozen:

- package [`results/v4_review/v4_1_planar2r_geometry_atlas/`](../../../results/v4_review/v4_1_planar2r_geometry_atlas/);
- work packages **V4-100–V4-108**;
- mechanisms: the legacy ~78° crank-rocker \(a=1,b=2.5,c=2,d=2\), its span-matched gearbox, and identity-on-shared-\(Q\).

The earlier span-defined “V4.1” proposal in the local post-V4.0 bundle was **never** the implemented V4.1. That bundle remains [superseded](../architecture/notes/V4_POST_V4_0_SPAN_STATIC_WRENCH_BUNDLE_SUPERSEDED.md). This program does not authorize a V4.1 defect review, relabel, or regeneration. Do not reuse V4-100–V4-108.

## Program intent

V3.6D already froze the five-span family and 17 unique ordered cases. V3.6E/F already froze the gravity-free force-set mathematics and a V3-lineage atlas. V4.1 already froze the shared-\(Q\) snapshot atlas machinery on the legacy pair.

This program is the **Version 4 lineage extension**: evaluate that frozen span family with V4.1-style geometry snapshots and identity controls (V4.2), then evaluate the frozen V3.6E force set on those V4.2 snapshot banks (V4.3).

The scientific question for V4.2:

> What intrinsic \(J_g\), \(J_f\), \(J_{xu}\), metric, and rank fields does the certified span family induce on shared mounted \(Q\) grids, relative to span-matched gearboxes and identity-on-shared-\(Q\)?

The scientific question for V4.3:

> How does the same frozen geometry redistribute a normalized actuator torque box into planar endpoint force capacity across that family?

## Reuse rule

Implement only missing work. Do not duplicate or retune a capability that already exists.

| Already shipped | V4.2/V4.3 must |
| --- | --- |
| V3.6D registry, ranges, 17 cases, span-matched gearboxes, typed 175° | consume by digest; do not resynthesize; do not move `PRIMARY_CERTIFICATE` |
| V4.1 `shared_q_atlas`, `geometry_atlas`, identity control, rank fields, HTML atlas | extend to the 17-case family; write a fresh V4.2 root |
| V4.0 `geometry_snapshot` | call it; do not rederive \(J_g\), \(J_f\), \(J_{xu}\) |
| V3.6E `static_wrench.py` / `wrench_directions.py` | V4.3 consumes the API; does not reimplement polygons |
| V3.6F methods and biological trace | V4.3 links them; does not claim new biology |

## Frozen-lineage rule

Do not overwrite or silently regenerate:

```text
results/v3_review/
results/v4_review/v4_0_kinematic_geometry_core/
results/v4_review/v4_1_planar2r_geometry_atlas/
```

Fresh roots only:

```text
results/v4_review/v4_2_span_controlled_geometry_atlas/
results/v4_review/v4_3_intrinsic_static_wrench/
```

The legacy ~78° four-bar remains the V4.1 atlas fixture. It is not a member of the V4.2 scientific span family.

## Experimental span design (consumed, not resynthesized)

\[
\mathcal R_{\mathrm{core}}=\{95^\circ,145^\circ,175^\circ\},\qquad
\mathcal R_{\mathrm{bio}}=\{135^\circ,145^\circ,150^\circ\}.
\]

Two complete ordered \(3\times 3\) matrices share only `(145,145)`, producing 18 labeled cells and 17 unique span assignments. Proximal/distal order is a factor: `(95,175)` and `(175,95)` are distinct arms. 175° remains `boundary_stress_only` under the frozen near-limit certificate.

Each nonlinear module in V4.2 receives:

- the V3.6D certified usable monotonic interval, geometry, branch, mounted output coordinate, gain descriptors, certificate, and provenance;
- an exact span-matched affine gearbox over the same usable U and Q intervals;
- an identity-on-shared-\(Q\) null control;
- V4.0 `KinematicGeometrySnapshot` evaluation on a per-case shared \(\eta\in[-1,1]^2\) grid.

## Gravity-free wrench scope (V4.3)

Unchanged from ADR-028 / V3.6E:

\[
\tau_u=J_{xu}^\mathsf T F,\qquad
\mathcal F_x(q)=\{F:-\bar\tau_u\le J_{xu}^\mathsf T F\le\bar\tau_u\},\qquad
\bar\tau_u=(1,1).
\]

Gravity, payload, dynamics, friction, compliance, structural limits, and contact remain absent from schema and estimand.

## Sequence

\[
\boxed{
\text{closed V4.1 + frozen V3.6D}
\rightarrow
\text{V4.2 span geometry extension}
\rightarrow
\text{V4.3 intrinsic wrench atlas}
\rightarrow
\text{V4.4 velocity / IK}
}
\]

Residual V3.7 remains a separately blocked choice. Do not mix 3R reconciliation into V4.2 or V4.3.

## Deliverables

| Sprint | Deliverable | Artifact target |
| --- | --- | --- |
| V4.2 | 17-case V4.0 snapshot atlas with gearbox and identity controls | `results/v4_review/v4_2_span_controlled_geometry_atlas/` |
| V4.3 | Intrinsic gravity-free wrench atlas on frozen V4.2 snapshots | `results/v4_review/v4_3_intrinsic_static_wrench/` |

## Authorization

This planning package may be committed before activation. `ACTIVE_SPRINT.md` must remain unchanged in the planning commit. A separate, reviewed activation change may later authorize **V4-200–V4-208 only**. V4.3 requires its own later activation after V4.2 closeout.

## Explicit non-goals

- regenerating or relabeling V4.1;
- resynthesizing the V3.6D family or retuning 175°;
- a second Jacobian or wrench kernel;
- gravity-aware wrench;
- force-aware planning;
- velocity / IK (V4.4);
- residual V3.7, 6R, obstacles, MoveIt.
