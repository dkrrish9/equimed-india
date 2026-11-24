# Section 1 Finalization Plan: Lookup Section Revamp & De-Hardcoding

**Target Scope:** Section 1 (`#lookupPanel` — currently **"Formulary Bioequivalence Lookup"**) in [server.py](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L813-L1154) and its supporting REST handlers ([L1602-L1665](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1602-L1665)).  
**Status:** Blueprint for approval — **no code changes have been made yet**.

---

## 1. Verification: Is the Lookup Data Really Coming From the Dataset?

**Yes — 100% of the clinical & pricing data displayed in the results card and table is live from `data/equimed_catalog.db` (`240,199` medicines), with zero hardcoded medicine results.**

Specifically, when you search any medicine:
- `/api/search` ([server.py:L1602-L1612](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1602-L1612)) queries `_repo.search_by_brand()` against `SQLiteMedicineRepository` (B-tree + FTS5 + `medicine_salts` indexes).
- `/api/substitutes` ([server.py:L1614-L1664](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1614-L1664)) calls `_engine.find_substitutes()`, which:
  1. Resolves the searched brand/salt from SQLite (`240,199` rows).
  2. Pulls cheaper, non-discontinued candidates matching the exact chemical `salt_fingerprint` via `get_substitute_candidates()`.
  3. Runs all 7 deterministic rules in `SafetyEngine.validate_substitution()` (composition, exact strength, form compatibility, release speed, NTI warning, discontinued blocking, and price check).
  4. Ranks results using the selected `SubstitutionStrategy` (`max_savings`, `jan_aushadhi`, or `balanced`).
  5. Returns live brand names, manufacturers, salts, `pack_size`, `mrp`, `price_per_unit`, `regulatory_tier`, `percentage_savings`, `savings_per_unit`, and `warnings` directly from the database.

### What *IS* Currently Hardcoded in Section 1 (UI Chrome & Config Only)
While the search results themselves are 100% live, the **surrounding UI controls and labels** in Section 1 still have hardcoded values that duplicate backend logic or assume static defaults:

| Hardcoded Item in Section 1 | Location in `src/server.py` | Problem |
| :--- | :--- | :--- |
| 8 preset brand chips (`Telma 40`, `Glycomet-GP 2`, `Augmentin 625 Duo`, `Foracort 200 Inhaler (120 MDI)`, `Lantus SoloSTAR Pen (3ml)`, `Calpol 250 Pediatric Suspension (60ml)`, `Vigamox 0.5% Eye Drops (5ml)`, `Thyronorm 50`) | [L824-L831](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L824-L831) | Brand names hardcoded in HTML instead of resolved/validated from the active backend catalog. |
| Default search input `value="Telma 40"` + placeholder text | [L838](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L838) | Hardcoded brand string; if `Telma 40` isn't first in a custom catalog, initial load fails. |
| Ranking strategy `<select>` options (`max_savings`, `jan_aushadhi`, `balanced`) | [L841-L845](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L841-L845) | Labels & option values hardcoded separately from Python `strategy.py`. |
| `PACK_ONLY_FORMS = new Set(['SYRUP', 'INHALER', 'INJECTION', 'DROPS', 'OINTMENT'])` | [L924](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L924) | Duplicates `SafetyEngine.PACK_ONLY_FORMS` in `src/safety_engine.py`. |
| `formatTierBadge()` tier keys & labels | [L960-L966](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L960-L966) | Duplicates `RegulatoryTier` enum in `src/models.py` (`BRANDED_INNOVATOR` silently falls back to `"Prescribed Brand"`). |
| `freqLabelFromUnits()`, dosage options (`1–4/day`), duration options (`5, 7, 10, 15, 30, 90`), pack quantity (`1, 2, 3`) | [L968-L974](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L968-L974), [L1010-L1035](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1010-L1035) | Lookup pack dropdown caps at `1–3` packs even though the Cart allows `1–24` packs; dosage & duration options are hardcoded inline. |
| Not-found message examples (`Telma 40`, `Paracetamol`, `Budesonide`) | [L995](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L995) | Hardcoded example names and no HTML escaping on user-entered `brand`. |
| Autocomplete settings (`q.length < 2`, `limit=15`, `180ms` debounce) | [L1529](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1529), [L1537](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1537), [L1550](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1550) | Hardcoded magic numbers in `window.onload`. |
| Raw `Pack of ${m.substitute_pack_size}` on pack-only forms | [L1089](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1089) | Shows `"Pack of 1"` for syrups/inhalers/drops instead of `pack_size_label` (e.g., `"bottle of 60 ml syrup"`). |

