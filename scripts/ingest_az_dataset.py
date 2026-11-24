"""Zero-Dependency ETL Pipeline & Downloader for A-Z Indian Medicines Dataset.

Downloads (optional) and ingests `A_Z_medicines_dataset_of_India.csv` (~253k rows)
merged with `data/medicine_catalog.json` (1,021 curated gold records) into an
indexed SQLite + FTS5 database (`data/equimed_catalog.db`) with strict clinical
quarantine rules and an audit report (`data/ingestion_report.json`).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.models import DosageForm, Medicine, RegulatoryTier, ReleaseType, SaltComponent
from src.repository import _normalize_text
from src.safety_engine import SafetyEngine

DOWNLOAD_ENDPOINTS = [
    (
        "Kaggle Public Dataset Endpoint",
        "https://www.kaggle.com/api/v1/datasets/download/shudhanshusingh/az-medicine-dataset-of-india",
    ),
    (
        "Hugging Face Public Mirror",
        "https://huggingface.co/spaces/MahatirTusher/DrugScan/resolve/main/A_Z_medicines_dataset_of_India.csv",
    ),
]

SUPPORTED_STRENGTH_UNITS = {
    "mg", "g", "gm", "gms", "mcg", "µg", "ug", "iu", "ml", "%",
    "%w/v", "w/v%", "%w/w", "w/w%", "%v/v", "v/v%",
    "mg/ml", "g/ml", "gm/ml", "mcg/ml", "µg/ml", "ug/ml",
    "mg/5ml", "g/5ml", "gm/5ml", "mcg/5ml", "µg/5ml", "ug/5ml", "mg/15ml",
    "iu/ml", "iu/5ml",
    "mcg/puff", "µg/puff", "ug/puff", "mg/puff",
    "mcg/actuation", "µg/actuation", "ug/actuation", "mg/actuation",
    "mcg/dose", "µg/dose", "ug/dose", "mg/dose",
    "mcg/spray", "µg/spray", "ug/spray", "mg/spray",
    "mg/g", "g/g", "gm/g", "mcg/g", "µg/g", "ug/g", "iu/g",
}

_SALT_CELL_RE = re.compile(
    r"^(.+?)\s*\(\s*(\d+(?:,\d+)*(?:\.\d+)?|\.\d+)\s*([a-zA-Zµμ%][a-zA-Zµμ%\s/0-9]*?)\s*\)\s*$"
)
_TRUNCATION_RE = re.compile(r"(?:\+$|(?:^|[\s),])(?:\.\.\.|…|etc\.?|and\s+others)\s*$)", re.IGNORECASE)

_ALLOWED_POWDER_OR_SPRAY_RE = re.compile(
    r"\b(?:dry\s+syrups?|powder\s+for\s+(?:oral\s+)?suspension|powder\s+for\s+injection|nasal\s+sprays?)\b",
    re.IGNORECASE,
)
_UNSUPPORTED_FORM_RE = re.compile(
    r"\b(?:soap|soaps|shampoo|shampoos|sachet|sachets|suppository|suppositories|patch|patches|"
    r"kit|kits|device|devices|mouthwash|gargle|lotion|lotions|granules|lozenge|lozenges|"
    r"pastille|pastilles|pessary|pessaries|enema|toothpaste|face\s+wash|body\s+wash|wash|"
    r"scrub|balm|liniment|oil|powder|powders)\b",
    re.IGNORECASE,
)

_FORM_PATTERNS: List[Tuple[DosageForm, re.Pattern[str]]] = [
    (DosageForm.DROPS, re.compile(r"\b(?:(?:eye|ear|nasal|oral|ophthalmic|otic)\s+)?drops?\b", re.I)),
    (DosageForm.INHALER, re.compile(r"\b(?:inhalers?|mdi|dpi|rotacaps?|respules?|nasal\s+sprays?|transcaps?|autohalers?)\b", re.I)),
    (DosageForm.INJECTION, re.compile(r"\b(?:injections?|inj\.?|vials?|ampoules?|prefilled\s+syringes?|pens?|infusions?|powder\s+for\s+injection)\b", re.I)),
    (DosageForm.SYRUP, re.compile(r"\b(?:syrups?|suspensions?|elixirs?|oral\s+liquids?|oral\s+solutions?|dry\s+syrups?|powder\s+for\s+(?:oral\s+)?suspension)\b", re.I)),
    (DosageForm.OINTMENT, re.compile(r"\b(?:ointments?|creams?|gels?|emulgels?|pastes?)\b", re.I)),
    (DosageForm.CAPSULE, re.compile(r"\b(?:capsules?|caps?|softgels?)\b", re.I)),
    (DosageForm.TABLET, re.compile(r"\b(?:tablets?|tabs?)\b", re.I)),
]

_PACK_MULTI_RE = re.compile(
    r"(\d+)\s*(?:strips?|blisters?|cards?)\s+of\s+(\d+)\s*(?:tablets?|tabs?|capsules?|caps?|softgels?)",
    re.I,
)
_PACK_MUL_RE = re.compile(
    r"(\d+)\s*[xX×]\s*(\d+)\s*(?:tablets?|tabs?|capsules?|caps?|softgels?)?",
    re.I,
)
_PACK_OF_N_RE = re.compile(
    r"\b(?:strip|bottle|jar|pack|blister|box|card|tube|vial)\s+of\s+(\d+)\s*(?:tablets?|tabs?|capsules?|caps?|softgels?)?",
    re.I,
)
_PACK_N_UNITS_RE = re.compile(
    r"\b(\d+)\s*(?:tablets?|tabs?|capsules?|caps?|softgels?)\b",
    re.I,
)

_PMBJP_RE = re.compile(r"\b(?:pmbjp|bppi|jan\s*aushadhi)\b", re.I)


def validate_az_csv_header(csv_path: Path) -> Tuple[bool, str]:
    """Verify the CSV starts with expected A-Z Indian Medicines headers."""
    try:
        with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            header = next(reader, None)
    except Exception as exc:
        return False, f"Failed reading CSV header: {exc}"

    if not header:
        return False, "Empty CSV file"

    cols = {c.strip().lower() for c in header}
    required = {"name", "short_composition1", "pack_size_label", "is_discontinued"}
    missing = required - cols
    has_price = any(c.startswith("price") for c in cols)
    if missing or not has_price:
        return False, f"Invalid A-Z CSV header; missing={sorted(missing)}, has_price={has_price}"
    return True, "OK"


def download_az_dataset(target_csv: Path, force: bool = False) -> Path:
    """Download A_Z_medicines_dataset_of_India.csv using pure stdlib urllib + zipfile."""
    target_csv.parent.mkdir(parents=True, exist_ok=True)
    if target_csv.exists() and not force:
        ok, _ = validate_az_csv_header(target_csv)
        if ok:
            print(f"[download] Using existing verified CSV at {target_csv}")
            return target_csv

    errors: List[str] = []
    for label, url in DOWNLOAD_ENDPOINTS:
        tmp_download = target_csv.with_suffix(".download.tmp")
        tmp_extracted = target_csv.with_suffix(".csv.tmp")
        try:
            print(f"[download] Trying {label}: {url}")
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "EquiMed-India/1.0 (Academic Clinical Formulary)"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                status = getattr(resp, "status", 200)
                if status != 200:
                    raise urllib.error.HTTPError(url, status, f"HTTP {status}", resp.headers, None)
                with open(tmp_download, "wb") as out_f:
                    while True:
                        chunk = resp.read(1024 * 256)
                        if not chunk:
                            break
                        out_f.write(chunk)

            if not tmp_download.exists() or tmp_download.stat().st_size < 1024:
                raise ValueError("Downloaded payload too small or empty")

            with open(tmp_download, "rb") as chk:
                magic = chk.read(4)

            if magic == b"PK\x03\x04":
                with zipfile.ZipFile(tmp_download, "r") as zf:
                    csv_members = [m for m in zf.infolist() if m.filename.lower().endswith(".csv")]
                    if not csv_members:
                        raise ValueError("Zip archive contained no CSV file")
                    best = max(csv_members, key=lambda m: m.file_size)
                    with zf.open(best, "r") as src_f, open(tmp_extracted, "wb") as dst_f:
                        while True:
                            buf = src_f.read(1024 * 256)
                            if not buf:
                                break
                            dst_f.write(buf)
                tmp_download.unlink(missing_ok=True)
            else:
                os.replace(tmp_download, tmp_extracted)

            ok, reason = validate_az_csv_header(tmp_extracted)
            if not ok:
                raise ValueError(reason)

            os.replace(tmp_extracted, target_csv)
            size_mb = target_csv.stat().st_size / (1024 * 1024)
            print(f"[download] Successfully downloaded & verified {target_csv} ({size_mb:.2f} MB)")
            return target_csv

        except Exception as exc:
            errors.append(f"{label}: {exc}")
            for p in (tmp_download, tmp_extracted):
                try:
                    if p.exists():
                        p.unlink()
                except OSError:
                    pass

    print("\n[download] Automatic download failed across all public endpoints:")
    for err in errors:
        print(f"  - {err}")
    print(
        "\nManual 2-step fallback:\n"
        "  1. Download `A_Z_medicines_dataset_of_India.csv` from Kaggle "
        "(https://www.kaggle.com/datasets/shudhanshusingh/az-medicine-dataset-of-india) "
        f"and place it at:\n     {target_csv}\n"
        "  2. Run:\n     python scripts/ingest_az_dataset.py\n"
    )
    raise RuntimeError("Dataset download blocked or unavailable from public endpoints.")


def _split_top_level_plus(text: str) -> List[str]:
    """Split a composition cell on '+' only outside parentheses."""
    parts: List[str] = []
    depth = 0
    start = 0
    for idx, ch in enumerate(text):
        if ch == "(":
            depth += 1
        elif ch == ")" and depth > 0:
            depth -= 1
        elif ch == "+" and depth == 0:
            segment = text[start:idx].strip()
            if segment:
                parts.append(segment)
            start = idx + 1
    tail = text[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def _canonicalize_unit_display(raw_unit: str) -> Optional[str]:
    """Validate and normalize strength unit string against pharmaceutical whitelist."""
    collapsed = re.sub(r"\s+", "", raw_unit.strip()).replace("μ", "µ")
    key = collapsed.lower()
    if key not in SUPPORTED_STRENGTH_UNITS:
        return None
    if key in ("%w/v", "w/v%"):
        return "% w/v"
    if key in ("%w/w", "w/w%"):
        return "% w/w"
    if key in ("%v/v", "v/v%"):
        return "% v/v"
    if key in ("µg", "ug"):
        return "mcg"
    return collapsed.replace("µg", "mcg").replace("ug", "mcg")


def _parse_salts(comp1: str, comp2: str) -> Tuple[Optional[List[SaltComponent]], Optional[str]]:
    """Parse short_composition1 and short_composition2 with strict 3+ salt quarantine."""
    c1 = comp1.strip()
    c2 = comp2.strip()

    if not c1 and not c2:
        return None, "missing_composition"

    if c2 and _TRUNCATION_RE.search(c2):
        return None, "truncated_multi_salt"

    if c1:
        if re.search(r"(?:^|[\s),])(?:\.\.\.|…|etc\.?|and\s+others)\s*$", c1, re.I):
            return None, "truncated_multi_salt"
        if c1.endswith("+"):
            if not c2:
                return None, "truncated_multi_salt"
            c1 = c1[:-1].strip()

    tokens: List[str] = []
    if c1:
        tokens.extend(_split_top_level_plus(c1))
    if c2:
        tokens.extend(_split_top_level_plus(c2))

    if not tokens:
        return None, "missing_composition"

    salts: List[SaltComponent] = []
    for tok in tokens:
        m = _SALT_CELL_RE.match(tok)
        if not m:
            return None, "invalid_or_missing_strength"
        salt_name = re.sub(r"\s+", " ", m.group(1)).strip()
        num_str = m.group(2).replace(",", "")
        unit_raw = m.group(3)
        if not salt_name:
            return None, "invalid_or_missing_strength"
        try:
            val = float(num_str)
        except ValueError:
            return None, "invalid_or_missing_strength"
        if math.isnan(val) or math.isinf(val) or val <= 0:
            return None, "invalid_or_missing_strength"
        unit = _canonicalize_unit_display(unit_raw)
        if not unit:
            return None, "invalid_or_missing_strength"
        salts.append(SaltComponent(name=salt_name, strength_value=val, strength_unit=unit))

    return salts, None


def _classify_dosage_form(pack_label: str, name: str) -> Optional[DosageForm]:
    """Classify supported dosage form and quarantine unsupported/unknown retail forms."""
    label_clean = pack_label.strip()
    name_clean = name.strip()

    # Reject explicitly unsupported pack forms unless it's an allowed dry syrup / nasal spray
    if label_clean and _UNSUPPORTED_FORM_RE.search(label_clean):
        if not _ALLOWED_POWDER_OR_SPRAY_RE.search(label_clean):
            return None

    for form, pattern in _FORM_PATTERNS:
        if label_clean and pattern.search(label_clean):
            return form

    # Check name for unsupported forms only if pack_size_label didn't match a supported form
    if name_clean and _UNSUPPORTED_FORM_RE.search(name_clean):
        if not _ALLOWED_POWDER_OR_SPRAY_RE.search(name_clean):
            return None

    for form, pattern in _FORM_PATTERNS:
        if name_clean and pattern.search(name_clean):
            return form

    return None


def _extract_release_type(name: str, pack_label: str) -> ReleaseType:
    """Extract release kinetics while guarding against 'Dr.' brand prefixes (e.g. Dr. Morepen)."""
    combined = f"{name} {pack_label}"
    if re.search(r"\b(?:CR|Controlled[\s-]+Release)\b", combined, re.I):
        return ReleaseType.CONTROLLED_RELEASE
    if re.search(r"\b(?:ER|XR|XL|PR|Extended[\s-]+Release|Prolonged[\s-]+Release)\b", combined, re.I):
        return ReleaseType.EXTENDED_RELEASE
    if re.search(r"\b(?:SR|Sustained[\s-]+Release)\b", combined, re.I):
        return ReleaseType.SUSTAINED_RELEASE
    if re.search(r"\b(?:MR(?!\.)|Modified[\s-]+Release)\b", combined, re.I):
        return ReleaseType.MODIFIED_RELEASE
    if re.search(r"\b(?:EC(?!\.)|Enteric[\s-]+Coated|Delayed[\s-]+Release|Gastro[\s-]+Resistant)\b", combined, re.I):
        return ReleaseType.ENTERIC_COATED
    # DR is only Enteric Coated when NOT followed by '.' and either in pack_size_label or
    # non-leading in name followed by end-of-string, digits, or dosage words.
    if pack_label and re.search(r"\bDR(?!\.)\b", pack_label, re.I):
        return ReleaseType.ENTERIC_COATED
    if re.search(r"(?<=\s)DR(?!\.)(?=\s*(?:$|\d|mg|mcg|tab|cap|tablet|capsule))", name, re.I):
        return ReleaseType.ENTERIC_COATED
    if re.search(r"[-/]DR(?!\.)\b", name, re.I):
        return ReleaseType.ENTERIC_COATED
    return ReleaseType.IMMEDIATE_RELEASE


def _parse_pack_size(dosage_form: DosageForm, pack_label: str) -> Optional[int]:
    """Determine pack_size matching existing catalog conventions (1 for pack-only forms)."""
    if dosage_form in SafetyEngine.PACK_ONLY_FORMS:
        return 1

    text = pack_label.strip()
    if not text:
        return None

    m_multi = _PACK_MULTI_RE.search(text)
    if m_multi:
        qty = int(m_multi.group(1)) * int(m_multi.group(2))
        return qty if 1 <= qty <= 1000 else None

    m_mul = _PACK_MUL_RE.search(text)
    if m_mul:
        qty = int(m_mul.group(1)) * int(m_mul.group(2))
        return qty if 1 <= qty <= 1000 else None

    m_of = _PACK_OF_N_RE.search(text)
    if m_of:
        qty = int(m_of.group(1))
        return qty if 1 <= qty <= 1000 else None

    m_units = _PACK_N_UNITS_RE.search(text)
    if m_units:
        qty = int(m_units.group(1))
        return qty if 1 <= qty <= 1000 else None

    return None


def _parse_price(raw_val: str) -> Optional[float]:
    cleaned = re.sub(r"[₹,\s]", "", raw_val.strip())
    if not cleaned:
        return None
    try:
        price = float(cleaned)
    except ValueError:
        return None
    if math.isnan(price) or math.isinf(price) or price <= 0:
        return None
    return round(price, 4)


def _write_sqlite_catalog(medicines: List[Medicine], out_db_path: Path) -> None:
    """Atomically write medicines, salt index, and FTS5 table into SQLite DB."""
    out_db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_db = out_db_path.with_suffix(".db.tmp")
    if tmp_db.exists():
        tmp_db.unlink()

    conn = sqlite3.connect(str(tmp_db))
    try:
        conn.execute("PRAGMA journal_mode = OFF")
        conn.execute("PRAGMA synchronous = OFF")
        conn.execute("PRAGMA temp_store = MEMORY")
        conn.execute("PRAGMA cache_size = -64000")

        conn.executescript(
            """
            CREATE TABLE medicines (
                id TEXT PRIMARY KEY,
                brand_name TEXT NOT NULL,
                brand_lower TEXT NOT NULL,
                brand_norm TEXT NOT NULL,
                manufacturer TEXT NOT NULL,
                salts_json TEXT NOT NULL,
                salts_text TEXT NOT NULL,
                salt_fingerprint TEXT NOT NULL,
                dosage_form TEXT NOT NULL,
                release_type TEXT NOT NULL,
                pack_size INTEGER NOT NULL,
                pack_size_label TEXT NOT NULL,
                mrp REAL NOT NULL,
                price_per_unit REAL NOT NULL,
                regulatory_tier TEXT NOT NULL,
                is_narrow_therapeutic_index INTEGER NOT NULL,
                therapeutic_category TEXT NOT NULL,
                is_discontinued INTEGER NOT NULL,
                source TEXT NOT NULL
            );

            CREATE TABLE medicine_salts (
                canonical_salt TEXT NOT NULL,
                medicine_id TEXT NOT NULL,
                PRIMARY KEY (canonical_salt, medicine_id)
            ) WITHOUT ROWID;

            CREATE VIRTUAL TABLE medicines_fts USING fts5(
                brand_name,
                brand_norm,
                salts_text,
                manufacturer,
                content='medicines',
                content_rowid='rowid',
                tokenize='unicode61'
            );
            """
        )

        med_rows: List[Tuple[Any, ...]] = []
        salt_rows: List[Tuple[str, str]] = []

        for med in medicines:
            brand_lower = med.brand_name.strip().lower()
            brand_norm = _normalize_text(med.brand_name)
            salts_json = json.dumps([s.to_dict() for s in med.salts], ensure_ascii=False)
            canonical_salts = sorted({SafetyEngine.normalize_salt_name(s.name) for s in med.salts})
            raw_salts_text = " ".join(
                sorted({s.name.strip() for s in med.salts} | set(canonical_salts))
            )
            fp = med.salt_fingerprint()

            med_rows.append((
                med.id,
                med.brand_name,
                brand_lower,
                brand_norm,
                med.manufacturer,
                salts_json,
                raw_salts_text,
                fp,
                med.dosage_form.value,
                med.release_type.value,
                med.pack_size,
                med.pack_size_label,
                med.mrp,
                med.price_per_unit,
                med.regulatory_tier.value,
                1 if med.is_narrow_therapeutic_index else 0,
                med.therapeutic_category,
                1 if med.is_discontinued else 0,
                med.source,
            ))
            for cs in canonical_salts:
                salt_rows.append((cs, med.id))

        conn.executemany(
            """
            INSERT INTO medicines (
                id, brand_name, brand_lower, brand_norm, manufacturer,
                salts_json, salts_text, salt_fingerprint, dosage_form,
                release_type, pack_size, pack_size_label, mrp, price_per_unit,
                regulatory_tier, is_narrow_therapeutic_index,
                therapeutic_category, is_discontinued, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            med_rows,
        )
        conn.executemany(
            "INSERT OR IGNORE INTO medicine_salts (canonical_salt, medicine_id) VALUES (?, ?)",
            salt_rows,
        )

        conn.execute("INSERT INTO medicines_fts(medicines_fts) VALUES('rebuild')")

        conn.executescript(
            """
            CREATE INDEX idx_medicines_brand_lower ON medicines(brand_lower);
            CREATE INDEX idx_medicines_brand_norm ON medicines(brand_norm);
            CREATE INDEX idx_medicines_fp ON medicines(salt_fingerprint);
            CREATE INDEX idx_medicines_sub_lookup ON medicines(salt_fingerprint, is_discontinued, price_per_unit);
            CREATE INDEX idx_medicines_tier_lookup ON medicines(salt_fingerprint, regulatory_tier, is_discontinued, price_per_unit);
            CREATE INDEX idx_medicines_source ON medicines(source);
            CREATE INDEX idx_medicine_salts_med_id ON medicine_salts(medicine_id);
            ANALYZE;
            """
        )
        conn.commit()
    finally:
        conn.close()

    os.replace(tmp_db, out_db_path)


