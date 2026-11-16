# Biological Joint Range Reference Trace

**Status:** initial source trace for experimental span selection
**Purpose:** preserve where the span anchors came from and what they do—and do not—mean

## Scope and caution

The software span values are experimental factors, not claims that all human joints share one range or that anatomical range alone identifies a transmission mechanism. Reported ROM depends on motion coordinate, active versus passive measurement, age, sex, body size, forearm posture, protocol, and whether the value is a mechanical maximum or a functional task requirement.

The current design uses biology to motivate a range corpus while keeping the robot experiment kinematic and controlled.

## Span interpretation

| Experimental span | Role in software | Biological/functional motivation | Must not be claimed |
|---:|---|---|---|
| 95° | restricted-range control | gait and slopes can require less than 90° knee flexion; stairs/chairs often occupy roughly 90–120° | a universal normal maximum for one named joint |
| 135° | lower biological refinement | functional knee demand near 135° for bath entry; lower edge of observed wrist flexion-extension totals and adult knee/elbow range cluster | the exact average elbow or knee ROM |
| 145° | central biological anchor | adult knee values cluster near 138–142°; adult elbow flexion commonly lies near 145–150°; an independent healthy-adult elbow study reported mean active flexion of 146° | one universal “human hinge” value |
| 150° | upper biological refinement | CDC adult female elbow flexion is 150°; healthy wrist flexion-extension totals can reach about 154° in the cited young cohort | proof that a wrist is a planar 150° hinge |
| 175° | near-limit/broad-orientation stress | adult shoulder flexion is near 169–172° in CDC data; combined forearm pronation-supination can approach the low/mid 170s in healthy cohorts | ordinary wrist flexion-extension, or evidence that anatomy is a crank-rocker |

## Source trace

### 1. Soucie et al. / CDC Normal Joint Range of Motion Study

**Citation:** J. M. Soucie et al., “Range of motion measurements: reference values and a database for comparison studies,” *Haemophilia*, 17(3), 500–507, 2011. DOI: `10.1111/j.1365-2516.2010.02399.x`. PubMed PMID: `21070485`.

**Study role:** broad community-based reference dataset, reported separately by sex and age.

**Adult age 20–44 reference values used here:**

| Motion | Females | Males |
|---|---:|---:|
| Knee flexion | 141.9° | 137.7° |
| Shoulder flexion | 172.0° | 168.8° |
| Elbow flexion | 150.0° | 144.6° |
| Elbow pronation | 82.0° | 76.9° |
| Elbow supination | 90.6° | 85.0° |

**Supports:** a central knee/elbow band around roughly 140–150°, shoulder flexion around 170°, and a broad forearm rotation arc when pronation and supination are combined.

**Complicates:** values differ by sex and age; individual motion coordinates may begin/end at different clinical reference positions.

**Links:**

- CDC archived study table: <https://archive.cdc.gov/www_cdc_gov/ncbddd/jointrom/index_1715172647.html>
- PubMed: <https://pubmed.ncbi.nlm.nih.gov/21070485/>

### 2. Zwerus et al. — healthy adult elbow

**Citation:** E. L. Zwerus et al., “Normative values and affecting factors for the elbow range of motion,” *Shoulder & Elbow*, 2019. PMCID: `PMC6555111`; PMID: `31210794`.

**Cohort:** 352 healthy adults.

**Reported dominant active means:**

- flexion 146°;
- extension −2°;
- pronation 80°;
- supination 87°.

Passive values were generally 3–5° larger, and age, sex, and BMI affected ROM.

**Supports:** 145° as a clean central elbow-like experimental anchor and combined forearm rotation near 167° at the reported means.

**Does not support:** treating 145° as a fixed anatomical constant.

**Link:** <https://pmc.ncbi.nlm.nih.gov/articles/PMC6555111/>

### 3. Fan et al. — wrist ROM and forearm rotation in healthy young adults

**Citation:** S. Fan et al., “Variation of Grip Strength and Wrist Range of Motion with Forearm Rotation in Healthy Young Volunteers Aged 23 to 30,” *Journal of Hand and Microsurgery*, 11(2), 88–93, 2019. DOI: `10.1055/s-0038-1676134`; PMCID: `PMC6692155`; PMID: `31413492`.

**Cohort:** 30 healthy volunteers, values separated by sex, side, and forearm posture.

**Examples used for span interpretation:**

- male dominant, neutral forearm: wrist flexion 70.2° + extension 65.6° = 135.8° total;
- female dominant, neutral forearm: wrist flexion 79.7° + extension 74.4° = 154.1° total;
- combined pronation/supination ranges in the table extend from about 162° into the mid-170s depending on sex and side.

**Supports:** representing the 135–150 band in the software and recognizing that a broad terminal orientation arc can approach 175°.

**Complicates:** wrist flexion-extension and forearm axial rotation are different coordinates. A planar third joint at 175° is therefore a terminal-orientation stress module, not a literal anatomical wrist claim.

**Link:** <https://pmc.ncbi.nlm.nih.gov/articles/PMC6692155/>

### 4. Rowe et al. — functional knee motion

**Citation:** P. J. Rowe et al., “Knee joint kinematics in gait and other functional activities measured using flexible electrogoniometry: how much knee motion is sufficient for normal daily life?” *Gait & Posture*, 2000. PMID: `10998612`; DOI: `10.1016/S0966-6362(00)00060-6`.

**Cohort:** 20 elderly normal subjects.

**Reported functional requirements:**

- gait and slopes: less than 90° flexion;
- stairs and chairs: approximately 90–120°;
- bath: approximately 135°.

**Supports:** 95° as a deliberately restricted/functional control and 135° as a meaningful high-functional knee anchor.

**Does not support:** 95° as the maximum healthy knee range.

**Link:** <https://pubmed.ncbi.nlm.nih.gov/10998612/>

## Experimental mapping decision

The primary 2R corpus is not an anatomical model. It is a controlled mechanism study with two complete ordered designs:

\[
\{95,145,175\}^2
\]

and

\[
\{135,145,150\}^2.
\]

The first spans restricted, central, and near-limit behavior. The second resolves the biologically motivated hinge/wrist band. Their union contains 17 unique ordered cases.

## Later planar-arm morphology study

After the 2R span/wrench program and architecture-final 3R reconciliation, retain two named hypotheses for a planar arm:

### Conservative arm analogue

\[
I_{175}-F_{145}-F_{150}
\]

- broad identity root/shoulder coordinate;
- nonlinear elbow-like module;
- nonlinear wrist-flexion/extension-like terminal module.

### Distal-capability stress arm

\[
I_{175}-F_{145}-F_{175}
\]

The last module is called a broad terminal-orientation module, not a literal wrist hinge.

These are morphology hypotheses to test. They are not conclusions drawn from the ROM sources.
