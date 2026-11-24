# Software Requirements Specification (SRS)
## EquiMed-India: Deterministic Generic Drug Substitution & Affordability Optimizer

**Standard Compliance:** IEEE Std 830-1998 (with ISO/IEC/IEEE 29148 traceability alignment)  
**Course:** Software Engineering  
**Institution:** Indian Institute of Information Technology (IIIT), Lucknow  
**Document Version:** 2.0.0 (Finalized for 240k+ Catalog & Revamped 2-Section Web UI)  
**Date:** November 25, 2026  
**Status:** Approved / Verified Baseline (`90/90` Automated Tests Passing)

---

## 1. Introduction

### 1.1 Purpose
This Software Requirements Specification (SRS) defines—completely, unambiguously, and verifiably—what the **EquiMed-India** software system shall do and how well it shall perform. It serves as the binding contract among:
- **Clients & End-Users** (patients, caregivers, retail pharmacists, PMBJP Jan Aushadhi staff): to confirm the exact lookup, safety-filtering, and prescription-billing capabilities delivered.
- **Developers**: to understand exact inputs, clinical safety rules, ranking algorithms, and interface contracts without ambiguity.
- **Testers & QA Auditors**: to derive deterministic unit, black-box (ECP/BVA), integration, and API test cases directly from numbered requirements.
- **Project Managers & Academic Evaluators**: to verify scope boundaries, quality attributes, and requirement-to-test traceability.

### 1.2 Scope
**EquiMed-India** is a zero-dependency clinical decision-support and healthcare price-transparency system for the Indian pharmaceutical market. The system ingests and indexes `1,021` curated gold formulations (PMBJP Jan Aushadhi & WHO-GMP generics) alongside the A–Z Indian Medicines Dataset (`253,973` retail rows → `240,199` validated records in SQLite + FTS5), and enables users—via Web UI, REST API, or CLI—to:
1. Search medicines by brand name or active chemical ingredient/synonym.
2. Identify chemically bioequivalent, currently active, lower-cost generic substitutes verified through a 7-rule deterministic safety gate.
3. Rank substitutes by configurable clinical/economic strategies (`max_savings`, `jan_aushadhi`, `balanced`).
4. Build multi-medicine prescription bills comparing branded MRP against generic alternatives under both retail pack/strip rounding and exact unit-cost modes, and print a chemist dispensing slip.
5. Evaluate predefined chronic therapy regimens via CLI and benchmark suites.

**Out of Scope (Explicit Boundaries):**
- Physical pharmacy inventory tracking or point-of-sale billing/payment gateways.
- Replacement of a licensed medical practitioner or pharmacist (all outputs are strictly advisory with mandatory clinical notices on Narrow Therapeutic Index drugs and container-size differences).
- Generative AI / LLM-based drug suggestions (strictly prohibited to preserve zero hallucination).
- Non-allopathic systems of medicine (Ayurveda, Homeopathy, Unani) and non-comparable retail commodities (soaps, shampoos, sachets, cosmetics).