---

## 2. Backend Changes to Eliminate All Hardcoding in Section 1

All API changes will remain **100% backwards-compatible** (existing JSON keys stay untouched so all 86 tests pass):

### 2.1 New `GET /api/ui-config` Endpoint (`src/server.py`)
Serves Section 1's configuration dynamically from Python constants & the active `_repo`:
- **`presets`**: Resolves curated preset items against `_repo.get_by_brand_exact()` (with `label`, `brand_name`, and `is_nti`) — only rendering chips for medicines actually verified present in `_repo`.
- **`default_query`**: First verified preset's `brand_name` (or fallback from `_repo`).
- **`strategies`**: Derived from `src/strategy.py` (`id`, `label`, `plain_description`) so dropdown options and plain-English labels come from one source of truth.
- **`pack_only_forms`**: `[f.value for f in sorted(SafetyEngine.PACK_ONLY_FORMS, key=lambda x: x.value)]`.
- **`regulatory_tiers`**: Canonical map from `RegulatoryTier` enum values to plain-English badge titles & helper descriptions.
- **`dosage_forms` & `release_types`**: Human-friendly labels (e.g., `TABLET` → `"Tablet"`, `IMMEDIATE_RELEASE` → `"Normal Release"`, `SUSTAINED_RELEASE` → `"Slow Release (SR)"`, `ENTERIC_COATED` → `"Stomach-Safe Coating (EC/DR)"`).
- **`regimen_options`**:
  - `frequencies`: `[{value: 1, label: "Once a day (1-0-0)", short: "1-0-0 (OD)"}, ...]`
  - `durations`: `[5, 7, 10, 15, 30, 90]` (with plain labels like `"30 days (1 month)"`)
  - `pack_quantities`: `min: 1, max: 24` (matching Cart)
- **`search_config`**: `{min_query_chars: 2, autocomplete_limit: 15, debounce_ms: 180, currency_symbol: "₹"}`.

### 2.2 Enriched Fields on `GET /api/substitutes` (`src/server.py`)
Keep every existing field unchanged and add clean presentation fields computed by the backend:
- **`is_pack_only`**: `orig.dosage_form in SafetyEngine.PACK_ONLY_FORMS`
- **`unit_label`**: `"tablet"`, `"capsule"`, `"bottle"`, `"inhaler / spray"`, `"injection / vial"`, `"drop bottle"`, or `"tube / pack"` (derived from `orig.dosage_form`)
- **`original_form_label`**: Plain-English form name (e.g., `"Tablet"`, `"Syrup / Liquid"`, `"Inhaler / Nasal Spray"`)
- **`original_release_label`**: Plain-English release speed (e.g., `"Normal Release"`, `"Slow Release (SR)"`, `"Extended Release (ER/XR)"`, `"Stomach-Safe Coating (EC/DR)"`)
- **`original_pack_label`**: `orig.pack_size_label` (or computed `"Strip/Pack of {pack_size}"` when `pack_size_label` is empty)
- **`substitute_pack_label`** and **`substitute_tier_label`** on each item in `matches` (using `m.substitute_medicine.pack_size_label` when available, so syrups/drops show `"bottle of 60 ml syrup"` instead of `"Pack of 1"`).

---

## 3. Simplified Plain-English Revamp (Before → After)

Designed so anyone — even without medical or technical background — immediately understands every number, label, and warning:

