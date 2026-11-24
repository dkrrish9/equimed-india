"""Strategy Pattern implementation for substitution ranking.

Supports multiple clinical and economic prioritization algorithms:
1. MaxSavingsStrategy: Highest percentage savings first.
2. JanAushadhiFirstStrategy: Pradhan Mantri Bhartiya Janaushadhi Pariyojana generics first.
3. ReputationBalancedStrategy: Multi-criteria decision ranking (Savings + Quality & Manufacturer Reputation).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from src.models import RegulatoryTier, SubstitutionMatch

MAJOR_PHARMA_KEYWORDS = (
    "sun pharmaceutical",
    "sun pharma",
    "cipla",
    "dr reddy",
    "dr. reddy",
    "lupin",
    "alkem",
    "torrent",
    "zydus",
    "cadila",
    "glenmark",
    "mankind",
    "abbott",
    "glaxosmithkline",
    "gsk",
    "pfizer",
    "sanofi",
    "intas",
    "macleods",
    "aristo",
    "micro labs",
    "usv",
    "alembic",
    "ipca",
    "biocon",
    "hetero",
    "natco",
    "wockhardt",
    "emcure",
    "ajanta",
    "novartis",
    "astrazeneca",
    "bayer",
    "merck",
    "eris",
)


def is_major_pharma(manufacturer: str) -> bool:
    """Return True if manufacturer matches an established CDSCO/WHO-GMP-audited pharma house."""
    low = (manufacturer or "").strip().lower()
    if not low:
        return False
    return any(kw in low for kw in MAJOR_PHARMA_KEYWORDS)


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
    """Prioritizes Government of India PMBJP (Jan Aushadhi) and certified generics first."""

    @property
    def name(self) -> str:
        return "Jan Aushadhi (PMBJP) Priority"

    def rank(self, matches: List[SubstitutionMatch]) -> List[SubstitutionMatch]:
        for match in matches:
            score = match.percentage_savings
            tier = match.substitute_medicine.regulatory_tier
            if tier == RegulatoryTier.PMBJP_JAN_AUSHADHI:
                score += 200.0
            elif tier == RegulatoryTier.WHO_GMP_GENERIC:
                score += 100.0
            elif tier == RegulatoryTier.CDSCO_APPROVED_GENERIC:
                score += 50.0

            match.ranking_score = score

        return sorted(matches, key=lambda m: m.ranking_score, reverse=True)


class ReputationBalancedStrategy(SubstitutionStrategy):
    """Balanced MAUT combining 40% price savings with 60% quality tier & manufacturer reputation."""

    TIER_SCORES = {
        RegulatoryTier.PMBJP_JAN_AUSHADHI: 100.0,
        RegulatoryTier.WHO_GMP_GENERIC: 96.0,
        RegulatoryTier.CDSCO_APPROVED_GENERIC: 85.0,
        RegulatoryTier.BRANDED_GENERIC: 45.0,
        RegulatoryTier.BRANDED_INNOVATOR: 50.0,
    }
    MAJOR_PHARMA_QUALITY_SCORE = 82.0

    @property
    def name(self) -> str:
        return "Balanced (Savings + Quality Certifications)"

    def rank(self, matches: List[SubstitutionMatch]) -> List[SubstitutionMatch]:
        for match in matches:
            med = match.substitute_medicine
            tier = med.regulatory_tier
            quality_score = self.TIER_SCORES.get(tier, 45.0)
            if tier == RegulatoryTier.BRANDED_GENERIC and is_major_pharma(med.manufacturer):
                quality_score = self.MAJOR_PHARMA_QUALITY_SCORE

            # 40% weight on price savings, 60% weight on regulatory tier + manufacturer reputation
            composite_score = (0.40 * match.percentage_savings) + (0.60 * quality_score)
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
