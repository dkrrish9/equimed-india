# EquiMed-India

### Deterministic Generic Drug Substitution & Healthcare Affordability Engine

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-66%20passed%20%7C%200%20failed-brightgreen.svg)]()
[![Catalog](https://img.shields.io/badge/catalog-611%20formulations-blue.svg)]()
[![Therapy Baskets](https://img.shields.io/badge/chronic%20baskets-28%20scenarios-teal.svg)]()
[![Dependencies](https://img.shields.io/badge/dependencies-zero%20(stdlib)-lightgrey.svg)]()

**EquiMed-India** is a zero-dependency clinical decision-support and price-transparency engine for the Indian pharmaceutical market. It matches branded prescriptions against chemically identical **CDSCO-approved** and **PMBJP Jan Aushadhi** generic equivalents while enforcing strict bioequivalence, dosage-form, release-kinetics, and Narrow Therapeutic Index (NTI) safety checks.

---

## Overview

In India, out-of-pocket expenditure accounts for the majority of household healthcare spending, with recurring chronic-care medications often carrying 70%–90% brand markups over identical generic formulations. EquiMed-India addresses this deterministically—without external APIs or generative model hallucinations:

1. **Canonical Salt & Strength Normalization:** Maps salt counter-ions and synonyms (e.g., *Metformin Hydrochloride* → *Metformin*, *Potassium Clavulanate* → *Clavulanic Acid*, *Levothyroxine Sodium* → *Thyroxine Sodium*), harmonizes units (`g` / `mcg` / `µg` → `mg`), and aggregates duplicate active ingredients.
2. **Order-Independent Chemical Fingerprinting:** Generates invariant keys (`<sorted_salts>#<dosage_form>#<release_type>`) so multi-salt combination formulations resolve consistently regardless of salt ordering.
3. **6-Rule Bioequivalence & Safety Gate:** Enforces exact active-salt and strength matching (`±0.001` tolerance), blocks incompatible dosage forms and dangerous release-kinetics downgrades (such as *Sustained Release* → *Immediate Release* dose-dumping or *Enteric Coated* → *Immediate Release* acid degradation), flags Narrow Therapeutic Index (NTI) drugs, and rejects candidates priced above the reference brand.
4. **Configurable Ranking Strategies:** Ranks verified substitutes by pure cost reduction (`max_savings`), government PMBJP Jan Aushadhi subsidy priority (`jan_aushadhi`), or a weighted savings-plus-certification score (`balanced`).
5. **Chronic Regimen Optimizer:** Evaluates multi-drug prescriptions across 30-day and 365-day horizons, surfacing item-level substitutions, clinical alerts, and safe fallbacks when no generic equivalent exists.

---

## Core Capabilities

- **Dual-Index In-Memory Repository:** Constant-time `O(1)` lookup by medicine ID, normalized exact brand name, and chemical salt fingerprint, backed by an inverted constituent-salt index (`_by_salt`) to surface valid oral-solid alternatives (e.g., `TABLET` ↔ `CAPSULE`) for safety evaluation.
- **Clinical Guardrails:**
  - Hardcoded NTI monitoring alerts for *Thyroxine Sodium*, *Warfarin*, *Digoxin*, *Lithium*, *Phenytoin*, *Theophylline*, and *Carbamazepine* (plus per-record `is_narrow_therapeutic_index` flags).
  - Controlled-release protection across `SUSTAINED_RELEASE`, `EXTENDED_RELEASE`, `CONTROLLED_RELEASE`, and `ENTERIC_COATED` formulations.
  - Non-fatal pharmacological warning when substituting between `TABLET` and `CAPSULE` (`is_exact_bioequivalent = False`).
- **Event Telemetry & Audit Ledger:** Observer-driven tracking (`AuditLogObserver`, `SavingsTrackerObserver`, `SafetyAlertObserver`) capturing query counts, cumulative savings, NTI alerts, and safety rejections without coupling to core search logic.
- **Interactive Web Console & REST API:** Zero-dependency HTTP server (`http.server`) serving a responsive Light/Dark-themed web UI with live brand autocomplete, quick formulation presets, strategy switching, and a chronic therapy simulator, alongside CORS-enabled JSON endpoints.
- **Interactive CLI:** Terminal interface for brand lookup, substitute ranking, and chronic basket benchmarking.

---

## Architecture

EquiMed-India is structured as a three-layer modular Python package:

```text
Presentation Layer
├── src/cli.py              # Argparse CLI (search, substitutes, chronic-baskets)
└── src/server.py           # Embedded HTTP REST API & single-page Web UI

Business Logic Layer
├── src/search_engine.py    # Facade & ObservableSubject orchestrating lookup, safety, and ranking
├── src/safety_engine.py    # Salt/unit normalization, bioequivalence rules, and NTI guard
├── src/strategy.py         # Ranking strategies (MaxSavings, JanAushadhiFirst, ReputationBalanced)
└── src/optimizer.py        # Multi-drug chronic prescription optimizer (30-day & annual projections)

Data & Telemetry Layer
├── src/models.py           # Domain dataclasses & enums (Medicine, SaltComponent, SafetyVerdict, etc.)
├── src/repository.py       # In-memory multi-index repository (ID, brand, fingerprint, inverted salt)
└── src/observer.py         # AuditLogObserver, SavingsTrackerObserver, SafetyAlertObserver
```

### Why Deterministic Rules Instead of Generative LLMs?

| Dimension | Generative LLM | EquiMed-India |
| :--- | :--- | :--- |
| **Hallucination Risk** | Can invent non-existent strengths, salts, or prices | **0%** — every result is strictly grounded in `data/medicine_catalog.json` |
| **Release Kinetics Safety** | May overlook SR/ER/CR/EC vs. IR distinctions | **Enforced** — incompatible release kinetics are deterministically rejected |
| **NTI Safeguards** | Inconsistent warnings | **Mandatory alerts** on all NTI compounds and flagged products |
| **Latency & Cost** | ~1,500–4,000 ms/call, network & API costs | **0.052 ms (p90)**, ~38,500 QPS, 100% offline, zero API fees |
| **Auditability** | Stochastic black box | **Deterministic** verdicts with structured observer audit logs |

---

## Empirical Benchmarks & Verification

Verified locally via `python3 run_tests.py` and `python3 benchmark.py` against **611 formulations** across **128 therapeutic categories** and **28 chronic therapy baskets**:

- **Test Suite:** **66 / 66 tests passing (100%)** in **~74 ms** (unit, integration, REST API, equivalence class partitioning, and boundary value analysis).
- **Lookup Latency (1,000 iterations):**
  - **p50:** `0.024 ms` | **p90:** `0.052 ms` | **p99:** `0.063 ms` | **Mean:** `0.026 ms`
  - **Throughput:** **`38,508.7 QPS`**
- **Bioequivalence Precision:** **`100.00%`** across `612` evaluated candidates (`0` salt mismatches, `0` strength breaches, `0` fabricated entities).
- **Patient Savings Across 28 Chronic Baskets:** **`82.8%` overall cost reduction** (`₹59,368.99/mo` branded vs. `₹10,203.00/mo` generic).

Representative scenarios from `benchmark.py`:

| Basket | Therapy Profile | Branded / Mo | Generic / Mo | Monthly Savings | Savings % | Annual Savings |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `BASKET-01` | Elderly Diabetic & Hypertensive (Age 62) | ₹1,531.80 | ₹250.50 | ₹1,281.30 | 83.7% | ₹15,375.60 |
| `BASKET-02` | Cardiovascular Secondary Prevention (Post-Stent) | ₹1,686.00 | ₹405.00 | ₹1,281.00 | 76.0% | ₹15,372.00 |
| `BASKET-03` | Geriatric Bone & Endocrine Care | ₹600.00 | ₹90.60 | ₹509.40 | 84.9% | ₹6,112.80 |
| `BASKET-04` | Acute Bacterial Infection & Fever Course | ₹381.99 | ₹97.30 | ₹284.69 | 74.5% | ₹3,416.28 |
| **All 28** | **Combined Multi-Morbidity Benchmark** | **₹59,368.99** | **₹10,203.00** | **₹49,165.99** | **82.8%** | **₹589,991.88** |

---

## Project Structure

```text
.
├── README.md
├── benchmark.py                      # Latency, bioequivalence precision, and basket savings benchmark
├── run_tests.py                      # Automated unittest runner
├── data/
│   ├── medicine_catalog.json         # 611 Indian branded & generic formulations
│   └── chronic_baskets.json          # 28 chronic multi-morbidity therapy regimens
├── docs/                             # Architecture, SRS, and traceability documentation
├── src/
│   ├── __init__.py
│   ├── models.py                     # Domain models, enums, and salt_fingerprint()
│   ├── safety_engine.py              # Clinical validation, normalization, and NTI rules
│   ├── strategy.py                   # Ranking strategy implementations and factory
│   ├── observer.py                   # Audit, savings, and safety telemetry observers
│   ├── repository.py                 # Multi-index in-memory medicine repository
│   ├── search_engine.py              # Search & substitution facade
│   ├── optimizer.py                  # Multi-drug prescription basket optimizer
│   ├── cli.py                        # Command-line interface
│   └── server.py                     # HTTP REST API & Web UI
└── tests/
    ├── test_models.py
    ├── test_safety_engine.py
    ├── test_strategies.py
    ├── test_search_engine.py
    ├── test_optimizer.py
    ├── test_server.py
    ├── test_blackbox.py
    └── test_cli_and_integration.py
```

---

## Quickstart

Requires **Python 3.9+**. No virtual environment or `pip install` needed.

### 1. Run the Test Suite & Benchmarks

```bash
python3 run_tests.py
python3 benchmark.py
```

### 2. Use the CLI

```bash
# Search the catalog by brand name
python3 -m src.cli search "Telma 40"

# Find bioequivalent substitutes (strategies: max_savings | jan_aushadhi | balanced)
python3 -m src.cli substitutes "Telma 40"
python3 -m src.cli substitutes "Augmentin 625 Duo" --strategy jan_aushadhi
python3 -m src.cli substitutes "Pan-D" --strategy balanced

# Simulate all 28 chronic therapy baskets
python3 -m src.cli chronic-baskets
```

### 3. Launch the Web UI & REST API

```bash
python3 -m src.server
```

Open **`http://localhost:8000`** in your browser for the interactive formulary comparator, preset chips, dark/light theme toggle, and chronic regimen simulator.

---

## REST API Reference

All API routes return JSON with `Access-Control-Allow-Origin: *`.

| Method | Endpoint | Query Parameters | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/` or `/index.html` | — | Serves the interactive Web UI |
| `GET` | `/api/search` | `q` (string), `limit` (int, default `10`) | Prefix/substring brand lookup |
| `GET` | `/api/substitutes` | `brand` (required), `strategy` (`max_savings` \| `jan_aushadhi` \| `balanced`) | Ranked bioequivalent substitutes and warnings |
| `GET` | `/api/baskets` | — | Lists all 28 chronic therapy basket profiles |
| `GET` | `/api/optimize-basket` | `basket_id` (default `BASKET-01`) | Itemized savings breakdown and safety alerts for a basket |
| `GET` | `/api/metrics` | — | Live savings, safety alert, and audit log counters |

### Example Requests

```bash
# Look up generic substitutes prioritized by Jan Aushadhi availability
curl "http://localhost:8000/api/substitutes?brand=Telma%2040&strategy=jan_aushadhi"

# Simulate a chronic prescription basket
curl "http://localhost:8000/api/optimize-basket?basket_id=BASKET-01"

# Inspect runtime telemetry
curl "http://localhost:8000/api/metrics"
```

---

## Medical & Regulatory Disclaimer

EquiMed-India is a clinical decision-support and price-transparency software tool. It does not prescribe or dispense medication. Any substitution of prescription pharmaceuticals should be verified by a licensed medical practitioner or registered pharmacist in accordance with the **Drugs and Cosmetics Act, 1940** and applicable clinical guidelines.
