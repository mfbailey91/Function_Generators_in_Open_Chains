# Sprint V2.2 — Certified Invertible Operating Branches

## Theme

> Make invertibility an explicit, tested object rather than an assumption in an experiment script.

## Objective

Introduce a certified operating-branch abstraction that restricts an existing mechanism to a nonperiodic, one-to-one domain with a unique inverse. Implement the initial branch support needed for unit/fixed gearboxes, equivalent affine gearboxes, and independent four-bar followers.

## Architectural rule

Do not change the existing `Mechanism` contract or `inverse_output()` all-preimages behavior. A full mechanism and an invertible operating branch are different objects.

## Target API

Create `src/inequality_mechanisms/mechanisms/operating_branch.py`.

```python
@dataclass(frozen=True)
class BranchCertificate:
    input_lower: tuple[float, ...]
    input_upper: tuple[float, ...]
    output_lower: tuple[float, ...]
    output_upper: tuple[float, ...]
    monotonic_sign: tuple[int, ...]
    min_abs_gain: tuple[float, ...]
    max_abs_gain: tuple[float, ...]
    max_forward_inverse_residual: float
    max_inverse_forward_residual: float
    certification_samples_per_axis: int
    certification_method: str
```

```python
class OperatingBranch:
    mechanism: Mechanism
    output_space: OutputSpace
    certificate: BranchCertificate

    def forward(self, u: ArrayLike) -> NDArray[np.float64]: ...
    def inverse(self, q: ArrayLike) -> NDArray[np.float64]: ...
    def jacobian(self, u: ArrayLike) -> NDArray[np.float64]: ...
    def contains_input(self, u: ArrayLike) -> bool: ...
    def contains_output(self, q: ArrayLike) -> bool: ...
    def to_dict(self) -> dict[str, Any]: ...
```

Version 2 initially supports square, axis-separable maps:

\[
q_i=g_i(u_i),
\qquad
J_g=\operatorname{diag}\left(\frac{dq_i}{du_i}\right).
\]

The abstraction may be written so future coupled branches are possible, but certification must reject unsupported coupling rather than pretending it is handled.

## Issues

### V2-201 — Define branch failure behavior

Document and implement exceptions for:

- output outside branch range;
- input outside branch range;
- nonunique inverse;
- unsupported nonseparable Jacobian;
- derivative sign change;
- gain below configured minimum;
- gain above optional configured maximum;
- forward/inverse residual above tolerance;
- failed assembly sample;
- ambiguous output chart.

Prefer explicit types such as:

```python
class BranchCertificationError(ValueError): ...
class BranchInverseError(ValueError): ...
```

### V2-202 — Implement affine gearbox branches

Support:

- unit gearbox branch;
- fixed-ratio gearbox branch;
- equivalent affine gearbox
  \[
  q=q_{\mathrm{ref}}+R(u-u_{\mathrm{ref}}).
  \]

For a matched four-bar branch, the equivalent affine gearbox should match input and output endpoints per axis:

\[
r_i=\frac{q_{i,\max}-q_{i,\min}}{u_{i,\max}-u_{i,\min}}.
\]

Store reference points and ratios explicitly. Reject zero range and zero gain.

### V2-203 — Select a four-bar monotonic branch

Implement branch selection from an existing continuous follower curve.

The selector must:

1. use one fixed assembly mode;
2. identify candidate intervals between follower extrema;
3. shrink the selected interval by configurable safety margins;
4. unwrap/canonicalize into the configured bounded output chart;
5. verify derivative sign consistency;
6. reject intervals that approach the minimum gain threshold;
7. expose input and output bounds.

Do not use full-cycle wrapping in the resulting branch.

### V2-204 — Implement unique inverse

For the initial independent four-bar branch, use a deterministic branch-local inverse.

Allowed approaches:

- monotonic interpolation table plus bracketed root refinement;
- direct bracketed root solve against the existing forward map.

Requirements:

