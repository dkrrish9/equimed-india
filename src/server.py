"""Zero-dependency embedded HTTP server & Interactive Web UI for EquiMed."""

from __future__ import annotations

import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
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
  <title>EquiMed-India | Generic Drug Substitution Optimizer</title>
  <style>
    :root {
      --primary: #0284c7;
      --primary-dark: #0369a1;
      --success: #16a34a;
      --bg: #f8fafc;
      --card-bg: #ffffff;
      --text: #0f172a;
      --text-muted: #64748b;
      --border: #e2e8f0;
      --warn-bg: #fffbeb;
      --warn-border: #fde68a;
      --warn-text: #b45309;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
    body { background-color: var(--bg); color: var(--text); padding: 24px; line-height: 1.5; }
    .container { max-width: 1000px; margin: 0 auto; }
    header { text-align: center; margin-bottom: 32px; padding: 20px 0; border-bottom: 1px solid var(--border); }
    h1 { font-size: 28px; font-weight: 800; color: #0369a1; display: flex; align-items: center; justify-content: center; gap: 10px; }
    .subtitle { color: var(--text-muted); font-size: 14px; margin-top: 6px; }
    .academic-tag { display: inline-block; background: #e0f2fe; color: #0369a1; font-weight: 600; padding: 4px 12px; border-radius: 9999px; font-size: 12px; margin-top: 10px; }
    
    .card { background: var(--card-bg); border-radius: 12px; border: 1px solid var(--border); padding: 24px; margin-bottom: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
    h2 { font-size: 18px; font-weight: 700; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; color: #1e293b; }
    
    .search-box { display: flex; gap: 12px; margin-bottom: 20px; }
    input[type="text"] { flex: 1; padding: 12px 16px; border: 1px solid var(--border); border-radius: 8px; font-size: 15px; outline: none; }
    input[type="text"]:focus { border-color: var(--primary); box-shadow: 0 0 0 3px rgba(2, 132, 199, 0.15); }
    select { padding: 12px 16px; border: 1px solid var(--border); border-radius: 8px; font-size: 14px; background: white; }
    button { background: var(--primary); color: white; border: none; padding: 12px 24px; border-radius: 8px; font-weight: 600; cursor: pointer; transition: background 0.2s; }
    button:hover { background: var(--primary-dark); }
    
    .results-table { width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 14px; }
    .results-table th { background: #f1f5f9; text-align: left; padding: 12px; color: var(--text-muted); font-weight: 600; border-bottom: 2px solid var(--border); }
    .results-table td { padding: 12px; border-bottom: 1px solid var(--border); vertical-align: middle; }
    .badge { display: inline-block; padding: 3px 8px; border-radius: 6px; font-size: 12px; font-weight: 600; }
    .badge-pmbjp { background: #dcfce7; color: #15803d; }
    .badge-who { background: #e0f2fe; color: #0369a1; }
    .badge-savings { background: #ecfdf5; color: #047857; font-weight: 700; }
    
    .alert-box { background: var(--warn-bg); border: 1px solid var(--warn-border); color: var(--warn-text); padding: 12px 16px; border-radius: 8px; font-size: 13px; margin-top: 12px; }
    .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 20px; }
    .metric-card { background: #f8fafc; border: 1px solid var(--border); padding: 16px; border-radius: 8px; text-align: center; }
    .metric-value { font-size: 24px; font-weight: 800; color: var(--primary); margin-top: 4px; }
    .metric-label { font-size: 12px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }

    .quick-chips { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }
    .chip { background: #f1f5f9; padding: 6px 12px; border-radius: 20px; font-size: 13px; cursor: pointer; color: #334155; border: 1px solid var(--border); }
    .chip:hover { background: #e2e8f0; color: #0f172a; }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>💊 EquiMed-India</h1>
      <p class="subtitle">Deterministic Generic Drug Substitution & Affordability Optimizer</p>
      <span class="academic-tag">IIIT Lucknow • Software Engineering Laboratory Project</span>
    </header>

    <div class="card">
      <h2>🔍 Search Prescribed Brand</h2>
      <div class="quick-chips">
        <span style="font-size: 13px; color: var(--text-muted); align-self: center;">Try popular:</span>
        <span class="chip" onclick="quickSearch('Telma 40')">Telma 40 (BP)</span>
        <span class="chip" onclick="quickSearch('Glycomet-GP 2')">Glycomet-GP 2 (Diabetes)</span>
        <span class="chip" onclick="quickSearch('Augmentin 625 Duo')">Augmentin 625 (Antibiotic)</span>
        <span class="chip" onclick="quickSearch('Pan-D')">Pan-D (Acid Reflux)</span>
        <span class="chip" onclick="quickSearch('Atorva 10')">Atorva 10 (Cholesterol)</span>
        <span class="chip" onclick="quickSearch('Thyronorm 50')">Thyronorm 50 (Thyroid)</span>
      </div>
      <div class="search-box">
        <input type="text" id="brandInput" placeholder="Enter branded medicine name (e.g., Telma 40, Glycomet-GP 2)..." value="Telma 40">
        <select id="strategySelect">
          <option value="max_savings">Maximum Cost Savings</option>
          <option value="jan_aushadhi">Jan Aushadhi (PMBJP) Priority</option>
          <option value="balanced">Balanced (Savings + Certifications)</option>
        </select>
        <button onclick="performSearch()">Find Generics</button>
      </div>
      <div id="searchResults"></div>
    </div>

    <div class="card">
      <h2>📊 Chronic Disease Therapy Basket Simulation</h2>
      <p style="font-size: 14px; color: var(--text-muted); margin-bottom: 16px;">
        Real-world chronic patient scenarios modeled to evaluate out-of-pocket healthcare expense reduction:
      </p>
      <div style="display: flex; gap: 12px; margin-bottom: 20px;">
        <select id="basketSelect" style="flex: 1;">
          <option value="BASKET-01">Elderly Diabetic & Hypertensive Patient (Age 62)</option>
          <option value="BASKET-02">Cardiovascular Secondary Prevention (Post-Angioplasty)</option>
          <option value="BASKET-03">Geriatric Bone & Endocrine Care</option>
          <option value="BASKET-04">Acute Bacterial Infection & Fever Course</option>
        </select>
        <button onclick="runBasketSimulation()">Simulate Savings</button>
      </div>
      <div id="basketResults"></div>
    </div>
  </div>

  <script>
    async function quickSearch(name) {
      document.getElementById('brandInput').value = name;
      performSearch();
    }

    async function performSearch() {
      const brand = document.getElementById('brandInput').value.trim();
      const strategy = document.getElementById('strategySelect').value;
      const resDiv = document.getElementById('searchResults');
      if (!brand) return;

      resDiv.innerHTML = '<p style="color: #64748b;">Evaluating bioequivalence and scanning database...</p>';

      try {
        const res = await fetch(`/api/substitutes?brand=${encodeURIComponent(brand)}&strategy=${strategy}`);
        const data = await res.json();

        if (!data.matches || data.matches.length === 0) {
          resDiv.innerHTML = `<div class="alert-box">No approved generic substitutes found for <b>${brand}</b>.</div>`;
          return;
        }

        const first = data.matches[0];
        let html = `
          <div style="margin-top: 16px; padding: 16px; background: #f8fafc; border-radius: 8px; border: 1px solid var(--border);">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <div>
                <h3 style="font-size: 16px; font-weight: 700; color: #1e293b;">Prescribed: ${data.original_brand}</h3>
                <p style="font-size: 13px; color: var(--text-muted);">${data.original_salts}</p>
              </div>
              <div style="text-align: right;">
                <span style="font-size: 13px; color: var(--text-muted);">Original Unit Price:</span>
                <span style="font-size: 18px; font-weight: 700; color: #ef4444; margin-left: 6px;">₹${data.original_price_unit.toFixed(2)}</span>
              </div>
            </div>
          </div>

          <table class="results-table">
            <thead>
              <tr>
                <th>Bioequivalent Generic Substitute</th>
                <th>Manufacturer & Regulatory Tier</th>
                <th>Price / Unit</th>
                <th>Patient Savings</th>
                <th>Bioequivalence</th>
              </tr>
            </thead>
            <tbody>
        `;

        data.matches.forEach(m => {
          const tierBadge = m.regulatory_tier === 'PMBJP_JAN_AUSHADHI'
            ? '<span class="badge badge-pmbjp">Govt Jan Aushadhi</span>'
            : '<span class="badge badge-who">WHO-GMP Generic</span>';

          html += `
            <tr>
              <td>
                <b>${m.substitute_brand}</b><br>
                <small style="color: var(--text-muted);">${m.substitute_manufacturer}</small>
              </td>
              <td>${tierBadge}</td>
              <td><b>₹${m.substitute_price_unit.toFixed(2)}</b></td>
              <td><span class="badge badge-savings">🟢 ${m.percentage_savings.toFixed(1)}% (₹${m.savings_per_unit.toFixed(2)})</span></td>
              <td><span style="color: #16a34a; font-weight: 600;">✓ Verified</span></td>
            </tr>
          `;
          if (m.warnings && m.warnings.length > 0) {
            html += `
              <tr>
                <td colspan="5" style="padding-top: 0; border-top: none;">
                  <div class="alert-box" style="margin: 4px 0;">⚠️ ${m.warnings.join(' | ')}</div>
                </td>
              </tr>
            `;
          }
        });

        html += '</tbody></table>';
        resDiv.innerHTML = html;
      } catch (e) {
        resDiv.innerHTML = `<div class="alert-box">Error loading data: ${e.message}</div>`;
      }
    }

    async function runBasketSimulation() {
      const basketId = document.getElementById('basketSelect').value;
      const bDiv = document.getElementById('basketResults');
      bDiv.innerHTML = '<p style="color: #64748b;">Optimizing prescription basket...</p>';

      try {
        const res = await fetch(`/api/optimize-basket?basket_id=${basketId}`);
        const data = await res.json();

        let html = `
          <div class="metrics-grid">
            <div class="metric-card">
              <div class="metric-label">Branded Monthly Spend</div>
              <div class="metric-value" style="color: #ef4444;">₹${data.original_total_cost.toFixed(2)}</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">EquiMed Generic Spend</div>
              <div class="metric-value" style="color: #0284c7;">₹${data.optimized_total_cost.toFixed(2)}</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">Monthly Savings</div>
              <div class="metric-value" style="color: #16a34a;">₹${data.monthly_savings_amount.toFixed(2)} (${data.monthly_savings_percentage.toFixed(1)}%)</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">Annual Projected Savings</div>
              <div class="metric-value" style="color: #16a34a;">₹${data.annual_projected_savings.toFixed(2)}</div>
            </div>
          </div>

          <table class="results-table">
            <thead>
              <tr>
                <th>Prescribed Medication</th>
                <th>Generic Substitute</th>
                <th>Branded Cost</th>
                <th>Generic Cost</th>
                <th>Monthly Savings</th>
              </tr>
            </thead>
            <tbody>
        `;

        data.items.forEach(it => {
          html += `
            <tr>
              <td><b>${it.original_brand}</b> (${it.units_needed} units)</td>
              <td>${it.substitute_brand}<br><small style="color: var(--text-muted);">${it.manufacturer}</small></td>
              <td>₹${it.original_cost.toFixed(2)}</td>
              <td>₹${it.optimized_cost.toFixed(2)}</td>
              <td><span class="badge badge-savings">₹${it.savings_amount.toFixed(2)} (${it.savings_percentage.toFixed(1)}%)</span></td>
            </tr>
          `;
        });

        html += '</tbody></table>';

        if (data.safety_alerts && data.safety_alerts.length > 0) {
          html += '<div style="margin-top: 16px;">';
          data.safety_alerts.forEach(alert => {
            html += `<div class="alert-box">⚠️ ${alert}</div>`;
          });
          html += '</div>';
        }

        bDiv.innerHTML = html;
      } catch (e) {
        bDiv.innerHTML = `<div class="alert-box">Error optimizing basket: ${e.message}</div>`;
      }
    }

    // Auto-run search on load
    window.onload = function() {
      performSearch();
      runBasketSimulation();
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
            limit = int(query.get("limit", [10])[0])
            results = _repo.search_by_brand(q, limit=limit)
            self.send_json([m.to_dict() for m in results])

        elif path == "/api/substitutes":
            brand = query.get("brand", [""])[0]
            strategy_name = query.get("strategy", ["max_savings"])[0]
            strategy = get_strategy(strategy_name)

            matches = _engine.find_substitutes(brand, strategy=strategy)
            if not matches:
                self.send_json({"matches": [], "original_brand": brand})
                return

            orig = matches[0].original_medicine
            salts_str = ", ".join(f"{s.name} {s.strength_value}{s.strength_unit}" for s in orig.salts)

            resp = {
                "original_id": orig.id,
                "original_brand": orig.brand_name,
                "original_manufacturer": orig.manufacturer,
                "original_salts": salts_str,
                "original_price_unit": orig.price_per_unit,
                "strategy": strategy.name,
                "matches": [m.to_dict() for m in matches],
            }
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
                "savings": _savings.get_metrics(),
                "safety": _safety_alerts.get_summary(),
                "audit_entries_count": len(_audit.get_logs()),
            })

        else:
            self.send_json({"error": "Endpoint not found"}, status=404)


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
