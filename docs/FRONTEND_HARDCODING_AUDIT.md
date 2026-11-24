# Frontend Hardcoding Audit (`src/server.py`)

**Scope:** Embedded web frontend (`HTML_TEMPLATE`) in [server.py](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L44-L1570).  
**Status:** Audit only — no code changes made yet (excluding `{{CATALOG_COUNT}}`, which was already converted to dynamic server-side rendering at [L788](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L788) and [L1594-L1595](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1594-L1595)).

---

## 1. Hardcoded Counts & Metadata

| Item | Hardcoded Value | Location | Current Runtime Behavior & Suggested Fix |
| :--- | :--- | :--- | :--- |
| Chronic basket description | `across 33 multi-morbidity patient scenarios` | [server.py:L889](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L889) | Never updated by JS if `data/chronic_baskets.json` grows or shrinks. Update dynamically inside `loadBasketsList()` or inject count from backend. |
| Chronic basket initial badge | `33 CLINICAL SCENARIOS` | [server.py:L891-L893](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L891-L893) | Initial placeholder text before `loadBasketsList()` overwrites `#basketCountBadge` at [L1465](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1465). Render placeholder dynamically or show `Loading scenarios...`. |
| Empty cart prompt | `load one of the 33 chronic therapy scenarios below.` | [server.py:L1223](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1223) | Never updated by JS. Reference dynamic `basketCount` variable populated by `loadBasketsList()`, or omit the exact number. |
| Regulatory standard tag | `CDSCO / IP 2026` | [server.py:L791](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L791) | Static navbar label. Centralize as a backend/config constant if versioned across UI & print slip. |
| Initial cart count badge | `0` | [server.py:L799](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L799) | Overwritten on `window.onload` by `loadCartState()` (`localStorage`). Fine as initial SSR value, though flashes `0` briefly if cart has items. |

---

## 2. Hardcoded Medicine Names, Presets & Default Search

| Item | Hardcoded Value | Location | Notes & Suggested Fix |
| :--- | :--- | :--- | :--- |
| Quick formulation preset chips (8 brands) | `'Telma 40'`, `'Glycomet-GP 2'`, `'Augmentin 625 Duo'`, `'Foracort 200 Inhaler (120 MDI)'`, `'Lantus SoloSTAR Pen (3ml)'`, `'Calpol 250 Pediatric Suspension (60ml)'`, `'Vigamox 0.5% Eye Drops (5ml)'`, `'Thyronorm 50'` | [server.py:L824-L831](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L824-L831) | Tightly coupled to exact `brand_name` strings in `data/medicine_catalog.json`. Could be served from `/api/metrics` or a config list and verified against the active repo. |
| Pre-filled search input & auto-search | `value="Telma 40"` + `performSearch()` on load | [server.py:L838](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L838), [L1565](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1565) | Runs `/api/substitutes?brand=Telma%2040` on every page load. Make configurable or show an empty prompt until user searches. |
| Search placeholder examples | `Search brand or chemical salt (e.g., Telma 40, Acetaminophen, Budesonide)...` | [server.py:L838](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L838) | Static example drug names in input placeholder. |
| Not-found helper message examples | `Try a brand name (e.g., Telma 40) or chemical salt (e.g., Paracetamol, Budesonide).` | [server.py:L995](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L995) | Static fallback examples when lookup returns no `original_id`. |

---

## 3. Duplicated Backend Domain Enums & Constants

