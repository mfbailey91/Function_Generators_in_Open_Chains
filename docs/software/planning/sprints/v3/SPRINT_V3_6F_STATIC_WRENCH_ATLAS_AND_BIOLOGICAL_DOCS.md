# Sprint V3.6F — Static Wrench Atlas and Biological Documentation

**Status:** completed; V3-670–V3-679 closed
**Reserved work packages:** V3-670–V3-679
**Depends on:** accepted V3.6D registry; accepted V3.6E math core; no-authorization state
**Blocks:** architecture-final V3.7 activation
**Report target:** `results/v3_review/v3_6f_static_wrench_atlas/`

## Sprint question

> Can the span corpus and gravity-free static force model be presented in one readable index that separates a useful scalar field, directional capability, exact local geometry, and singularity warnings?

## Report information architecture

The report opens with the 17-case matrix and supports filters for:

- study membership: core / biological refinement;
- J1 and J2 spans;
- four-bar / matched gearbox;
- primary scalar / direction / polygon overlay;
- regular / near-singular / rank-deficient masks.

Every paired four-bar/gearbox plot uses the same Q samples and shared color limits.

Across different span cases, provide both:

- physical angle ticks in degrees;
- normalized range coordinates
  \(
  \bar q_i=2(q_i-q_{c,i})/R_i\in[-1,1]
  \)
  for morphological comparison.

## Work packages

### V3-670 — Atlas contract and manifest

Define static assets, case-page schema, index navigation, print fallback, source-data links, and artifact manifest. Extend freeze guards so the exporter writes only to the F target.

### V3-671 — Primary scalar heatmaps

Render `normalized_isotropic_force_capacity` / `wrench_inscribed_radius` over the shared Q grid. Requirements:

- paired mechanism color scale;
- explicit normalized units;
- no visual clipping in source data;
- mask overlays for invalid and nonregular states;
- local min/median/max summary;
- selected-point readout containing Q, U, `J_g`, `J_f`, `J_xu`, rank, and status.

This is the default view in `index.html`.

### V3-672 — Directional heatmaps

Render `+x`, `+y`, radial, and tangential capacity. Use one direction selector rather than four permanently expanded plot rows. Undefined radial/tangential cells receive a typed mask. Preserve signed direction metadata even though symmetric actuator limits make positive/negative capacities equal in V1.

### V3-673 — Sparse exact force polygons

Add force-polygon glyphs at a decimated set of regular grid locations. The density is configurable and defaults to a readable sparse lattice. Requirements:

- same force scale within a panel;
- local coordinate axes;
- regular polygons only;
- unbounded/rank-deficient symbol rather than a fake clipped polygon;
- optional selected-cell enlarged polygon;
- source vertex JSON link.

### V3-674 — Index integration

Build one top-level `index.html` containing:

1. scope and normalization banner;
2. span/case matrix;
3. mechanism cards and certificate status;
4. scalar heatmap view;
5. directional selector;
6. polygon diagnostic overlay;
7. transmission/arm/composite decomposition;
8. singularity and near-limit legend;
9. methods and biological-reference links;
10. raw records and manifest.

Do not overwrite the V3.6C index. This is a new artifact lineage.

### V3-675 — Methods and kinematic-geometry documentation

Integrate the full derivation from

\[
q=g(u)
\]

to

\[
\tau_u=J_g^\mathsf TJ_f^\mathsf Tw
\]

and explain the duality with the existing actuator-travel metric. State clearly:

> The force field is not an added dynamic model. Under ideal virtual work it is the static dual of the same kinematic geometry already used to map actuator motion into joint and Cartesian motion.

Also document why low `dq/du` can simultaneously imply fine output resolution, low output speed, and high ideal output torque amplification, while exact toggle behavior remains singular and structurally unmodeled.

### V3-676 — Paper and literature-map integration

Update the paper and literature map with:

- force/wrench polytopes and actuator-limit representations;
- the gravity-free scope;
- exact 2R force-polygon method;
- scalar and directional configuration-space capability fields;
- kinematic-geometry interpretation;
- limitations separating normalized ideal force from safe force and biological strength.

### V3-677 — Biological range reference trace

Land a dedicated trace document that records:

- source and cohort;
- motion coordinate;
- active/passive convention;
- measured value or range;
- experimental span anchor;
- claim supported;
- claim not supported.

The trace must state:

- 145 degrees is a central experimental anchor, not a universal norm;
- 135 and 150 refine the observed hinge/wrist band;
- 175 is better interpreted as a near-limit stress span or broad shoulder/forearm orientation arc, not ordinary planar wrist flexion-extension;
- 95 is a restricted/functional control, not a normative anatomical maximum.

### V3-678 — Exporter and report tests

Required tests:

1. all 17 cases linked exactly once in the index;
2. paired four-bar/gearbox arrays share Q coordinates and color bounds;
3. index default is scalar heatmap;
4. direction selector points to valid data;
5. polygon vertices match E-core records;
6. singular/unbounded statuses never render as ordinary finite polygons;
7. all assets and source-data links resolve;
8. print fallback shows core scope and primary maps;
9. trace mode does not alter calculations;
10. no gravity wording appears as an implemented option;
11. frozen artifact hashes unchanged.

### V3-679 — Clean generation and program gate

- implementation/docs commit first;
- full suite and link checks;
- generate atlas from clean revision;
- artifact commit separately;
- visual review of at least one case from each span and both mechanism classes;
- inspect 175 end regions and singularity masks;
- return to no authorization;
- architecture-final V3.7 requires separate activation.

## Proposed source targets

```text
src/inequality_mechanisms/audits/
├── static_wrench_atlas.py
├── static_wrench_plots.py
└── html_report.py              # extend through generic sections

scripts/export_v3_6f_static_wrench_atlas.py
tests/v3/test_v3_6f_static_wrench_atlas.py

docs/software/architecture/notes/STATIC_WRENCH_KINEMATIC_GEOMETRY_METHOD.md
docs/research/literature/BIOLOGICAL_JOINT_RANGE_REFERENCE_TRACE.md
```

## Exit criteria

1. The scalar heatmap is readable enough to stand alone.
2. Directional maps and polygons explain, rather than obscure, the scalar result.
3. Four-bar and gearbox comparisons use shared physical Q grids and paired scales.
4. Singularities, near-toggle states, and unbounded ideal directions are explicit.
5. Methods docs derive the field and frame it as kinematic geometry plus virtual work.
6. Biological span anchors are traceable and carefully qualified.
7. Gravity remains absent from implementation and result schema.
8. The new index is complete and frozen predecessors are unchanged.
9. Repository returns to no authorization.