def ingest_az_dataset(
    csv_path: str | Path,
    curated_path: str | Path,
    out_db_path: str | Path,
    report_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """Run deterministic ETL merging curated JSON and A-Z CSV into SQLite + FTS5."""
    t0 = time.perf_counter()
    csv_p = Path(csv_path)
    curated_p = Path(curated_path)
    out_p = Path(out_db_path)

    if not curated_p.exists():
        raise FileNotFoundError(f"Curated catalog not found: {curated_p}")
    if not csv_p.exists():
        raise FileNotFoundError(f"A-Z CSV file not found: {csv_p}")

    # 1. Load curated Layer 1 records first (priority in deduplication)
    with open(curated_p, "r", encoding="utf-8") as f:
        curated_raw = json.load(f)

    dedup_map: Dict[Tuple[str, str], Medicine] = {}
    curated_count = 0
    for item in curated_raw:
        item_copy = dict(item)
        item_copy.setdefault("source", "curated")
        item_copy.setdefault("is_discontinued", False)
        item_copy.setdefault("pack_size_label", "")
        med = Medicine.from_dict(item_copy)
        key = (_normalize_text(med.brand_name), med.salt_fingerprint())
        dedup_map[key] = med
        curated_count += 1

    # 2. Stream and validate A-Z CSV Layer 2 rows
    quarantine_counts: Counter[str] = Counter()
    csv_rows_read = 0
    az_valid_parsed = 0
    az_discontinued_parsed = 0
    duplicates_curated_skipped = 0
    duplicates_az_skipped = 0

    with open(csv_p, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"Empty CSV header in {csv_p}")

        col_map: Dict[str, str] = {}
        price_col: Optional[str] = None
        for col in reader.fieldnames:
            low = col.strip().lower()
            col_map[low] = col
            if price_col is None and low.startswith("price"):
                price_col = col

        if price_col is None:
            raise ValueError("Price column not found in A-Z CSV")

        id_col = col_map.get("id")
        name_col = col_map.get("name")
        disc_col = col_map.get("is_discontinued")
        mfg_col = col_map.get("manufacturer_name")
        type_col = col_map.get("type")
        pack_col = col_map.get("pack_size_label")
        comp1_col = col_map.get("short_composition1")
        comp2_col = col_map.get("short_composition2")

        for row_idx, row in enumerate(reader, 1):
            csv_rows_read += 1

            raw_name = (row.get(name_col) or "").strip() if name_col else ""
            if not raw_name:
                quarantine_counts["missing_name"] += 1
                continue

            raw_type = (row.get(type_col) or "").strip().lower() if type_col else ""
            if raw_type != "allopathy":
                quarantine_counts["non_allopathy"] += 1
                continue

            mrp = _parse_price(row.get(price_col) or "")
            if mrp is None:
                quarantine_counts["invalid_price"] += 1
                continue

            comp1 = (row.get(comp1_col) or "").strip() if comp1_col else ""
            comp2 = (row.get(comp2_col) or "").strip() if comp2_col else ""
            salts, salt_err = _parse_salts(comp1, comp2)
            if salt_err or not salts:
                quarantine_counts[salt_err or "invalid_or_missing_strength"] += 1
                continue

            pack_label = (row.get(pack_col) or "").strip() if pack_col else ""
            dosage_form = _classify_dosage_form(pack_label, raw_name)
            if dosage_form is None:
                quarantine_counts["unsupported_or_unknown_form"] += 1
                continue

            pack_size = _parse_pack_size(dosage_form, pack_label)
            if pack_size is None:
                quarantine_counts["invalid_pack_size"] += 1
                continue

            price_per_unit = round(mrp / pack_size, 4)
            release_type = _extract_release_type(raw_name, pack_label)

            raw_disc = (row.get(disc_col) or "").strip().upper() if disc_col else ""
            is_discontinued = raw_disc in ("TRUE", "1", "YES")

            manufacturer = ((row.get(mfg_col) or "").strip() if mfg_col else "") or "Unknown"
            reg_tier = (
                RegulatoryTier.PMBJP_JAN_AUSHADHI
                if _PMBJP_RE.search(manufacturer)
                else RegulatoryTier.BRANDED_GENERIC
            )

            is_nti = any(
                SafetyEngine.normalize_salt_name(s.name) in SafetyEngine.NTI_SUBSTANCES
                for s in salts
            )

            raw_id = ((row.get(id_col) or "").strip() if id_col else "") or str(row_idx)
            med = Medicine(
                id=f"AZ-{raw_id}",
                brand_name=raw_name,
                manufacturer=manufacturer,
                salts=salts,
                dosage_form=dosage_form,
                release_type=release_type,
                pack_size=pack_size,
                mrp=mrp,
                price_per_unit=price_per_unit,
                regulatory_tier=reg_tier,
                is_narrow_therapeutic_index=is_nti,
                therapeutic_category="Retail Allopathy (A-Z)",
                is_discontinued=is_discontinued,
                pack_size_label=pack_label,
                source="az_india_csv",
            )

            az_valid_parsed += 1
            if is_discontinued:
                az_discontinued_parsed += 1

            dedup_key = (_normalize_text(med.brand_name), med.salt_fingerprint())
            existing = dedup_map.get(dedup_key)
            if existing is not None:
                if existing.source == "curated":
                    duplicates_curated_skipped += 1
                    continue
                duplicates_az_skipped += 1
                # Prefer active over discontinued, then lowest valid MRP
                if existing.is_discontinued and not med.is_discontinued:
                    dedup_map[dedup_key] = med
                elif existing.is_discontinued == med.is_discontinued and med.mrp < existing.mrp:
                    dedup_map[dedup_key] = med
            else:
                dedup_map[dedup_key] = med

    final_medicines = list(dedup_map.values())
    _write_sqlite_catalog(final_medicines, out_p)

    az_inserted = sum(1 for m in final_medicines if m.source != "curated")
    discontinued_indexed = sum(1 for m in final_medicines if m.is_discontinued)
    elapsed_sec = round(time.perf_counter() - t0, 3)

    report = {
        "csv_path": str(csv_p),
        "curated_path": str(curated_p),
        "output_db_path": str(out_p),
        "curated_loaded": curated_count,
        "csv_rows_read": csv_rows_read,
        "az_valid_parsed": az_valid_parsed,
        "az_discontinued_parsed": az_discontinued_parsed,
        "az_inserted": az_inserted,
        "discontinued_indexed": discontinued_indexed,
        "total_medicines_indexed": len(final_medicines),
        "duplicates_curated_skipped": duplicates_curated_skipped,
        "duplicates_az_skipped": duplicates_az_skipped,
        "quarantined_total": sum(quarantine_counts.values()),
        "quarantined_by_reason": dict(sorted(quarantine_counts.items())),
        "elapsed_seconds": elapsed_sec,
    }

    if report_path is not None:
        rep_p = Path(report_path)
        rep_p.parent.mkdir(parents=True, exist_ok=True)
        tmp_rep = rep_p.with_suffix(".json.tmp")
        with open(tmp_rep, "w", encoding="utf-8") as rf:
            json.dump(report, rf, indent=2)
        os.replace(tmp_rep, rep_p)

    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="EquiMed-India A-Z Indian Medicines Dataset Downloader & SQLite ETL"
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download A_Z_medicines_dataset_of_India.csv into --csv path if missing",
    )
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Re-download CSV even if already present locally",
    )
    parser.add_argument(
        "--csv",
        default=str(_ROOT / "data" / "raw" / "A_Z_medicines_dataset_of_India.csv"),
        help="Path to A_Z_medicines_dataset_of_India.csv",
    )
    parser.add_argument(
        "--curated",
        default=str(_ROOT / "data" / "medicine_catalog.json"),
        help="Path to curated gold JSON catalog",
    )
    parser.add_argument(
        "--out",
        default=str(_ROOT / "data" / "equimed_catalog.db"),
        help="Output SQLite + FTS5 database path",
    )
    parser.add_argument(
        "--report",
        default=str(_ROOT / "data" / "ingestion_report.json"),
        help="Output JSON ingestion audit report path",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if args.download or args.force_download:
        try:
            download_az_dataset(csv_path, force=args.force_download)
        except Exception:
            return 1

    if not csv_path.exists():
        print(f"ERROR: CSV file not found at {csv_path}")
        print("Run with --download or place A_Z_medicines_dataset_of_India.csv in data/raw/ first.")
        return 1

    report = ingest_az_dataset(
        csv_path=csv_path,
        curated_path=args.curated,
        out_db_path=args.out,
        report_path=args.report,
    )

    print("\n" + "=" * 72)
    print("  EquiMed-India A-Z Dataset Ingestion Complete")
    print("=" * 72)
    print(f"  Curated Gold Loaded      : {report['curated_loaded']:,}")
    print(f"  CSV Rows Read            : {report['csv_rows_read']:,}")
    print(f"  A-Z Records Inserted     : {report['az_inserted']:,}")
    print(f"  Discontinued Indexed     : {report['discontinued_indexed']:,} (searchable as input only)")
    print(f"  Total Indexed in SQLite  : {report['total_medicines_indexed']:,}")
    print(f"  Duplicates Skipped       : {report['duplicates_curated_skipped'] + report['duplicates_az_skipped']:,}")
    print(f"  Quarantined Total        : {report['quarantined_total']:,}")
    for reason, cnt in report["quarantined_by_reason"].items():
        print(f"    - {reason:<30}: {cnt:,}")
    print(f"  Elapsed Time             : {report['elapsed_seconds']}s")
    print(f"  Database Output          : {report['output_db_path']}")
    print(f"  Report Output            : {args.report}")
    print("=" * 72 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
