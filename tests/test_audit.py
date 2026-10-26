import csv
import json
import sqlite3
import subprocess
import sys
import unittest
from pathlib import Path

class TestFreightAuditEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.data_dir = cls.root / "test_audit_data"
        cls.out_dir = cls.root / "test_audit_out"
        cls.db_path = cls.out_dir / "test_freight.db"

        # Generate data once for suite
        subprocess.run([
            sys.executable, str(cls.root / "src/generate_data.py"),
            "--scale", "starter", "--seed", "20261022", "--out", str(cls.data_dir)
        ], check=True, capture_output=True)

        subprocess.run([
            sys.executable, str(cls.root / "src/audit_invoices.py"),
            "--data", str(cls.data_dir), "--out", str(cls.out_dir)
        ], check=True, capture_output=True)

        subprocess.run([
            sys.executable, str(cls.root / "src/load_sqlite.py"),
            "--data", str(cls.data_dir), "--db", str(cls.db_path), "--outputs", str(cls.out_dir)
        ], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        import shutil
        if cls.data_dir.exists():
            shutil.rmtree(cls.data_dir, ignore_errors=True)
        if cls.out_dir.exists():
            shutil.rmtree(cls.out_dir, ignore_errors=True)

    def test_reproducibility_same_seed(self):
        """Step 10: Regenerate twice with same seed and compare SHA-256 checksums."""
        dir_a = self.root / "test_rep_a"
        dir_b = self.root / "test_rep_b"
        try:
            subprocess.run([
                sys.executable, str(self.root / "src/generate_data.py"),
                "--scale", "starter", "--seed", "20261022", "--out", str(dir_a)
            ], check=True, capture_output=True)

            subprocess.run([
                sys.executable, str(self.root / "src/generate_data.py"),
                "--scale", "starter", "--seed", "20261022", "--out", str(dir_b)
            ], check=True, capture_output=True)

            manifest_a = json.loads((dir_a / "source_manifest.json").read_text())["sha256"]
            manifest_b = json.loads((dir_b / "source_manifest.json").read_text())["sha256"]

            for tbl, hash_val in manifest_a.items():
                self.assertEqual(hash_val, manifest_b.get(tbl), f"Hash mismatch on table {tbl}")
        finally:
            import shutil
            shutil.rmtree(dir_a, ignore_errors=True)
            shutil.rmtree(dir_b, ignore_errors=True)

    def test_validation_integrity_rules(self):
        """Step 8: Run comprehensive validation checks."""
        summary_file = self.out_dir / "val_summary.json"
        subprocess.run([
            sys.executable, str(self.root / "src/validate_data.py"),
            "--data", str(self.data_dir), "--out", str(summary_file)
        ], check=True, capture_output=True)

        summary = json.loads(summary_file.read_text())
        self.assertTrue(summary["all_checks_passed"], "Not all validation checks passed")
        self.assertGreaterEqual(summary["total_checks"], 35)

    def test_ground_truth_isolation_and_recall(self):
        """Step 7 & Step 5: Ground truth isolation and 100% anomaly detection recall."""
        metrics_file = self.out_dir / "metrics.json"
        metrics = json.loads(metrics_file.read_text())

        eval_data = metrics["ground_truth_evaluation"]
        self.assertEqual(eval_data["recall"], 1.0, "Audit engine did not detect all injected anomalies")
        self.assertEqual(eval_data["precision"], 1.0, "Audit engine had false positive anomalies")
        self.assertGreaterEqual(eval_data["anomalies_injected"], 14)

        # Check all anomaly categories have 100% detection rate
        rates = eval_data["detection_rate_by_issue_type"]
        for itype, data in rates.items():
            self.assertEqual(data["rate"], 1.0, f"Detection rate for {itype} is not 100%: {data}")

    def test_dimensional_weight_formula(self):
        """Verify dimensional weight divisor 5000 and chargeable weight logic."""
        with open(self.data_dir / "shipment.csv", newline="", encoding="utf-8") as f:
            shipments = list(csv.DictReader(f))

        for s in shipments:
            l = float(s["length_cm"])
            w = float(s["width_cm"])
            h = float(s["height_cm"])
            actual = float(s["actual_weight_kg"])
            expected_dim = round((l * w * h) / 5000.0, 2)
            expected_chg = round(max(actual, expected_dim), 2)

            self.assertAlmostEqual(float(s["dimensional_weight_kg"]), expected_dim, delta=0.02)
            self.assertAlmostEqual(float(s["chargeable_weight_kg"]), expected_chg, delta=0.02)

    def test_credit_note_excess_dispute(self):
        """Acceptance Criteria: Credits reconcile to approved disputes and excess credits flagged."""
        with open(self.out_dir / "credit_note_validation.csv", newline="", encoding="utf-8") as f:
            credits = list(csv.DictReader(f))

        self.assertGreater(len(credits), 0)
        has_valid = any(c["validation_status"] == "VALID" for c in credits)
        has_excess = any(c["validation_status"] == "EXCESS_CREDIT" for c in credits)
        self.assertTrue(has_valid, "Missing valid credit notes in test dataset")
        self.assertTrue(has_excess, "Missing EXCESS_CREDIT anomaly in test dataset")

    def test_sqlite_queryability(self):
        """SQLite persistence with primary keys and relationships."""
        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        cur.execute("SELECT count(*) FROM freight_invoice WHERE status = 'RECEIVED'")
        count = cur.fetchone()[0]
        self.assertEqual(count, 150)

        # Test join between invoice, shipment, and rate card
        cur.execute("""
            SELECT i.invoice_id, s.shipment_id, r.rate_id, s.chargeable_weight_kg
            FROM freight_invoice i
            JOIN shipment s ON i.shipment_id = s.shipment_id
            JOIN rate_card r ON i.source_rate_id = r.rate_id
            LIMIT 5
        """)
        rows = cur.fetchall()
        self.assertEqual(len(rows), 5)
        con.close()

if __name__ == "__main__":
    unittest.main()
