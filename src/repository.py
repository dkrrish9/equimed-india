"""Data Repository with Inverted In-Memory Indexes for O(1) Drug Lookup."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Set

from src.models import Medicine, SaltComponent
from src.safety_engine import SafetyEngine


class MedicineRepository:
    """Repository managing medicine data with multi-dimensional indexed lookups.

    Maintains:
    - ID Index: O(1) by primary ID.
    - Brand Name Index: O(1) normalized brand lookup.
    - Chemical Salt Fingerprint Index: O(1) lookup of all identical salt combinations.
    - Inverted Salt Component Index: Fast lookup by constituent salt active ingredients.
    """

    def __init__(self) -> None:
        self._by_id: Dict[str, Medicine] = {}
        self._by_brand_lower: Dict[str, Medicine] = {}
        self._by_fingerprint: Dict[str, List[Medicine]] = {}
        self._by_salt: Dict[str, Set[str]] = {}  # salt_name -> set of medicine IDs

    def add(self, medicine: Medicine) -> None:
        """Add medicine to all repository indexes."""
        self._by_id[medicine.id] = medicine
        brand_clean = medicine.brand_name.strip().lower()
        self._by_brand_lower[brand_clean] = medicine

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
        return self._by_brand_lower.get(brand_name.strip().lower())

    def search_by_brand(self, query: str, limit: int = 10) -> List[Medicine]:
        """Search by prefix or substring with exact matches prioritized."""
        q = query.strip().lower()
        if not q:
            return []

        exact_matches: List[Medicine] = []
        prefix_matches: List[Medicine] = []
        contains_matches: List[Medicine] = []

        for name, med in self._by_brand_lower.items():
            if name == q:
                exact_matches.append(med)
            elif name.startswith(q):
                prefix_matches.append(med)
            elif q in name:
                contains_matches.append(med)

        results = exact_matches + prefix_matches + contains_matches
        return results[:limit]

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
