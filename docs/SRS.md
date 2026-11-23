# Software Requirements Specification (SRS)
## Generic Drug Substitution & Affordability Optimizer (EquiMed-India)

**Document Reference:** IEEE Std 830-1998 Compliant  
**Course:** Software Engineering (Credits: 4)  
**Institution:** Indian Institute of Information Technology (IIIT), Lucknow  
**Version:** 1.0.0  
**Date:** November 23, 2026  
**Status:** Approved / Release Candidate  

---

## 1. Introduction

### 1.1 Purpose
This Software Requirements Specification (SRS) defines the functional, clinical, performance, and structural software requirements for **EquiMed-India**, an automated, deterministic Generic Drug Substitution and Out-of-Pocket Healthcare Affordability Optimizer. The document targets software engineers, clinical validators, academic evaluators, and system auditors.

### 1.2 Scope
EquiMed-India is an engineering-grade clinical decision support software designed for the Indian healthcare ecosystem. The system accepts branded pharmaceutical drug names or multi-salt prescription baskets, normalizes Active Pharmaceutical Ingredients (APIs) and dosage strengths under Indian Pharmacopoeia standards, performs deterministic bioequivalence verification (filtering incompatible dosage forms and hazardous release kinetics mismatches), and recommends verified generic equivalents (including PMBJP Jan Aushadhi and WHO-GMP certified generics) ranked by customizable economic optimization strategies.

**Out of Scope:**
- Physical dispensing of pharmaceutical inventory.
- Replacement of certified medical practitioners (system functions strictly as clinical/economic advisory with mandatory disclaimers).
- Direct e-commerce payment gateway processing.

### 1.3 Definitions, Acronyms, and Abbreviations
- **API:** Active Pharmaceutical Ingredient (the therapeutically active salt).
- **BVA:** Boundary Value Analysis.
- **CDSCO:** Central Drugs Standard Control Organization (India).
- **ECP:** Equivalence Class Partitioning.
- **ER / SR / CR / IR:** Extended Release / Sustained Release / Controlled Release / Immediate Release.
- **IEEE 830:** Standard Recommended Practice for Software Requirements Specifications.
- **NTI:** Narrow Therapeutic Index (drugs where minor concentration changes cause severe toxicity).
- **PMBJP:** Pradhan Mantri Bhartiya Janaushadhi Pariyojana (Govt of India generic pharmacy scheme).
- **RTM:** Requirements Traceability Matrix.
- **WHO-GMP:** World Health Organization Good Manufacturing Practices.

### 1.4 References
1. IEEE Std 830-1998: *IEEE Recommended Practice for Software Requirements Specifications*.
2. Ministry of Health and Family Welfare, Government of India: *Drugs and Cosmetics Act, 1940 and Rules, 1945*.
3. Central Drugs Standard Control Organization (CDSCO): *Guidelines for Bioavailability & Bioequivalence Studies*.
4. Sommerville, Ian: *Software Engineering*, 10th Edition, Pearson.
5. Gamma, E., Helm, R., Johnson, R., Vlissides, J.: *Design Patterns: Elements of Reusable Object-Oriented Software*.

---

## 2. Overall Description

### 2.1 Product Perspective
In India, out-of-pocket health expenditure constitutes over 50–60% of total health spending, with pharmaceutical purchases representing the largest single component. Branded innovator medicines are frequently marketed at 70% to 90% markups over chemically identical generic equivalents. EquiMed-India acts as an autonomous middleware verifying chemical composition, bioequivalence, and regulatory certification to systematically reduce recurring household pharmaceutical expenditures.

```
+--------------------------------------------------------------+
|                     User Interface Layer                     |
|           [CLI Interactive Tool]   [Embedded Web UI]         |
+------------------------------+-------------------------------+
                               |
+------------------------------v-------------------------------+
|               Business Logic & Safety Engine                 |
|  [Salt Normalizer] [Safety Engine] [Strategy Pattern Engine] |
|                 [Prescription Optimizer]                     |
+------------------------------+-------------------------------+
                               |
+------------------------------v-------------------------------+
|                      Data & Audit Layer                      |
|  [Inverted Fingerprint Index] [Observer Telemetry & Audit]   |
|            [Indian Pharmacopoeia Medicine Catalog]           |
+--------------------------------------------------------------+
```

