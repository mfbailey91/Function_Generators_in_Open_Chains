# Inequality Mechanisms — Literature Map

This file is extracted from Section 19 of the paper draft.

## 19. Literature map and reading program

This section is deliberately more than a bibliography. It records what each source is expected to contribute to the argument, what should be read first, and where the literature may resist the proposed framing.

### 19.1 First reading pass

#### Classical mechanism theory

**[1] Freudenstein — four-bar input/output synthesis.**  
Read first for the historical and analytical foundation of treating a four-bar as a function generator. The paper is important not only for the equation that bears Freudenstein’s name, but because it frames mechanism geometry as a deliberate mapping between input and output motion.

**[2] Hunt — kinematic geometry and mechanism structure.**  
Read alongside Freudenstein for the geometrical language behind lower pairs, higher pairs, closed chains, freedom, and structure. This is a book rather than a paper, but it is central to the intellectual lineage of the project and to the eventual discussion of biological joints and kinematic substitution.

#### Embodied intelligence and morphological computation

**[3] McGeer — passive dynamic walking.**  
The cleanest demonstration that morphology and dynamics can generate organized behavior without a conventional continuously commanding controller.

**[4] Pfeifer and Bongard — embodiment as an enabling constraint.**  
The broad conceptual introduction. Particularly relevant to the language that the body both constrains and enables cognition and behavior.

**[5] Hauser et al. — theoretical foundation for morphological computation.**  
Useful for avoiding vague claims that “the body computes.” It gives a more technical account of how compliant morphology can contribute computationally.

**[6] Ghazi-Zahedi et al. — state-dependent morphological computation.**  
Especially relevant to this project because the proposed inequality is also state dependent. A mechanism cannot be judged by one global scalar; its contribution changes across configuration and behavior.

**[7] Hoffmann and Müller — tradeoffs and criticism.**  
Important counterweight. It questions simplistic claims that complicated or compliant bodies automatically reduce control burden and emphasizes tradeoffs between body complexity, modeling, and control.

**[8] Langer and Ay — controller complexity and learning.**  
Directly relevant to the conjecture that morphology can reduce control burden while learning may still require complexity. This may help prevent the reinforcement-learning argument from becoming one directional.

#### Robot and controller co-design

**[9] Ha et al. — computational co-optimization of robot design and motion.**  
A foundational modern comparison point for optimizing link dimensions, actuator placement, motion trajectories, and forces together.

**[10] Belmonte-Baeza et al. — learned evaluation of kinematic and actuator designs.**  
Directly relevant because the work optimizes robot kinematics and actuator parameters through meta reinforcement learning.

**[11] He and Ciocarlie — hardware–policy co-optimization.**  
Useful for the later software and reinforcement-learning program. It provides a concrete example of learned hardware and policy co-design in reaching and manipulation tasks.

#### Joint mechanisms and surgical or prosthetic reconstruction

**[12] Radcliffe — four-bar prosthetic knees.**  
A foundational technical treatment of polycentric prosthetic knee kinematics, alignment, and prescription criteria.

**[13] Floerkemeier et al. — arthroplasty and four-bar-like rollback.**  
The most direct source previously referenced for a knee arthroplasty design intended to reconstruct a four-bar-like rollback mechanism.

**[14] Scott et al. — criticism and qualification of the knee four-bar model.**  
Essential because it directly questions whether a total knee can be both rotationally unconstrained and anterior–posterior stable, and reviews the historical four-bar interpretation. This is the kind of paper that should prevent the surgical section from becoming too tidy.

**[15] Chen et al. — linkage failure in total elbow arthroplasty.**  
Relevant less as proof of a four-bar elbow and more as evidence that linked surgical joints are real mechanisms with mechanism-specific failure modes.

#### Broader physical intelligence

**[16] Thakur et al. — physical artificial intelligence.**  
A recent broad framing source. It is useful for vocabulary and field positioning, but it should not replace the more specific mechanism, morphology, and planning literature above.

#### Force polytopes and gravity-free static capability

The software now records an exact planar 2R force polygon from a symmetric actuator torque box under ideal virtual work, $\tau_u=J_{xu}^\mathsf T w$. This is a kinematic-geometry dual of the existing actuator-travel metric, not a dynamics, gravity, or biological-strength model. Rank loss is typed (`unbounded_ideal_direction`) rather than clipped. Primary visualization is the inscribed isotropic radius; directional $+x/+y$/radial/tangential capacities and sparse exact polygons remain inspectable. Scope and limitations: [ADR-028](../../software/architecture/adr/ADR-028-gravity-free-static-wrench.md), [method note](../../software/architecture/notes/STATIC_WRENCH_KINEMATIC_GEOMETRY_METHOD.md), and the [biological range trace](BIOLOGICAL_JOINT_RANGE_REFERENCE_TRACE.md).

### 19.2 Conceptual framing and narrative order

The literature should be read through a two-view structure that also organizes the paper's explanation.

#### Mechanism view

Begin with the conventional identity transmission,

$$
q=u,
$$

