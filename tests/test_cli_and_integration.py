"""End-to-End Integration and CLI Testing Suite."""

import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from src.cli import cmd_chronic_baskets, cmd_search, cmd_substitutes, get_default_repo
from src.models import RegulatoryTier
from src.observer import AuditLogObserver, SafetyAlertObserver, SavingsTrackerObserver
from src.optimizer import PrescriptionOptimizer
from src.repository import MedicineRepository
from src.search_engine import SearchEngine
from src.strategy import JanAushadhiFirstStrategy


class DummyArgs:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class TestCliAndIntegration(unittest.TestCase):
    def setUp(self):
        self.repo = get_default_repo()
        self.audit = AuditLogObserver()
        self.savings = SavingsTrackerObserver()
        self.safety = SafetyAlertObserver()

        self.engine = SearchEngine(self.repo)
        self.engine.attach(self.audit)
        self.engine.attach(self.savings)
        self.engine.attach(self.safety)

    def test_repository_initialization_catalog_size(self):
        self.assertGreaterEqual(self.repo.count(), 30)

    def test_cli_search_command_output(self):
        args = DummyArgs(query=["Augmentin"])
        stdout_trap = io.StringIO()
        with patch("sys.stdout", stdout_trap):
            cmd_search(args, self.repo, self.engine)

        out = stdout_trap.getvalue()
        self.assertIn("Augmentin 625 Duo", out)
        self.assertIn("Found", out)

    def test_cli_substitutes_command_output(self):
        args = DummyArgs(brand=["Telma", "40"], strategy="max_savings")
        stdout_trap = io.StringIO()
        with patch("sys.stdout", stdout_trap):
            cmd_substitutes(args, self.repo, self.engine)

        out = stdout_trap.getvalue()
        self.assertIn("Telmisartan", out)
        self.assertIn("Best Option", out)
        self.assertIn("DISCLAIMER", out)

    def test_cli_chronic_baskets_command_output(self):
        args = DummyArgs()
        stdout_trap = io.StringIO()
        with patch("sys.stdout", stdout_trap):
            cmd_chronic_baskets(args, self.repo, self.engine)

        out = stdout_trap.getvalue()
        self.assertIn("TOTAL MONTHLY EXPENDITURE", out)
        self.assertIn("AVERAGE SAVINGS", out)
        self.assertIn("ANNUAL SAVINGS", out)

    def test_end_to_end_patient_flow(self):
        # 1. User searches for high cost brand
        found_meds = self.repo.search_by_brand("Pan-D")
        self.assertGreater(len(found_meds), 0)
        orig_med = found_meds[0]

        # 2. Engine finds generic substitutes (MaxSavings default + Jan Aushadhi priority)
        subs = self.engine.find_substitutes(orig_med)
        self.assertGreater(len(subs), 0)
        self.assertGreater(subs[0].percentage_savings, 50.0)

        jan_subs = self.engine.find_substitutes(orig_med, strategy=JanAushadhiFirstStrategy())
        self.assertGreater(len(jan_subs), 0)
        best_jan = jan_subs[0]
        self.assertIn(
            best_jan.substitute_medicine.regulatory_tier,
            (RegulatoryTier.PMBJP_JAN_AUSHADHI, RegulatoryTier.WHO_GMP_GENERIC),
        )
        self.assertGreater(best_jan.percentage_savings, 50.0)

        # 3. Audit trail reflects the operation
        logs = self.audit.get_logs()
        self.assertTrue(any(l["data"].get("original") == "Pan-D" for l in logs))


if __name__ == "__main__":
    unittest.main()
