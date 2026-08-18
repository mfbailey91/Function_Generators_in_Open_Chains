# V3.6E gravity-free static wrench core closeout

**Disposition:** generated; non-inferential math fixtures
**Package:** [`results/v3_review/v3_6e_static_wrench_core/`](../../../../results/v3_review/v3_6e_static_wrench_core/)
**Work packages closed:** V3-660 through V3-669
**ADR:** [ADR-028](../adr/ADR-028-gravity-free-static-wrench.md)

## Review conclusion

The gravity-free planar force set is the exact torque-box polytope

\[
\mathcal W=\{w:[F_x,F_y]:|J_{xu}^\mathsf T w|\le\bar\tau_u\},\qquad\bar\tau_u=[1,1].
\]

Jacobians, rank, and virtual work come from the closed V4.0 `transmission_geometry` kernel. There is no second composite-Jacobian module. Regular states return four torque-box vertices. Rank-deficient states return an H-representation and typed `unbounded_ideal_direction` rather than a fake polygon. Gravity and payload keys are rejected. Interior evaluations of all 17 realized V3.6D cases are `regular`. This sprint is not V4.3.

## Authorization

`ACTIVE_SPRINT.md` returns to **no code authorization** at E closeout. V3.6F requires a separate activation. This closeout does not authorize HTML/atlas work, V4.2, V4.3, or residual V3.7.
