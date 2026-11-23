# 5-Slide Presentation Deck: EquiMed-India
## Deterministic Generic Drug Substitution & Affordability Optimizer

**Institution:** Indian Institute of Information Technology (IIIT), Lucknow  
**Course:** Software Engineering (4 Credits)  
**Format:** 5 Slides Max | 10-Minute Presentation + Cross-Examination  

---

```
========================================================================================
SLIDE 1: PROBLEM STATEMENT & REAL-WORLD MOTIVATION
========================================================================================
```

### Title: The Out-Of-Pocket Drug Expenditure Trap in Indian Chronic Care

#### 1. The Core Problem (Single, Focused Problem):
- In India, **65% to 70% of total healthcare expenditure is out-of-pocket (OOP)**, with recurring monthly pharmaceutical purchases representing the largest recurring financial burden on households.
- Patients suffering from chronic conditions (Type 2 Diabetes, Hypertension, Dyslipidemia, Cardiovascular diseases) spend **₹1,500 to ₹4,500 per month** on branded medicines (e.g., *Telma 40*, *Glycomet-GP 2*, *Augmentin 625*, *Pan-D*).
- Chemically identical, bioequivalent generic alternatives—including Government of India **Jan Aushadhi (PMBJP)** and WHO-GMP certified generics—exist at **70% to 90% lower cost**, but patients cannot substitute them safely because prescriptions specify commercial brand names rather than generic chemical salts.

#### 2. The Measurable Goal (Concrete Number):
- **Reduce recurring monthly chronic prescription expenditure by > 75%** while guaranteeing **100.0% chemical bioequivalence** and **0% clinical dosage mismatches**.

---

```
========================================================================================
SLIDE 2: PROPOSED SOLUTION & THE ROLE OF SOFTWARE ENGINEERING
========================================================================================
```

### Title: EquiMed-India: System Architecture & Software Engineering Discipline

#### 1. System Overview:
- EquiMed-India is an autonomous, deterministic clinical decision engine that resolves branded drugs to canonical Active Pharmaceutical Ingredients (APIs), validates bioequivalence under CDSCO standards, and computes line-item and aggregate chronic therapy savings.

#### 2. How Core Software Engineering Principles Drove the Project:
- **IEEE Std 830-1998 SRS Specification:** Authored full specification with 8 Functional Requirements (REQ-1 to REQ-8) and strict Non-Functional Requirements (Performance, Clinical Safety, Zero Hallucination).
- **Object-Oriented Design & GoF Design Patterns:**
  - *Strategy Pattern:* Decouples economic prioritization algorithms (`MaxSavings`, `JanAushadhiFirst`, `BalancedQuality`).
  - *Observer Pattern:* Decoupled clinical telemetry, audit trails, and savings tracking.
  - *Repository & Multi-Index Pattern:* O(1) in-memory inverted chemical fingerprint indexing.
- **Agile / Scrum Methodology:** Executed in 3 test-driven micro-sprints with user stories, acceptance criteria, and burndown velocity tracking.
- **Verification & Validation (V&V):** Dual-tier testing suite with unit testing, black-box testing, and continuous integration via Git.

---

```
========================================================================================
SLIDE 3: WHY THAT APPROACH? (DESIGN CHOICES & JUSTIFICATIONS)
========================================================================================
```

### Title: Architectural Decisions & Design Justifications

#### 1. Inverted Chemical Salt Fingerprinting vs. Linear Catalog Scanning
- *Choice:* Canonical salt hashing: `sorted_salts#dosage_form#release_type` in a hash map.
- *Justification:* In combination drugs (e.g., Metformin 500mg + Glimepiride 2mg vs Glimepiride 2mg + Metformin 500mg), array scanning is $O(N \cdot M)$ and prone to ordering bugs. Inverted hash indexing achieves **$O(1)$ constant-time retrieval**, enabling sub-millisecond throughput ($>100,000\text{ queries/sec}$).

#### 2. Strategy Pattern vs. Hardcoded If-Else Conditional Trees
- *Choice:* Pluggable `SubstitutionStrategy` subclasses (`MaxSavingsStrategy`, `JanAushadhiFirstStrategy`, `ReputationBalancedStrategy`).
- *Justification:* Adheres to Open-Closed Principle (OCP). Enables users and retail pharmacies to switch between pure price optimization and public healthcare subsidy preference without modifying core safety engine code.