and make explicit that the ordinary revolute-joint model already contains a hidden **unit gearbox**. Because conventional kinematics usually begins in output coordinates $q$, the actuator-to-joint map is obscured. The identity case appears neutral only because its input and output coordinates coincide.

Next introduce the general map

$$
\mathcal U\xrightarrow{g_m}\mathcal Q.
$$

Sample $\mathcal U$ uniformly and map those samples into $\mathcal Q$. This makes the function generator visible: equal actuator increments become equal, uniformly scaled, or configuration-dependent output increments for the unit gearbox, fixed gearbox, and four-bar respectively. The reader should see the deformation before being asked to interpret a graph-search result.

> A uniform input graph reveals what motion the function generator physically generates.

#### Planning-control view

After the deformation is understood, return to a common uniform output graph. Give each mechanism the same output nodes, adjacency, output limits, start, goal, and nominal resolution. Reintroduce the mechanism through the inverse map, preimage state, feasibility, and edge weights.

On an invertible branch,

$$
M_Q(q)
=
J_g^{-\mathsf T}W_uJ_g^{-1}
$$

expresses actuator-side cost in output coordinates. Two arms can therefore share the same $Q$ graph while assigning different costs to its edges and selecting different paths.

> A uniform output graph reveals how different transmissions value the same possible arm motions.

This second view is the controlled apples-to-apples comparison. It should also make clear why the function generator is easy to overlook: a uniform $Q$ graph without mechanism-dependent weights or hidden-state labels silently reduces every transmission to the unit gearbox abstraction.

#### Proposed reader walk-up

The narrative order should be:

1. the familiar arm represented directly in $Q$;
2. recognition that $q=u$ is an identity transmission rather than the absence of a transmission;
3. explicit separation of $\mathcal U\to\mathcal Q\to\mathcal X$;
4. a uniform-$U$ graph mapped into $Q$ to reveal the generated inequality;
5. gearbox and four-bar examples as constant and variable cases;
6. the induced metric and local speed, torque, and resolution consequences;
7. a uniform-$Q$ graph with mechanism-dependent costs as the controlled planning comparison;
8. lifted output state $(q,\sigma)$ when the mechanism is not globally invertible.

This sequence lets the argument move from the familiar abstraction to the generalized mechanism without asking the reader to accept the full graph-theoretic formulation at once.

### 19.3 Questions to carry into the reading

1. Does the literature treat kinematic mappings themselves as computational structure, or primarily focus on compliance, dynamics, materials, and actuator placement?
2. Has anyone explicitly measured path-planning node expansions as a function of transmission geometry?
3. Is the four-bar-induced metric best described as a preconditioner, a morphology-induced metric, a task prior, or something else?
4. Which parts of the full-crank, multiple-preimage topology have already been studied in mechanism-aware planning?
5. Do prosthetic and implant papers use an actual linkage, a shaped-contact higher pair, or only a four-bar analogy?
6. Which morphology–control papers measure learning speed or sample complexity rather than only final task performance?
7. Where does added morphological inequality make control or learning worse?

### 19.4 Reading-note template

For each source, preserve notes in this form:

```text
Citation:
Why it matters:
Claim it supports:
Claim it complicates:
Useful equation, figure, or experiment:
Connection to inequality mechanisms:
Follow-up sources:
```

This should eventually become a separate literature database or BibTeX file, but keeping interpretive notes beside the references is useful while the central argument is still changing.

---

## References

