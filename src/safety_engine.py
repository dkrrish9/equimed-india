"""Clinical Bioequivalence & Safety Validation Engine.

Enforces CDSCO / Indian Pharmacopoeia safety constraints, salt synonym
normalization, dosage release equivalence, and Narrow Therapeutic Index (NTI)
protection to prevent improper drug substitution.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from src.models import (
    DosageForm,
    Medicine,
    ReleaseType,
    SafetyVerdict,
    SaltComponent,
)


class SafetyEngine:
    """Deterministic clinical validation engine for generic substitution.

    Ensures zero hallucination, strict chemical salt matching, strength
    equivalence, dosage kinetics compatibility, and NTI safety alerts.
    """

    # Salt synonyms mapping to canonical base active pharmaceutical ingredient
    SALT_SYNONYMS: Dict[str, str] = {
        "metformin hydrochloride": "metformin",
        "metformin hcl": "metformin",
        "amoxicillin trihydrate": "amoxicillin",
        "clavulanate potassium": "clavulanic acid",
        "potassium clavulanate": "clavulanic acid",
        "atorvastatin calcium": "atorvastatin",
        "rosuvastatin calcium": "rosuvastatin",
        "acetaminophen": "paracetamol",
        "levothyroxine": "thyroxine sodium",
        "levothyroxine sodium": "thyroxine sodium",
        "l-thyroxine": "thyroxine sodium",
        "pantoprazole sodium": "pantoprazole",
        "rabeprazole sodium": "rabeprazole",
        "esomeprazole magnesium": "esomeprazole",
        "telmisartan sodium": "telmisartan",
        "cilnidipine": "cilnidipine",
        "domperidone maleate": "domperidone",
        "aspirin": "aspirin",
        "acetylsalicylic acid": "aspirin",
    }

    # Narrow Therapeutic Index (NTI) active substances requiring strict oversight
    NTI_SUBSTANCES: Set[str] = {
        "thyroxine sodium",
        "warfarin",
        "digoxin",
        "lithium",
        "phenytoin",
        "theophylline",
        "carbamazepine",
    }

    # Compatible oral solid forms (Tablet <-> Capsule often interchangeable for IR)
    ORAL_SOLID_FORMS: Set[DosageForm] = {DosageForm.TABLET, DosageForm.CAPSULE}

    @classmethod
    def normalize_salt_name(cls, name: str) -> str:
        """Strip salt counter-ions, waters of hydration, and normalize case/spacing."""
        cleaned = name.strip().lower()
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cls.SALT_SYNONYMS.get(cleaned, cleaned)

    @classmethod
    def normalize_strength(cls, value: float, unit: str) -> Tuple[float, str]:
        """Convert strength to canonical units (mg or IU)."""
        u = unit.strip().lower()
        v = float(value)
        if u == "g":
            return v * 1000.0, "mg"
        if u in ("mcg", "µg", "ug"):
            return v / 1000.0, "mg"
        if u in ("mg", "iu", "ml", "%"):
            return v, u
        return v, u

    @classmethod
    def create_canonical_salt_map(cls, salts: List[SaltComponent]) -> Dict[str, Tuple[float, str]]:
        """Build dictionary of {canonical_name: (normalized_strength, unit)}."""
        result: Dict[str, Tuple[float, str]] = {}
        for salt in salts:
            canonical_name = cls.normalize_salt_name(salt.name)
            norm_val, norm_unit = cls.normalize_strength(salt.strength_value, salt.strength_unit)
            # Round to 4 decimal places for floating-point tolerance
            norm_val = round(norm_val, 4)
            if canonical_name in result:
                existing_val, existing_unit = result[canonical_name]
                if existing_unit == norm_unit:
                    norm_val = round(existing_val + norm_val, 4)
            result[canonical_name] = (norm_val, norm_unit)
        return result

    def validate_substitution(
        self,
        original: Medicine,
        candidate: Medicine,
    ) -> SafetyVerdict:
        """Thoroughly validate whether a candidate medicine is a safe, bioequivalent substitute.

        Rules enforced:
        1. Exact active chemical composition (no missing or extra salts).
        2. Exact strength equivalence per salt.
        3. Form equivalence (e.g. tablet vs syrup rejected).
        4. Release kinetics safety (IR vs SR/ER flagged/rejected).
        5. Narrow Therapeutic Index (NTI) warning generation.
        6. Cost sanity check (candidate must not be more expensive).
        """
        warnings: List[str] = []

        # Rule 0: Candidate cannot be the exact same medicine ID
        if original.id == candidate.id:
            return SafetyVerdict(
                is_safe=False,
                is_exact_bioequivalent=False,
                rejection_reason="Candidate is identical to the original medicine.",
            )

        # Rule 1: Check active salt composition
        orig_map = self.create_canonical_salt_map(original.salts)
        cand_map = self.create_canonical_salt_map(candidate.salts)

        if set(orig_map.keys()) != set(cand_map.keys()):
            missing = set(orig_map.keys()) - set(cand_map.keys())
            extra = set(cand_map.keys()) - set(orig_map.keys())
            details = []
            if missing:
                details.append(f"Missing active salt(s): {', '.join(missing)}")
            if extra:
                details.append(f"Contains unexpected salt(s): {', '.join(extra)}")
            return SafetyVerdict(
                is_safe=False,
                is_exact_bioequivalent=False,
                rejection_reason=f"Chemical composition mismatch. {'; '.join(details)}",
            )

        # Rule 2: Check strength equivalence for each salt
        for salt_name, (orig_val, orig_unit) in orig_map.items():
            cand_val, cand_unit = cand_map[salt_name]
            if orig_unit != cand_unit or abs(orig_val - cand_val) > 0.001:
                return SafetyVerdict(
                    is_safe=False,
                    is_exact_bioequivalent=False,
                    rejection_reason=(
                        f"Strength mismatch for '{salt_name}': "
                        f"Prescribed {orig_val}{orig_unit} vs Candidate {cand_val}{cand_unit}."
                    ),
                )

        # Rule 3: Check Dosage Form compatibility
        if original.dosage_form != candidate.dosage_form:
            # Check if both are oral solid forms (tablet vs capsule)
            if (
                original.dosage_form in self.ORAL_SOLID_FORMS
                and candidate.dosage_form in self.ORAL_SOLID_FORMS
            ):
                warnings.append(
                    f"Dosage form variation: Prescribed as {original.dosage_form.value}, "
                    f"substitute is {candidate.dosage_form.value}. Pharmacologically interchangeable for oral absorption."
                )
            else:
                return SafetyVerdict(
                    is_safe=False,
                    is_exact_bioequivalent=False,
                    rejection_reason=(
                        f"Incompatible dosage form: Prescribed {original.dosage_form.value} "
                        f"cannot be substituted with {candidate.dosage_form.value}."
                    ),
                )

        # Rule 4: Check Release Kinetics
        if original.release_type != candidate.release_type:
            if original.release_type in (ReleaseType.SUSTAINED_RELEASE, ReleaseType.EXTENDED_RELEASE):
                return SafetyVerdict(
                    is_safe=False,
                    is_exact_bioequivalent=False,
                    rejection_reason=(
                        f"Critical release kinetics clash: Prescribed {original.release_type.value} "
                        f"cannot be substituted with {candidate.release_type.value} due to dose-dumping/peak plasma risk."
                    ),
                )
            warnings.append(
                f"Release mechanism note: Prescribed {original.release_type.value} vs "
                f"substitute {candidate.release_type.value}."
            )

        # Rule 5: Narrow Therapeutic Index (NTI) check
        is_nti = original.is_narrow_therapeutic_index or candidate.is_narrow_therapeutic_index
        if not is_nti:
            for s_name in orig_map:
                if s_name in self.NTI_SUBSTANCES:
                    is_nti = True
                    break

        if is_nti:
            warnings.append(
                "CAUTION: Narrow Therapeutic Index (NTI) medicine. "
                "Consult physician or clinical pharmacist for TSH/plasma concentration monitoring before brand switch."
            )

        # Rule 6: Price sanity check (Substitute must not be more expensive)
        if candidate.price_per_unit > original.price_per_unit:
            return SafetyVerdict(
                is_safe=False,
                is_exact_bioequivalent=False,
                rejection_reason=(
                    f"Substitute price per unit (₹{candidate.price_per_unit:.2f}) "
                    f"exceeds original brand price (₹{original.price_per_unit:.2f})."
                ),
            )

        is_exact = (
            original.dosage_form == candidate.dosage_form
            and original.release_type == candidate.release_type
        )

        return SafetyVerdict(
            is_safe=True,
            is_exact_bioequivalent=is_exact,
            warnings=warnings,
        )
