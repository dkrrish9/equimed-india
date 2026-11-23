"""Unit tests for SearchEngine and Observer notifications."""

import unittest
from pathlib import Path
from src.observer import AuditLogObserver, SafetyAlertObserver, SavingsTrackerObserver
from src.repository import MedicineRepository
from src.search_engine import SearchEngine
from src.strategy import MaxSavingsStrategy


class TestSearchEngine(unittest.TestCase):
    def setUp(self):
        self.repo = MedicineRepository()
        catalog_path = Path(__file__).resolve().parent.parent / "data" / "medicine_catalog.json"
        self.repo.load_from_json(catalog_path)

        self.audit = AuditLogObserver()
        self.savings = SavingsTrackerObserver()
        self.safety = SafetyAlertObserver()

        self.engine = SearchEngine(self.repo)
        self.engine.attach(self.audit)
        self.engine.attach(self.savings)
        self.engine.attach(self.safety)

    def test_find_substitutes_for_telma_40(self):
        matches = self.engine.find_substitutes("Telma 40")
        self.assertGreater(len(matches), 0)
        top = matches[0]
        self.assertEqual(top.original_medicine.brand_name, "Telma 40")
        self.assertGreater(top.percentage_savings, 70.0)
        self.assertTrue(top.safety_verdict.is_safe)

    def test_find_substitutes_for_combination_drug_augmentin(self):
        matches = self.engine.find_substitutes("Augmentin 625 Duo")
        self.assertGreater(len(matches), 0)
        # All substitutes must contain both Amoxicillin and Clavulanic Acid
        for m in matches:
            salt_names = [s.name.lower() for s in m.substitute_medicine.salts]
            self.assertTrue(any("amoxicillin" in s for s in salt_names))
            self.assertTrue(any("clavulanic" in s or "clavulanate" in s for s in salt_names))

    def test_observer_events_triggered(self):
        self.audit.clear()
        self.savings.reset()

        matches = self.engine.find_substitutes("Pan-D")
        self.assertGreater(len(matches), 0)

        # Verify audit observer recorded entries
        logs = self.audit.get_logs()
        self.assertGreater(len(logs), 0)
        event_types = [l["event_type"] for l in logs]
        self.assertIn("SUBSTITUTION_FOUND", event_types)

        # Verify savings tracker updated
        metrics = self.savings.get_metrics()
        self.assertGreater(metrics["total_substitutions_found"], 0)
        self.assertGreater(metrics["cumulative_potential_savings"], 0.0)

    def test_nti_warning_notification(self):
        # Searching for Thyronorm 50 should trigger NTI alert
        matches = self.engine.find_substitutes("Thyronorm 50")
        self.assertGreater(len(matches), 0)
        summary = self.safety.get_summary()
        self.assertGreater(summary["nti_alerts_count"], 0)

    def test_unknown_medicine_returns_empty(self):
        matches = self.engine.find_substitutes("NonExistentMiracleDrug 9000")
        self.assertEqual(len(matches), 0)

    def test_min_savings_filter(self):
        # Set threshold to 85%: only substitutions with >= 85% savings should be returned
        matches = self.engine.find_substitutes("Telma 40", min_savings_percentage=85.0)
        for m in matches:
            self.assertGreaterEqual(m.percentage_savings, 85.0)


if __name__ == "__main__":
    unittest.main()