### 2.2 Product Functions
1. **Chemical Salt & Synonym Normalization:** Canonicalization of active salt nomenclature (e.g., "Metformin Hydrochloride" $\rightarrow$ "Metformin").
2. **Order-Independent Combination Fingerprinting:** Deterministic hashing of multi-ingredient formulations independent of input salt ordering.
3. **Bioequivalence & Clinical Safety Verification:** Multi-stage filtering preventing dangerous dosage-form or release-kinetics mismatches (e.g. blocking IR substitution for SR).
4. **Narrow Therapeutic Index (NTI) Protection:** Automated warnings for critical-window medications (Levothyroxine, Warfarin).
5. **Economic Optimization & Strategy Ranking:** Strategy pattern ranking (Maximum Savings, Government Jan Aushadhi Priority, Balanced Quality-Price).
6. **Chronic Multi-Morbidity Basket Simulation:** Aggregated 30-day and 365-day household financial savings projection across co-morbidities.
7. **Observer-Driven Telemetry:** Decoupled audit logging and economic impact metrics tracking.

### 2.3 User Classes and Characteristics
- **Chronic Care Patients & Families:** Non-technical consumers seeking verified affordable alternatives for recurring monthly prescriptions.
- **Retail Pharmacists:** Licensed dispensers seeking CDSCO-approved generic alternatives with verified bioequivalence.
- **Academic Evaluators / Software Auditors:** Technical reviewers verifying IEEE 830 compliance, design patterns, and black-box/white-box test coverage.

### 2.4 Operating Environment
- Operating System: OS-agnostic (macOS, Linux, Windows).
- Runtime: Python 3.9+ standard library (zero external dependencies required for execution).
- Memory Footprint: $< 50\text{ MB}$ RAM.
- Execution Latency: Sub-millisecond ($< 0.1\text{ ms}$) deterministic candidate retrieval.

### 2.5 Design and Implementation Constraints
- **Zero Hallucination Constraint:** The system must never synthesize or infer non-existent drug compositions. Every substitution candidate must strictly exist in the validated catalog.
- **Zero-Dependency Core:** Execution must not rely on fragile external package managers or remote LLM cloud endpoints to guarantee 100% offline uptime and zero API latency.
- **Design Pattern Utilization:** Must explicitly incorporate Gang of Four (GoF) patterns (Strategy, Observer, Repository, Factory).

---

## 3. Specific System Features & Functional Requirements

### REQ-1: Drug Query & Brand Identification
- **Description:** System shall accept user queries as brand name strings or primary medicine identifiers.
- **Input:** Brand query (e.g., `"Telma 40"`, `"Augmentin 625 Duo"`).
- **Processing:** Normalize query, query O(1) exact brand index, fallback to prefix/substring search.
- **Output:** Matched `Medicine` object or clean error notification.
- **Priority:** High.

### REQ-2: Active Salt Normalization & Unit Harmonization
- **Description:** System shall normalize constituent salts into canonical chemical bases and convert diverse strength units into standardized milligrams (mg) or International Units (IU).
- **Input:** Raw salt components (e.g., `Amoxicillin Trihydrate 0.5g`).
- **Processing:** Synonym lookup table conversion and unit conversion ($0.5\text{ g} \rightarrow 500\text{ mg}$; $50\text{ mcg} \rightarrow 0.05\text{ mg}$).
- **Output:** Canonicalized `SaltComponent` collection.
- **Priority:** Critical.

### REQ-3: Order-Independent Combination Salt Fingerprinting
- **Description:** System shall generate identical chemical fingerprints for combination pharmaceuticals regardless of component entry order.
- **Input:** Constituent salts in arbitrary order.
- **Processing:** Lexicographical sort of canonical salt keys followed by concatenation with dosage form and release type.
- **Output:** Deterministic fingerprint string (e.g., `amoxicillin:500.0:mg|clavulanic acid:125.0:mg#TABLET#IMMEDIATE_RELEASE`).
- **Priority:** High.

### REQ-4: Clinical Bioequivalence & Safety Validation
- **Description:** System shall validate substitution safety using a 6-tier deterministic rule hierarchy.
- **Rules:**
  1. Identical active chemical salts (no missing, no extra ingredients).
  2. Identical normalized active strength per salt ($\pm 0.001\text{ mg}$ tolerance).
  3. Dosage form compatibility (reject Tablet $\rightarrow$ Syrup; flag Tablet $\leftrightarrow$ Capsule).
  4. Release kinetics safety (strictly reject Sustained Release $\rightarrow$ Immediate Release).
  5. Narrow Therapeutic Index (NTI) mandatory clinical alert generation.
  6. Economic ceiling check (strictly reject substitute if unit price exceeds original brand).