### 1.3 Definitions, Acronyms, and Abbreviations
- **API (Clinical):** Active Pharmaceutical Ingredient — the active chemical salt responsible for therapeutic effect.
- **API (Software):** Application Programming Interface (HTTP/JSON endpoints).
- **BVA:** Boundary Value Analysis (black-box testing technique).
- **CDSCO:** Central Drugs Standard Control Organization (India's national drug regulator).
- **EC / DR / SR / ER / CR / MR / IR:** Enteric Coated / Delayed Release / Sustained Release / Extended Release / Controlled Release / Modified Release / Immediate Release.
- **ECP:** Equivalence Class Partitioning (black-box testing technique).
- **FTS5:** SQLite Full-Text Search version 5 virtual table extension.
- **IEEE 830:** IEEE Recommended Practice for Software Requirements Specifications (`IEEE Std 830-1998`).
- **ISO/IEC/IEEE 29148:** Current international standard superseding IEEE 830 for requirements engineering processes and lifecycle management.
- **NTI:** Narrow Therapeutic Index — medicines where small dosage or blood-concentration variations can cause serious toxicity or therapeutic failure.
- **Pack-Only Forms:** Dosage forms billed and dispensed per container (`SYRUP`, `INHALER`, `INJECTION`, `DROPS`, `OINTMENT`) rather than individual tablets/capsules.
- **PMBJP:** Pradhan Mantri Bhartiya Janaushadhi Pariyojana (Government of India subsidized generic medicine scheme).
- **Quarantine:** Deterministic rejection of incomplete, non-allopathic, or clinically ambiguous raw CSV rows during ETL ingestion so unsafe records never enter the searchable catalog.
- **RTM:** Requirements Traceability Matrix.
- **WHO-GMP:** World Health Organization Good Manufacturing Practices.

### 1.4 References
1. IEEE Std 830-1998: *IEEE Recommended Practice for Software Requirements Specifications*.
2. ISO/IEC/IEEE 29148:2018: *Systems and software engineering — Life cycle processes — Requirements engineering*.
3. Ministry of Health and Family Welfare, Government of India: *Drugs and Cosmetics Act, 1940 and Rules, 1945*.
4. Central Drugs Standard Control Organization (CDSCO): *Guidelines for Bioavailability and Bioequivalence Studies*.
5. Indian Pharmacopoeia Commission (IPC): *Indian Pharmacopoeia Standards*.
6. Sommerville, Ian: *Software Engineering*, 10th Edition, Pearson.

### 1.5 Overview
Section 2 describes the product perspective, major functions, user classes, constraints, and assumptions. Section 3 specifies all external interfaces, testable functional requirements (`FR-01`–`FR-18`), performance targets (`PR-01`–`PR-04`), design constraints (`DC-01`–`DC-04`), and non-functional quality attributes (`NFR-01`–`NFR-08`). Section 4 documents elicitation techniques, IEEE 830 quality compliance, verification/validation practices, and requirement traceability.

---

## 2. Overall Description

### 2.1 Product Perspective
EquiMed-India is a **standalone, self-contained software system** requiring zero third-party runtime packages or external inference APIs. It operates across three logical tiers:

```text
+-------------------------------------------------------------------------+
|                        External Users & Clients                         |
|     [Web Browser (HTTP/HTML)]   [REST Consumers]   [Terminal CLI]       |
+------------------------------------+------------------------------------+
                                     |
+------------------------------------v------------------------------------+
|                      Application & Safety Layer                         |
|  [ThreadingHTTPServer]  [SearchEngine]  [SafetyEngine (7 Rules)]        |
|  [Strategy Rankers]     [PrescriptionOptimizer]  [Event Observers]      |
+------------------------------------+------------------------------------+
                                     |
+------------------------------------v------------------------------------+
|                       Data & Ingestion Layer                            |
|  [SQLite + FTS5 Catalog (240,199 rows)]  <--fallback--  [Curated JSON]  |
|  [ETL & Clinical Quarantine Pipeline (scripts/ingest_az_dataset.py)]    |
+-------------------------------------------------------------------------+
```

### 2.2 Product Functions (High-Level Summary)
1. **Hybrid Dataset Ingestion & Quarantine:** Merge curated gold JSON formulations with the A–Z Indian retail medicines CSV into an atomic SQLite + FTS5 database while quarantining unsafe/ambiguous entries and preserving curated priority.
2. **Multi-Mode Medicine Lookup:** Search brands by exact name, punctuation-normalized name, prefix/FTS5 tokens, or active salt/synonym.
3. **Deterministic Bioequivalence & Discontinued Gate:** Validate every substitute candidate against 7 clinical, regulatory, and economic rules.
4. **Configurable Substitute Ranking:** Sort verified substitutes by Maximum Savings, Jan Aushadhi Priority, or Balanced Quality + Savings.
5. **Interactive Prescription Bill & Chemist Slip:** Manage multi-drug regimens with strip-rounding (`ceil(units / pack_size)`) vs. exact unit billing, browser persistence, and printable chemist slips.
6. **CLI & Chronic Basket Evaluation:** Provide command-line lookup and chronic-therapy basket simulation/benchmarking.

### 2.3 User Characteristics
| User Class | Technical & Domain Expertise | Primary Goals |
| :--- | :--- | :--- |
| **Patients & Caregivers** | Low-to-moderate medical & technical literacy | Understand what salt is in their medicine, find safe cheaper alternatives in plain English, and print a chemist list. |
| **Retail Pharmacists & PMBJP Staff** | High pharmaceutical knowledge; moderate IT familiarity | Verify exact bioequivalence (salts, strengths, release kinetics), check NTI warnings, and compute strip-level bills. |
| **Clinical Auditors & Academic Evaluators** | High software engineering & verification expertise | Inspect deterministic safety rules, verify zero-hallucination guarantees, and audit latency/precision benchmarks. |

### 2.4 Constraints
- **Zero External Dependencies:** Production execution shall rely exclusively on Python 3.10+ standard library modules (including built-in `sqlite3` with FTS5) and browser-native HTML/CSS/JavaScript.
- **No Unverified Tier Fabrication:** Retail rows from the A–Z CSV shall not be assigned `PMBJP_JAN_AUSHADHI` or `WHO_GMP_GENERIC` tiers unless explicitly verified by manufacturer name (`PMBJP`, `BPPI`, `Jan Aushadhi`).
- **Clinical Non-Equivalence Preservation:** Ester/counter-ion variants with distinct pharmacokinetics (e.g., *Metoprolol Succinate* vs. *Metoprolol Tartrate*; *Diclofenac Sodium* vs. *Diclofenac Potassium*) shall never be collapsed into the same canonical key.
- **Container Portability:** Must run as a non-root user (`UID 1000`) listening on environment-configured `PORT` (e.g., `7860` on Hugging Face Spaces, `8000` locally).

### 2.5 Assumptions and Dependencies
- The host Python runtime provides `sqlite3` compiled with FTS5 support (verified on Python 3.13 / SQLite 3.49.1 and `python:3.12-slim`).
- If `data/equimed_catalog.db` is absent at startup, the repository automatically falls back to `data/medicine_catalog.json` (`1,021` curated records).
- Patients consult a licensed medical practitioner or pharmacist prior to switching medications, especially for NTI drugs.

---

## 3. Specific Requirements

### 3.1 External Interfaces

#### 3.1.1 User Interfaces
- **Web Interface (`GET /`):** Two-section responsive single-page application (Light/Dark theme toggle, plain-English copy, dynamic navbar count `{{CATALOG_COUNT}} FORMULATIONS ACTIVE`, Section 1 **Find Cheaper Same-Salt Medicines**, Section 2 **My Medicine Bill & Savings** with print-formatted `@media print` chemist slip).
- **Command-Line Interface (`src/cli.py`):** Subcommands `search <query>`, `substitutes <brand> [--strategy ...]`, and `chronic-baskets [--strategy ...]`, plus `--curated-only`.

#### 3.1.2 Hardware & Software Interfaces
- **Storage Backend:** Local SQLite 3 database (`data/equimed_catalog.db`) with `medicines`, `medicine_salts`, and `medicines_fts` (FTS5) tables; fallback JSON catalogs (`data/medicine_catalog.json`, `data/chronic_baskets.json`); optional raw CSV input (`A_Z_medicines_dataset_of_India.csv`, UTF-8-BOM).
- **Client Browser Persistence:** Browser `localStorage` keys `equimed-theme` and `equimed-cart`.

#### 3.1.3 Communication Interfaces (HTTP / JSON REST API)
| Endpoint | Method | Request Parameters / Body | Response Contract |
| :--- | :--- | :--- | :--- |
| `/` , `/index.html` | `GET` | None | `200 text/html` rendered with live formulation count |
| `/api/ui-config` | `GET` | None | `200 application/json` presets, strategies, form/release/tier maps, regimen bounds, cart config |
| `/api/search` | `GET` | `q` (string), `limit` (int, default `10`) | `200 application/json` array of matching `Medicine` dicts |
| `/api/substitutes` | `GET` | `brand` (required), `strategy` (`max_savings`\|`jan_aushadhi`\|`balanced`) | `200 application/json` (or `400` if missing `brand`) original profile + ranked matches + plain-English labels |
| `/api/optimize-cart` | `POST` | JSON `{ "strategy": str, "items": [...] }` | `200 application/json` (or `400` if invalid/oversized `>1MB`) dual unit + pack bill & alerts |
| `/api/baskets` | `GET` | None | `200 application/json` list of predefined chronic baskets |
| `/api/optimize-basket` | `GET` | `basket_id`, `strategy` | `200 application/json` (or `404` if unknown basket) monthly/annual simulation |
| `/api/metrics` | `GET` | None | `200 application/json` `catalog_count`, `savings`, `safety`, `audit_entries_count` |

---

### 3.2 Functional Requirements

#### A. Data Ingestion, Cleaning & Repository Indexing
- **FR-01 (Priority: High — Curated-First Hybrid Catalog):** The system shall load all curated records from `data/medicine_catalog.json` prior to A–Z retail ingestion so curated `PMBJP_JAN_AUSHADHI` and `WHO_GMP_GENERIC` records take precedence during `(normalized_brand, salt_fingerprint)` deduplication.
- **FR-02 (Priority: High — Strict Clinical Quarantine):** During CSV ingestion, the system shall quarantine—and exclude from the searchable database—any row that: (a) has missing brand name, (b) has `type` other than `allopathy`, (c) has missing, non-numeric, or `<= 0` MRP, (d) has missing chemical composition or bare salts lacking numeric strength, (e) indicates truncated 3+ salts (`comp2` ending in `+`, `...`, `etc`, or `and others`), (f) specifies an unsupported/unrecognized dosage form (e.g., `soap`, `shampoo`, `sachet`, `lotion`, `powder` other than dry syrup/injection), or (g) has an invalid oral-solid pack count (`<= 0` or `> 1000`).
- **FR-03 (Priority: High — Nested Parentheses & Compound Unit Parsing):** The ingestion parser shall extract the final parenthesized numeric strength on salts with nested descriptions (e.g., `Cholecalciferol (Vitamin D3) (60000IU)`), handle comma-formatted numbers and leading decimals, and normalize units (`g`/`mcg`/`µg`/`ug` → `mg`, `mg/5ml` → `mg/ml`, `mg/puff` → `mcg/puff`, `mcg/spray`, `% w/v`, `% w/w`).
- **FR-04 (Priority: High — Pack-Size Price Normalization):** For `TABLET` and `CAPSULE` formulations, the system shall compute `price_per_unit = round(mrp / pack_size, 4)` (supporting multi-strip boxes such as `10 strips of 10 tablets` = `100`); for pack-only forms (`SYRUP`, `INHALER`, `INJECTION`, `DROPS`, `OINTMENT`), the system shall preserve `pack_size = 1` and `price_per_unit = mrp`.
- **FR-05 (Priority: Medium — Release Kinetics & Brand Prefix Guard):** The ingestion parser shall classify `SR`, `ER`/`XR`/`XL`/`PR`, `CR`, `MR`, and `EC`/`DR` release mechanisms while ensuring brand prefixes containing `Dr.` (e.g., `Dr. Morepen`, `Dr. Reddy's`) are not misclassified as `ENTERIC_COATED`.
- **FR-06 (Priority: High — Graceful Fallback):** If `data/equimed_catalog.db` does not exist at startup (or `--curated-only` is specified), the system shall automatically load `data/medicine_catalog.json` into the in-memory indexed repository.

#### B. Search & Clinical Safety Validation
- **FR-07 (Priority: High — Multi-Tier Brand & Salt Search):** The system shall resolve medicine queries across exact brand name, punctuation/hyphen-insensitive brand name, prefix matches, FTS5 multi-token matches, and canonical active-salt synonyms (e.g., `Acetaminophen` → `Paracetamol`).
- **FR-08 (Priority: High — Discontinued Drug Policy [Rule 0b]):** The system shall index discontinued A–Z medicines (`Is_discontinued = True`) so patients can search them as prescribed input and view active replacements, and shall unconditionally reject any candidate with `is_discontinued == True` from being recommended as a substitute.
- **FR-09 (Priority: High — Exact Chemical & Strength Equivalence [Rules 1–2]):** The safety engine shall approve a substitute only when the canonical active salt set and normalized strength per salt (`±0.001` tolerance) match the prescribed medicine identically, independent of salt ordering.
- **FR-10 (Priority: High — Dosage Form & Container Warnings [Rule 3]):** The safety engine shall reject incompatible dosage forms (e.g., `TABLET` vs. `SYRUP`), allow `TABLET` ↔ `CAPSULE` interchange only with a pharmacological variation warning (`is_exact_bioequivalent = False`), and emit a soft container-size warning when pack-only substitutes differ in volume/doses (e.g., `60ml` vs. `100ml`).
- **FR-11 (Priority: High — Release Kinetics & NTI Protection [Rules 4–5]):** The safety engine shall symmetrically reject mismatches involving `SUSTAINED_RELEASE`, `EXTENDED_RELEASE`, `CONTROLLED_RELEASE`, `MODIFIED_RELEASE`, or `ENTERIC_COATED` vs. `IMMEDIATE_RELEASE`, and shall attach a mandatory physician-monitoring caution whenever any active ingredient is in `NTI_SUBSTANCES` or flagged `is_narrow_therapeutic_index`.
- **FR-12 (Priority: High — Economic Sanity Check [Rule 6]):** The safety engine shall reject any candidate whose `price_per_unit` exceeds the prescribed medicine's `price_per_unit`.

#### C. Ranking, Web UI & Prescription Bill Optimization
- **FR-13 (Priority: High — Strategy-Based Ranking):** The search engine shall rank verified substitutes according to the user-selected strategy (`MaxSavingsStrategy`, `JanAushadhiFirstStrategy`, or `ReputationBalancedStrategy`).
- **FR-14 (Priority: Medium — Backend-Driven UI Configuration):** The server shall expose `/api/ui-config` so the Web UI dynamically populates verified example chips, default query, strategy options, regulatory tier labels, dosage/release labels, and numeric regimen bounds without hardcoded frontend duplicates.
- **FR-15 (Priority: High — Plain-English Lookup Presentation):** The Web UI shall display the searched medicine's active salt, plain-English form/release labels, per-unit price, and verified cheaper alternatives table with dynamic unit headings (`Price per Tablet` / `Price per Bottle`), accurate pack descriptions (`pack_size_label`), and clear NTI/discontinued badges.
- **FR-16 (Priority: High — Multi-Medicine Bill & Strip Rounding):** The prescription optimizer (`POST /api/optimize-cart`) shall compute both exact unit cost (`units_per_day * duration_days * price_per_unit`) and real retail strip/pack cost (`ceil(total_units / pack_size) * mrp`), allow switching alternatives or keeping the prescribed brand (`KEEP_ORIGINAL`), persist cart state in `localStorage`, and support a print-formatted chemist slip.
- **FR-17 (Priority: Low — Observer Telemetry):** The search engine shall emit `SUBSTITUTION_FOUND`, `SUBSTITUTION_REJECTED`, `SAFETY_WARNING`, and `BASKET_OPTIMIZED` events to bounded observers (`maxlen=10000`) without interrupting substitution execution if an observer fails.
- **FR-18 (Priority: Medium — CLI & Chronic Basket Simulation):** The CLI (`src/cli.py`) shall support brand search, substitute lookup, and predefined chronic therapy basket savings reports.

---

### 3.3 Performance Requirements
- **PR-01:** Under the full ~240k-formulation SQLite + FTS5 catalog, 90th-percentile (`p90`) substitute lookup latency across 1,000 queries shall be **`< 5.0 ms`** (verified at **`3.522 ms`** p90, `306.5 QPS`).
- **PR-02:** Full ETL ingestion and SQLite + FTS5 index compilation of ~254k raw CSV rows shall complete within **`120 seconds`** on standard desktop hardware (verified at **`70.56 s`**).
- **PR-03:** Web search autocomplete shall debounce keystrokes by **`180 ms`** and cancel superseded in-flight HTTP requests via `AbortController`.
- **PR-04:** In-memory audit and safety-alert observer logs shall remain bounded to at most **`10,000` entries** via `collections.deque` to prevent unbounded RAM growth.

---

### 3.4 Design Constraints
- **DC-01:** Zero third-party Python dependencies (`pip` packages prohibited in runtime/ETL).
- **DC-02:** All SQLite index rebuilds (`scripts/ingest_az_dataset.py`) shall write to a temporary file (`.db.tmp`) and atomically replace the target `.db` only after successful completion.
- **DC-03:** Concurrent Web UI requests shall be handled via `ThreadingHTTPServer` paired with thread-local read-only SQLite connections (`threading.local()`).
- **DC-04:** All user-supplied or database-sourced text rendered in the Web UI DOM shall be HTML-escaped (`escapeHtml()`) to prevent XSS injection.

---

### 3.5 Quality Attributes (Non-Functional Requirements)
- **NFR-01 (Performance):** Lookup response time shall achieve `< 5 ms` p90 on 240k+ records (see `PR-01`).
- **NFR-02 (Security):** The system shall sanitize all FTS5 query tokens (`re.findall(r"[a-z0-9]+", ...)`), use parameterized SQLite queries exclusively (preventing SQL injection), reject HTTP POST bodies exceeding `1,000,000` bytes, and HTML-escape all dynamic UI strings.
- **NFR-03 (Usability):** The Web UI shall present all medical terms, badges, pack quantities, and savings in plain, non-technical English usable without formal pharmacy training, and support keyboard `Enter` submission and Light/Dark themes.
- **NFR-04 (Reliability / Zero Hallucination):** The system shall achieve **100.00% bioequivalence precision** (`0` chemical salt mismatches, `0` strength tolerance breaches, `0` discontinued substitute leaks, and `0` invented drug entities) across stratified audits.
- **NFR-05 (Scalability):** The repository shall support 240,000+ records with O(1) priority-tier caching and single-equality composite B-tree index queries (`idx_medicines_sub_lookup`) without full-table Python scans.
- **NFR-06 (Maintainability):** Domain models, safety rules, ranking strategies, repository backends, and UI configuration shall remain cleanly separated across modular layers (`models`, `safety_engine`, `strategy`, `repository`, `search_engine`, `optimizer`, `server`).
- **NFR-07 (Availability / Fault Tolerance):** The application shall remain operational on fresh clones or missing `.db` builds by falling back automatically to `data/medicine_catalog.json`, and observer failures shall never crash core search execution.
- **NFR-08 (Portability):** The system shall run identically on Windows, Linux, and Docker containers (`python:3.12-slim`, UID `1000`, configurable `PORT` and `EQUIMED_SQLITE_MMAP_MB`).

---

## 4. Elicitation, IEEE 830 Quality Verification & Traceability

### 4.1 Elicitation Techniques Applied
- **Document Analysis:** Review of CDSCO bioequivalence norms, Indian Pharmacopoeia dosage/release classifications, PMBJP Jan Aushadhi pricing structures, and the A–Z Indian Medicines CSV schema (`253,973` rows).
- **Observation & Prototyping:** Iterative browser walkthroughs of Section 1 and Section 2 UI flows, uncovering and eliminating jargon (`Originator Unit Price`, `Pack of 1`, `NTI`) and stale hardcoded defaults.

### 4.2 IEEE 830 Characteristics Checklist
| Characteristic | How Satisfied in This SRS |
| :--- | :--- |
| **Correct** | Every FR, PR, and schema detail reflects verified codebase behavior and actual benchmark/ingestion telemetry. |
| **Unambiguous** | All mandatory requirements use `"shall"` with explicit numeric tolerances (`±0.001`), pack formulas (`ceil`), and rule criteria. |
| **Complete** | Covers ETL quarantine, SQLite + JSON fallback, all 7 clinical rules, 3 strategies, Web UI, CLI, REST API, and Docker portability. |
| **Consistent** | Section 2 summary functions align 1-to-1 with Section 3 `FR`/`PR`/`NFR` statements and out-of-scope boundaries. |
| **Ranked** | Each `FR` is explicitly prioritized (`High`, `Medium`, `Low`). |
| **Verifiable** | Every requirement maps to concrete automated tests (`run_tests.py`) or quantitative benchmarks (`benchmark.py`). |
| **Modifiable** | Modular numbered sections (`FR-01`..`FR-18`, `PR-01`..`PR-04`, `NFR-01`..`NFR-08`) with zero requirement duplication. |
| **Traceable** | Bidirectional traceability maintained below and in [TRACEABILITY_MATRIX.md](file:///c:/Users/91994/Desktop/CS/equimed-india/docs/TRACEABILITY_MATRIX.md). |

### 4.3 Verification & Validation Traceability Summary
- **Verification (*"Are we building the specification right?"*):** Requirements walkthroughs against IEEE 830 checklist and `python -W error::SyntaxWarning run_tests.py` (**90/90 tests passing**, `0` warnings).
- **Validation (*"Are we building the right system?"*):** End-to-end live testing against `240,199` indexed medicines (`benchmark.py`: **3.522 ms p90**, **100.00% precision**) and browser verification on `http://localhost:8000`.

| Requirement IDs | Implementation Module(s) | Automated Verification Suite |
| :--- | :--- | :--- |
| `FR-01`–`FR-05`, `DC-02` | [ingest_az_dataset.py](file:///c:/Users/91994/Desktop/CS/equimed-india/scripts/ingest_az_dataset.py) | `tests/test_az_ingestion.py` |
| `FR-06`–`FR-07`, `PR-01`, `NFR-05`, `NFR-07` | [repository.py](file:///c:/Users/91994/Desktop/CS/equimed-india/src/repository.py), [search_engine.py](file:///c:/Users/91994/Desktop/CS/equimed-india/src/search_engine.py) | `tests/test_az_ingestion.py`, `tests/test_search_engine.py`, `benchmark.py` |
| `FR-08`–`FR-12`, `NFR-04` | [safety_engine.py](file:///c:/Users/91994/Desktop/CS/equimed-india/src/safety_engine.py), [models.py](file:///c:/Users/91994/Desktop/CS/equimed-india/src/models.py) | `tests/test_safety_engine.py`, `tests/test_blackbox.py`, `tests/test_models.py` |
| `FR-13` | [strategy.py](file:///c:/Users/91994/Desktop/CS/equimed-india/src/strategy.py) | `tests/test_strategies.py` |
| `FR-14`–`FR-16`, `PR-03`, `DC-03`–`DC-04`, `NFR-02`–`NFR-03` | [server.py](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py), [optimizer.py](file:///c:/Users/91994/Desktop/CS/equimed-india/src/optimizer.py) | `tests/test_server.py`, `tests/test_optimizer.py` |
| `FR-17`, `PR-04` | [observer.py](file:///c:/Users/91994/Desktop/CS/equimed-india/src/observer.py) | `tests/test_az_ingestion.py`, `tests/test_search_engine.py` |
| `FR-18` | [cli.py](file:///c:/Users/91994/Desktop/CS/equimed-india/src/cli.py) | `tests/test_cli_and_integration.py` |
| `DC-01`, `NFR-08` | [Dockerfile](file:///c:/Users/91994/Desktop/CS/equimed-india/Dockerfile), [server.py](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py) | Full stdlib test run (`90/90`) + Docker config check |
