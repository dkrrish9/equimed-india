"""Unit tests for the Clinical Bioequivalence & Safety Validation Engine."""

import unittest
from src.models import (
    DosageForm,
    Medicine,
    RegulatoryTier,
    ReleaseType,
    SaltComponent,
)
from src.safety_engine import SafetyEngine


class TestSafetyEngine(unittest.TestCase):
    def setUp(self):
        self.engine = SafetyEngine()

        # Base Reference Medicine: Augmentin 625 Duo
        self.augmentin = Medicine(
            id="MED-001",
            brand_name="Augmentin 625 Duo",
            manufacturer="GlaxoSmithKline",
            salts=[
                SaltComponent("Amoxicillin", 500.0, "mg"),
                SaltComponent("Clavulanic Acid", 125.0, "mg"),
            ],
            dosage_form=DosageForm.TABLET,
            release_type=ReleaseType.IMMEDIATE_RELEASE,
            pack_size=10,
            mrp=204.50,
            price_per_unit=20.45,
            regulatory_tier=RegulatoryTier.BRANDED_INNOVATOR,
        )

        # Valid Generic Substitute: Amoxyclav 625 (Jan Aushadhi)
        self.amoxyclav_generic = Medicine(
            id="MED-002",
            brand_name="Amoxyclav 625 (Jan Aushadhi)",
            manufacturer="PMBJP",
            salts=[
                SaltComponent("Amoxicillin Trihydrate", 500.0, "mg"),
                SaltComponent("Potassium Clavulanate", 125.0, "mg"),
            ],
            dosage_form=DosageForm.TABLET,
            release_type=ReleaseType.IMMEDIATE_RELEASE,
            pack_size=10,
            mrp=54.00,
            price_per_unit=5.40,
            regulatory_tier=RegulatoryTier.PMBJP_JAN_AUSHADHI,
        )

    def test_salt_synonym_normalization(self):
        self.assertEqual(SafetyEngine.normalize_salt_name("Metformin Hydrochloride"), "metformin")
        self.assertEqual(SafetyEngine.normalize_salt_name("Amoxicillin Trihydrate"), "amoxicillin")
        self.assertEqual(SafetyEngine.normalize_salt_name("Potassium Clavulanate"), "clavulanic acid")
        self.assertEqual(SafetyEngine.normalize_salt_name("Acetaminophen"), "paracetamol")
        self.assertEqual(SafetyEngine.normalize_salt_name("Levothyroxine Sodium"), "thyroxine sodium")

    def test_strength_normalization(self):
        val, unit = SafetyEngine.normalize_strength(0.5, "g")
        self.assertEqual((val, unit), (500.0, "mg"))

        val, unit = SafetyEngine.normalize_strength(50.0, "mcg")
        self.assertEqual((val, unit), (0.05, "mg"))

        val, unit = SafetyEngine.normalize_strength(650.0, "mg")
        self.assertEqual((val, unit), (650.0, "mg"))

    def test_valid_bioequivalence_pass(self):
        verdict = self.engine.validate_substitution(self.augmentin, self.amoxyclav_generic)
        self.assertTrue(verdict.is_safe)
        self.assertTrue(verdict.is_exact_bioequivalent)
        self.assertIsNone(verdict.rejection_reason)

    def test_reject_self_substitution(self):
        verdict = self.engine.validate_substitution(self.augmentin, self.augmentin)
        self.assertFalse(verdict.is_safe)
        self.assertIn("identical", verdict.rejection_reason.lower())

    def test_reject_missing_salt(self):
        # Candidate only has Amoxicillin, missing Clavulanic Acid
        single_salt_candidate = Medicine(
            id="MED-999",
            brand_name="Plain Amox 500",
            manufacturer="Generic Labs",
            salts=[SaltComponent("Amoxicillin", 500.0, "mg")],
            dosage_form=DosageForm.TABLET,
            release_type=ReleaseType.IMMEDIATE_RELEASE,
            pack_size=10,
            mrp=30.0,
            price_per_unit=3.0,
            regulatory_tier=RegulatoryTier.WHO_GMP_GENERIC,
        )
        verdict = self.engine.validate_substitution(self.augmentin, single_salt_candidate)
        self.assertFalse(verdict.is_safe)
        self.assertIn("Missing active salt", verdict.rejection_reason)

    def test_reject_extra_salt(self):
        # Candidate has an extra third drug
        triple_salt_candidate = Medicine(
            id="MED-998",
            brand_name="Amox-Clav-Extra",
            manufacturer="Generic Labs",
            salts=[
                SaltComponent("Amoxicillin", 500.0, "mg"),
                SaltComponent("Clavulanic Acid", 125.0, "mg"),
                SaltComponent("Lactobacillus", 60.0, "mg"),
            ],
            dosage_form=DosageForm.TABLET,
            release_type=ReleaseType.IMMEDIATE_RELEASE,
            pack_size=10,
            mrp=50.0,
            price_per_unit=5.0,
            regulatory_tier=RegulatoryTier.WHO_GMP_GENERIC,
        )
        verdict = self.engine.validate_substitution(self.augmentin, triple_salt_candidate)
        self.assertFalse(verdict.is_safe)
        self.assertIn("Contains unexpected salt", verdict.rejection_reason)

    def test_reject_strength_mismatch(self):
        # Candidate has 250mg Amox instead of 500mg
        wrong_strength = Medicine(
            id="MED-997",
            brand_name="Amoxyclav 375",
            manufacturer="Generic Labs",
            salts=[
                SaltComponent("Amoxicillin", 250.0, "mg"),
                SaltComponent("Clavulanic Acid", 125.0, "mg"),
            ],
            dosage_form=DosageForm.TABLET,
            release_type=ReleaseType.IMMEDIATE_RELEASE,
            pack_size=10,
            mrp=40.0,
            price_per_unit=4.0,
            regulatory_tier=RegulatoryTier.WHO_GMP_GENERIC,
        )
        verdict = self.engine.validate_substitution(self.augmentin, wrong_strength)
        self.assertFalse(verdict.is_safe)
        self.assertIn("Strength mismatch", verdict.rejection_reason)

    def test_reject_dosage_form_incompatibility(self):
        # Tablet prescribed, candidate is Syrup
        syrup_candidate = Medicine(
            id="MED-996",
            brand_name="Amoxyclav Dry Syrup",
            manufacturer="Generic Labs",
            salts=[
                SaltComponent("Amoxicillin", 500.0, "mg"),
                SaltComponent("Clavulanic Acid", 125.0, "mg"),
            ],
            dosage_form=DosageForm.SYRUP,
            release_type=ReleaseType.IMMEDIATE_RELEASE,
            pack_size=1,
            mrp=50.0,
            price_per_unit=5.0,
            regulatory_tier=RegulatoryTier.WHO_GMP_GENERIC,
        )
        verdict = self.engine.validate_substitution(self.augmentin, syrup_candidate)
        self.assertFalse(verdict.is_safe)
        self.assertIn("Incompatible dosage form", verdict.rejection_reason)

    def test_oral_solid_interchangeability_warning(self):
        # Tablet prescribed, candidate is Capsule
        capsule_candidate = Medicine(
            id="MED-995",
            brand_name="Amoxyclav Capsules",
            manufacturer="Generic Labs",
            salts=[
                SaltComponent("Amoxicillin", 500.0, "mg"),
                SaltComponent("Clavulanic Acid", 125.0, "mg"),
            ],
            dosage_form=DosageForm.CAPSULE,
            release_type=ReleaseType.IMMEDIATE_RELEASE,
            pack_size=10,
            mrp=50.0,
            price_per_unit=5.0,
            regulatory_tier=RegulatoryTier.WHO_GMP_GENERIC,
        )
        verdict = self.engine.validate_substitution(self.augmentin, capsule_candidate)
        self.assertTrue(verdict.is_safe)
        self.assertFalse(verdict.is_exact_bioequivalent)
        self.assertTrue(any("Dosage form variation" in w for w in verdict.warnings))

    def test_reject_release_kinetics_clash(self):
        # Prescribed Sustained Release, candidate is Immediate Release -> Dose dumping risk!
        glycomet_sr = Medicine(
            id="MED-SR",
            brand_name="Glycomet SR 500",
            manufacturer="USV",
            salts=[SaltComponent("Metformin", 500.0, "mg")],
            dosage_form=DosageForm.TABLET,
            release_type=ReleaseType.SUSTAINED_RELEASE,
            pack_size=10,
            mrp=40.0,
            price_per_unit=4.0,
            regulatory_tier=RegulatoryTier.BRANDED_INNOVATOR,
        )
        plain_ir = Medicine(
            id="MED-IR",
            brand_name="Metformin IR 500",
            manufacturer="PMBJP",
            salts=[SaltComponent("Metformin", 500.0, "mg")],
            dosage_form=DosageForm.TABLET,
            release_type=ReleaseType.IMMEDIATE_RELEASE,
            pack_size=10,
            mrp=10.0,
            price_per_unit=1.0,
            regulatory_tier=RegulatoryTier.PMBJP_JAN_AUSHADHI,
        )
        verdict = self.engine.validate_substitution(glycomet_sr, plain_ir)
        self.assertFalse(verdict.is_safe)
        self.assertIn("Critical release kinetics clash", verdict.rejection_reason)

    def test_narrow_therapeutic_index_warning(self):
        # Thyroxine / Levothyroxine requires strict monitoring
        thyronorm = Medicine(
            id="MED-THY1",
            brand_name="Thyronorm 50",
            manufacturer="Abbott",
            salts=[SaltComponent("Thyroxine Sodium", 50.0, "mcg")],
            dosage_form=DosageForm.TABLET,
            release_type=ReleaseType.IMMEDIATE_RELEASE,
            pack_size=100,
            mrp=190.0,
            price_per_unit=1.90,
            regulatory_tier=RegulatoryTier.BRANDED_INNOVATOR,
            is_narrow_therapeutic_index=True,
        )
        generic_thy = Medicine(
            id="MED-THY2",
            brand_name="Thyroxine 50mcg Generic",
            manufacturer="PMBJP",
            salts=[SaltComponent("Levothyroxine", 0.05, "mg")],
            dosage_form=DosageForm.TABLET,
            release_type=ReleaseType.IMMEDIATE_RELEASE,
            pack_size=100,
            mrp=40.0,
            price_per_unit=0.40,
            regulatory_tier=RegulatoryTier.PMBJP_JAN_AUSHADHI,
        )
        verdict = self.engine.validate_substitution(thyronorm, generic_thy)
        self.assertTrue(verdict.is_safe)
        self.assertTrue(any("Narrow Therapeutic Index" in w for w in verdict.warnings))

    def test_reject_more_expensive_candidate(self):
        # Candidate costs more than original brand -> must reject
        expensive_candidate = Medicine(
            id="MED-EXP",
            brand_name="Overpriced Generic",
            manufacturer="Shady Pharma",
            salts=[
                SaltComponent("Amoxicillin", 500.0, "mg"),
                SaltComponent("Clavulanic Acid", 125.0, "mg"),
            ],
            dosage_form=DosageForm.TABLET,
            release_type=ReleaseType.IMMEDIATE_RELEASE,
            pack_size=10,
            mrp=300.0,
            price_per_unit=30.0,
            regulatory_tier=RegulatoryTier.BRANDED_GENERIC,
        )
        verdict = self.engine.validate_substitution(self.augmentin, expensive_candidate)
        self.assertFalse(verdict.is_safe)
        self.assertIn("exceeds original brand price", verdict.rejection_reason)


if __name__ == "__main__":
    unittest.main()
