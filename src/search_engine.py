"""Core Search and Generic Drug Substitution Engine."""

from __future__ import annotations

from typing import List, Optional

from src.models import Medicine, SubstitutionMatch
from src.observer import ObservableSubject
from src.repository import MedicineRepository
from src.safety_engine import SafetyEngine
from src.strategy import MaxSavingsStrategy, SubstitutionStrategy


class SearchEngine(ObservableSubject):
    """Facade orchestrating drug lookup, safety validation, and economic strategy ranking."""

    def __init__(
        self,
        repository: MedicineRepository,
        safety_engine: Optional[SafetyEngine] = None,
        default_strategy: Optional[SubstitutionStrategy] = None,
    ) -> None:
        super().__init__()
        self.repository = repository
        self.safety_engine = safety_engine or SafetyEngine()
        self.default_strategy = default_strategy or MaxSavingsStrategy()

    def find_substitutes(
        self,
        query_or_medicine: str | Medicine,
        strategy: Optional[SubstitutionStrategy] = None,
        min_savings_percentage: float = 0.0,
        limit: int = 10,
    ) -> List[SubstitutionMatch]:
        """Find clinically bioequivalent and cheaper generic substitutes for a given medicine.

        Args:
            query_or_medicine: Brand name string or Medicine instance.
            strategy: Ranking strategy (defaults to MaxSavingsStrategy).
            min_savings_percentage: Filter to exclude substitutes below threshold savings.
            limit: Maximum matches to return.

        Returns:
            Ranked list of verified SubstitutionMatch objects.
        """
        active_strategy = strategy or self.default_strategy

        # 1. Resolve original medicine
        original: Optional[Medicine] = None
        if isinstance(query_or_medicine, Medicine):
            original = query_or_medicine
        else:
            original = self.repository.get_by_brand_exact(query_or_medicine)
            if not original:
                # Try prefix/substring search
                matches = self.repository.search_by_brand(query_or_medicine, limit=1)
                if matches:
                    original = matches[0]

        if not original:
            return []

        # 2. Retrieve potential candidates from repository (O(1) fingerprint + active salt index)
        fingerprint = original.salt_fingerprint()
        raw_candidates = self.repository.get_by_fingerprint(fingerprint)

        # Also search by constituent salts to catch formulation variations (e.g. tablet vs capsule)
        salt_candidates = self.repository.get_candidates_by_salts(original.salts)
        candidate_pool = {m.id: m for m in (raw_candidates + salt_candidates)}

        # 3. Clinical Validation & Economic Evaluation
        valid_matches: List[SubstitutionMatch] = []

        for candidate in candidate_pool.values():
            if candidate.id == original.id:
                continue

            verdict = self.safety_engine.validate_substitution(original, candidate)

            if not verdict.is_safe:
                self.notify("SUBSTITUTION_REJECTED", {
                    "original": original.brand_name,
                    "candidate": candidate.brand_name,
                    "reason": verdict.rejection_reason,
                })
                continue

            # Calculate savings
            savings_unit = original.price_per_unit - candidate.price_per_unit
            pct_savings = (savings_unit / original.price_per_unit) * 100.0 if original.price_per_unit > 0 else 0.0

            if pct_savings < min_savings_percentage:
                continue

            match = SubstitutionMatch(
                original_medicine=original,
                substitute_medicine=candidate,
                price_original_unit=original.price_per_unit,
                price_substitute_unit=candidate.price_per_unit,
                savings_per_unit=savings_unit,
                percentage_savings=pct_savings,
                safety_verdict=verdict,
            )
            valid_matches.append(match)

            self.notify("SUBSTITUTION_FOUND", {
                "original": original.brand_name,
                "substitute": candidate.brand_name,
                "savings_per_unit": savings_unit,
                "percentage_savings": pct_savings,
            })

            if verdict.warnings:
                self.notify("SAFETY_WARNING", {
                    "medicine": original.brand_name,
                    "candidate": candidate.brand_name,
                    "warnings": verdict.warnings,
                })

        # 4. Apply Strategy Pattern for scoring and ranking
        ranked_matches = active_strategy.rank(valid_matches)
        return ranked_matches[:limit]
