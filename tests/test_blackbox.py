"""Black-Box Testing Suite: Equivalence Class Partitioning (ECP) & Boundary Value Analysis (BVA).

Directly demonstrates formal verification methodologies required under Software Engineering syllabus.
"""

import unittest
from src.models import (
    DosageForm,
    Medicine,
    RegulatoryTier,
    ReleaseType,
    SaltComponent,
)
from src.safety_engine import SafetyEngine


class TestEquivalenceClassPartitioning(unittest.TestCase):
    """Formal Equivalence Class Partitioning (ECP) tests.

    Partitions:
    - EC1 (Valid): Active salts identical, strength identical, release kinetics identical -> ACCEPT
    - EC2 (Invalid): Active salt chemical composition differs (missing/extra) -> REJECT
    - EC3 (Invalid): Strength differs beyond clinical tolerance -> REJECT
    - EC4 (Invalid): Dosage form pharmacokinetically incompatible (Tablet vs Syrup) -> REJECT
    - EC5 (Valid with warning): Oral solid forms interchange (Tablet <-> Capsule) -> ACCEPT WITH WARNING
    - EC6 (Invalid): Release profile clash (Sustained Release substituted with Immediate Release) -> REJECT
    - EC7 (Valid with alert): Narrow Therapeutic Index (NTI) drug -> ACCEPT WITH MANDATORY ALERT
    - EC8 (Invalid): Economic violation (Candidate price exceeds original price) -> REJECT
    """

    def setUp(self):
        self.engine = SafetyEngine()
        self.base_med = Medicine(
            id="REF-1", brand_name="Reference Tablet 500mg", manufacturer="Originator",
            salts=[SaltComponent("Metformin", 500.0, "mg")],
            dosage_form=DosageForm.TABLET, release_type=ReleaseType.SUSTAINED_RELEASE,
            pack_size=10, mrp=50.0, price_per_unit=5.0, regulatory_tier=RegulatoryTier.BRANDED_INNOVATOR
        )

    def test_ec1_valid_exact_match(self):
        cand = Medicine(
            id="CAND-1", brand_name="Generic Metformin SR 500mg", manufacturer="PMBJP",
            salts=[SaltComponent("Metformin Hydrochloride", 500.0, "mg")],
            dosage_form=DosageForm.TABLET, release_type=ReleaseType.SUSTAINED_RELEASE,
            pack_size=10, mrp=12.0, price_per_unit=1.20, regulatory_tier=RegulatoryTier.PMBJP_JAN_AUSHADHI
        )
        verdict = self.engine.validate_substitution(self.base_med, cand)
        self.assertTrue(verdict.is_safe)
        self.assertTrue(verdict.is_exact_bioequivalent)

    def test_ec2_invalid_chemical_salt_mismatch(self):
        cand = Medicine(
            id="CAND-2", brand_name="Glimepiride 2mg", manufacturer="Generic",
            salts=[SaltComponent("Glimepiride", 2.0, "mg")],
            dosage_form=DosageForm.TABLET, release_type=ReleaseType.SUSTAINED_RELEASE,
            pack_size=10, mrp=10.0, price_per_unit=1.0, regulatory_tier=RegulatoryTier.WHO_GMP_GENERIC
        )
        verdict = self.engine.validate_substitution(self.base_med, cand)
        self.assertFalse(verdict.is_safe)
        self.assertIn("Chemical composition mismatch", verdict.rejection_reason)

    def test_ec3_invalid_strength_mismatch(self):
        cand = Medicine(
            id="CAND-3", brand_name="Metformin SR 850mg", manufacturer="Generic",
            salts=[SaltComponent("Metformin", 850.0, "mg")],
            dosage_form=DosageForm.TABLET, release_type=ReleaseType.SUSTAINED_RELEASE,
            pack_size=10, mrp=15.0, price_per_unit=1.50, regulatory_tier=RegulatoryTier.WHO_GMP_GENERIC
        )
        verdict = self.engine.validate_substitution(self.base_med, cand)
        self.assertFalse(verdict.is_safe)
        self.assertIn("Strength mismatch", verdict.rejection_reason)

    def test_ec4_invalid_form_incompatibility(self):
        cand = Medicine(
            id="CAND-4", brand_name="Metformin Oral Suspension", manufacturer="Generic",
            salts=[SaltComponent("Metformin", 500.0, "mg")],
            dosage_form=DosageForm.SYRUP, release_type=ReleaseType.SUSTAINED_RELEASE,
            pack_size=1, mrp=20.0, price_per_unit=2.0, regulatory_tier=RegulatoryTier.WHO_GMP_GENERIC
        )
        verdict = self.engine.validate_substitution(self.base_med, cand)
        self.assertFalse(verdict.is_safe)
        self.assertIn("Incompatible dosage form", verdict.rejection_reason)

    def test_ec5_valid_oral_solid_interchange_with_warning(self):
        # Immediate release tablet to immediate release capsule
        ir_tablet = Medicine(
            id="REF-IR", brand_name="IR Tablet 500", manufacturer="Mfg",
            salts=[SaltComponent("Amoxicillin", 500.0, "mg")],
            dosage_form=DosageForm.TABLET, release_type=ReleaseType.IMMEDIATE_RELEASE,
            pack_size=10, mrp=100.0, price_per_unit=10.0, regulatory_tier=RegulatoryTier.BRANDED_INNOVATOR
        )
        ir_capsule = Medicine(
            id="CAND-CAP", brand_name="IR Capsule 500", manufacturer="Generic",
            salts=[SaltComponent("Amoxicillin", 500.0, "mg")],
            dosage_form=DosageForm.CAPSULE, release_type=ReleaseType.IMMEDIATE_RELEASE,
            pack_size=10, mrp=40.0, price_per_unit=4.0, regulatory_tier=RegulatoryTier.WHO_GMP_GENERIC
        )
        verdict = self.engine.validate_substitution(ir_tablet, ir_capsule)
        self.assertTrue(verdict.is_safe)
        self.assertFalse(verdict.is_exact_bioequivalent)
        self.assertTrue(any("Dosage form variation" in w for w in verdict.warnings))

    def test_ec6_invalid_release_profile_clash(self):
        # Sustained release substituted with immediate release -> dangerous!
        cand_ir = Medicine(
            id="CAND-IR", brand_name="Plain Metformin IR", manufacturer="Generic",
            salts=[SaltComponent("Metformin", 500.0, "mg")],
            dosage_form=DosageForm.TABLET, release_type=ReleaseType.IMMEDIATE_RELEASE,
            pack_size=10, mrp=10.0, price_per_unit=1.0, regulatory_tier=RegulatoryTier.WHO_GMP_GENERIC
        )
        verdict = self.engine.validate_substitution(self.base_med, cand_ir)
        self.assertFalse(verdict.is_safe)
        self.assertIn("release kinetics clash", verdict.rejection_reason.lower())

    def test_ec7_valid_nti_alert(self):
        # Warfarin / Levothyroxine NTI check
        orig_nti = Medicine(
            id="REF-NTI", brand_name="Coumadin 5mg", manufacturer="Innovator",
            salts=[SaltComponent("Warfarin", 5.0, "mg")],
            dosage_form=DosageForm.TABLET, release_type=ReleaseType.IMMEDIATE_RELEASE,
            pack_size=30, mrp=300.0, price_per_unit=10.0, regulatory_tier=RegulatoryTier.BRANDED_INNOVATOR,
            is_narrow_therapeutic_index=True
        )
        cand_nti = Medicine(
            id="CAND-NTI", brand_name="Warfarin Generic 5mg", manufacturer="PMBJP",
            salts=[SaltComponent("Warfarin", 5.0, "mg")],
            dosage_form=DosageForm.TABLET, release_type=ReleaseType.IMMEDIATE_RELEASE,
            pack_size=30, mrp=60.0, price_per_unit=2.0, regulatory_tier=RegulatoryTier.PMBJP_JAN_AUSHADHI
        )
        verdict = self.engine.validate_substitution(orig_nti, cand_nti)
        self.assertTrue(verdict.is_safe)
        self.assertTrue(any("Narrow Therapeutic Index" in w for w in verdict.warnings))

    def test_ec8_invalid_economic_price_escalation(self):
        expensive_cand = Medicine(
            id="CAND-EXP", brand_name="Overpriced Generic", manufacturer="Generic",
            salts=[SaltComponent("Metformin", 500.0, "mg")],
            dosage_form=DosageForm.TABLET, release_type=ReleaseType.SUSTAINED_RELEASE,
            pack_size=10, mrp=90.0, price_per_unit=9.0, regulatory_tier=RegulatoryTier.BRANDED_GENERIC
        )
        verdict = self.engine.validate_substitution(self.base_med, expensive_cand)
        self.assertFalse(verdict.is_safe)
        self.assertIn("exceeds original brand price", verdict.rejection_reason)