[1] Ferdinand Freudenstein, “An Analytical Approach to the Design of Four-Link Mechanisms,” *Transactions of the ASME*, vol. 76, no. 3, pp. 483–489, 1954. [doi:10.1115/1.4014881](https://doi.org/10.1115/1.4014881)

[2] Kenneth H. Hunt, *Kinematic Geometry of Mechanisms*. Oxford: Clarendon Press, 1978. [Book record](https://books.google.com/books/about/Kinematic_Geometry_of_Mechanisms.html?id=B6cjho7N3EoC)

[3] Tad McGeer, “Passive Dynamic Walking,” *The International Journal of Robotics Research*, vol. 9, no. 2, pp. 62–82, 1990. [doi:10.1177/027836499000900206](https://doi.org/10.1177/027836499000900206)

[4] Rolf Pfeifer and Josh Bongard, *How the Body Shapes the Way We Think: A New View of Intelligence*. Cambridge, MA: MIT Press, 2006. [Publisher page](https://mitpress.mit.edu/9780262537421/how-the-body-shapes-the-way-we-think/)

[5] Helmut Hauser, Auke J. Ijspeert, Rudolf M. Füchslin, Rolf Pfeifer, and Wolfgang Maass, “Towards a Theoretical Foundation for Morphological Computation with Compliant Bodies,” *Biological Cybernetics*, vol. 105, pp. 355–370, 2011. [doi:10.1007/s00422-012-0471-0](https://doi.org/10.1007/s00422-012-0471-0)

[6] Keyan Ghazi-Zahedi, Daniel F. B. Haeufle, Guido Montúfar, Syn Schmitt, and Nihat Ay, “Evaluating Morphological Computation in Muscle and DC-Motor Driven Models of Human Hopping,” arXiv:1512.00250, 2015. [arXiv](https://arxiv.org/abs/1512.00250)

[7] Matej Hoffmann and Vincent C. Müller, “Trade-Offs in Exploiting Body Morphology for Control: From Simple Bodies and Model-Based Control to Complex Bodies with Model-Free Distributed Control Schemes,” arXiv:1411.2276, 2014; revised book-chapter version published 2017. [arXiv](https://arxiv.org/abs/1411.2276) · [doi:10.1007/978-3-319-43784-2_17](https://doi.org/10.1007/978-3-319-43784-2_17)

[8] Carlotta Langer and Nihat Ay, “Outsourcing Control Requires Control Complexity,” arXiv:2209.01418, 2022. [arXiv](https://arxiv.org/abs/2209.01418)

[9] Sehoon Ha, Stelian Coros, Alexander Alspach, Joohyung Kim, and Katsu Yamane, “Computational Co-Optimization of Design Parameters and Motion Trajectories for Robotic Systems,” *The International Journal of Robotics Research*, vol. 37, nos. 13–14, pp. 1521–1536, 2018. [doi:10.1177/0278364918771172](https://doi.org/10.1177/0278364918771172)

[10] Álvaro Belmonte-Baeza, Joonho Lee, Giorgio Valsecchi, and Marco Hutter, “Meta Reinforcement Learning for Optimal Design of Legged Robots,” *IEEE Robotics and Automation Letters*, vol. 7, no. 4, pp. 12134–12141, 2022. [doi:10.1109/LRA.2022.3211785](https://doi.org/10.1109/LRA.2022.3211785) · [arXiv](https://arxiv.org/abs/2210.02750)

[11] Zhanpeng He and Matei Ciocarlie, “MORPH: Design Co-Optimization with Reinforcement Learning via a Differentiable Hardware Model Proxy,” in *2024 IEEE International Conference on Robotics and Automation (ICRA)*, pp. 7764–7771, 2024. [IEEE record](https://ieeexplore.ieee.org/document/10610732) · [arXiv](https://arxiv.org/abs/2309.17227)

[12] C. W. Radcliffe, “Four-Bar Linkage Prosthetic Knee Mechanisms: Kinematics, Alignment and Prescription Criteria,” *Prosthetics and Orthotics International*, vol. 18, no. 3, pp. 159–173, 1994. [doi:10.3109/03093649409164401](https://doi.org/10.3109/03093649409164401)

[13] Thilo Floerkemeier et al., “Physiologically Shaped Knee Arthroplasty Induces Natural Roll-Back,” *Technology and Health Care*, vol. 19, no. 2, pp. 91–102, 2011. [doi:10.3233/THC-2011-0616](https://doi.org/10.3233/THC-2011-0616)

[14] G. Scott et al., “Can a Total Knee Arthroplasty Be Both Rotationally Unconstrained and Anteroposteriorly Stable? A Pulsed Fluoroscopic Investigation,” *Bone & Joint Research*, 2016. [PubMed record](https://pubmed.ncbi.nlm.nih.gov/26965166/)

[15] Po-An Chen et al., “Failure of the Linkage Mechanism in a Semi-Constrained Total Elbow Arthroplasty Is a Rare and Unpredictable Event: A Review of Seven Cases,” *International Orthopaedics*, vol. 48, no. 2, pp. 537–545, 2024. [doi:10.1007/s00264-023-06015-1](https://doi.org/10.1007/s00264-023-06015-1)

[16] Atul Thakur, Krishnanand Kaipa, Ashis G. Banerjee, David J. Cappelleri, and colleagues, “Physical Artificial Intelligence for Powering the Next Revolution in Robotics,” *Journal of Computing and Information Science in Engineering*, vol. 25, no. 12, article 120809, 2025. [doi:10.1115/1.4070122](https://doi.org/10.1115/1.4070122)

### Additional reading queue

The following sources were not central citations in the earlier discussion but are likely useful next:

- Vincent C. Müller and Matej Hoffmann, “What Is Morphological Computation? On How the Body Contributes to Cognition and Control,” *Artificial Life*, vol. 23, no. 1, pp. 1–24, 2017. [Publisher page](https://direct.mit.edu/artl/article/23/1/1/2858/What-Is-Morphological-Computation-On-How-the-Body)
- R. D. Komistek et al., “In Vivo Kinematics for Subjects with and without an Anterior Cruciate Ligament,” 2002. [PubMed record](https://pubmed.ncbi.nlm.nih.gov/12439275/)
- S. Ha et al., “Task-Based Limb Optimization for Legged Robots,” *IEEE/RSJ International Conference on Intelligent Robots and Systems*, 2016.
- J. Whitman and H. Choset, “Task-Specific Manipulator Design and Trajectory Synthesis,” *IEEE Robotics and Automation Letters*, vol. 4, no. 2, pp. 301–308, 2019. [doi:10.1109/LRA.2018.2890206](https://doi.org/10.1109/LRA.2018.2890206)
