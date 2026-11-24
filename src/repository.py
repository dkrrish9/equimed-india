"""Data Repository with Inverted In-Memory Indexes for O(1) Drug Lookup."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set

from src.models import Medicine, SaltComponent
from src.safety_engine import SafetyEngine


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

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Lowercase and collapse hyphens/punctuation to single spaces."""
        cleaned = re.sub(r"[-_/.,()+]+", " ", text.strip().lower())
        return re.sub(r"\s+", " ", cleaned).strip()

    def add(self, medicine: Medicine) -> None:
        """Add medicine to all repository indexes."""
        self._by_id[medicine.id] = medicine
        brand_clean = medicine.brand_name.strip().lower()
        # Keep deterministic first-or-cheapest primary brand without silently erasing collisions
        if brand_clean not in self._by_brand_lower:
            self._by_brand_lower[brand_clean] = medicine
        self._by_brand_all.setdefault(brand_clean, [])
        if medicine not in self._by_brand_all[brand_clean]:
            self._by_brand_all[brand_clean].append(medicine)

        brand_norm = self._normalize_text(medicine.brand_name)
        self._by_brand_norm.setdefault(brand_norm, [])
        if medicine not in self._by_brand_norm[brand_norm]:
            self._by_brand_norm[brand_norm].append(medicine)

        fp = medicine.salt_fingerprint()
        if fp not in self._by_fingerprint:
            self._by_fingerprint[fp] = []
        if medicine not in self._by_fingerprint[fp]:
            self._by_fingerprint[fp].append(medicine)

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
            for med in meds:
                norm_name = self._normalize_text(name)
                if name == q:
                    exact_matches.append(med)
                elif norm_q and norm_name == norm_q:
                    norm_exact_matches.append(med)
                elif name.startswith(q) or (norm_q and norm_name.startswith(norm_q)):
                    prefix_matches.append(med)
                elif q in name:
                    contains_matches.append(med)
                elif q_tokens and all(tok in norm_name for tok in q_tokens):
                    token_matches.append(med)

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

        # Prioritize branded originators slightly lower/higher? Keep stable deterministic ordering
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