- **Output:** `SafetyVerdict` with boolean pass/fail status and warning list.
- **Priority:** Critical.

### REQ-5: Strategy-Driven Substitution Prioritization
- **Description:** System shall rank verified candidates using interchangeable algorithmic strategies via the GoF Strategy Pattern.
- **Strategies Supported:**
  - `MaxSavingsStrategy`: Order by descending percentage cost reduction.
  - `JanAushadhiFirstStrategy`: Order PMBJP government generic stores first (+200 score bonus).
  - `ReputationBalancedStrategy`: Multi-attribute scoring ($65\%$ price savings + $35\%$ regulatory tier score).
- **Output:** Ranked list of `SubstitutionMatch` objects.
- **Priority:** High.

### REQ-6: Multi-Drug Prescription & Chronic Basket Optimization
- **Description:** System shall evaluate composite prescriptions containing multiple line items, calculating individual and aggregate monthly and annual financial savings.
- **Input:** `PrescriptionBasket` containing multiple items with daily unit frequencies.
- **Processing:** Per-item optimal generic resolution, cost summation, savings percentage derivation, annual projection ($\text{Monthly} \times 12$).
- **Output:** `BasketOptimizationResult` with line-by-line breakdown and aggregate statistics.
- **Priority:** High.

### REQ-7: Decoupled Telemetry & Audit Logging (Observer Pattern)
- **Description:** System shall record clinical query events, safety rejections, NTI warnings, and cumulative consumer savings without coupling business logic to logging implementations.
- **Processing:** Subject notifications on `SUBSTITUTION_FOUND`, `SUBSTITUTION_REJECTED`, `SAFETY_WARNING`, `BASKET_OPTIMIZED`.
- **Output:** Queryable audit logs and running economic metrics.
- **Priority:** Medium.

### REQ-8: Dual Interface Access (CLI & Embedded REST/Web)
- **Description:** System shall expose all engine capabilities via both an interactive ANSI terminal CLI and a zero-dependency local HTTP REST API / responsive Web GUI.
- **Priority:** Medium.

---

## 4. Non-Functional Requirements (NFRs)

### NFR-1: Performance & Algorithmic Latency
- The system shall execute single-brand candidate lookups in less than $1.0\text{ ms}$ under median load and less than $5.0\text{ ms}$ at 99th percentile (p99).
- Multi-item chronic basket optimization shall execute in $< 10.0\text{ ms}$.

### NFR-2: Clinical Safety & Zero-Tolerance Integrity
- The system shall produce **zero (0%) false-positive bioequivalence errors**. Under no circumstance shall a chemically mismatched or dosage-clashing substitute be marked as safe.

### NFR-3: Zero Cloud/Network Dependency & Privacy
- All matching, validation, and optimization logic shall execute purely locally on the host machine. No patient prescription data shall be transmitted across networks.

### NFR-4: Portability & Zero-Install Execution
- The codebase shall run on any system possessing standard Python 3.9+ without requiring third-party library installations via `pip`.

### NFR-5: Testability & Formal Verification
- The codebase shall achieve $> 90\%$ statement and branch test coverage across all domain and algorithmic modules, with formal test cases covering Equivalence Class Partitioning and Boundary Value Analysis.

---

## 5. Software Requirements Traceability

| Requirement ID | Description | Architectural Component | Verification Test Suite |
| :--- | :--- | :--- | :--- |
| **REQ-1** | Drug Query & Brand Identification | `MedicineRepository` | `test_search_engine.py`, `test_cli_and_integration.py` |
| **REQ-2** | Salt & Strength Normalization | `SafetyEngine` | `test_safety_engine.py`, `test_blackbox.py` |
| **REQ-3** | Invariant Salt Fingerprinting | `Medicine.salt_fingerprint` | `test_models.py` |
| **REQ-4** | 6-Tier Bioequivalence Safety Engine | `SafetyEngine` | `test_safety_engine.py`, `test_blackbox.py` |
| **REQ-5** | Strategy-Driven Ranking | `src.strategy.*` | `test_strategies.py` |
| **REQ-6** | Chronic Prescription Optimization | `PrescriptionOptimizer` | `test_optimizer.py`, `test_cli_and_integration.py` |
| **REQ-7** | Observer Telemetry & Audit | `src.observer.*` | `test_search_engine.py` |
| **REQ-8** | CLI & Embedded HTTP Server | `src.cli`, `src.server` | `test_cli_and_integration.py` |

---
**Approved by:** Academic Project Evaluation Board, Software Engineering Laboratory, IIIT Lucknow.
