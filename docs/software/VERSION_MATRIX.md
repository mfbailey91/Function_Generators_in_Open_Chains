# Architecture version matrix

| Concern | Version 1 | Version 2 | Version 3 |
| --- | --- | --- | --- |
| Mechanism regime | Full-cycle or potentially noninjective | Certified one-to-one operating branch | Certified monotonic branch initially; noninjective restored later |
| Planning center | Graph experiment in \(\mathcal U\) | Graph experiment in \(\mathcal Q\) with attached \(u\) | Planner-independent planning problem |
| Planning node identity | Complete actuator state in \(\mathcal U\) | Output state in \(\mathcal Q\) with unique actuator realization attached | Physical state \((u,q,\text{assembly state},\ldots)\); representation is planner-specific |
| Duplicate output preimages | Preserved as distinct states | Excluded by branch certification | Excluded on monotonic branch; preserved when noninjective maps return |
| Input topology | May be periodic | Bounded and nonperiodic in the core study | Same initial branch contract as V2; generalizes with later state models |
| Primary representation | Input-state graph | Output-state embedded graph | Direct, lattice, roadmap, tree, OMPL, later MoveIt |
| Local motion | Graph adjacency / edge traces | Four-connected lattice edges | Continuous local-motion models; adjacency is candidate generation |
| Start / goal | Graph nodes / V1 queries | Lattice attachment; Cartesian goal regions (B) | Exact start; goal as task predicate; attachment residual is diagnostic |
| Sampling modes | Uniform actuator lattice | Uniform-\(\mathcal U\) mapped to \(\mathcal Q\), plus uniform-\(\mathcal Q\) control | External task banks; planner sampling is backend-specific |
| Config/result schema | Version 1 | Separate Version 2 schema | Separate Version 3 problem/result schema |
| Status | Preserved research baseline | Frozen historical experiment lineage | V3.6C review candidate generated; Gate A corrective amendment V3-640–V3-644 active; provisional 3R free-space remains blocked |

ADR-001 remains authoritative for Version 1. Version 2 may use output-state identity only after the operating branch satisfies the accepted certification contract. Version 3 contracts are accepted under ADRs 021–026 and do not reinterpret frozen Version 2 evidence.
