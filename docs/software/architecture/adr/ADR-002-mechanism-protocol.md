# ADR-002 — Mechanism Protocol

**Status:** Accepted

## Context

Version 1 compares unit gearboxes, fixed-ratio gearboxes, and planar four-bars under a shared search pipeline. Those mechanisms differ in injectivity, assembly domain, and periodicity, but graph construction, costs, and search must call one interface.

The paper sketch exposes forward map, Jacobian, inverse, validity, and periodic axes. Experiments also need stable serialization of mechanism parameters.

## Decision

All Version 1 transmissions implement an abstract `Mechanism` base class in
`inequality_mechanisms.mechanisms.base` with the following contract.

### Methods and shapes

| Member | Contract |
| --- | --- |
| `name` | Short identifier string for logging and configs. |
| `input_dim` / `output_dim` | Positive integers. Version 1 uses equal dimensions (planar 2R → \(n=2\)). |
| `input_to_output(u)` | \(g\colon\mathcal U\to\mathcal Q\). Input shape `(input_dim,)`, output shape `(output_dim,)`. |
| `output_jacobian(u)` | \(J_g(u)=\partial q/\partial u\), shape `(output_dim, input_dim)`. |
| `inverse_output(q)` | All valid input preimages of \(q\) as a `list` of arrays of shape `(input_dim,)`. Empty list if none. Duplicate preimages remain distinct entries. |
| `valid_input(u)` | Assembly / kinematic domain only. Does **not** apply shared output joint limits (IM-009 / ADR-004). |
| `periodic_axes()` | Tuple of length `input_dim`. `True` means that axis wraps with period \(2\pi\). |
| `to_dict()` / `from_dict(data)` | Plain `dict` with a `type` discriminator; `from_dict` dispatches through a registry. |

Array arguments are converted to `float64` NumPy arrays. Callers may pass any array-like of the correct shape.

### Failure behavior

| Condition | Behavior |
| --- | --- |
| Wrong rank or length | `ValueError` |
| Non-finite entries in `u` or `q` | `ValueError` |
| `input_to_output` / `output_jacobian` at an invalid assembly | `ValueError` (callers may check `valid_input` first) |
| No preimages for `q` | `[]` (not an exception) |
| Unknown `type` in `from_dict` | `MechanismRegistryError` |
| Missing `type` key in `from_dict` | `ValueError` |

### Serialization

Concrete types register with `register_mechanism_type(type_key, cls)`. Dicts must include `"type"` matching a registered key. No pydantic models on this path; experiment configs remain separate (IM-014 / ADR-006).

## Consequences

Benefits:

- one call site for graphs, search, and experiments;
- multi-valued inverse preserves ADR-001 preimage semantics;
- assembly validity stays separable from shared output limits;
- registry-based round-trips support reproducible runs.

Costs:

- every new mechanism must implement the full ABC and register for deserialization;
- Version 1 assumes square maps (`input_dim == output_dim`); non-square maps would need an ADR update.
