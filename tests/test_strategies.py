"""Unit tests for Strategy Pattern implementations."""

import unittest
from src.models import (
    DosageForm,
    Medicine,
    RegulatoryTier,
    ReleaseType,
    SafetyVerdict,
    SaltComponent,
    SubstitutionMatch,
)
from src.strategy import (
    JanAushadhiFirstStrategy,
    MaxSavingsStrategy,
    ReputationBalancedStrategy,
    get_strategy,
)


class TestStrategies(unittest.TestCase):
    def setUp(self):
        s_tel = SaltComponent("Telmisartan", 40.0, "mg")
        self.orig = Medicine(
            id="ORIG", brand_name="Telma 40", manufacturer="Glenmark",
            salts=[s_tel], dosage_form=DosageForm.TABLET,
            release_type=ReleaseType.IMMEDIATE_RELEASE, pack_size=15,
            mrp=150.0, price_per_unit=10.0, regulatory_tier=RegulatoryTier.BRANDED_INNOVATOR
        )

        # Substitute 1: Jan Aushadhi (85% savings)
        self.sub_pmbjp = Medicine(
            id="SUB-1", brand_name="Telmisartan Jan Aushadhi", manufacturer="PMBJP",
            salts=[s_tel], dosage_form=DosageForm.TABLET,
            release_type=ReleaseType.IMMEDIATE_RELEASE, pack_size=10,
            mrp=15.0, price_per_unit=1.50, regulatory_tier=RegulatoryTier.PMBJP_JAN_AUSHADHI
        )
        self.match_pmbjp = SubstitutionMatch(
            original_medicine=self.orig,
            substitute_medicine=self.sub_pmbjp,
            price_original_unit=10.0,
            price_substitute_unit=1.50,
            savings_per_unit=8.50,
            percentage_savings=85.0,
            safety_verdict=SafetyVerdict(is_safe=True, is_exact_bioequivalent=True),
        )

        # Substitute 2: WHO-GMP Generic (90% savings, lower price than Jan Aushadhi)
        self.sub_who = Medicine(
            id="SUB-2", brand_name="SuperCheap WHO Generic", manufacturer="Pharma Ltd",
            salts=[s_tel], dosage_form=DosageForm.TABLET,
            release_type=ReleaseType.IMMEDIATE_RELEASE, pack_size=10,
            mrp=10.0, price_per_unit=1.00, regulatory_tier=RegulatoryTier.WHO_GMP_GENERIC
        )
        self.match_who = SubstitutionMatch(
            original_medicine=self.orig,
            substitute_medicine=self.sub_who,
            price_original_unit=10.0,
            price_substitute_unit=1.00,
            savings_per_unit=9.00,
            percentage_savings=90.0,
            safety_verdict=SafetyVerdict(is_safe=True, is_exact_bioequivalent=True),
        )

        # Substitute 3: Branded Generic (40% savings)
        self.sub_brand_gen = Medicine(
            id="SUB-3", brand_name="Moderate Brand Generic", manufacturer="Local Ltd",
            salts=[s_tel], dosage_form=DosageForm.TABLET,
            release_type=ReleaseType.IMMEDIATE_RELEASE, pack_size=10,
            mrp=60.0, price_per_unit=6.00, regulatory_tier=RegulatoryTier.BRANDED_GENERIC
        )
        self.match_brand_gen = SubstitutionMatch(
            original_medicine=self.orig,
            substitute_medicine=self.sub_brand_gen,
            price_original_unit=10.0,
            price_substitute_unit=6.00,
            savings_per_unit=4.00,
            percentage_savings=40.0,
            safety_verdict=SafetyVerdict(is_safe=True, is_exact_bioequivalent=True),
        )

    def test_max_savings_strategy(self):
        strategy = MaxSavingsStrategy()
        ranked = strategy.rank([self.match_pmbjp, self.match_who, self.match_brand_gen])
        # 90% savings should be #1, 85% #2, 40% #3
        self.assertEqual(ranked[0].substitute_medicine.id, "SUB-2")
        self.assertEqual(ranked[1].substitute_medicine.id, "SUB-1")
        self.assertEqual(ranked[2].substitute_medicine.id, "SUB-3")

    def test_jan_aushadhi_first_strategy(self):
        strategy = JanAushadhiFirstStrategy()
        ranked = strategy.rank([self.match_who, self.match_pmbjp, self.match_brand_gen])
        # PMBJP must be #1 due to government subsidy priority bonus
        self.assertEqual(ranked[0].substitute_medicine.id, "SUB-1")
        self.assertEqual(ranked[0].substitute_medicine.regulatory_tier, RegulatoryTier.PMBJP_JAN_AUSHADHI)

    def test_reputation_balanced_strategy(self):
        strategy = ReputationBalancedStrategy()
        ranked = strategy.rank([self.match_brand_gen, self.match_pmbjp, self.match_who])
        # Both PMBJP (85% + 100 tier) and WHO (90% + 95 tier) must beat branded generic (40% + 70 tier)
        self.assertEqual(ranked[2].substitute_medicine.id, "SUB-3")
        self.assertIn(ranked[0].substitute_medicine.id, ("SUB-1", "SUB-2"))

    def test_get_strategy_factory(self):
        self.assertIsInstance(get_strategy("max_savings"), MaxSavingsStrategy)
        self.assertIsInstance(get_strategy("jan_aushadhi"), JanAushadhiFirstStrategy)
        self.assertIsInstance(get_strategy("balanced"), ReputationBalancedStrategy)
        self.assertIsInstance(get_strategy("unknown_default"), MaxSavingsStrategy)


if __name__ == "__main__":
    unittest.main()
