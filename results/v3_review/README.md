# Version 3 review results

This directory is the explicit exception to the repository-wide `results/*`
ignore rule. It contains **small, reviewable Version 3 smoke/parity snapshots**
that are intentionally committed to GitHub with the code revision that
generated them.

These snapshots are not production evidence, task-population inference, or
Monte Carlo campaigns. They exist so reviewers can inspect the behavioral
consequences of the Version 3 architecture without rerunning every local smoke
pack.

## V3.5 closeout snapshot

Generate the complete V3.2–V3.5 review package in an OMPL-enabled environment:

```bash
PYTHONPATH=src python scripts/export_v3_review_results.py
```

Output: `results/v3_review/v3_5_closeout/`.

## V3.6 free-space evidence

`results/v3_review/v3_6_free_space/` is retained as the **v1 pilot artifact**.
Review found that equal normalized actuator starts did not produce equal
physical starts across the paired mechanisms, so its pooled means are not the
V3.6 closeout evidence.

The corrected V3.6 contract is generated from `free_space_planar2r_v2.json`:

```bash
# First commit the implementation/bank correction so HEAD is clean.
PYTHONPATH=src:. python scripts/run_v3_6_free_space_evidence_v2.py

# Then review and commit the generated evidence separately.
git add results/v3_review/v3_6_free_space_v2         docs/software/experiments/reports/V3_6_FREE_SPACE_EVIDENCE_V2.html
```

The v2 exporter records the clean implementation revision that generated the
artifact, resolves one shared `q`/Cartesian start for both mechanisms, freezes
the represented Cartesian goal set, and runs stochastic OMPL repetitions in
fresh processes.
