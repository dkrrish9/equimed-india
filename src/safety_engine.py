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

    # Salt synonyms mapping to canonical base active pharmaceutical ingredient.
    # Deliberately preserves clinically non-equivalent salts/esters such as
    # metoprolol succinate vs tartrate and diclofenac sodium vs potassium.
    SALT_SYNONYMS: Dict[str, str] = {
        "metformin hydrochloride": "metformin",
        "metformin hcl": "metformin",
        "amoxicillin trihydrate": "amoxicillin",
        "amoxycillin": "amoxicillin",
        "amoxycillin trihydrate": "amoxicillin",
        "clavulanate potassium": "clavulanic acid",
        "potassium clavulanate": "clavulanic acid",
        "atorvastatin calcium": "atorvastatin",
        "rosuvastatin calcium": "rosuvastatin",
        "acetaminophen": "paracetamol",
        "pcm": "paracetamol",
        "levothyroxine": "thyroxine sodium",
        "levothyroxine sodium": "thyroxine sodium",
        "l-thyroxine": "thyroxine sodium",
        "pantoprazole sodium": "pantoprazole",
        "pantoprazole sodium sesquihydrate": "pantoprazole",
        "rabeprazole sodium": "rabeprazole",
        "esomeprazole magnesium": "esomeprazole",
        "omeprazole magnesium": "omeprazole",
        "telmisartan sodium": "telmisartan",
        "amlodipine besylate": "amlodipine",
        "amlodipine besilate": "amlodipine",
        "losartan potassium": "losartan",
        "olmesartan medoxomil": "olmesartan",
        "cilnidipine": "cilnidipine",
        "domperidone maleate": "domperidone",
        "aspirin": "aspirin",
        "acetylsalicylic acid": "aspirin",
        "clopidogrel bisulfate": "clopidogrel",
        "clopidogrel bisulphate": "clopidogrel",
        "sitagliptin phosphate": "sitagliptin",
        "montelukast sodium": "montelukast",
        "cetirizine hcl": "cetirizine",
        "cetirizine hydrochloride": "cetirizine",
        "cetirizine dihydrochloride": "cetirizine",
        "levocetirizine hcl": "levocetirizine",
        "levocetirizine dihydrochloride": "levocetirizine",
        "fexofenadine hcl": "fexofenadine",
        "fexofenadine hydrochloride": "fexofenadine",
        "sertraline hcl": "sertraline",
        "sertraline hydrochloride": "sertraline",
        "escitalopram oxalate": "escitalopram",
        "fluoxetine hcl": "fluoxetine",
        "fluoxetine hydrochloride": "fluoxetine",
        "amitriptyline hcl": "amitriptyline",
        "amitriptyline hydrochloride": "amitriptyline",
        "tamsulosin hcl": "tamsulosin",
        "tamsulosin hydrochloride": "tamsulosin",
        "alfuzosin hcl": "alfuzosin",
        "ciprofloxacin hcl": "ciprofloxacin",
        "ciprofloxacin hydrochloride": "ciprofloxacin",
        "levofloxacin hemihydrate": "levofloxacin",
        "azithromycin dihydrate": "azithromycin",
        "doxycycline hyclate": "doxycycline",
        "doxycycline monohydrate": "doxycycline",
        "propranolol hcl": "propranolol",
        "propranolol hydrochloride": "propranolol",
        "nebivolol hcl": "nebivolol",
        "diltiazem hcl": "diltiazem",
        "tramadol hcl": "tramadol",
        "ondansetron hcl": "ondansetron",
        "drotaverine hcl": "drotaverine",
        "salbutamol sulfate": "salbutamol",
        "salbutamol sulphate": "salbutamol",
        "albuterol": "salbutamol",
        "formoterol fumarate": "formoterol",
        "tiotropium bromide": "tiotropium",
        "enoxaparin sodium": "enoxaparin",
        "warfarin sodium": "warfarin",
        "phenytoin sodium": "phenytoin",
        "lithium carbonate": "lithium",
        "divalproex sodium": "sodium valproate",
        "valproate sodium": "sodium valproate",
        "frusemide": "furosemide",
        "torasemide": "torsemide",
        "mesalazine": "mesalamine",
        "vitamin d3": "cholecalciferol",
        "cholecalciferol (vitamin d3)": "cholecalciferol",
        "vitamin d3 (cholecalciferol)": "cholecalciferol",
        "vitamin c": "ascorbic acid",
        "vitamin b12": "methylcobalamin",
        "mecobalamin": "methylcobalamin",
        "vitamin e": "tocopheryl acetate",
        "udca": "ursodeoxycholic acid",
        # A-Z retail dataset common spellings & counter-ions
        "cefixime trihydrate": "cefixime",
        "cefuroxime axetil": "cefuroxime",
        "cefpodoxime proxetil": "cefpodoxime",
        "phenylephrine hydrochloride": "phenylephrine",
        "phenylephrine hcl": "phenylephrine",
        "chlorpheniramine maleate": "chlorpheniramine",
        "caffeine anhydrous": "caffeine",
        "hctz": "hydrochlorothiazide",
        "ranitidine hydrochloride": "ranitidine",
        "ranitidine hcl": "ranitidine",
        "ambroxol hydrochloride": "ambroxol",
        "ambroxol hcl": "ambroxol",
        "levosalbutamol sulphate": "levosalbutamol",
        "levosalbutamol sulfate": "levosalbutamol",
        "levalbuterol": "levosalbutamol",
        "terbutaline sulphate": "terbutaline",
        "terbutaline sulfate": "terbutaline",
        "guaiphenesin": "guaifenesin",
        "dextromethorphan hydrobromide": "dextromethorphan",
        "dextromethorphan hbr": "dextromethorphan",
        "moxifloxacin hydrochloride": "moxifloxacin",
        "moxifloxacin hcl": "moxifloxacin",
        "nebivolol hydrochloride": "nebivolol",
        "diltiazem hydrochloride": "diltiazem",
        "tramadol hydrochloride": "tramadol",
        "ondansetron hydrochloride": "ondansetron",
        "drotaverine hydrochloride": "drotaverine",
        "alfuzosin hydrochloride": "alfuzosin",
        "teneligliptin hydrobromide": "teneligliptin",
        "teneligliptin hydrobromide hydrate": "teneligliptin",
        "terbinafine hydrochloride": "terbinafine",
        "terbinafine hcl": "terbinafine",
        "betahistine dihydrochloride": "betahistine",
        "betahistine hcl": "betahistine",
        "pyridoxine hydrochloride": "pyridoxine",
        "vitamin b6": "pyridoxine",
        "vitamin b9": "folic acid",
        "paracetamol (acetaminophen)": "paracetamol",
        "acetaminophen (paracetamol)": "paracetamol",
        "aceclofenac": "aceclofenac",
        "ofloxacin": "ofloxacin",
        "ornidazole": "ornidazole",
        "telmisartan": "telmisartan",
        "hydrochlorothiazide": "hydrochlorothiazide",
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
        "sodium valproate",
        "valproic acid",
        "tacrolimus",
        "cyclosporine",
        "amiodarone",
    }

    # Compatible oral solid forms (Tablet <-> Capsule often interchangeable for IR)
    ORAL_SOLID_FORMS: Set[DosageForm] = {DosageForm.TABLET, DosageForm.CAPSULE}

    # Pack-only forms billed per container/pack rather than individual tablet/capsule
    PACK_ONLY_FORMS: Set[DosageForm] = {
        DosageForm.SYRUP,
        DosageForm.INHALER,
        DosageForm.INJECTION,
        DosageForm.DROPS,
        DosageForm.OINTMENT,
    }

    _CONTAINER_MEASURE_RE = re.compile(
        r"(\d+(?:\.\d+)?)\s*(ml|l|gms?|g|mdi|metered\s+doses?|doses?|puffs?)\b",
        re.IGNORECASE,
    )

    @classmethod
    def normalize_salt_name(cls, name: str) -> str:
        """Strip salt counter-ions, waters of hydration, and normalize case/spacing."""
        cleaned = name.strip().lower()
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cls.SALT_SYNONYMS.get(cleaned, cleaned)

    @classmethod
    def normalize_strength(cls, value: float, unit: str) -> Tuple[float, str]:
        """Convert strength to canonical units (mg, mg/ml, mg/g, iu, iu/ml, iu/g, mcg/puff, mcg/spray, %)."""
        u = re.sub(r"\s+", "", unit.strip().lower()).replace("μ", "µ")
        v = float(value)
        if u in ("g", "gm", "gms"):
            return v * 1000.0, "mg"
        if u in ("mcg", "µg", "ug"):
            return v / 1000.0, "mg"
        if u == "mg/5ml":
            return v / 5.0, "mg/ml"
        if u == "mg/15ml":
            return v / 15.0, "mg/ml"
        if u in ("g/5ml", "gm/5ml"):
            return v * 200.0, "mg/ml"
        if u in ("mcg/5ml", "µg/5ml", "ug/5ml"):
            return v / 5000.0, "mg/ml"
        if u in ("mcg/ml", "µg/ml", "ug/ml"):
            return v / 1000.0, "mg/ml"
        if u in ("g/ml", "gm/ml"):
            return v * 1000.0, "mg/ml"
        if u == "iu/5ml":
            return v / 5.0, "iu/ml"
        if u in ("mcg/puff", "µg/puff", "ug/puff", "mcg/actuation", "µg/actuation", "ug/actuation", "mcg/dose", "µg/dose", "ug/dose"):
            return v, "mcg/puff"
        if u in ("mg/puff", "mg/actuation", "mg/dose"):
            return v * 1000.0, "mcg/puff"
        if u in ("mcg/spray", "µg/spray", "ug/spray"):
            return v, "mcg/spray"
        if u == "mg/spray":
            return v * 1000.0, "mcg/spray"
        if u == "mg/g":
            return v, "mg/g"
        if u in ("g/g", "gm/g"):
            return v * 1000.0, "mg/g"
        if u in ("mcg/g", "µg/g", "ug/g"):
            return v / 1000.0, "mg/g"
        if u == "iu/g":
            return v, "iu/g"
        if u in ("%w/v", "w/v%"):
            return v, "% w/v"
        if u in ("%w/w", "w/w%"):
            return v, "% w/w"
        if u in ("%v/v", "v/v%"):
            return v, "% v/v"
        if u in ("mg", "iu", "ml", "%", "mg/ml", "iu/ml"):
            return v, u
        return v, u

    @classmethod
    def _extract_container_measure(cls, med: Medicine) -> Optional[Tuple[float, str, str]]:
        """Extract normalized container quantity (value, canonical_unit, display) for pack-only forms."""
        text = med.pack_size_label.strip() or med.brand_name.strip()
        if not text:
            return None
        match = cls._CONTAINER_MEASURE_RE.search(text)
        if not match:
            return None
        raw_val = float(match.group(1))
        raw_unit = re.sub(r"\s+", " ", match.group(2).strip().lower())
        if raw_unit == "l":
            return raw_val * 1000.0, "ml", f"{match.group(1)} {match.group(2).strip()}"
        if raw_unit in ("g", "gm", "gms"):
            return raw_val, "g", f"{match.group(1)}{raw_unit}"
        if raw_unit in ("mdi", "dose", "doses", "puff", "puffs") or "metered" in raw_unit:
            return raw_val, "mdi", f"{match.group(1)} {match.group(2).strip()}"
        return raw_val, raw_unit, f"{match.group(1)}{raw_unit}"

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
                else:
                    ev, eu = cls.normalize_strength(existing_val, existing_unit)
                    nv, nu = cls.normalize_strength(norm_val, norm_unit)
                    if eu == nu:
                        norm_val = round(ev + nv, 4)
                        norm_unit = eu
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

        # Rule 0b: Discontinued medicines cannot be recommended as substitutes
        if candidate.is_discontinued:
            return SafetyVerdict(
                is_safe=False,
                is_exact_bioequivalent=False,
                rejection_reason="Candidate medicine is discontinued and unavailable.",
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

        # Rule 4: Check Release Kinetics (symmetrically prevent IR <-> modified release mismatch)
        if original.release_type != candidate.release_type:
            critical_releases = (
                ReleaseType.SUSTAINED_RELEASE,
                ReleaseType.EXTENDED_RELEASE,
                ReleaseType.CONTROLLED_RELEASE,
                ReleaseType.MODIFIED_RELEASE,
                ReleaseType.ENTERIC_COATED,
            )
            if original.release_type in critical_releases or candidate.release_type in critical_releases:
                if (
                    original.release_type == ReleaseType.ENTERIC_COATED
                    or candidate.release_type == ReleaseType.ENTERIC_COATED
                ):
                    risk_msg = "acid degradation or severe gastric irritation risk"
                else:
                    risk_msg = "dose-dumping, altered dosing frequency, or peak plasma toxicity risk"
                return SafetyVerdict(
                    is_safe=False,
                    is_exact_bioequivalent=False,
                    rejection_reason=(
                        f"Critical release kinetics clash: Prescribed {original.release_type.value} "
                        f"cannot be substituted with {candidate.release_type.value} due to {risk_msg}."
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

        # Soft container-size warning for pack-only forms (e.g., 60ml vs 100ml syrup)
        if original.dosage_form in self.PACK_ONLY_FORMS and original.dosage_form == candidate.dosage_form:
            orig_container = self._extract_container_measure(original)
            cand_container = self._extract_container_measure(candidate)
            if orig_container and cand_container:
                o_val, o_unit, o_disp = orig_container
                c_val, c_unit, c_disp = cand_container
                if o_unit != c_unit or abs(o_val - c_val) > 0.01:
                    warnings.append(
                        f"Pack/container size variation: Prescribed {o_disp} vs substitute {c_disp}. "
                        f"Verify total volume/doses before dispensing."
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
