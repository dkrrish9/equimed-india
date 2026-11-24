"""Zero-dependency embedded HTTP server & Interactive Web UI for EquiMed."""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Ensure project root is in sys.path when executed directly
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from typing import Any, Dict, List

from src.models import DosageForm, Medicine, PrescriptionItem, RegulatoryTier, ReleaseType
from src.observer import AuditLogObserver, SafetyAlertObserver, SavingsTrackerObserver
from src.optimizer import PrescriptionOptimizer
from src.repository import load_default_repository
from src.safety_engine import SafetyEngine
from src.search_engine import SearchEngine
from src.strategy import (
    JanAushadhiFirstStrategy,
    ReputationBalancedStrategy,
    get_strategy,
    is_major_pharma,
)

# Global state instances
_baskets_path = Path(__file__).resolve().parent.parent / "data" / "chronic_baskets.json"
_repo = load_default_repository()

_audit = AuditLogObserver()
_savings = SavingsTrackerObserver()
_safety_alerts = SafetyAlertObserver()

_engine = SearchEngine(_repo)
_engine.attach(_audit)
_engine.attach(_savings)
_engine.attach(_safety_alerts)

_optimizer = PrescriptionOptimizer(_engine)

_FORM_DISPLAY_META: Dict[DosageForm, Dict[str, str]] = {
    DosageForm.TABLET: {"label": "Tablet", "unit_label": "tablet"},
    DosageForm.CAPSULE: {"label": "Capsule", "unit_label": "capsule"},
    DosageForm.SYRUP: {"label": "Syrup / Liquid", "unit_label": "bottle"},
    DosageForm.INHALER: {"label": "Inhaler / Spray", "unit_label": "inhaler / spray"},
    DosageForm.INJECTION: {"label": "Injection", "unit_label": "injection / vial"},
    DosageForm.DROPS: {"label": "Drops", "unit_label": "drop bottle"},
    DosageForm.OINTMENT: {"label": "Cream / Ointment", "unit_label": "tube / pack"},
}

_RELEASE_DISPLAY_LABELS: Dict[ReleaseType, str] = {
    ReleaseType.IMMEDIATE_RELEASE: "Normal Release",
    ReleaseType.SUSTAINED_RELEASE: "Slow Release (SR)",
    ReleaseType.EXTENDED_RELEASE: "Extended Release (ER/XR)",
    ReleaseType.CONTROLLED_RELEASE: "Controlled Release (CR)",
    ReleaseType.MODIFIED_RELEASE: "Modified Release (MR)",
    ReleaseType.ENTERIC_COATED: "Stomach-Safe Coating (EC/DR)",
}

_TIER_DISPLAY_META: Dict[RegulatoryTier, Dict[str, str]] = {
    RegulatoryTier.PMBJP_JAN_AUSHADHI: {
        "label": "Govt. Jan Aushadhi",
        "badge_class": "badge-pmbjp",
    },
    RegulatoryTier.WHO_GMP_GENERIC: {
        "label": "WHO-GMP Certified",
        "badge_class": "badge-who",
    },
    RegulatoryTier.CDSCO_APPROVED_GENERIC: {
        "label": "CDSCO Approved",
        "badge_class": "badge-cdsco",
    },
    RegulatoryTier.BRANDED_GENERIC: {
        "label": "Retail Generic Brand",
        "badge_class": "badge-branded",
    },
    RegulatoryTier.BRANDED_INNOVATOR: {
        "label": "Original Brand",
        "badge_class": "badge-branded",
    },
}

_PRESET_CANDIDATES: List[tuple[str, str]] = [
    ("Telma 40", "Telma 40"),
    ("Glycomet-GP 2", "Glycomet-GP 2"),
    ("Augmentin 625 Duo", "Augmentin 625"),
    ("Foracort 200 Inhaler (120 MDI)", "Foracort 200 Inhaler"),
    ("Lantus SoloSTAR Pen (3ml)", "Lantus Injection"),
    ("Calpol 250 Pediatric Suspension (60ml)", "Calpol 250 Syrup"),
    ("Vigamox 0.5% Eye Drops (5ml)", "Vigamox Drops"),
    ("Thyronorm 50", "Thyronorm 50 (Sensitive Dose)"),
]

_LOOKUP_STRATEGIES: List[Dict[str, str]] = [
    {"id": "max_savings", "label": "Lowest Price First"},
    {"id": "jan_aushadhi", "label": "Govt. Jan Aushadhi Stores First"},
    {"id": "balanced", "label": "Best Balance (Price + Quality)"},
]


def _format_pack_label(med: Medicine) -> str:
    """Return human-readable strip/bottle/container description."""
    if med.pack_size_label:
        return med.pack_size_label
    meta = _FORM_DISPLAY_META.get(med.dosage_form, {"label": "Unit", "unit_label": "unit"})
    unit_word = meta["unit_label"]
    if med.dosage_form in SafetyEngine.PACK_ONLY_FORMS:
        return f"1 {unit_word}"
    plural = unit_word if med.pack_size == 1 or unit_word.endswith("s") else f"{unit_word}s"
    return f"Pack of {med.pack_size} {plural}"


