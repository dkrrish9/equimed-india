"""Domain models for EquiMed Generic Medicine Substitution Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Any, Dict, List, Optional


class DosageForm(str, Enum):
    """Pharmaceutical dosage forms recognized under Indian Pharmacopoeia."""
    TABLET = "TABLET"
    CAPSULE = "CAPSULE"
    SYRUP = "SYRUP"
    INJECTION = "INJECTION"
    INHALER = "INHALER"
    DROPS = "DROPS"
    OINTMENT = "OINTMENT"

    @classmethod
    def from_str(cls, val: str) -> "DosageForm":
        normalized = val.strip().upper()
        for member in cls:
            if member.value == normalized:
                return member
        return cls.TABLET


class ReleaseType(str, Enum):
    """Drug release kinetics mechanism."""
    IMMEDIATE_RELEASE = "IMMEDIATE_RELEASE"  # IR
    SUSTAINED_RELEASE = "SUSTAINED_RELEASE"  # SR
    EXTENDED_RELEASE = "EXTENDED_RELEASE"    # ER
    CONTROLLED_RELEASE = "CONTROLLED_RELEASE"  # CR
    MODIFIED_RELEASE = "MODIFIED_RELEASE"      # MR
    ENTERIC_COATED = "ENTERIC_COATED"        # EC

    @classmethod
    def from_str(cls, val: str) -> "ReleaseType":
        normalized = val.strip().upper()
        for member in cls:
            if member.value == normalized:
                return member
        return cls.IMMEDIATE_RELEASE


class RegulatoryTier(str, Enum):
    """Regulatory and manufacturing certification tiers in India."""
    PMBJP_JAN_AUSHADHI = "PMBJP_JAN_AUSHADHI"      # Government scheme, highest subsidy
    WHO_GMP_GENERIC = "WHO_GMP_GENERIC"            # World Health Organization GMP certified
    CDSCO_APPROVED_GENERIC = "CDSCO_APPROVED_GENERIC"  # Indian central regulator approved
    BRANDED_INNOVATOR = "BRANDED_INNOVATOR"        # High-cost branded originator/marketing
    BRANDED_GENERIC = "BRANDED_GENERIC"            # Branded generic with moderate markup


_SAFETY_ENGINE_CLS: Any = None


@dataclass(frozen=True)
class SaltComponent:
    """Active Pharmaceutical Ingredient (API) component with strength."""
    name: str
    strength_value: float
    strength_unit: str = "mg"

    def normalized_key(self) -> str:
        """Returns standard chemical identifier string: e.g. 'amoxicillin:500.0:mg'."""
        global _SAFETY_ENGINE_CLS
        if _SAFETY_ENGINE_CLS is None:
            from src.safety_engine import SafetyEngine
            _SAFETY_ENGINE_CLS = SafetyEngine
        canonical_name = _SAFETY_ENGINE_CLS.normalize_salt_name(self.name)
        norm_val, norm_unit = _SAFETY_ENGINE_CLS.normalize_strength(self.strength_value, self.strength_unit)
        return f"{canonical_name}:{round(norm_val, 4)}:{norm_unit}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "strength_value": self.strength_value,
            "strength_unit": self.strength_unit,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SaltComponent":
        return cls(
            name=str(data["name"]),
            strength_value=float(data["strength_value"]),
            strength_unit=str(data.get("strength_unit", "mg")),
        )


@dataclass
class Medicine:
    """Entity representing a pharmaceutical product in the Indian market."""
    id: str
    brand_name: str
    manufacturer: str
    salts: List[SaltComponent]
    dosage_form: DosageForm
    release_type: ReleaseType
    pack_size: int
    mrp: float
    price_per_unit: float
    regulatory_tier: RegulatoryTier
    is_narrow_therapeutic_index: bool = False
    therapeutic_category: str = "General"
    is_discontinued: bool = False
    pack_size_label: str = ""
    source: str = "curated"

    def salt_fingerprint(self) -> str:
        """Deterministic fingerprint independent of salt ordering in combination drugs.

        e.g. Glimepiride 2mg + Metformin 500mg produces identical fingerprint to
             Metformin 500mg + Glimepiride 2mg.
        """
        sorted_keys = sorted(salt.normalized_key() for salt in self.salts)
        form_str = self.dosage_form.value
        release_str = self.release_type.value
        return f"{'|'.join(sorted_keys)}#{form_str}#{release_str}"

    def packs_for_units(self, total_units: int) -> int:
        """Compute minimum whole retail packs/strips needed for a unit quantity."""
        if total_units <= 0:
            return 0
        pack = max(1, int(self.pack_size))
        return math.ceil(total_units / pack)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "brand_name": self.brand_name,
            "manufacturer": self.manufacturer,
            "salts": [s.to_dict() for s in self.salts],
            "dosage_form": self.dosage_form.value,
            "release_type": self.release_type.value,
            "pack_size": self.pack_size,
            "mrp": self.mrp,
            "price_per_unit": self.price_per_unit,
            "regulatory_tier": self.regulatory_tier.value,
            "is_narrow_therapeutic_index": self.is_narrow_therapeutic_index,
            "therapeutic_category": self.therapeutic_category,
            "is_discontinued": self.is_discontinued,
            "pack_size_label": self.pack_size_label,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Medicine":
        salts = [SaltComponent.from_dict(s) for s in data.get("salts", [])]
        dosage_form = DosageForm.from_str(data.get("dosage_form", "TABLET"))
        release_type = ReleaseType.from_str(data.get("release_type", "IMMEDIATE_RELEASE"))
        reg_tier_raw = data.get("regulatory_tier", "BRANDED_GENERIC")
        try:
            reg_tier = RegulatoryTier(reg_tier_raw)
        except ValueError:
            reg_tier = RegulatoryTier.BRANDED_GENERIC

        return cls(
            id=str(data["id"]),
            brand_name=str(data["brand_name"]),
            manufacturer=str(data.get("manufacturer", "Unknown")),
            salts=salts,
            dosage_form=dosage_form,
            release_type=release_type,
            pack_size=int(data.get("pack_size", 10)),
            mrp=float(data["mrp"]),
            price_per_unit=float(data["price_per_unit"]),
            regulatory_tier=reg_tier,
            is_narrow_therapeutic_index=bool(data.get("is_narrow_therapeutic_index", False)),
            therapeutic_category=str(data.get("therapeutic_category", "General")),
            is_discontinued=bool(data.get("is_discontinued", False)),
            pack_size_label=str(data.get("pack_size_label", "")),
            source=str(data.get("source", "curated")),
        )


@dataclass
class SafetyVerdict:
    """Result of clinical bioequivalence and safety validation check."""
    is_safe: bool
    is_exact_bioequivalent: bool
    rejection_reason: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


@dataclass
class SubstitutionMatch:
    """Evaluated generic substitute with savings and safety metadata."""
    original_medicine: Medicine
    substitute_medicine: Medicine
    price_original_unit: float
    price_substitute_unit: float
    savings_per_unit: float
    percentage_savings: float
    safety_verdict: SafetyVerdict
    ranking_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_id": self.original_medicine.id,
            "original_brand": self.original_medicine.brand_name,
            "substitute_id": self.substitute_medicine.id,
            "substitute_brand": self.substitute_medicine.brand_name,
            "substitute_manufacturer": self.substitute_medicine.manufacturer,
            "regulatory_tier": self.substitute_medicine.regulatory_tier.value,
            "original_price_unit": self.price_original_unit,
            "substitute_price_unit": self.price_substitute_unit,
            "savings_per_unit": round(self.savings_per_unit, 2),
            "percentage_savings": round(self.percentage_savings, 2),
            "is_exact_bioequivalent": self.safety_verdict.is_exact_bioequivalent,
            "warnings": self.safety_verdict.warnings,
            "ranking_score": round(self.ranking_score, 4),
        }


@dataclass
class PrescriptionItem:
    """Single prescribed item with daily dosage and duration."""
    medicine: Medicine
    units_per_day: int = 1
    duration_days: int = 30

    @property
    def total_units(self) -> int:
        return self.units_per_day * self.duration_days

    @property
    def total_cost(self) -> float:
        return round(self.total_units * self.medicine.price_per_unit, 2)

    @property
    def packs_needed(self) -> int:
        return self.medicine.packs_for_units(self.total_units)

    @property
    def pack_total_cost(self) -> float:
        return round(self.packs_needed * self.medicine.mrp, 2)


@dataclass
class PrescriptionBasket:
    """Collection of prescription items for a patient."""
    basket_id: str
    patient_profile: str
    items: List[PrescriptionItem] = field(default_factory=list)

    @property
    def total_cost(self) -> float:
        return round(sum(item.total_cost for item in self.items), 2)


@dataclass
class OptimizedItem:
    """Optimized prescription item comparing original vs substitute."""
    original_item: PrescriptionItem
    best_substitute: Optional[Medicine]
    substitution_match: Optional[SubstitutionMatch]
    original_cost: float
    optimized_cost: float
    savings_amount: float
    savings_percentage: float
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        sub_name = self.best_substitute.brand_name if self.best_substitute else "None"
        sub_mfg = self.best_substitute.manufacturer if self.best_substitute else "N/A"
        salts_str = ", ".join(
            f"{s.name} {int(s.strength_value) if float(s.strength_value).is_integer() else s.strength_value}{s.strength_unit}"
            for s in self.original_item.medicine.salts
        )
        return {
            "original_id": self.original_item.medicine.id,
            "original_brand": self.original_item.medicine.brand_name,
            "dosage_form": self.original_item.medicine.dosage_form.value,
            "salts": salts_str,
            "units_per_day": self.original_item.units_per_day,
            "duration_days": self.original_item.duration_days,
            "substitute_id": self.best_substitute.id if self.best_substitute else None,
            "substitute_brand": sub_name,
            "manufacturer": sub_mfg,
            "units_needed": self.original_item.total_units,
            "original_cost": self.original_cost,
            "optimized_cost": self.optimized_cost,
            "savings_amount": self.savings_amount,
            "savings_percentage": self.savings_percentage,
            "warnings": self.warnings,
        }


@dataclass
class BasketOptimizationResult:
    """Aggregate savings report for a multi-medicine prescription."""
    basket_id: str
    patient_profile: str
    items: List[OptimizedItem]
    original_total_cost: float
    optimized_total_cost: float
    monthly_savings_amount: float
    monthly_savings_percentage: float
    annual_projected_savings: float
    safety_alerts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "basket_id": self.basket_id,
            "patient_profile": self.patient_profile,
            "original_total_cost": self.original_total_cost,
            "optimized_total_cost": self.optimized_total_cost,
            "monthly_savings_amount": self.monthly_savings_amount,
            "monthly_savings_percentage": self.monthly_savings_percentage,
            "annual_projected_savings": self.annual_projected_savings,
            "safety_alerts": self.safety_alerts,
            "items": [it.to_dict() for it in self.items],
        }
