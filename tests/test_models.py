"""Unit tests for EquiMed domain models."""

import unittest
from src.models import (
    DosageForm,
    Medicine,
    PrescriptionBasket,
    PrescriptionItem,
    RegulatoryTier,
    ReleaseType,
    SafetyVerdict,
    SaltComponent,
    SubstitutionMatch,
)


class TestModels(unittest.TestCase):
    def setUp(self):
        self.salt1 = SaltComponent(name="Amoxicillin", strength_value=500.0, strength_unit="mg")
        self.salt2 = SaltComponent(name="Clavulanic Acid", strength_value=125.0, strength_unit="mg")

    def test_salt_component_normalized_key(self):
        key = self.salt1.normalized_key()
        self.assertEqual(key, "amoxicillin:500.0:mg")

    def test_salt_serialization_roundtrip(self):
        d = self.salt1.to_dict()
        reconstructed = SaltComponent.from_dict(d)
        self.assertEqual(self.salt1, reconstructed)

    def test_medicine_salt_fingerprint_invariance(self):
        # Glimepiride + Metformin vs Metformin + Glimepiride must have identical fingerprint
        s_met = SaltComponent("Metformin", 500.0, "mg")
        s_glim = SaltComponent("Glimepiride", 2.0, "mg")

        med_order1 = Medicine(
            id="M1", brand_name="Brand A", manufacturer="Mfg 1",
            salts=[s_met, s_glim], dosage_form=DosageForm.TABLET,
            release_type=ReleaseType.SUSTAINED_RELEASE, pack_size=10,
            mrp=100.0, price_per_unit=10.0, regulatory_tier=RegulatoryTier.BRANDED_INNOVATOR
        )
        med_order2 = Medicine(
            id="M2", brand_name="Brand B", manufacturer="Mfg 2",
            salts=[s_glim, s_met], dosage_form=DosageForm.TABLET,
            release_type=ReleaseType.SUSTAINED_RELEASE, pack_size=10,
            mrp=30.0, price_per_unit=3.0, regulatory_tier=RegulatoryTier.PMBJP_JAN_AUSHADHI
        )

        self.assertEqual(med_order1.salt_fingerprint(), med_order2.salt_fingerprint())

    def test_medicine_fingerprint_differs_by_form_or_release(self):
        s_met = SaltComponent("Metformin", 500.0, "mg")
        med_ir = Medicine(
            id="M1", brand_name="Brand A", manufacturer="Mfg 1",
            salts=[s_met], dosage_form=DosageForm.TABLET,
            release_type=ReleaseType.IMMEDIATE_RELEASE, pack_size=10,
            mrp=50.0, price_per_unit=5.0, regulatory_tier=RegulatoryTier.BRANDED_INNOVATOR
        )
        med_sr = Medicine(
            id="M2", brand_name="Brand B", manufacturer="Mfg 2",
            salts=[s_met], dosage_form=DosageForm.TABLET,
            release_type=ReleaseType.SUSTAINED_RELEASE, pack_size=10,
            mrp=50.0, price_per_unit=5.0, regulatory_tier=RegulatoryTier.BRANDED_INNOVATOR
        )
        med_syrup = Medicine(
            id="M3", brand_name="Brand C", manufacturer="Mfg 3",
            salts=[s_met], dosage_form=DosageForm.SYRUP,
            release_type=ReleaseType.IMMEDIATE_RELEASE, pack_size=10,
            mrp=50.0, price_per_unit=5.0, regulatory_tier=RegulatoryTier.BRANDED_INNOVATOR
        )

        self.assertNotEqual(med_ir.salt_fingerprint(), med_sr.salt_fingerprint())
        self.assertNotEqual(med_ir.salt_fingerprint(), med_syrup.salt_fingerprint())

    def test_medicine_serialization_roundtrip(self):
        med = Medicine(
            id="MED-TEST", brand_name="Test Brand", manufacturer="Test Mfg",
            salts=[self.salt1, self.salt2], dosage_form=DosageForm.TABLET,
            release_type=ReleaseType.IMMEDIATE_RELEASE, pack_size=10,
            mrp=200.0, price_per_unit=20.0, regulatory_tier=RegulatoryTier.BRANDED_INNOVATOR,
            is_narrow_therapeutic_index=False, therapeutic_category="Antibiotic"
        )
        d = med.to_dict()
        reconstructed = Medicine.from_dict(d)
        self.assertEqual(med.id, reconstructed.id)
        self.assertEqual(med.brand_name, reconstructed.brand_name)
        self.assertEqual(len(med.salts), len(reconstructed.salts))
        self.assertEqual(med.dosage_form, reconstructed.dosage_form)
        self.assertEqual(med.regulatory_tier, reconstructed.regulatory_tier)

    def test_prescription_item_cost_calculation(self):
        med = Medicine(
            id="M1", brand_name="Brand", manufacturer="Mfg",
            salts=[self.salt1], dosage_form=DosageForm.TABLET,
            release_type=ReleaseType.IMMEDIATE_RELEASE, pack_size=10,
            mrp=100.0, price_per_unit=10.0, regulatory_tier=RegulatoryTier.BRANDED_INNOVATOR
        )
        item = PrescriptionItem(medicine=med, units_per_day=2, duration_days=30)
        self.assertEqual(item.total_units, 60)
        self.assertEqual(item.total_cost, 600.0)

    def test_prescription_basket_total_cost(self):
        med1 = Medicine(
            id="M1", brand_name="Brand 1", manufacturer="Mfg 1",
            salts=[self.salt1], dosage_form=DosageForm.TABLET,
            release_type=ReleaseType.IMMEDIATE_RELEASE, pack_size=10,
            mrp=100.0, price_per_unit=10.0, regulatory_tier=RegulatoryTier.BRANDED_INNOVATOR
        )
        med2 = Medicine(
            id="M2", brand_name="Brand 2", manufacturer="Mfg 2",
            salts=[self.salt2], dosage_form=DosageForm.TABLET,
            release_type=ReleaseType.IMMEDIATE_RELEASE, pack_size=10,
            mrp=50.0, price_per_unit=5.0, regulatory_tier=RegulatoryTier.BRANDED_INNOVATOR
        )
        basket = PrescriptionBasket(
            basket_id="B-TEST",
            patient_profile="Test Profile",
            items=[
                PrescriptionItem(medicine=med1, units_per_day=1, duration_days=30),  # 30 * 10 = 300
                PrescriptionItem(medicine=med2, units_per_day=2, duration_days=30),  # 60 * 5 = 300
            ]
        )
        self.assertEqual(basket.total_cost, 600.0)


if __name__ == "__main__":
    unittest.main()
