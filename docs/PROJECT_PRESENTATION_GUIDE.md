# EquiMed-India — Presentation & Live Demo Walkthrough Guide

*A plain-English guide explaining every part of the EquiMed-India website, how it works behind the scenes, and how to present it confidently.*

---

## 1. 30-Second Elevator Pitch

> **"In India, families pay 70% to 90% extra simply because prescriptions name an expensive brand instead of an equally safe generic medicine with the exact same chemical salt inside. EquiMed-India is a deterministic, zero-AI-hallucination medicine comparison tool with over 2.4 lakh (240,199) Indian medicines. In about 3.5 milliseconds, it finds strictly verified, cheaper alternatives with the exact same salt, strength, and release speed—and builds a printable bill comparing what you pay at the chemist."**

### Key Numbers to Remember for Your Slides / Viva
- **240,199 active formulations** in our database (built from `253,973` Indian retail pharmacy records + `1,021` verified Jan Aushadhi / WHO-GMP gold records).
- **10,739 unsafe/ambiguous rows quarantined** during data cleaning so bad data never reaches a patient.
- **3.52 ms (90th percentile)** lookup speed (**~306 searches/second**).
- **100.0% bioequivalence accuracy** across `23,166` checked pairs (`0` wrong salts, `0` wrong strengths, `0` discontinued substitutes).
- **Zero external libraries / Zero LLM guessing** — runs completely on standard Python + SQLite.

---

## 2. Top-to-Bottom Tour of Everything Visible on the Website

### A. Top Navigation Bar
1. **Logo & Title (`EQ · EquiMed-India`)**: Shows the project name and purpose (*Generic Drug Substitution & Formulary Affordability Optimizer*).
2. **Green Dot + `240,199 FORMULATIONS ACTIVE`**: Dynamically reads the live count of verified medicines loaded in the database (never hardcoded).
3. **`CDSCO / IP 2026`**: Indicates the clinical rules follow Indian Pharmacopoeia and Central Drugs Standard Control Organization (CDSCO) bioequivalence principles.
4. **`My Medicine Bill [N]`**: Shows how many medicines are currently in the user's bill and smoothly scrolls down to Section 2 when clicked.
5. **`Dark Mode / Light Mode`**: Switches the color theme and remembers the user's choice in the browser.

---

### B. Section 1 — "Find Cheaper Same-Salt Medicines"

This is the **single-medicine lookup & safe alternative finder**.

1. **Quick Examples (Preset Chips)**:
   - One-click example medicines (`Telma 40`, `Glycomet-GP 2`, `Augmentin 625`, `Foracort 200 Inhaler`, `Lantus Injection`, `Calpol 250 Syrup`, `Vigamox Drops`, `Thyronorm 50 (Sensitive Dose)`).
   - They cover all 7 medicine forms supported by the system (Tablets, Capsules, Syrups, Inhalers, Injections, Eye Drops, Ointments) and are verified by the backend before appearing.