| Item | Hardcoded Value | Location | Risk & Suggested Fix |
| :--- | :--- | :--- | :--- |
| Pack-only dosage forms | `PACK_ONLY_FORMS = new Set(['SYRUP', 'INHALER', 'INJECTION', 'DROPS', 'OINTMENT'])` | [server.py:L924](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L924) | Duplicates `SafetyEngine.PACK_ONLY_FORMS` in `src/safety_engine.py`. Inject from backend or return `is_pack_only` boolean in API responses. |
| Regulatory tier mapping | `'PMBJP_JAN_AUSHADHI'`, `'WHO_GMP_GENERIC'`, `'CDSCO_APPROVED_GENERIC'`, `'BRANDED_GENERIC'`, fallback `'Prescribed Brand'` | [server.py:L960-L966](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L960-L966) | Duplicates `RegulatoryTier` enum in `src/models.py`; `'BRANDED_INNOVATOR'` falls through to `'Prescribed Brand'`. |
| Strategy `<select>` options (duplicated 3x) | `max_savings`, `jan_aushadhi`, `balanced` | [L841-L845](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L841-L845), [L867-L871](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L867-L871), [L898-L902](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L898-L902) | Three separate copies with slightly different labels (`Balanced Quality & Savings` vs `Balanced (Savings + Quality Tier)`) and different defaults (`max_savings` vs `jan_aushadhi`). |
| Keep-original sentinel | `'KEEP_ORIGINAL'` | [server.py:L1282](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1282) | Magic string shared with `PrescriptionOptimizer.optimize_custom_cart()` in `src/optimizer.py`. |
| Currency symbol & annual multiplier | `₹` and `12x` | [L1003-L1004](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1003-L1004), [L1052](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1052), [L1089](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1089), [L1095-L1097](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1095-L1097), [L1242-L1254](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1242-L1254), [L1380-L1424](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1380-L1424), [L1546](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1546) | Repeated inline formatting instead of a shared `formatINR()` helper. |

---

## 4. Hardcoded Regimen Limits, UI Tuning & Storage Keys

| Item | Hardcoded Value | Location | Notes |
| :--- | :--- | :--- | :--- |
| Lookup pack quantity dropdown | Options `1`, `2`, `3` | [server.py:L1010-L1014](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1010-L1014) | Lookup limits pack-only items to `1–3` packs, whereas the Cart input below allows `min="1" max="24"`. |
| Cart pack quantity bounds | `min="1" max="24"` | [server.py:L1289](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1289) | Inconsistent with Lookup dropdown (`1–3`). |
| Dosage frequencies | `1` (OD), `2` (BD), `3` (TDS), `4` (QID) | [L968-L974](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L968-L974), [L1021-L1026](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1021-L1026), [L1290](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1290) | Hardcoded in three places (`freqLabelFromUnits()`, Lookup `<select>`, and Cart `<select>`). |
| Lookup duration options & Cart bounds | Lookup: `5, 7, 10, 15, 30, 90` days (default `30`); Cart: `min="1" max="365"` | [L1028-L1035](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1028-L1035), [L1130](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1130), [L1290](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1290) | Static presets and numeric caps. |
| Autocomplete tuning | `q.length < 2`, `limit=15`, `180` ms debounce | [L1529](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1529), [L1537](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1537), [L1550](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1550) | UI config constants embedded directly inside `window.onload`. |
| Toast display timeout | `2800` ms | [server.py:L935](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L935) | Magic number inside `showToast()`. |
| `localStorage` keys | `'equimed-theme'`, `'equimed-cart'` | [L768](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L768), [L944](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L944), [L951](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L951), [L1485](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1485), [L1510](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L1510) | Repeated literal strings without shared JS constants. |

---

## 5. External Font URLs & Static Institutional Copy

| Item | Hardcoded Value | Location | Notes |
| :--- | :--- | :--- | :--- |
| Google Fonts CDN links | `https://fonts.googleapis.com/...` (`Plus Jakarta Sans`, `JetBrains Mono`) | [server.py:L50-L52](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L50-L52) | Requires internet access for custom fonts (falls back to system fonts offline). |
| Institutional branding & print header | `EquiMed-India`, `Indian Institute of Information Technology, Lucknow (Software Engineering Laboratory)`, print counter slip copy | [L781-L782](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L781-L782), [L858-L859](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L858-L859), [L919-L920](file:///c:/Users/91994/Desktop/CS/equimed-india/src/server.py#L919-L920) | Static institutional and disclaimer strings. |
