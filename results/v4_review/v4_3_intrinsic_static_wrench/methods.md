# V4.3 Intrinsic Gravity-Free Static Wrench — Methods

This package evaluates the accepted ideal static-wrench model on frozen
corrected V4.2B mounted-Q geometry snapshots. It does not recompute
Jacobians, resynthesize branches, or retune rank thresholds.

## Scientific contract

Normalized actuator torque box \(\bar\tau_u = (1, 1)\) with units
`normalized_actuator_torque`. Force values use `normalized_torque_per_length`. Gravity, payload,
dynamics, friction, compliance, structural limits, and contact are absent.

Virtual work uses the stored maps

\[
J_{xu} = J_f J_g,\qquad
\tau_u = J_{xu}^\mathsf T F,\qquad
\mathcal F(q) = \{ F :
-\bar\tau_u \le J_{xu}^\mathsf T F \le \bar\tau_u \}.
\]

`directional_capacity` is **ray capacity** along a unit direction \(d\),
not the support function. The isotropic radius \(\rho_{\mathrm{iso}}\)
is the largest origin-centered disk inside \(\mathcal F\).

## Snapshot source and sampling

Canonical input: `results/v4_review/v4_2b_span_controlled_corrective_closeout` (mounted-coordinate V4.2B
closeout). Rows are restored through `parse_retained_atlas_row` and evaluated
with `static_wrench_from_snapshot`. Sampling measure: uniform mounted-Q grid
retained by V4.2B (33 × 33 per case). Summaries are descriptive over that
grid, not workspace-uniform or application-frequency estimates.

Primary heatmap cells require status `regular` and a finite isotropic radius.
Finite near-singular or singular diagnostics remain in detail records and are
masked from the primary view. An unbounded strip may still report finite
directional capacities along constrained axes.

## Inherited tolerances

```json
{
  "direction_eps": 1e-12,
  "near_singular_condition": 1000000.0,
  "note": "Rank, direction, and near-singular thresholds are inherited from the V3.6E API; V4.3 does not retune them for display.",
  "primary_display_statuses": [
    "regular"
  ],
  "vertex_feasibility_atol": 1e-09
}
```

## Authoritative method note

See also the accepted kinematic-geometry method contract copied from:

`docs/software/architecture/notes/STATIC_WRENCH_KINEMATIC_GEOMETRY_METHOD.md`

Full upstream note begins:

> # Static Wrench Capability from Kinematic Geometry

## Nonclaims

- Not an application load rating or structural strength certificate.
- Not a general ranking of mechanisms.
- Biological span memberships motivate experimental ranges only; they do not
  claim biological force capability.
- Historical V4.2 / V4.2A / V3.6F packages are provenance links only.
