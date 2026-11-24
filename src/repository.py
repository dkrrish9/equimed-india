"""Data Repository with Inverted In-Memory Indexes and SQLite + FTS5 Backend."""

from __future__ import annotations

import json
import os
import random
import re
import sqlite3
import threading
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union

from src.models import DosageForm, Medicine, RegulatoryTier, ReleaseType, SaltComponent
from src.safety_engine import SafetyEngine


def _normalize_text(text: str) -> str:
    """Lowercase and collapse hyphens/punctuation to single spaces."""
    cleaned = re.sub(r"[-_/.,()+]+", " ", text.strip().lower())
    return re.sub(r"\s+", " ", cleaned).strip()


class MedicineRepository:
    """Repository managing medicine data with multi-dimensional indexed lookups.

    Maintains:
    - ID Index: O(1) by primary ID.
    - Brand Name Index: O(1) normalized brand lookup (collision-safe).
    - Chemical Salt Fingerprint Index: O(1) lookup of all identical salt combinations.
    - Inverted Salt Component Index: Fast lookup by constituent salt active ingredients.
    """

    def __init__(self) -> None:
        self._by_id: Dict[str, Medicine] = {}
        self._by_brand_lower: Dict[str, Medicine] = {}
        self._by_brand_all: Dict[str, List[Medicine]] = {}
        self._by_brand_norm: Dict[str, List[Medicine]] = {}
        self._by_fingerprint: Dict[str, List[Medicine]] = {}
        self._by_salt: Dict[str, Set[str]] = {}  # salt_name -> set of medicine IDs
        # O(1) membership sets to avoid quadratic list scans during bulk inserts
        self._seen_brand_all_ids: Dict[str, Set[str]] = {}
        self._seen_brand_norm_ids: Dict[str, Set[str]] = {}
        self._seen_fp_ids: Dict[str, Set[str]] = {}
        self._brand_norm_cache: Dict[str, str] = {}

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Lowercase and collapse hyphens/punctuation to single spaces."""
        return _normalize_text(text)

    def add(self, medicine: Medicine) -> None:
        """Add medicine to all repository indexes in O(1) amortized time."""
        self._by_id[medicine.id] = medicine
        brand_clean = medicine.brand_name.strip().lower()
        # Keep deterministic first-or-cheapest primary brand without silently erasing collisions
        if brand_clean not in self._by_brand_lower:
            self._by_brand_lower[brand_clean] = medicine

        seen_all = self._seen_brand_all_ids.setdefault(brand_clean, set())
        if medicine.id not in seen_all:
            seen_all.add(medicine.id)
            self._by_brand_all.setdefault(brand_clean, []).append(medicine)

        brand_norm = self._brand_norm_cache.get(brand_clean)
        if brand_norm is None:
            brand_norm = self._normalize_text(medicine.brand_name)
            self._brand_norm_cache[brand_clean] = brand_norm

        seen_norm = self._seen_brand_norm_ids.setdefault(brand_norm, set())
        if medicine.id not in seen_norm:
            seen_norm.add(medicine.id)
            self._by_brand_norm.setdefault(brand_norm, []).append(medicine)

        fp = medicine.salt_fingerprint()
        seen_fp = self._seen_fp_ids.setdefault(fp, set())
        if medicine.id not in seen_fp:
            seen_fp.add(medicine.id)
            self._by_fingerprint.setdefault(fp, []).append(medicine)

        for s in medicine.salts:
            canonical_salt = SafetyEngine.normalize_salt_name(s.name)
            if canonical_salt not in self._by_salt:
                self._by_salt[canonical_salt] = set()
            self._by_salt[canonical_salt].add(medicine.id)

    def load_from_json(self, file_path: str | Path) -> int:
        """Load medicine catalog from a JSON file."""
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"Medicine catalog not found: {p}")

        with open(p, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        count = 0
        for item in raw_data:
            med = Medicine.from_dict(item)
            self.add(med)
            count += 1
        return count

    def get_by_id(self, med_id: str) -> Optional[Medicine]:
        return self._by_id.get(med_id)

    def get_by_brand_exact(self, brand_name: str) -> Optional[Medicine]:
        cleaned = brand_name.strip().lower()
        exact = self._by_brand_lower.get(cleaned)
        if exact:
            return exact
        norm = self._normalize_text(brand_name)
        matches = self._by_brand_norm.get(norm, [])
        return matches[0] if matches else None

    def search_by_brand(self, query: str, limit: int = 10) -> List[Medicine]:
        """Search by brand name (exact, prefix, token/normalized, substring) and active salt."""
        q = query.strip().lower()
        if not q:
            return []

        norm_q = self._normalize_text(query)
        q_tokens = [tok for tok in norm_q.split(" ") if tok]

        exact_matches: List[Medicine] = []
        norm_exact_matches: List[Medicine] = []
        prefix_matches: List[Medicine] = []
        token_matches: List[Medicine] = []
        contains_matches: List[Medicine] = []
        salt_matches: List[Medicine] = []

        for name, meds in self._by_brand_all.items():
            norm_name = self._brand_norm_cache.get(name)
            if norm_name is None:
                norm_name = self._normalize_text(name)
                self._brand_norm_cache[name] = norm_name

            if name == q:
                exact_matches.extend(meds)
            elif norm_q and norm_name == norm_q:
                norm_exact_matches.extend(meds)
            elif name.startswith(q) or (norm_q and norm_name.startswith(norm_q)):
                prefix_matches.extend(meds)
            elif q in name:
                contains_matches.extend(meds)
            elif q_tokens and all(tok in norm_name for tok in q_tokens):
                token_matches.extend(meds)

        # Active ingredient / canonical salt lookup (e.g. "Acetaminophen" -> Paracetamol brands)
        canonical_salt_q = SafetyEngine.normalize_salt_name(q)
        salt_id_candidates: Set[str] = set()
        if canonical_salt_q in self._by_salt:
            salt_id_candidates.update(self._by_salt[canonical_salt_q])
        else:
            for salt_key, med_ids in self._by_salt.items():
                if (norm_q and norm_q in salt_key) or (q_tokens and all(t in salt_key for t in q_tokens)):
                    salt_id_candidates.update(med_ids)

        for mid in salt_id_candidates:
            med = self._by_id.get(mid)
            if med:
                salt_matches.append(med)

        salt_matches.sort(key=lambda m: m.brand_name.lower())

        seen_ids: Set[str] = set()
        results: List[Medicine] = []
        for med in (
            exact_matches
            + norm_exact_matches
            + prefix_matches
            + contains_matches
            + token_matches
            + salt_matches
        ):
            if med.id not in seen_ids:
                seen_ids.add(med.id)
                results.append(med)
                if len(results) >= limit:
                    break
        return results

    def get_by_fingerprint(self, fingerprint: str) -> List[Medicine]:
        """Return all medicines with identical salt composition, dosage form, and release type."""
        return list(self._by_fingerprint.get(fingerprint, []))

    def get_candidates_by_salts(self, salts: List[SaltComponent]) -> List[Medicine]:
        """Find candidate medicines that share all specified active salts."""
        if not salts:
            return []

        candidate_id_sets: List[Set[str]] = []
        for s in salts:
            canonical_salt = SafetyEngine.normalize_salt_name(s.name)
            ids = self._by_salt.get(canonical_salt, set())
            candidate_id_sets.append(ids)

        if not candidate_id_sets:
            return []

        # Intersection: must contain all target salts
        common_ids = set.intersection(*candidate_id_sets)
        return [self._by_id[mid] for mid in common_ids if mid in self._by_id]

    def all_medicines(self) -> List[Medicine]:
        return list(self._by_id.values())

    def count(self) -> int:
        return len(self._by_id)


class SQLiteMedicineRepository:
    """Thread-safe SQLite + FTS5 repository supporting 250k+ medicines with sub-5ms lookups."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"SQLite catalog database not found: {self.db_path}")
        self._local = threading.local()
        self._conns_lock = threading.Lock()
        self._conns: List[sqlite3.Connection] = []
        self._priority_by_fp: Optional[Dict[str, List[Medicine]]] = None

    def _get_conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA temp_store = MEMORY")
            conn.execute("PRAGMA cache_size = -16000")
            try:
                mmap_mb = max(0, int(os.environ.get("EQUIMED_SQLITE_MMAP_MB", "256")))
            except ValueError:
                mmap_mb = 256
            try:
                conn.execute(f"PRAGMA mmap_size = {mmap_mb * 1024 * 1024}")
            except sqlite3.Error:
                pass
            conn.execute("PRAGMA query_only = ON")
            self._local.conn = conn
            with self._conns_lock:
                self._conns.append(conn)
        return conn

    def _get_priority_by_fp(self) -> Dict[str, List[Medicine]]:
        """Lazily cache active priority-tier generics grouped by salt fingerprint."""
        cached = self._priority_by_fp
        if cached is not None:
            return cached
        with self._conns_lock:
            if self._priority_by_fp is not None:
                return self._priority_by_fp
            conn = self._get_conn()
            rows = conn.execute(
                """
                SELECT * FROM medicines
                WHERE is_discontinued = 0
                  AND regulatory_tier IN ('PMBJP_JAN_AUSHADHI', 'WHO_GMP_GENERIC', 'CDSCO_APPROVED_GENERIC')
                ORDER BY price_per_unit ASC
                """
            ).fetchall()
            grouped: Dict[str, List[Medicine]] = {}
            for r in rows:
                grouped.setdefault(r["salt_fingerprint"], []).append(self._row_to_medicine(r))
            self._priority_by_fp = grouped
            return grouped

    def close(self) -> None:
        """Close all thread-local SQLite connections cleanly."""
        with self._conns_lock:
            for conn in self._conns:
                try:
                    conn.close()
                except sqlite3.Error:
                    pass
            self._conns.clear()
        self._local = threading.local()

    @staticmethod
    def _normalize_text(text: str) -> str:
        return _normalize_text(text)

    @staticmethod
    def _prefix_upper_bound(prefix: str) -> str:
        """Return exclusive lexicographic upper bound for fast B-tree prefix range scans."""
        if not prefix:
            return "\uffff"
        return prefix[:-1] + chr(ord(prefix[-1]) + 1)

    @staticmethod
    def _row_to_medicine(row: sqlite3.Row) -> Medicine:
        salts = [
            SaltComponent(
                name=s["name"],
                strength_value=float(s["strength_value"]),
                strength_unit=s.get("strength_unit", "mg"),
            )
            for s in json.loads(row["salts_json"])
        ]
        return Medicine(
            id=row["id"],
            brand_name=row["brand_name"],
            manufacturer=row["manufacturer"],
            salts=salts,
            dosage_form=DosageForm(row["dosage_form"]),
            release_type=ReleaseType(row["release_type"]),
            pack_size=int(row["pack_size"]),
            mrp=float(row["mrp"]),
            price_per_unit=float(row["price_per_unit"]),
            regulatory_tier=RegulatoryTier(row["regulatory_tier"]),
            is_narrow_therapeutic_index=bool(row["is_narrow_therapeutic_index"]),
            therapeutic_category=row["therapeutic_category"],
            is_discontinued=bool(row["is_discontinued"]),
            pack_size_label=row["pack_size_label"],
            source=row["source"],
        )

    def get_by_id(self, med_id: str) -> Optional[Medicine]:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM medicines WHERE id = ?", (med_id,)).fetchone()
        return self._row_to_medicine(row) if row else None

    def get_by_brand_exact(self, brand_name: str) -> Optional[Medicine]:
        cleaned = brand_name.strip().lower()
        if not cleaned:
            return None
        conn = self._get_conn()
        row = conn.execute(
            """
            SELECT * FROM medicines
            WHERE brand_lower = ?
            ORDER BY CASE WHEN source = 'curated' THEN 0 ELSE 1 END,
                     is_discontinued ASC,
                     price_per_unit ASC
            LIMIT 1
            """,
            (cleaned,),
        ).fetchone()
        if row:
            return self._row_to_medicine(row)

        norm = self._normalize_text(brand_name)
        if not norm:
            return None
        row = conn.execute(
            """
            SELECT * FROM medicines
            WHERE brand_norm = ?
            ORDER BY CASE WHEN source = 'curated' THEN 0 ELSE 1 END,
                     is_discontinued ASC,
                     price_per_unit ASC
            LIMIT 1
            """,
            (norm,),
        ).fetchone()
        return self._row_to_medicine(row) if row else None

    def search_by_brand(self, query: str, limit: int = 10) -> List[Medicine]:
        """Search indexed brands (exact, prefix, FTS5 tokens) and canonical salts."""
        q = query.strip().lower()
        if not q or limit <= 0:
            return []

        conn = self._get_conn()
        norm_q = self._normalize_text(query)
        seen_ids: Set[str] = set()
        results: List[Medicine] = []

        def _append_rows(rows: List[sqlite3.Row]) -> None:
            for r in rows:
                mid = r["id"]
                if mid not in seen_ids:
                    seen_ids.add(mid)
                    results.append(self._row_to_medicine(r))
                    if len(results) >= limit:
                        return

        # 1. Exact brand_lower match
        _append_rows(conn.execute(
            """
            SELECT * FROM medicines
            WHERE brand_lower = ?
            ORDER BY CASE WHEN source = 'curated' THEN 0 ELSE 1 END,
                     is_discontinued ASC,
                     price_per_unit ASC
            LIMIT ?
            """,
            (q, limit),
        ).fetchall())
        if len(results) >= limit:
            return results

        # 2. Exact brand_norm match (hyphen/punctuation-insensitive)
        if norm_q:
            _append_rows(conn.execute(
                """
                SELECT * FROM medicines
                WHERE brand_norm = ?
                ORDER BY CASE WHEN source = 'curated' THEN 0 ELSE 1 END,
                         is_discontinued ASC,
                         price_per_unit ASC
                LIMIT ?
                """,
                (norm_q, limit),
            ).fetchall())
            if len(results) >= limit:
                return results

        # 3. Fast B-tree prefix range scans on brand_lower and brand_norm
        upper_q = self._prefix_upper_bound(q)
        _append_rows(conn.execute(
            """
            SELECT * FROM medicines
            WHERE brand_lower >= ? AND brand_lower < ?
            ORDER BY CASE WHEN source = 'curated' THEN 0 ELSE 1 END,
                     is_discontinued ASC,
                     length(brand_name) ASC,
                     brand_lower ASC
            LIMIT ?
            """,
            (q, upper_q, limit * 2),
        ).fetchall())
        if len(results) >= limit:
            return results

        if norm_q:
            upper_norm = self._prefix_upper_bound(norm_q)
            _append_rows(conn.execute(
                """
                SELECT * FROM medicines
                WHERE brand_norm >= ? AND brand_norm < ?
                ORDER BY CASE WHEN source = 'curated' THEN 0 ELSE 1 END,
                         is_discontinued ASC,
                         length(brand_name) ASC,
                         brand_lower ASC
                LIMIT ?
                """,
                (norm_q, upper_norm, limit * 2),
            ).fetchall())
            if len(results) >= limit:
                return results

        # 4. FTS5 token/prefix search across brand_name, brand_norm, salts_text, manufacturer
        tokens = re.findall(r"[a-z0-9]+", norm_q)
        if tokens:
            fts_query = " ".join(f'"{t}"*' for t in tokens)
            try:
                _append_rows(conn.execute(
                    """
                    SELECT m.* FROM medicines m
                    JOIN medicines_fts f ON m.rowid = f.rowid
                    WHERE medicines_fts MATCH ?
                    ORDER BY CASE WHEN m.source = 'curated' THEN 0 ELSE 1 END,
                             m.is_discontinued ASC,
                             length(m.brand_name) ASC
                    LIMIT ?
                    """,
                    (fts_query, limit * 3),
                ).fetchall())
            except sqlite3.OperationalError:
                pass
            if len(results) >= limit:
                return results

        # 5. Canonical salt lookup (e.g. "Acetaminophen" -> Paracetamol brands)
        canonical_salt_q = SafetyEngine.normalize_salt_name(q)
        _append_rows(conn.execute(
            """
            SELECT m.* FROM medicines m
            JOIN medicine_salts ms ON m.id = ms.medicine_id
            WHERE ms.canonical_salt = ?
            ORDER BY CASE WHEN m.source = 'curated' THEN 0 ELSE 1 END,
                     m.is_discontinued ASC,
                     m.brand_lower ASC
            LIMIT ?
            """,
            (canonical_salt_q, limit * 3),
        ).fetchall())
        if len(results) >= limit:
            return results

        if len(norm_q) >= 3:
            upper_salt = self._prefix_upper_bound(norm_q)
            _append_rows(conn.execute(
                """
                SELECT m.* FROM medicines m
                JOIN medicine_salts ms ON m.id = ms.medicine_id
                WHERE ms.canonical_salt >= ? AND ms.canonical_salt < ?
                GROUP BY m.id
                ORDER BY CASE WHEN m.source = 'curated' THEN 0 ELSE 1 END,
                         m.is_discontinued ASC,
                         m.brand_lower ASC
                LIMIT ?
                """,
                (norm_q, upper_salt, limit * 3),
            ).fetchall())

        return results[:limit]

    def get_by_fingerprint(self, fingerprint: str) -> List[Medicine]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM medicines WHERE salt_fingerprint = ?",
            (fingerprint,),
        ).fetchall()
        return [self._row_to_medicine(r) for r in rows]

    def get_candidates_by_salts(self, salts: List[SaltComponent]) -> List[Medicine]:
        if not salts:
            return []
        canonical_salts = sorted({SafetyEngine.normalize_salt_name(s.name) for s in salts})
        placeholders = ",".join("?" for _ in canonical_salts)
        conn = self._get_conn()
        rows = conn.execute(
            f"""
            SELECT m.* FROM medicines m
            WHERE m.id IN (
                SELECT medicine_id FROM medicine_salts
                WHERE canonical_salt IN ({placeholders})
                GROUP BY medicine_id
                HAVING COUNT(DISTINCT canonical_salt) = ?
            )
            """,
            (*canonical_salts, len(canonical_salts)),
        ).fetchall()
        return [self._row_to_medicine(r) for r in rows]

    def get_substitute_candidates(
        self,
        original: Medicine,
        max_candidates: int = 30,
    ) -> List[Medicine]:
        """Pre-filter active, cheaper candidates via single-equality composite SQLite B-tree indexes.

        Issues single-fingerprint equality queries so SQLite reads directly in
        `price_per_unit ASC` index order with zero temp B-tree sorting.
        """
        fp = original.salt_fingerprint()
        fingerprints = [fp]
        if original.dosage_form == DosageForm.TABLET:
            fingerprints.append(
                fp.replace(f"#{DosageForm.TABLET.value}#", f"#{DosageForm.CAPSULE.value}#", 1)
            )
        elif original.dosage_form == DosageForm.CAPSULE:
            fingerprints.append(
                fp.replace(f"#{DosageForm.CAPSULE.value}#", f"#{DosageForm.TABLET.value}#", 1)
            )

        conn = self._get_conn()
        priority_map = self._get_priority_by_fp()
        seen_ids: Set[str] = set()
        candidates: List[Medicine] = []

        # 1. Instant O(1) priority-tier candidates (PMBJP, WHO-GMP, CDSCO) across matching fingerprints
        for target_fp in fingerprints:
            for med in priority_map.get(target_fp, ()):
                if med.id != original.id and med.price_per_unit <= original.price_per_unit and med.id not in seen_ids:
                    seen_ids.add(med.id)
                    candidates.append(med)
                    if len(candidates) >= max_candidates:
                        return candidates

        # 2. Single primary-fingerprint equality query via idx_medicines_sub_lookup (zero temp B-tree sort)
        for target_fp in fingerprints:
            remaining = max_candidates - len(candidates)
            if remaining <= 0:
                break
            rows = conn.execute(
                """
                SELECT * FROM medicines
                WHERE salt_fingerprint = ?
                  AND is_discontinued = 0
                  AND price_per_unit <= ?
                  AND id != ?
                ORDER BY price_per_unit ASC
                LIMIT ?
                """,
                (target_fp, original.price_per_unit, original.id, max_candidates),
            ).fetchall()
            for r in rows:
                mid = r["id"]
                if mid not in seen_ids:
                    seen_ids.add(mid)
                    candidates.append(self._row_to_medicine(r))
                    if len(candidates) >= max_candidates:
                        break

        return candidates[:max_candidates]

    def get_stratified_sample(self, sample_size: int = 2000, seed: int = 42) -> List[Medicine]:
        """Return all curated records plus a deterministic seeded sample of A-Z rows."""
        conn = self._get_conn()
        curated_rows = conn.execute(
            "SELECT * FROM medicines WHERE source = 'curated' ORDER BY id"
        ).fetchall()
        sample = [self._row_to_medicine(r) for r in curated_rows]

        if sample_size <= 0:
            return sample

        az_id_rows = conn.execute(
            "SELECT id FROM medicines WHERE source != 'curated' ORDER BY id"
        ).fetchall()
        az_ids = [r["id"] for r in az_id_rows]
        if not az_ids:
            return sample

        chosen_count = min(sample_size, len(az_ids))
        chosen_ids = random.Random(seed).sample(az_ids, chosen_count)

        chunk_size = 500
        for i in range(0, len(chosen_ids), chunk_size):
            chunk = chosen_ids[i : i + chunk_size]
            placeholders = ",".join("?" for _ in chunk)
            rows = conn.execute(
                f"SELECT * FROM medicines WHERE id IN ({placeholders})",
                chunk,
            ).fetchall()
            for r in rows:
                sample.append(self._row_to_medicine(r))

        return sample

    def all_medicines(self) -> List[Medicine]:
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM medicines").fetchall()
        return [self._row_to_medicine(r) for r in rows]

    def count(self) -> int:
        conn = self._get_conn()
        row = conn.execute("SELECT COUNT(*) AS cnt FROM medicines").fetchone()
        return int(row["cnt"]) if row else 0


RepositoryType = Union[MedicineRepository, SQLiteMedicineRepository]


def load_default_repository(
    db_path: Optional[str | Path] = None,
    json_path: Optional[str | Path] = None,
    curated_only: bool = False,
) -> RepositoryType:
    """Load the compiled SQLite+FTS5 catalog if present, falling back to curated JSON."""
    root = Path(__file__).resolve().parent.parent

    if not curated_only:
        if db_path is not None:
            resolved_db = Path(db_path)
        elif os.environ.get("EQUIMED_DB_PATH"):
            resolved_db = Path(os.environ["EQUIMED_DB_PATH"])
        else:
            resolved_db = root / "data" / "equimed_catalog.db"

        if resolved_db.exists():
            return SQLiteMedicineRepository(resolved_db)

    resolved_json = Path(json_path) if json_path is not None else (root / "data" / "medicine_catalog.json")
    repo = MedicineRepository()
    repo.load_from_json(resolved_json)
    return repo