| UI Element | Current Text (Technical) | New Plain-English Text |
| :--- | :--- | :--- |
| **Section Title** | `Formulary Bioequivalence Lookup` | **Find Cheaper Same-Salt Medicines** |
| **Section Subtitle** | `Search by brand name or active chemical salt, inspect bioequivalent alternatives, and add to your prescription cart.` | **Type your prescribed medicine name or ingredient to see safe, cheaper alternatives with the exact same medicine inside.** |
| **Presets Label** | `Formulation Presets:` | **Quick Examples:** |
| **Search Placeholder** | `Search brand or chemical salt (e.g., Telma 40, Acetaminophen, Budesonide)...` | **Type medicine name or salt (e.g., Dolo 650, Telma 40, Paracetamol)...** |
| **Search Button** | `Analyze` | **Find Alternatives** |
| **Strategy Dropdown** | `Maximum Price Savings` / `Jan Aushadhi (PMBJP) Priority` / `Balanced (Savings + Quality Tier)` | **Lowest Price First** / **Govt. Jan Aushadhi Stores First** / **Best Balance (Price + Quality)** |
| **Loading Text** | `Executing clinical validation rules and scanning database index...` | **Checking active ingredients, strength, and safety rules...** |
| **Top-Right Price Box** | `Originator Unit Price` | **Your Medicine (Per Tablet)** *(or **Per Bottle / Inhaler / Tube** dynamically from `unit_label`)* |
| **Active Salt Line** | `Active API: ...` | **Inside This Medicine (Salt):** `...` |
| **Form & Release Line** | `TABLET · IMMEDIATE_RELEASE · Strip MRP: ₹...` | **Tablet · Normal Release · 15 tablets strip MRP ₹...** *(human-readable form & release labels)* |
| **NTI Badge** | `Narrow Therapeutic Index (NTI)` | **Sensitive Dose — Ask Doctor Before Switching** |
| **Discontinued Badge** | `Discontinued — Active Substitutes Shown Below` | **Discontinued Brand — Active Alternatives Shown Below** |
| **Add-to-Cart Prompt** | `Configure prescribed dosage & add directly to your patient cart:` | **How many do you need? Add to your Prescription Bill below:** |
| **New Table Explainer Header** *(currently missing!)* | *(none)* | **Verified Cheaper Alternatives (`N` found)** + subtitle: *"All options below have the **exact same active ingredient and strength** as **<Brand>**, checked by safety rules."* |
| **Column 1** | `Generic Formulation` | **Cheaper Alternative Medicine** *(shows brand + pack size/bottle size + full pack MRP)* |
| **Column 2** | `Manufacturer & Quality Certification` | **Company & Quality Badge** *(plain-English badge: `Govt. Jan Aushadhi`, `WHO-GMP Certified`, `CDSCO Approved`, or `Retail Generic Brand`)* |
| **Column 3** | `Pack / Unit Price` | **Price per Tablet** *(or **Price per Bottle / Pack** dynamically via `unit_label`)* |
| **Column 4** | `Net Patient Savings` | **You Save (per Tablet)** *(shows `-53.3% · Save ₹1.76 each`)* |
| **Column 5** | `Action` / `+ Use in Cart` | **Select** / **+ Pick This Option** |
| **No Cheaper Match Banner** | `No cheaper bioequivalent generic substitute is available for ... (it may already be the lowest-cost formulation in its class)...` | **No cheaper exact-match alternative found for `<Brand>`** — it may already be the lowest-priced option available. You can still add it to your cart above. |
| **Not Found Banner** | `No medicine matching ... was found in the catalog...` | **Could not find `<query>` in our retail medicine database.** Please check the spelling, or search by the chemical ingredient name printed on the strip. |

---

## 4. Safety & UX Polish Included in This Revamp

1. **XSS-safe HTML escaping (`escapeHtml()`)**: Escape all user queries, brand names, manufacturer strings, and warnings before inserting into `innerHTML` (fixes raw `${brand}` interpolation in the not-found banner and `${m.substitute_brand}` / `${data.original_brand}`).
2. **Accurate Pack Labels for Liquids/Inhalers/Ointments**: Display `substitute_pack_label` (e.g., `bottle of 60 ml syrup`, `tube of 15 gm ointment`) instead of `"Pack of 1"` on pack-only forms.
3. **Consistent Pack Quantity Control**: Replace the hardcoded `1–3` `<select>` in Lookup with an input/selector matching the Cart (`1–24` packs) populated from `/api/ui-config`.
4. **Section-Isolated Changes Only**: Only `#lookupPanel`, its rendering/config functions (`loadUiConfig()`, `performSearch()`, `addCurrentLookupToCart()`, autocomplete setup), and `/api/ui-config` + additive fields on `/api/substitutes` will be touched. Sections 2 and 3 (Prescription Cart & Chronic Baskets) remain untouched until we work on them separately.

---

## 5. Verification Plan (After Your Approval)

1. Update [server.py](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py) and add tests in [test_server.py](file:///c:/Users/91994/Desktop/CS/equimed-india/tests/test_server.py) covering:
   - `GET /api/ui-config` schema, verified presets, strategies, and `pack_only_forms`.
   - `GET /api/substitutes` new plain-English fields (`unit_label`, `is_pack_only`, `original_form_label`, `original_release_label`, `substitute_pack_label`) and backwards-compatibility with all existing fields.
   - `GET /` verifies no hardcoded `1,021` or old hardcoded preset block remains and renders live `240,199 FORMULATIONS ACTIVE`.
2. Run `python run_tests.py` (expect **100% pass** across all existing + new server tests).
3. Restart the live server (`http://localhost:8000`) and verify the revamped Section 1 visually & via API checks.