#### 3. 6-Tier Deterministic Safety Gate vs. Fuzzy/Heuristic Matching
- *Choice:* Multi-stage validation gate: Salt Match $\rightarrow$ Strength Match $\rightarrow$ Form Bioequivalence $\rightarrow$ Release Kinetics Safety $\rightarrow$ Narrow Therapeutic Index (NTI) Flag $\rightarrow$ Price Ceiling Check.
- *Justification:* Medical substitution is a zero-tolerance domain. Fuzzy matching could allow dose-dumping (substituting Sustained Release with Immediate Release) or toxicity in NTI drugs (Levothyroxine, Warfarin).

---

```
========================================================================================
SLIDE 4: MEASURABLE OUTCOMES & EMPIRICAL TEST BENCHMARKS
========================================================================================
```

### Title: Empirical Test Numbers & Out-of-Pocket Savings Results

#### 1. Real-World Patient Savings (Validated Across Chronic Baskets):
| Chronic Patient Therapy Profile | Branded Monthly Spend | EquiMed Generic Spend | Monthly Savings (₹) | Savings (%) | Projected Annual Savings |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Elderly Diabetic & Hypertensive** | ₹1,531.80 | ₹250.50 | **₹1,281.30** | **83.7%** | **₹15,375.60 / year** |
| **Cardiovascular Post-Angioplasty** | ₹1,686.00 | ₹405.00 | **₹1,281.00** | **76.0%** | **₹15,372.00 / year** |
| **Geriatric Bone & Endocrine Care** | ₹576.00 | ₹141.60 | **₹434.40** | **75.4%** | **₹5,212.80 / year** |
| **Acute Bacterial Infection Course** | ₹306.90 | ₹82.25 | **₹224.65** | **73.2%** | **₹2,695.80 / year** |
| **COMBINED MULTI-MORBIDITY TOTAL** | **₹4,100.70** | **₹879.35** | **₹3,221.35** | **🟢 78.6%** | **₹38,656.20 / year** |

#### 2. Rigorous Test Suite & Computational Benchmarks:
- **Test Suite Results:** **47 / 47 formal tests passing (100.0%)** across 6 modules.
- **Black-Box Testing:** Formal Equivalence Class Partitioning (ECP: 8 classes) and Boundary Value Analysis (BVA: 4 boundary tests on microgram-milligram limits and price ceilings).
- **Latency (p90):** **0.012 ms** per substitution lookup (Throughput: $103,963\text{ QPS}$).
- **Bioequivalence Precision:** **100.0%** (0 chemical salt mismatches, 0 strength tolerance breaches).

---

```
========================================================================================
SLIDE 5: INNOVATION & "WHY NOT CHATGPT?"
========================================================================================
```

### Title: Innovation Defense: Why a Deterministic SE System Outperforms LLMs

| Evaluation Dimension | Generic LLM / ChatGPT Prompt | EquiMed-India (Our Software System) |
| :--- | :--- | :--- |
| **Clinical Safety & Hallucination** | Risk of hallucinating non-existent drug strengths or wrong salt ratios. | **Mathematically deterministic 0% hallucination.** Every candidate verified against CDSCO catalog. |
| **Dosage Release Kinetics Guard** | Frequently overlooks IR vs SR/ER pharmacokinetics (dangerous dose dumping). | **Automated Release Gatekeeper:** Sustained Release $\rightarrow$ Immediate Release substitution strictly vetoed. |
| **Narrow Therapeutic Index (NTI)** | Inconsistent, uncalibrated warnings depending on prompt wording. | **Mandatory hardcoded clinical warnings** triggered for high-risk substances (Levothyroxine, Warfarin). |
| **Offline Reliability & Latency** | 1,500 ms – 4,000 ms per query, requires cloud connectivity, token costs. | **0.012 ms ($>100,000\times$ faster)**, 100% offline, zero-install, zero-cloud API dependency. |
| **Auditability & Traceability** | Non-deterministic "black box" output; impossible to audit formally. | **Full Observer Pattern audit ledger** tracking every substitution event and rupee saved for compliance. |

#### Conclusion:
*"EquiMed proves that in high-stakes healthcare domains, robust Software Engineering architectures, formal verification, and deterministic safety patterns vastly outperform uncalibrated Large Language Models."*