def _build_ui_config() -> Dict[str, Any]:
    """Build Section 1 UI configuration from live repository & domain constants."""
    verified_presets: List[Dict[str, Any]] = []
    for brand_name, short_label in _PRESET_CANDIDATES:
        med = _repo.get_by_brand_exact(brand_name)
        if med:
            verified_presets.append({
                "brand_name": med.brand_name,
                "label": short_label,
                "is_nti": med.is_narrow_therapeutic_index,
            })

    default_query = verified_presets[0]["brand_name"] if verified_presets else ""
    if not default_query:
        sample = _repo.search_by_brand("a", limit=1)
        default_query = sample[0].brand_name if sample else ""

    return {
        "presets": verified_presets,
        "default_query": default_query,
        "strategies": _LOOKUP_STRATEGIES,
        "pack_only_forms": sorted(f.value for f in SafetyEngine.PACK_ONLY_FORMS),
        "regulatory_tiers": {k.value: v for k, v in _TIER_DISPLAY_META.items()},
        "dosage_forms": {k.value: v for k, v in _FORM_DISPLAY_META.items()},
        "release_types": {k.value: v for k, v in _RELEASE_DISPLAY_LABELS.items()},
        "regimen_options": {
            "frequencies": [
                {"value": 1, "label": "Once a day (1-0-0)", "short": "1-0-0 (OD)", "cart_short": "1/day"},
                {"value": 2, "label": "Twice a day (1-0-1)", "short": "1-0-1 (BD)", "cart_short": "2/day"},
                {"value": 3, "label": "3 times a day (1-1-1)", "short": "1-1-1 (TDS)", "cart_short": "3/day"},
                {"value": 4, "label": "4 times a day (1-1-1-1)", "short": "1-1-1-1 (QID)", "cart_short": "4/day"},
            ],
            "durations": [
                {"value": 5, "label": "5 days"},
                {"value": 7, "label": "7 days (1 week)"},
                {"value": 10, "label": "10 days"},
                {"value": 15, "label": "15 days"},
                {"value": 30, "label": "30 days (1 month)"},
                {"value": 90, "label": "90 days (3 months)"},
            ],
            "default_duration": 30,
            "duration_min": 1,
            "duration_max": 365,
            "pack_min": 1,
            "pack_max": 24,
            "pack_default": 1,
        },
        "cart_config": {
            "default_strategy": "jan_aushadhi",
            "default_billing_mode": "pack",
            "keep_original_sentinel": "KEEP_ORIGINAL",
            "billing_modes": [
                {
                    "id": "pack",
                    "label": "Full Strips / Bottles You Buy",
                    "short_label": "Full Strips / Bottles",
                },
                {
                    "id": "unit",
                    "label": "Exact Tablet / Dose Cost",
                    "short_label": "Exact Dose Cost",
                },
            ],
        },
        "search_config": {
            "min_query_chars": 2,
            "autocomplete_limit": 15,
            "debounce_ms": 180,
            "currency_symbol": "₹",
        },
    }


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>EquiMed-India | Generic Drug Substitution & Formulary Optimizer</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #f8fafc;
      --surface: #ffffff;
      --surface-subtle: #f1f5f9;
      --border: #e2e8f0;
      --border-dark: #cbd5e1;
      --text-main: #0f172a;
      --text-muted: #64748b;
      --text-subtle: #94a3b8;
      
      --brand-mark-bg: #0f172a;
      --brand-mark-fg: #ffffff;

      --btn-primary-bg: #0f172a;
      --btn-primary-fg: #ffffff;
      --btn-primary-border: #0f172a;
      --btn-primary-hover: #1e293b;
      
      --focus-ring: #0f172a;
      --table-hover: #fafbfc;
      
      --accent: #0f766e;
      --accent-hover: #115e59;
      --accent-surface: #f0fdfa;
      --accent-border: #ccfbf1;
      
      --success: #15803d;
      --success-bg: #f0fdf4;
      --success-border: #bbf7d0;
      
      --danger: #b91c1c;
      --danger-bg: #fef2f2;
      --danger-border: #fecaca;
      
      --warn: #b45309;
      --warn-bg: #fffbeb;
      --warn-border: #fde68a;
      
      --badge-pmbjp-bg: #ecfdf5;
      --badge-pmbjp-text: #065f46;
      --badge-pmbjp-border: #a7f3d0;
      
      --badge-who-bg: #eff6ff;
      --badge-who-text: #1e40af;
      --badge-who-border: #bfdbfe;
      
      --badge-savings-bg: #f0fdf4;
      --badge-savings-text: #166534;
      --badge-savings-border: #bbf7d0;
      
      --badge-verified-bg: #f8fafc;
      --badge-verified-text: #334155;
      --badge-verified-border: #cbd5e1;

      --stat-blue: #0284c7;

      --radius: 8px;
      --radius-sm: 6px;
    }

    [data-theme="dark"] {
      --bg: #090d16;
      --surface: #0f172a;
      --surface-subtle: #172033;
      --border: #1e293b;
      --border-dark: #334155;
      --text-main: #f1f5f9;
      --text-muted: #94a3b8;
      --text-subtle: #64748b;
      
      --brand-mark-bg: #f1f5f9;
      --brand-mark-fg: #090d16;

      --btn-primary-bg: #f8fafc;
      --btn-primary-fg: #0f172a;
      --btn-primary-border: #f8fafc;
      --btn-primary-hover: #e2e8f0;
      
      --focus-ring: #38bdf8;
      --table-hover: #131d30;
      
      --accent: #14b8a6;
      --accent-hover: #2dd4bf;
      --accent-surface: #042f2e;
      --accent-border: #115e59;
      
      --success: #10b981;
      --success-bg: rgba(6, 78, 59, 0.25);
      --success-border: #065f46;
      
      --danger: #ef4444;
      --danger-bg: rgba(127, 29, 29, 0.2);
      --danger-border: #991b1b;
      
      --warn: #f59e0b;
      --warn-bg: rgba(120, 53, 15, 0.2);
      --warn-border: #92400e;
      
      --badge-pmbjp-bg: rgba(6, 78, 59, 0.3);
      --badge-pmbjp-text: #34d399;
      --badge-pmbjp-border: #065f46;
      
      --badge-who-bg: rgba(30, 58, 138, 0.3);
      --badge-who-text: #60a5fa;
      --badge-who-border: #1d4ed8;
      
      --badge-savings-bg: rgba(6, 78, 59, 0.3);
      --badge-savings-text: #34d399;
      --badge-savings-border: #065f46;
      
      --badge-verified-bg: #1e293b;
      --badge-verified-text: #94a3b8;
      --badge-verified-border: #334155;

      --stat-blue: #38bdf8;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg);
      color: var(--text-main);
      font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      font-size: 14px;
      line-height: 1.5;
      -webkit-font-smoothing: antialiased;
    }

    .tnum {
      font-variant-numeric: tabular-nums;
      font-feature-settings: "tnum";
    }

    .mono {
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px;
    }

    /* Navigation Bar */
    .navbar {
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 0 32px;
      height: 64px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .brand-group {
      display: flex;
      align-items: center;
      gap: 16px;
    }
    .brand-mark {
      width: 32px;
      height: 32px;
      background: var(--brand-mark-bg);
      color: var(--brand-mark-fg);
      border-radius: 6px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      font-size: 14px;
      letter-spacing: -0.5px;
    }
    .brand-text h1 {
      font-size: 16px;
      font-weight: 700;
      letter-spacing: -0.3px;
      color: var(--text-main);
      line-height: 1.2;
    }
    .brand-text span {
      font-size: 11px;
      color: var(--text-muted);
      display: block;
    }
    .nav-meta {
      display: flex;
      align-items: center;
      gap: 20px;
    }
    .meta-stat {
      font-size: 12px;
      color: var(--text-muted);
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .status-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: var(--success);
    }

    /* Layout Shell */
    .app-shell {
      max-width: 1280px;
      margin: 0 auto;
      padding: 32px;
      display: flex;
      flex-direction: column;
      gap: 28px;
    }

    /* View Switcher / Sub-header */
    .view-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      border-bottom: 1px solid var(--border);
      padding-bottom: 16px;
    }
    .section-title {
      font-size: 18px;
      font-weight: 700;
      color: var(--text-main);
      letter-spacing: -0.3px;
    }
    .section-desc {
      font-size: 13px;
      color: var(--text-muted);
      margin-top: 4px;
    }
    .tabs-group {
      display: flex;
      background: var(--surface-subtle);
      padding: 4px;
      border-radius: var(--radius);
      border: 1px solid var(--border);
      gap: 4px;
    }
    .tab-btn {
      background: transparent;
      border: none;
      padding: 6px 14px;
      font-size: 13px;
      font-weight: 500;
      color: var(--text-muted);
      border-radius: 4px;
      cursor: pointer;
      transition: all 0.15s ease;
    }
    .tab-btn.active {
      background: var(--surface);
      color: var(--text-main);
      box-shadow: 0 1px 2px rgba(0,0,0,0.06);
    }

    /* Card Panels */
    .panel {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 24px;
      box-shadow: 0 1px 2px rgba(0,0,0,0.02);
    }

    /* Clinical Search Bar */
    .search-row {
      display: grid;
      grid-template-columns: 1fr 240px 140px;
      gap: 12px;
      margin-top: 16px;
    }
    .input-wrapper {
      position: relative;
      display: flex;
      align-items: center;
    }
    .input-icon {
      position: absolute;
      left: 14px;
      color: var(--text-subtle);
      pointer-events: none;
    }
    input[type="text"] {
      width: 100%;
      height: 42px;
      padding: 0 14px 0 40px;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      font-size: 14px;
      color: var(--text-main);
      outline: none;
      transition: border-color 0.15s;
    }
    input[type="text"]:focus {
      border-color: var(--focus-ring);
    }
    select {
      height: 42px;
      padding: 0 14px;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      font-size: 13px;
      color: var(--text-main);
      outline: none;
      cursor: pointer;
    }
    select:focus { border-color: var(--focus-ring); }
    .btn-primary {
      height: 42px;
      padding: 0 20px;
      background: var(--btn-primary-bg);
      color: var(--btn-primary-fg);
      border: 1px solid var(--btn-primary-border);
      border-radius: var(--radius-sm);
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.15s, border-color 0.15s;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
    }
    .btn-primary:hover { background: var(--btn-primary-hover); }

    .btn-secondary {
      height: 42px;
      padding: 0 16px;
      background: var(--surface-subtle);
      color: var(--text-main);
      border: 1px solid var(--border-dark);
      border-radius: var(--radius-sm);
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.15s, border-color 0.15s;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      font-family: inherit;
      white-space: nowrap;
    }
    .btn-secondary:hover { background: var(--border); }

    .btn-sm {
      height: 32px;
      padding: 0 12px;
      font-size: 12px;
      border-radius: 4px;
    }

    .cart-badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 20px;
      height: 20px;
      padding: 0 6px;
      border-radius: 999px;
      background: var(--accent);
      color: #ffffff;
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      font-weight: 600;
    }

    .add-cart-bar {
      margin-top: 14px;
      padding-top: 14px;
      border-top: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
    }
    .regimen-controls {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .regimen-controls label {
      font-size: 12px;
      color: var(--text-muted);
      font-weight: 500;
    }
    .regimen-controls select, .regimen-controls input[type="number"] {
      height: 34px;
      padding: 0 10px;
      font-size: 12px;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 4px;
      color: var(--text-main);
    }
    .inline-number {
      width: 64px;
      height: 32px;
      padding: 0 8px;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 4px;
      color: var(--text-main);
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px;
      text-align: center;
    }
    .inline-select {
      height: 32px;
      padding: 0 8px;
      font-size: 12px;
      max-width: 260px;
    }
    .icon-btn {
      width: 30px;
      height: 30px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      background: transparent;
      border: 1px solid var(--border);
      border-radius: 4px;
      color: var(--text-muted);
      cursor: pointer;
    }
    .icon-btn:hover {
      border-color: var(--danger);
      color: var(--danger);
      background: var(--danger-bg);
    }
    .cart-empty {
      padding: 28px 20px;
      text-align: center;
      background: var(--surface-subtle);
      border: 1px dashed var(--border-dark);
      border-radius: var(--radius-sm);
      margin-top: 16px;
      color: var(--text-muted);
      font-size: 13px;
    }
    .toast-notice {
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: var(--btn-primary-bg);
      color: var(--btn-primary-fg);
      border: 1px solid var(--border-dark);
      padding: 10px 16px;
      border-radius: var(--radius-sm);
      font-size: 13px;
      font-weight: 500;
      z-index: 1000;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      display: none;
    }

    /* Theme Switcher Toggle */
    .theme-toggle {
      background: var(--surface-subtle);
      border: 1px solid var(--border);
      color: var(--text-muted);
      padding: 6px 12px;
      border-radius: var(--radius-sm);
      font-size: 12px;
      font-weight: 500;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s ease;
      font-family: inherit;
      user-select: none;
    }
    .theme-toggle:hover {
      background: var(--border);
      color: var(--text-main);
    }
    .theme-toggle svg {
      flex-shrink: 0;
    }

    /* Quick Clinical Preset Chips */
    .presets-row {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 14px;
    }
    .presets-label {
      font-size: 12px;
      font-weight: 500;
      color: var(--text-muted);
      margin-right: 4px;
    }
    .chip {
      background: var(--surface-subtle);
      border: 1px solid var(--border);
      padding: 4px 10px;
      border-radius: 4px;
      font-size: 12px;
      color: var(--text-main);
      cursor: pointer;
      transition: all 0.12s ease;
      font-family: 'JetBrains Mono', monospace;
    }
    .chip:hover {
      background: var(--border);
      border-color: var(--border-dark);
    }

    /* Clinical Medicine Profile Banner */
    .med-profile-card {
      background: var(--surface-subtle);
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      padding: 16px 20px;
      margin-top: 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .med-meta h3 {
      font-size: 16px;
      font-weight: 700;
      color: var(--text-main);
      letter-spacing: -0.2px;
    }
    .med-salts {
      font-size: 12px;
      color: var(--text-muted);
      font-family: 'JetBrains Mono', monospace;
      margin-top: 3px;
    }
    .med-price-badge {
      text-align: right;
    }
    .price-sub {
      font-size: 11px;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .price-num {
      font-size: 20px;
      font-weight: 700;
      color: var(--danger);
      font-variant-numeric: tabular-nums;
    }

    /* Ledger Data Table */
    .table-container {
      margin-top: 16px;
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      overflow: hidden;
      background: var(--surface);
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
      text-align: left;
    }
    thead {
      background: var(--surface-subtle);
      border-bottom: 1px solid var(--border);
    }
    th {
      padding: 12px 16px;
      font-weight: 600;
      font-size: 12px;
      color: var(--text-muted);
      letter-spacing: 0.2px;
    }
    td {
      padding: 14px 16px;
      border-bottom: 1px solid var(--border);
      vertical-align: middle;
    }
    tr:last-child td { border-bottom: none; }
    tbody tr:hover { background-color: var(--table-hover); }

    /* Badges */
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 3px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 600;
      line-height: 1.3;
    }
    .badge-pmbjp {
      background: var(--badge-pmbjp-bg);
      color: var(--badge-pmbjp-text);
      border: 1px solid var(--badge-pmbjp-border);
    }
    .badge-who {
      background: var(--badge-who-bg);
      color: var(--badge-who-text);
      border: 1px solid var(--badge-who-border);
    }
    .badge-savings {
      background: var(--badge-savings-bg);
      color: var(--badge-savings-text);
      border: 1px solid var(--badge-savings-border);
      font-family: 'JetBrains Mono', monospace;
      font-weight: 700;
    }
    .badge-verified {
      background: var(--badge-verified-bg);
      color: var(--badge-verified-text);
      border: 1px solid var(--badge-verified-border);
      font-size: 11px;
    }
    .badge-cdsco {
      background: var(--accent-surface);
      color: var(--accent);
      border: 1px solid var(--accent-border);
    }
    .badge-branded {
      background: var(--surface-subtle);
      color: var(--text-muted);
      border: 1px solid var(--border-dark);
    }
    .badge-nti {
      background: var(--warn-bg);
      color: var(--warn);
      border: 1px solid var(--warn-border);
    }
    .badge-discontinued {
      background: var(--danger-bg);
      color: var(--danger);
      border: 1px solid var(--danger-border);
    }

    /* Clinical Alert Box */
    .alert-banner {
      background: var(--warn-bg);
      border: 1px solid var(--warn-border);
      border-left: 3px solid var(--warn);
      padding: 12px 16px;
      border-radius: 4px;
      margin-top: 8px;
      font-size: 12px;
      color: var(--warn);
      display: flex;
      align-items: flex-start;
      gap: 10px;
      line-height: 1.4;
    }

    /* Plain-English Results Section Header */
    .results-explainer {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 20px;
      padding: 12px 16px;
      background: var(--accent-surface);
      border: 1px solid var(--accent-border);
      border-radius: var(--radius-sm);
    }
    .results-explainer-title {
      font-size: 14px;
      font-weight: 700;
      color: var(--text-main);
    }
    .results-explainer-sub {
      font-size: 12px;
      color: var(--text-muted);
      margin-top: 2px;
    }

    /* Simulation Metrics Bar */
    .metrics-row {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px;
      margin-bottom: 20px;
    }
    .stat-box {
      background: var(--surface-subtle);
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      padding: 16px 20px;
    }
    .stat-label {
      font-size: 11px;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .stat-figure {
      font-size: 24px;
      font-weight: 700;
      color: var(--text-main);
      margin-top: 4px;
      letter-spacing: -0.5px;
    }
    .stat-figure.green { color: var(--success); }
    .stat-figure.red { color: var(--danger); }
    .stat-figure.blue { color: var(--stat-blue); }

    /* Footer */
    footer {
      border-top: 1px solid var(--border);
      padding: 24px 32px;
      color: var(--text-subtle);
      font-size: 12px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      max-width: 1280px;
      margin: 0 auto;
    }

    @media (max-width: 900px) {
      .search-row { grid-template-columns: 1fr; }
      .metrics-row { grid-template-columns: 1fr 1fr; }
      .app-shell { padding: 16px; }
      .navbar { padding: 0 16px; }
    }

    @media print {
      body { background: #ffffff !important; color: #000000 !important; }
      .navbar, #lookupPanel, footer, .no-print, .toast-notice { display: none !important; }
      #cartPanel { border: none !important; box-shadow: none !important; padding: 0 !important; }
      .panel, .stat-box, .table-container { background: #ffffff !important; border-color: #cbd5e1 !important; color: #000000 !important; }
      .print-only-header { display: block !important; margin-bottom: 16px; border-bottom: 2px solid #0f172a; padding-bottom: 10px; }
    }
    .print-only-header { display: none; }
  </style>
  <script>
    (function() {
      try {
        var t = localStorage.getItem('equimed-theme') || 'light';
        document.documentElement.setAttribute('data-theme', t);
      } catch(e) {}
    })();
  </script>
</head>
<body>

  <!-- Top Institutional Bar -->
  <header class="navbar">
    <div class="brand-group">
      <div class="brand-mark">EQ</div>
      <div class="brand-text">
        <h1>EquiMed-India</h1>
        <span>Find Cheaper, Safe Same-Salt Medicines in India</span>
      </div>
    </div>
    <div class="nav-meta">
      <div class="meta-stat">
        <span class="status-dot"></span>
        <span id="navCatalogCount" class="mono">{{CATALOG_COUNT}} MEDICINES AVAILABLE</span>
      </div>
      <div class="meta-stat">
        <span class="mono">CDSCO SAFETY RULES</span>
      </div>
      <button class="theme-toggle" onclick="scrollToCart()" aria-label="Jump to My Medicine Bill">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="9" cy="21" r="1"></circle><circle cx="20" cy="21" r="1"></circle>
          <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"></path>
        </svg>
        <span>My Medicine Bill</span>
        <span id="navCartCount" class="cart-badge">0</span>
      </button>
      <button id="themeToggleBtn" class="theme-toggle" onclick="toggleTheme()" aria-label="Toggle display theme">
        <svg id="themeIcon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
        </svg>
        <span id="themeLabel">Dark Mode</span>
      </button>
    </div>
  </header>

  <main class="app-shell">

    <!-- Section 1: Search Any Medicine & Find Cheaper Options -->
    <section id="lookupPanel" class="panel">
      <div class="view-header">
        <div>
          <h2 class="section-title">Search Any Medicine & Find Cheaper Options</h2>
          <p class="section-desc">Enter a medicine name from your prescription to see lower-cost alternatives with the exact same ingredient inside.</p>
        </div>
      </div>

      <!-- Quick Presets (populated dynamically from /api/ui-config) -->
      <div class="presets-row" id="presetsRow">
        <span class="presets-label">Try Common Medicines:</span>
      </div>

      <!-- Search Inputs -->
      <form class="search-row" onsubmit="event.preventDefault();">
        <div class="input-wrapper">
          <svg class="input-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
          <input type="text" id="brandInput" list="medSuggestions" autocomplete="off" placeholder="Type medicine name or salt (e.g., Dolo 650, Telma 40, Paracetamol)..." value="">
          <datalist id="medSuggestions"></datalist>
        </div>
        <select id="strategySelect" aria-label="Sort Alternatives By"></select>
        <button type="button" id="findAlternativesBtn" class="btn-primary" onclick="performSearch()">
          <span>Find Alternatives</span>
        </button>
      </form>

      <!-- Results Slot -->
      <div id="searchResults"></div>
    </section>

    <!-- Section 2: My Medicine Bill & Total Savings -->
    <section id="cartPanel" class="panel">
      <div class="print-only-header">
        <h2>EquiMed-India · Medicine List for Your Chemist</h2>
        <p style="font-size: 12px; color: #475569; margin-top: 4px;">Every alternative below has the exact same active ingredient and strength. Show the salt names to your PMBJP Jan Aushadhi Kendra or licensed pharmacist.</p>
      </div>
      <div class="view-header no-print">
        <div>
          <h2 class="section-title">My Medicine Bill & Total Savings</h2>
          <p class="section-desc">Compare the total cost of your doctor's brands vs. cheaper alternatives, and print a list for the chemist.</p>
        </div>
        <div class="regimen-controls">
          <select id="cartStrategySelect" aria-label="Sort Cart Alternatives By" onchange="recalculateCart()"></select>
          <select id="cartBillingMode" aria-label="How to Calculate Bill" onchange="renderCartFromCache()"></select>
          <button class="btn-secondary btn-sm" onclick="window.print()">Print List for Chemist</button>
          <button class="btn-secondary btn-sm" onclick="clearCart()">Clear All</button>
        </div>
      </div>

      <div id="cartResults"></div>
    </section>

  </main>

  <div id="toastNotice" class="toast-notice"></div>

  <footer>
    <div>EquiMed-India · Indian Institute of Information Technology, Lucknow</div>
  </footer>

  <script>
    let PACK_ONLY_FORMS = new Set();
    let uiConfig = {
      presets: [],
      default_query: '',
      strategies: [
        { id: 'max_savings', label: 'Lowest Price First' },
        { id: 'jan_aushadhi', label: 'Govt. Jan Aushadhi Stores First' },
        { id: 'balanced', label: 'Best Balance (Price + Quality)' },
      ],
      pack_only_forms: ['SYRUP', 'INHALER', 'INJECTION', 'DROPS', 'OINTMENT'],
      regulatory_tiers: {},
      dosage_forms: {},
      release_types: {},
      regimen_options: {
        frequencies: [
          { value: 1, label: 'Once a day (1-0-0)', short: '1-0-0 (OD)', cart_short: '1/day' },
          { value: 2, label: 'Twice a day (1-0-1)', short: '1-0-1 (BD)', cart_short: '2/day' },
          { value: 3, label: '3 times a day (1-1-1)', short: '1-1-1 (TDS)', cart_short: '3/day' },
          { value: 4, label: '4 times a day (1-1-1-1)', short: '1-1-1-1 (QID)', cart_short: '4/day' },
        ],
        durations: [
          { value: 5, label: '5 days' },
          { value: 7, label: '7 days (1 week)' },
          { value: 10, label: '10 days' },
          { value: 15, label: '15 days' },
          { value: 30, label: '30 days (1 month)' },
          { value: 90, label: '90 days (3 months)' },
        ],
        default_duration: 30,
        duration_min: 1,
        duration_max: 365,
        pack_min: 1,
        pack_max: 24,
        pack_default: 1,
      },
      cart_config: {
        default_strategy: 'jan_aushadhi',
        default_billing_mode: 'pack',
        keep_original_sentinel: 'KEEP_ORIGINAL',
        billing_modes: [
          { id: 'pack', label: 'Full Strips / Bottles You Buy', short_label: 'Full Strips / Bottles' },
          { id: 'unit', label: 'Exact Tablet / Dose Cost', short_label: 'Exact Dose Cost' },
        ],
      },
      search_config: {
        min_query_chars: 2,
        autocomplete_limit: 15,
        debounce_ms: 180,
        currency_symbol: '₹',
      },
    };
    PACK_ONLY_FORMS = new Set(uiConfig.pack_only_forms);
    let prescriptionCart = [];
    let lastOptimizedCart = null;
    let lastLookupData = null;

    function escapeHtml(val) {
      return String(val ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    function titleCaseLabel(str) {
      return String(str || 'unit').replace(/\\b\\w/g, c => c.toUpperCase());
    }

    function showToast(msg) {
      const el = document.getElementById('toastNotice');
      if (!el) return;
      el.textContent = msg;
      el.style.display = 'block';
      clearTimeout(window._toastTimer);
      window._toastTimer = setTimeout(() => { el.style.display = 'none'; }, 2800);
    }

    function scrollToCart() {
      const panel = document.getElementById('cartPanel');
      if (panel) panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function saveCartState() {
      try { localStorage.setItem('equimed-cart', JSON.stringify(prescriptionCart)); } catch(e) {}
      const badge = document.getElementById('navCartCount');
      if (badge) badge.textContent = String(prescriptionCart.length);
    }

    function loadCartState() {
      try {
        const raw = localStorage.getItem('equimed-cart');
        if (raw) {
          const parsed = JSON.parse(raw);
          if (Array.isArray(parsed)) prescriptionCart = parsed;
        }
      } catch(e) { prescriptionCart = []; }
      saveCartState();
    }

    function formatTierBadge(tier) {
      const meta = uiConfig.regulatory_tiers && uiConfig.regulatory_tiers[tier];
      if (meta) {
        return `<span class="badge ${escapeHtml(meta.badge_class)}">${escapeHtml(meta.label)}</span>`;
      }
      if (tier === 'PMBJP_JAN_AUSHADHI') return '<span class="badge badge-pmbjp">Govt. Jan Aushadhi</span>';
      if (tier === 'WHO_GMP_GENERIC') return '<span class="badge badge-who">WHO-GMP Certified</span>';
      if (tier === 'CDSCO_APPROVED_GENERIC') return '<span class="badge badge-cdsco">CDSCO Approved</span>';
      if (tier === 'BRANDED_GENERIC') return '<span class="badge badge-branded">Retail Generic Brand</span>';
      return '<span class="badge badge-branded">Original Brand</span>';
    }

    function freqLabelFromUnits(units) {
      const freqs = (uiConfig.regimen_options && uiConfig.regimen_options.frequencies) || [];
      const found = freqs.find(f => Number(f.value) === Number(units));
      if (found) return found.short || found.label;
      return `${units}/day`;
    }

    async function loadUiConfig() {
      try {
        const res = await fetch('/api/ui-config');
        const cfg = await res.json();
        if (cfg && typeof cfg === 'object') {
          uiConfig = { ...uiConfig, ...cfg };
          if (Array.isArray(uiConfig.pack_only_forms)) {
            PACK_ONLY_FORMS = new Set(uiConfig.pack_only_forms);
          }
        }
      } catch (e) {
        console.error('Failed to load /api/ui-config', e);
      }

      const presetsRow = document.getElementById('presetsRow');
      if (presetsRow && Array.isArray(uiConfig.presets)) {
        presetsRow.innerHTML = '<span class="presets-label">Try Common Medicines:</span>';
        uiConfig.presets.forEach(p => {
          const chip = document.createElement('span');
          chip.className = 'chip';
          chip.textContent = p.label;
          chip.onclick = () => quickSearch(p.brand_name);
          presetsRow.appendChild(chip);
        });
      }

      const stratSel = document.getElementById('strategySelect');
      if (stratSel && Array.isArray(uiConfig.strategies)) {
        const prev = stratSel.value;
        stratSel.innerHTML = '';
        uiConfig.strategies.forEach(s => {
          const opt = document.createElement('option');
          opt.value = s.id;
          opt.textContent = s.label;
          stratSel.appendChild(opt);
        });
        if (prev && uiConfig.strategies.some(s => s.id === prev)) {
          stratSel.value = prev;
        }
      }

      const bInput = document.getElementById('brandInput');
      if (bInput && !bInput.value.trim() && uiConfig.default_query) {
        bInput.value = uiConfig.default_query;
      }

      const cartStratSel = document.getElementById('cartStrategySelect');
      const cartCfg = uiConfig.cart_config || {};
      if (cartStratSel && Array.isArray(uiConfig.strategies)) {
        const prev = cartStratSel.value;
        cartStratSel.innerHTML = '';
        uiConfig.strategies.forEach(s => {
          const opt = document.createElement('option');
          opt.value = s.id;
          opt.textContent = s.label;
          cartStratSel.appendChild(opt);
        });
        const defStrat = cartCfg.default_strategy || 'jan_aushadhi';
        if (prev && uiConfig.strategies.some(s => s.id === prev)) {
          cartStratSel.value = prev;
        } else if (uiConfig.strategies.some(s => s.id === defStrat)) {
          cartStratSel.value = defStrat;
        }
      }

      const billSel = document.getElementById('cartBillingMode');
      if (billSel && Array.isArray(cartCfg.billing_modes)) {
        const prevMode = billSel.value;
        billSel.innerHTML = '';
        cartCfg.billing_modes.forEach(m => {
          const opt = document.createElement('option');
          opt.value = m.id;
          opt.textContent = m.label;
          billSel.appendChild(opt);
        });
        const defMode = cartCfg.default_billing_mode || 'pack';
        if (prevMode && cartCfg.billing_modes.some(m => m.id === prevMode)) {
          billSel.value = prevMode;
        } else if (cartCfg.billing_modes.some(m => m.id === defMode)) {
          billSel.value = defMode;
        }
      }
    }

    function quickSearch(name) {
      document.getElementById('brandInput').value = name;
      const btn = document.getElementById('findAlternativesBtn');
      if (btn) btn.focus();
      showToast(`Selected "${name}" — click Find Alternatives`);
    }

    async function performSearch() {
      const brand = document.getElementById('brandInput').value.trim();
      const strategy = document.getElementById('strategySelect').value || 'max_savings';
      const resDiv = document.getElementById('searchResults');
      if (!brand) {
        resDiv.innerHTML = '<div class="alert-banner" style="margin-top: 16px;"><div>Please type a medicine name or salt first, then click <b>Find Alternatives</b>.</div></div>';
        return;
      }

      const cur = (uiConfig.search_config && uiConfig.search_config.currency_symbol) || '₹';
      resDiv.innerHTML = '<p style="color: var(--text-muted); margin-top: 16px;">Checking active ingredients, strength, and safety rules...</p>';

      try {
        const res = await fetch(`/api/substitutes?brand=${encodeURIComponent(brand)}&strategy=${encodeURIComponent(strategy)}`);
        const data = await res.json();
        lastLookupData = data;

        if (!data.original_id) {
          resDiv.innerHTML = `<div class="alert-banner" style="margin-top: 16px;"><div>Could not find <b>${escapeHtml(brand)}</b> in our retail medicine database. Please check the spelling, or search by the chemical ingredient name printed on the strip.</div></div>`;
          return;
        }

        const isPackOnly = typeof data.is_pack_only === 'boolean'
          ? data.is_pack_only
          : PACK_ONLY_FORMS.has(data.original_form);
        const unitLabel = data.unit_label || (isPackOnly ? 'pack' : 'tablet');
        const unitTitle = titleCaseLabel(unitLabel);
        const formLabel = data.original_form_label || data.original_form;
        const releaseLabel = data.original_release_label || data.original_release;
        const packDesc = data.original_pack_label || (isPackOnly ? `1 ${unitLabel}` : `${data.original_pack_size} units`);

        const ntiTag = data.is_nti
          ? '<span class="badge badge-nti" style="margin-left: 8px;">Sensitive Dose — Ask Doctor Before Switching</span>'
          : '';
        const discontinuedTag = data.is_discontinued
          ? '<span class="badge badge-discontinued" style="margin-left: 8px;">Discontinued Brand — Active Alternatives Shown Below</span>'
          : '';
        const packLabel = isPackOnly
          ? `Full Pack MRP: ${cur}${data.original_mrp.toFixed(2)} (${escapeHtml(packDesc)})`
          : `Strip MRP: ${cur}${data.original_mrp.toFixed(2)} (${escapeHtml(packDesc)}) · ${cur}${data.original_price_unit.toFixed(2)}/${escapeHtml(unitLabel)}`;

        const regOpts = uiConfig.regimen_options || {};
        const pMin = regOpts.pack_min || 1;
        const pMax = regOpts.pack_max || 24;
        const pDef = regOpts.pack_default || 1;
        const freqs = regOpts.frequencies || [];
        const durs = regOpts.durations || [];
        const defDur = regOpts.default_duration || 30;

        const addControls = isPackOnly
          ? `
            <div class="regimen-controls">
              <label for="lookupPacksQty">How many packs?</label>
              <input type="number" id="lookupPacksQty" class="inline-number" min="${pMin}" max="${pMax}" value="${pDef}">
              <span style="font-size: 12px; color: var(--text-muted);">${escapeHtml(unitLabel)}(s)</span>
              <button type="button" class="btn-primary btn-sm" onclick="addCurrentLookupToCart()">Add to Cart</button>
            </div>
          `
          : `
            <div class="regimen-controls">
              <label for="lookupFreq">Daily Dose:</label>
              <select id="lookupFreq">
                ${freqs.map(f => `<option value="${f.value}" ${Number(f.value) === 1 ? 'selected' : ''}>${escapeHtml(f.label)}</option>`).join('')}
              </select>
              <label for="lookupDays">For How Long:</label>
              <select id="lookupDays">
                ${durs.map(d => `<option value="${d.value}" ${Number(d.value) === Number(defDur) ? 'selected' : ''}>${escapeHtml(d.label)}</option>`).join('')}
              </select>
              <button type="button" class="btn-primary btn-sm" onclick="addCurrentLookupToCart()">Add to Cart</button>
            </div>
          `;

        let html = `
          <div class="med-profile-card" style="display: block;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap;">
              <div class="med-meta">
                <h3>${escapeHtml(data.original_brand)}${ntiTag}${discontinuedTag}</h3>
                <div class="med-salts">Main Ingredient: ${escapeHtml(data.original_salts)}</div>
                <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">
                  ${escapeHtml(data.original_manufacturer)} · <span class="mono">${escapeHtml(formLabel)} · ${escapeHtml(releaseLabel)}</span> · <span class="mono">${packLabel}</span>
                </div>
              </div>
              <div class="med-price-badge">
                <div class="price-sub">Current Price (1 ${escapeHtml(unitTitle)})</div>
                <div class="price-num">${cur}${data.original_price_unit.toFixed(2)}</div>
              </div>
            </div>
            <div class="add-cart-bar">
              <div style="font-size: 12px; color: var(--text-muted);">Want to add this to your medicine bill? Pick your dose:</div>
              ${addControls}
            </div>
          </div>
        `;

        if (!data.matches || data.matches.length === 0) {
          html += `<div class="alert-banner" style="margin-top: 16px;"><div><b>No cheaper exact-match alternative found for ${escapeHtml(data.original_brand)}</b> — it may already be the lowest-priced option available. You can still add it to your cart above.</div></div>`;
          resDiv.innerHTML = html;
          return;
        }

        const activeStratObj = (uiConfig.strategies || []).find(s => s.id === (data.strategy_id || strategy));
        const activeStratLabel = activeStratObj ? activeStratObj.label : (data.strategy || '');

        let janMissingBanner = '';
        if (data.strategy_id === 'jan_aushadhi' && Number(data.jan_aushadhi_count || 0) === 0) {
          janMissingBanner = `<div class="alert-banner" style="margin-top: 12px;"><div>No <b>Govt. Jan Aushadhi (PMBJP)</b> store listing was found in our catalog for this exact strength — showing the closest verified active alternatives below. You can still ask at a Jan Aushadhi Kendra using the salt name above.</div></div>`;
        }

        html += `
          <div class="results-explainer">
            <div>
              <div class="results-explainer-title">Cheaper Options With the Exact Same Medicine (${data.matches.length} found)</div>
              <div class="results-explainer-sub">Every medicine below has the <strong>exact same ingredient and strength</strong> as <strong>${escapeHtml(data.original_brand)}</strong>.</div>
            </div>
            <div class="mono" style="font-size: 11px; color: var(--accent); font-weight: 600;">Sorted by: ${escapeHtml(activeStratLabel)}</div>
          </div>
          ${janMissingBanner}
          <div class="table-container" style="margin-top: 12px;">
            <table>
              <thead>
                <tr>
                  <th>Cheaper Medicine</th>
                  <th>Company & Trust Level</th>
                  <th class="tnum" style="text-align: right;">Price (1 ${escapeHtml(unitTitle)})</th>
                  <th class="tnum" style="text-align: right;">Savings (per ${escapeHtml(unitTitle)})</th>
                  <th style="text-align: right;">Add to Bill</th>
                </tr>
              </thead>
              <tbody>
        `;

        data.matches.forEach(m => {
          const tierBadge = formatTierBadge(m.regulatory_tier);
          const subPackLabel = m.substitute_pack_label || `Pack of ${m.substitute_pack_size}`;
          const trustedTag = (data.strategy_id === 'balanced' && m.is_major_pharma && m.regulatory_tier === 'BRANDED_GENERIC')
            ? ' <span class="badge badge-who">Trusted Pharma</span>'
            : '';
          const scoreLine = data.strategy_id === 'balanced'
            ? `<div class="mono" style="font-size: 10px; color: var(--accent); margin-top: 2px;">Balance Score: ${Number(m.ranking_score || 0).toFixed(0)}/100</div>`
            : '';
          const rowHighlight = (data.strategy_id === 'jan_aushadhi' && m.regulatory_tier === 'PMBJP_JAN_AUSHADHI')
            ? ' style="background-color: var(--badge-pmbjp-bg);"'
            : '';
          html += `
            <tr${rowHighlight}>
              <td>
                <div style="font-weight: 600; color: var(--text-main);">${escapeHtml(m.substitute_brand)}</div>
                <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">${escapeHtml(subPackLabel)} · Full Pack MRP ${cur}${m.substitute_mrp.toFixed(2)}</div>
              </td>
              <td>
                ${tierBadge}${trustedTag}
                <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">${escapeHtml(m.substitute_manufacturer)}</div>
                ${scoreLine}
              </td>
              <td class="tnum" style="text-align: right; font-weight: 600;">${cur}${m.substitute_price_unit.toFixed(2)}</td>
              <td class="tnum" style="text-align: right;">
                <span class="badge badge-savings">-${m.percentage_savings.toFixed(1)}% · Save ${cur}${m.savings_per_unit.toFixed(2)} each</span>
              </td>
              <td style="text-align: right;">
                <button type="button" class="btn-secondary btn-sm" onclick="addCurrentLookupToCart('${escapeHtml(m.substitute_id)}')">+ Add to Bill</button>
              </td>
            </tr>
          `;
          if (m.warnings && m.warnings.length > 0) {
            html += `
              <tr>
                <td colspan="5" style="padding-top: 0; background-color: var(--surface);">
                  <div class="alert-banner">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="flex-shrink: 0; margin-top: 2px;"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
                    <div>${m.warnings.map(escapeHtml).join(' | ')}</div>
                  </div>
                </td>
              </tr>
            `;
          }
        });

        html += '</tbody></table></div>';
        resDiv.innerHTML = html;
      } catch (e) {
        resDiv.innerHTML = `<div class="alert-banner" style="margin-top: 16px;">Error processing formulary query: ${escapeHtml(e.message)}</div>`;
      }
    }

    function addCurrentLookupToCart(preferredSubId = '') {
      if (!lastLookupData || !lastLookupData.original_id) return;
      const isPackOnly = typeof lastLookupData.is_pack_only === 'boolean'
        ? lastLookupData.is_pack_only
        : PACK_ONLY_FORMS.has(lastLookupData.original_form);
      const regOpts = uiConfig.regimen_options || {};
      const pMin = regOpts.pack_min || 1;
      const pMax = regOpts.pack_max || 24;
      let unitsPerDay = 1;
      let durationDays = regOpts.default_duration || 30;
      let freqLabel = '1 pack';

      if (isPackOnly) {
        const qtyEl = document.getElementById('lookupPacksQty');
        const parsedQty = qtyEl ? parseInt(qtyEl.value, 10) || 1 : 1;
        durationDays = Math.min(pMax, Math.max(pMin, parsedQty));
        unitsPerDay = 1;
        freqLabel = `${durationDays} pack${durationDays > 1 ? 's' : ''}`;
      } else {
        const freqSel = document.getElementById('lookupFreq');
        const daysSel = document.getElementById('lookupDays');
        unitsPerDay = freqSel ? parseInt(freqSel.value, 10) || 1 : 1;
        durationDays = daysSel ? parseInt(daysSel.value, 10) || (regOpts.default_duration || 30) : (regOpts.default_duration || 30);
        freqLabel = freqLabelFromUnits(unitsPerDay);
      }

      upsertCartItem({
        medicine_id: lastLookupData.original_id,
        brand_name: lastLookupData.original_brand,
        units_per_day: unitsPerDay,
        duration_days: durationDays,
        frequency_label: freqLabel,
        selected_substitute_id: preferredSubId || '',
      });
      showToast(`Added ${lastLookupData.original_brand} to Prescription Cart`);
    }

    function upsertCartItem(newItem) {
      const idx = prescriptionCart.findIndex(it => it.medicine_id === newItem.medicine_id);
      if (idx >= 0) {
        prescriptionCart[idx] = { ...prescriptionCart[idx], ...newItem };
      } else {
        prescriptionCart.push(newItem);
      }
      saveCartState();
      recalculateCart();
    }

    function removeCartItem(medId) {
      prescriptionCart = prescriptionCart.filter(it => it.medicine_id !== medId);
      saveCartState();
      recalculateCart();
    }

    function clearCart() {
      prescriptionCart = [];
      lastOptimizedCart = null;
      saveCartState();
      renderCartFromCache();
      showToast('Prescription Cart cleared');
    }

    function updateCartItemField(medId, field, value) {
      const item = prescriptionCart.find(it => it.medicine_id === medId);
      if (!item) return;
      const regOpts = uiConfig.regimen_options || {};
      if (field === 'duration_days') {
        const parsed = parseInt(value, 10) || 1;
        const cachedItem = lastOptimizedCart && lastOptimizedCart.items
          ? lastOptimizedCart.items.find(it => it.medicine_id === medId)
          : null;
        const isPackOnly = cachedItem ? PACK_ONLY_FORMS.has(cachedItem.dosage_form) : false;
        const minVal = isPackOnly ? (regOpts.pack_min || 1) : (regOpts.duration_min || 1);
        const maxVal = isPackOnly ? (regOpts.pack_max || 24) : (regOpts.duration_max || 365);
        item.duration_days = Math.min(maxVal, Math.max(minVal, parsed));
      } else if (field === 'units_per_day') {
        item.units_per_day = Math.max(1, parseInt(value, 10) || 1);
        item.frequency_label = freqLabelFromUnits(item.units_per_day);
      } else {
        item[field] = value;
      }
      saveCartState();
      recalculateCart();
    }

    async function recalculateCart() {
      const cDiv = document.getElementById('cartResults');
      if (!prescriptionCart || prescriptionCart.length === 0) {
        lastOptimizedCart = null;
        renderCartFromCache();
        return;
      }
      const cartStratEl = document.getElementById('cartStrategySelect');
      const defStrat = (uiConfig.cart_config && uiConfig.cart_config.default_strategy) || 'jan_aushadhi';
      const strategy = (cartStratEl && cartStratEl.value) || defStrat;
      try {
        const res = await fetch('/api/optimize-cart', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ strategy: strategy, items: prescriptionCart }),
        });
        const data = await res.json();
        lastOptimizedCart = data;
        renderCartFromCache();
      } catch (e) {
        cDiv.innerHTML = `<div class="alert-banner" style="margin-top: 16px;">Error optimizing medicine list: ${escapeHtml(e.message)}</div>`;
      }
    }

    function renderCartFromCache() {
      const cDiv = document.getElementById('cartResults');
      if (!lastOptimizedCart || !lastOptimizedCart.items || lastOptimizedCart.items.length === 0) {
        cDiv.innerHTML = `
          <div class="cart-empty">
            <strong>Your medicine list is empty.</strong> Search any medicine above, choose how many days you need it, and click <strong>Add to Cart</strong> (or <strong>+ Pick This Option</strong>).
          </div>
        `;
        return;
      }

      const cartCfg = uiConfig.cart_config || {};
      const regOpts = uiConfig.regimen_options || {};
      const cur = (uiConfig.search_config && uiConfig.search_config.currency_symbol) || '₹';
      const keepSentinel = cartCfg.keep_original_sentinel || 'KEEP_ORIGINAL';
      const billEl = document.getElementById('cartBillingMode');
      const mode = (billEl && billEl.value) || cartCfg.default_billing_mode || 'pack';
      const billingModes = cartCfg.billing_modes || [];
      const activeModeObj = billingModes.find(m => m.id === mode);
      const modeTitle = activeModeObj
        ? (activeModeObj.short_label || activeModeObj.label)
        : (mode === 'pack' ? 'Full Strips / Bottles' : 'Exact Dose Cost');

      const sum = lastOptimizedCart.summary;
      const origTotal = mode === 'pack' ? sum.original_pack_total : sum.original_unit_total;
      const optTotal = mode === 'pack' ? sum.optimized_pack_total : sum.optimized_unit_total;
      const savTotal = mode === 'pack' ? sum.pack_savings_total : sum.unit_savings_total;
      const savPct = mode === 'pack' ? sum.pack_savings_pct : sum.unit_savings_pct;
      const annualSav = mode === 'pack' ? sum.annual_projected_pack_savings : sum.annual_projected_unit_savings;

      let html = `
        <div class="metrics-row" style="margin-top: 18px;">
          <div class="stat-box">
            <div class="stat-label">Original Bill (${escapeHtml(modeTitle)})</div>
            <div class="stat-figure red tnum">${cur}${origTotal.toFixed(2)}</div>
          </div>
          <div class="stat-box">
            <div class="stat-label">New Cheaper Bill</div>
            <div class="stat-figure blue tnum">${cur}${optTotal.toFixed(2)}</div>
          </div>
          <div class="stat-box">
            <div class="stat-label">You Save</div>
            <div class="stat-figure green tnum">${cur}${savTotal.toFixed(2)} <span style="font-size: 14px; font-weight: 500;">(${savPct.toFixed(1)}%)</span></div>
          </div>
          <div class="stat-box">
            <div class="stat-label">Yearly Savings (12 Months)</div>
            <div class="stat-figure green tnum">${cur}${annualSav.toFixed(2)}</div>
          </div>
        </div>

        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>Your Medicine</th>
                <th>Dose & Days</th>
                <th>Selected Cheaper Medicine</th>
                <th class="tnum" style="text-align: right;">Old Price</th>
                <th class="tnum" style="text-align: right;">New Price</th>
                <th class="tnum" style="text-align: right;">Saved</th>
                <th class="no-print" style="text-align: center;">Remove</th>
              </tr>
            </thead>
            <tbody>
      `;

      const pMin = regOpts.pack_min || 1;
      const pMax = regOpts.pack_max || 24;
      const dMin = regOpts.duration_min || 1;
      const dMax = regOpts.duration_max || 365;
      const freqs = regOpts.frequencies || [];

      lastOptimizedCart.items.forEach(it => {
        const isPackOnly = PACK_ONLY_FORMS.has(it.dosage_form);
        const origCost = mode === 'pack' ? it.original_pack_cost : it.original_unit_cost;
        const optCost = mode === 'pack' ? it.optimized_pack_cost : it.optimized_unit_cost;
        const itemSav = mode === 'pack' ? it.pack_savings : it.unit_savings;
        const itemPct = mode === 'pack' ? it.pack_savings_pct : it.unit_savings_pct;
        const ntiFlag = it.is_nti ? ' <span class="badge badge-nti">Sensitive Dose</span>' : '';

        const fMeta = uiConfig.dosage_forms && uiConfig.dosage_forms[it.dosage_form];
        const formLabel = fMeta ? fMeta.label : it.dosage_form;
        const unitWord = fMeta ? fMeta.unit_label : (isPackOnly ? 'pack' : 'tablet');
        const unitPlural = unitWord.endsWith('s') ? unitWord : `${unitWord}s`;
        const relLabel = (uiConfig.release_types && uiConfig.release_types[it.release_type]) || it.release_type;
        const safeMedId = escapeHtml(it.medicine_id);

        const origPackNote = isPackOnly
          ? `${cur}${it.original_mrp.toFixed(2)} / ${unitWord}`
          : `${cur}${it.original_mrp.toFixed(2)} / ${it.original_pack_size} ${unitPlural}`;

        let optionsHtml = `<option value="${escapeHtml(keepSentinel)}" ${it.selected_substitute_id === keepSentinel ? 'selected' : ''}>Keep Prescribed Brand: ${escapeHtml(it.original_brand)} (${escapeHtml(origPackNote)})</option>`;
        (it.alternatives || []).forEach(alt => {
          const sel = it.selected_substitute_id === alt.id ? 'selected' : '';
          const altPackNote = isPackOnly
            ? `${cur}${alt.mrp.toFixed(2)} / ${unitWord}`
            : `${cur}${alt.mrp.toFixed(2)} / ${alt.pack_size} ${unitPlural}`;
          optionsHtml += `<option value="${escapeHtml(alt.id)}" ${sel}>${escapeHtml(alt.brand_name)} (${escapeHtml(altPackNote)} · -${alt.percentage_savings.toFixed(0)}%)</option>`;
        });

        const freqOptionsHtml = freqs.map(f => {
          const sel = Number(it.units_per_day) === Number(f.value) ? 'selected' : '';
          const lbl = f.cart_short || f.short || `${f.value}/day`;
          return `<option value="${f.value}" ${sel}>${escapeHtml(lbl)}</option>`;
        }).join('');

        const stripWord = it.optimized_packs_needed === 1 ? 'strip' : 'strips';
        const origCountLabel = isPackOnly
          ? `${it.original_packs_needed} ${unitWord}${it.original_packs_needed === 1 ? '' : 's'}`
          : `${it.original_packs_needed} ${it.original_packs_needed === 1 ? 'strip' : 'strips'}`;
        const optCountLabel = isPackOnly
          ? `${it.optimized_packs_needed} ${unitWord}${it.optimized_packs_needed === 1 ? '' : 's'}`
          : `${it.optimized_packs_needed} ${stripWord}`;

        const regimenEditor = isPackOnly
          ? `<div class="regimen-controls"><input type="number" min="${pMin}" max="${pMax}" class="inline-number" value="${it.duration_days}" onchange="updateCartItemField('${safeMedId}', 'duration_days', this.value)"><span style="font-size: 11px; color: var(--text-muted);">${escapeHtml(unitWord)}(s)</span></div>`
          : `<div class="regimen-controls"><select class="inline-select" style="width: 78px;" onchange="updateCartItemField('${safeMedId}', 'units_per_day', this.value)">${freqOptionsHtml}</select><input type="number" min="${dMin}" max="${dMax}" class="inline-number" value="${it.duration_days}" onchange="updateCartItemField('${safeMedId}', 'duration_days', this.value)"><span style="font-size: 11px; color: var(--text-muted);">days</span></div><div class="mono" style="color: var(--text-muted); margin-top: 3px;">${it.total_units} ${escapeHtml(unitPlural)} total (buy ${it.optimized_packs_needed} ${stripWord} of ${it.substitute_pack_size})</div>`;

        let savingsBadgeHtml;
        if (it.selected_substitute_id === keepSentinel) {
          savingsBadgeHtml = `<span class="badge badge-branded">Kept original</span>`;
        } else if (itemSav <= 0) {
          savingsBadgeHtml = `<span class="badge badge-branded">Same price</span>`;
        } else {
          savingsBadgeHtml = `<span class="badge badge-savings">-${cur}${itemSav.toFixed(2)} (${itemPct.toFixed(1)}%)</span>`;
        }

        html += `
          <tr>
            <td>
              <div style="font-weight: 600; color: var(--text-main);">${escapeHtml(it.original_brand)}${ntiFlag}</div>
              <div class="mono" style="color: var(--accent); margin-top: 2px;">${escapeHtml(it.salts)}</div>
              <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">${escapeHtml(formLabel)} · ${escapeHtml(relLabel)}</div>
            </td>
            <td>${regimenEditor}</td>
            <td>
              <select class="inline-select no-print" onchange="updateCartItemField('${safeMedId}', 'selected_substitute_id', this.value)">${optionsHtml}</select>
              <div style="margin-top: 4px;">${formatTierBadge(it.substitute_tier)} <span style="font-size: 11px; color: var(--text-muted);">${escapeHtml(it.substitute_brand)}</span></div>
            </td>
            <td class="tnum" style="text-align: right;">
              <div>${cur}${origCost.toFixed(2)}</div>
              <div style="font-size: 11px; color: var(--text-muted);">${escapeHtml(origCountLabel)}</div>
            </td>
            <td class="tnum" style="text-align: right; font-weight: 600;">
              <div>${cur}${optCost.toFixed(2)}</div>
              <div style="font-size: 11px; color: var(--text-muted);">${escapeHtml(optCountLabel)}</div>
            </td>
            <td class="tnum" style="text-align: right;">
              ${savingsBadgeHtml}
            </td>
            <td class="no-print" style="text-align: center;">
              <button type="button" class="icon-btn" title="Remove medicine" onclick="removeCartItem('${safeMedId}')">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
              </button>
            </td>
          </tr>
        `;
      });

      html += '</tbody></table></div>';

      if (sum.safety_alerts && sum.safety_alerts.length > 0) {
        html += '<div style="margin-top: 14px;">';
        sum.safety_alerts.forEach(alert => {
          html += `
            <div class="alert-banner">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="flex-shrink: 0; margin-top: 2px;"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
              <div>${escapeHtml(alert)}</div>
            </div>
          `;
        });
        html += '</div>';
      }

      cDiv.innerHTML = html;
    }

    async function loadCatalogMeta() {
      try {
        const res = await fetch('/api/metrics');
        const data = await res.json();
        const navCount = document.getElementById('navCatalogCount');
        if (navCount && data.catalog_count) {
          navCount.textContent = `${data.catalog_count.toLocaleString()} MEDICINES AVAILABLE`;
        }
      } catch (e) {}
    }

    function applyTheme(theme) {
      document.documentElement.setAttribute('data-theme', theme);
      try { localStorage.setItem('equimed-theme', theme); } catch(e) {}
      const icon = document.getElementById('themeIcon');
      const label = document.getElementById('themeLabel');
      if (theme === 'dark') {
        if (icon) {
          icon.innerHTML = '<circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>';
        }
        if (label) label.textContent = 'Light Mode';
      } else {
        if (icon) {
          icon.innerHTML = '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>';
        }
        if (label) label.textContent = 'Dark Mode';
      }
    }

    function toggleTheme() {
      const current = document.documentElement.getAttribute('data-theme') || 'light';
      const next = current === 'dark' ? 'light' : 'dark';
      applyTheme(next);
    }

    window.onload = function() {
      let savedTheme = 'light';
      try {
        savedTheme = localStorage.getItem('equimed-theme') || 'light';
      } catch(e) {}
      applyTheme(savedTheme);

      loadCartState();

      const bInput = document.getElementById('brandInput');
      const dList = document.getElementById('medSuggestions');
      if (bInput && dList) {
        let _searchDebounceTimer = null;
        let _searchAbortController = null;
        bInput.addEventListener('input', function() {
          const sCfg = uiConfig.search_config || {};
          const minChars = sCfg.min_query_chars || 2;
          const autoLimit = sCfg.autocomplete_limit || 15;
          const debounceMs = sCfg.debounce_ms || 180;
          const cur = sCfg.currency_symbol || '₹';

          const q = this.value.trim();
          if (_searchDebounceTimer) clearTimeout(_searchDebounceTimer);
          if (q.length < minChars) {
            if (_searchAbortController) _searchAbortController.abort();
            return;
          }
          _searchDebounceTimer = setTimeout(async () => {
            if (_searchAbortController) _searchAbortController.abort();
            _searchAbortController = new AbortController();
            try {
              const res = await fetch(`/api/search?q=${encodeURIComponent(q)}&limit=${autoLimit}`, {
                signal: _searchAbortController.signal
              });
              const items = await res.json();
              dList.innerHTML = '';
              items.forEach(item => {
                const opt = document.createElement('option');
                opt.value = item.brand_name;
                const discFlag = item.is_discontinued ? ' [Discontinued]' : '';
                const fMeta = uiConfig.dosage_forms && uiConfig.dosage_forms[item.dosage_form];
                const fLabel = fMeta ? fMeta.label : item.dosage_form;
                opt.label = `${fLabel} · ${item.manufacturer} (${cur}${item.price_per_unit.toFixed(2)})${discFlag}`;
                dList.appendChild(opt);
              });
            } catch(e) {}
          }, debounceMs);
        });
      }

      loadCatalogMeta();
      loadUiConfig().then(() => {
        if (prescriptionCart.length > 0) {
          recalculateCart();
        } else {
          renderCartFromCache();
        }
        const resDiv = document.getElementById('searchResults');
        if (resDiv && !resDiv.innerHTML.trim()) {
          resDiv.innerHTML = '<div class="cart-empty" style="margin-top: 16px;">Choose a medicine and sort option above, then click <strong>Find Alternatives</strong>.</div>';
        }
      });
    };
  </script>
</body>
</html>
"""


class EquiMedHTTPRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for REST API and embedded UI."""

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default stdout access log for silent testing."""
        pass

    def send_json(self, data: Any, status: int = 200) -> None:
        payload = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path in ("/", "/index.html"):
            content = HTML_TEMPLATE.replace("{{CATALOG_COUNT}}", f"{_repo.count():,}").encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        elif path == "/api/ui-config":
            self.send_json(_build_ui_config())

        elif path == "/api/search":
            q = query.get("q", [""])[0]
            raw_limit = query.get("limit", [10])[0]
            try:
                limit = int(raw_limit)
                if limit <= 0:
                    limit = 10
            except (ValueError, TypeError):
                limit = 10
            results = _repo.search_by_brand(q, limit=limit)
            self.send_json([m.to_dict() for m in results])

        elif path == "/api/substitutes":
            brand = query.get("brand", [""])[0].strip()
            if not brand:
                self.send_json({"error": "Missing required query parameter 'brand'", "matches": []}, status=400)
                return

            strategy_name = query.get("strategy", ["max_savings"])[0]
            strategy = get_strategy(strategy_name)

            matches = _engine.find_substitutes(brand, strategy=strategy)
            orig = matches[0].original_medicine if matches else _repo.get_by_brand_exact(brand)
            if not orig:
                hits = _repo.search_by_brand(brand, limit=1)
                orig = hits[0] if hits else None

            if not orig:
                self.send_json({"matches": [], "original_brand": brand})
                return

            salts_str = ", ".join(
                f"{s.name} {int(s.strength_value) if float(s.strength_value).is_integer() else s.strength_value}{s.strength_unit}"
                for s in orig.salts
            )

            orig_form_meta = _FORM_DISPLAY_META.get(
                orig.dosage_form, {"label": orig.dosage_form.value, "unit_label": "unit"}
            )
            orig_is_pack_only = orig.dosage_form in SafetyEngine.PACK_ONLY_FORMS

            if isinstance(strategy, JanAushadhiFirstStrategy):
                strategy_id = "jan_aushadhi"
            elif isinstance(strategy, ReputationBalancedStrategy):
                strategy_id = "balanced"
            else:
                strategy_id = "max_savings"

            jan_count = sum(
                1 for m in matches
                if m.substitute_medicine.regulatory_tier == RegulatoryTier.PMBJP_JAN_AUSHADHI
            )

            enriched_matches = [
                {
                    **m.to_dict(),
                    "substitute_pack_size": m.substitute_medicine.pack_size,
                    "substitute_pack_label": _format_pack_label(m.substitute_medicine),
                    "substitute_mrp": m.substitute_medicine.mrp,
                    "dosage_form": m.substitute_medicine.dosage_form.value,
                    "is_major_pharma": is_major_pharma(m.substitute_medicine.manufacturer),
                    "substitute_form_label": _FORM_DISPLAY_META.get(
                        m.substitute_medicine.dosage_form,
                        {"label": m.substitute_medicine.dosage_form.value},
                    )["label"],
                    "substitute_tier_label": _TIER_DISPLAY_META.get(
                        m.substitute_medicine.regulatory_tier,
                        {"label": m.substitute_medicine.regulatory_tier.value},
                    )["label"],
                }
                for m in matches
            ]

            resp = {
                "original_id": orig.id,
                "original_brand": orig.brand_name,
                "original_manufacturer": orig.manufacturer,
                "original_salts": salts_str,
                "original_form": orig.dosage_form.value,
                "original_form_label": orig_form_meta["label"],
                "original_release": orig.release_type.value,
                "original_release_label": _RELEASE_DISPLAY_LABELS.get(
                    orig.release_type, orig.release_type.value
                ),
                "original_pack_size": orig.pack_size,
                "original_pack_label": _format_pack_label(orig),
                "original_mrp": orig.mrp,
                "original_price_unit": orig.price_per_unit,
                "is_pack_only": orig_is_pack_only,
                "unit_label": orig_form_meta["unit_label"],
                "is_nti": orig.is_narrow_therapeutic_index,
                "is_discontinued": orig.is_discontinued,
                "original_source": orig.source,
                "strategy": strategy.name,
                "strategy_id": strategy_id,
                "jan_aushadhi_count": jan_count,
                "matches": enriched_matches,
            }
            self.send_json(resp)

        elif path == "/api/baskets":
            all_baskets = PrescriptionOptimizer.load_chronic_baskets(_baskets_path, _repo)
            resp = [
                {
                    "basket_id": b["basket_id"],
                    "patient_profile": b["patient_profile"],
                    "description": b.get("description", ""),
                    "items_count": len(b.get("items", [])),
                }
                for b in all_baskets
            ]
            self.send_json(resp)

        elif path == "/api/optimize-basket":
            basket_id = query.get("basket_id", ["BASKET-01"])[0]
            strategy_name = query.get("strategy", ["max_savings"])[0]
            strategy = get_strategy(strategy_name)
            all_baskets = PrescriptionOptimizer.load_chronic_baskets(_baskets_path, _repo)
            target = next((b for b in all_baskets if b["basket_id"] == basket_id), None)
            if not target:
                self.send_json({"error": f"Basket '{basket_id}' not found."}, status=404)
                return

            res = _optimizer.optimize_basket(
                basket_id=target["basket_id"],
                patient_profile=target["patient_profile"],
                items=target["items"],
                strategy=strategy,
            )
            payload = res.to_dict()
            payload["strategy"] = strategy.name
            self.send_json(payload)

        elif path == "/api/metrics":
            self.send_json({
                "catalog_count": _repo.count(),
                "savings": _savings.get_metrics(),
                "safety": _safety_alerts.get_summary(),
                "audit_entries_count": len(_audit.get_logs()),
            })

        else:
            self.send_json({"error": "Endpoint not found"}, status=404)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/optimize-cart":
            try:
                content_len = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                content_len = 0

            if content_len <= 0 or content_len > 1_000_000:
                self.send_json({"error": "Invalid or missing request body"}, status=400)
                return

            raw_body = self.rfile.read(content_len)
            try:
                payload = json.loads(raw_body.decode("utf-8"))
            except Exception:
                self.send_json({"error": "Malformed JSON payload"}, status=400)
                return

            if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
                self.send_json({"error": "Payload must contain an 'items' list"}, status=400)
                return

            strategy_name = str(payload.get("strategy", "jan_aushadhi"))
            strategy = get_strategy(strategy_name)
            result = _optimizer.optimize_custom_cart(payload["items"], strategy=strategy)
            self.send_json(result)
        else:
            self.send_json({"error": "Endpoint not found"}, status=404)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def run_server(port: int = 8000) -> None:
    server = ThreadingHTTPServer(("0.0.0.0", port), EquiMedHTTPRequestHandler)
    print(f"🚀 EquiMed HTTP Server running on http://localhost:{port} ({_repo.count():,} formulations)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        server.server_close()


if __name__ == "__main__":
    try:
        port = int(os.environ.get("PORT", "8000"))
    except ValueError:
        port = 8000
    run_server(port)
