"""Result schema constants for experiment trial rows."""

from __future__ import annotations

# Sprint Four trial / summary schema version.
# 4.0.0 — P0 path metrics / cost+heuristic fields
# 4.1.0 — P1 factorial: runtime, beta, reachable counts, edge-cost variance
RESULT_SCHEMA_VERSION = "4.1.0"

# Sprint Five path-quality trial / summary schema version.
# 5.0.0 — directness, turning, self-intersections, near-revisits
SPRINT5_RESULT_SCHEMA_VERSION = "5.0.0"

# Sprint Six equivalence / resolution / hierarchical MC schema.
# 6.0.0 — equivalent gearboxes, M×K hierarchy, hierarchical bootstrap
SPRINT6_RESULT_SCHEMA_VERSION = "6.0.0"
