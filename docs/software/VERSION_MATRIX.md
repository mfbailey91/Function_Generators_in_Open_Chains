# Architecture version matrix

| Concern | Version 1 | Version 2 |
| --- | --- | --- |
| Mechanism regime | Full-cycle or potentially noninjective | Certified one-to-one operating branch |
| Planning node identity | Complete actuator state in \(\mathcal U\) | Output state in \(\mathcal Q\) with unique actuator realization attached |
| Duplicate output preimages | Preserved as distinct states | Excluded by branch certification |
| Input topology | May be periodic | Bounded and nonperiodic in the core study |
| Primary graph | Input-state graph | Output-state embedded graph |
| Sampling modes | Uniform actuator lattice | Uniform-\(\mathcal U\) mapped to \(\mathcal Q\), plus uniform-\(\mathcal Q\) control |
| Config/result schema | Version 1 | Separate Version 2 schema |
| Status | Preserved research baseline | Active rearchitecture |

ADR-001 remains authoritative for Version 1. Version 2 may use output-state identity only after the operating branch satisfies the accepted certification contract.