2. **Search Box + Autocomplete**:
   - Users can type **either a brand name** (like `Allopurizol 300`, `Dolo 650`, `Telma 40`) **or a chemical ingredient name** (like `Paracetamol`, `Budesonide`, or even its US synonym `Acetaminophen`).
   - As soon as 2+ letters are typed, it waits `180 ms` (so it doesn't spam the server while typing fast) and shows matching suggestions from the 240,199-medicine database.

3. **Sort Dropdown (`Sort Alternatives By`)**:
   - **Lowest Price First**: Shows the cheapest exact-match alternative at the top (`Maximum Cost Savings`).
   - **Govt. Jan Aushadhi Stores First**: Puts subsidized Government **PMBJP Jan Aushadhi** medicines at the very top, followed by WHO-GMP generics, then retail generics.
   - **Best Balance (Price + Quality)**: Balances 65% savings + 35% regulatory quality certification score.

4. **The Searched Medicine Summary Card (Grey Box)**:
   When you search a medicine, this card confirms what you searched before showing alternatives:
   - **Medicine Name** + optional warning badges:
     - **`Sensitive Dose — Ask Doctor Before Switching`**: Appears on Narrow Therapeutic Index (NTI) drugs like *Thyroxine*, *Warfarin*, *Digoxin*, *Lithium*, *Phenytoin*, where tiny dose changes matter clinically.
     - **`Discontinued Brand — Active Alternatives Shown Below`**: Appears if a doctor/old prescription names a discontinued brand. EquiMed lets you search it as your starting point so you can still find **active, available replacements**, while blocking discontinued medicines from ever appearing as recommendations.
   - **`Inside This Medicine (Salt)`**: Exact active chemical(s) and strength (e.g., `Allopurinol 300mg`).
   - **Form, Release Speed & Pack MRP**: Written in plain English (e.g., `Tablet · Normal Release · Strip/Bottle info · MRP`).
   - **Right Price Box (`Your Medicine (Per Tablet)` or `Per Bottle`)**: Shows the price of **1 single tablet/capsule** (or **1 full bottle/inhaler/tube** for liquids/inhalers/creams) so strips of 10 tablets and strips of 15 tablets can be compared fairly!
   - **Add-to-Cart Bar (`How many do you need?`)**: Pick Daily Dose (`Once a day`, `Twice a day`, `3 times a day`, `4 times a day`) and Duration (`5 days` to `90 days`), or Number of Packs (`1–24`) for syrups/inhalers, and click **Add to Cart**.

5. **Verified Cheaper Alternatives Table**:
   - **Banner Above Table**: Clearly tells the user how many verified alternatives were found and that all of them have the **exact same active ingredient and strength**.
   - **Column 1 — `Cheaper Alternative Medicine`**: Name of the alternative brand, pack size/bottle size (e.g., `strip of 10 tablets` or `bottle of 60 ml syrup`), and full strip/pack MRP.
   - **Column 2 — `Company & Quality Badge`**: Manufacturer name + color-coded trust badge:
     - **Govt. Jan Aushadhi** (Green) — PMBJP subsidized generic stores.
     - **WHO-GMP Certified** (Blue) — WHO Good Manufacturing Practice verified.
     - **CDSCO Approved** (Teal) — Central regulator approved generic.
     - **Retail Generic Brand** (Grey) — Standard Indian retail allopathic brands from the 2.5L A–Z dataset.
   - **Column 3 — `Price per Tablet` (or `Bottle`)**: Cost per 1 unit for apples-to-apples comparison.
   - **Column 4 — `You Save (per Tablet)`**: Percentage saved and exact rupees saved per unit (e.g., `-53.3% · Save ₹1.76 each`).
   - **Column 5 — `Select` (`+ Pick This Option`)**: Adds your searched medicine to the bill below with **this specific alternative pre-selected**.
   - **Inline Caution Banners** (when applicable): E.g., Tablet ↔ Capsule interchangeability note, NTI doctor-consultation notice, or container-size difference note (e.g., `60 ml` vs `100 ml` bottle).

---

### C. Section 2 — "My Medicine Bill & Savings"

This is the **multi-medicine prescription bill calculator**.

1. **Top Controls**:
   - **Sort Cart Alternatives By**: Defaults to *Govt. Jan Aushadhi Stores First* (can switch anytime to *Lowest Price First* or *Best Balance*).
   - **How to Calculate Bill**:
     - **Full Strips / Bottles You Buy** *(Default — realistic pharmacy billing)*: If a patient needs `14` tablets (`2/day` for `7` days) and strips come in `10` tablets, you have to buy **2 full strips** (`ceil(14 / 10) = 2`). This mode calculates the real amount paid at the chemist counter!
     - **Exact Tablet / Dose Cost**: Multiplies exact tablets needed × price per tablet.
   - **`Print List for Chemist`**: Opens a clean print-friendly dispensing slip (hiding web buttons/headers) listing the active salt names and chosen alternatives to hand to a pharmacist or Jan Aushadhi Kendra.
   - **`Clear All`**: Empties the bill.
   - *(Note: The cart automatically saves in the browser's `localStorage`, so refreshing the page doesn't lose your list.)*

2. **4 Summary Cards**:
   - **Prescribed Brands Total** (Red) — What the original branded prescription would cost.
   - **Cheaper Alternatives Total** (Blue) — What the verified cheaper alternatives cost.
   - **Total Money Saved** (Green) — Exact rupees and percentage saved on this bill.
   - **Yearly Savings (If Taken Monthly)** (Green) — `12×` projection for chronic monthly medications.

3. **Bill Table Columns**:
   - **Prescribed Medicine & Salt**: Original drug, active salts, form & release speed, and `Sensitive Dose` badge if NTI.
   - **How Many You Need**: Live editable `1/day–4/day` + `days` (or `packs` for syrups/inhalers). Below it shows exact math, e.g., `30 tablets total (buy 3 strips of 10)`.
   - **Chosen Alternative**: Dropdown letting the user pick **any** of the top 5 safe alternatives or **Keep Prescribed Brand** (`Kept original` neutral badge).
   - **Original Cost / New Cost / You Save / Remove**: Real-time cost comparison per row plus a delete button.

---

## 3. What Happens Behind the Scenes (Without Technical Jargon)

1. **Why Not Use ChatGPT / an AI LLM?**
   - An AI language model can hallucinate a wrong milligram strength (`50mg` vs `500mg`), confuse *Sustained Release* with *Immediate Release*, or invent a fake price.
   - EquiMed-India is **100% deterministic**: every medicine comes from a verified database and passes 7 strict clinical rules before it is ever shown.

2. **How Did We Clean the 2.5 Lakh (253,973) Dataset Safely?**
   - When real retail pharmacy CSV data is messy, guessing is dangerous. Our ingestion pipeline (`scripts/ingest_az_dataset.py`) follows **Strict Clinical Quarantine**:
     - Rows with missing prices (`4`), non-allopathy items, unknown/non-comparable forms like soaps/shampoos/sachets (`4,393`), missing strengths (`6,329`), or truncated 3+ salt combinations are **quarantined** instead of guessed.
     - Curated PMBJP Jan Aushadhi & WHO-GMP records (`1,021`) always take deduplication priority over duplicate retail rows.
     - Names with `"Dr."` (like `Dr. Morepen`) are carefully protected so they aren't mistaken for `"DR"` (Delayed Release / Enteric Coated)!

3. **The 7 Safety Rules Every Substitute Must Pass**:
   1. Not the exact same product.
   2. **Not discontinued** (`Is_discontinued = False`).
   3. Exact same active ingredient(s) — zero missing or extra chemicals.
   4. Exact same strength (automatically converting `0.5 g` ↔ `500 mg`, `50 mcg` ↔ `0.05 mg`, `125 mg/5ml` ↔ `25 mg/ml`).
   5. Compatible dosage form (never swaps a tablet for a syrup or injection).
   6. Exact same release speed (never swaps Slow/Extended/Enteric-coated release with Normal/Immediate release).
   7. Equal or lower price per unit (never recommends a costlier drug).

---

## 4. Suggested 3-Minute Live Demo Flow

1. **Start at the Top Bar**: Point out **`240,199 FORMULATIONS ACTIVE`** and explain that this is a live local SQLite + FTS5 index built from the A–Z Indian Medicines dataset + Jan Aushadhi curated data.
2. **Demo 1 — Instant Brand Lookup (`Telma 40`)**: Show the summary card (`Telmisartan 40mg`, `Tablet · Normal Release`) and point out the verified alternatives sorted by **Lowest Price First** vs switching the dropdown to **Govt. Jan Aushadhi Stores First**.
3. **Demo 2 — Ingredient / Synonym Search (`Acetaminophen`)**: Type `Acetaminophen` in the search box to show it automatically resolves Indian `Paracetamol` brands (proving chemical synonym normalization).
4. **Demo 3 — Safety Guardrail (`Thyronorm 50`)**: Click `Thyronorm 50 (Sensitive Dose)` to show the yellow **`Sensitive Dose — Ask Doctor Before Switching`** alert for Narrow Therapeutic Index medicines.
5. **Demo 4 — Build a Prescription Bill**: Click **`+ Pick This Option`** on 2 medicines (e.g. `Telma 40` + `Augmentin 625`), scroll to **My Medicine Bill & Savings**, change duration to `14` days (`2/day`), toggle **Full Strips / Bottles You Buy** vs **Exact Tablet / Dose Cost**, and click **`Print List for Chemist`** to show the clean printable slip.

---

## 5. Likely Presentation / Viva Questions & Simple Answers

1. **Q: Why does a medicine like `Soliris` not show up when searched?**
   - **A:** Soliris (*eculizumab*) is an ultra-rare hospital biologic not sold on regular Indian retail pharmacy counters, so it isn't in the 2.53L retail dataset. Because EquiMed never guesses or hallucinates drugs, it honestly reports *"Could not find it in our retail medicine database."*
2. **Q: Why did you keep discontinued medicines searchable if they are unsafe to recommend?**
   - **A:** Patients often bring an old prescription with a discontinued brand name. Keeping it searchable as the **input** lets the patient still look up what chemical was in it and see **currently active, available replacements**—while Rule 0b strictly guarantees a discontinued brand is *never* recommended as a substitute.
3. **Q: Why do you keep *Metoprolol Succinate* separate from *Metoprolol Tartrate*?**
   - **A:** Even though both contain Metoprolol, their salt esters have different absorption/dosing profiles clinically (often extended-release succinate vs immediate-release tartrate). Treating them as separate chemical salts prevents unsafe substitutions.
4. **Q: How is "Full Strips / Bottles" billing different from "Exact Dose Cost"?**
   - **A:** Indian pharmacies sell whole strips (e.g., 10 tablets per strip), not loose half-strips. If you need 14 tablets, you must pay for 2 strips (20 tablets). Our bill calculator shows both the theoretical per-tablet savings and the real-world counter bill.
5. **Q: How do you keep search fast (< 4 ms) across 240,199 medicines without paid databases?**
   - **A:** We compile the cleaned data once into SQLite with B-tree composite indexes (`salt_fingerprint`, `is_discontinued`, `price_per_unit`) and an **FTS5** full-text search index, which comes built into Python's standard library.
