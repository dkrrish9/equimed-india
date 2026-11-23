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
