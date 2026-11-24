"""Prescription Basket & Chronic Disease Care Optimizer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.models import (
    BasketOptimizationResult,
    OptimizedItem,
    PrescriptionBasket,
    PrescriptionItem,
)
from src.search_engine import SearchEngine
from src.strategy import SubstitutionStrategy


class PrescriptionOptimizer:
    """Optimizes multi-drug prescriptions and chronic disease therapy baskets."""

    def __init__(self, search_engine: SearchEngine) -> None:
        self.search_engine = search_engine

    def optimize_basket(
        self,
        basket_id: str,
        patient_profile: str,
        items: List[PrescriptionItem],
        strategy: Optional[SubstitutionStrategy] = None,
    ) -> BasketOptimizationResult:
        """Optimize an entire prescription by identifying the best bioequivalent generic for each item.

        Args:
            basket_id: Unique identifier for the basket.
            patient_profile: Clinical / demographic patient description.
            items: Prescribed items with quantity and days supply.
            strategy: Custom ranking strategy (optional).

        Returns:
            BasketOptimizationResult with comprehensive economic and safety analysis.
        """
        optimized_items: List[OptimizedItem] = []
        original_total = 0.0
        optimized_total = 0.0
        all_safety_alerts: List[str] = []

        for item in items:
            orig_cost = item.total_cost
            original_total += orig_cost

            # Find best substitute
            matches = self.search_engine.find_substitutes(
                query_or_medicine=item.medicine,
                strategy=strategy,
                limit=1,
            )

            if matches:
                best_match = matches[0]
                best_sub = best_match.substitute_medicine
                item_opt_cost = round(item.total_units * best_sub.price_per_unit, 2)
                item_savings = round(orig_cost - item_opt_cost, 2)
                item_pct = round((item_savings / orig_cost) * 100.0, 2) if orig_cost > 0 else 0.0
                item_warnings = list(best_match.safety_verdict.warnings)

                for w in item_warnings:
                    alert_text = f"[{item.medicine.brand_name} -> {best_sub.brand_name}] {w}"
                    if alert_text not in all_safety_alerts:
                        all_safety_alerts.append(alert_text)

                optimized_items.append(OptimizedItem(
                    original_item=item,
                    best_substitute=best_sub,
                    substitution_match=best_match,
                    original_cost=orig_cost,
                    optimized_cost=item_opt_cost,
                    savings_amount=item_savings,
                    savings_percentage=item_pct,
                    warnings=item_warnings,
                ))
                optimized_total += item_opt_cost
            else:
                # No valid substitute found
                optimized_items.append(OptimizedItem(
                    original_item=item,
                    best_substitute=None,
                    substitution_match=None,
                    original_cost=orig_cost,
                    optimized_cost=orig_cost,
                    savings_amount=0.0,
                    savings_percentage=0.0,
                    warnings=["No approved generic substitute with identical salt strength found."],
                ))
                optimized_total += orig_cost

        monthly_savings = round(original_total - optimized_total, 2)
        pct_monthly = round((monthly_savings / original_total) * 100.0, 2) if original_total > 0 else 0.0
        annual_savings = round(monthly_savings * 12.0, 2)

        result = BasketOptimizationResult(
            basket_id=basket_id,
            patient_profile=patient_profile,
            items=optimized_items,
            original_total_cost=round(original_total, 2),
            optimized_total_cost=round(optimized_total, 2),
            monthly_savings_amount=monthly_savings,
            monthly_savings_percentage=pct_monthly,
            annual_projected_savings=annual_savings,
            safety_alerts=all_safety_alerts,
        )

        self.search_engine.notify("BASKET_OPTIMIZED", {
            "basket_id": basket_id,
            "patient_profile": patient_profile,
            "monthly_savings_amount": monthly_savings,
            "monthly_savings_percentage": pct_monthly,
        })

        return result

    def optimize_custom_cart(
        self,
        cart_specs: List[Dict[str, Any]],
        strategy: Optional[SubstitutionStrategy] = None,
    ) -> Dict[str, Any]:
        """Optimize a custom prescription cart with dual unit + real pharmacy strip/pack billing."""
        repo = self.search_engine.repository
        resolved_items: List[Dict[str, Any]] = []
        unresolved_items: List[str] = []
        all_alerts: List[str] = []

        orig_unit_total = 0.0
        opt_unit_total = 0.0
        orig_pack_total = 0.0
        opt_pack_total = 0.0

        for spec in cart_specs:
            med_id = str(spec.get("medicine_id") or "").strip()
            brand_name = str(spec.get("brand_name") or "").strip()

            med = repo.get_by_id(med_id) if med_id else None
            if not med and brand_name:
                med = repo.get_by_brand_exact(brand_name)
                if not med:
                    hits = repo.search_by_brand(brand_name, limit=1)
                    med = hits[0] if hits else None

            if not med:
                unresolved_items.append(brand_name or med_id or "Unknown medicine")
                continue

            try:
                units_per_day = max(1, int(spec.get("units_per_day", 1)))
            except (TypeError, ValueError):
                units_per_day = 1
            try:
                duration_days = max(1, int(spec.get("duration_days", 30)))
            except (TypeError, ValueError):
                duration_days = 30

            freq_label = str(spec.get("frequency_label") or f"{units_per_day}/day")
            selected_sub_id = str(spec.get("selected_substitute_id") or "").strip()

            matches = self.search_engine.find_substitutes(
                query_or_medicine=med,
                strategy=strategy,
                limit=5,
            )

            chosen_match = None
            if selected_sub_id == "KEEP_ORIGINAL":
                chosen_med = med
            elif selected_sub_id:
                chosen_match = next(
                    (m for m in matches if m.substitute_medicine.id == selected_sub_id),
                    matches[0] if matches else None,
                )
                chosen_med = chosen_match.substitute_medicine if chosen_match else med
            elif matches:
                chosen_match = matches[0]
                chosen_med = chosen_match.substitute_medicine
            else:
                chosen_med = med

            total_units = units_per_day * duration_days
            orig_unit_cost = round(total_units * med.price_per_unit, 2)
            orig_packs = med.packs_for_units(total_units)
            orig_pack_cost = round(orig_packs * med.mrp, 2)

            chosen_unit_cost = round(total_units * chosen_med.price_per_unit, 2)
            chosen_packs = chosen_med.packs_for_units(total_units)
            chosen_pack_cost = round(chosen_packs * chosen_med.mrp, 2)

            unit_savings = round(orig_unit_cost - chosen_unit_cost, 2)
            unit_savings_pct = round((unit_savings / orig_unit_cost) * 100.0, 2) if orig_unit_cost > 0 else 0.0
            pack_savings = round(orig_pack_cost - chosen_pack_cost, 2)
            pack_savings_pct = round((pack_savings / orig_pack_cost) * 100.0, 2) if orig_pack_cost > 0 else 0.0

            warnings: List[str] = []
            if chosen_match:
                warnings.extend(chosen_match.safety_verdict.warnings)
            elif selected_sub_id != "KEEP_ORIGINAL" and not matches:
                warnings.append("No cheaper bioequivalent generic substitute available; dispensing prescribed brand.")
            if med.is_narrow_therapeutic_index and not any("Narrow Therapeutic Index" in w for w in warnings):
                warnings.append("Narrow Therapeutic Index (NTI) medicine — physician supervision recommended.")

            for w in warnings:
                entry = f"[{med.brand_name} -> {chosen_med.brand_name}] {w}"
                if entry not in all_alerts:
                    all_alerts.append(entry)

            salts_str = ", ".join(
                f"{s.name} {int(s.strength_value) if float(s.strength_value).is_integer() else s.strength_value}{s.strength_unit}"
                for s in med.salts
            )

            alternatives = [
                {
                    "id": m.substitute_medicine.id,
                    "brand_name": m.substitute_medicine.brand_name,
                    "manufacturer": m.substitute_medicine.manufacturer,
                    "regulatory_tier": m.substitute_medicine.regulatory_tier.value,
                    "pack_size": m.substitute_medicine.pack_size,
                    "mrp": m.substitute_medicine.mrp,
                    "price_per_unit": m.substitute_medicine.price_per_unit,
                    "percentage_savings": round(m.percentage_savings, 2),
                }
                for m in matches
            ]

            resolved_items.append({
                "medicine_id": med.id,
                "original_brand": med.brand_name,
                "original_manufacturer": med.manufacturer,
                "dosage_form": med.dosage_form.value,
                "release_type": med.release_type.value,
                "salts": salts_str,
                "is_nti": med.is_narrow_therapeutic_index or any("Narrow Therapeutic Index" in w for w in warnings),
                "frequency_label": freq_label,
                "units_per_day": units_per_day,
                "duration_days": duration_days,
                "total_units": total_units,
                "original_pack_size": med.pack_size,
                "original_mrp": med.mrp,
                "original_packs_needed": orig_packs,
                "original_unit_cost": orig_unit_cost,
                "original_pack_cost": orig_pack_cost,
                "selected_substitute_id": "KEEP_ORIGINAL" if chosen_med.id == med.id else chosen_med.id,
                "substitute_brand": chosen_med.brand_name,
                "substitute_manufacturer": chosen_med.manufacturer,
                "substitute_tier": chosen_med.regulatory_tier.value,
                "substitute_pack_size": chosen_med.pack_size,
                "substitute_mrp": chosen_med.mrp,
                "optimized_packs_needed": chosen_packs,
                "optimized_unit_cost": chosen_unit_cost,
                "optimized_pack_cost": chosen_pack_cost,
                "unit_savings": unit_savings,
                "unit_savings_pct": unit_savings_pct,
                "pack_savings": pack_savings,
                "pack_savings_pct": pack_savings_pct,
                "warnings": warnings,
                "alternatives": alternatives,
            })

            orig_unit_total += orig_unit_cost
            opt_unit_total += chosen_unit_cost
            orig_pack_total += orig_pack_cost
            opt_pack_total += chosen_pack_cost

        unit_savings_total = round(orig_unit_total - opt_unit_total, 2)
        unit_savings_pct_total = round((unit_savings_total / orig_unit_total) * 100.0, 2) if orig_unit_total > 0 else 0.0
        pack_savings_total = round(orig_pack_total - opt_pack_total, 2)
        pack_savings_pct_total = round((pack_savings_total / orig_pack_total) * 100.0, 2) if orig_pack_total > 0 else 0.0

        return {
            "items": resolved_items,
            "unresolved_items": unresolved_items,
            "summary": {
                "item_count": len(resolved_items),
                "original_unit_total": round(orig_unit_total, 2),
                "optimized_unit_total": round(opt_unit_total, 2),
                "unit_savings_total": unit_savings_total,
                "unit_savings_pct": unit_savings_pct_total,
                "original_pack_total": round(orig_pack_total, 2),
                "optimized_pack_total": round(opt_pack_total, 2),
                "pack_savings_total": pack_savings_total,
                "pack_savings_pct": pack_savings_pct_total,
                "annual_projected_unit_savings": round(unit_savings_total * 12.0, 2),
                "annual_projected_pack_savings": round(pack_savings_total * 12.0, 2),
                "safety_alerts": all_alerts,
            },
        }

    @classmethod
    def load_chronic_baskets(cls, file_path: str | Path, repository) -> List[Dict[str, Any]]:
        """Load and resolve predefined chronic disease baskets from JSON."""
        p = Path(file_path)
        with open(p, "r", encoding="utf-8") as f:
            baskets_data = json.load(f)

        resolved_baskets = []
        for b in baskets_data:
            basket_id = b["basket_id"]
            patient_profile = b["patient_profile"]
            items: List[PrescriptionItem] = []
            for item_raw in b.get("items", []):
                med = repository.get_by_brand_exact(item_raw["brand_name"])
                if med:
                    items.append(PrescriptionItem(
                        medicine=med,
                        units_per_day=item_raw.get("units_per_day", 1),
                        duration_days=item_raw.get("days", 30),
                    ))
            resolved_baskets.append({
                "basket_id": basket_id,
                "patient_profile": patient_profile,
                "description": b.get("description", ""),
                "items": items,
            })
        return resolved_baskets
