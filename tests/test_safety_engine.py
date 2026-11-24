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

    def test_reject_controlled_release_clash(self):
        cr_med = Medicine(
            id="MED-CR",
            brand_name="Glipizide CR 10mg",
            manufacturer="Innovator",
            salts=[SaltComponent("Glipizide", 10.0, "mg")],
            dosage_form=DosageForm.TABLET,
            release_type=ReleaseType.CONTROLLED_RELEASE,
            pack_size=10,
            mrp=100.0,
            price_per_unit=10.0,
            regulatory_tier=RegulatoryTier.BRANDED_INNOVATOR,
        )
        ir_cand = Medicine(
            id="MED-IR",
            brand_name="Glipizide IR 10mg Generic",
            manufacturer="PMBJP",
            salts=[SaltComponent("Glipizide", 10.0, "mg")],
            dosage_form=DosageForm.TABLET,
            release_type=ReleaseType.IMMEDIATE_RELEASE,
            pack_size=10,
            mrp=20.0,
            price_per_unit=2.0,
            regulatory_tier=RegulatoryTier.PMBJP_JAN_AUSHADHI,
        )
        verdict = self.engine.validate_substitution(cr_med, ir_cand)
        self.assertFalse(verdict.is_safe)
        self.assertIn("Critical release kinetics clash", verdict.rejection_reason)
        self.assertIn("dose-dumping", verdict.rejection_reason)

    def test_reject_enteric_coated_clash(self):
        ec_med = Medicine(
            id="MED-EC",
            brand_name="Pantoprazole EC 40mg",
            manufacturer="Innovator",
            salts=[SaltComponent("Pantoprazole", 40.0, "mg")],
            dosage_form=DosageForm.TABLET,
            release_type=ReleaseType.ENTERIC_COATED,
            pack_size=10,
            mrp=120.0,
            price_per_unit=12.0,
            regulatory_tier=RegulatoryTier.BRANDED_INNOVATOR,
        )
        ir_cand = Medicine(
            id="MED-IR-PANTO",
            brand_name="Pantoprazole Plain 40mg Generic",
            manufacturer="PMBJP",
            salts=[SaltComponent("Pantoprazole", 40.0, "mg")],
            dosage_form=DosageForm.TABLET,
            release_type=ReleaseType.IMMEDIATE_RELEASE,
            pack_size=10,
            mrp=25.0,
            price_per_unit=2.50,
            regulatory_tier=RegulatoryTier.PMBJP_JAN_AUSHADHI,
        )
        verdict = self.engine.validate_substitution(ec_med, ir_cand)
        self.assertFalse(verdict.is_safe)
        self.assertIn("Critical release kinetics clash", verdict.rejection_reason)
        self.assertIn("acid degradation", verdict.rejection_reason)

    def test_canonical_salt_map_mixed_units_additive(self):
        # Two salt components mapping to same canonical salt but in g and mg
        s1 = SaltComponent("Metformin Hydrochloride", 0.5, "g")
        s2 = SaltComponent("Metformin", 500.0, "mg")
        cmap = SafetyEngine.create_canonical_salt_map([s1, s2])
        self.assertIn("metformin", cmap)
        val, unit = cmap["metformin"]
        self.assertEqual(val, 1000.0)
        self.assertEqual(unit, "mg")

    def test_reject_immediate_to_sustained_release_symmetric(self):
        # Prescribed IR substituted with SR must also be rejected symmetrically
        ir_med = Medicine(
            id="MED-IR-SYM",
            brand_name="Metformin IR 500",
            manufacturer="Innovator",
            salts=[SaltComponent("Metformin", 500.0, "mg")],
            dosage_form=DosageForm.TABLET,
            release_type=ReleaseType.IMMEDIATE_RELEASE,
            pack_size=10,
            mrp=30.0,
            price_per_unit=3.0,
            regulatory_tier=RegulatoryTier.BRANDED_INNOVATOR,
        )
        sr_cand = Medicine(
            id="MED-SR-SYM",
            brand_name="Metformin SR 500 Generic",
            manufacturer="PMBJP",
            salts=[SaltComponent("Metformin", 500.0, "mg")],
            dosage_form=DosageForm.TABLET,
            release_type=ReleaseType.SUSTAINED_RELEASE,
            pack_size=10,
            mrp=10.0,
            price_per_unit=1.0,
            regulatory_tier=RegulatoryTier.PMBJP_JAN_AUSHADHI,
        )
        verdict = self.engine.validate_substitution(ir_med, sr_cand)
        self.assertFalse(verdict.is_safe)
        self.assertIn("Critical release kinetics clash", verdict.rejection_reason)

    def test_liquid_concentration_and_inhaler_unit_normalization(self):
        # 125 mg/5ml == 25 mg/ml
        val1, u1 = SafetyEngine.normalize_strength(125.0, "mg/5ml")
        val2, u2 = SafetyEngine.normalize_strength(25.0, "mg/ml")
        self.assertEqual((val1, u1), (25.0, "mg/ml"))
        self.assertEqual((val2, u2), (25.0, "mg/ml"))

        # 0.2 mg/puff == 200 mcg/puff
        p1, pu1 = SafetyEngine.normalize_strength(0.2, "mg/puff")
        p2, pu2 = SafetyEngine.normalize_strength(200.0, "mcg/puff")
        self.assertEqual((p1, pu1), (p2, pu2))

    def test_nti_detection_by_salt_synonym_warfarin_sodium(self):
        # Even without is_narrow_therapeutic_index=True flag, Warfarin Sodium must trigger NTI warning
        orig = Medicine(
            id="MED-WAR1",
            brand_name="WarfBrand 5",
            manufacturer="Innovator",
            salts=[SaltComponent("Warfarin Sodium", 5.0, "mg")],
            dosage_form=DosageForm.TABLET,
            release_type=ReleaseType.IMMEDIATE_RELEASE,
            pack_size=10,
            mrp=50.0,
            price_per_unit=5.0,
            regulatory_tier=RegulatoryTier.BRANDED_INNOVATOR,
            is_narrow_therapeutic_index=False,
        )
        cand = Medicine(
            id="MED-WAR2",
            brand_name="Warfarin 5 Generic",
            manufacturer="PMBJP",
            salts=[SaltComponent("Warfarin", 5.0, "mg")],
            dosage_form=DosageForm.TABLET,
            release_type=ReleaseType.IMMEDIATE_RELEASE,
            pack_size=10,
            mrp=15.0,
            price_per_unit=1.5,
            regulatory_tier=RegulatoryTier.PMBJP_JAN_AUSHADHI,
            is_narrow_therapeutic_index=False,
        )
        verdict = self.engine.validate_substitution(orig, cand)
        self.assertTrue(verdict.is_safe)
        self.assertTrue(any("Narrow Therapeutic Index" in w for w in verdict.warnings))

    def test_non_equivalent_ester_salts_kept_distinct(self):
        # Metoprolol Succinate must NOT normalize into Metoprolol Tartrate
        self.assertNotEqual(
            SafetyEngine.normalize_salt_name("Metoprolol Succinate"),
            SafetyEngine.normalize_salt_name("Metoprolol Tartrate"),
        )

    def test_modified_release_enum_and_clash_rejection(self):
        self.assertEqual(ReleaseType.from_str("MODIFIED_RELEASE"), ReleaseType.MODIFIED_RELEASE)
        mr_med = Medicine(
            id="MED-MR",
            brand_name="Urimax 0.4",
            manufacturer="Cipla",
            salts=[SaltComponent("Tamsulosin", 0.4, "mg")],
            dosage_form=DosageForm.CAPSULE,
            release_type=ReleaseType.MODIFIED_RELEASE,
            pack_size=15,
            mrp=320.0,
            price_per_unit=21.33,
            regulatory_tier=RegulatoryTier.BRANDED_INNOVATOR,
        )
        ir_cand = Medicine(
            id="MED-MR-IR",
            brand_name="Tamsulosin IR 0.4",
            manufacturer="Generic",
            salts=[SaltComponent("Tamsulosin", 0.4, "mg")],
            dosage_form=DosageForm.CAPSULE,
            release_type=ReleaseType.IMMEDIATE_RELEASE,
            pack_size=10,
            mrp=38.0,
            price_per_unit=3.80,
            regulatory_tier=RegulatoryTier.PMBJP_JAN_AUSHADHI,
        )
        verdict = self.engine.validate_substitution(mr_med, ir_cand)
        self.assertFalse(verdict.is_safe)
        self.assertIn("Critical release kinetics clash", verdict.rejection_reason)


if __name__ == "__main__":
    unittest.main()
