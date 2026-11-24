"""Comprehensive unit and integration tests for A-Z Dataset ETL & SQLite+FTS5 scaling."""

from __future__ import annotations

import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from scripts.ingest_az_dataset import ingest_az_dataset, validate_az_csv_header
from src.models import (
    DosageForm,
    Medicine,
    RegulatoryTier,
    ReleaseType,
    SaltComponent,
)
from src.observer import AuditLogObserver, SafetyAlertObserver
from src.repository import (
    MedicineRepository,
    SQLiteMedicineRepository,
    load_default_repository,
)
from src.safety_engine import SafetyEngine
from src.search_engine import SearchEngine
from src.strategy import JanAushadhiFirstStrategy, MaxSavingsStrategy

_ROOT = Path(__file__).resolve().parent.parent
_CURATED_JSON = _ROOT / "data" / "medicine_catalog.json"
_SAMPLE_CSV = _ROOT / "tests" / "fixtures" / "az_sample.csv"


class TestAZIngestionAndSQLite(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmpdir = tempfile.TemporaryDirectory()
        tmp_path = Path(cls._tmpdir.name)
        cls.db_path = tmp_path / "test_equimed.db"
        cls.report_path = tmp_path / "test_report.json"

        cls.report = ingest_az_dataset(
            csv_path=_SAMPLE_CSV,
            curated_path=_CURATED_JSON,
            out_db_path=cls.db_path,
            report_path=cls.report_path,
        )
        cls.repo = SQLiteMedicineRepository(cls.db_path)
        cls.engine = SearchEngine(cls.repo)
        cls.safety = SafetyEngine()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.repo.close()
        cls._tmpdir.cleanup()

    def test_csv_header_validation_and_ingestion_report_counts(self) -> None:
        ok, msg = validate_az_csv_header(_SAMPLE_CSV)
        self.assertTrue(ok, msg)

        self.assertEqual(self.report["curated_loaded"], 1021)
        self.assertEqual(self.report["csv_rows_read"], 33)
        self.assertEqual(self.report["az_valid_parsed"], 24)
        self.assertEqual(self.report["duplicates_curated_skipped"], 1)
        self.assertEqual(self.report["duplicates_az_skipped"], 1)
        self.assertEqual(self.report["az_inserted"], 22)
        self.assertEqual(self.report["discontinued_indexed"], 2)
        self.assertEqual(self.report["total_medicines_indexed"], 1043)

        q_reasons = self.report["quarantined_by_reason"]
        self.assertEqual(self.report["quarantined_total"], 9)
        self.assertEqual(q_reasons.get("truncated_multi_salt"), 3)
        self.assertEqual(q_reasons.get("invalid_or_missing_strength"), 1)
        self.assertEqual(q_reasons.get("invalid_price"), 2)
        self.assertEqual(q_reasons.get("non_allopathy"), 1)
        self.assertEqual(q_reasons.get("unsupported_or_unknown_form"), 2)

    def test_curated_priority_and_zero_fabricated_tiers(self) -> None:
        # Curated Telma 40 must win deduplication over fake A-Z Telma 40 (MRP 999)
        telma = self.repo.get_by_brand_exact("Telma 40")
        self.assertIsNotNone(telma)
        self.assertEqual(telma.source, "curated")
        self.assertNotEqual(telma.id, "AZ-120")

        # Non-PMBJP A-Z brand must remain BRANDED_GENERIC
        dolo_test = self.repo.get_by_id("AZ-101")
        self.assertIsNotNone(dolo_test)
        self.assertEqual(dolo_test.regulatory_tier, RegulatoryTier.BRANDED_GENERIC)
        self.assertEqual(dolo_test.pack_size, 15)
        self.assertEqual(dolo_test.price_per_unit, 2.0)

        # Explicit BPPI / Jan Aushadhi manufacturer gets PMBJP_JAN_AUSHADHI
        jan_med = self.repo.get_by_id("AZ-103")
        self.assertIsNotNone(jan_med)
        self.assertEqual(jan_med.regulatory_tier, RegulatoryTier.PMBJP_JAN_AUSHADHI)

        # Active intra-A-Z duplicate must replace discontinued duplicate
        dup_med = self.repo.get_by_brand_exact("DupBrand 10 Tablet")
        self.assertIsNotNone(dup_med)
        self.assertEqual(dup_med.id, "AZ-122")
        self.assertFalse(dup_med.is_discontinued)

    def test_edge_cases_nested_parens_release_kinetics_dr_guard_and_packs(self) -> None:
        # Nested parentheses: Cholecalciferol (Vitamin D3) (60000IU)
        d3 = self.repo.get_by_id("AZ-106")
        self.assertIsNotNone(d3)
        self.assertEqual(d3.dosage_form, DosageForm.CAPSULE)
        self.assertEqual(d3.pack_size, 4)
        self.assertEqual(d3.salts[0].normalized_key(), "cholecalciferol:60000.0:iu")

        # Multi-strip box + comma strength: 10 strips of 10 tablets, 1,000mg
        cal = self.repo.get_by_id("AZ-107")
        self.assertIsNotNone(cal)
        self.assertEqual(cal.pack_size, 100)
        self.assertEqual(cal.price_per_unit, 5.0)
        self.assertEqual(cal.salts[0].strength_value, 1000.0)

        # Leading decimal strength (.25mg)
        alpra = self.repo.get_by_id("AZ-108")
        self.assertIsNotNone(alpra)
        self.assertEqual(alpra.salts[0].strength_value, 0.25)

        # Dr. Morepen must NOT be falsely classified as ENTERIC_COATED
        dr_morepen = self.repo.get_by_id("AZ-109")
        self.assertIsNotNone(dr_morepen)
        self.assertEqual(dr_morepen.release_type, ReleaseType.IMMEDIATE_RELEASE)

        # SR / MR / DR extraction
        self.assertEqual(self.repo.get_by_id("AZ-110").release_type, ReleaseType.SUSTAINED_RELEASE)
        self.assertEqual(self.repo.get_by_id("AZ-111").release_type, ReleaseType.MODIFIED_RELEASE)
        self.assertEqual(self.repo.get_by_id("AZ-112").release_type, ReleaseType.ENTERIC_COATED)

        # Multi-salt within single composition cell + trailing '+' in comp1
        combo = self.repo.get_by_id("AZ-123")
        self.assertIsNotNone(combo)
        self.assertEqual(len(combo.salts), 2)
        aug_az = self.repo.get_by_id("AZ-102")
        self.assertIsNotNone(aug_az)
        self.assertEqual(len(aug_az.salts), 2)

        # NTI auto-detection on Warfarin Sodium
        warf = self.repo.get_by_id("AZ-124")
        self.assertIsNotNone(warf)
        self.assertTrue(warf.is_narrow_therapeutic_index)

    def test_pack_only_forms_and_container_size_warning(self) -> None:
        # Syrups, inhalers, drops, ointments, injections keep pack_size=1 and price_per_unit=mrp
        for az_id, expected_form in [
            ("AZ-113", DosageForm.SYRUP),
            ("AZ-115", DosageForm.INHALER),
            ("AZ-116", DosageForm.INHALER),
            ("AZ-117", DosageForm.DROPS),
            ("AZ-118", DosageForm.OINTMENT),
            ("AZ-119", DosageForm.INJECTION),
        ]:
            med = self.repo.get_by_id(az_id)
            self.assertIsNotNone(med)
            self.assertEqual(med.dosage_form, expected_form)
            self.assertEqual(med.pack_size, 1)
            self.assertEqual(med.price_per_unit, med.mrp)

        # Nasal spray mcg/spray must NOT match MDI inhaler mcg/puff
        puff_val, puff_unit = SafetyEngine.normalize_strength(200.0, "mcg/puff")
        spray_val, spray_unit = SafetyEngine.normalize_strength(50.0, "mcg/spray")
        self.assertEqual((puff_val, puff_unit), (200.0, "mcg/puff"))
        self.assertEqual((spray_val, spray_unit), (50.0, "mcg/spray"))
        self.assertNotEqual(puff_unit, spray_unit)

        # 60ml syrup vs 100ml syrup emits soft container-size warning
        syrup_60 = self.repo.get_by_id("AZ-113")
        syrup_100 = self.repo.get_by_id("AZ-114")
        verdict = self.safety.validate_substitution(syrup_60, syrup_100)
        self.assertTrue(verdict.is_safe)
        self.assertTrue(any("Pack/container size variation" in w for w in verdict.warnings))

    def test_discontinued_searchable_as_input_and_blocked_as_substitute(self) -> None:
        # 1. Discontinued drug IS searchable as input
        hits = self.repo.search_by_brand("OldBrand-Discontinued")
        self.assertTrue(any(m.id == "AZ-104" and m.is_discontinued for m in hits))

        old_disc = self.repo.get_by_brand_exact("OldBrand-Discontinued 625 Tablet")
        self.assertIsNotNone(old_disc)
        self.assertTrue(old_disc.is_discontinued)

        # 2. Direct SafetyEngine Rule 0b blocks discontinued candidate
        ultra_cheap_disc = self.repo.get_by_id("AZ-105")
        self.assertIsNotNone(ultra_cheap_disc)
        verdict = self.safety.validate_substitution(old_disc, ultra_cheap_disc)
        self.assertFalse(verdict.is_safe)
        self.assertIn("discontinued", verdict.rejection_reason.lower())

        # 3. SearchEngine finds active substitutes for discontinued prescribed brand,
        #    and NEVER returns AZ-105 or any discontinued medicine as a substitute
        matches = self.engine.find_substitutes(old_disc, strategy=JanAushadhiFirstStrategy())
        self.assertGreater(len(matches), 0)
        self.assertTrue(all(not m.substitute_medicine.is_discontinued for m in matches))
        self.assertFalse(any(m.substitute_medicine.id == "AZ-105" for m in matches))

        # 4. Searching active brand Augmentin-AZ 625 also never returns AZ-105
        active_matches = self.engine.find_substitutes("Augmentin-AZ 625 Tablet", strategy=MaxSavingsStrategy())
        self.assertGreater(len(active_matches), 0)
        self.assertTrue(all(not m.substitute_medicine.is_discontinued for m in active_matches))
        self.assertFalse(any(m.substitute_medicine.id == "AZ-105" for m in active_matches))

    def test_sqlite_fts5_hyphen_synonym_and_thread_safety(self) -> None:
        # Hyphen-insensitive lookup
        res_hyphen = self.repo.search_by_brand("glycomet gp 2")
        self.assertTrue(any(m.brand_name == "Glycomet-GP 2" for m in res_hyphen))

        # Canonical salt synonym lookup ("Acetaminophen" -> Paracetamol brands)
        res_salt = self.repo.search_by_brand("Acetaminophen", limit=15)
        self.assertGreater(len(res_salt), 0)
        self.assertTrue(any("paracetamol" in s.name.lower() for m in res_salt for s in m.salts))

        # FTS5 multi-token search
        res_fts = self.repo.search_by_brand("Morepen Paracetamol")
        self.assertTrue(any(m.id == "AZ-109" for m in res_fts))

        # Concurrent multi-threaded queries on SQLiteMedicineRepository
        queries = ["Telma 40", "Augmentin-AZ", "Acetaminophen", "D3-Nested", "glycomet gp 2"]
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda q: self.repo.search_by_brand(q, limit=5), queries * 4))
        self.assertEqual(len(results), 20)
        self.assertTrue(all(len(r) > 0 for r in results))

    def test_json_fallback_when_sqlite_db_missing(self) -> None:
        missing_db = Path(self._tmpdir.name) / "nonexistent_catalog.db"
        fallback_repo = load_default_repository(db_path=missing_db, json_path=_CURATED_JSON)
        self.assertIsInstance(fallback_repo, MedicineRepository)
        self.assertEqual(fallback_repo.count(), 1021)

        env_backup = os.environ.get("EQUIMED_DB_PATH")
        try:
            os.environ["EQUIMED_DB_PATH"] = str(self.db_path)
            sqlite_repo = load_default_repository()
            try:
                self.assertIsInstance(sqlite_repo, SQLiteMedicineRepository)
                self.assertEqual(sqlite_repo.count(), 1043)
            finally:
                sqlite_repo.close()
        finally:
            if env_backup is None:
                os.environ.pop("EQUIMED_DB_PATH", None)
            else:
                os.environ["EQUIMED_DB_PATH"] = env_backup

    def test_bounded_observer_deques(self) -> None:
        audit = AuditLogObserver(maxlen=5)
        safety_obs = SafetyAlertObserver(maxlen=5)
        for i in range(12):
            audit.on_event("SUBSTITUTION_FOUND", {"idx": i})
            safety_obs.on_event("SUBSTITUTION_REJECTED", {"reason": f"r{i}", "candidate": f"c{i}"})

        logs = audit.get_logs()
        self.assertIsInstance(logs, list)
        self.assertEqual(len(logs), 5)
        self.assertEqual(logs[0]["data"]["idx"], 7)
        self.assertEqual(len(audit.get_logs(limit=2)), 2)

        self.assertEqual(safety_obs.rejection_count, 12)
        self.assertEqual(len(safety_obs.warnings_logged), 5)


if __name__ == "__main__":
    unittest.main()
