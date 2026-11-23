"""Interactive Command-Line Interface for EquiMed Generic Medicine Engine."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is in sys.path when executed directly
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from typing import List

from src.models import PrescriptionItem
from src.observer import AuditLogObserver, SafetyAlertObserver, SavingsTrackerObserver
from src.optimizer import PrescriptionOptimizer
from src.repository import MedicineRepository
from src.safety_engine import SafetyEngine
from src.search_engine import SearchEngine
from src.strategy import get_strategy


def get_default_repo() -> MedicineRepository:
    repo = MedicineRepository()
    catalog_path = Path(__file__).resolve().parent.parent / "data" / "medicine_catalog.json"
    repo.load_from_json(catalog_path)
    return repo


def print_banner() -> None:
    print("=" * 76)
    print("  💊 EquiMed-India: Generic Drug Substitution & Affordability Optimizer")
    print("  Indian Institute of Information Technology (IIIT), Lucknow - SE Project")
    print("=" * 76)


def cmd_search(args, repo: MedicineRepository, engine: SearchEngine) -> None:
    query = " ".join(args.query)
    results = repo.search_by_brand(query, limit=10)
    print(f"\n🔍 Search Results for '{query}': Found {len(results)} matches\n")
    if not results:
        print("  No medicines matching the query found in catalog.")
        return

    print(f"{'ID':<9} | {'Brand Name':<28} | {'Form':<9} | {'MRP (₹)':<8} | {'Price/Unit':<10} | {'Tier'}")
    print("-" * 76)
    for m in results:
        print(
            f"{m.id:<9} | {m.brand_name:<28} | {m.dosage_form.value:<9} | "
            f"₹{m.mrp:<7.2f} | ₹{m.price_per_unit:<9.2f} | {m.regulatory_tier.value}"
        )
    print("-" * 76)


def cmd_substitutes(args, repo: MedicineRepository, engine: SearchEngine) -> None:
    query = " ".join(args.brand)
    strategy = get_strategy(args.strategy)
    matches = engine.find_substitutes(query, strategy=strategy)

    if not matches:
        print(f"\n⚠️  No approved generic substitutes found for '{query}'.")
        print("    Ensure the exact brand name exists in the catalog or try 'search'.\n")
        return

    orig = matches[0].original_medicine
    print(f"\n🏷️  Prescribed Brand: {orig.brand_name} ({orig.manufacturer})")
    salts_str = ", ".join(f"{s.name} {s.strength_value}{s.strength_unit}" for s in orig.salts)
    print(f"   Active Salts: {salts_str}")
    print(f"   Original Price: ₹{orig.price_per_unit:.2f}/unit (MRP: ₹{orig.mrp:.2f} for pack of {orig.pack_size})")
    print(f"   Prioritization Strategy: {strategy.name}\n")

    print(f"{'#':<3} | {'Generic Substitute':<30} | {'Manufacturer / Tier':<22} | {'Price/Unit':<11} | {'Savings':<10}")
    print("=" * 85)

    for i, m in enumerate(matches, 1):
        sub = m.substitute_medicine
        tier_short = sub.regulatory_tier.value.replace("_GENERIC", "").replace("PMBJP_", "")
        print(
            f"{i:<3} | {sub.brand_name:<30} | {tier_short:<22} | "
            f"₹{sub.price_per_unit:<10.2f} | 🟢 {m.percentage_savings:.1f}% (₹{m.savings_per_unit:.2f})"
        )
        if m.safety_verdict.warnings:
            for w in m.safety_verdict.warnings:
                print(f"    ⚠️  [CLINICAL WARNING] {w}")

    print("=" * 85)
    best = matches[0]
    print(
        f"\n💡 Best Option: '{best.substitute_medicine.brand_name}' gives "
        f"{best.percentage_savings:.1f}% savings (₹{best.savings_per_unit:.2f} saved per dose)."
    )
    print("   DISCLAIMER: Consult a registered medical practitioner or pharmacist prior to drug substitution.\n")


def cmd_chronic_baskets(args, repo: MedicineRepository, engine: SearchEngine) -> None:
    baskets_path = Path(__file__).resolve().parent.parent / "data" / "chronic_baskets.json"
    baskets = PrescriptionOptimizer.load_chronic_baskets(baskets_path, repo)
    optimizer = PrescriptionOptimizer(engine)

    print("\n📊 Chronic Therapy Basket Affordability Simulation")
    print("   Benchmarking Real-World Indian Monthly Disease Prescriptions:\n")

    total_monthly_orig = 0.0
    total_monthly_generic = 0.0

    for b in baskets:
        res = optimizer.optimize_basket(
            basket_id=b["basket_id"],
            patient_profile=b["patient_profile"],
            items=b["items"],
        )
        total_monthly_orig += res.original_total_cost
        total_monthly_generic += res.optimized_total_cost

        print(f"┌─ [{res.basket_id}] {res.patient_profile}")
        print(f"│  Items: {len(res.items)} prescribed chronic medications")
        print(f"│  Original Branded Cost:   ₹{res.original_total_cost:>8.2f} / month")
        print(f"│  EquiMed Generic Cost:    ₹{res.optimized_total_cost:>8.2f} / month")
        print(f"│  Monthly Savings:         ₹{res.monthly_savings_amount:>8.2f}  ({res.monthly_savings_percentage:.1f}%)")
        print(f"│  Annual Projected Savings: ₹{res.annual_projected_savings:>8.2f} / year")
        if res.safety_alerts:
            for alert in res.safety_alerts:
                print(f"│  ⚠️  {alert}")
        print("└" + "─" * 70 + "\n")

    overall_savings = total_monthly_orig - total_monthly_generic
    overall_pct = (overall_savings / total_monthly_orig * 100.0) if total_monthly_orig > 0 else 0.0

    print("=" * 76)
    print(f"  TOTAL MONTHLY EXPENDITURE ACROSS ALL BASKETS:")
    print(f"    Original Branded Cost: ₹{total_monthly_orig:.2f}")
    print(f"    Generic Optimized:    ₹{total_monthly_generic:.2f}")
    print(f"    AVERAGE SAVINGS:      ₹{overall_savings:.2f} ({overall_pct:.1f}% reduction)")
    print(f"    ANNUAL SAVINGS:       ₹{overall_savings * 12:.2f}")
    print("=" * 76 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="EquiMed: Deterministic Generic Drug Substitution & Affordability Optimizer"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Search command
    p_search = subparsers.add_parser("search", help="Search catalog by brand name")
    p_search.add_argument("query", nargs="+", help="Brand query to search")

    # Substitutes command
    p_sub = subparsers.add_parser("substitutes", help="Find generic substitutes for a brand")
    p_sub.add_argument("brand", nargs="+", help="Brand name of prescribed medicine")
    p_sub.add_argument(
        "--strategy",
        choices=["max_savings", "jan_aushadhi", "balanced"],
        default="max_savings",
        help="Ranking strategy algorithm",
    )

    # Chronic baskets benchmark command
    subparsers.add_parser("chronic-baskets", help="Run chronic prescription baskets benchmark")

    # Parse arguments
    args = parser.parse_args()

    repo = get_default_repo()
    audit_observer = AuditLogObserver()
    savings_observer = SavingsTrackerObserver()
    safety_observer = SafetyAlertObserver()

    engine = SearchEngine(repo)
    engine.attach(audit_observer)
    engine.attach(savings_observer)
    engine.attach(safety_observer)

    print_banner()

    if args.command == "search":
        cmd_search(args, repo, engine)
    elif args.command == "substitutes":
        cmd_substitutes(args, repo, engine)
    elif args.command == "chronic-baskets":
        cmd_chronic_baskets(args, repo, engine)
    else:
        # Default behavior when no subcommand: show chronic baskets demo
        print("\n[Default Run] Executing chronic therapy simulation & sample lookups:\n")
        cmd_chronic_baskets(args, repo, engine)
        print("💡 Tip: Run 'python3 -m src.cli substitutes \"Telma 40\"' to search specific brands.")


if __name__ == "__main__":
    main()
