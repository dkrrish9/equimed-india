"""Unit tests for PrescriptionOptimizer and chronic disease basket processing."""

import unittest
from pathlib import Path
from src.models import (
    DosageForm,
    Medicine,
    PrescriptionItem,
    RegulatoryTier,
    ReleaseType,
    SaltComponent,
)
from src.optimizer import PrescriptionOptimizer
from src.repository import MedicineRepository
from src.search_engine import SearchEngine


class TestOptimizer(unittest.TestCase):
    def setUp(self):
        self.repo = MedicineRepository()
        catalog_path = Path(__file__).resolve().parent.parent / "data" / "medicine_catalog.json"
        self.baskets_path = Path(__file__).resolve().parent.parent / "data" / "chronic_baskets.json"
        self.repo.load_from_json(catalog_path)
        self.engine = SearchEngine(self.repo)
        self.optimizer = PrescriptionOptimizer(self.engine)

    def test_optimize_elderly_diabetic_basket(self):
        # Diabetic basket: Glycomet-GP 2 + Telma 40 + Pan-D + Atorva 10
        baskets = PrescriptionOptimizer.load_chronic_baskets(self.baskets_path, self.repo)
        diabetic_basket = baskets[0]

        result = self.optimizer.optimize_basket(
            basket_id=diabetic_basket["basket_id"],
            patient_profile=diabetic_basket["patient_profile"],
            items=diabetic_basket["items"],
        )

        self.assertEqual(len(result.items), 4)
        self.assertGreater(result.original_total_cost, result.optimized_total_cost)
        self.assertGreater(result.monthly_savings_percentage, 75.0)
        self.assertEqual(
            result.annual_projected_savings,
            round(result.monthly_savings_amount * 12.0, 2)
        )

    def test_basket_with_unmatched_medicine_fallback(self):
        # Create a rare medicine with no generic substitute in catalog
        rare_med = Medicine(
            id="RARE-01",
            brand_name="NovelPatentedRareDrug 50mg",
            manufacturer="Innovator Pharma",
            salts=[SaltComponent("NovelMoleculeX", 50.0, "mg")],
            dosage_form=DosageForm.TABLET,
            release_type=ReleaseType.IMMEDIATE_RELEASE,
            pack_size=10,
            mrp=500.0,
            price_per_unit=50.0,
            regulatory_tier=RegulatoryTier.BRANDED_INNOVATOR,
        )
        self.repo.add(rare_med)

        telma = self.repo.get_by_brand_exact("Telma 40")
        items = [
            PrescriptionItem(medicine=telma, units_per_day=1, duration_days=30),
            PrescriptionItem(medicine=rare_med, units_per_day=1, duration_days=30),
        ]

        result = self.optimizer.optimize_basket(
            basket_id="BASKET-FALLBACK",
            patient_profile="Fallback Test Patient",
            items=items,
        )

        self.assertEqual(len(result.items), 2)
        # Telma item was substituted
        self.assertIsNotNone(result.items[0].best_substitute)
        self.assertGreater(result.items[0].savings_amount, 0.0)

        # Rare item was NOT substituted, kept original cost safely
        self.assertIsNone(result.items[1].best_substitute)
        self.assertEqual(result.items[1].savings_amount, 0.0)
        self.assertEqual(result.items[1].original_cost, result.items[1].optimized_cost)

    def test_all_predefined_baskets_produce_substantial_savings(self):
        baskets = PrescriptionOptimizer.load_chronic_baskets(self.baskets_path, self.repo)
        for b in baskets:
            res = self.optimizer.optimize_basket(
                basket_id=b["basket_id"],
                patient_profile=b["patient_profile"],
                items=b["items"],
            )
            # All clinical chronic disease packages in India must yield > 65% generic savings
            self.assertGreater(res.monthly_savings_percentage, 65.0)


if __name__ == "__main__":
    unittest.main()
