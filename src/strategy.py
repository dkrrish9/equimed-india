"""Strategy Pattern implementation for substitution ranking.

Supports multiple clinical and economic prioritization algorithms:
1. MaxSavingsStrategy: Highest percentage savings first.
2. JanAushadhiFirstStrategy: Pradhan Mantri Bhartiya Janaushadhi Pariyojana generics first.
3. ReputationBalancedStrategy: Multi-criteria decision ranking (Savings + Regulatory GMP Certification).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from src.models import RegulatoryTier, SubstitutionMatch


class SubstitutionStrategy(ABC):
    """Abstract Strategy defining the contract for sorting generic candidates."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable strategy identifier."""
        pass

    @abstractmethod
    def rank(self, matches: List[SubstitutionMatch]) -> List[SubstitutionMatch]:
        """Rank and score candidate substitutions in-place or return ordered list."""
        pass


class MaxSavingsStrategy(SubstitutionStrategy):
    """Prioritizes maximizing direct out-of-pocket financial savings for the patient."""

    @property
    def name(self) -> str:
        return "Maximum Cost Savings"

    def rank(self, matches: List[SubstitutionMatch]) -> List[SubstitutionMatch]:
        for match in matches:
            # Score primarily on percentage savings + slight tie-breaker on absolute savings
            match.ranking_score = match.percentage_savings + (match.savings_per_unit * 0.01)

        return sorted(matches, key=lambda m: m.ranking_score, reverse=True)


class JanAushadhiFirstStrategy(SubstitutionStrategy):
    """Prioritizes Government of India PMBJP (Jan Aushadhi) outlets for maximum reliability and public subsidy."""

    @property
    def name(self) -> str:
        return "Jan Aushadhi (PMBJP) Priority"

    def rank(self, matches: List[SubstitutionMatch]) -> List[SubstitutionMatch]:
        for match in matches:
            score = match.percentage_savings
            if match.substitute_medicine.regulatory_tier == RegulatoryTier.PMBJP_JAN_AUSHADHI:
                score += 200.0  # Dominant priority bonus for Jan Aushadhi
            elif match.substitute_medicine.regulatory_tier == RegulatoryTier.WHO_GMP_GENERIC:
                score += 50.0

            match.ranking_score = score

        return sorted(matches, key=lambda m: m.ranking_score, reverse=True)


class ReputationBalancedStrategy(SubstitutionStrategy):
    """Balanced multi-attribute utility theory (MAUT) balancing economic savings with manufacturing certifications."""

    # Regulatory tier weight map
    TIER_SCORES = {
        RegulatoryTier.PMBJP_JAN_AUSHADHI: 100.0,
        RegulatoryTier.WHO_GMP_GENERIC: 95.0,
        RegulatoryTier.CDSCO_APPROVED_GENERIC: 80.0,
        RegulatoryTier.BRANDED_GENERIC: 70.0,
        RegulatoryTier.BRANDED_INNOVATOR: 50.0,
    }

    @property
    def name(self) -> str:
        return "Balanced (Savings + Quality Certifications)"

    def rank(self, matches: List[SubstitutionMatch]) -> List[SubstitutionMatch]:
        for match in matches:
            tier = match.substitute_medicine.regulatory_tier
            tier_score = self.TIER_SCORES.get(tier, 60.0)

            # 65% weight on price savings, 35% weight on regulatory tier
            composite_score = (0.65 * match.percentage_savings) + (0.35 * tier_score)
            match.ranking_score = composite_score

        return sorted(matches, key=lambda m: m.ranking_score, reverse=True)


def get_strategy(strategy_name: str) -> SubstitutionStrategy:
    """Factory method for instantiating substitution strategies."""
    normalized = strategy_name.strip().lower().replace("-", "_")
    if "jan" in normalized or "aushadh" in normalized or "pmbjp" in normalized:
        return JanAushadhiFirstStrategy()
    if "balance" in normalized or "reput" in normalized or "quality" in normalized:
        return ReputationBalancedStrategy()
    return MaxSavingsStrategy()
