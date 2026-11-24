"""Integration and unit tests for the EquiMed embedded HTTP server and REST API."""

import io
import json
import unittest

from src.server import EquiMedHTTPRequestHandler


class DummyServer:
    """Mock server container for BaseHTTPRequestHandler."""
    pass


class MockSocket:
    """Mock socket stream that captures request and response in-memory."""
    def __init__(self, raw_req: bytes):
        self.rfile = io.BytesIO(raw_req)
        self.wfile = io.BytesIO()

    def makefile(self, mode, *args, **kwargs):
        if "b" in mode:
            return self.rfile if "r" in mode else self.wfile
        raise ValueError(f"Unsupported mode: {mode}")

    def sendall(self, data):
        self.wfile.write(data)


class TestEquiMedServer(unittest.TestCase):
    def _request(self, method: str, path: str, body_data=None):
        if body_data is not None:
            raw_payload = body_data.encode("utf-8") if isinstance(body_data, str) else json.dumps(body_data).encode("utf-8")
            req_bytes = (
                f"{method} {path} HTTP/1.1\r\n"
                f"Host: localhost\r\n"
                f"Content-Type: application/json\r\n"
                f"Content-Length: {len(raw_payload)}\r\n\r\n"
            ).encode("utf-8") + raw_payload
        else:
            req_bytes = f"{method} {path} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode("utf-8")
        sock = MockSocket(req_bytes)
        _ = EquiMedHTTPRequestHandler(sock, ("127.0.0.1", 54321), DummyServer())

        response_bytes = sock.wfile.getvalue()
        response_text = response_bytes.decode("utf-8", errors="replace")

        # Parse response status line, headers, and body
        parts = response_text.split("\r\n\r\n", 1)
        headers_part = parts[0]
        body = parts[1] if len(parts) > 1 else ""

        header_lines = headers_part.split("\r\n")
        status_line = header_lines[0]
        status_code = int(status_line.split(" ")[1])

        headers = {}
        for line in header_lines[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()

        return status_code, headers, body

    def test_get_root_html(self):
        status, headers, body = self._request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers.get("content-type", ""))
        self.assertIn("EquiMed-India", body)
        self.assertIn("Generic Drug Substitution", body)

    def test_get_index_html(self):
        status, headers, body = self._request("GET", "/index.html")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers.get("content-type", ""))

    def test_api_search_valid(self):
        status, headers, body = self._request("GET", "/api/search?q=Telma")
        self.assertEqual(status, 200)
        self.assertIn("application/json", headers.get("content-type", ""))
        items = json.loads(body)
        self.assertIsInstance(items, list)
        self.assertGreater(len(items), 0)
        self.assertTrue(any("Telma" in item["brand_name"] for item in items))

    def test_api_search_with_limit(self):
        status, _, body = self._request("GET", "/api/search?q=Telma&limit=1")
        self.assertEqual(status, 200)
        items = json.loads(body)
        self.assertLessEqual(len(items), 1)

    def test_api_search_invalid_limit_fallback(self):
        # Invalid integer for limit should default gracefully to 10 without 500 crash
        status, _, body = self._request("GET", "/api/search?q=Telma&limit=invalid_number")
        self.assertEqual(status, 200)
        items = json.loads(body)
        self.assertIsInstance(items, list)

    def test_api_substitutes_valid(self):
        status, headers, body = self._request("GET", "/api/substitutes?brand=Telma%2040&strategy=max_savings")
        self.assertEqual(status, 200)
        self.assertIn("application/json", headers.get("content-type", ""))
        payload = json.loads(body)
        self.assertEqual(payload["original_brand"], "Telma 40")
        self.assertIn("matches", payload)
        self.assertGreater(len(payload["matches"]), 0)
        top = payload["matches"][0]
        self.assertIn("substitute_brand", top)
        self.assertGreater(top["percentage_savings"], 70.0)

    def test_api_substitutes_strategy_selection(self):
        top_brands = {}
        for strat in ("max_savings", "jan_aushadhi", "balanced"):
            status, _, body = self._request("GET", f"/api/substitutes?brand=Dolo%20650&strategy={strat}")
            self.assertEqual(status, 200)
            payload = json.loads(body)
            self.assertEqual(payload["strategy_id"], strat)
            self.assertIn("jan_aushadhi_count", payload)
            self.assertGreater(len(payload["matches"]), 0)
            self.assertIn("is_major_pharma", payload["matches"][0])
            top_brands[strat] = payload["matches"][0]["substitute_brand"]

        # Verify Jan Aushadhi prioritizes PMBJP when available
        _, _, jan_body = self._request("GET", "/api/substitutes?brand=Telma%2040&strategy=jan_aushadhi")
        jan_payload = json.loads(jan_body)
        self.assertEqual(jan_payload["strategy"], "Jan Aushadhi (PMBJP) Priority")
        self.assertEqual(jan_payload["matches"][0]["regulatory_tier"], "PMBJP_JAN_AUSHADHI")
        self.assertGreater(jan_payload["jan_aushadhi_count"], 0)
        self.assertGreater(len(set(top_brands.values())), 1)

    def test_api_substitutes_missing_brand_param(self):
        status, _, body = self._request("GET", "/api/substitutes")
        self.assertEqual(status, 400)
        payload = json.loads(body)
        self.assertIn("error", payload)

    def test_api_substitutes_nonexistent_brand(self):
        status, _, body = self._request("GET", "/api/substitutes?brand=NonExistentPharmaMoleculeX")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(len(payload["matches"]), 0)

    def test_api_baskets_list(self):
        status, headers, body = self._request("GET", "/api/baskets")
        self.assertEqual(status, 200)
        self.assertIn("application/json", headers.get("content-type", ""))
        baskets = json.loads(body)
        self.assertIsInstance(baskets, list)
        self.assertGreaterEqual(len(baskets), 20)
        first = baskets[0]
        self.assertIn("basket_id", first)
        self.assertIn("patient_profile", first)

    def test_api_optimize_basket_valid(self):
        status, _, body = self._request("GET", "/api/optimize-basket?basket_id=BASKET-01")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["basket_id"], "BASKET-01")
        self.assertEqual(payload["strategy"], "Maximum Cost Savings")
        self.assertGreater(payload["monthly_savings_amount"], 0)
        self.assertGreater(payload["monthly_savings_percentage"], 75.0)

    def test_api_optimize_basket_with_strategy(self):
        status, _, body = self._request("GET", "/api/optimize-basket?basket_id=BASKET-01&strategy=jan_aushadhi")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["basket_id"], "BASKET-01")
        self.assertEqual(payload["strategy"], "Jan Aushadhi (PMBJP) Priority")
        self.assertGreater(payload["monthly_savings_amount"], 0)

    def test_api_optimize_basket_invalid_id(self):
        status, _, body = self._request("GET", "/api/optimize-basket?basket_id=INVALID-BASKET-99")
        self.assertEqual(status, 404)
        payload = json.loads(body)
        self.assertIn("error", payload)

    def test_api_metrics_endpoint(self):
        status, _, body = self._request("GET", "/api/metrics")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertIn("catalog_count", payload)
        self.assertGreaterEqual(payload["catalog_count"], 1000)
        self.assertIn("savings", payload)
        self.assertIn("safety", payload)
        self.assertIn("audit_entries_count", payload)

    def test_api_optimize_cart_valid_and_pack_math(self):
        status, headers, body = self._request(
            "POST",
            "/api/optimize-cart",
            body_data={
                "strategy": "jan_aushadhi",
                "items": [
                    {"brand_name": "Telma 40", "units_per_day": 1, "duration_days": 30},
                    {"brand_name": "Augmentin 625 Duo", "units_per_day": 2, "duration_days": 7},
                    {"brand_name": "Calpol 250 Pediatric Suspension (60ml)", "units_per_day": 1, "duration_days": 1},
                ],
            },
        )
        self.assertEqual(status, 200)
        self.assertIn("application/json", headers.get("content-type", ""))
        payload = json.loads(body)
        self.assertEqual(payload["summary"]["item_count"], 3)
        self.assertGreater(payload["summary"]["pack_savings_total"], 0.0)
        # Augmentin: 14 units / pack_size 10 -> 2 packs needed
        aug = payload["items"][1]
        self.assertEqual(aug["total_units"], 14)
        self.assertEqual(aug["original_packs_needed"], 2)

    def test_api_optimize_cart_invalid_payload(self):
        status, _, body = self._request("POST", "/api/optimize-cart", body_data="{not-json")
        self.assertEqual(status, 400)
        self.assertIn("error", json.loads(body))

    def test_api_ui_config(self):
        status, headers, body = self._request("GET", "/api/ui-config")
        self.assertEqual(status, 200)
        self.assertIn("application/json", headers.get("content-type", ""))
        cfg = json.loads(body)
        self.assertGreater(len(cfg.get("presets", [])), 0)
        self.assertTrue(all("brand_name" in p and "label" in p for p in cfg["presets"]))
        self.assertTrue(bool(cfg.get("default_query")))
        self.assertEqual(len(cfg.get("strategies", [])), 3)
        self.assertEqual(
            set(cfg.get("pack_only_forms", [])),
            {"SYRUP", "INHALER", "INJECTION", "DROPS", "OINTMENT"},
        )
        self.assertIn("PMBJP_JAN_AUSHADHI", cfg.get("regulatory_tiers", {}))
        self.assertIn("frequencies", cfg.get("regimen_options", {}))
        self.assertEqual(cfg["regimen_options"].get("duration_min"), 1)
        self.assertEqual(cfg["regimen_options"].get("duration_max"), 365)
        self.assertIn("debounce_ms", cfg.get("search_config", {}))
        cart_cfg = cfg.get("cart_config", {})
        self.assertEqual(cart_cfg.get("default_strategy"), "jan_aushadhi")
        self.assertEqual(cart_cfg.get("keep_original_sentinel"), "KEEP_ORIGINAL")
        self.assertEqual(len(cart_cfg.get("billing_modes", [])), 2)

    def test_api_substitutes_plain_english_fields(self):
        status, _, body = self._request("GET", "/api/substitutes?brand=Telma%2040")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertFalse(payload["is_pack_only"])
        self.assertEqual(payload["unit_label"], "tablet")
        self.assertEqual(payload["original_form_label"], "Tablet")
        self.assertEqual(payload["original_release_label"], "Normal Release")
        self.assertIn("original_pack_label", payload)
        self.assertGreater(len(payload["matches"]), 0)
        self.assertIn("substitute_pack_label", payload["matches"][0])
        self.assertIn("substitute_tier_label", payload["matches"][0])

        status_s, _, body_s = self._request(
            "GET",
            "/api/substitutes?brand=Calpol%20250%20Pediatric%20Suspension%20(60ml)",
        )
        self.assertEqual(status_s, 200)
        syrup_payload = json.loads(body_s)
        self.assertTrue(syrup_payload["is_pack_only"])
        self.assertEqual(syrup_payload["unit_label"], "bottle")
        self.assertEqual(syrup_payload["original_form_label"], "Syrup / Liquid")
        if syrup_payload["matches"]:
            self.assertNotEqual(syrup_payload["matches"][0]["substitute_pack_label"], "Pack of 1")

    def test_root_html_no_hardcoded_lookup_presets_or_old_count(self):
        status, _, body = self._request("GET", "/")
        self.assertEqual(status, 200)
        self.assertNotIn("1,021 FORMULATIONS ACTIVE", body)
        self.assertIn("Search Any Medicine & Find Cheaper Options", body)
        self.assertIn("MEDICINES AVAILABLE", body)
        self.assertNotIn("onclick=\"quickSearch('Telma 40')\"", body)

    def test_root_html_cart_revamped_and_chronic_section_removed(self):
        status, _, body = self._request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("My Medicine Bill & Total Savings", body)
        self.assertNotIn('id="chronicPanel"', body)
        self.assertNotIn("Chronic Therapy Regimen Simulation", body)
        self.assertNotIn("33 CLINICAL SCENARIOS", body)
        self.assertNotIn('<option value="jan_aushadhi">', body)

    def test_root_html_search_waits_for_find_alternatives_button(self):
        status, _, body = self._request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn('id="findAlternativesBtn"', body)
        self.assertIn('onclick="performSearch()"', body)
        self.assertNotIn('onchange="performSearch()"', body)
        self.assertNotIn('onsubmit="event.preventDefault(); performSearch();"', body)

    def test_api_404_not_found(self):
        status, _, body = self._request("GET", "/api/non_existent_route")
        self.assertEqual(status, 404)
        payload = json.loads(body)
        self.assertIn("error", payload)


if __name__ == "__main__":
    unittest.main()
