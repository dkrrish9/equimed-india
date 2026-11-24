"""Zero-dependency embedded HTTP server & Interactive Web UI for EquiMed."""

from __future__ import annotations

import json
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# Ensure project root is in sys.path when executed directly
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from typing import Any, Dict

from src.models import PrescriptionItem
from src.observer import AuditLogObserver, SafetyAlertObserver, SavingsTrackerObserver
from src.optimizer import PrescriptionOptimizer
from src.repository import MedicineRepository
from src.safety_engine import SafetyEngine
from src.search_engine import SearchEngine
from src.strategy import get_strategy

# Global state instances
_repo = MedicineRepository()
_catalog_path = Path(__file__).resolve().parent.parent / "data" / "medicine_catalog.json"
_baskets_path = Path(__file__).resolve().parent.parent / "data" / "chronic_baskets.json"
_repo.load_from_json(_catalog_path)

_audit = AuditLogObserver()
_savings = SavingsTrackerObserver()
_safety_alerts = SafetyAlertObserver()

_engine = SearchEngine(_repo)
_engine.attach(_audit)
_engine.attach(_savings)
_engine.attach(_safety_alerts)

_optimizer = PrescriptionOptimizer(_engine)


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
      .navbar, #lookupPanel, #chronicPanel, footer, .no-print, .toast-notice { display: none !important; }
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
        <span>Generic Drug Substitution & Formulary Affordability Optimizer</span>
      </div>
    </div>
    <div class="nav-meta">
      <div class="meta-stat">
        <span class="status-dot"></span>
        <span id="navCatalogCount" class="mono">1,021 FORMULATIONS ACTIVE</span>
      </div>
      <div class="meta-stat">
        <span class="mono">CDSCO / IP 2026</span>
      </div>
      <button class="theme-toggle" onclick="scrollToCart()" aria-label="Jump to Prescription Cart">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="9" cy="21" r="1"></circle><circle cx="20" cy="21" r="1"></circle>
          <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"></path>
        </svg>
        <span>Prescription Cart</span>
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

    <!-- Section 1: Formulary Search -->
    <section id="lookupPanel" class="panel">
      <div class="view-header">
        <div>
          <h2 class="section-title">Formulary Bioequivalence Lookup</h2>
          <p class="section-desc">Search by brand name or active chemical salt, inspect bioequivalent alternatives, and add to your prescription cart.</p>
        </div>
      </div>

      <!-- Quick Presets -->
      <div class="presets-row">
        <span class="presets-label">Formulation Presets:</span>
        <span class="chip" onclick="quickSearch('Telma 40')">Telma 40</span>
        <span class="chip" onclick="quickSearch('Glycomet-GP 2')">Glycomet-GP 2</span>
        <span class="chip" onclick="quickSearch('Augmentin 625 Duo')">Augmentin 625</span>
        <span class="chip" onclick="quickSearch('Foracort 200 Inhaler (120 MDI)')">Foracort 200 Inhaler</span>
        <span class="chip" onclick="quickSearch('Lantus SoloSTAR Pen (3ml)')">Lantus Injection</span>
        <span class="chip" onclick="quickSearch('Calpol 250 Pediatric Suspension (60ml)')">Calpol 250 Syrup</span>
        <span class="chip" onclick="quickSearch('Vigamox 0.5% Eye Drops (5ml)')">Vigamox Drops</span>
        <span class="chip" onclick="quickSearch('Thyronorm 50')">Thyronorm 50 (NTI)</span>
      </div>

      <!-- Search Inputs -->
      <form class="search-row" onsubmit="event.preventDefault(); performSearch();">
        <div class="input-wrapper">
          <svg class="input-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
          <input type="text" id="brandInput" list="medSuggestions" autocomplete="off" placeholder="Search brand or chemical salt (e.g., Telma 40, Acetaminophen, Budesonide)..." value="Telma 40" onkeydown="if(event.key === 'Enter'){ event.preventDefault(); performSearch(); }">
          <datalist id="medSuggestions"></datalist>
        </div>
        <select id="strategySelect" aria-label="Ranking Strategy" onchange="performSearch()">
          <option value="max_savings">Maximum Price Savings</option>
          <option value="jan_aushadhi">Jan Aushadhi (PMBJP) Priority</option>
          <option value="balanced">Balanced (Savings + Quality Tier)</option>
        </select>
        <button type="submit" class="btn-primary">
          <span>Analyze</span>
        </button>
      </form>

      <!-- Results Slot -->
      <div id="searchResults"></div>
    </section>

    <!-- Section 2: Complete Prescription Cart -->
    <section id="cartPanel" class="panel">
      <div class="print-only-header">
        <h2>EquiMed-India · Verified Generic Prescription & Counter Dispensing Slip</h2>
        <p style="font-size: 12px; color: #475569; margin-top: 4px;">Bioequivalent substitutes validated under CDSCO / Indian Pharmacopoeia standards. Show active salt names to your PMBJP Jan Aushadhi Kendra or licensed pharmacist.</p>
      </div>
      <div class="view-header no-print">
        <div>
          <h2 class="section-title">Prescription Cart & Dispensing Ledger</h2>
          <p class="section-desc">Build a complete prescription bill comparing branded MRP against verified generic alternatives across strips, packs, syrups, and inhalers.</p>
        </div>
        <div class="regimen-controls">
          <select id="cartStrategySelect" aria-label="Cart Optimization Strategy" onchange="recalculateCart()">
            <option value="jan_aushadhi">Jan Aushadhi (PMBJP) Priority</option>
            <option value="max_savings">Maximum Price Savings</option>
            <option value="balanced">Balanced Quality & Savings</option>
          </select>
          <select id="cartBillingMode" aria-label="Billing Calculation Basis" onchange="renderCartFromCache()">
            <option value="pack">Billing: Retail Strips / Packs</option>
            <option value="unit">Billing: Exact Unit Cost</option>
          </select>
          <button class="btn-secondary btn-sm" onclick="window.print()">Print Counter Slip</button>
          <button class="btn-secondary btn-sm" onclick="clearCart()">Clear Cart</button>
        </div>
      </div>

      <div id="cartResults"></div>
    </section>

    <!-- Section 3: Chronic Disease Baskets -->
    <section id="chronicPanel" class="panel">
      <div class="view-header">
        <div>
          <h2 class="section-title">Chronic Therapy Regimen Simulation</h2>
          <p class="section-desc">Evaluate 30-day and annual out-of-pocket savings across 33 multi-morbidity patient scenarios, or load any regimen into your Prescription Cart.</p>
        </div>
        <div id="basketCountBadge" class="mono" style="color: var(--text-muted); font-size: 11px;">
          33 CLINICAL SCENARIOS
        </div>
      </div>

      <div style="display: flex; gap: 12px; margin-top: 16px; flex-wrap: wrap;">
        <select id="basketSelect" style="flex: 1; min-width: 260px;" aria-label="Select Patient Profile" onchange="runBasketSimulation()"></select>
        <button class="btn-primary" onclick="runBasketSimulation()">
          <span>Simulate</span>
        </button>
        <button class="btn-secondary" onclick="loadBasketIntoCart()">
          <span>Load Regimen into Cart</span>
        </button>
      </div>

      <div id="basketResults"></div>
    </section>

  </main>

  <div id="toastNotice" class="toast-notice"></div>

  <footer>
    <div>EquiMed-India · Indian Institute of Information Technology, Lucknow (Software Engineering Laboratory)</div>
    <div class="mono">Deterministic Verification · Zero-Hallucination Bioequivalence</div>
  </footer>

  <script>
    const PACK_ONLY_FORMS = new Set(['SYRUP', 'INHALER', 'INJECTION', 'DROPS', 'OINTMENT']);
    let prescriptionCart = [];
    let lastOptimizedCart = null;
    let lastLookupData = null;

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
      if (tier === 'PMBJP_JAN_AUSHADHI') return '<span class="badge badge-pmbjp">PMBJP Jan Aushadhi</span>';
      if (tier === 'WHO_GMP_GENERIC') return '<span class="badge badge-who">WHO-GMP Generic</span>';
      if (tier === 'CDSCO_APPROVED_GENERIC') return '<span class="badge badge-cdsco">CDSCO Approved Generic</span>';
      if (tier === 'BRANDED_GENERIC') return '<span class="badge badge-branded">Branded Generic</span>';
      return '<span class="badge badge-branded">Prescribed Brand</span>';
    }

    function freqLabelFromUnits(units) {
      if (units === 1) return '1-0-0 (OD)';
      if (units === 2) return '1-0-1 (BD)';
      if (units === 3) return '1-1-1 (TDS)';
      if (units === 4) return '1-1-1-1 (QID)';
      return `${units}/day`;
    }

    async function quickSearch(name) {
      document.getElementById('brandInput').value = name;
      performSearch();
    }

    async function performSearch() {
      const brand = document.getElementById('brandInput').value.trim();
      const strategy = document.getElementById('strategySelect').value;
      const resDiv = document.getElementById('searchResults');
      if (!brand) return;

      resDiv.innerHTML = '<p style="color: var(--text-muted); margin-top: 16px;">Executing clinical validation rules and scanning database index...</p>';

      try {
        const res = await fetch(`/api/substitutes?brand=${encodeURIComponent(brand)}&strategy=${strategy}`);
        const data = await res.json();
        lastLookupData = data;

        if (!data.original_id) {
          resDiv.innerHTML = `<div class="alert-banner" style="margin-top: 16px;">No medicine matching <b>${brand}</b> was found in the catalog. Try a brand name (e.g., Telma 40) or chemical salt (e.g., Paracetamol, Budesonide).</div>`;
          return;
        }

        const isPackOnly = PACK_ONLY_FORMS.has(data.original_form);
        const ntiTag = data.is_nti ? '<span class="badge badge-nti" style="margin-left: 8px;">Narrow Therapeutic Index (NTI)</span>' : '';
        const packLabel = isPackOnly
          ? `Pack MRP: ₹${data.original_mrp.toFixed(2)} (1 ${data.original_form.toLowerCase()})`
          : `Strip MRP: ₹${data.original_mrp.toFixed(2)} (${data.original_pack_size} units) · ₹${data.original_price_unit.toFixed(2)}/unit`;

        const addControls = isPackOnly
          ? `
            <div class="regimen-controls">
              <label for="lookupPacksQty">Quantity (Packs):</label>
              <select id="lookupPacksQty">
                <option value="1">1 pack / bottle / inhaler</option>
                <option value="2">2 packs</option>
                <option value="3">3 packs</option>
              </select>
              <button type="button" class="btn-primary btn-sm" onclick="addCurrentLookupToCart()">Add to Cart</button>
            </div>
          `
          : `
            <div class="regimen-controls">
              <label for="lookupFreq">Dosage:</label>
              <select id="lookupFreq">
                <option value="1" selected>1-0-0 (Once Daily)</option>
                <option value="2">1-0-1 (Twice Daily)</option>
                <option value="3">1-1-1 (Thrice Daily)</option>
                <option value="4">Four Times Daily</option>
              </select>
              <label for="lookupDays">Duration:</label>
              <select id="lookupDays">
                <option value="5">5 days</option>
                <option value="7">7 days</option>
                <option value="10">10 days</option>
                <option value="15">15 days</option>
                <option value="30" selected>30 days (Chronic)</option>
                <option value="90">90 days (Quarterly)</option>
              </select>
              <button type="button" class="btn-primary btn-sm" onclick="addCurrentLookupToCart()">Add to Cart</button>
            </div>
          `;

        let html = `
          <div class="med-profile-card" style="display: block;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap;">
              <div class="med-meta">
                <h3>${data.original_brand}${ntiTag}</h3>
                <div class="med-salts">Active API: ${data.original_salts}</div>
                <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">
                  ${data.original_manufacturer} · <span class="mono">${data.original_form} · ${data.original_release}</span> · <span class="mono">${packLabel}</span>
                </div>
              </div>
              <div class="med-price-badge">
                <div class="price-sub">Originator Unit Price</div>
                <div class="price-num">₹${data.original_price_unit.toFixed(2)}</div>
              </div>
            </div>
            <div class="add-cart-bar">
              <div style="font-size: 12px; color: var(--text-muted);">Configure prescribed dosage & add directly to your patient cart:</div>
              ${addControls}
            </div>
          </div>
        `;

        if (!data.matches || data.matches.length === 0) {
          html += `<div class="alert-banner" style="margin-top: 16px;">No cheaper bioequivalent generic substitute is available for <b>${data.original_brand}</b> (it may already be the lowest-cost formulation in its class). You can still add it to your cart above.</div>`;
          resDiv.innerHTML = html;
          return;
        }

        html += `
          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th>Generic Formulation</th>
                  <th>Manufacturer & Quality Certification</th>
                  <th class="tnum" style="text-align: right;">Pack / Unit Price</th>
                  <th class="tnum" style="text-align: right;">Net Patient Savings</th>
                  <th style="text-align: right;">Action</th>
                </tr>
              </thead>
              <tbody>
        `;

        data.matches.forEach(m => {
          const tierBadge = formatTierBadge(m.regulatory_tier);
          html += `
            <tr>
              <td>
                <div style="font-weight: 600; color: var(--text-main);">${m.substitute_brand}</div>
                <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">Pack of ${m.substitute_pack_size} · MRP ₹${m.substitute_mrp.toFixed(2)}</div>
              </td>
              <td>
                ${tierBadge}
                <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">${m.substitute_manufacturer}</div>
              </td>
              <td class="tnum" style="text-align: right; font-weight: 600;">₹${m.substitute_price_unit.toFixed(2)}</td>
              <td class="tnum" style="text-align: right;">
                <span class="badge badge-savings">-${m.percentage_savings.toFixed(1)}% (₹${m.savings_per_unit.toFixed(2)})</span>
              </td>
              <td style="text-align: right;">
                <button type="button" class="btn-secondary btn-sm" onclick="addCurrentLookupToCart('${m.substitute_id}')">+ Use in Cart</button>
              </td>
            </tr>
          `;
          if (m.warnings && m.warnings.length > 0) {
            html += `
              <tr>
                <td colspan="5" style="padding-top: 0; background-color: var(--surface);">
                  <div class="alert-banner">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="flex-shrink: 0; margin-top: 2px;"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
                    <div>${m.warnings.join(' | ')}</div>
                  </div>
                </td>
              </tr>
            `;
          }
        });

        html += '</tbody></table></div>';
        resDiv.innerHTML = html;
      } catch (e) {
        resDiv.innerHTML = `<div class="alert-banner" style="margin-top: 16px;">Error processing formulary query: ${e.message}</div>`;
      }
    }

    function addCurrentLookupToCart(preferredSubId = '') {
      if (!lastLookupData || !lastLookupData.original_id) return;
      const isPackOnly = PACK_ONLY_FORMS.has(lastLookupData.original_form);
      let unitsPerDay = 1;
      let durationDays = 30;
      let freqLabel = '1 pack';

      if (isPackOnly) {
        const qtySel = document.getElementById('lookupPacksQty');
        durationDays = qtySel ? parseInt(qtySel.value, 10) || 1 : 1;
        unitsPerDay = 1;
        freqLabel = `${durationDays} pack${durationDays > 1 ? 's' : ''}`;
      } else {
        const freqSel = document.getElementById('lookupFreq');
        const daysSel = document.getElementById('lookupDays');
        unitsPerDay = freqSel ? parseInt(freqSel.value, 10) || 1 : 1;
        durationDays = daysSel ? parseInt(daysSel.value, 10) || 30 : 30;
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
      if (field === 'duration_days' || field === 'units_per_day') {
        item[field] = Math.max(1, parseInt(value, 10) || 1);
        if (field === 'units_per_day') {
          item.frequency_label = freqLabelFromUnits(item.units_per_day);
        }
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
      const strategy = document.getElementById('cartStrategySelect').value;
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
        cDiv.innerHTML = `<div class="alert-banner" style="margin-top: 16px;">Error optimizing prescription cart: ${e.message}</div>`;
      }
    }

    function renderCartFromCache() {
      const cDiv = document.getElementById('cartResults');
      if (!lastOptimizedCart || !lastOptimizedCart.items || lastOptimizedCart.items.length === 0) {
        cDiv.innerHTML = `
          <div class="cart-empty">
            <strong>Your prescription cart is empty.</strong> Search any medicine above to configure dosage & add it, or load one of the 33 chronic therapy scenarios below.
          </div>
        `;
        return;
      }

      const mode = document.getElementById('cartBillingMode').value;
      const sum = lastOptimizedCart.summary;
      const origTotal = mode === 'pack' ? sum.original_pack_total : sum.original_unit_total;
      const optTotal = mode === 'pack' ? sum.optimized_pack_total : sum.optimized_unit_total;
      const savTotal = mode === 'pack' ? sum.pack_savings_total : sum.unit_savings_total;
      const savPct = mode === 'pack' ? sum.pack_savings_pct : sum.unit_savings_pct;
      const annualSav = mode === 'pack' ? sum.annual_projected_pack_savings : sum.annual_projected_unit_savings;
      const modeTitle = mode === 'pack' ? 'Retail Strip / Pack MRP' : 'Exact Clinical Unit Cost';

      let html = `
        <div class="metrics-row" style="margin-top: 18px;">
          <div class="stat-box">
            <div class="stat-label">Branded Bill (${modeTitle})</div>
            <div class="stat-figure red tnum">₹${origTotal.toFixed(2)}</div>
          </div>
          <div class="stat-box">
            <div class="stat-label">EquiMed Generic Bill</div>
            <div class="stat-figure blue tnum">₹${optTotal.toFixed(2)}</div>
          </div>
          <div class="stat-box">
            <div class="stat-label">Prescription Savings</div>
            <div class="stat-figure green tnum">₹${savTotal.toFixed(2)} <span style="font-size: 14px; font-weight: 500;">(${savPct.toFixed(1)}%)</span></div>
          </div>
          <div class="stat-box">
            <div class="stat-label">Annualized Projection (12x)</div>
            <div class="stat-figure green tnum">₹${annualSav.toFixed(2)}</div>
          </div>
        </div>

        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>Prescribed Drug & Generic Salt</th>
                <th>Regimen / Qty</th>
                <th>Counter Substitution Choice</th>
                <th class="tnum" style="text-align: right;">Branded</th>
                <th class="tnum" style="text-align: right;">Generic Bill</th>
                <th class="tnum" style="text-align: right;">Saved</th>
                <th class="no-print" style="text-align: center;">Remove</th>
              </tr>
            </thead>
            <tbody>
      `;

      lastOptimizedCart.items.forEach(it => {
        const isPackOnly = PACK_ONLY_FORMS.has(it.dosage_form);
        const origCost = mode === 'pack' ? it.original_pack_cost : it.original_unit_cost;
        const optCost = mode === 'pack' ? it.optimized_pack_cost : it.optimized_unit_cost;
        const itemSav = mode === 'pack' ? it.pack_savings : it.unit_savings;
        const itemPct = mode === 'pack' ? it.pack_savings_pct : it.unit_savings_pct;
        const ntiFlag = it.is_nti ? ' <span class="badge badge-nti">NTI</span>' : '';

        let optionsHtml = `<option value="KEEP_ORIGINAL" ${it.selected_substitute_id === 'KEEP_ORIGINAL' ? 'selected' : ''}>Keep Brand: ${it.original_brand} (₹${it.original_mrp.toFixed(2)}/${it.original_pack_size}u)</option>`;
        it.alternatives.forEach(alt => {
          const sel = it.selected_substitute_id === alt.id ? 'selected' : '';
          optionsHtml += `<option value="${alt.id}" ${sel}>${alt.brand_name} (₹${alt.mrp.toFixed(2)}/${alt.pack_size}u · -${alt.percentage_savings.toFixed(0)}%)</option>`;
        });

        const regimenEditor = isPackOnly
          ? `<div class="regimen-controls"><input type="number" min="1" max="24" class="inline-number" value="${it.duration_days}" onchange="updateCartItemField('${it.medicine_id}', 'duration_days', this.value)"><span style="font-size: 11px; color: var(--text-muted);">pack(s)</span></div>`
          : `<div class="regimen-controls"><select class="inline-select" style="width: 82px;" onchange="updateCartItemField('${it.medicine_id}', 'units_per_day', this.value)"><option value="1" ${it.units_per_day === 1 ? 'selected' : ''}>OD (1/d)</option><option value="2" ${it.units_per_day === 2 ? 'selected' : ''}>BD (2/d)</option><option value="3" ${it.units_per_day === 3 ? 'selected' : ''}>TDS (3/d)</option><option value="4" ${it.units_per_day === 4 ? 'selected' : ''}>QID (4/d)</option></select><input type="number" min="1" max="365" class="inline-number" value="${it.duration_days}" onchange="updateCartItemField('${it.medicine_id}', 'duration_days', this.value)"><span style="font-size: 11px; color: var(--text-muted);">days</span></div><div class="mono" style="color: var(--text-muted); margin-top: 3px;">${it.total_units} units (${it.optimized_packs_needed} × ${it.substitute_pack_size}u pack)</div>`;

        html += `
          <tr>
            <td>
              <div style="font-weight: 600; color: var(--text-main);">${it.original_brand}${ntiFlag}</div>
              <div class="mono" style="color: var(--accent); margin-top: 2px;">${it.salts}</div>
              <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">${it.dosage_form} · ${it.release_type}</div>
            </td>
            <td>${regimenEditor}</td>
            <td>
              <select class="inline-select no-print" onchange="updateCartItemField('${it.medicine_id}', 'selected_substitute_id', this.value)">${optionsHtml}</select>
              <div style="margin-top: 4px;">${formatTierBadge(it.substitute_tier)} <span style="font-size: 11px; color: var(--text-muted);">${it.substitute_brand}</span></div>
            </td>
            <td class="tnum" style="text-align: right;">
              <div>₹${origCost.toFixed(2)}</div>
              <div style="font-size: 11px; color: var(--text-muted);">${it.original_packs_needed} pack(s)</div>
            </td>
            <td class="tnum" style="text-align: right; font-weight: 600;">
              <div>₹${optCost.toFixed(2)}</div>
              <div style="font-size: 11px; color: var(--text-muted);">${it.optimized_packs_needed} pack(s)</div>
            </td>
            <td class="tnum" style="text-align: right;">
              <span class="badge badge-savings">-₹${itemSav.toFixed(2)} (${itemPct.toFixed(1)}%)</span>
            </td>
            <td class="no-print" style="text-align: center;">
              <button type="button" class="icon-btn" title="Remove item" onclick="removeCartItem('${it.medicine_id}')">
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
              <div>${alert}</div>
            </div>
          `;
        });
        html += '</div>';
      }

      cDiv.innerHTML = html;
    }

    async function loadBasketIntoCart() {
      const basketId = document.getElementById('basketSelect').value;
      try {
        const res = await fetch(`/api/optimize-basket?basket_id=${encodeURIComponent(basketId)}`);
        const data = await res.json();
        if (!data.items || data.items.length === 0) return;
        data.items.forEach(it => {
          upsertCartItem({
            medicine_id: it.original_id,
            brand_name: it.original_brand,
            units_per_day: it.units_per_day || 1,
            duration_days: it.duration_days || 30,
            frequency_label: freqLabelFromUnits(it.units_per_day || 1),
            selected_substitute_id: it.substitute_id || '',
          });
        });
        showToast(`Loaded ${data.items.length} medicines from ${data.basket_id} into Cart`);
        scrollToCart();
      } catch (e) {
        showToast('Failed to load regimen into cart');
      }
    }

    async function runBasketSimulation() {
      const basketId = document.getElementById('basketSelect').value;
      const bDiv = document.getElementById('basketResults');
      bDiv.innerHTML = '<p style="color: var(--text-muted); margin-top: 16px;">Calculating prescription economics across regimen...</p>';

      try {
        const res = await fetch(`/api/optimize-basket?basket_id=${basketId}`);
        const data = await res.json();

        let html = `
          <div class="metrics-row" style="margin-top: 20px;">
            <div class="stat-box">
              <div class="stat-label">Branded Monthly Out-of-Pocket</div>
              <div class="stat-figure red tnum">₹${data.original_total_cost.toFixed(2)}</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">EquiMed Generic Spend</div>
              <div class="stat-figure blue tnum">₹${data.optimized_total_cost.toFixed(2)}</div>
            </div>
            <div class="stat-label-wrap stat-box">
              <div class="stat-label">Monthly Direct Savings</div>
              <div class="stat-figure green tnum">₹${data.monthly_savings_amount.toFixed(2)} <span style="font-size: 14px; font-weight: 500;">(${data.monthly_savings_percentage.toFixed(1)}%)</span></div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Projected Annual Household Relief</div>
              <div class="stat-figure green tnum">₹${data.annual_projected_savings.toFixed(2)}</div>
            </div>
          </div>

          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th>Prescribed Therapy Item</th>
                  <th>Bioequivalent Substitute</th>
                  <th class="tnum" style="text-align: right;">Branded Spend</th>
                  <th class="tnum" style="text-align: right;">Generic Spend</th>
                  <th class="tnum" style="text-align: right;">Patient Relief</th>
                </tr>
              </thead>
              <tbody>
        `;

        data.items.forEach(it => {
          html += `
            <tr>
              <td>
                <div style="font-weight: 600;">${it.original_brand}</div>
                <div class="mono" style="color: var(--text-muted);">${it.units_needed} units / course</div>
              </td>
              <td>
                <div style="font-weight: 600;">${it.substitute_brand}</div>
                <div style="font-size: 11px; color: var(--text-muted);">${it.manufacturer}</div>
              </td>
              <td class="tnum" style="text-align: right;">₹${it.original_cost.toFixed(2)}</td>
              <td class="tnum" style="text-align: right; font-weight: 600;">₹${it.optimized_cost.toFixed(2)}</td>
              <td class="tnum" style="text-align: right;">
                <span class="badge badge-savings">-₹${it.savings_amount.toFixed(2)} (${it.savings_percentage.toFixed(1)}%)</span>
              </td>
            </tr>
          `;
        });

        html += '</tbody></table></div>';

        if (data.safety_alerts && data.safety_alerts.length > 0) {
          html += '<div style="margin-top: 14px;">';
          data.safety_alerts.forEach(alert => {
            html += `
              <div class="alert-banner">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="flex-shrink: 0; margin-top: 2px;"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
                <div>${alert}</div>
              </div>
            `;
          });
          html += '</div>';
        }

        bDiv.innerHTML = html;
      } catch (e) {
        bDiv.innerHTML = `<div class="alert-banner" style="margin-top: 16px;">Error simulating regimen: ${e.message}</div>`;
      }
    }

    async function loadBasketsList() {
      try {
        const res = await fetch('/api/baskets');
        const list = await res.json();
        const sel = document.getElementById('basketSelect');
        const badge = document.getElementById('basketCountBadge');
        if (list && list.length > 0) {
          sel.innerHTML = '';
          list.forEach(b => {
            const opt = document.createElement('option');
            opt.value = b.basket_id;
            opt.textContent = `[${b.basket_id}] ${b.patient_profile} (${b.items_count} medications)`;
            sel.appendChild(opt);
          });
          if (badge) badge.textContent = `${list.length} CLINICAL SCENARIOS`;
        }
      } catch (e) {
        console.error('Failed to load baskets list', e);
      }
    }

    async function loadCatalogMeta() {
      try {
        const res = await fetch('/api/metrics');
        const data = await res.json();
        const navCount = document.getElementById('navCatalogCount');
        if (navCount && data.catalog_count) {
          navCount.textContent = `${data.catalog_count.toLocaleString()} FORMULATIONS ACTIVE`;
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
      if (prescriptionCart.length > 0) {
        recalculateCart();
      } else {
        renderCartFromCache();
      }

      const bInput = document.getElementById('brandInput');
      const dList = document.getElementById('medSuggestions');
      if (bInput && dList) {
        bInput.addEventListener('input', async function() {
          const q = this.value.trim();
          if (q.length < 2) return;
          try {
            const res = await fetch(`/api/search?q=${encodeURIComponent(q)}&limit=15`);
            const items = await res.json();
            dList.innerHTML = '';
            items.forEach(item => {
              const opt = document.createElement('option');
              opt.value = item.brand_name;
              opt.label = `${item.dosage_form} · ${item.manufacturer} (₹${item.price_per_unit.toFixed(2)})`;
              dList.appendChild(opt);
            });
          } catch(e) {}
        });

        bInput.addEventListener('keydown', function(e) {
          if (e.key === 'Enter') {
            e.preventDefault();
            performSearch();
          }
        });
      }

      loadCatalogMeta();
      loadBasketsList().then(() => {
        runBasketSimulation();
      });
      performSearch();
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
            content = HTML_TEMPLATE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

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

            enriched_matches = [
                {
                    **m.to_dict(),
                    "substitute_pack_size": m.substitute_medicine.pack_size,
                    "substitute_mrp": m.substitute_medicine.mrp,
                    "dosage_form": m.substitute_medicine.dosage_form.value,
                }
                for m in matches
            ]

            resp = {
                "original_id": orig.id,
                "original_brand": orig.brand_name,
                "original_manufacturer": orig.manufacturer,
                "original_salts": salts_str,
                "original_form": orig.dosage_form.value,
                "original_release": orig.release_type.value,
                "original_pack_size": orig.pack_size,
                "original_mrp": orig.mrp,
                "original_price_unit": orig.price_per_unit,
                "is_nti": orig.is_narrow_therapeutic_index,
                "strategy": strategy.name,
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
            all_baskets = PrescriptionOptimizer.load_chronic_baskets(_baskets_path, _repo)
            target = next((b for b in all_baskets if b["basket_id"] == basket_id), None)
            if not target:
                self.send_json({"error": f"Basket '{basket_id}' not found."}, status=404)
                return

            res = _optimizer.optimize_basket(
                basket_id=target["basket_id"],
                patient_profile=target["patient_profile"],
                items=target["items"],
            )
            self.send_json(res.to_dict())

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
    server = HTTPServer(("0.0.0.0", port), EquiMedHTTPRequestHandler)
    print(f"🚀 EquiMed HTTP Server running on http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        server.server_close()


if __name__ == "__main__":
    run_server(8000)