- no global all-preimages lookup in normal branch inversion;
- deterministic convergence;
- explicit tolerance and iteration limit;
- residual checked after solve;
- no SciPy dependency unless justified and approved.

A NumPy interpolation seed plus a robust bisection/Brent-like in-house bracketed method is acceptable if tested thoroughly.

### V2-205 — Certify the branch

Certification must sample the branch deterministically and evaluate:

- mechanism assembly validity;
- output-space containment;
- derivative sign;
- minimum and maximum absolute gain;
- forward then inverse residual;
- inverse then forward residual;
- endpoint consistency;
- finite values throughout.

Certification density must be configured and serialized. The certificate is evidence, not mathematical proof; documentation must say so.

### V2-206 — Serialization and branch IDs

Serialize:

- underlying mechanism;
- input bounds;
- output-space chart;
- selector method and safety margins;
- certification parameters;
- certificate values.

Create a deterministic branch ID/hash from canonical serialized inputs, not from floating-point object identity.

### V2-207 — Branch diagnostics

Add static diagnostics showing per axis:

- \(q(u)\);
- selected branch bounds;
- \(dq/du\);
- minimum gain threshold;
- inverse residual across sampled \(q\);
- matched affine gearbox line.

Diagnostics must consume the same certified branch object used by graphs.

## Tests

### Unit tests

- affine forward/inverse exactness;
- contains-input/output boundary behavior;
- serialization round trip;
- invalid bounds and thresholds;
- inverse errors outside range.

### Four-bar branch tests

- monotonic positive branch;
- monotonic negative branch;
- branch crossing a principal-angle representation seam but remaining continuous in the output chart;
- rejection at a follower reversal;
- rejection when minimum absolute gain is too small;
- forward/inverse residual across endpoints and interior samples;
- deterministic certificate for fixed mechanism and settings.

### Property-style invariants

For sampled points:

\[
\|g^{-1}(g(u))-u\|\le\epsilon_u,
\]

\[
\|g(g^{-1}(q))-q\|\le\epsilon_q.
\]

## Expected file changes

```text
src/inequality_mechanisms/mechanisms/operating_branch.py
src/inequality_mechanisms/mechanisms/branch_selection.py    # optional
src/inequality_mechanisms/mechanisms/gearbox.py             # additive affine helper if needed
src/inequality_mechanisms/visualization/branches.py
tests/operating_branches/...
docs/software/architecture/audits/V2_2_BRANCH_CERTIFICATION.md
```

## Non-goals

- no graph construction;
- no search-state change;
- no periodic branch topology;
- no coupled multivariable inverse;
- no singular operating regions;
- no mechanism optimization.

## Recommended pull requests

1. **PR V2.2-A:** branch API, failure behavior, affine implementations.
2. **PR V2.2-B:** four-bar branch selector and unique inverse.
3. **PR V2.2-C:** certification, serialization, and tests.
4. **PR V2.2-D:** diagnostics and closeout note.

## Verification

```bash
pytest tests/operating_branches
pytest tests/golden_v1
pytest
ruff check .
ruff format --check .
mypy src
```

## Sprint exit criteria

1. A four-bar branch can be selected, certified, serialized, and inverted uniquely.
2. Branches are nonperiodic and remain inside one bounded output chart.
3. Near-reversal and low-gain intervals are rejected.
4. Matched affine gearbox branches are generated deterministically.
5. Version 1 mechanism APIs and golden tests remain unchanged.

## Cursor starter prompt

```text
Implement Sprint V2.2 only. Do not modify Mechanism.inverse_output semantics.
Create a separate OperatingBranch abstraction with explicit certification and a
unique branch-local inverse. First define failure behavior and tests. Then add
affine gearbox branches, four-bar monotonic branch selection, deterministic
inverse solving, certificate serialization, and diagnostics. Reject unsupported
coupling and near-zero gain. Run operating-branch tests, Version 1 golden tests,
and full CI after each PR slice. Do not build Version 2 graphs yet.
```