class TestBoundaryValueAnalysis(unittest.TestCase):
    """Formal Boundary Value Analysis (BVA) tests for numerical strengths and prices."""

    def setUp(self):
        self.engine = SafetyEngine()

    def test_bva_strength_microgram_to_milligram_boundary(self):
        # Boundary at 0.05 mg == 50.0 mcg (Thyroxine standard)
        orig = Medicine(
            id="BVA-1", brand_name="Thyro Brand", manufacturer="Mfg",
            salts=[SaltComponent("Thyroxine Sodium", 50.0, "mcg")],
            dosage_form=DosageForm.TABLET, release_type=ReleaseType.IMMEDIATE_RELEASE,
            pack_size=10, mrp=20.0, price_per_unit=2.0, regulatory_tier=RegulatoryTier.BRANDED_INNOVATOR
        )
        # Test exact boundary: 0.05 mg
        cand_exact = Medicine(
            id="BVA-2", brand_name="Thyro Generic", manufacturer="PMBJP",
            salts=[SaltComponent("Thyroxine Sodium", 0.05, "mg")],
            dosage_form=DosageForm.TABLET, release_type=ReleaseType.IMMEDIATE_RELEASE,
            pack_size=10, mrp=5.0, price_per_unit=0.5, regulatory_tier=RegulatoryTier.PMBJP_JAN_AUSHADHI
        )
        verdict = self.engine.validate_substitution(orig, cand_exact)
        self.assertTrue(verdict.is_safe)

        # Test slightly outside boundary: 0.052 mg (exceeds tolerance of 0.001)
        cand_off = Medicine(
            id="BVA-3", brand_name="Thyro Off", manufacturer="PMBJP",
            salts=[SaltComponent("Thyroxine Sodium", 0.055, "mg")],
            dosage_form=DosageForm.TABLET, release_type=ReleaseType.IMMEDIATE_RELEASE,
            pack_size=10, mrp=5.0, price_per_unit=0.5, regulatory_tier=RegulatoryTier.PMBJP_JAN_AUSHADHI
        )
        verdict_off = self.engine.validate_substitution(orig, cand_off)
        self.assertFalse(verdict_off.is_safe)

    def test_bva_equal_price_boundary(self):
        # Boundary: Candidate price is exactly equal to original price
        orig = Medicine(
            id="BVA-P1", brand_name="Equal Price Brand", manufacturer="Mfg",
            salts=[SaltComponent("Paracetamol", 500.0, "mg")],
            dosage_form=DosageForm.TABLET, release_type=ReleaseType.IMMEDIATE_RELEASE,
            pack_size=10, mrp=20.0, price_per_unit=2.00, regulatory_tier=RegulatoryTier.BRANDED_INNOVATOR
        )
        cand_equal = Medicine(
            id="BVA-P2", brand_name="Equal Price Generic", manufacturer="Generic",
            salts=[SaltComponent("Paracetamol", 500.0, "mg")],
            dosage_form=DosageForm.TABLET, release_type=ReleaseType.IMMEDIATE_RELEASE,
            pack_size=10, mrp=20.0, price_per_unit=2.00, regulatory_tier=RegulatoryTier.WHO_GMP_GENERIC
        )
        verdict = self.engine.validate_substitution(orig, cand_equal)
        # Price is equal (not strictly greater), so safe check passes
        self.assertTrue(verdict.is_safe)

        # Price boundary + 0.01 paise higher -> must reject
        cand_higher = Medicine(
            id="BVA-P3", brand_name="Slightly Higher Generic", manufacturer="Generic",
            salts=[SaltComponent("Paracetamol", 500.0, "mg")],
            dosage_form=DosageForm.TABLET, release_type=ReleaseType.IMMEDIATE_RELEASE,
            pack_size=10, mrp=20.10, price_per_unit=2.01, regulatory_tier=RegulatoryTier.WHO_GMP_GENERIC
        )
        verdict_higher = self.engine.validate_substitution(orig, cand_higher)
        self.assertFalse(verdict_higher.is_safe)


if __name__ == "__main__":
    unittest.main()
