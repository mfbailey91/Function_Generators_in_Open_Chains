"""Future lifted output-state search ``(q, σ)`` (S4-12).

Sprint Four documents this representation but does **not** implement a
planner on it. Physical Version 1 search remains input-space identity
(ADR-001). The monotonic uniform-``Q`` control (S4-11) is a different,
narrower experiment: it requires a one-to-one branch so each ``q`` has a
unique attached ``u``, and therefore does not need an explicit sheet index.

## Motivation

A full-cycle four-bar follower map is generally not injective:

```text
u_a ≠ u_b,    g(u_a) = g(u_b).
```

Collapsing those states onto ``q`` alone creates false connectivity. A
future planner may instead use

```text
state = (q, σ)
```

where ``σ`` identifies the preimage / branch / winding sector / assembly
sheet so that distinct physical configurations remain distinct nodes even
when their follower angles coincide.

## Contrast with ADR-011 chart lift

ADR-011 lifts raw Freudenstein (or gearbox) angles into a shared bounded
revolute chart for metrics, limits, and heuristics. That lift is about
**coordinates and distances in Q**, not about expanding the **search node
identity**. Chart lift can make a continuous follower curve look smooth
across the principal seam; it does not encode which crank preimage produced
``q``.

By contrast, ``(q, σ)`` would change the search graph's node key so that
two preimages of the same chart coordinate are different states.

## Relationship to S4-11

S4-11 builds a regular ``Q`` lattice only after restricting to a monotonic
injective sector where ``u = g^{-1}(q)`` is unique. That control asks
whether planning behavior comes from nonlinear ``g`` versus uniform
actuator sampling. It is explicitly **not** a proposal to replace ADR-001,
and it does not generalize to multi-preimage full-cycle graphs.

## Deferred implementation notes

If ``(q, σ)`` is implemented later:

1. Define ``σ`` explicitly (algebraic branch, crank sector, winding index,
   or discrete preimage id).
2. Prove or test that edges never connect incompatible sheets.
3. Keep output limits and chart distances on the ``q`` factor.
4. Validate against ADR-001 U-identity search on matched tasks.
5. Update ADR-001 (or supersede it) only after that evidence exists.

Until then, do not treat regular ``Q``-only lattices as a physical state
representation outside the documented monotonic control.
"""
