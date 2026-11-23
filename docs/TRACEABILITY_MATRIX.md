# Requirements Traceability Matrix (RTM)
## EquiMed-India: Generic Drug Substitution & Affordability Optimizer

**Institution:** Indian Institute of Information Technology (IIIT), Lucknow  
**Course:** Software Engineering (Credits: 4)  
**Standard:** IEEE Std 830-1998 Traceability Guidelines  
**Status:** 100% Verified (All 47 Tests Passing)  

---

| Req ID | Requirement Description | Design Module / Source Class | Test File & Methods | Verification Status |
| :--- | :--- | :--- | :--- | :--- |
| **REQ-1** | Brand Query Lookup & Resolution | `src.repository.MedicineRepository`<br>`src.search_engine.SearchEngine` | `tests/test_search_engine.py`<br>- `test_find_substitutes_for_telma_40`<br>- `test_unknown_medicine_returns_empty` | 🟢 PASS |
| **REQ-2** | Active Salt & Unit Normalization | `src.safety_engine.SafetyEngine` | `tests/test_safety_engine.py`<br>- `test_salt_synonym_normalization`<br>- `test_strength_normalization`<br>`tests/test_blackbox.py`<br>- `test_bva_strength_microgram_to_milligram_boundary` | 🟢 PASS |
| **REQ-3** | Invariant Combination Fingerprinting | `src.models.Medicine`<br>- `salt_fingerprint()`<br>`src.models.SaltComponent` | `tests/test_models.py`<br>- `test_medicine_salt_fingerprint_invariance`<br>- `test_medicine_fingerprint_differs_by_form_or_release` | 🟢 PASS |
| **REQ-4.1**| Bioequivalence: Exact Salt Match | `src.safety_engine.SafetyEngine`<br>- `validate_substitution()` | `tests/test_safety_engine.py`<br>- `test_reject_missing_salt`<br>- `test_reject_extra_salt`<br>`tests/test_blackbox.py`<br>- `test_ec2_invalid_chemical_salt_mismatch` | 🟢 PASS |
| **REQ-4.2**| Bioequivalence: Strength Equivalence | `src.safety_engine.SafetyEngine` | `tests/test_safety_engine.py`<br>- `test_reject_strength_mismatch`<br>`tests/test_blackbox.py`<br>- `test_ec3_invalid_strength_mismatch` | 🟢 PASS |
| **REQ-4.3**| Dosage Form Compatibility | `src.safety_engine.SafetyEngine` | `tests/test_safety_engine.py`<br>- `test_reject_dosage_form_incompatibility`<br>- `test_oral_solid_interchangeability_warning`<br>`tests/test_blackbox.py`<br>- `test_ec4_invalid_form_incompatibility`<br>- `test_ec5_valid_oral_solid_interchange_with_warning` | 🟢 PASS |
| **REQ-4.4**| Release Kinetics Safety (SR vs IR) | `src.safety_engine.SafetyEngine` | `tests/test_safety_engine.py`<br>- `test_reject_release_kinetics_clash`<br>`tests/test_blackbox.py`<br>- `test_ec6_invalid_release_profile_clash` | 🟢 PASS |
| **REQ-4.5**| Narrow Therapeutic Index (NTI) Guard | `src.safety_engine.SafetyEngine`<br>`src.observer.SafetyAlertObserver` | `tests/test_safety_engine.py`<br>- `test_narrow_therapeutic_index_warning`<br>`tests/test_search_engine.py`<br>- `test_nti_warning_notification`<br>`tests/test_blackbox.py`<br>- `test_ec7_valid_nti_alert` | 🟢 PASS |
| **REQ-4.6**| Price Sanity Ceiling Check | `src.safety_engine.SafetyEngine` | `tests/test_safety_engine.py`<br>- `test_reject_more_expensive_candidate`<br>`tests/test_blackbox.py`<br>- `test_ec8_invalid_economic_price_escalation`<br>- `test_bva_equal_price_boundary` | 🟢 PASS |
| **REQ-5.1**| Strategy Pattern: Max Savings | `src.strategy.MaxSavingsStrategy` | `tests/test_strategies.py`<br>- `test_max_savings_strategy` | 🟢 PASS |
| **REQ-5.2**| Strategy Pattern: Jan Aushadhi Priority | `src.strategy.JanAushadhiFirstStrategy` | `tests/test_strategies.py`<br>- `test_jan_aushadhi_first_strategy` | 🟢 PASS |
| **REQ-5.3**| Strategy Pattern: Balanced Quality-Price | `src.strategy.ReputationBalancedStrategy` | `tests/test_strategies.py`<br>- `test_reputation_balanced_strategy`<br>- `test_get_strategy_factory` | 🟢 PASS |
| **REQ-6** | Multi-Drug Chronic Prescription Optimizer | `src.optimizer.PrescriptionOptimizer`<br>`src.models.BasketOptimizationResult` | `tests/test_optimizer.py`<br>- `test_optimize_elderly_diabetic_basket`<br>- `test_basket_with_unmatched_medicine_fallback`<br>- `test_all_predefined_baskets_produce_substantial_savings` | 🟢 PASS |
| **REQ-7** | Observer Telemetry & Audit Trail | `src.observer.AuditLogObserver`<br>`src.observer.SavingsTrackerObserver`<br>`src.observer.SafetyAlertObserver` | `tests/test_search_engine.py`<br>- `test_observer_events_triggered`<br>- `test_nti_warning_notification` | 🟢 PASS |
| **REQ-8.1**| Terminal Command Line Interface (CLI) | `src.cli` | `tests/test_cli_and_integration.py`<br>- `test_cli_search_command_output`<br>- `test_cli_substitutes_command_output`<br>- `test_cli_chronic_baskets_command_output` | 🟢 PASS |
| **REQ-8.2**| End-to-End System Integration | Whole Application Flow | `tests/test_cli_and_integration.py`<br>- `test_end_to_end_patient_flow`<br>- `test_repository_initialization_catalog_size` | 🟢 PASS |

---

### Verification Summary
- **Total Functional Requirements (FRs):** 8 Major (16 granular clauses)
- **Total Test Cases Executed:** 47 automated tests
- **Requirements Coverage:** **100.0%**
- **Test Pass Rate:** **100.0% (47/47 passing)**
- **Verification Environment:** Python 3.9+ standard library test runner (`run_tests.py`).
