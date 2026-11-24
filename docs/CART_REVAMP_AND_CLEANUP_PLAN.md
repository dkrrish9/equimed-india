# Plan: Remove Section 3 & Simplify/De-Hardcode Section 2 (Prescription Cart)

**Target Scope:** `HTML_TEMPLATE`, `_build_ui_config()`, and `src/optimizer.py` (additive presentation fields only, if needed) / [server.py](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py).  
**Status:** Blueprint for approval — **no code changes have been made yet**.

---

## Part A — Remove Section 3 (`Chronic Therapy Regimen Simulation`) From the Website UI

### What Will Be Removed From the Web Frontend (`src/server.py`)
1. **HTML Panel (`#chronicPanel`)**: Remove lines [L1021-L1049](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1021-L1049) (`Chronic Therapy Regimen Simulation`, `33 CLINICAL SCENARIOS`, `#basketSelect`, `#basketStrategySelect`, `Simulate`, `Load Regimen into Cart`, `#basketResults`).
2. **Print CSS Selector**: Remove `#chronicPanel` from the `@media print` rule at [L877](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L877) (note: let's verify exact line in `@media print` around `758` in original / shifted after Section 1 edits — `.navbar, #lookupPanel, #chronicPanel, ...`).
3. **Unused Frontend JS Functions & Calls**:
   - Remove `loadBasketIntoCart()` ([L1605-L1627](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1605-L1627)), `runBasketSimulation()` ([L1629-L1712](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1629-L1712)), and `loadBasketsList()` ([L1714-L1733](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1714-L1733)).
   - Remove `loadBasketsList().then(() => { runBasketSimulation(); });` from `window.onload`.
4. **Empty Cart Prompt Reference**: Remove `"or load one of the 33 chronic therapy scenarios below"` from `renderCartFromCache()` ([L1486](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1486)).

### What Stays Intact (Zero Breakage)
- Backend endpoints `GET /api/baskets` and `GET /api/optimize-basket`, `data/chronic_baskets.json`, `src/cli.py`, and `benchmark.py` remain untouched so all existing API/CLI/benchmark tests (`89/89`) stay green.

---

## Part B — De-Hardcode & Simplify Section 2 (`#cartPanel` — Prescription Cart)

### 1. Hardcoded Items Currently in Section 2 (`src/server.py`)
| Hardcoded Item | Location | Fix |
| :--- | :--- | :--- |
| `#cartStrategySelect` options (`jan_aushadhi`, `max_savings`, `balanced`) | [L1004-L1008](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1004-L1008) | Populate dynamically from `uiConfig.strategies` with `default_strategy` from `uiConfig.cart_config`. |
| `#cartBillingMode` options (`pack`, `unit`) | [L1009-L1012](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1009-L1012) | Populate dynamically from `uiConfig.cart_config.billing_modes`. |
| Magic `'KEEP_ORIGINAL'` string | [L1545](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1545) | Read `uiConfig.cart_config.keep_original_sentinel`. |
| Inline frequency `<select>` (`OD (1/d)`, `BD (2/d)`, `TDS (3/d)`, `QID (4/d)`) | [L1553](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1553) | Populate dynamically from `uiConfig.regimen_options.frequencies` (plain English: `1/day`, `2/day`, `3/day`, `4/day`). |
| Numeric bounds (`min="1" max="24"` packs, `min="1" max="365"` days) | [L1552-L1553](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1552-L1553) | Read `pack_min`, `pack_max`, `duration_min`, `duration_max` from `uiConfig.regimen_options`. |
| Raw `₹` currency symbol & `33 chronic therapy scenarios` text | [L1486](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1486), [L1505-L1576](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1505-L1576) | Use `uiConfig.search_config.currency_symbol` and remove the `33 scenarios` reference. |
| Raw `dosage_form` / `release_type` enums & `/1u` pack display | [L1545-L1560](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1545-L1560) | Map through `uiConfig.dosage_forms` & `uiConfig.release_types`; for pack-only items show `(₹MRP / bottle)` instead of `/1u`. |
| Missing XSS escaping in cart table & alerts | [L1545-L1595](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1545-L1595) | Wrap all dynamic strings (`original_brand`, `salts`, `substitute_brand`, `alternatives`, `safety_alerts`) in `escapeHtml()`. |
| Race condition on page load | [L1778-L1782](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1778-L1782) | Run `recalculateCart()` inside `loadUiConfig().then(...)` so `uiConfig` and `#cartStrategySelect` are populated first. |

### 2. Backend Config Extension (`/api/ui-config` in `src/server.py`)
Extend `_build_ui_config()` (additive keys only):
- Add `"duration_min": 1`, `"duration_max": 365` to `regimen_options`.
- Add `"cart_config"`:
  ```json
  {
    "default_strategy": "jan_aushadhi",
    "default_billing_mode": "pack",
    "keep_original_sentinel": "KEEP_ORIGINAL",
    "billing_modes": [
      {"id": "pack", "label": "Full Strips / Bottles You Buy", "short_label": "Full Strips / Bottles"},
      {"id": "unit", "label": "Exact Tablet / Dose Cost", "short_label": "Exact Dose Cost"}
    ]
  }
  ```

### 3. Plain-English Wording Revamp (Before → After)

| UI Element | Current Text (Technical) | New Plain-English Text |
| :--- | :--- | :--- |
| **Navbar Cart Button** | `Prescription Cart` | **My Medicine Bill** *(keep `aria-label` clear)* |
| **Section Title** | `Prescription Cart & Dispensing Ledger` | **My Medicine Bill & Savings** |
| **Section Subtitle** | `Build a complete prescription bill comparing branded MRP against verified generic alternatives across strips, packs, syrups, and inhalers.` | **Compare your doctor's prescribed brands with cheaper same-salt alternatives, and print a list to show your chemist.** |
| **Strategy Dropdown** | `Jan Aushadhi (PMBJP) Priority` / `Maximum Price Savings` / `Balanced Quality & Savings` | Uses `uiConfig.strategies`: **Govt. Jan Aushadhi Stores First** *(default)* / **Lowest Price First** / **Best Balance (Price + Quality)** |
| **Billing Mode Dropdown** | `Billing: Retail Strips / Packs` / `Billing: Exact Unit Cost` | **Full Strips / Bottles You Buy** / **Exact Tablet / Dose Cost** |
| **Buttons** | `Print Counter Slip` / `Clear Cart` | **Print List for Chemist** / **Clear All** |
| **Print Slip Header** | `Verified Generic Prescription & Counter Dispensing Slip` + `Bioequivalent substitutes validated under CDSCO...` | **EquiMed-India · Medicine List for Your Chemist** + *"Every alternative below has the exact same active ingredient and strength. Show the salt names to your PMBJP Jan Aushadhi Kendra or licensed pharmacist."* |
| **Empty Cart Box** | `Your prescription cart is empty. Search any medicine above to configure dosage & add it, or load one of the 33 chronic therapy scenarios below.` | **Your medicine list is empty.** Search any medicine above, choose how many days you need it, and click **Add to Cart** (or **+ Pick This Option**). |
| **Summary Card 1** | `Branded Bill (Retail Strip / Pack MRP)` | **Prescribed Brands Total** *(sublabel: `Full Strips / Bottles` or `Exact Dose Cost`)* |
| **Summary Card 2** | `EquiMed Generic Bill` | **Cheaper Alternatives Total** |
| **Summary Card 3** | `Prescription Savings` | **Total Money Saved** |
| **Summary Card 4** | `Annualized Projection (12x)` | **Yearly Savings (If Taken Monthly)** |
| **Column 1** | `Prescribed Drug & Generic Salt` | **Prescribed Medicine & Salt** *(shows plain-English form & release speed: e.g. `Tablet · Normal Release`)* |
| **Column 2** | `Regimen / Qty` | **How Many You Need** *(shows `1/day`, `2/day`, `3/day`, `4/day` + days, and plain text: `30 tablets total (buy 3 strips of 10)` or `1 bottle(s)`)* |
| **Column 3** | `Counter Substitution Choice` | **Chosen Alternative** *(dropdown shows `Keep Prescribed Brand (₹...)` or `Alt Brand (₹... / 10 tablets · -78%)`, or `(₹... / bottle)` for pack-only)* |
| **Column 4** | `Branded` | **Original Cost** *(shows `₹...` + `2 strips` or `1 bottle`)* |
| **Column 5** | `Generic Bill` | **New Cost** *(shows `₹...` + `3 strips` or `1 bottle`)* |
| **Column 6** | `Saved` | **You Save** *(shows `-₹... (80.7%)`, or neutral `"Same price"` / `"Kept original"` badge when `KEEP_ORIGINAL` or `₹0.00`)* |
| **Column 7** | `Remove` | **Remove** |
| **NTI Tag** | `NTI` | **Sensitive Dose** |

---

## Part C — Verification Plan (After Approval)

1. Update [server.py](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py) and add/update tests in [test_server.py](file:///c:/Users/91994/Desktop/CS/equimed-india/tests/test_server.py):
   - Assert `#chronicPanel` and `Chronic Therapy Regimen Simulation` are NOT present in `GET /` HTML.
   - Assert `GET /api/baskets` and `GET /api/optimize-basket` still return `200`.
   - Assert `GET /api/ui-config` includes `cart_config` (`billing_modes`, `default_strategy`, `keep_original_sentinel`) and `duration_min`/`duration_max`.
   - Assert `GET /` contains `My Medicine Bill & Savings` and zero hardcoded `<option value="jan_aushadhi">` inside `#cartStrategySelect`.
2. Run `python -W error::SyntaxWarning run_tests.py` (expect **100% pass**).
3. Restart the live server (`http://localhost:8000`) and verify `/` renders cleanly with 2 sections only (Lookup + My Medicine Bill).
