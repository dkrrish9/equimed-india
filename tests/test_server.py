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
    def _request(self, method: str, path: str):
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
        status, _, body = self._request("GET", "/api/substitutes?brand=Telma%2040&strategy=jan_aushadhi")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["strategy"], "Jan Aushadhi (PMBJP) Priority")

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
        self.assertGreater(payload["monthly_savings_amount"], 0)
        self.assertGreater(payload["monthly_savings_percentage"], 75.0)

    def test_api_optimize_basket_invalid_id(self):
        status, _, body = self._request("GET", "/api/optimize-basket?basket_id=INVALID-BASKET-99")
        self.assertEqual(status, 404)
        payload = json.loads(body)
        self.assertIn("error", payload)

    def test_api_metrics_endpoint(self):
        status, _, body = self._request("GET", "/api/metrics")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertIn("savings", payload)
        self.assertIn("safety", payload)
        self.assertIn("audit_entries_count", payload)

    def test_api_404_not_found(self):
        status, _, body = self._request("GET", "/api/non_existent_route")
        self.assertEqual(status, 404)
        payload = json.loads(body)
        self.assertIn("error", payload)


if __name__ == "__main__":
    unittest.main()
